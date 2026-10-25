#!/usr/bin/env python3
"""Compare complete selected tiles with the original production exporter."""
import argparse
import importlib.util
from io import BytesIO
from pathlib import Path

import numpy as np

from diagnostic import DiagnosticArtifacts, active_groups, weights, digest, json_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / "project/hardware/host").is_dir())
    path = root / "project/software/model/export_scalellm_llama31_artifacts.py"
    spec = importlib.util.spec_from_file_location("original_exporter_packing", path)
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    artifacts = DiagnosticArtifacts(args.bundle)
    payloads = {name: artifacts.records[name].read_verified() for name in ("mlp_gate_up_c0", "mlp_gate_up_c1", "mlp_gate_meta")}
    case = artifacts.manifest["case"]
    checked = []
    for tile in (0, 1, 447, 448, 894, 895):
        for matrix in (0, 1):
            quantized = np.zeros((16, 128, 32), dtype=np.int8)
            codes = np.zeros((16, 128), dtype=np.uint8)
            shifts = np.zeros((16, 128), dtype=np.uint8)
            for group in active_groups(case):
                w, code, shift = weights(case, matrix, np.arange(tile * 16, tile * 16 + 16), group)
                quantized[:, group], codes[:, group], shifts[:, group] = w, code, shift
            writers = {key: BytesIO() for key in ("c0", "c1", "meta")}
            exporter._write_mlp_tile(writers, quantized, codes, shifts, 128)
            for writer, name, stride in (("c0", "mlp_gate_up_c0", 128), ("c1", "mlp_gate_up_c1", 128), ("meta", "mlp_gate_meta", 32)):
                offset = (2 * tile + matrix) * 128 * stride
                actual = payloads[name][offset:offset + 128 * stride]
                assert actual == writers[writer].getvalue(), (tile, matrix, name)
            checked.append({"tile16": tile, "matrix": matrix, "groups": 128, "parity": "PASS"})
    json_write(args.out, {"verdict": "PASS", "scope": "bounded complete-tile byte parity with original exporter; no numerical/DUT claim", "exporter": str(path.relative_to(root)), "exporter_sha256": digest(path.read_bytes()), "checks": checked})
    print(f"ORIGINAL_EXPORTER_PACKING_PASS tiles={len(checked)}")


if __name__ == "__main__":
    main()
