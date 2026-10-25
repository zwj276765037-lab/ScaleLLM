#!/usr/bin/env python3
"""Publish a local evidence summary without changing shared project indexes."""
import argparse
import datetime
import json
from pathlib import Path

import numpy as np

from diagnostic import DiagnosticArtifacts, decode_output, digest, json_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_root")
    args = parser.parse_args()
    results = Path(args.results_root).resolve()
    source = Path(__file__).resolve().parent
    root = next(parent for parent in source.parents if (parent / "project/hardware/host").is_dir())
    report = {"execution_state": "completed", "verdict": "CPU_PREPARATION_PASS",
              "stage": "diagnostic_delivery", "board_execution": "NOT_RUN_BY_DIAGNOSTIC_AUTHOR",
              "scope": "two complete production-shape diagnostic bundles and existing-backend driver; host owner runs actual device",
              "desired_model": "gpt-6.1-sol", "desired_effort": "xhigh", "actual_model": None, "actual_effort": None,
              "runtime_id": "/root/board_gu_vectors", "case_reports": {}, "source_identity": [],
              "updated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "ownership": "diagnostic_gu source/results only; original backend/RTL/ABI/catalog not changed"}
    for case in ("structured_v1", "s37_cancellation_v1"):
        bundle = results / case
        artifacts = DiagnosticArtifacts(bundle)
        manifest = artifacts.manifest
        checks = json.loads((bundle / "verification.json").read_text())
        values = decode_output(artifacts.records["gold_gu_s24"].read_verified())
        halves = []
        for matrix in (0, 1):
            for half in (0, 1):
                selected = values[matrix].reshape(16, 896, 16)[:, :, half * 8:(half + 1) * 8]
                halves.append({"matrix": ["gate", "up"][matrix], "logical_weight_half": half,
                               "values": int(selected.size), "nonzero": int(np.count_nonzero(selected)),
                               "positive": int(np.count_nonzero(selected > 0)), "negative": int(np.count_nonzero(selected < 0)),
                               "min": int(selected.min()), "max": int(selected.max())})
        literals = [entry for entry in checks["scalar_samples"] if entry["column"] in (0, 1, 7, 8, 15, 14335)]
        case_report = {"files": manifest["files"], "manifest_sha256": digest((bundle / "manifest.json").read_bytes()),
                       "verification_sha256": digest((bundle / "verification.json").read_bytes()),
                       "gold_statistics": manifest["gold_statistics"], "arithmetic": manifest["arithmetic"],
                       "per_matrix_half_statistics": halves, "independent_scalar_literals": literals,
                       "s36_mutation_witnesses": checks["s36_truncation_witnesses"],
                       "actual_total_shifts": checks["actual_nonzero_total_shifts"],
                       "verification_seconds": checks["verify_seconds"],
                       "original_exporter_parity": json.loads((bundle / "exporter_tile_parity.json").read_text())}
        json_write(bundle / "coverage_report.json", case_report)
        report["case_reports"][case] = case_report
    for path in sorted(source.glob("*.py")):
        report["source_identity"].append({"path": str(path.relative_to(root)), "size": path.stat().st_size,
                                           "sha256": digest(path.read_bytes())})
    report["driver_cpu_checks"] = json.loads((results / "driver_cpu_selfcheck_v1/result.json").read_text())
    json_write(results / "delivery_report.json", report)
    print("DIAGNOSTIC_DELIVERY_SUMMARY_WRITTEN")


if __name__ == "__main__":
    main()
