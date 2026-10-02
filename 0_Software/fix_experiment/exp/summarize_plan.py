#!/usr/bin/env python3
"""Create a paper-facing summary without mixing incompatible protocols."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--baseline-manifest",
        action="append",
        type=Path,
        default=[],
        help="Optional completed BF16 merged manifest outside --root.",
    )
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    args = parse_args()
    manifests = sorted(
        {
            *(path.resolve() for path in args.root.glob("*/merged/manifest.json")),
            *(path.resolve() for path in args.baseline_manifest),
        }
    )
    runs = [load(path) for path in manifests]
    rows: list[dict[str, Any]] = []
    for run in runs:
        audit = run.get("hardware_audit_total") or {}
        rows.append(
            {
                "run_status": run["status"],
                "case": run["case"],
                "protocol": run["protocol"]["protocol"],
                "context_length": run["protocol"]["context_length"],
                "full_split": run["protocol"]["full_split"],
                "protocol_literature_comparable": run["protocol"][
                    "literature_comparable"
                ],
                "hardware_constrained": run["protocol"]["hardware_constrained"],
                "hardware_contract_status": run["hardware_contract_status"],
                "software_reference_numeric_status": run.get(
                    "software_reference_numeric_status"
                ),
                "macro_accuracy": run["macro_accuracy"],
                "ppl": run["ppl"],
                "linear_total_shift_format_error": audit.get(
                    "linear_total_shift_format_error", ""
                ),
                "linear_group_guard_overflow_s37": audit.get(
                    "linear_group_guard_overflow_s37", ""
                ),
                "linear_software_group_guard_overflow": audit.get(
                    "linear_software_group_guard_overflow", ""
                ),
                "linear_accumulator_overflow": audit.get(
                    "linear_accumulator_overflow", ""
                ),
                "linear_software_accumulator_overflow": audit.get(
                    "linear_software_accumulator_overflow", ""
                ),
                "linear_output_saturation": audit.get(
                    "linear_output_saturation", ""
                ),
                "matched_bf16_delta_acc_pp": "",
                "matched_bf16_delta_ppl_percent": "",
                "cross_protocol_comparison_allowed": False,
                "error": "",
            }
        )
    completed_phase_dirs = {path.parent.parent.resolve() for path in manifests}
    for phase_dir in sorted(path for path in args.root.iterdir() if path.is_dir()):
        if phase_dir.resolve() in completed_phase_dirs:
            continue
        state_paths = sorted(phase_dir.glob("shard_gpu*/run_state.json"))
        if not state_paths:
            continue
        states = [load(path) for path in state_paths]
        representative = states[0]
        protocol = representative.get("protocol", {})
        errors = [
            f"{state.get('cuda_visible_devices')}: {state.get('error')}"
            for state in states
            if state.get("error")
        ]
        rows.append(
            {
                "run_status": (
                    "failed" if any(state.get("status") == "failed" for state in states)
                    else "incomplete"
                ),
                "case": representative.get("case", phase_dir.name.split("_", 1)[0]),
                "protocol": protocol.get("protocol", "unknown"),
                "context_length": protocol.get("context_length", ""),
                "full_split": protocol.get("full_split", ""),
                "protocol_literature_comparable": protocol.get(
                    "literature_comparable", False
                ),
                "hardware_constrained": protocol.get("hardware_constrained", False),
                "hardware_contract_status": "strict_failure_before_metrics",
                "software_reference_numeric_status": "",
                "macro_accuracy": "",
                "ppl": "",
                "linear_total_shift_format_error": "",
                "linear_group_guard_overflow_s37": "",
                "linear_software_group_guard_overflow": "",
                "linear_accumulator_overflow": "",
                "linear_software_accumulator_overflow": "",
                "linear_output_saturation": "",
                "matched_bf16_delta_acc_pp": "",
                "matched_bf16_delta_ppl_percent": "",
                "cross_protocol_comparison_allowed": False,
                "error": " | ".join(errors),
            }
        )
    by_key = {(row["case"], row["protocol"]): row for row in rows}
    for row in rows:
        if row["case"] not in {
            "reference_qdq", "v5_attention", "v5_mlp", "v5", "v5_algorithm"
        } or row["run_status"] != "complete":
            continue
        baseline = by_key.get(("bf16", row["protocol"]))
        if baseline is None:
            continue
        if not row["full_split"] or not baseline["full_split"]:
            continue
        row["matched_bf16_delta_acc_pp"] = 100.0 * (
            float(row["macro_accuracy"]) - float(baseline["macro_accuracy"])
        )
        row["matched_bf16_delta_ppl_percent"] = 100.0 * (
            float(row["ppl"]) / float(baseline["ppl"]) - 1.0
        )
        row["cross_protocol_comparison_allowed"] = True

    args.root.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    csv_path = args.root / "paper_summary.csv"
    temporary = csv_path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(csv_path)
    manifest = {
        "schema": "scalellm_acc_ppl_plan_summary_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule": (
            "Only compare BF16 and Reference-QDQ/V5/V5-algorithm when protocol "
            "names and context lengths match. Reference-QDQ is the algorithm "
            "quality result; V5-algorithm is a software numeric reference, not "
            "a hardware-valid result. Never compare hardware_128 PPL against "
            "literature_2048 PPL."
        ),
        "runs": rows,
        "source_manifests": [str(path.resolve()) for path in manifests],
    }
    manifest_path = args.root / "paper_manifest.json"
    temporary = manifest_path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(manifest_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
