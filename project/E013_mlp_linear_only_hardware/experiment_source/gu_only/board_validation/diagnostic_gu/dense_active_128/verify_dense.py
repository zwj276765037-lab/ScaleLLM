#!/usr/bin/env python3
"""Independently audit every wire byte and recompute the 32-column period."""
import argparse
from pathlib import Path
import time

import numpy as np

from dense import DenseArtifacts, write_json, sha


def decode_gold_period(data):
    b = np.frombuffer(data, np.uint8).reshape(2, 2, 16, 16, 3).astype(np.int64)
    u = b[..., 0] + 256 * b[..., 1] + 65536 * b[..., 2]
    v = np.where(u >= 8388608, u - 16777216, u)
    return v.transpose(1, 2, 0, 3).reshape(2, 16, 32)


def verify_bundle(bundle):
    started = time.monotonic()
    artifacts = DenseArtifacts(bundle)
    data = {name: record.read_verified() for name, record in artifacts.records.items()}
    # Every complete period is compared, including the final physical column.
    period_checks = {}
    for name, period_bytes in (("mlp_gate_up_c0", 65536), ("mlp_gate_up_c1", 65536),
                               ("mlp_gate_meta", 16384), ("gold_gu_s24", 3072)):
        periods = np.frombuffer(data[name], np.uint8).reshape(448, period_bytes)
        assert np.all(periods == periods[0]), f"period mismatch in {name}"
        period_checks[name] = {"period_bytes": period_bytes, "periods_checked": 448,
                               "bytes_checked": len(data[name]), "period_sha256": sha(periods[0].tobytes())}
    aw = np.frombuffer(data["input_rec576"], np.uint8).reshape(128, 576)
    assert not np.any(aw[:, 560:]), "REC576 padding"
    q = aw[:, :512].reshape(128, 16, 32).astype(np.int64)
    am = aw[:, 512:560].reshape(128, 16, 3).astype(np.int64)
    am = am[..., 0] + 256 * am[..., 1] + 65536 * am[..., 2]
    assert not np.any(am & 0xC00000), "REC576 reserved bits"
    zp, ac, ash = am & 255, am >> 8 & 255, am >> 16 & 63
    for group in range(128):
        for row in range(16):
            assert int(zp[group, row]) == 128
            assert int(ac[group, row]) == 17 + (row + group) % 13
            assert int(ash[group, row]) == 14 + (row + group) % 3
            expected_q = [128 + (-1 if (lane + row + group) % 2 else 1) * (1 + (lane + 3 * row + group) % 7) for lane in range(32)]
            assert q[group, row].tolist() == expected_q, ("activation formula", group, row)
    delta = q - zp[:, :, None]
    assert np.all(delta != 0) and np.all(ac != 0)
    metadata = np.frombuffer(data["mlp_gate_meta"], np.uint8).reshape(229376, 32)
    assert not np.any(metadata[:, 28:]), "metadata padding"
    assert np.all(metadata[:, :16] != 0), "zero weight code"
    p0 = np.frombuffer(data["mlp_gate_up_c0"], np.uint8).reshape(229376, 128)
    p1 = np.frombuffer(data["mlp_gate_up_c1"], np.uint8).reshape(229376, 128)
    nonzero_weights = 0
    for packed in (p0, p1):
        assert np.all((packed & 15) != 0) and np.all((packed >> 4) != 0), "zero S4 weight"
        nonzero_weights += int(packed.size * 2)
    w = np.zeros((2, 128, 32, 32), dtype=np.int64)
    wc = np.zeros((2, 128, 32), dtype=np.int64)
    wsh = np.zeros((2, 128, 32), dtype=np.int64)
    for tile in (0, 1):
        for matrix in (0, 1):
            for group in range(128):
                record = (2 * tile + matrix) * 128 + group
                wm = metadata[record]
                shift_bits = int.from_bytes(wm[16:28].tobytes(), "little")
                for local_column in range(16):
                    column = tile * 16 + local_column
                    wc[matrix, group, column] = int(wm[local_column])
                    wsh[matrix, group, column] = (shift_bits >> (6 * local_column)) & 63
                    assert int(wc[matrix, group, column]) == 19 + (column + 3 * group + matrix) % 11
                    assert int(wsh[matrix, group, column]) == 14 + (column + group + matrix) % 3
                    packed = (p0 if local_column < 8 else p1)[record, (local_column % 8) * 16:(local_column % 8 + 1) * 16]
                    nibble = np.empty(32, dtype=np.int64)
                    nibble[0::2], nibble[1::2] = packed & 15, packed >> 4
                    values = np.where(nibble >= 8, nibble - 16, nibble)
                    expected_w = [(-1 if (lane + column + group + matrix) % 2 else 1) * (1 + (3 * lane + 5 * column + group + 2 * matrix) % 7) for lane in range(32)]
                    assert values.tolist() == expected_w, ("weight formula", matrix, group, column)
                    w[matrix, group, column] = values
    # Independently decoded integer wire oracle: floor division, no source helper.
    sums = np.zeros((2, 16, 32), dtype=np.int64)
    total_shift_counts = {}
    dot_max = raw_max = guard_max = 0
    for group in range(128):
        for matrix in (0, 1):
            dots = delta[group] @ w[matrix, group].T
            raw = dots * ac[group, :, None] * wc[matrix, group, None, :]
            shifts = ash[group, :, None] + wsh[matrix, group, None, :]
            assert np.all((shifts >= 28) & (shifts <= 32))
            guards = np.floor_divide(raw, 2 ** (shifts - 24))
            sums[matrix] += guards
            dot_max, raw_max, guard_max = max(dot_max, int(np.abs(dots).max())), max(raw_max, int(np.abs(raw).max())), max(guard_max, int(np.abs(guards).max()))
            for shift, count in zip(*np.unique(shifts, return_counts=True)):
                total_shift_counts[str(int(shift))] = total_shift_counts.get(str(int(shift)), 0) + int(count) * 448
    assert dot_max <= 1568 and raw_max <= 1318688 and guard_max <= 82418
    assert int(np.abs(sums).max()) <= 10549504
    magnitude, remainder = np.divmod(np.abs(sums), 256)
    rounded = magnitude + (remainder >= 128)
    rounded[sums < 0] *= -1
    expected = decode_gold_period(data["gold_gu_s24"][:3072])
    assert np.array_equal(rounded, expected), "full-period gold mismatch"
    assert np.all((rounded > -8388608) & (rounded < 8388607)), "unexpected saturation"
    # Direct scalar formula, full128groups, at row/half/tile/tail boundaries.
    samples = []
    for matrix in (0, 1):
        for row in (0, 7, 8, 15):
            for column in (0, 7, 8, 15, 16, 23, 24, 31, 14335):
                cp, accumulator = column % 32, 0
                for group in range(128):
                    dot = 0
                    for lane in range(32):
                        ad = (-1 if (lane + row + group) % 2 else 1) * (1 + (lane + 3 * row + group) % 7)
                        ww = (-1 if (lane + cp + group + matrix) % 2 else 1) * (1 + (3 * lane + 5 * cp + group + 2 * matrix) % 7)
                        dot += ad * ww
                    raw = dot * (17 + (row + group) % 13) * (19 + (cp + 3 * group + matrix) % 11)
                    total_shift = 28 + (row + group) % 3 + (cp + group + matrix) % 3
                    accumulator += raw // (1 << (total_shift - 24))
                mag = (abs(accumulator) + 128) // 256
                value = -mag if accumulator < 0 else mag
                assert value == int(expected[matrix, row, cp]), ("scalar mismatch", matrix, row, column)
                samples.append({"matrix": matrix, "row": row, "column": column, "s44": accumulator, "s24": value})
    stats = {"values": 458752, "nonzero": int(np.count_nonzero(expected)) * 448,
             "positive": int(np.count_nonzero(expected > 0)) * 448,
             "negative": int(np.count_nonzero(expected < 0)) * 448,
             "min": int(expected.min()), "max": int(expected.max()), "saturation_count": 0,
             "tail32_nonzero": int(np.count_nonzero(expected)),
             "tail_column_14335": expected[:, :, 31].tolist(),
             "per_row_nonzero": [int(np.count_nonzero(expected[:, row])) * 448 for row in range(16)],
             "per_matrix_half": []}
    for matrix in (0, 1):
        for half in (0, 1):
            selected = expected[matrix, :, [*range(half * 8, half * 8 + 8), *range(16 + half * 8, 24 + half * 8)]]
            stats["per_matrix_half"].append({"matrix": matrix, "logical_half": half,
                       "nonzero": int(np.count_nonzero(selected)) * 448,
                       "positive": int(np.count_nonzero(selected > 0)) * 448,
                       "negative": int(np.count_nonzero(selected < 0)) * 448})
    assert stats["nonzero"] == 458752 and stats["tail32_nonzero"] == 1024
    return {"verdict": "PASS", "scope": "all emitted wire bytes validated with exact contract formula, all448 periods, independent full-period integer oracle and scalar samples; board NOT_RUN",
            "files": artifacts.manifest["files"], "full_weight_records_checked": 229376,
            "period_checks": period_checks, "gold_MACs_per_independent_period_pass": 4194304,
            "all_output_values_checked_via_verified_periods": 458752,
            "activation_codes_nonzero": int(np.count_nonzero(ac)),
            "activation_q_minus_zp_nonzero": int(np.count_nonzero(delta)),
            "weight_codes_nonzero": int(metadata[:, :16].size),
            "weight_s4_values_nonzero": nonzero_weights,
            "metadata_padding_zero": True, "rec576_padding_reserved_zero": True,
            "canonical_zero_violation_count": 0, "nonzero_total_shift_counts": total_shift_counts,
            "dot_abs_max": dot_max, "raw_abs_max": raw_max, "guard_abs_max": guard_max,
            "sum_abs_max": int(np.abs(sums).max()), "output_statistics": stats,
            "scalar_samples_count": len(samples), "independent_scalar_literals": samples,
            "verification_seconds": time.monotonic() - started}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = verify_bundle(args.bundle)
    if args.out:
        write_json(args.out, result)
    print("DENSE_ACTIVE128_WIRE_VERIFY_PASS")
