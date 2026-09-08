#!/usr/bin/env python3
"""Generate a bit-exact reduced-shape V5 serial gate/up + down command.

The external stream is still the production 16-column/group32 A8W4 ABI.
Only N is reduced: gate/up computes 32 intermediate columns from all 128
hidden groups, while down computes 128 output columns from the resulting one
product group.  The two DDR commands therefore contain 512 and 8 records,
respectively, both legal multiples of the reader's eight-record burst.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from mlp_fixed import (
    build_silu_lut,
    hadamard32_product_normalized,
    robust_a8_quantize_s35,
    swiglu_product_s32,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_serial_ddr_command16_v5_reduced"
ROWS = 16
GROUP_SIZE = 32
HIDDEN_GROUPS = 128
INTERMEDIATE_COLUMNS = 32
DOWN_GROUPS = INTERMEDIATE_COLUMNS // GROUP_SIZE
HIDDEN_COLUMNS = 128
GATE_SOURCE_RECORDS = 2 * ((INTERMEDIATE_COLUMNS + 15) // 16)
GATE_TRANSACTIONS = GATE_SOURCE_RECORDS * HIDDEN_GROUPS
GATE_COMPUTE_TRANSACTIONS = (
    2 * ((INTERMEDIATE_COLUMNS + 11) // 12) * HIDDEN_GROUPS
)
GATE_PASSES = 2 * ((INTERMEDIATE_COLUMNS + 11) // 12)
DOWN_SOURCE_RECORDS = (HIDDEN_COLUMNS + 15) // 16
DOWN_TRANSACTIONS = DOWN_SOURCE_RECORDS * DOWN_GROUPS
DOWN_COMPUTE_TILES = (HIDDEN_COLUMNS + 11) // 12
SEED = 0x5E21_1605


def twos(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"{value} does not fit S{width}")
    return value & ((1 << width) - 1)


def pack(values: list[int], width: int, *, signed: bool = False) -> int:
    result = 0
    for index, value in enumerate(values):
        encoded = twos(value, width) if signed else value
        if not signed and not 0 <= encoded < (1 << width):
            raise ValueError(f"{value} does not fit U{width}")
        result |= encoded << (index * width)
    return result


def align_guard(raw: int, total_shift: int) -> int:
    if raw == 0:
        return 0
    if not 21 <= total_shift <= 44:
        raise ValueError(f"nonzero ScaleCode total shift {total_shift}")
    value = raw << (24 - total_shift) if total_shift < 24 else \
        raw >> (total_shift - 24)
    if not -(1 << 35) <= value < (1 << 35):
        raise ValueError("S36 group guard overflow")
    return value


def project_s24(value: int) -> tuple[int, bool]:
    rounded = (value + 128) >> 8 if value >= 0 else \
        -((-value + 128) >> 8)
    saturated = max(-(1 << 23), min((1 << 23) - 1, rounded))
    return saturated, saturated != rounded


def pack_weight_record(weights: list[list[int]]) -> str:
    return f"{pack([item for column in weights for item in column], 4, signed=True):0512x}"


def pack_weight_meta(codes: list[int], shifts: list[int]) -> str:
    value = pack(codes, 8) | (pack(shifts, 6) << 128)
    return f"{value:056x}"


def write_rows(name: str, rows: list[str]) -> None:
    (OUT / name).write_text("\n".join(rows) + "\n", encoding="ascii")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if GATE_TRANSACTIONS % 8 or DOWN_TRANSACTIONS % 8:
        raise AssertionError("DDR transactions must be burst aligned")
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    cache_rows: list[str] = []
    cache_meta_rows: list[str] = []
    centered: list[list[list[int]]] = []
    activation_codes: list[list[int]] = []
    activation_shifts: list[list[int]] = []
    for group in range(HIDDEN_GROUPS):
        samples: list[int] = []
        metadata: list[int] = []
        centered_rows: list[list[int]] = []
        codes: list[int] = []
        shifts: list[int] = []
        for row in range(ROWS):
            zero = 112 + ((group * 3 + row * 5) % 24)
            code = 3 + ((group * 11 + row * 7) % 29)
            shift = 12 + ((group + row * 2) % 5)
            row_centered = [
                ((group * 13 + row * 7 + lane * 5) % 31) - 15
                for lane in range(GROUP_SIZE)
            ]
            row_samples = [zero + value for value in row_centered]
            if not all(0 <= value <= 255 for value in row_samples):
                raise AssertionError("activation escaped U8")
            samples.extend(row_samples)
            metadata.append((shift << 16) | (code << 8) | zero)
            centered_rows.append(row_centered)
            codes.append(code)
            shifts.append(shift)
        cache_rows.append(f"{pack(samples, 8):01024x}")
        cache_meta_rows.append(f"{pack(metadata, 24):096x}")
        centered.append(centered_rows)
        activation_codes.append(codes)
        activation_shifts.append(shifts)

    gate_accum = [
        [[0 for _ in range(INTERMEDIATE_COLUMNS)] for _ in range(ROWS)]
        for _ in range(2)
    ]
    gate_weights: list[str] = []
    gate_metadata: list[str] = []
    # Exact external source order: record, gate/up matrix, hidden K group.
    for record in range(INTERMEDIATE_COLUMNS // 16):
        for matrix in range(2):
            for group in range(HIDDEN_GROUPS):
                weights = [
                    [rng.randint(-8, 7) for _ in range(GROUP_SIZE)]
                    for _ in range(16)
                ]
                codes = [rng.randint(1, 31) for _ in range(16)]
                shifts = [rng.randint(12, 18) for _ in range(16)]
                gate_weights.append(pack_weight_record(weights))
                gate_metadata.append(pack_weight_meta(codes, shifts))
                for row in range(ROWS):
                    for column in range(16):
                        global_column = record * 16 + column
                        dot = sum(
                            value * weight
                            for value, weight in zip(
                                centered[group][row], weights[column],
                                strict=True,
                            )
                        )
                        raw = dot * activation_codes[group][row] * codes[column]
                        gate_accum[matrix][row][global_column] += align_guard(
                            raw, activation_shifts[group][row] + shifts[column]
                        )

    gate_projection = [
        [[0 for _ in range(INTERMEDIATE_COLUMNS)] for _ in range(ROWS)]
        for _ in range(2)
    ]
    gate_saturation = 0
    for matrix in range(2):
        for row in range(ROWS):
            for column in range(INTERMEDIATE_COLUMNS):
                value, did_saturate = project_s24(
                    gate_accum[matrix][row][column]
                )
                gate_projection[matrix][row][column] = value
                gate_saturation += int(did_saturate)

    gate_projection_records: list[str] = []
    for record in range(INTERMEDIATE_COLUMNS // 16):
        for matrix in range(2):
            values = [
                gate_projection[matrix][row][record * 16 + column]
                for row in range(ROWS) for column in range(16)
            ]
            gate_projection_records.append(
                f"{pack(values, 24, signed=True):01536x}"
            )

    silu_table = build_silu_lut()
    down_u8: list[int] = []
    down_meta: list[int] = []
    down_centered: list[list[int]] = []
    down_codes: list[int] = []
    down_shifts: list[int] = []
    for row in range(ROWS):
        products = [
            swiglu_product_s32(
                gate_projection[0][row][column],
                gate_projection[1][row][column], silu_table,
            )
            for column in range(INTERMEDIATE_COLUMNS)
        ]
        transformed = hadamard32_product_normalized(products)
        quantized = robust_a8_quantize_s35(transformed.values)
        down_u8.extend(quantized.values)
        down_meta.append(quantized.metadata)
        down_centered.append([
            value - quantized.zero_point for value in quantized.values
        ])
        down_codes.append(quantized.scale_code)
        down_shifts.append(quantized.scale_shift)

    down_weights: list[str] = []
    down_metadata: list[str] = []
    down_projection = [
        [0 for _ in range(HIDDEN_COLUMNS)] for _ in range(ROWS)
    ]
    down_saturation = 0
    for record in range(DOWN_SOURCE_RECORDS):
        weights = [
            [rng.randint(-8, 7) for _ in range(GROUP_SIZE)]
            for _ in range(16)
        ]
        codes = [rng.randint(1, 31) for _ in range(16)]
        nonzero_shifts = [
            shift for code, shift in zip(down_codes, down_shifts, strict=True)
            if code != 0
        ]
        shifts: list[int] = []
        for _column in range(16):
            low = max(4, max(21 - shift for shift in nonzero_shifts))
            high = min(20, min(44 - shift for shift in nonzero_shifts))
            if low > high:
                raise ValueError("no legal shared down weight shift")
            shifts.append(rng.randint(low, high))
        down_weights.append(pack_weight_record(weights))
        down_metadata.append(pack_weight_meta(codes, shifts))
        for row in range(ROWS):
            for column in range(16):
                global_column = record * 16 + column
                dot = sum(
                    value * weight for value, weight in zip(
                        down_centered[row], weights[column], strict=True
                    )
                )
                raw = dot * down_codes[row] * codes[column]
                guard = align_guard(
                    raw, down_shifts[row] + shifts[column]
                ) if down_codes[row] != 0 else 0
                value, did_saturate = project_s24(guard)
                down_projection[row][global_column] = value
                down_saturation += int(did_saturate)

    expected_records: list[str] = []
    for record in range(DOWN_SOURCE_RECORDS):
        values = [
            down_projection[row][record * 16 + column]
            for row in range(ROWS) for column in range(16)
        ]
        expected_records.append(
            f"{pack(values, 24, signed=True):01536x}"
        )

    write_rows("cache_u8x16x32.mem", cache_rows)
    write_rows("cache_meta_u24x16.mem", cache_meta_rows)
    write_rows("gate_weights_s4x16x32.mem", gate_weights)
    write_rows("gate_weight_meta_u224.mem", gate_metadata)
    write_rows("gate_projection_s24x16x16.mem", gate_projection_records)
    write_rows("expected_activation_u8x16x32.mem", [
        f"{pack(down_u8, 8):01024x}"
    ])
    write_rows("expected_activation_meta_u24x16.mem", [
        f"{pack(down_meta, 24):096x}"
    ])
    write_rows("down_weights_s4x16x32.mem", down_weights)
    write_rows("down_weight_meta_u224.mem", down_metadata)
    write_rows("expected_s24x16x16.mem", expected_records)

    files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(OUT.glob("*.mem"))
    }
    manifest = {
        "schema": "hap_mlp_serial_ddr_command16_v5_reduced_v1",
        "rows": ROWS,
        "group_size": GROUP_SIZE,
        "intermediate_columns": INTERMEDIATE_COLUMNS,
        "hidden_columns": HIDDEN_COLUMNS,
        "hidden_groups": HIDDEN_GROUPS,
        "down_groups": DOWN_GROUPS,
        "gate_source_records": GATE_SOURCE_RECORDS,
        "gate_transactions": GATE_TRANSACTIONS,
        "gate_compute_transactions": GATE_COMPUTE_TRANSACTIONS,
        "gate_projection_passes": GATE_PASSES,
        "gate_output_records": INTERMEDIATE_COLUMNS // 16 * 2,
        "down_source_records": DOWN_SOURCE_RECORDS,
        "down_transactions": DOWN_TRANSACTIONS,
        "down_compute_tiles": DOWN_COMPUTE_TILES,
        "expected_gate_saturation": gate_saturation,
        "expected_down_saturation": down_saturation,
        "expected_total_saturation": gate_saturation + down_saturation,
        "gate_physical_bytes": GATE_TRANSACTIONS * 256,
        "gate_useful_bytes": GATE_TRANSACTIONS * 256,
        "down_physical_bytes": DOWN_TRANSACTIONS * 256,
        "down_useful_bytes": DOWN_TRANSACTIONS * 256,
        "seed": f"0x{SEED:x}",
        "files": files,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: generated reduced V5 serial gate/down vectors "
        f"gate={GATE_TRANSACTIONS}/{GATE_COMPUTE_TRANSACTIONS} "
        f"down={DOWN_TRANSACTIONS}/{DOWN_COMPUTE_TILES} "
        f"saturation={gate_saturation + down_saturation}"
    )


if __name__ == "__main__":
    main()
