"""Recover exact discrete differences from immutable R006 full-tensor moments.

This only compares current output to the same-input OUTPUT_ONLY reference,
both on an F16 grid. It does not recover pre-rounding values or pointwise
relative errors. For |integer difference| <= 1, sum(d**2) is exactly the
number of changed outputs, without any assumption about the sign of d.
"""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS = HERE.parent.parent
MANIFEST = RUNS / "R006/session_S001/analysis_manifest.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_int(value):
    assert math.isfinite(value) and value == int(value), value
    return int(value)


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows, sources = [], []
    totals = defaultdict(lambda: defaultdict(float))
    seen = set()
    for group in manifest["ordered_groups"]:
        attempt = Path(group["attempt_path"])
        receipt_path = attempt / "execution_receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["exit_code"] == 0 and receipt["source_unchanged"]
        assert receipt["coverage_complete"]
        path = attempt / "local_tensor_metrics.jsonl"
        sources.append({"path": str(path), "sha256": sha256(path),
                        "receipt_path": str(receipt_path), "receipt_sha256": sha256(receipt_path)})
        for line in path.open():
            r = json.loads(line)
            if r.get("layer") != 31 or r.get("op") not in ("o_proj", "down_proj"):
                continue
            op, doc = r["op"], r["doc_id"]
            assert (op, doc) not in seen
            seen.add((op, doc))
            assert r["trajectory"] == "v5_current_local_paired"
            n = r["node_metadata"]
            assert n["comparison"] == "current_vs_output_only_common_exit"
            assert n["fractional_bits"] == 16
            N = r["counts"]["accepted_metric_elements"]
            assert N == n["count"] == r["counts"]["total_elements"]
            for key in ("saturation_count", "group_guard_overflow_count",
                        "software_group_guard_overflow_count", "accumulator_overflow_count",
                        "software_accumulator_overflow_count"):
                assert n["audit_current_delta"][key] == 0
            maxcode = n["max_abs"] * 65536
            assert 0 <= maxcode <= 1
            signed_sum = exact_int(n["sum_diff"] * 65536)
            squares = exact_int(n["sum_diff2"] * 4294967296)
            assert (squares + signed_sum) % 2 == 0
            plus = (squares + signed_sum) // 2
            minus = (squares - signed_sum) // 2
            zero = N - squares
            assert min(zero, plus, minus) >= 0
            assert zero + plus + minus == N
            row = dict(group=group["group_id"], doc_id=doc, operator=op,
                       scalar_count=N, identical_count=zero, minus_one_step_count=minus,
                       plus_one_step_count=plus, changed_count=squares,
                       changed_percent=100 * squares / N,
                       maximum_absolute_difference=n["max_abs"],
                       error_energy=n["sum_diff2"], signal_energy=n["sum_signal2"],
                       relative_l2_percent=n["relative_l2_percent"])
            rows.append(row)
            for key in ("scalar_count", "identical_count", "minus_one_step_count",
                        "plus_one_step_count", "changed_count", "error_energy", "signal_energy"):
                totals[op][key] += row[key]
            totals[op]["document_count"] += 1
    for op, total in totals.items():
        assert total["document_count"] == 1024
        for key in ("scalar_count", "identical_count", "minus_one_step_count",
                    "plus_one_step_count", "changed_count", "document_count"):
            total[key] = exact_int(total[key])
        N = total["scalar_count"]
        total["changed_percent"] = 100 * total["changed_count"] / N
        total["identical_percent"] = 100 * total["identical_count"] / N
        total["pooled_relative_l2_percent"] = 100 * math.sqrt(total["error_energy"] / total["signal_energy"])
        total["absolute_rmse"] = math.sqrt(total["error_energy"] / N)
        total["absolute_mean_difference"] = total["changed_count"] / N / 65536
        total["maximum_absolute_difference"] = max(r["maximum_absolute_difference"] for r in rows if r["operator"] == op)
    output = {
        "schema": "r010_existing_full1024_discrete_differences_v1",
        "method": "For F16 differences d in {-1,0,1}: changed=sum(d^2), positive=(sum(d^2)+sum(d))/2, negative=(sum(d^2)-sum(d))/2. Per-row integer/parity/nonnegative/closure assertions passed.",
        "comparison": "Original current output versus same-current-input OUTPUT_ONLY common F16 exit; isolates additional intermediate-rounding discrepancy on this output grid.",
        "not_measured": ["pre-final-round versus post-final-round loss", "pointwise relative error proportions", "causal fraction of the full32-layer end-to-end discrepancy"],
        "denominator": "All real accepted scalar outputs in layer31 o_proj/down_proj for the frozen 1024-document R006 dataset, 103700 token positions each operator.",
        "one_output_step": 1 / 65536,
        "fractional_bits": 16,
        "per_operator": dict(totals),
        "source_manifest": {"path": str(MANIFEST), "sha256": sha256(MANIFEST)},
        "sources": sources,
        "analysis_source_sha256": sha256(Path(__file__)),
    }
    (HERE / "full1024_output_differences.json").write_text(json.dumps(output, indent=2) + "\n")
    with (HERE / "full1024_output_differences_per_document.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(output["per_operator"], indent=2))


if __name__ == "__main__":
    main()
