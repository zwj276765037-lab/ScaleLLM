#!/usr/bin/env python3
"""Independently decode emitted wire records and recompute every GU output."""
import argparse
from pathlib import Path
import sys
import time

import numpy as np

from diagnostic import (DiagnosticArtifacts, SIZES, active_groups, decode_output,
                        output_statistics, digest, json_write)


def verify_bundle(bundle):
    start = time.monotonic()
    artifacts = DiagnosticArtifacts(bundle)
    data = {name: record.read_verified() for name, record in artifacts.records.items()}
    groups = active_groups(artifacts.manifest["case"])
    inactive = np.array([group not in groups for group in range(128)])
    packed_meta = np.frombuffer(data["mlp_gate_meta"], np.uint8).reshape(1792, 128, 32)
    assert not np.any(packed_meta[:, :, 28:]), "nonzero metadata padding"
    assert not np.any(packed_meta[:, inactive]), "unclaimed metadata group"
    packed_halves = [np.frombuffer(data[name], np.uint8).reshape(1792, 128, 128)
                     for name in ("mlp_gate_up_c0", "mlp_gate_up_c1")]
    for half in packed_halves:
        assert not np.any(half[:, inactive]), "unclaimed weight group"
    activation_wire = np.frombuffer(data["input_rec576"], np.uint8).reshape(128, 576)
    assert not np.any(activation_wire[:, 560:]), "nonzero REC576 padding"
    assert not np.any(activation_wire[inactive]), "unclaimed input group"
    q = activation_wire[:, :512].reshape(128, 16, 32).astype(np.int64)
    am = activation_wire[:, 512:560].reshape(128, 16, 3).astype(np.int64)
    am = am[..., 0] + 256 * am[..., 1] + 65536 * am[..., 2]
    assert not np.any(am & 0xC00000), "nonzero activation reserved bits"
    zp, acode, ashift = am & 255, (am >> 8) & 255, (am >> 16) & 63
    zero = acode == 0
    assert not np.any(am[zero]) and not np.any(q[zero]), "noncanonical activation zero"
    decoded = np.zeros((2, 16, 14336), dtype=np.int64)
    scalar_samples = []
    # This wire oracle deliberately uses floor division / multiplication rather
    # than source_gold's vector shift implementation and output packing path.
    shifted = set()
    outside_s36 = 0
    scalar_coords = {(matrix, row, col) for matrix in (0, 1)
                     for row in (0, 7, 8, 15)
                     for col in (0, 1, 7, 8, 15, 16, 23, 24, 47, 48, 14303, 14304, 14327, 14328, 14335)}
    scalar_acc = {coord: 0 for coord in scalar_coords}
    guard36_acc = {coord: 0 for coord in scalar_coords}
    for record in range(1792):
        tile, matrix = record // 2, record % 2
        acc = np.zeros((16, 16), dtype=np.int64)
        for group in groups:
            raw_meta = packed_meta[record, group]
            codes = raw_meta[:16].astype(np.int64)
            shift_word = int.from_bytes(raw_meta[16:28].tobytes(), "little")
            shifts = np.array([(shift_word >> (6 * column)) & 63 for column in range(16)])
            columns = []
            for half in packed_halves:
                packed = half[record, group]
                nibble = np.empty(256, dtype=np.int64)
                nibble[0::2], nibble[1::2] = packed & 15, packed >> 4
                columns.append(np.where(nibble >= 8, nibble - 16, nibble).reshape(8, 32))
            w = np.concatenate(columns, axis=0)
            assert not np.any(shifts[codes == 0]) and not np.any(w[codes == 0]), "noncanonical weight zero"
            dots = (q[group] - zp[group, :, None]) @ w.T
            assert np.all((dots >= -65536) & (dots < 65536)), "S17 overflow"
            raw = dots * acode[group, :, None] * codes[None, :]
            assert np.all((raw >= -(1 << 32)) & (raw < (1 << 32))), "S33 overflow"
            contribution = np.zeros((16, 16), dtype=np.int64)
            for column in range(16):
                for row in range(16):
                    if acode[group, row] == 0 or codes[column] == 0:
                        continue
                    total_shift = int(ashift[group, row] + shifts[column])
                    assert 20 <= total_shift <= 44
                    shifted.add(total_shift)
                    value = int(raw[row, column])
                    value = value * 2 ** (24 - total_shift) if total_shift <= 24 else value // 2 ** (total_shift - 24)
                    assert -(1 << 36) <= value < (1 << 36), "S37 overflow"
                    outside_s36 += int(not -(1 << 35) <= value < (1 << 35))
                    contribution[row, column] = value
                    coord = (matrix, row, tile * 16 + column)
                    if coord in scalar_acc:
                        # Separate Python-integer dot across all 32 lanes.
                        dot_scalar = sum((int(q[group, row, lane]) - int(zp[group, row])) * int(w[column, lane]) for lane in range(32))
                        raw_scalar = dot_scalar * int(acode[group, row]) * int(codes[column])
                        guard_scalar = raw_scalar * (1 << (24 - total_shift)) if total_shift < 24 else raw_scalar // (1 << (total_shift - 24))
                        assert guard_scalar == value
                        scalar_acc[coord] += guard_scalar
                        truncated36 = (guard_scalar + (1 << 35)) % (1 << 36) - (1 << 35)
                        guard36_acc[coord] += truncated36
            acc += contribution
            assert np.all((acc >= -(1 << 43)) & (acc < (1 << 43))), "S44 overflow"
        rounded = (np.abs(acc) + 128) // 256
        rounded[acc < 0] *= -1
        decoded[matrix, :, tile * 16:tile * 16 + 16] = np.minimum(8388607, np.maximum(-8388608, rounded))
    expected = decode_output(data["gold_gu_s24"])
    mismatches = np.argwhere(decoded != expected)
    if mismatches.size:
        matrix, row, column = map(int, mismatches[0])
        raise AssertionError(f"wire gold mismatch matrix={matrix} row={row} column={column}: computed={decoded[matrix,row,column]} gold={expected[matrix,row,column]}")
    mutation_witnesses = []
    for coord, accumulator in sorted(scalar_acc.items()):
        magnitude = (abs(accumulator) + 128) // 256
        exact = max(-8388608, min(8388607, -magnitude if accumulator < 0 else magnitude))
        assert exact == int(expected[coord])
        scalar_samples.append({"matrix": coord[0], "row": coord[1], "column": coord[2], "s44": accumulator, "s24": exact})
        mutated = guard36_acc[coord]
        magnitude = (abs(mutated) + 128) // 256
        mutated_out = max(-8388608, min(8388607, -magnitude if mutated < 0 else magnitude))
        if mutated_out != exact:
            mutation_witnesses.append({"matrix": coord[0], "row": coord[1], "column": coord[2], "correct": exact, "truncated_s36": mutated_out})
    # Compare public wire codecs as a third packing cross-check only.
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "project/hardware/host").is_dir())
    sys.path.insert(0, str(root / "project/hardware"))
    from host.scalellm_mlp_linear import unpack_a8_rec576, unpack_gu_interleaved_s24, pack_a8_rec576
    public_q, public_meta = unpack_a8_rec576(data["input_rec576"], groups=128)
    assert pack_a8_rec576(public_q, public_meta) == data["input_rec576"]
    public_output = np.stack(unpack_gu_interleaved_s24(data["gold_gu_s24"]))
    assert np.array_equal(expected, public_output)
    stats = output_statistics(expected)
    assert stats["nonzero"] and stats["tail_block_nonzero"]
    assert all(stats["per_row_nonzero"]) and all(stats["per_matrix_nonzero"])
    if artifacts.manifest["case"] == "structured":
        assert stats["negative"] and stats["positive"]
        assert np.all(expected[:, :, 0] == 1) and np.all(expected[:, :, 1] == -1)
        assert np.all(expected[:, :, 7] == 8388607) and np.all(expected[:, :, 8] == -8388608)
    else:
        assert outside_s36 > 0 and mutation_witnesses and not stats["saturation_endpoint_count"]
    return {"verdict": "PASS", "scope": "CPU full-shape source gold versus independently decoded wire integer oracle; board NOT_RUN",
            "files": artifacts.manifest["files"], "all_output_values_checked": int(expected.size),
            "scalar_samples": scalar_samples, "scalar_samples_count": len(scalar_samples),
            "active_groups": list(groups), "metadata_records": 229376, "output_records": 1792,
            "all_inactive_groups_zero": True, "metadata_padding_zero": True,
            "rec576_padding_reserved_zero": True, "canonical_zero": True,
            "actual_nonzero_total_shifts": sorted(shifted), "guard_outside_s36_count": outside_s36,
            "s36_truncation_witnesses": mutation_witnesses[:16], "gold_statistics": stats,
            "verify_seconds": time.monotonic() - start}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = verify_bundle(args.bundle)
    if args.out:
        json_write(args.out, result)
    print(f"DIAGNOSTIC_VERIFY_PASS values={result['all_output_values_checked']} scalar={result['scalar_samples_count']} shifts={result['actual_nonzero_total_shifts']}")
