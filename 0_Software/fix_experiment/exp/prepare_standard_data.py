#!/usr/bin/env python3
"""Materialize the missing official ARC test splits under fpga_llm_project/data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from protocol import DATA_ROOT, TASK_SOURCES, data_manifest


ARC_REVISION = "210d026faf9955653af8916fad021475a3f00453"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Only verify files; do not download missing ARC test splits.",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    for task, config in (
        ("arc_easy", "ARC-Easy"),
        ("arc_challenge", "ARC-Challenge"),
    ):
        source = TASK_SOURCES[task]
        if source.path.exists() and not args.force:
            continue
        if args.offline:
            raise FileNotFoundError(
                f"{source.path} is required for the standard protocol"
            )
        from datasets import load_dataset

        dataset = load_dataset(
            "allenai/ai2_arc",
            config,
            split="test",
            revision=ARC_REVISION,
        )
        rows = [dict(row) for row in dataset]
        if len(rows) != source.expected_rows:
            raise ValueError(
                f"downloaded {task} has {len(rows)} rows; expected {source.expected_rows}"
            )
        write_jsonl(source.path, rows)

    manifest = {
        "schema": "scalellm_literature_eval_data_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_root": str(DATA_ROOT.resolve()),
        "arc_huggingface_revision": ARC_REVISION,
        "datasets": data_manifest(TASK_SOURCES, include_wikitext=True),
    }
    manifest_path = DATA_ROOT / "lm_eval_standard" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(manifest_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
