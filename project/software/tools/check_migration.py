#!/usr/bin/env python3
"""Hash provenance and parse code without importing or running experiment code."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "file_mapping.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_pairs(plan):
    pairs = []
    for directory, names in plan["same_path_groups"].items():
        pairs.extend((f"{directory}/{name}", f"{directory}/{name}") for name in names)
    pairs.extend(plan["remapped_files"].items())
    return sorted(pairs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Record destination hashes; never change the recorded source baseline")
    args = parser.parse_args()
    plan = json.loads((ROOT / "COPY_PLAN.json").read_text())
    source_root = Path(plan["source_root"])
    baseline = json.loads(MAP.read_text()) if MAP.exists() else {"files": []}
    old = {entry["destination"]: entry for entry in baseline["files"]}
    entries = []
    errors = []
    modified = []
    for source, destination in copy_pairs(plan):
        src, dst = source_root / source, ROOT / destination
        if not src.is_file() or not dst.is_file() or dst.is_symlink():
            errors.append(f"missing file or destination symlink: {destination}")
            continue
        source_hash, destination_hash = sha256(src), sha256(dst)
        expected = old.get(destination, {}).get("source_sha256", source_hash)
        if source_hash != expected:
            errors.append(f"source changed since initial snapshot: {source}")
        changed = source_hash != destination_hash
        if changed:
            modified.append(destination)
            if destination not in plan["path_adaptations"]:
                errors.append(f"unexpected modification: {destination}")
        if old and not args.refresh and destination_hash != old[destination]["destination_sha256"]:
            errors.append(f"destination checksum mismatch: {destination}")
        entries.append({
            "source": str(src), "destination": destination,
            "source_sha256": expected, "destination_sha256": destination_hash,
            "modified": changed, "source_bytes": src.stat().st_size,
            "destination_bytes": dst.stat().st_size,
        })
    trees = {}
    for path in sorted(ROOT.rglob("*.py")):
        relative = str(path.relative_to(ROOT))
        try:
            tree = ast.parse(path.read_text(), filename=relative)
            compile(tree, relative, "exec")
            trees[path] = tree
        except (SyntaxError, ValueError) as exc:
            errors.append(f"syntax: {relative}: {exc}")
    local_modules = {path.stem for path in trees} | {"model"}
    external = set()
    local_imports = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
                if names[0] == "model" and len(node.module.split(".")) > 1:
                    module = ROOT.joinpath(*node.module.split(".")).with_suffix(".py")
                    if not module.is_file():
                        errors.append(f"missing local model module: {node.module}")
            else:
                continue
            for name in names:
                if name in local_modules:
                    local_imports.add(name)
                elif name not in sys.stdlib_module_names:
                    external.add(name)
    for path in ROOT.rglob("*.json"):
        if path.name not in {"file_mapping.json", "static_check.json"}:
            try:
                json.loads(path.read_text())
            except (ValueError, UnicodeError) as exc:
                errors.append(f"JSON: {path.relative_to(ROOT)}: {exc}")
    local_path_checks = {}
    for relative in (
        "0_Software/FPtoQ/experiment/v5_fullchain.py",
        "0_Software/FPtoQ/experiment/torch_frontend.py",
        "0_Software/FPtoQ/experiment/run_experiment.py",
        "0_Software/experiment/scripts/accuracy_MLP_4bit/mlp4_method_inference.py",
        "0_Software/experiment/scripts/scale_code_linear/scalepath4_method_inference.py",
        "model/export_scalellm_llama31_artifacts.py", "model/fixbit_v2.py", "model/mlp_fixed.py",
    ):
        local_path_checks[relative] = (ROOT / relative).is_file()
        if not local_path_checks[relative]:
            errors.append(f"missing local dependency path: {relative}")
    for path, tree in trees.items():
        if path.name in {"run_six_model_eval.py", "run_extended_ppl_eval.py"}:
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(".py"):
                    dependency = path.parent / node.value
                    local_path_checks[str(dependency.relative_to(ROOT))] = dependency.is_file()
                    if not dependency.is_file():
                        errors.append(f"missing runner script: {node.value}")
    data_identity = json.loads((ROOT / "evidence/literature_2048/data_manifest.json").read_text())
    external_paths = [Path(row["path"]) for row in data_identity["datasets"]]
    external_root = Path(data_identity["data_root"]).parent
    external_paths.append(external_root / "data/bape_eval/manifest.json")
    matrix = trees[ROOT / "0_Software/fix_experiment/exp/six_model_matrix.py"]
    for node in ast.walk(matrix):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ModelSpec":
            external_paths.append(external_root / "configs/models" / ast.literal_eval(node.args[1]) / "config.json")
    external_paths.append(Path("/home/user/anaconda3/envs/zhouwenjun/bin/python"))
    # Check that path-only edits leave numerical functions/classes unchanged.
    for entry in entries:
        relative = entry["destination"]
        if not entry["modified"] or not relative.endswith(".py"):
            continue
        original = ast.parse(Path(entry["source"]).read_text())
        migrated = trees[ROOT / relative]
        original_defs = {node.name: ast.dump(node) for node in original.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        migrated_defs = {node.name: ast.dump(node) for node in migrated.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        allowed = {"code_identity"} if relative.endswith("summarize_six_models.py") else {"validate_asset"} if relative.endswith("run_extended_ppl_worker.py") else set()
        for name in original_defs.keys() | migrated_defs.keys():
            if name not in allowed and original_defs.get(name) != migrated_defs.get(name):
                errors.append(f"non-path definition changed: {relative}:{name}")
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "SHA256, Python parse/compile, local import inventory, JSON parse, path-only definition comparison; no application imports or experiments",
        "status": "pass" if not errors else "fail", "errors": errors,
        "copied_files": len(entries),
        "copied_source_bytes": sum(entry["source_bytes"] for entry in entries),
        "copied_destination_bytes": sum(entry["destination_bytes"] for entry in entries),
        "byte_identical_files": len(entries) - len(modified),
        "modified_files": modified, "python_files_parsed": len(trees),
        "local_import_roots": sorted(local_imports), "external_import_roots": sorted(external),
        "local_path_checks": local_path_checks,
        "external_default_path_checks": {str(path): path.exists() for path in external_paths},
        "limitations": ["Dynamic imports, GPU kernels and numerical tests not executed", "External model/data contents not rehashed", "Historical result identity is not the migrated-code identity"]
    }
    if args.refresh and not errors:
        generated = []
        copied = {entry["destination"] for entry in entries}
        for path in sorted(ROOT.rglob("*")):
            relative = str(path.relative_to(ROOT))
            if path.is_file() and relative not in copied and relative not in {"file_mapping.json", "static_check.json"}:
                generated.append({"source": None, "destination": relative, "source_sha256": None, "destination_sha256": sha256(path), "modified": True, "destination_bytes": path.stat().st_size})
        MAP.write_text(json.dumps({"schema": "scalellm_software_migration_v1", "source_root": str(source_root), "destination_root": str(ROOT), "files": entries, "generated_files": generated, "self_exclusions": ["file_mapping.json", "static_check.json"]}, indent=2) + "\n")
    (ROOT / "static_check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
