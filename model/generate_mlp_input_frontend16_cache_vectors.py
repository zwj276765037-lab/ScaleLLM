#!/usr/bin/env python3

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_input_frontend16_cache"
GROUPS, ROWS, LANES = 128, 16, 32
INV_SQRT32_Q16 = 11_585
ABS_Q9999_Q16, CLIP_Q001_Q16, CLIP_Q999_Q16 = 65_333, 2_032, 63_504
SCALE_SHIFT_LIMIT = 4_269_834_239


def signed(value: int, width: int) -> int:
    if not -(1 << (width-1)) <= value < (1 << (width-1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value


def twos(value: int, width: int) -> int:
    return signed(value, width) & ((1 << width)-1)


def round_shift_away(value: int, shift: int) -> int:
    half = 1 << (shift-1)
    return (value+half) >> shift if value >= 0 else -((-value+half) >> shift)


def hadamard(values: list[int]) -> tuple[list[int], int]:
    work = [signed(value, 24) for value in values]
    distance, width = 1, 25
    while distance < LANES:
        nxt = work.copy()
        for base in range(0, LANES, 2*distance):
            for offset in range(distance):
                lhs, rhs = work[base+offset], work[base+offset+distance]
                nxt[base+offset] = signed(lhs+rhs, width)
                nxt[base+offset+distance] = signed(lhs-rhs, width)
        work, distance, width = nxt, 2*distance, width+1
    output, saturation = [], 0
    for value in work:
        rounded = round_shift_away(signed(value, 29)*INV_SQRT32_Q16, 16)
        clamped = max(-(1 << 26), min((1 << 26)-1, rounded))
        saturation += int(clamped != rounded)
        output.append(clamped)
    return output, saturation


def two_smallest(values: list[int]) -> tuple[int, int]:
    first = second = None
    for value in values:
        if first is None or value <= first:
            second, first = first, value
        elif second is None or value < second:
            second = value
    assert first is not None and second is not None
    return first, second


def two_largest(values: list[int]) -> tuple[int, int]:
    first, second = two_smallest([-value for value in values])
    return -first, -second


def interp(base: int, high: int, low: int, coefficient: int) -> int:
    return base + (((high-low)*coefficient) >> 16)


def encoded_ratio(value: int, code: int, shift: int) -> int:
    if code == 0:
        return 0
    adjusted = (abs(value) << shift) + (code << 15)
    if adjusted >= (code*255 << 16):
        return 255
    return min(255, (adjusted >> 16)//code)


def quantize(values: list[int]) -> tuple[list[int], int]:
    abs1, abs2 = two_largest([abs(value) for value in values])
    threshold = interp(abs2, abs1, abs2, ABS_Q9999_Q16)
    clipped = [max(-threshold, min(threshold, value)) for value in values]
    min1, min2 = two_smallest(clipped)
    max1, max2 = two_largest(clipped)
    low = interp(min1, min2, min1, CLIP_Q001_Q16)
    high = interp(max2, max1, max2, CLIP_Q999_Q16)
    diff = high-low
    if diff <= 0:
        return [0]*LANES, 0
    shifted, shift = diff, 0
    while shift < 63 and (shifted << 1) <= SCALE_SHIFT_LIMIT:
        shifted <<= 1
        shift += 1
    code = max(1, min(255, (shifted+(255 << 15))//(255 << 16)))
    zero = 0 if low >= 0 else min(255, encoded_ratio(low, code, shift))
    output = []
    for value in clipped:
        value = max(low, min(high, value))
        magnitude = encoded_ratio(value, code, shift)
        output.append(max(0, min(255,
            zero-magnitude if value < 0 else zero+magnitude)))
    return output, zero | (code << 8) | (shift << 16)


def build_row(rng: random.Random, group: int, row: int) -> list[int]:
    mode = (group+row) % 6
    if mode == 0:
        return [0]*LANES
    if mode == 1:
        return [(lane-16) << 14 for lane in range(LANES)]
    if mode == 2:
        return [-(1 << 23) if lane & 1 else (1 << 23)-1
                for lane in range(LANES)]
    if mode == 3:
        return [rng.randint(-(2 << 16), (2 << 16)-1) for _ in range(LANES)]
    if mode == 4:
        impulse = [0]*LANES
        impulse[(group*ROWS+row) % LANES] = rng.randint(
            -(64 << 16), (64 << 16)-1)
        return impulse
    return [rng.randint(-(64 << 16), (64 << 16)-1) for _ in range(LANES)]


def main() -> None:
    rng = random.Random(0x16_CACE)
    OUT.mkdir(parents=True, exist_ok=True)
    input_rows, u8_rows, meta_rows = [], [], []
    saturation_total = 0
    for group in range(GROUPS):
        inputs, outputs, metadata = [], [], []
        for row in range(ROWS):
            values = build_row(rng, group, row)
            transformed, saturation = hadamard(values)
            quantized, meta = quantize(transformed)
            inputs.extend(values)
            outputs.extend(quantized)
            metadata.append(meta)
            saturation_total += saturation
        input_rows.append(f"{sum(twos(v, 24) << (i*24) for i,v in enumerate(inputs)):03072x}")
        u8_rows.append(f"{sum(v << (i*8) for i,v in enumerate(outputs)):01024x}")
        meta_rows.append(f"{sum(v << (i*24) for i,v in enumerate(metadata)):096x}")
    for name, rows in (
        ("input_s24x16x32.mem", input_rows),
        ("expected_u8x16x32.mem", u8_rows),
        ("expected_meta_u24x16.mem", meta_rows),
    ):
        (OUT/name).write_text("\n".join(rows)+"\n", encoding="ascii")
    (OUT/"manifest.json").write_text(json.dumps({
        "groups": GROUPS, "requests": ROWS, "lanes": LANES,
        "hadamard_saturation_count": saturation_total,
        "seed": "0x16cace",
    }, indent=2)+"\n", encoding="utf-8")
    print("PASS: generated cohort16 MLP input frontend/cache vectors "
          f"saturation={saturation_total}")


if __name__ == "__main__":
    main()
