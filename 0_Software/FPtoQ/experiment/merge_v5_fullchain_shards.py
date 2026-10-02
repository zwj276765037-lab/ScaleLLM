#!/usr/bin/env python3
"""Merge disjoint V5 quality-evaluation shards into one audited result set."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_ORDER = (
    "wikitext2",
    "piqa",
    "arc_challenge",
    "openbookqa",
    "hellaswag",
    "winogrande",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        action="append",
        type=Path,
        required=True,
        help="V5 case directory; repeat for every disjoint task shard",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def coerce(value: str) -> Any:
    if value == "":
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def load_source(path: Path) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    state_path = manifest_path if manifest_path.exists() else path / "run_state.json"
    state = read_json(state_path)
    with (path / "quality_by_task.csv").open(newline="", encoding="utf-8") as handle:
        rows = [
            {key: coerce(value) for key, value in row.items() if value != ""}
            for row in csv.DictReader(handle)
        ]
    completed = {str(task) for task in state.get("completed_tasks", [])}
    if not completed:
        completed = {str(row["task"]) for row in rows}
    rows = [row for row in rows if str(row["task"]) in completed]

    records: list[dict[str, Any]] = []
    records_path = path / "mcqa_records.jsonl"
    if records_path.exists():
        with records_path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if str(record["task"]) in completed:
                    records.append(record)
    return {
        "path": str(path.resolve()),
        "state_file": state_path.name,
        "state": state,
        "rows": rows,
        "records": records,
        "completed": completed,
    }


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    sources = [load_source(path) for path in args.source]
    by_task: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for source in sources:
        for row in source["rows"]:
            task = str(row["task"])
            if task in by_task:
                raise ValueError(f"task {task!r} occurs in more than one shard")
            by_task[task] = (row, source)
    missing = [task for task in TASK_ORDER if task not in by_task]
    extra = sorted(set(by_task) - set(TASK_ORDER))
    if missing or extra:
        raise ValueError(f"task coverage mismatch: missing={missing}, extra={extra}")

    rows = [by_task[task][0] for task in TASK_ORDER]
    audit_keys: set[str] = set()
    for source in sources:
        audit_keys.update((source["state"].get("audit") or {}).keys())
    audit = {
        key: sum(
            int((source["state"].get("audit") or {}).get(key, 0))
            for source in sources
        )
        for key in sorted(audit_keys)
    }
    hardware_status = (
        "invalid_format_error"
        if audit.get("linear_total_shift_format_error", 0) > 0
        else "valid"
    )

    for row in rows:
        row["hardware_contract_status"] = hardware_status

    records_by_task: dict[str, list[dict[str, Any]]] = {
        task: [] for task in TASK_ORDER if task != "wikitext2"
    }
    for task in records_by_task:
        records_by_task[task] = [
            record
            for record in by_task[task][1]["records"]
            if str(record["task"]) == task
        ]
        expected = int(by_task[task][0]["samples"])
        if len(records_by_task[task]) != expected:
            raise ValueError(
                f"{task} record count {len(records_by_task[task])} != {expected}"
            )

    args.output.mkdir(parents=True, exist_ok=True)
    snapshots = args.output / "merge_sources"
    snapshots.mkdir(exist_ok=True)
    for index, source in enumerate(sources):
        source_path = Path(source["path"])
        for name in (
            "quality_by_task.csv",
            "mcqa_records.jsonl",
            source["state_file"],
        ):
            candidate = source_path / name
            if candidate.exists():
                shutil.copy2(candidate, snapshots / f"source{index}_{name}")

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    summary_tmp = (args.output / "quality_by_task.csv").with_suffix(".csv.tmp")
    with summary_tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary_tmp.replace(args.output / "quality_by_task.csv")

    records_tmp = (args.output / "mcqa_records.jsonl").with_suffix(".jsonl.tmp")
    with records_tmp.open("w", encoding="utf-8") as handle:
        for task in TASK_ORDER:
            for record in records_by_task.get(task, []):
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    records_tmp.replace(args.output / "mcqa_records.jsonl")

    primary_state = sources[0]["state"]
    complete_status = (
        "complete_invalid_format_error"
        if hardware_status != "valid"
        else "complete"
    )
    provenance = [
        {
            "path": source["path"],
            "state_file": source["state_file"],
            "completed_tasks": sorted(source["completed"]),
            "audit": source["state"].get("audit"),
        }
        for source in sources
    ]
    reproducibility = next(
        (
            source["state"]["reproducibility"]
            for source in sources
            if source["state"].get("reproducibility")
        ),
        None,
    )
    manifest = {
        "schema": "scalellm_v5_fullchain_quality_v1",
        "case": "v5",
        "status": complete_status,
        "hardware_contract_status": hardware_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_elapsed_sec_sum": sum(float(row["elapsed_sec"]) for row in rows),
        "method": primary_state.get("method"),
        "reproducibility": reproducibility,
        "merge_provenance": provenance,
        "audit": audit,
        "results": rows,
    }
    atomic_json(args.output / "manifest.json", manifest)
    atomic_json(
        args.output / "run_state.json",
        {
            "schema": manifest["schema"],
            "case": "v5",
            "status": complete_status,
            "hardware_contract_status": hardware_status,
            "completed_tasks": list(TASK_ORDER),
            "audit": audit,
        },
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
