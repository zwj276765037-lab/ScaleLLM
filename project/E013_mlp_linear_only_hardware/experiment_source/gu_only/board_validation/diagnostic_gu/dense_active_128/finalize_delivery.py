#!/usr/bin/env python3
"""Publish the new bundle's final runtime boundary; preserve all manifests."""
import argparse
import datetime
import json
from pathlib import Path

from dense import root_path, sha, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    args = parser.parse_args()
    bundle = Path(args.bundle).resolve()
    root = root_path()
    source = Path(__file__).resolve().parent
    verification = json.loads((bundle / "verification.json").read_text())
    manifest = json.loads((bundle / "manifest.json").read_text())
    prior = json.loads((bundle.parent / "delivery_report.json").read_text())
    preserved = []
    for entry in prior["source_identity"]:
        path = root / entry["path"]
        actual = sha(path.read_bytes())
        assert actual == entry["sha256"], f"old diagnostic source changed: {path}"
        preserved.append({"path": entry["path"], "sha256": actual})
    for old in ("structured_v1", "s37_cancellation_v1"):
        old_report = prior["case_reports"][old]
        old_bundle = bundle.parent / old
        assert sha((old_bundle / "manifest.json").read_bytes()) == old_report["manifest_sha256"]
        for name, entry in old_report["files"].items():
            path = old_bundle / entry["path"]
            assert path.stat().st_size == entry["size"] and sha(path.read_bytes()) == entry["sha256"]
    code_identity = [{"path": str(path.relative_to(root)), "size": path.stat().st_size,
                      "sha256": sha(path.read_bytes())} for path in sorted(source.glob("*")) if path.is_file()]
    report = {"execution_state": "completed", "stage": "dense128_diagnostic_delivery", "verdict": "CPU_PREPARATION_PASS",
              "board_execution": "NOT_RUN_BY_VECTOR_AUTHOR", "runtime_id": "/root/board_gu_vectors",
              "desired_model": "gpt-6.1-sol", "desired_effort": "xhigh", "actual_model": None, "actual_effort": None,
              "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "manifest_sha256": sha((bundle / "manifest.json").read_bytes()),
              "verification_sha256": sha((bundle / "verification.json").read_bytes()),
              "files": manifest["files"], "output_statistics": verification["output_statistics"],
              "nonzero_counts": {key: verification[key] for key in ("activation_codes_nonzero", "activation_q_minus_zp_nonzero", "weight_codes_nonzero", "weight_s4_values_nonzero")},
              "runtime_source_identity": code_identity,
              "version_boundary": "manifest source_identity is generation-time provenance; this delivery freezes final provider/verifier/runner/docs; binary inputs/gold and manifest unchanged",
              "old_source_hashes_preserved": preserved, "old_bundle_manifests_and_binary_hashes_preserved": True,
              "CPU_runner_pair_check": json.loads((bundle / "CPU_driver_pair_check/CPU_fixture_scope.json").read_text()),
              "limits": "32-column periodic diagnostic, not a model or maximum switching/power guarantee; actual measurement remains host-owned"}
    write_json(bundle / "delivery.json", report)
    print("DENSE_ACTIVE128_DELIVERY_FINALIZED")


if __name__ == "__main__":
    main()
