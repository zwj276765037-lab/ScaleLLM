#!/usr/bin/env python3
"""Build and verify a portable, explicitly selected ScaleLLM release.

No git history, research-management directories, model weights, credentials,
or generated Vivado projects are traversed by the package selector.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BIT_NAME = "ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit"
BIT_SOURCE = "project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/" + BIT_NAME
BIT_SHA256 = "66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47"
BIT_SIZE = 80159259
DISALLOWED_SUFFIXES = {".pem", ".key", ".pfx", ".p12", ".cer", ".crt", ".sys", ".cat",
                       ".safetensors", ".npy", ".npz", ".pt", ".pth", ".f32", ".dcp"}
DISALLOWED_PARTS = {".git", "__pycache__", ".pytest_cache", ".Xil", ".cache", "node_modules"}
SECRET_PATTERNS = [re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
                   re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
                   re.compile(rb"\bhf_[A-Za-z0-9]{30,}\b")]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_relative(value: str) -> str:
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts or "\\" in value or not value or value == ".":
        raise ValueError(f"Unsafe release path: {value}")
    return p.as_posix()


def selected_files(config: dict) -> dict[str, Path]:
    chosen: dict[str, Path] = {}

    def add(source: Path, target: str) -> None:
        target = safe_relative(target)
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing, symlinked, or external source: {source}")
        if any(part in DISALLOWED_PARTS for part in source.parts) or source.suffix.lower() in DISALLOWED_SUFFIXES:
            raise ValueError(f"Excluded data type selected: {source}")
        if source.name.startswith(".env"):
            raise ValueError(f"Environment file selected: {source}")
        if target in chosen and chosen[target] != source:
            raise ValueError(f"Duplicate release target: {target}")
        chosen[target] = source

    for entry in config["files"]:
        source_name = safe_relative(entry["source"])
        add(ROOT / source_name, entry.get("target", source_name))
    for entry in config.get("trees", []):
        source_name = safe_relative(entry["source"])
        base = ROOT / source_name
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"Missing release source tree: {base}")
        suffixes = set(entry["suffixes"])
        for source in sorted(base.rglob("*")):
            rel = source.relative_to(base)
            if any(part in DISALLOWED_PARTS for part in rel.parts):
                continue
            if source.is_file() and source.suffix in suffixes:
                add(source, str(PurePosixPath(entry.get("target", source_name)) / rel.as_posix()))
    for target, source_name in config.get("overrides", {}).items():
        target = safe_relative(target)
        if target not in chosen:
            raise ValueError(f"Override is not an existing selected path: {target}")
        del chosen[target]
        add(ROOT / safe_relative(source_name), target)
    # The public build/runtime must carry every frozen input, even when a new
    # extension is added to the vendor snapshot.
    vendor_manifest = chosen.get("deploy/vendor_manifest.json")
    if vendor_manifest is None:
        raise ValueError("Release must include the deployment vendor manifest")
    for relative, entry in json.loads(vendor_manifest.read_text())["files"].items():
        target = "deploy/" + safe_relative(relative)
        source = chosen.get(target)
        if source is None:
            raise ValueError(f"Required deployment dependency omitted: {target}")
        if source.stat().st_size != entry["bytes"] or sha256(source) != entry["sha256"]:
            raise ValueError(f"Frozen deployment dependency mismatch: {target}")
    if chosen.get("bitstream/" + BIT_NAME) != ROOT / BIT_SOURCE:
        raise ValueError("Release must include the exact board-tested bitstream")
    bit = ROOT / BIT_SOURCE
    if bit.stat().st_size != BIT_SIZE or sha256(bit) != BIT_SHA256:
        raise ValueError("Board-tested bitstream identity mismatch")
    return chosen


def verify(directory: Path) -> dict:
    manifest = json.loads((directory / "RELEASE_MANIFEST.json").read_text())
    if manifest["project"] != "ScaleLLM_VCU118_GU_only":
        raise ValueError("Not a ScaleLLM release")
    expected = set()
    for entry in manifest["files"]:
        name = safe_relative(entry["path"])
        if name in expected:
            raise ValueError(f"Duplicate manifest entry: {name}")
        expected.add(name)
        path = directory / name
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f"Unsafe installed file: {name}")
        if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"Release verification failed: {name}")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()
              and not any(x in DISALLOWED_PARTS for x in p.relative_to(directory).parts)}
    extra = actual - expected - {"RELEASE_MANIFEST.json"}
    if extra:
        raise ValueError(f"Unlisted files in release: {sorted(extra)[:10]}")
    bit = directory / "bitstream" / BIT_NAME
    if bit.stat().st_size != BIT_SIZE or sha256(bit) != BIT_SHA256:
        raise ValueError("Released bitstream differs from the board-tested identity")
    return {"status": "PASS", "file_count": len(expected), "bytes": sum(p["bytes"] for p in manifest["files"]),
            "bitstream_sha256": BIT_SHA256}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "deploy/release_files.json")
    ap.add_argument("--output", type=Path, default=ROOT / "dist/ScaleLLM_VCU118")
    ap.add_argument("--verify", type=Path, help="Only verify an extracted package")
    ap.add_argument("--replace", action="store_true", help="Replace a previously generated release directory")
    args = ap.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify.resolve()), indent=2))
        return 0
    config = json.loads(args.config.read_text())
    selected = selected_files(config)
    output = args.output.resolve()
    if output == ROOT or output in ROOT.parents:
        raise ValueError("Output cannot be the source workspace or an ancestor")
    if any(source.is_relative_to(output) for source in selected.values()):
        raise ValueError("Output overlaps release input sources")
    if output.exists():
        if not args.replace:
            raise ValueError("Output exists; --replace is required for a previous release")
        old = json.loads((output / "RELEASE_MANIFEST.json").read_text())
        if old.get("project") != "ScaleLLM_VCU118_GU_only":
            raise ValueError("Refusing to replace a directory not created by this tool")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    files = []
    for name, source in sorted(selected.items()):
        if source.suffix not in {".bit", ".png", ".pdf"}:
            content = source.read_bytes()
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                raise ValueError(f"Potential credential detected in {source.relative_to(ROOT)}")
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        dest.chmod(0o644)
        files.append({"path": name, "bytes": dest.stat().st_size, "sha256": sha256(dest),
                      "source": str(source.relative_to(ROOT))})
    manifest = {"schema": 1, "project": "ScaleLLM_VCU118_GU_only", "release_date": "2026-10-25",
                "status": "ENGINEERING_VALIDATION_WITH_DOCUMENTED_LIMITS", "files": files,
                "excluded": ["model weights and exports", "machine credentials/signatures", "AMD tools",
                             "generated Vivado caches", "local Git and research-management history"],
                "bitstream_sha256": BIT_SHA256}
    (output / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validation = verify(output)
    archive = output.with_suffix(".tar.gz")
    with archive.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in sorted(p for p in output.rglob("*") if p.is_file()):
                info = tar.gettarinfo(str(path), arcname=str(Path(output.name) / path.relative_to(output)))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.mode = 0o644
                with path.open("rb") as f:
                    tar.addfile(info, f)
    digest = sha256(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n")
    receipt = {"created_utc": datetime.now(timezone.utc).isoformat(), "archive": archive.name,
               "archive_sha256": digest, "archive_bytes": archive.stat().st_size, **validation}
    archive.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
