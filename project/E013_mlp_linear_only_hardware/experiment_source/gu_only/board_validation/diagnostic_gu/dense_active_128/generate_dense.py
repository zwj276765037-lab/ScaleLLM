#!/usr/bin/env python3
"""Generate the frozen power/performance plan section4 diagnostic verbatim."""
import argparse
import datetime
from pathlib import Path
import sys
import time

import numpy as np

from dense import (KIND, SHAPE, SIZES, BIT_SHA, activation, weight, period_gold,
                   encode_gold_period, sha, write_json, root_path)


def generate(destination):
    started = time.monotonic()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    # Two consecutive tile16s are one 32-column period, each G then U.
    halves = [bytearray(65536), bytearray(65536)]
    meta = bytearray(16384)
    rec576 = bytearray(73728)
    for group in range(128):
        q, ac, ash = activation(group)
        base = group * 576
        rec576[base:base + 512] = q.astype(np.uint8).tobytes()
        for row in range(16):
            word = 128 | int(ac[row]) << 8 | int(ash[row]) << 16
            rec576[base + 512 + 3 * row:base + 515 + 3 * row] = word.to_bytes(3, "little")
        for matrix in (0, 1):
            w, wc, wsh = weight(matrix, group)
            for tile in (0, 1):
                record = (tile * 2 + matrix) * 128 + group
                for half in (0, 1):
                    flat = (w[tile * 16 + half * 8:tile * 16 + half * 8 + 8] & 15).astype(np.uint8).reshape(256)
                    packed = flat[0::2] | (flat[1::2] << 4)
                    halves[half][record * 128:(record + 1) * 128] = packed.tobytes()
                word = 0
                for local_column in range(16):
                    column = tile * 16 + local_column
                    word |= int(wc[column]) << (8 * local_column)
                    word |= int(wsh[column]) << (128 + 6 * local_column)
                meta[record * 32:record * 32 + 28] = word.to_bytes(28, "little")
    gold, arithmetic = period_gold()
    payloads = {"mlp_gate_up_c0": bytes(halves[0]) * 448,
                "mlp_gate_up_c1": bytes(halves[1]) * 448,
                "mlp_gate_meta": bytes(meta) * 448,
                "input_rec576": bytes(rec576), "gold_gu_s24": encode_gold_period(gold) * 448}
    files = {}
    for name, data in payloads.items():
        assert len(data) == SIZES[name]
        (destination / (name + ".bin")).write_bytes(data)
        files[name] = {"path": name + ".bin", "size": len(data), "sha256": sha(data)}
    root = root_path()
    sources = list(Path(__file__).parent.glob("*.py")) + [root / "mission/M006_mlp_linear_only_hardware/power_performance_plan_2026-10-25.md",
                root / "project/hardware/source/mlp_linear/abi_gu_only.json",
                root / "project/software/model/export_scalellm_llama31_artifacts.py",
                root / "project/hardware/model/mlp_fixed.py"]
    manifest = {"schema_kind": KIND, "schema_version": 1, "diagnostic_only": True,
                "model_catalog": False, "case": "dense_active_128_v1", "diagnostic_layer": 0,
                "shape": SHAPE, "column_period": 32, "period_repetitions": 448,
                "active_groups": list(range(128)), "bit_sha256": BIT_SHA,
                "formula_authority": "mission/M006_mlp_linear_only_hardware/power_performance_plan_2026-10-25.md section4",
                "gold_reference_MACs_per_pass": 4194304,
                "arithmetic": arithmetic, "files": files,
                "source_identity": [{"path": str(p.relative_to(root)), "sha256": sha(p.read_bytes()), "size": p.stat().st_size} for p in sorted(sources)],
                "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "generation_seconds": time.monotonic() - started,
                "scope": "all128 groups nonzero activation differences, weights and codes; periodic diagnostic, not real model or worst-case switching proof",
                "board_execution": "NOT_RUN_BY_VECTOR_AUTHOR", "gold_origin": "exact contract integer formula; never DUT output"}
    write_json(destination / "manifest.json", manifest)
    from verify_dense import verify_bundle
    verification = verify_bundle(destination)
    write_json(destination / "verification.json", verification)
    print(f"DENSE_ACTIVE128_PREPARATION_PASS {destination}")
    print(f"nonzero={verification['output_statistics']['nonzero']} positive={verification['output_statistics']['positive']} negative={verification['output_statistics']['negative']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    generate(parser.parse_args().out)
