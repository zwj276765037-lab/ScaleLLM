#!/usr/bin/env python3
"""Create a compact A/B table from run_model_ppl.py JSON outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = ["software", "pre_q_only", "rtl_exact"]
    records = {
        case: json.loads((args.input_dir / f"{case}.json").read_text(encoding="utf-8"))
        for case in cases
    }
    baseline = records["software"]["metrics"]
    rows = []
    for case in cases:
        result = records[case]
        metrics = result["metrics"]
        rows.append({
            "case": case,
            "activation_frontend": result["method"]["activation_frontend"],
            "samples": metrics["samples"],
            "num_tokens": metrics["num_tokens"],
            "ppl": metrics["ppl"],
            "ppl_delta_vs_software": metrics["ppl"] - baseline["ppl"],
            "ppl_relative_delta_vs_software": metrics["ppl"] / baseline["ppl"] - 1.0,
            "avg_nll": metrics["avg_nll"],
            "avg_nll_delta_vs_software": metrics["avg_nll"] - baseline["avg_nll"],
            "token_accuracy": metrics["token_accuracy"],
            "token_accuracy_delta_vs_software": (
                metrics["token_accuracy"] - baseline["token_accuracy"]),
            "finite": metrics["finite"],
            "status": metrics["status"],
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "comparison.csv").open(
            "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "schema": "scalellm_fp_to_q_ppl_comparison_v1",
        "baseline": "software",
        "controlled_variable": "activation frontend; folded weights and all evaluation settings are unchanged",
        "rows": rows,
    }
    (args.output_dir / "comparison.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

