#!/usr/bin/env python3
"""Generate a nonzero full-lane 5-group x 16-tile M12 smoke workload.

The mini workload preserves the complete 16-row x 12-column arithmetic width
of the formal M12 comparison while reducing only the number of group/tile
transactions.  Tiles 0..14 reuse the deterministic synthetic construction;
local tile 15 reuses physical tile 341 so the real four-column tail is covered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import generate_vectors as full


HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "data_mini"
ROWS, COLS, GROUPS, TILES, K = 16, 12, 5, 16, 32
FULL_GROUPS = 448
SOURCE_TILES = list(range(TILES - 1)) + [341]
TRANSACTIONS = GROUPS * TILES
PAYLOAD_BITS = {"sc": 26 * 256, "fp16": 26 * 256, "fp32": 28 * 256}
EXPECTED_BITS = ROWS * COLS * 24


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_inputs() -> tuple[np.ndarray, ...]:
    activation_rng = np.random.default_rng(0x12A8_448)
    activations = activation_rng.integers(
        -32, 33, size=(FULL_GROUPS, ROWS, K), dtype=np.int16)
    activation_codes = activation_rng.integers(
        96, 256, size=(FULL_GROUPS, ROWS), dtype=np.uint16)
    activation_shifts = activation_rng.integers(
        12, 15, size=(FULL_GROUPS, ROWS), dtype=np.uint8)
    activations[0, :, :] = 0
    activations[1, :, :] = np.where(
        np.indices((ROWS, K)).sum(axis=0) & 1, 255, -255)
    activation_codes[0, :] = 0
    activation_shifts[0, :] = 12
    activation_codes[1, :] = 255
    activation_shifts[1, :] = 14

    weights = np.empty((GROUPS, TILES, COLS, K), dtype=np.int8)
    weight_codes = np.empty((GROUPS, TILES, COLS), dtype=np.uint16)
    weight_shifts = np.empty((GROUPS, TILES, COLS), dtype=np.uint8)
    for local_tile, source_tile in enumerate(SOURCE_TILES):
        seed = full.SEEDS[source_tile % len(full.SEEDS)] ^ (
            source_tile * 0x9E37)
        rng = np.random.default_rng(seed)
        source_weights = rng.integers(
            -8, 8, size=(FULL_GROUPS, COLS, K), dtype=np.int8)
        source_codes = rng.integers(
            96, 256, size=(FULL_GROUPS, COLS), dtype=np.uint16)
        source_shifts = rng.integers(
            13, 16, size=(FULL_GROUPS, COLS), dtype=np.uint8)
        weights[:, local_tile] = source_weights[:GROUPS]
        weight_codes[:, local_tile] = source_codes[:GROUPS]
        weight_shifts[:, local_tile] = source_shifts[:GROUPS]

    weights[0, :, :, :] = 0
    weight_codes[0, :, :] = 0
    weight_shifts[0, :, :] = 13
    weights[1, 0, :, :] = np.where(
        np.indices((COLS, K)).sum(axis=0) & 1, 7, -8)
    weight_codes[1, 0, :] = 255
    weight_shifts[1, 0, :] = 15
    weights[:, -1, 4:, :] = 0
    weight_codes[:, -1, 4:] = 0
    weight_shifts[:, -1, 4:] = 13
    return (
        activations[:GROUPS], activation_codes[:GROUPS],
        activation_shifts[:GROUPS], weights, weight_codes, weight_shifts,
    )


def build_payloads_and_expected() -> tuple[dict[str, list[int]], dict[str, list[int]], dict]:
    (activations, activation_codes, activation_shifts, weights,
     weight_codes, weight_shifts) = build_inputs()
    act_scale_real = activation_codes.astype(np.float64) / np.exp2(
        activation_shifts.astype(np.int16))
    weight_scale_real = weight_codes.astype(np.float64) / np.exp2(
        weight_shifts.astype(np.int16))
    act_scale16 = full.fp16_ftz_array(act_scale_real)
    weight_scale16 = full.fp16_ftz_array(weight_scale_real)
    act_scale32 = act_scale_real.astype(np.float32)
    weight_scale32 = weight_scale_real.astype(np.float32)

    payloads = {variant: [] for variant in PAYLOAD_BITS}
    expected = {variant: [] for variant in PAYLOAD_BITS}
    fp16_zero_contributions = 0
    arithmetic_nonzero_group_tiles = {
        "correlation": 0, "sc": 0, "fp16": 0, "fp32": 0,
    }

    for group in range(GROUPS):
        for tile in range(TILES):
            mask = 0x00F if tile == TILES - 1 else 0xFFF
            common = (
                full.pack(activations[group].reshape(-1), 9) |
                (full.pack(weights[group, tile].reshape(-1), 4) << 4608)
            )
            control_sc = (
                (full.pack(activation_codes[group], 8) << 6144) |
                (full.pack(activation_shifts[group], 6) << 6272) |
                (full.pack(weight_codes[group, tile], 8) << 6368) |
                (full.pack(weight_shifts[group, tile], 6) << 6464) |
                (mask << 6536) | (tile << 6548) |
                ((group == 0) << 6557) |
                ((group == GROUPS - 1) << 6558)
            )
            control_fp16 = (
                (full.pack([full.fp16_bits(value) for value in
                            act_scale16[group]], 16) << 6144) |
                (full.pack([full.fp16_bits(value) for value in
                            weight_scale16[group, tile]], 16) << 6400) |
                (mask << 6592) | (tile << 6604) |
                ((group == 0) << 6613) |
                ((group == GROUPS - 1) << 6614)
            )
            control_fp32 = (
                (full.pack([full.fp32_bits(value) for value in
                            act_scale32[group]], 32) << 6144) |
                (full.pack([full.fp32_bits(value) for value in
                            weight_scale32[group, tile]], 32) << 6656) |
                (mask << 7040) | (tile << 7052) |
                ((group == 0) << 7061) |
                ((group == GROUPS - 1) << 7062)
            )
            payloads["sc"].append(common | control_sc)
            payloads["fp16"].append(common | control_fp16)
            payloads["fp32"].append(common | control_fp32)

    for tile in range(TILES):
        corr = np.einsum(
            "grk,gck->grc", activations.astype(np.int32),
            weights[:, tile].astype(np.int32), optimize=True,
        ).astype(np.int64)
        arithmetic_nonzero_group_tiles["correlation"] += int(np.count_nonzero(
            np.any(corr != 0, axis=(1, 2))))
        shifts = (
            activation_shifts[:, :, None].astype(np.int16) +
            weight_shifts[:, tile, None, :].astype(np.int16)
        )
        raw = (
            corr * activation_codes[:, :, None].astype(np.int64) *
            weight_codes[:, tile, None, :].astype(np.int64)
        )
        sc_terms = np.right_shift(raw, shifts - 24)
        arithmetic_nonzero_group_tiles["sc"] += int(np.count_nonzero(
            np.any(sc_terms != 0, axis=(1, 2))))
        sc_out = full.sc_round_sat_array(
            np.sum(sc_terms, axis=0, dtype=np.int64))

        corr16 = full.fp16_ftz_array(corr.astype(np.float32))
        term16 = full.fp16_mul_ip_array(
            full.fp16_mul_ip_array(corr16, act_scale16[:, :, None]),
            weight_scale16[:, tile, None, :],
        )
        fp16_zero_contributions += int(np.count_nonzero(
            (term16.view(np.uint16) & np.uint16(0x7FFF)) == 0))
        arithmetic_nonzero_group_tiles["fp16"] += int(np.count_nonzero(
            np.any((term16.view(np.uint16) & np.uint16(0x7FFF)) != 0,
                   axis=(1, 2))))
        accum16 = np.zeros((ROWS, COLS), dtype=np.float32)
        accum32 = np.zeros((ROWS, COLS), dtype=np.float32)
        term32_all = np.asarray(
            corr.astype(np.float32) * act_scale32[:, :, None],
            dtype=np.float32)
        term32_all = np.asarray(
            term32_all * weight_scale32[:, tile, None, :],
            dtype=np.float32)
        arithmetic_nonzero_group_tiles["fp32"] += int(np.count_nonzero(
            np.any(term32_all != 0, axis=(1, 2))))
        for group in range(GROUPS):
            accum16 = np.asarray(
                accum16 + term16[group].astype(np.float32), dtype=np.float32)
            accum32 = np.asarray(
                accum32 + term32_all[group], dtype=np.float32)

        outputs = {
            "sc": sc_out,
            "fp16": full.round_sat_s24_array(accum16),
            "fp32": full.round_sat_s24_array(accum32),
        }
        for variant, values in outputs.items():
            expected[variant].append(full.pack(values.reshape(-1), 24))

    stats = {
        "fp16_zero_contributions": fp16_zero_contributions,
        "arithmetic_nonzero_group_tiles": arithmetic_nonzero_group_tiles,
        "payload_nonzero_transactions": {
            variant: sum(value != 0 for value in values)
            for variant, values in payloads.items()
        },
        "expected_nonzero_elements": {
            variant: sum(
                int(np.count_nonzero([
                    (word >> (24 * lane)) & 0xFFFFFF
                    for lane in range(ROWS * COLS)
                ]))
                for word in words
            )
            for variant, words in expected.items()
        },
    }
    return payloads, expected, stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    boundary_cases = full.verify_fp16_mul_ip_boundary()
    payloads, expected, stats = build_payloads_and_expected()

    files: dict[str, int] = {}
    for variant, words in payloads.items():
        name = f"payload_{variant}_u{PAYLOAD_BITS[variant]}.mem"
        files[name] = PAYLOAD_BITS[variant]
        with (out / name).open("w", encoding="ascii") as handle:
            for word in words:
                full.write_word(handle, word, PAYLOAD_BITS[variant])
    for variant, words in expected.items():
        name = f"expected_{variant}_s24x16x12.mem"
        files[name] = EXPECTED_BITS
        with (out / name).open("w", encoding="ascii") as handle:
            for word in words:
                full.write_word(handle, word, EXPECTED_BITS)

    generator = Path(__file__).resolve()
    semantics_model = HERE / "generate_vectors.py"
    manifest = {
        "schema": "scalellm_m12_down_a8w4_full_lane_mini_v1",
        "rows": ROWS,
        "physical_columns": COLS,
        "groups": GROUPS,
        "tiles": TILES,
        "transactions": TRANSACTIONS,
        "group_size": K,
        "source_tiles": SOURCE_TILES,
        "tail_mask": "0x00f",
        "payload_bits": PAYLOAD_BITS,
        "expected_bits": EXPECTED_BITS,
        "fp16_boundary_cases": boundary_cases,
        **stats,
        "generator": str(generator),
        "generator_sha256": sha256(generator),
        "fp_semantics_model": str(semantics_model.resolve()),
        "fp_semantics_model_sha256": sha256(semantics_model),
        "files": {
            name: {"bits": bits, "bytes": (out / name).stat().st_size,
                   "sha256": sha256(out / name)}
            for name, bits in sorted(files.items())
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "M12_MINI_VECTOR_GENERATE_PASS "
        f"files={len(files)} groups={GROUPS} tiles={TILES} "
        f"transactions={TRANSACTIONS} boundary_cases={boundary_cases} "
        f"manifest_sha256={sha256(out / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
