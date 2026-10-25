"""Exact format05 Host boundaries for the cohort16 linear-only MLP.

Numeric APIs consume *integers in F16 units*, never floating point tensors.
``prepare_gate_up_input`` takes S24 after the existing Host RMSNorm boundary;
``prepare_gate_up_input_from_normalized_fp32`` adapts that boundary's already
normalized FP32 result. Neither function performs RMSNorm.

All vector arithmetic uses signed int64. H32's largest intermediate is
32*2**31*11585 < 2**50 (S24 uses <2**42); SiLU*Up is at most 2**46.
For S35 MinMax, H-L <2**35, 255*x and 255*(H-L) <2**43,
and twice the division remainder <2**36. Scale scanning never increases
its operand beyond 4,261,478,400. Thus no int64 intermediate can overflow.
The codecs have the production 16-row shape, independent of mlp_fixed.ROWS=8.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path

import numpy as np

ROWS = 16
HIDDEN = 4096
INTERMEDIATE = 14336
GROUP_SIZE = 32
REC576_BYTES = 576
GU_RECORD_BYTES = 768
DOWN_RECORD_BYTES = 1024
GU_PAYLOAD_BYTES = 1_376_256
DOWN_PAYLOAD_BYTES = 262_144
SCALE_EXACT_LIMIT = 4_261_478_400
SCALE_DIFF_Q16_MAX = 4_269_834_239
SILU_LIMIT_Q16 = 16 << 16
SILU_ROM_PATH = Path(__file__).resolve().parents[1] / "data/mlp_silu_q16.mem"
SILU_ROM_SHA256 = "8263e8981b637b00143c6dfd6674f2397a73c85c6ed8934f0ee839f76db6ea67"


class MLPLinearFormatError(ValueError):
    """Input violates the frozen numeric or tensor format contract."""


def _integers(values, low: int, high: int, name: str) -> np.ndarray:
    array = np.asarray(values)
    if array.dtype.kind not in "iu":
        raise TypeError(f"{name} requires an integer array in F16 units")
    if array.size == 0 or np.any(array < low) or np.any(array > high):
        raise MLPLinearFormatError(f"{name} must be nonempty and in [{low}, {high}]")
    return array.astype(np.int64, copy=False)


def _signed(values, bits: int, name: str) -> np.ndarray:
    return _integers(values, -(1 << (bits - 1)), (1 << (bits - 1)) - 1, name)


def _grouped(array: np.ndarray) -> np.ndarray:
    if array.ndim == 0 or array.shape[-1] % GROUP_SIZE:
        raise MLPLinearFormatError("last axis must contain a positive multiple of 32 lanes")
    return array.reshape(*array.shape[:-1], array.shape[-1] // GROUP_SIZE, GROUP_SIZE)


def _round_shift_away(value: np.ndarray, shift: int) -> np.ndarray:
    # Callers establish |value|<2**50, so abs and addition are int64-safe.
    magnitude = (np.abs(value) + (1 << (shift - 1))) >> shift
    return np.where(value < 0, -magnitude, magnitude)


def _hadamard32(values, input_bits: int, output_bits: int) -> np.ndarray:
    source = _signed(values, input_bits, f"H32 S{input_bits} input")
    work = _grouped(source).copy()
    distance = 1
    while distance < GROUP_SIZE:
        stage = work.reshape(*work.shape[:-1], GROUP_SIZE // (2 * distance), 2, distance)
        lhs, rhs = stage[..., 0, :].copy(), stage[..., 1, :].copy()
        stage[..., 0, :], stage[..., 1, :] = lhs + rhs, lhs - rhs
        distance *= 2
    rounded = _round_shift_away(work * 11585, 16)
    return np.clip(rounded, -(1 << (output_bits - 1)),
                   (1 << (output_bits - 1)) - 1).reshape(source.shape)


def hadamard32_s24_exact(x_s24) -> np.ndarray:
    """Five butterflies and 11585/65536 half-away normalization to S27."""
    return _hadamard32(x_s24, 24, 27)


def hadamard32_s32_exact(x_s32) -> np.ndarray:
    """S32 product to S35; preserve the wide path without S24 truncation."""
    return _hadamard32(x_s32, 32, 35)


def _round_div_even(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    quotient, remainder = np.divmod(numerator, denominator)
    twice = remainder * 2
    return quotient + ((twice > denominator) |
                       ((twice == denominator) & ((quotient & 1) != 0)))


def minmax_a8_scalecode_exact(values, *, input_bits: int = 27) -> tuple[np.ndarray, np.ndarray]:
    """Return U8 q and packed U24 metadata per last-axis group32.

    q has the input shape, metadata has shape ``input.shape[:-1]+(groups,)``.
    S35 unrepresentable groups raise before a DOWN payload can be returned.
    """
    if input_bits not in (27, 35):
        raise ValueError("A8 input_bits must be 27 or 35")
    source = _signed(values, input_bits, f"A8 S{input_bits} input")
    grouped = _grouped(source)
    low = np.minimum(grouped.min(axis=-1), 0)
    high = np.maximum(grouped.max(axis=-1), 0)
    diff = high - low
    if np.any(diff > SCALE_DIFF_Q16_MAX):
        index = tuple(int(i) for i in np.argwhere(diff > SCALE_DIFF_Q16_MAX)[0])
        raise MLPLinearFormatError(
            f"S35 scale range D={int(diff[index])} at group {index} exceeds {SCALE_DIFF_Q16_MAX}")
    nonzero = diff != 0
    divisor = np.where(nonzero, diff, 1)
    zp = np.clip(_round_div_even(-low * 255, divisor), 0, 255)
    numerator = grouped * 255 + zp[..., None] * diff[..., None]
    numerator = np.clip(numerator, 0, 255 * diff[..., None])
    quantized = _round_div_even(numerator, divisor[..., None]).astype(np.uint8)

    shifted = diff.copy()
    shift = np.zeros(diff.shape, dtype=np.int64)
    for _ in range(63):
        active = nonzero & (shift < 63) & (shifted <= SCALE_EXACT_LIMIT // 2)
        if not np.any(active):
            break
        shifted[active] *= 2
        shift[active] += 1
    code = np.where(nonzero, np.clip(_round_div_even(shifted, 255 << 16), 1, 255), 0)
    metadata = (zp | (code << 8) | (shift << 16)).astype(np.uint32)
    return quantized.reshape(source.shape), metadata


def _validate_a8(q: np.ndarray, metadata: np.ndarray) -> None:
    if np.any(metadata & 0xC00000):
        raise MLPLinearFormatError("REC576 metadata reserved bits must be zero")
    zero = ((metadata >> 8) & 255) == 0
    invalid_zero = zero & ((metadata != 0) | np.any(q != 0, axis=-1))
    if np.any(invalid_zero):
        raise MLPLinearFormatError("REC576 noncanonical zero code: q, zero_point and shift must be zero")


def pack_a8_rec576(q_u8, meta_u24) -> bytes:
    """Pack (16, groups*32) q and (16, groups) metadata, group-major.

    Single-group metadata may have shape (16,). Padding/reserved/canonical
    zero checks also apply to callers supplying pre-quantized arrays.
    """
    q = _integers(q_u8, 0, 255, "REC576 q")
    metadata = _integers(meta_u24, 0, 0xFFFFFF, "REC576 metadata")
    if q.ndim != 2 or q.shape[0] != ROWS or q.shape[1] % GROUP_SIZE:
        raise MLPLinearFormatError("REC576 q shape must be (16, groups*32)")
    groups = q.shape[1] // GROUP_SIZE
    if metadata.shape == (ROWS,) and groups == 1:
        metadata = metadata[:, None]
    if metadata.shape != (ROWS, groups):
        raise MLPLinearFormatError("REC576 metadata shape must be (16, groups)")
    grouped = q.reshape(ROWS, groups, GROUP_SIZE)
    _validate_a8(grouped, metadata)
    records = np.zeros((groups, REC576_BYTES), dtype=np.uint8)
    records[:, :512] = grouped.transpose(1, 0, 2).reshape(groups, 512)
    wire_meta = metadata.T
    for byte in range(3):
        records[:, 512 + byte:560:3] = (wire_meta >> (8 * byte)) & 255
    return records.tobytes()


def _payload_bytes(payload, expected: int, name: str) -> np.ndarray:
    view = memoryview(payload).cast("B")
    if len(view) != expected:
        raise MLPLinearFormatError(f"{name} requires exactly {expected} bytes, got {len(view)}")
    return np.frombuffer(view, dtype=np.uint8)


def unpack_a8_rec576(payload, *, groups: int) -> tuple[np.ndarray, np.ndarray]:
    """Strictly decode exactly groups records; return row-major arrays."""
    if isinstance(groups, bool) or not isinstance(groups, (int, np.integer)) or groups <= 0:
        raise ValueError("groups must be a positive integer")
    records = _payload_bytes(payload, int(groups) * REC576_BYTES, "REC576").reshape(groups, REC576_BYTES)
    if np.any(records[:, 560:]):
        raise MLPLinearFormatError("REC576 padding must be zero")
    packed = records[:, 512:560].reshape(groups, ROWS, 3).astype(np.uint32)
    metadata = (packed[..., 0] | (packed[..., 1] << 8) | (packed[..., 2] << 16)).T.copy()
    q = records[:, :512].reshape(groups, ROWS, GROUP_SIZE).transpose(1, 0, 2).copy()
    _validate_a8(q, metadata)
    return q.reshape(ROWS, groups * GROUP_SIZE), metadata


def unpack_gu_interleaved_s24(payload) -> tuple[np.ndarray, np.ndarray]:
    """G0,U0,...,G895,U895 to independent (16,14336) S24 arrays."""
    packed = _payload_bytes(payload, GU_PAYLOAD_BYTES, "GU S24").reshape(896, 2, ROWS, 16, 3).astype(np.int64)
    raw = packed[..., 0] | (packed[..., 1] << 8) | (packed[..., 2] << 16)
    signed = (raw ^ 0x800000) - 0x800000
    return tuple(signed[:, matrix].transpose(1, 0, 2).reshape(ROWS, INTERMEDIATE).copy()
                 for matrix in range(2))


def unpack_down_s32(payload) -> np.ndarray:
    """Tile16-major little-endian S32 output to integer (16,4096)."""
    raw = _payload_bytes(payload, DOWN_PAYLOAD_BYTES, "Down S32")
    return raw.view("<i4").reshape(256, ROWS, 16).transpose(1, 0, 2).reshape(ROWS, HIDDEN).astype(np.int64)


@lru_cache(maxsize=1)
def load_silu_rom() -> tuple[int, ...]:
    """Load the frozen 8192-word ROM and append RTL's implicit top entry."""
    data = SILU_ROM_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != SILU_ROM_SHA256:
        raise MLPLinearFormatError("SiLU ROM SHA256 differs from frozen format05 table")
    words = data.split()
    if len(words) != 8192:
        raise MLPLinearFormatError("SiLU ROM requires 8192 stored entries")
    raw = [int(word, 16) for word in words]
    if any(word < 0 or word > 0xFFFFFF for word in raw):
        raise MLPLinearFormatError("SiLU ROM word does not fit 24 bits")
    return tuple((word ^ 0x800000) - 0x800000 for word in raw) + (SILU_LIMIT_Q16,)


def silu_table_mul_exact(gate_s24, up_s24) -> np.ndarray:
    """Frozen SiLU address rounding/endpoints, S48 multiply, S32/F16 result."""
    gate = _signed(gate_s24, 24, "SiLU gate")
    up = _signed(up_s24, 24, "SiLU up")
    if gate.shape != up.shape:
        raise MLPLinearFormatError("Gate and Up shapes must match")
    address = np.clip((gate + SILU_LIMIT_Q16 + 128) >> 8, 0, 8192)
    silu = np.asarray(load_silu_rom(), dtype=np.int64)[address]
    silu = np.where(gate <= -SILU_LIMIT_Q16, 0,
                    np.where(gate >= SILU_LIMIT_Q16, gate, silu))
    product = _round_shift_away(silu * up, 16)
    return _signed(product, 32, "SwiGLU S32 output")


def s24_from_normalized_fp32(normalized_fp32) -> np.ndarray:
    """Adapt existing already-normalized FP32 (16,4096), without RMSNorm.

    Preserve the existing FP32 scale/half-away boundary and saturate S24.
    Clip before int64 conversion so even extreme finite FP32 inputs saturate.
    """
    values = np.asarray(normalized_fp32)
    if values.dtype != np.dtype(np.float32):
        raise TypeError("normalized boundary requires float32")
    if values.shape != (ROWS, HIDDEN) or not np.all(np.isfinite(values)):
        raise MLPLinearFormatError("normalized FP32 boundary requires finite (16,4096)")
    clipped = np.clip(values, np.float32(-128), np.float32(128))
    magnitude = np.floor(np.abs(clipped) * np.float32(65536) + np.float32(0.5))
    rounded = np.copysign(magnitude, clipped)
    return np.clip(rounded, -(1 << 23), (1 << 23) - 1).astype(np.int64)


def prepare_gate_up_input(x_s24) -> bytes:
    """Prepare exactly cohort16x4096 post-RMSNorm S24 integers for GU."""
    source = _signed(x_s24, 24, "GU input")
    if source.shape != (ROWS, HIDDEN):
        raise MLPLinearFormatError("GU S24 input shape must be (16,4096)")
    return pack_a8_rec576(*minmax_a8_scalecode_exact(hadamard32_s24_exact(source)))


def prepare_gate_up_input_from_normalized_fp32(normalized_fp32) -> bytes:
    """Adapt the existing FP32 RMSNorm result once, then prepare GU."""
    return prepare_gate_up_input(s24_from_normalized_fp32(normalized_fp32))


def prepare_down_input(gu_payload) -> bytes:
    """Decode full GU, table SwiGLU, wide H32 and checked S35 A8 for DOWN."""
    gate, up = unpack_gu_interleaved_s24(gu_payload)
    product = silu_table_mul_exact(gate, up)
    return pack_a8_rec576(*minmax_a8_scalecode_exact(
        hadamard32_s32_exact(product), input_bits=35))
