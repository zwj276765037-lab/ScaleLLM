#!/usr/bin/env python3
"""Generate an explicit diagnostic layer with complete production byte sizes."""
import argparse
import datetime
from pathlib import Path
import sys
import time

import numpy as np

from diagnostic import (KIND, SIZES, TILES, active_groups, activation, weights,
                        source_gold, pack_output, digest, json_write,
                        output_statistics)


def project_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "project/hardware/source/mlp_linear/abi_gu_only.json").is_file():
            return parent
    raise RuntimeError("cannot locate project root")


def generate(destination, case):
    started = time.monotonic()
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    half = [bytearray(SIZES["mlp_gate_up_c0"]), bytearray(SIZES["mlp_gate_up_c1"])]
    meta = bytearray(SIZES["mlp_gate_meta"])
    rec576 = bytearray(SIZES["input_rec576"])
    for group in active_groups(case):
        q, zp, code, shift = activation(case, group)
        assert np.all((q >= 0) & (q <= 255))
        record = group * 576
        rec576[record:record + 512] = q.astype(np.uint8).tobytes()
        for row in range(16):
            word = int(zp[row]) | (int(code[row]) << 8) | (int(shift[row]) << 16)
            rec576[record + 512 + row * 3:record + 515 + row * 3] = word.to_bytes(3, "little")
    for tile in range(TILES):
        columns = np.arange(tile * 16, tile * 16 + 16)
        for matrix in (0, 1):
            for group in active_groups(case):
                w, code, shift = weights(case, matrix, columns, group)
                record = (tile * 2 + matrix) * 128 + group
                nibble = (w & 15).astype(np.uint8).reshape(2, 256)
                for logical_half in (0, 1):
                    packed = nibble[logical_half, 0::2] | (nibble[logical_half, 1::2] << 4)
                    half[logical_half][record * 128:(record + 1) * 128] = packed.tobytes()
                word = 0
                for column in range(16):
                    word |= int(code[column]) << (8 * column)
                    word |= int(shift[column]) << (128 + 6 * column)
                meta[record * 32:record * 32 + 28] = word.to_bytes(28, "little")
    outputs, arithmetic = source_gold(case)
    payloads = {"mlp_gate_up_c0": half[0], "mlp_gate_up_c1": half[1],
                "mlp_gate_meta": meta, "input_rec576": rec576,
                "gold_gu_s24": pack_output(outputs)}
    files = {}
    for name, data in payloads.items():
        assert len(data) == SIZES[name]
        filename = name + ".bin"
        (destination / filename).write_bytes(data)
        files[name] = {"path": filename, "size": len(data), "sha256": digest(data)}
    root = project_root()
    source_paths = [Path(__file__), Path(__file__).with_name("diagnostic.py"),
                    root / "project/hardware/source/mlp_linear/abi_gu_only.json",
                    root / "project/software/model/export_scalellm_llama31_artifacts.py",
                    root / "project/hardware/model/mlp_fixed.py",
                    root / "project/hardware/host/scalellm_mlp_linear.py"]
    sources = [{"path": str(path.relative_to(root)), "sha256": digest(path.read_bytes())}
               for path in source_paths]
    manifest = {"schema_kind": KIND, "schema_version": 1, "diagnostic_only": True,
                "case": case, "diagnostic_layer": 0, "model_catalog": False,
                "shape": {"rows": 16, "groups": 128, "k": 4096, "n": 14336},
                "active_groups": list(active_groups(case)), "files": files,
                "bit_sha256": "66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47",
                "arithmetic": arithmetic, "gold_statistics": output_statistics(outputs),
                "source_identity": sources, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "generation_seconds": time.monotonic() - started,
                "board_execution": "NOT_RUN", "gold_origin": "independent exact sparse integer source; no DUT reads"}
    json_write(destination / "manifest.json", manifest)
    from verify import verify_bundle
    checks = verify_bundle(destination)
    json_write(destination / "verification.json", checks)
    print(f"DIAGNOSTIC_GENERATION_PASS {destination}")
    print(f"case={case} nonzero={checks['gold_statistics']['nonzero']} negative={checks['gold_statistics']['negative']} tail_nonzero={checks['gold_statistics']['tail_block_nonzero']}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--case", choices=("structured", "s37_cancellation"), default="structured")
    args = parser.parse_args()
    generate(args.out, args.case)
