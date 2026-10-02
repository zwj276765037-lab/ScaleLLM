#!/usr/bin/env python3
"""Generate bit-exact vectors for cohort16 two-wave W8 reuse."""

from __future__ import annotations

import json
import random
from pathlib import Path

from attention_two_wave_reuse_contract import (
    GROUPS,
    audit_projection_schedule,
    build_projection_schedule,
)
from fixbit_v2 import (
    FORMAT_ID,
    a8w8_group32_guard_s42,
    hadamard32_normalized,
    pack_lanes,
    minmax_a8_quantize,
    round_sat_guard_s42_to_s24,
    self_test,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "projection_core16x16_w8_reuse"
WAVES = 2
ROWS = 8
COLS = 16
SEED = 0x4838_4138_5738_5201


def pack_unsigned(values: list[int], width: int) -> int:
    packed = 0
    for index, value in enumerate(values):
        packed |= int(value) << (index * width)
    return packed


def main() -> None:
    self_test()
    schedule = build_projection_schedule()
    audit_projection_schedule(schedule)
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    activations = [[[] for _ in range(GROUPS)] for _ in range(WAVES)]
    input_saturation = 0
    for wave in range(WAVES):
        with (OUT_DIR / f"input_wave{wave}_s24.mem").open(
                "w", encoding="ascii") as input_file:
            for group in range(GROUPS):
                source_rows = []
                activation_rows = []
                for _row in range(ROWS):
                    source = [rng.randint(-(3 << 16), 3 << 16)
                              for _ in range(32)]
                    source_rows.append(source)
                    transformed = hadamard32_normalized(source)
                    input_saturation += transformed.saturation_count
                    activation_rows.append(
                        minmax_a8_quantize(transformed.values))
                activations[wave][group] = activation_rows
                flat_source = [value for row in source_rows for value in row]
                input_file.write(f"{pack_lanes(flat_source, 24):01536x}\n")

    accum = [[0] * (ROWS * COLS) for _ in range(WAVES)]
    with (OUT_DIR / "weight_s8.mem").open("w", encoding="ascii") as wf, \
            (OUT_DIR / "weight_meta16.mem").open(
                "w", encoding="ascii") as mf:
        for group in range(GROUPS):
            packed_weights = []
            packed_metadata = []
            for col in range(COLS):
                weights = [rng.randint(-127, 127) for _ in range(32)]
                weight_code = rng.randint(1, 192)
                active = [activations[wave][group][row]
                          for wave in range(WAVES)
                          for row in range(ROWS)]
                min_act_shift = min(item.scale_shift for item in active
                                    if item.scale_code)
                max_act_shift = max(item.scale_shift for item in active
                                    if item.scale_code)
                minimum = max(0, 26 - min_act_shift)
                maximum = min(32, 47 - max_act_shift)
                weight_shift = rng.randint(minimum, maximum)
                packed_weights.extend(weights)
                packed_metadata.append((weight_shift << 8) | weight_code)
                for wave in range(WAVES):
                    for row in range(ROWS):
                        activation = activations[wave][group][row]
                        accum[wave][row * COLS + col] += \
                            a8w8_group32_guard_s42(
                                activation.values,
                                weights,
                                activation.zero_point,
                                activation.scale_code,
                                activation.scale_shift,
                                weight_code,
                                weight_shift,
                            )
            wf.write(f"{pack_lanes(packed_weights, 8):01024x}\n")
            mf.write(f"{pack_unsigned(packed_metadata, 16):064x}\n")

    output_saturation = 0
    with (OUT_DIR / "expected_s24.mem").open(
            "w", encoding="ascii") as output_file:
        for wave in range(WAVES):
            packed_output = 0
            for lane, value in enumerate(accum[wave]):
                output, saturated = round_sat_guard_s42_to_s24(value)
                output_saturation += int(saturated)
                packed_output |= (output & 0xFFFFFF) << (lane * 24)
            output_file.write(f"{packed_output:0768x}\n")

    manifest = {
        "schema": "hap_projection_core16x16_w8_reuse_vectors_v1",
        "format_id": f"0x{FORMAT_ID:08x}",
        "seed": SEED,
        "waves": WAVES,
        "rows_per_wave": ROWS,
        "cols": COLS,
        "groups": GROUPS,
        "weight_acceptances": len(schedule.weights),
        "wave_consumptions": len(schedule.consumptions),
        "physical_weight_bytes": schedule.physical_weight_bytes,
        "avoided_reread_bytes": (
            schedule.reread_weight_bytes - schedule.physical_weight_bytes),
        "frontend_hadamard_saturation": input_saturation,
        "projection_saturation": output_saturation,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("PROJECTION_CORE16_REUSE_VECTOR_JSON:",
          json.dumps(manifest, sort_keys=True))
    print("PASS: cohort16 two-wave W8 reuse vectors generated")


if __name__ == "__main__":
    main()
