"""Bounded CPU replay with immutable start manifest and retained failure evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identity(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def memory_available_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def source_identities() -> list[dict]:
    experiment = Path(__file__).resolve().parent
    project_root = experiment.parents[4]
    files = sorted(experiment.glob("*.py"))
    for rel in ["project/software/0_Software/FPtoQ/experiment/v5_fullchain.py",
                "project/software/model/export_scalellm_llama31_artifacts.py",
                "project/software/model/fixbit_v2.py",
                "project/software/model/mlp_fixed.py",
                "project/E012_multistage_rounding_precision/experiment_source/protocol.md"]:
        path = project_root / rel
        if path.is_file():
            files.append(path)
    files += sorted((experiment.parent / "tests").glob("test_*.py"))
    for name in ["design.md", "input_schema.json"]:
        path = experiment.parent / "source" / name
        if path.is_file():
            files.append(path)
    return [identity(path) for path in files]


def load_rows(path: Path, max_samples: int = 10000, max_bytes: int = 64 << 20) -> list[dict]:
    if path.stat().st_size > max_bytes:
        raise ValueError("input exceeds byte bound")
    rows = []
    ids = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line {line_number}")
            def reject_constant(value):
                raise ValueError(f"nonfinite JSON constant {value} at line {line_number}")
            row = json.loads(line, parse_constant=reject_constant)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL line {line_number} is not an object")
            sample_id = row.get("sample_id")
            if not isinstance(sample_id, str) or not sample_id:
                raise ValueError(f"missing string sample_id at line {line_number}")
            if sample_id in ids:
                raise ValueError(f"duplicate sample_id at line {line_number}: {sample_id}")
            ids.add(sample_id)
            rows.append(row)
            if len(rows) > max_samples:
                raise ValueError("input exceeds sample bound")
    if not rows:
        raise ValueError("empty input")
    return rows


def validate_source_files(row: dict, input_parent: Path, cache: dict) -> dict:
    """Verify declared small artifacts without ever hashing whole weight shards."""
    provenance = row.get("provenance", {})
    if not isinstance(provenance, dict) or provenance.get("kind") != "real_trace":
        return {"required": False, "verified": False, "reason": "not_real_trace", "files": []}
    files = provenance.get("source_files")
    if not isinstance(files, list) or not files:
        return {"required": True, "verified": False, "reason": "source_files_missing", "files": []}
    checks = []
    for declaration in files:
        if not isinstance(declaration, dict) or not isinstance(declaration.get("path"), str):
            checks.append({"verified": False, "reason": "invalid_source_declaration"})
            continue
        path = Path(declaration["path"])
        path = (path if path.is_absolute() else input_parent / path).resolve()
        expected = declaration.get("sha256")
        key = str(path)
        if key not in cache:
            if len(cache) >= 128:
                checks.append({"path": key, "verified": False, "reason": "source_file_count_bound"})
                continue
            elif not path.is_file():
                cache[key] = {"path": key, "verified": False, "reason": "source_file_missing"}
            elif path.stat().st_size > 64 << 20:
                cache[key] = {"path": key, "verified": False, "reason": "source_file_size_bound; supply frozen consumed slices"}
            elif sum(item.get("bytes", 0) for item in cache.values()) + path.stat().st_size > 256 << 20:
                cache[key] = {"path": key, "verified": False, "reason": "source_total_bytes_bound"}
            else:
                cache[key] = {**identity(path), "verified": True}
        actual = cache[key]
        check = {**actual, "expected_sha256": expected,
                 "verified": actual.get("verified", False) and isinstance(expected, str)
                             and actual.get("sha256") == expected.lower()}
        if actual.get("verified") and not check["verified"]:
            check["reason"] = "source_sha256_mismatch"
        checks.append(check)
    return {"required": True, "verified": all(check["verified"] for check in checks), "files": checks}


def worker(args: argparse.Namespace) -> int:
    byte_limit = args.memory_gib * (1 << 30)
    resource.setrlimit(resource.RLIMIT_AS, (byte_limit, byte_limit))
    resource.setrlimit(resource.RLIMIT_CPU, (args.wall_seconds, args.wall_seconds + 1))
    from linear_recovery import evaluate_linear_sample
    from metrics import summarize_results
    rows = load_rows(args.input, args.max_samples)
    results = []
    source_cache = {}
    start = time.monotonic()
    with (args.attempt_dir / "results.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            result = evaluate_linear_sample(row)
            validation = validate_source_files(row, args.input.parent, source_cache)
            result["source_file_validation"] = validation
            result["source_identity_status"] = ("verified" if validation["verified"] else
                                                "failed" if validation["required"] else "not_required")
            if validation["verified"] and isinstance(result.get("provenance_reasons"), list):
                result["provenance_reasons"] = [reason for reason in result["provenance_reasons"]
                                                if reason != "source_identity_not_verified"]
            if validation["required"] and not validation["verified"]:
                result["eligible_current_format_evidence"] = False
                result["source_qualification"] = "real_source_identity_not_verified"
                result["provenance_status"] = "real_source_identity_not_verified"
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            results.append(result)
    summary = summarize_results(results)
    summary["execution"] = {"input_samples": len(rows), "result_samples": len(results),
                            "wall_seconds": time.monotonic() - start,
                            "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            "input_kinds": {kind: sum(row.get("provenance", {}).get("kind") == kind for row in rows)
                                            for kind in sorted({str(row.get("provenance", {}).get("kind")) for row in rows})},
                            "full_model_evaluated": False, "ppl_evaluated": False, "acc_evaluated": False}
    write_new(args.attempt_dir / "summary.json", summary)
    write_new(args.attempt_dir / "source_file_validation.json", {"files": list(source_cache.values()),
              "max_unique_files": 128, "max_file_bytes": 64 << 20, "max_total_bytes": 256 << 20})
    print(json.dumps({"completed": len(results), "summary": str(args.attempt_dir / "summary.json")}, ensure_ascii=False))
    return 0


def run(args: argparse.Namespace) -> int:
    if not 1 <= args.threads <= 2:
        raise ValueError("threads must be 1..2")
    if not 1 <= args.wall_seconds <= 1200:
        raise ValueError("wall-seconds must be 1..1200")
    if not 1 <= args.memory_gib <= 8:
        raise ValueError("memory-gib must be 1..8")
    args.input = args.input.resolve()
    if args.input.stat().st_size > 64 << 20:
        raise ValueError("input exceeds 64 MiB bound; not hashing or launching")
    args.attempt_dir = args.attempt_dir.resolve()
    args.attempt_dir.mkdir(parents=True, exist_ok=True)
    for name in ["manifest.json", "execution_receipt.json", "stdout.log", "stderr.log", "results.jsonl", "summary.json", "source_file_validation.json"]:
        if (args.attempt_dir / name).exists():
            raise FileExistsError(f"refusing to overwrite prior evidence: {name}")
    available = memory_available_bytes()
    sources = source_identities()
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", "--input", str(args.input),
               "--attempt-dir", str(args.attempt_dir), "--wall-seconds", str(args.wall_seconds),
               "--memory-gib", str(args.memory_gib), "--max-samples", str(args.max_samples),
               "--threads", str(args.threads)]
    env = os.environ.copy()
    for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"]:
        env[key] = str(args.threads)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = {"schema": "m005_cpu_attempt_manifest_v1", "started_at": utc_now(),
                "execution_state": "starting", "parent_command": [sys.executable] + sys.argv,
                "worker_command": command, "cwd": str(Path.cwd()), "input": identity(args.input),
                "code": sources, "environment": {"hostname": platform.node(), "python": sys.version,
                    "executable": sys.executable, "platform": platform.platform(),
                    "thread_limits": {key: env[key] for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]}},
                "resources": {"threads": args.threads, "memory_gib": args.memory_gib,
                              "wall_seconds": args.wall_seconds, "memory_available_bytes": available,
                              "minimum_available_bytes": 32 * (1 << 30)},
                "scope": "local exact integer Linear recovery; no model inference or hardware execution"}
    write_new(args.attempt_dir / "manifest.json", manifest)
    if available is None or available < 32 * (1 << 30):
        write_new(args.attempt_dir / "execution_receipt.json", {"execution_state": "blocked", "exit_code": 75,
                  "started_at": manifest["started_at"], "ended_at": utc_now(),
                  "stop_reason": "available memory unknown or below 32 GiB; worker not launched"})
        return 75
    start = time.monotonic()
    stop_reason = None
    with (args.attempt_dir / "stdout.log").open("x") as stdout, (args.attempt_dir / "stderr.log").open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
        write_new(args.attempt_dir / "launch.json", {"worker_pid": process.pid, "launched_at": utc_now(), "command": command})
        try:
            exit_code = process.wait(timeout=args.wall_seconds)
        except subprocess.TimeoutExpired:
            stop_reason = "assigned CPU attempt wall-time budget"
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            exit_code = 124
    current_sources = source_identities()
    source_unchanged = sources == current_sources
    input_unchanged = manifest["input"] == identity(args.input)
    if exit_code == 0 and (not source_unchanged or not input_unchanged):
        exit_code = 76
        stop_reason = "consumed code or input changed during execution; result not frozen"
    write_new(args.attempt_dir / "execution_receipt.json", {"schema": "m005_cpu_execution_receipt_v1",
        "execution_state": "completed" if exit_code == 0 else "failed", "started_at": manifest["started_at"],
        "ended_at": utc_now(), "wall_seconds": time.monotonic() - start, "exit_code": exit_code,
        "worker_returncode": process.returncode, "stop_reason": stop_reason,
        "source_unchanged": source_unchanged, "input_unchanged": input_unchanged,
        "worker_pid": process.pid, "worker_reaped": True})
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attempt-dir", required=True, type=Path)
    parser.add_argument("--threads", default=2, type=int)
    parser.add_argument("--memory-gib", default=8, type=int)
    parser.add_argument("--wall-seconds", default=240, type=int)
    parser.add_argument("--max-samples", default=10000, type=int)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        code = worker(args) if args.worker else run(args)
    except Exception:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
