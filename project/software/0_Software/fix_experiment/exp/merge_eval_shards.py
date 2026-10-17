#!/usr/bin/env python3
"""Merge disjoint dual-GPU worker manifests into one protocol result."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from protocol import PRIMARY_METRIC, TASK_ORDER


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-compatible-v5-format-policy",
        action="store_true",
        help=(
            "Allow strict and RTL-zero-guard V5 workers to merge when their "
            "numeric method is otherwise identical and every strict worker "
            "observed zero format errors."
        ),
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    temporary.replace(path)


def canonical_method(source: dict[str, Any]) -> dict[str, Any]:
    """Normalize backward-compatible manifest defaults before comparison.

    The format-v3 PPL runs predate the explicit ``mlp_down_output_width``
    provenance field.  Their numeric path nevertheless used the function
    default, S24.  New ACC workers record that value explicitly.  Treating the
    missing legacy field as a method mismatch would discard otherwise
    identical full-stream PPL evidence after the multi-hour ACC runs finish.
    A non-default value (for example the diagnostic S32 ablation) remains a
    real mismatch and is never normalized away.
    """
    method = dict(source.get("method") or {})
    if method.get("case") in {
        "v5_mlp_only_controlled_ablation",
        "v5_production_fullchain",
    }:
        method.setdefault("mlp_down_output_width", 24)
    return method


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "case",
        "protocol",
        "context_length",
        "task",
        "kind",
        "primary_metric",
        "value",
        "stderr",
        "samples",
        "truncated_documents",
        "truncated_document_fraction",
        "left_truncated_prompt_documents",
        "windowed_continuation_documents",
        "hardware_contract_status",
    ]
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in columns} for row in rows])
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    sources = []
    for source_dir in args.source:
        manifest_path = source_dir / "manifest.json"
        if not manifest_path.exists():
            state_path = source_dir / "run_state.json"
            detail = read_json(state_path) if state_path.exists() else {}
            raise FileNotFoundError(
                f"worker manifest missing: {manifest_path}; state={detail.get('status')} "
                f"error={detail.get('error')}"
            )
        sources.append(read_json(manifest_path))
    if not sources:
        raise ValueError("at least one source is required")

    identity_keys = ("model", "model_spec", "model_identity", "case", "seed", "versions")
    for key in identity_keys:
        values = {json.dumps(source[key], sort_keys=True) for source in sources}
        if len(values) != 1:
            raise ValueError(f"worker {key} mismatch: {values}")
    protocols = {json.dumps(source["protocol"], sort_keys=True) for source in sources}
    if len(protocols) != 1:
        raise ValueError("worker protocol mismatch")
    methods = {
        json.dumps(canonical_method(source), sort_keys=True) for source in sources
    }
    mixed_v5_format_policy = False
    if len(methods) != 1:
        if not args.allow_compatible_v5_format_policy:
            raise ValueError("worker method mismatch")

        def normalized_v5_method(source: dict[str, Any]) -> str:
            method = canonical_method(source)
            method.pop("strict_total_shift", None)
            method.pop("total_shift_policy", None)
            return json.dumps(method, sort_keys=True)

        normalized = {normalized_v5_method(source) for source in sources}
        if len(normalized) != 1:
            raise ValueError(
                "worker methods differ beyond the V5 total-shift policy"
            )
        for source in sources:
            method = source.get("method") or {}
            if method.get("strict_total_shift") and int(
                (source.get("hardware_audit") or {}).get(
                    "linear_total_shift_format_error", 0
                )
            ):
                raise ValueError(
                    "strict V5 source observed format errors and cannot be "
                    "merged with an RTL-zero-guard source"
                )
        mixed_v5_format_policy = True

    by_task: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for source in sources:
        for row in source["results"]:
            task = str(row["task"])
            if task in by_task:
                raise ValueError(f"task {task!r} appears in more than one shard")
            by_task[task] = (row, source)
    expected = set(TASK_ORDER) | {"wikitext2"}
    missing = expected - set(by_task)
    extra = set(by_task) - expected
    if missing or extra:
        raise ValueError(f"task coverage mismatch: missing={sorted(missing)}, extra={sorted(extra)}")

    order = list(TASK_ORDER) + ["wikitext2"]
    rows: list[dict[str, Any]] = []
    for task in order:
        raw, source = by_task[task]
        row = {
            **raw,
            "case": source["case"],
            "protocol": source["protocol"]["protocol"],
            "context_length": source["protocol"]["context_length"],
            "hardware_contract_status": source["hardware_contract_status"],
        }
        if row["kind"] == "acc":
            truncation = source.get("truncation_audit", {}).get(task, {})
            row.setdefault(
                "left_truncated_prompt_documents",
                truncation.get("left_truncated_prompt_documents"),
            )
            row.setdefault(
                "windowed_continuation_documents",
                truncation.get("windowed_continuation_documents"),
            )
        # Early smoke/full runs used bootstrap_iters=0, which suppresses even
        # lm_eval's analytic Bernoulli stderr. Recover the identical closed
        # form from the primary accuracy and sample count during merge.
        if row["kind"] == "acc" and row.get("stderr") is None:
            count = int(row["samples"])
            probability = float(row["value"])
            row["stderr"] = (
                math.sqrt(probability * (1.0 - probability) / (count - 1))
                if count > 1
                else None
            )
        rows.append(row)
    acc_rows = [row for row in rows if row["kind"] == "acc"]
    macro_acc = sum(float(row["value"]) for row in acc_rows) / len(acc_rows)
    statuses = {source["status"] for source in sources}
    hardware_statuses = {source["hardware_contract_status"] for source in sources}
    if "invalid_format_error" in hardware_statuses:
        hardware_status = "invalid_format_error"
    elif hardware_statuses == {"diagnostic_ablation_not_hardware"}:
        hardware_status = "diagnostic_ablation_not_hardware"
    elif "software_reference_not_hardware" in hardware_statuses:
        hardware_status = "software_reference_not_hardware"
    elif hardware_statuses == {"not_applicable_algorithm_reference"}:
        hardware_status = "not_applicable_algorithm_reference"
    else:
        hardware_status = "valid"
    status = (
        "complete_invalid_format_error"
        if hardware_status == "invalid_format_error"
        else ("complete" if statuses == {"complete"} else "inspect")
    )
    protocol = sources[0]["protocol"]
    hardware_audit_total: dict[str, int] = {}
    hardware_audit_by_module_total: dict[str, dict[str, int]] = {}
    for source in sources:
        for name, value in (source.get("hardware_audit") or {}).items():
            hardware_audit_total[name] = (
                hardware_audit_total.get(name, 0) + int(value)
            )
        for module, values in (
            source.get("hardware_audit_by_module") or {}
        ).items():
            target = hardware_audit_by_module_total.setdefault(module, {})
            for name, value in values.items():
                numeric = int(value)
                if name == "linear_total_shift_min":
                    target[name] = min(target.get(name, 127), numeric)
                elif name == "linear_total_shift_max":
                    target[name] = max(target.get(name, -1), numeric)
                else:
                    target[name] = target.get(name, 0) + numeric
    software_reference_numeric_status = None
    if hardware_status == "software_reference_not_hardware":
        software_overflow = (
            hardware_audit_total.get("linear_software_group_guard_overflow", 0)
            + hardware_audit_total.get("linear_software_accumulator_overflow", 0)
        )
        software_reference_numeric_status = (
            "valid_no_software_width_overflow"
            if software_overflow == 0
            else "invalid_software_width_overflow"
        )
    # Always materialize semantic defaults in the merged provenance, even
    # when the first source happens to be an older manifest.
    merged_method = canonical_method(sources[0])
    if mixed_v5_format_policy:
        merged_method["mixed_total_shift_policy"] = True
        merged_method["worker_total_shift_policies"] = sorted({
            "strict_rtl"
            if (source.get("method") or {}).get("strict_total_shift")
            else "rtl_zero_guard"
            for source in sources
        })
    manifest = {
        "schema": "scalellm_literature_aligned_eval_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "hardware_contract_status": hardware_status,
        "software_reference_numeric_status": software_reference_numeric_status,
        "hardware_audit_total": hardware_audit_total or None,
        "hardware_audit_by_module": hardware_audit_by_module_total or None,
        "model": sources[0]["model"],
        "model_spec": sources[0].get("model_spec"),
        "model_identity": sources[0].get("model_identity"),
        "case": sources[0]["case"],
        "method": merged_method,
        "protocol": protocol,
        "primary_metric_policy": PRIMARY_METRIC,
        "macro_accuracy": macro_acc,
        "macro_accuracy_unit": "fraction",
        "ppl": float(by_task["wikitext2"][0]["value"]),
        "results": rows,
        "worker_manifests": [
            {
                "cuda_visible_devices": source.get("cuda_visible_devices"),
                "gpu_name": source.get("gpu_name"),
                "tasks": source.get("tasks"),
                "status": source.get("status"),
                "elapsed_sec": source.get("elapsed_sec"),
                "method": source.get("method"),
                "hardware_audit": source.get("hardware_audit"),
                "data": source.get("data"),
                "model_fingerprint_sha256": (
                    (source.get("model_identity") or {}).get("fingerprint_sha256")
                ),
            }
            for source in sources
        ],
        "versions": sources[0]["versions"],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output / "manifest.json", manifest)
    write_csv(args.output / "summary.csv", rows)
    print(json.dumps({
        "status": status,
        "case": manifest["case"],
        "protocol": protocol["protocol"],
        "macro_accuracy": macro_acc,
        "ppl": manifest["ppl"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
