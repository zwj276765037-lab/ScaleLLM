#!/usr/bin/env python3
"""Create a content-addressed identity manifest for one local checkpoint."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from six_model_matrix import get_model_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checkpoint_files(model: Path) -> list[Path]:
    files = sorted(path for path in model.iterdir() if path.is_file())
    if not files:
        raise ValueError(f"checkpoint contains no files: {model}")
    if not any(path.suffix in {".safetensors", ".bin"} for path in files):
        raise ValueError(f"checkpoint contains no weight shards: {model}")
    required = {"config.json", "tokenizer_config.json"}
    missing = sorted(name for name in required if not (model / name).is_file())
    if missing:
        raise FileNotFoundError(f"checkpoint missing required files: {missing}")
    return files


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    model = args.model.resolve()
    spec = get_model_spec(model)
    entries = []
    for path in checkpoint_files(model):
        stat = path.stat()
        entries.append(
            {
                "name": path.name,
                "bytes": stat.st_size,
                "sha256": sha256_file(path),
            }
        )
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    value = {
        "schema": "scalellm_checkpoint_identity_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint_name": spec.name,
        "resolved_path": str(model),
        "fingerprint_sha256": fingerprint,
        "total_bytes": sum(int(entry["bytes"]) for entry in entries),
        "file_count": len(entries),
        "files": entries,
        "model_spec": spec.to_dict(),
    }
    atomic_json(args.output.resolve(), value)
    print(json.dumps({
        "checkpoint_name": spec.name,
        "fingerprint_sha256": fingerprint,
        "file_count": len(entries),
        "total_bytes": value["total_bytes"],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

