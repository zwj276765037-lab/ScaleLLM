#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path("/home/user/EDA-202/zhuowenjun/ScaleLLM")
OUT = Path(__file__).resolve().parent.parent / "data"
COUNT = 512


def signed(value: int, width: int) -> int:
    return value - (1 << width) if value & (1 << (width - 1)) else value


def bits16(value: float) -> int:
    return int(np.float16(value).view(np.uint16))


def bits32(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(np.float32(value))))[0]


def q16_s32(value: float) -> int:
    if np.isnan(value):
        return 0
    if np.isposinf(value):
        return 0x7FFFFFFF
    if np.isneginf(value):
        return 0x80000000
    quantized = int(np.rint(float(value) * 65536.0))
    quantized = min(0x7FFFFFFF, max(-0x80000000, quantized))
    return quantized & 0xFFFFFFFF


def write_hex(name: str, values: list[int], digits: int) -> None:
    (OUT / name).write_text("".join(f"{value:0{digits}x}\n" for value in values))


gate_path = ROOT / "data/mlp_silu_gate_s24.mem"
up_path = ROOT / "data/mlp_silu_up_s24.mem"
gate_raw = [int(line, 16) for line in gate_path.read_text().splitlines()]
up_raw = [int(line, 16) for line in up_path.read_text().splitlines()]
assert len(gate_raw) == COUNT and len(up_raw) == COUNT
gate = [signed(value, 24) / 65536.0 for value in gate_raw]
up = [signed(value, 24) / 65536.0 for value in up_raw]

gate16: list[int] = []
up16: list[int] = []
gate32: list[int] = []
up32: list[int] = []
expected16: list[int] = []
expected32: list[int] = []
with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
    for gate_value, up_value in zip(gate, up):
        g16 = np.float16(gate_value)
        u16 = np.float16(up_value)
        exp16 = np.exp(np.float16(-g16), dtype=np.float16)
        denominator16 = np.float16(np.float16(1.0) + exp16)
        silu16 = np.float16(g16 / denominator16)
        product16 = np.float16(silu16 * u16)

        g32 = np.float32(gate_value)
        u32 = np.float32(up_value)
        exp32 = np.exp(np.float32(-g32), dtype=np.float32)
        denominator32 = np.float32(np.float32(1.0) + exp32)
        silu32 = np.float32(g32 / denominator32)
        product32 = np.float32(silu32 * u32)

        gate16.append(bits16(g16))
        up16.append(bits16(u16))
        gate32.append(bits32(g32))
        up32.append(bits32(u32))
        expected16.append(q16_s32(float(product16)))
        expected32.append(q16_s32(float(product32)))

OUT.mkdir(parents=True, exist_ok=True)
write_hex("gate_fp16.mem", gate16, 4)
write_hex("up_fp16.mem", up16, 4)
write_hex("gate_fp32.mem", gate32, 8)
write_hex("up_fp32.mem", up32, 8)
write_hex("expected_fp16_s32.mem", expected16, 8)
write_hex("expected_fp32_s32.mem", expected32, 8)
manifest = {
    "schema": "m10_fp_silu_v1",
    "vectors": COUNT,
    "common_output": "S32 Q16.16",
    "operation_order": "exp(-gate), add(1), gate/divisor, multiply(up)",
    "rounding": "nearest-even at FP operations and final fixed conversion",
    "source_sha256": {
        gate_path.name: hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        up_path.name: hashlib.sha256(up_path.read_bytes()).hexdigest(),
    },
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("M10_VECTOR_JSON:", json.dumps(manifest, sort_keys=True))
