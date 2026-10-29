"""DDR-local final decode16 layout and exact host tensor boundaries.

The six staging buffers are transfer buffers, not logical request slots.  Each
buffer holds all sixteen independent request rows.  DDR0 owns Attention and
KV; DDR1 owns the online MLP and the existing staged GU weights.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ROWS = 16
HIDDEN = 4096
INTERMEDIATE = 14336
LAYERS = 32
BUFFER_COUNT = 6
APERTURE = 0x80000000
INPUT_BYTES = ROWS * HIDDEN * 3
ATTENTION_OUTPUT_BYTES = INPUT_BYTES
MLP_OUTPUT_BYTES = ROWS * INTERMEDIATE * 4
ATTENTION_HALF_BYTES = 0x01400000
ATTENTION_META_BYTES = 0x00280000
GU_HALF_BYTES = 0x01C00000
GU_META_BYTES = 0x00700000
ROPE_BASE = 0x57000000
ROPE_BYTES = 8192
KV_BASE = 0x60000000
KV_BYTES = 0x10000000


def index(value: int, count: int, name: str) -> int:
    if type(value) is not int or not 0 <= value < count:
        raise ValueError(f"{name} must be an integer in 0..{count - 1}")
    return value


@dataclass(frozen=True)
class Span:
    name: str
    channel: int
    address: int
    size: int
    alignment: int = 32

    def __post_init__(self) -> None:
        index(self.channel, 2, "DDR channel")
        if (type(self.address) is not int or type(self.size) is not int
                or self.address < 0 or self.size <= 0
                or self.address + self.size > APERTURE
                or self.alignment <= 0 or self.address % self.alignment):
            raise ValueError(f"invalid DDR span: {self!r}")

    @property
    def host_address(self) -> int:
        return self.channel * APERTURE + self.address


def layer_spans(layer: int) -> dict[str, Span]:
    index(layer, LAYERS, "layer")
    return {
        "attention_c0": Span("attention_c0", 0, layer * 0x02800000,
                             ATTENTION_HALF_BYTES, 1024),
        "attention_c1": Span("attention_c1", 0,
                             layer * 0x02800000 + ATTENTION_HALF_BYTES,
                             ATTENTION_HALF_BYTES, 1024),
        "attention_meta": Span("attention_meta", 0,
                               0x50000000 + layer * ATTENTION_META_BYTES,
                               ATTENTION_META_BYTES),
        "mlp_gate_meta": Span("mlp_gate_meta", 1,
                              0x20000000 + layer * GU_META_BYTES,
                              GU_META_BYTES),
    }


def tensor_spans(buffer_id: int) -> dict[str, Span]:
    index(buffer_id, BUFFER_COUNT, "staging buffer")
    return {
        "attention_input": Span("attention_input", 0,
                                0x56000000 + buffer_id * 0x100000, INPUT_BYTES),
        "attention_output": Span("attention_output", 0,
                                 0x56080000 + buffer_id * 0x100000,
                                 ATTENTION_OUTPUT_BYTES),
        "mlp_input": Span("mlp_input", 1,
                          0x10000000 + buffer_id * 0x800000, INPUT_BYTES),
        "mlp_output": Span("mlp_output", 1,
                           0x10100000 + buffer_id * 0x800000, MLP_OUTPUT_BYTES),
    }


def static_spans() -> tuple[Span, ...]:
    spans = [s for layer in range(LAYERS) for s in layer_spans(layer).values()]
    spans += [s for buffer_id in range(BUFFER_COUNT)
              for s in tensor_spans(buffer_id).values()]
    spans += [Span("RoPE", 0, ROPE_BASE, ROPE_BYTES),
              Span("persistent KV", 0, KV_BASE, KV_BYTES, 64),
              Span("GU half0", 1, 0, GU_HALF_BYTES, 1024),
              Span("GU half1", 1, GU_HALF_BYTES, GU_HALF_BYTES, 1024)]
    for i, left in enumerate(spans):
        for right in spans[i + 1:]:
            if (left.channel == right.channel
                    and max(left.address, right.address)
                    < min(left.address + left.size, right.address + right.size)):
                raise ValueError(f"overlapping DDR spans: {left!r}, {right!r}")
    return tuple(spans)


def _integer_tensor(values, shape: tuple[int, ...], low: int,
                    high: int, label: str) -> np.ndarray:
    data = np.asarray(values)
    if data.shape != shape or data.dtype.kind not in "iu":
        raise ValueError(f"{label} requires integer shape {shape}")
    if np.any(data < low) or np.any(data > high):
        raise ValueError(f"{label} outside signed range")
    return data.astype(np.int64, copy=False)


def zero_inactive(values, active_mask: int) -> np.ndarray:
    index(active_mask, 1 << ROWS, "active mask")
    data = np.array(values, copy=True)
    if data.ndim != 2 or data.shape[0] != ROWS:
        raise ValueError("tensor requires sixteen physical rows")
    for slot in range(ROWS):
        if not (active_mask >> slot) & 1:
            data[slot] = 0
    return data


def pack_input_s24(values, active_mask: int = 0xFFFF) -> bytes:
    """Already normalized S24/F16 rows; online H32/A8 is on FPGA."""
    data = _integer_tensor(values, (ROWS, HIDDEN), -(1 << 23), (1 << 23) - 1,
                           "normalized S24")
    data = zero_inactive(data, active_mask).astype(np.uint32)
    octets = np.empty((*data.shape, 3), dtype=np.uint8)
    for byte in range(3):
        octets[..., byte] = (data >> (8 * byte)) & 255
    return octets.tobytes()


def pack_normalized_fp32(values, active_mask: int = 0xFFFF) -> bytes:
    from .scalellm_mlp_linear import s24_from_normalized_fp32
    return pack_input_s24(s24_from_normalized_fp32(values), active_mask)


def unpack_attention_s24(payload: bytes) -> np.ndarray:
    if len(payload) != ATTENTION_OUTPUT_BYTES:
        raise ValueError("Attention output requires exactly 196608 bytes")
    raw = np.frombuffer(payload, dtype=np.uint8).reshape(ROWS, HIDDEN, 3)
    data = (raw[..., 0].astype(np.int32)
            | raw[..., 1].astype(np.int32) << 8
            | raw[..., 2].astype(np.int32) << 16)
    return (data ^ (1 << 23)) - (1 << 23)


def pack_mlp_s32(values, active_mask: int = 0xFFFF) -> bytes:
    data = _integer_tensor(values, (ROWS, INTERMEDIATE), -(1 << 31),
                           (1 << 31) - 1, "SwiGLU S32")
    data = zero_inactive(data, active_mask)
    return data.reshape(ROWS, INTERMEDIATE // 16, 16).transpose(1, 0, 2).astype(
        "<i4").tobytes()


def unpack_mlp_s32(payload: bytes) -> np.ndarray:
    """Tile16-major S32/F16, with no second scale restoration."""
    if len(payload) != MLP_OUTPUT_BYTES:
        raise ValueError("online MLP output requires exactly 917504 bytes")
    return np.frombuffer(payload, dtype="<i4").reshape(
        INTERMEDIATE // 16, ROWS, 16).transpose(1, 0, 2).reshape(
            ROWS, INTERMEDIATE).copy()


def prepare_host_down(payload: bytes) -> bytes:
    """Post-product H32/A8 stays on host before the existing host Down."""
    from .scalellm_mlp_linear import (hadamard32_s32_exact,
                                     minmax_a8_scalecode_exact, pack_a8_rec576)
    product = unpack_mlp_s32(payload)
    return pack_a8_rec576(*minmax_a8_scalecode_exact(
        hadamard32_s32_exact(product), input_bits=35))


static_spans()
