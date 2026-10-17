#!/usr/bin/env python3
"""Validate and summarize the frozen six-model BF16/ScaleCode matrix."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from protocol import PRIMARY_METRIC, SOFTWARE_ROOT, TASK_ORDER, TASK_SOURCES
from six_model_matrix import FIVE_CONFIG_CASES, MODEL_SPECS


CASES = FIVE_CONFIG_CASES
THIS_DIR = Path(__file__).resolve().parent
CODE_IDENTITY_FILES = (
    THIS_DIR / "protocol.py",
    THIS_DIR / "run_eval_worker.py",
    THIS_DIR / "merge_eval_shards.py",
    THIS_DIR / "six_model_matrix.py",
    THIS_DIR / "audit_tokenizer_boundaries.py",
    THIS_DIR / "prepare_model_identity.py",
    THIS_DIR / "prepare_standard_data.py",
    THIS_DIR / "run_six_model_eval.py",
    SOFTWARE_ROOT
    / "0_Software"
    / "experiment"
    / "scripts"
    / "accuracy_MLP_4bit"
    / "mlp4_method_inference.py",
    SOFTWARE_ROOT
    / "0_Software"
    / "experiment"
    / "scripts"
    / "scale_code_linear"
    / "scalepath4_method_inference.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def code_identity() -> dict[str, Any]:
    """Content-address the numerical method and frozen evaluation pipeline."""
    files: list[dict[str, str]] = []
    for path in CODE_IDENTITY_FILES:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"code identity source is missing: {resolved}")
        files.append(
            {
                "path": str(resolved.relative_to(SOFTWARE_ROOT)),
                "sha256": sha256_file(resolved),
            }
        )
    payload = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "scalellm_algorithm_evaluation_code_identity_v1",
        "aggregate_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "files": files,
    }


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])
    temporary.replace(path)


def phase_manifest(root: Path, model: str, case: str) -> Path:
    return root / model / f"{case}_literature_2048" / "merged" / "manifest.json"


def validate_run(run: dict[str, Any], model: str, case: str) -> None:
    if run.get("status") != "complete":
        raise ValueError(f"{model}/{case}: status={run.get('status')}")
    if run.get("case") != case:
        raise ValueError(f"{model}/{case}: case mismatch {run.get('case')}")
    protocol = run.get("protocol", {})
    expected_protocol = {
        "protocol": "literature_2048",
        "context_length": 2048,
        "full_split": True,
        "literature_comparable": True,
        "hardware_constrained": False,
    }
    for key, expected in expected_protocol.items():
        if protocol.get(key) != expected:
            raise ValueError(
                f"{model}/{case}: protocol {key}={protocol.get(key)!r}, expected={expected!r}"
            )
    identity = run.get("model_identity") or {}
    if identity.get("checkpoint_name") != model or not identity.get("fingerprint_sha256"):
        raise ValueError(f"{model}/{case}: missing or mismatched checkpoint identity")
    by_task = {str(row["task"]): row for row in run.get("results", [])}
    expected_tasks = set(TASK_ORDER) | {"wikitext2"}
    if set(by_task) != expected_tasks:
        raise ValueError(
            f"{model}/{case}: task coverage={sorted(by_task)}, expected={sorted(expected_tasks)}"
        )
    for task in TASK_ORDER:
        row = by_task[task]
        if row.get("primary_metric") != PRIMARY_METRIC[task]:
            raise ValueError(f"{model}/{case}/{task}: primary metric mismatch")
        if int(row.get("samples", -1)) != TASK_SOURCES[task].expected_rows:
            raise ValueError(f"{model}/{case}/{task}: sample count mismatch")
        if not math.isfinite(float(row["value"])):
            raise ValueError(f"{model}/{case}/{task}: non-finite value")
        if row.get("stderr") is None or not math.isfinite(float(row["stderr"])):
            raise ValueError(f"{model}/{case}/{task}: missing/non-finite stderr")
    ppl = by_task["wikitext2"]
    if not ppl.get("full_stream") or int(ppl.get("block_size", -1)) != 2048:
        raise ValueError(f"{model}/{case}: PPL is not a complete 2048-block run")
    if not ppl.get("non_overlapping") or ppl.get("tail_policy") != "drop_incomplete_block":
        raise ValueError(f"{model}/{case}: PPL blocking policy mismatch")
    if not math.isfinite(float(ppl["value"])) or int(ppl.get("scoring_tokens", 0)) <= 0:
        raise ValueError(f"{model}/{case}: invalid PPL value/token count")


def run_to_row(run: dict[str, Any]) -> dict[str, Any]:
    by_task = {str(row["task"]): row for row in run["results"]}
    identity = run["model_identity"]
    row: dict[str, Any] = {
        "model": identity["checkpoint_name"],
        "model_fingerprint_sha256": identity["fingerprint_sha256"],
        "case": run["case"],
        "context_length": run["protocol"]["context_length"],
        "full_split": run["protocol"]["full_split"],
    }
    for task in TASK_ORDER:
        row[task] = float(by_task[task]["value"])
        row[f"{task}_stderr"] = float(by_task[task]["stderr"])
        row[f"{task}_samples"] = int(by_task[task]["samples"])
    ppl = by_task["wikitext2"]
    row.update(
        {
            "macro_accuracy": float(run["macro_accuracy"]),
            "ppl": float(ppl["value"]),
            "ppl_raw_tokens": int(ppl["raw_token_count"]),
            "ppl_blocks": int(ppl["evaluated_blocks"]),
            "ppl_scoring_tokens": int(ppl["scoring_tokens"]),
            "ppl_tail_tokens": int(ppl["discarded_tail_tokens"]),
            "status": run["status"],
        }
    )
    return row


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    runs: dict[tuple[str, str], dict[str, Any]] = {}
    missing: list[str] = []
    errors: list[str] = []
    sources: list[str] = []
    boundary_audits: list[dict[str, Any]] = []
    boundary_audit_sources: list[str] = []
    for spec in MODEL_SPECS:
        audit_path = root / "tokenizer_boundary_audits" / f"{spec.name}.json"
        if not audit_path.exists():
            errors.append(f"{spec.name}: missing tokenizer boundary audit")
            continue
        audit = read_json(audit_path)
        identity_path = root / "model_identities" / f"{spec.name}.json"
        identity = read_json(identity_path) if identity_path.exists() else {}
        if (
            audit.get("schema") != "scalellm_tokenizer_boundary_audit_v1"
            or audit.get("checkpoint_name") != spec.name
            or audit.get("model_fingerprint_sha256")
            != identity.get("fingerprint_sha256")
            or int(audit.get("total_requests", -1)) != 67106
            or int(audit.get("empty_continuations_after_fix", -1)) != 0
        ):
            errors.append(f"{spec.name}: invalid tokenizer boundary audit")
            continue
        boundary_audits.append(audit)
        boundary_audit_sources.append(str(audit_path))
    for spec in MODEL_SPECS:
        for case in CASES:
            path = phase_manifest(root, spec.name, case)
            if not path.exists():
                missing.append(f"{spec.name}/{case}")
                continue
            try:
                run = read_json(path)
                validate_run(run, spec.name, case)
                runs[(spec.name, case)] = run
                sources.append(str(path))
            except Exception as exc:  # preserve every failed validation in the plan manifest
                errors.append(f"{spec.name}/{case}: {type(exc).__name__}: {exc}")
    complete = not missing and not errors and len(runs) == len(MODEL_SPECS) * len(CASES)
    if not complete and not args.allow_incomplete:
        raise RuntimeError(f"six-model result is incomplete: missing={missing}, errors={errors}")

    summary_rows = [
        run_to_row(runs[(spec.name, case)])
        for spec in MODEL_SPECS
        for case in CASES
        if (spec.name, case) in runs
    ]
    summary_columns = [
        "model", "model_fingerprint_sha256", "case", "context_length", "full_split",
    ]
    for task in TASK_ORDER:
        summary_columns.extend([task, f"{task}_stderr", f"{task}_samples"])
    summary_columns.extend([
        "macro_accuracy", "ppl", "ppl_raw_tokens", "ppl_blocks",
        "ppl_scoring_tokens", "ppl_tail_tokens", "status",
    ])
    write_csv(root / "six_model_summary.csv", summary_rows, summary_columns)

    five_config_delta_rows: list[dict[str, Any]] = []
    for spec in MODEL_SPECS:
        baseline = runs.get((spec.name, "bf16"))
        if baseline is None:
            continue
        baseline_tasks = {row["task"]: row for row in baseline["results"]}
        for case in CASES:
            if case == "bf16":
                continue
            quantized = runs.get((spec.name, case))
            if quantized is None:
                continue
            if (
                baseline["model_identity"]["fingerprint_sha256"]
                != quantized["model_identity"]["fingerprint_sha256"]
            ):
                errors.append(f"{spec.name}: BF16/{case} fingerprint mismatch")
                continue
            quantized_tasks = {row["task"]: row for row in quantized["results"]}
            delta: dict[str, Any] = {
                "model": spec.name,
                "model_fingerprint_sha256": baseline["model_identity"]["fingerprint_sha256"],
                "case": case,
            }
            for task in TASK_ORDER:
                delta[f"{task}_delta_pp"] = 100.0 * (
                    float(quantized_tasks[task]["value"])
                    - float(baseline_tasks[task]["value"])
                )
            delta["macro_accuracy_delta_pp"] = 100.0 * (
                float(quantized["macro_accuracy"])
                - float(baseline["macro_accuracy"])
            )
            delta["ppl_bf16"] = float(baseline["ppl"])
            delta["ppl_quantized"] = float(quantized["ppl"])
            delta["ppl_relative_change_percent"] = 100.0 * (
                float(quantized["ppl"]) / float(baseline["ppl"]) - 1.0
            )
            five_config_delta_rows.append(delta)
    five_config_delta_columns = ["model", "model_fingerprint_sha256", "case"] + [
        f"{task}_delta_pp" for task in TASK_ORDER
    ] + [
        "macro_accuracy_delta_pp", "ppl_bf16", "ppl_quantized",
        "ppl_relative_change_percent",
    ]
    write_csv(
        root / "five_config_delta.csv",
        five_config_delta_rows,
        five_config_delta_columns,
    )
    reference_delta_rows = []
    for row in five_config_delta_rows:
        if row["case"] != "reference_qdq":
            continue
        reference_delta_rows.append({
            **{key: value for key, value in row.items() if key not in {"case", "ppl_quantized"}},
            "ppl_reference_qdq": row["ppl_quantized"],
        })
    legacy_delta_columns = ["model", "model_fingerprint_sha256"] + [
        f"{task}_delta_pp" for task in TASK_ORDER
    ] + [
        "macro_accuracy_delta_pp", "ppl_bf16", "ppl_reference_qdq",
        "ppl_relative_change_percent",
    ]
    write_csv(root / "six_model_delta.csv", reference_delta_rows, legacy_delta_columns)

    manifest = {
        "schema": "scalellm_six_model_five_config_acc_ppl_summary_v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if complete and not errors else "incomplete",
        "protocol": "literature_2048",
        "models_expected": [spec.name for spec in MODEL_SPECS],
        "cases_expected": list(CASES),
        "completed_model_cases": [f"{model}/{case}" for model, case in runs],
        "missing": missing,
        "validation_errors": errors,
        "code_identity": code_identity(),
        "source_manifests": sources,
        "tokenizer_boundary_audits": boundary_audits,
        "tokenizer_boundary_audit_sources": boundary_audit_sources,
        "summary_csv": str((root / "six_model_summary.csv").resolve()),
        "delta_csv": str((root / "six_model_delta.csv").resolve()),
        "five_config_delta_csv": str((root / "five_config_delta.csv").resolve()),
    }
    atomic_json(root / "experiment_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest["status"] != "complete" and not args.allow_incomplete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
