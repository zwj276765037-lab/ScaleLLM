"""Exact CPU Down for GU-only format05; inputs/outputs are F16 integers.

The FPGA ABI is v7; immutable weight bytes retain W4F5 layout. No float GEMM,
weight requantization, RMSNorm or hardware DOWN command occurs here.
Legal dot<=65280, raw<=4244832000, guard<=17386831872000 and a448-group
accumulator<=7789300678656000, below S17/S33/S45/S54 and signed int64 limits.
All width checks occur before conversion. Scalar reference uses Python ints;
the blocked kernel uses signed int64 batched matmul and exact integer shifts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

import numpy as np

from . import scalellm_mlp_linear as linear
from .scalellm_artifacts import ArtifactRecord

ROWS, GROUPS, COLUMNS, LANES = 16, 448, 4096, 32


class HostDownFormatError(ValueError):
    """Malformed artifact or illegal format05 numeric input."""


def _integer_array(values, low, high, label):
    result = np.asarray(values)
    if result.dtype.kind not in "iu":
        raise TypeError(f"{label} requires integers")
    if not result.size or np.any(result < low) or np.any(result > high):
        raise HostDownFormatError(f"{label} outside [{low},{high}]")
    return result


def _immutable(values, dtype):
    array = np.asarray(values, dtype=dtype, order="C")
    # A bytes-backed view cannot be made writable by setflags(write=True).
    return np.frombuffer(array.tobytes(), dtype=dtype).reshape(array.shape)


@dataclass(frozen=True)
class DownWeights:
    """Layer-owned immutable arrays: W=(448,columns,32), code/shift=(448,columns)."""
    values: np.ndarray
    codes: np.ndarray
    shifts: np.ndarray
    source_sha256: tuple[str, ...] = ()
    layer_id: int | None = None

    def __post_init__(self):
        w = _integer_array(self.values, -8, 7, "W4")
        c = _integer_array(self.codes, 0, 255, "weight codes")
        s = _integer_array(self.shifts, 0, 63, "weight shifts")
        if w.ndim != 3 or w.shape[0] != GROUPS or w.shape[2] != LANES or not 0 < w.shape[1] <= COLUMNS:
            raise HostDownFormatError("Down weights require (448,columns<=4096,32)")
        if c.shape != w.shape[:2] or s.shape != c.shape:
            raise HostDownFormatError("weight code/shift shape mismatch")
        if np.any((c == 0) & (s != 0)):
            raise HostDownFormatError("zero weight code requires zero shift")
        if self.layer_id is not None and (type(self.layer_id) is not int or not 0 <= self.layer_id < 32):
            raise HostDownFormatError("weight layer must be in0..31")
        object.__setattr__(self, "values", _immutable(w, np.int8))
        object.__setattr__(self, "codes", _immutable(c, np.uint8))
        object.__setattr__(self, "shifts", _immutable(s, np.uint8))

    @property
    def columns(self):
        return self.values.shape[1]

    @classmethod
    def from_records(cls, c0, c1, metadata, *, columns=COLUMNS, layer_id=None):
        """Original group-major/tile16 records; half128B, metadata32B padded."""
        if type(columns) is not int or columns <= 0 or columns > COLUMNS or columns % 16:
            raise HostDownFormatError("artifact columns must be a positive multiple of16 <=4096")
        tiles = columns // 16
        record_count = GROUPS * tiles
        payloads = [bytes(memoryview(x).cast("B")) for x in (c0, c1, metadata)]
        for data, size in zip(payloads, (record_count * 128, record_count * 128, record_count * 32), strict=True):
            if len(data) != size:
                raise HostDownFormatError(f"Down artifact requires exactly {size} bytes, got {len(data)}")
        w = np.empty((GROUPS, tiles, 16, LANES), np.int8)
        for half, data in enumerate(payloads[:2]):
            packed = np.frombuffer(data, np.uint8).reshape(GROUPS, tiles, 128)
            nibble = np.empty((GROUPS, tiles, 256), np.uint8)
            nibble[..., 0::2] = packed & 15
            nibble[..., 1::2] = packed >> 4
            w[:, :, half * 8:(half + 1) * 8] = ((nibble ^ 8).astype(np.int8) - 8).reshape(GROUPS, tiles, 8, LANES)
        packed_meta = np.frombuffer(payloads[2], np.uint8).reshape(GROUPS, tiles, 32)
        if np.any(packed_meta[..., 28:]):
            raise HostDownFormatError("weight metadata padding must be zero")
        codes = packed_meta[..., :16].copy()
        shifts = np.empty(codes.shape, np.uint8)
        for col in range(16):
            byte, bit = divmod(col * 6, 8)
            word = packed_meta[..., 16 + byte].astype(np.uint16) | (packed_meta[..., 17 + byte].astype(np.uint16) << 8)
            shifts[..., col] = (word >> bit) & 63
        return cls(w.reshape(GROUPS, columns, LANES), codes.reshape(GROUPS, columns),
                   shifts.reshape(GROUPS, columns), tuple(hashlib.sha256(x).hexdigest() for x in payloads), layer_id)

    @classmethod
    def from_artifact_records(cls, c0: ArtifactRecord, c1: ArtifactRecord,
                              metadata: ArtifactRecord, *, layer_id: int):
        """Verify original size and SHA on read, then retain independent owned bytes."""
        return cls.from_records(c0.read_verified(), c1.read_verified(), metadata.read_verified(), layer_id=layer_id)


def _activation(q, metadata):
    q = _integer_array(q, 0, 255, "Down U8 q")
    m = _integer_array(metadata, 0, 0xFFFFFF, "activation metadata")
    if q.shape != (ROWS, GROUPS * LANES) or m.shape != (ROWS, GROUPS):
        raise HostDownFormatError("Down requires q=(16,14336), metadata=(16,448)")
    m = m.astype(np.int64)
    if np.any(m & 0xC00000):
        raise HostDownFormatError("activation reserved bits must be zero")
    zp, code, shift = m & 255, (m >> 8) & 255, (m >> 16) & 63
    grouped = q.reshape(ROWS, GROUPS, LANES)
    if np.any((code == 0) & ((m != 0) | np.any(grouped != 0, axis=-1))):
        raise HostDownFormatError("zero activation code must be canonical")
    return grouped.astype(np.int64) - zp[..., None], code, shift


def recover_down_guard_scalar(raw: int, total_shift: int) -> int:
    """S33 to S45/F24; arithmetic shift, without projection rounding."""
    if type(raw) is not int or not -(1 << 32) <= raw < (1 << 32):
        raise HostDownFormatError("raw does not fit S33")
    if type(total_shift) is not int or not 12 <= total_shift <= 44:
        raise HostDownFormatError("nonzero Down total shift must be in12..44")
    guard = raw << (24 - total_shift) if total_shift <= 24 else raw >> (total_shift - 24)
    if not -(1 << 44) <= guard < (1 << 44):
        raise HostDownFormatError("Down guard does not fit S45")
    return guard


def finalize_down_scalar(accumulator: int) -> int:
    if type(accumulator) is not int or not -(1 << 53) <= accumulator < (1 << 53):
        raise HostDownFormatError("Down accumulator does not fit S54")
    magnitude = (abs(accumulator) + 128) >> 8
    rounded = -magnitude if accumulator < 0 else magnitude
    return min((1 << 31) - 1, max(-(1 << 31), rounded))


def down_scalar_oracle(q, metadata, weights: DownWeights, *, rows=(0,), columns=(0,)):
    """Independent Python-int oracle; bounded outputs, all448 groups/32lanes.

    At most256 output coordinates, to avoid a0.94G-MAC scalar regression.
    This function does not call the optimized matmul or its alignment code.
    """
    _activation(q, metadata)  # validation only; math reads original q/meta.
    rows, columns = tuple(rows), tuple(columns)
    if not rows or not columns or len(rows) * len(columns) > 256:
        raise ValueError("scalar oracle requires1..256 output coordinates")
    if any(type(r) is not int or not 0 <= r < ROWS for r in rows) or any(type(c) is not int or not 0 <= c < weights.columns for c in columns):
        raise ValueError("scalar oracle coordinate out of range")
    out = np.empty((len(rows), len(columns)), np.int64)
    for ri, row in enumerate(rows):
        for ci, col in enumerate(columns):
            acc = 0
            for group in range(GROUPS):
                meta = int(metadata[row, group])
                zp, ac, ash = meta & 255, (meta >> 8) & 255, (meta >> 16) & 63
                wc, wsh = int(weights.codes[group, col]), int(weights.shifts[group, col])
                if ac == 0 or wc == 0:
                    continue
                total = ash + wsh
                if not 12 <= total <= 44:
                    raise HostDownFormatError("nonzero Down total shift must be in12..44")
                dot = sum((int(q[row, group * 32 + lane]) - zp) * int(weights.values[group, col, lane]) for lane in range(32))
                if not -(1 << 16) <= dot < (1 << 16):
                    raise HostDownFormatError("dot does not fit S17")
                raw = dot * ac * wc
                if not -(1 << 32) <= raw < (1 << 32):
                    raise HostDownFormatError("raw does not fit S33")
                guard = raw * (1 << (24 - total)) if total <= 24 else raw // (1 << (total - 24))
                if not -(1 << 44) <= guard < (1 << 44):
                    raise HostDownFormatError("guard does not fit S45")
                acc += guard
                if not -(1 << 53) <= acc < (1 << 53):
                    raise HostDownFormatError("accumulator does not fit S54")
            magnitude = (abs(acc) + 128) // 256
            value = -magnitude if acc < 0 else magnitude
            out[ri, ci] = min(2147483647, max(-2147483648, value))
    return out


def down_blocked_int64(q, metadata, weights: DownWeights, *, column_block=256,
                       group_block=8, require_production_shape=True) -> np.ndarray:
    """Exact blocked CPU Down, returns int64 carrying saturated S32/F16.

    Largest temporary is group_block*16*column_block int64 (default256KiB).
    Each group contribution is aligned before the group sum; this preserves
    arithmetic truncation, unlike applying scales after a full-matrix GEMM.
    """
    centered, ac, ash = _activation(q, metadata)
    if require_production_shape and weights.columns != COLUMNS:
        raise HostDownFormatError("production Down requires4096 output columns")
    if type(column_block) is not int or not 1 <= column_block <= COLUMNS or type(group_block) is not int or not 1 <= group_block <= GROUPS:
        raise ValueError("invalid Down block dimensions")
    out = np.zeros((ROWS, weights.columns), np.int64)
    for col in range(0, weights.columns, column_block):
        end = min(weights.columns, col + column_block)
        acc = np.zeros((ROWS, end - col), np.int64)
        for start in range(0, GROUPS, group_block):
            stop = min(GROUPS, start + group_block)
            a = centered[:, start:stop].transpose(1, 0, 2)
            w = weights.values[start:stop, col:end].astype(np.int64).transpose(0, 2, 1)
            dot = np.matmul(a, w)
            if np.any(dot < -(1 << 16)) or np.any(dot >= (1 << 16)):
                raise HostDownFormatError("dot does not fit S17")
            activation_code = ac[:, start:stop].T[..., None]
            weight_code = weights.codes[start:stop, col:end].astype(np.int64)[:, None, :]
            total = ash[:, start:stop].T[..., None] + weights.shifts[start:stop, col:end].astype(np.int64)[:, None, :]
            live = (activation_code != 0) & (weight_code != 0)
            if np.any(live & ((total < 12) | (total > 44))):
                raise HostDownFormatError("nonzero Down total shift must be in12..44")
            raw = dot * activation_code * weight_code
            if np.any(raw < -(1 << 32)) or np.any(raw >= (1 << 32)):
                raise HostDownFormatError("raw does not fit S33")
            # Zero paths need no shift and must never perform an illegal large
            # left shift. Each selected nonzero path has total in12..44.
            total = np.where(live, total, 24)
            guard = np.left_shift(raw, np.maximum(24 - total, 0))
            guard = np.right_shift(guard, np.maximum(total - 24, 0))
            if np.any(guard < -(1 << 44)) or np.any(guard >= (1 << 44)):
                raise HostDownFormatError("guard does not fit S45")
            acc += guard.sum(axis=0, dtype=np.int64)
            if np.any(acc < -(1 << 53)) or np.any(acc >= (1 << 53)):
                raise HostDownFormatError("accumulator does not fit S54")
        magnitude = (np.abs(acc) + 128) >> 8
        rounded = np.where(acc < 0, -magnitude, magnitude)
        out[:, col:end] = np.clip(rounded, -2147483648, 2147483647)
    return out


def prepare_down_arrays(gu_payload):
    """Original frozen SiLU/S32 product, wide H32/S35, checked MinMax A8."""
    gate, up = linear.unpack_gu_interleaved_s24(gu_payload)
    products = linear.silu_table_mul_exact(gate, up)
    return linear.minmax_a8_scalecode_exact(linear.hadamard32_s32_exact(products), input_bits=35)


def prepare_and_run_down(gu_payload, weights: DownWeights, **block_options):
    return down_blocked_int64(*prepare_down_arrays(gu_payload), weights, **block_options)
