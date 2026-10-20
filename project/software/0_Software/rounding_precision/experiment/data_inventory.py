"""Bounded, read-only input inventory. It never loads model weights or pickle."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import struct
import zipfile

SCHEMA = "m005_bounded_data_inventory_v1"


def sha256_file(path: Path, max_bytes: int = 16 << 20) -> str | None:
    if path.stat().st_size > max_bytes:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_identity(path: Path, max_hash_bytes: int = 16 << 20) -> dict:
    path = path.resolve()
    stat = path.stat()
    digest = sha256_file(path, max_hash_bytes)
    return {"path": str(path), "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "sha256": digest,
            "hash_status": "hashed" if digest else "omitted_size_bound"}


def npz_headers(path: Path, max_members: int = 32, max_header_bytes: int = 65536) -> list[dict]:
    result = []
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > max_members:
            raise ValueError("archive member count exceeds inventory bound")
        for member in members:
            if not member.filename.endswith(".npy"):
                raise ValueError("non-NPY archive member")
            with archive.open(member) as stream:
                magic = stream.read(8)
                if magic[:6] != b"\x93NUMPY" or magic[6] not in (1, 2, 3):
                    raise ValueError("unsupported NumPy header")
                width = 2 if magic[6] == 1 else 4
                count_bytes = stream.read(width)
                if len(count_bytes) != width:
                    raise ValueError("truncated NumPy header length")
                count = int.from_bytes(count_bytes, "little")
                if count > max_header_bytes:
                    raise ValueError("NumPy header exceeds inventory bound")
                raw = stream.read(count)
                if len(raw) != count:
                    raise ValueError("truncated NumPy header")
                header = ast.literal_eval(raw.decode("utf-8" if magic[6] == 3 else "latin1"))
            result.append({"name": member.filename.removesuffix(".npy"),
                           "dtype": header["descr"], "shape": list(header["shape"]),
                           "fortran_order": header["fortran_order"],
                           "uncompressed_bytes": member.file_size})
    return result


def bounded_listing(root: Path, max_depth: int = 2, max_files: int = 100) -> dict:
    entries = []
    truncated = False
    if not root.is_dir():
        return {"path": str(root), "exists": False, "entries": []}
    for here, dirs, files in os.walk(root, followlinks=False):
        depth = len(Path(here).relative_to(root).parts)
        dirs[:] = sorted(d for d in dirs if not (Path(here) / d).is_symlink())
        if depth >= max_depth:
            dirs[:] = []
        for name in sorted(files):
            path = Path(here) / name
            if path.is_symlink():
                continue
            if len(entries) >= max_files:
                truncated = True
                break
            stat = path.stat()
            entries.append({"relative_path": str(path.relative_to(root)), "bytes": stat.st_size})
        if truncated:
            break
    return {"path": str(root.resolve()), "exists": True, "max_depth": max_depth,
            "max_files": max_files, "truncated": truncated, "entries": entries}


def build_inventory(project_root: Path, legacy_root: Path) -> dict:
    trace_root = legacy_root / "0_Software/FPtoQ/results/llama3.1-8b-instruct"
    archive = trace_root / "activation_groups.npz"
    metadata_path = trace_root / "activation_groups.json"
    result = {"schema": SCHEMA, "scope": "explicit paths only; no model weight reads",
              "legacy_results": bounded_listing(trace_root, 2, 100),
              "current_evidence": bounded_listing(project_root / "project/software/evidence", 2, 100)}
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    result["trace_metadata"] = metadata
    if archive.exists():
        result["trace_archive"] = file_identity(archive)
        result["trace_archive"]["arrays"] = npz_headers(archive)
    result["metadata_identity"] = file_identity(metadata_path) if metadata_path.exists() else None
    collector = legacy_root / "0_Software/FPtoQ/experiment/capture_model_activations.py"
    result["collector_identity"] = file_identity(collector) if collector.exists() else None
    model_path = Path(metadata["model"]) if metadata.get("model") else None
    if model_path and model_path.is_dir():
        # Only top-level file metadata; in particular safetensors are never hashed.
        result["checkpoint"] = {"path": str(model_path), "exists": True, "files": [
            {"name": p.name, "bytes": p.stat().st_size,
             "sha256": sha256_file(p, 1 << 20) if p.suffix == ".json" else None}
            for p in sorted(model_path.iterdir()) if p.is_file()][:32],
            "weight_content_identity": "not_verified; metadata_only"}
    else:
        result["checkpoint"] = {"path": str(model_path), "exists": False}
    calibration = Path(metadata["calibration_jsonl"]) if metadata.get("calibration_jsonl") else None
    result["calibration"] = (file_identity(calibration) if calibration and calibration.is_file()
                             else {"path": str(calibration), "exists": False})
    names = {a["name"] for a in result.get("trace_archive", {}).get("arrays", [])}
    float_only = names == {"groups", "labels"}
    result["replay_qualification"] = {
        "existing_same_code_linear_replay": False,
        "float_activation_archive_available": float_only,
        "classification": "real_float_frontend_groups_only" if float_only else "requires_schema_review",
        "missing_fields": ["per-group layer/token/input-group ordering", "activation integer codes and zero point",
                           "weight integer codes", "activation and weight ScaleCode code/shift", "per-group dot products"],
        "reason": "Float Group32 blocks and op labels cannot establish the shared integer operands of a Linear output.",
        "metadata_claims_are_not_row_provenance": True,
        "historical_summaries_are_inputs": False}
    result["next_collection"] = {
        "proposal_only": True, "gpu_started": False,
        "initial_scope": "Llama-3.1-8B-Instruct, 1 fixed prompt <=32 tokens; layers 0/15/31; selected attention/gate/up/down outputs",
        "required": ["freeze format05 and quantized weight artifacts once", "save same q_a/zp_a/q_w and code/shift for both branches",
                     "preserve all 128 or 448 input groups for each selected output", "record real model/layer/token/output IDs",
                     "independently recompute dot from saved integer operands", "hash only actually consumed input slices"],
        "resource_decision": "Root must first qualify GPU0 identity/occupancy/budget/pilot; GPU1 excluded"}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_inventory(args.project_root, args.legacy_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "qualification": result["replay_qualification"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
