#!/usr/bin/env python3
"""Verify a power evidence ZIP and optionally extract its checked members.

Only Python's standard library is required. This does not execute archived code.
The archive SHA-256 must also be checked against the separately published index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

PREFIX = "resource_optimization_power/"
MANIFEST = PREFIX + "MANIFEST.json"


def relative(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or value == "." or path.is_absolute() or ".." in path.parts
            or "\\" in value or ":" in value or path.as_posix() != value):
        raise ValueError(f"Unsafe member path: {value}")
    return value


def verify(archive: Path, extract: Path | None) -> dict:
    if extract is not None:
        # Resolve the parent only, so an existing destination symlink is rejected.
        extract = extract.parent.resolve() / extract.name
        if extract.exists() or extract.is_symlink():
            raise ValueError("Extraction destination must be a new directory")
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        names = [entry.filename for entry in infos]
        if len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError("Duplicate members or missing manifest")
        for entry in infos:
            relative(entry.filename)
            mode = entry.external_attr >> 16
            if (not entry.filename.startswith(PREFIX) or entry.is_dir()
                    or stat.S_ISLNK(mode) or entry.flag_bits & 1):
                raise ValueError(f"Unsupported member: {entry.filename}")
        if bundle.getinfo(MANIFEST).file_size > 4 * 1024**2:
            raise ValueError("Manifest exceeds size limit")
        manifest_bytes = bundle.read(MANIFEST)
        manifest = json.loads(manifest_bytes)
        if manifest.get("schema") != "scalellm_power_evidence_bundle_v1":
            raise ValueError("Not a ScaleLLM power evidence bundle")
        expected = {}
        for entry in manifest["files"]:
            name = PREFIX + relative(entry["path"])
            if name in expected or name == MANIFEST:
                raise ValueError("Duplicate or self-referential manifest entry")
            if not isinstance(entry["bytes"], int) or entry["bytes"] < 0:
                raise ValueError("Invalid file size")
            expected[name] = entry
        if set(names) != set(expected) | {MANIFEST}:
            raise ValueError("Archive membership differs from manifest")
        for name, entry in expected.items():
            if bundle.getinfo(name).file_size != entry["bytes"]:
                raise ValueError(f"Size mismatch: {name}")
        # Validate every byte before creating the extraction destination.
        for name, entry in expected.items():
            with bundle.open(name) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {name}")
        if extract is not None:
            extract.mkdir(parents=True, exist_ok=False)
            for name in names:
                target = extract / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(name) as source, target.open("xb") as output:
                    while chunk := source.read(4 * 1024**2):
                        output.write(chunk)
        with archive.open("rb") as stream:
            archive_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        return {"status": "PASS", "archive_sha256": archive_sha,
                "archive_bytes": archive.stat().st_size,
                "payload_files": len(expected), "payload_bytes": sum(e["bytes"] for e in expected.values()),
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "extracted_to": str(extract) if extract is not None else None,
                "code_executed_from_archive": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--extract", type=Path, help="New destination; existing paths are never overwritten")
    parser.add_argument("--output", type=Path, help="Optional new JSON receipt")
    args = parser.parse_args()
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        raise ValueError("Output receipt must be a new file")
    result = verify(args.archive, args.extract)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x") as output:
            output.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
