#!/usr/bin/env python3
"""Download or verify the frozen KV32/KV128 cycle-simulation Release asset."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/evidence/kv32_kv128_cycle_sim/release_asset.json"
BLOCK = 1 << 20


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BLOCK), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, output: Path, expected_bytes: int, expected_sha: str) -> None:
    if output.exists():
        raise ValueError(f"Destination already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    if temporary.exists():
        raise ValueError(f"Existing partial download needs review: {temporary}")
    try:
        request = Request(url, headers={"User-Agent": "ScaleLLM-evidence-verifier/1"})
        with urlopen(request, timeout=60) as response, temporary.open("xb") as stream:
            while chunk := response.read(BLOCK):
                stream.write(chunk)
        if temporary.stat().st_size != expected_bytes or sha(temporary) != expected_sha:
            raise ValueError("Downloaded bytes differ from the frozen asset identity")
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def check_zip(path: Path, *, full: bool) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member names")
        for name in names:
            part = PurePosixPath(name)
            if part.is_absolute() or ".." in part.parts or "\\" in name:
                raise ValueError(f"Unsafe ZIP member: {name}")
        required = {"BUNDLE_MANIFEST.json", "BUNDLE_FAILURE_INDEX.json", "READ_ME.txt",
                    "0_Source/operator_timing_kv32/kv128_compare/results/publication_final_001/coverage_closure.json",
                    "0_Source/operator_timing_kv32/kv128_compare/REPORT.md"}
        if not required.issubset(names):
            raise ValueError("Required evidence member missing")
        catalog = json.loads(archive.read("BUNDLE_MANIFEST.json"))
        if catalog.get("schema") != "scalellm_kv_comparison_portable_bundle_v1" or catalog.get("mode") != "FINAL":
            raise ValueError("Not the frozen final evidence bundle")
        listed = {item["archive_path"]: item for item in catalog["files"]}
        if set(names) != set(listed) | {"BUNDLE_MANIFEST.json", "BUNDLE_FAILURE_INDEX.json", "READ_ME.txt"}:
            raise ValueError("ZIP members differ from bundle inventory")
        if len(catalog["selected_analyses"]) != 12:
            raise ValueError("Selected command count differs")
        closure = json.loads(archive.read(
            "0_Source/operator_timing_kv32/kv128_compare/results/publication_final_001/coverage_closure.json"))
        if closure.get("status") != "PASS" or closure.get("selected_command_count") != 12 or closure.get("validated_stage_rows") != 52:
            raise ValueError("Coverage closure differs")
        if full:
            for name, item in listed.items():
                info = archive.getinfo(name)
                if info.file_size != item["bytes"]:
                    raise ValueError(f"ZIP member size differs: {name}")
                h = hashlib.sha256()
                with archive.open(info) as stream:
                    while chunk := stream.read(BLOCK):
                        h.update(chunk)
                if h.hexdigest() != item["sha256"]:
                    raise ValueError(f"ZIP member hash differs: {name}")
    return {"archive_files": len(listed), "selected_commands": 12,
            "valid_stage_rows": 52,
            "zip_member_sha256_and_crc": "PASS" if full else "NOT_RUN"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--asset", type=Path, help="Already downloaded ZIP")
    choice.add_argument("--url", help="GitHub Release ZIP asset URL")
    parser.add_argument("--output", type=Path, help="Destination for --url")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                        help="Small public release_asset.json")
    parser.add_argument("--full", action="store_true",
                        help="Also stream-hash every archived member and check its CRC")
    args = parser.parse_args()
    if bool(args.url) != bool(args.output):
        parser.error("--url and --output must be used together")
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("schema") != "scalellm_cycle_public_release_asset_v1":
        raise ValueError("Unknown release asset manifest")
    path = args.asset if args.asset is not None else args.output
    assert path is not None
    if args.url:
        download(args.url, path, manifest["bytes"], manifest["sha256"])
    actual_size, actual_sha = path.stat().st_size, sha(path)
    if actual_size != manifest["bytes"] or actual_sha != manifest["sha256"]:
        raise ValueError("Release ZIP size or SHA-256 differs from frozen manifest")
    result = check_zip(path, full=args.full)
    result.update(status="PASS", asset_name=manifest["asset_name"],
                  bytes=actual_size, sha256=actual_sha)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
