#!/usr/bin/env python3
"""Resumable two-GPU runner for the frozen six-model ACC/PPL matrix."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any

from six_model_matrix import FIVE_CONFIG_CASES, MODEL_SPECS, ModelSpec
from protocol import MODEL_ROOT


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_ROOT = MODEL_ROOT
DEFAULT_OUTPUT = THIS_DIR.parent / "results" / "six_model_algorithm_literature_2048"
ALL_TASKS = "wikitext2,piqa,arc_easy,arc_challenge,boolq,hellaswag,winogrande"
CASES = FIVE_CONFIG_CASES
PRINT_LOCK = threading.Lock()


@dataclass(frozen=True)
class Job:
    spec: ModelSpec
    case: str
    limit: int
    output_root: Path

    @property
    def phase_dir(self) -> Path:
        return self.output_root / self.spec.name / f"{self.case}_literature_2048"

    @property
    def label(self) -> str:
        stage = "full" if self.limit == 0 else f"smoke{self.limit}"
        return f"{stage}/{self.spec.name}/{self.case}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("all", "smoke", "full"), default="all")
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--python", default="/home/user/anaconda3/envs/zhouwenjun/bin/python")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--ppl-batch-size", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument("--offline-data", action="store_true")
    return parser.parse_args()


def announce(message: str) -> None:
    with PRINT_LOCK:
        print(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {message}", flush=True)


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_state(root: Path, value: dict[str, Any]) -> None:
    path = root / "runner_state.json"
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def run_checked(command: list[str], *, stdout: Any = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, stdout=stdout, stderr=subprocess.STDOUT, env=env)


def check_gpu_count() -> None:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    )
    if len([line for line in result.stdout.splitlines() if line.strip()]) < 2:
        raise RuntimeError("the six-model plan requires two CUDA GPUs")


def prepare_identities(args: argparse.Namespace) -> dict[str, Path]:
    identity_dir = args.output / "model_identities"
    identity_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for spec in MODEL_SPECS:
        model = args.model_root / spec.directory
        output = identity_dir / f"{spec.name}.json"
        announce(f"fingerprinting checkpoint {spec.name}")
        run_checked([
            args.python,
            str(THIS_DIR / "prepare_model_identity.py"),
            "--model", str(model),
            "--output", str(output),
        ])
        result[spec.name] = output
    return result


def prepare_boundary_audits(
    args: argparse.Namespace, identities: dict[str, Path]
) -> None:
    audit_dir = args.output / "tokenizer_boundary_audits"
    audit_dir.mkdir(parents=True, exist_ok=True)

    def audit(spec: ModelSpec) -> None:
        output = audit_dir / f"{spec.name}.json"
        identity = read_json(identities[spec.name])
        if output.exists():
            try:
                cached = read_json(output)
                if (
                    cached.get("schema") == "scalellm_tokenizer_boundary_audit_v1"
                    and cached.get("model_fingerprint_sha256")
                    == identity["fingerprint_sha256"]
                    and cached.get("empty_continuations_after_fix") == 0
                ):
                    announce(f"boundary-audit cache hit {spec.name}")
                    return
            except Exception:
                pass
        announce(f"auditing tokenizer boundaries {spec.name}")
        run_checked([
            args.python,
            str(THIS_DIR / "audit_tokenizer_boundaries.py"),
            "--model", str(args.model_root / spec.directory),
            "--model-identity", str(identities[spec.name]),
            "--output", str(output),
        ])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(audit, spec) for spec in MODEL_SPECS]
        for future in as_completed(futures):
            future.result()


def identity_fingerprint(identity_path: Path) -> str:
    return str(read_json(identity_path)["fingerprint_sha256"])


def merged_is_valid(job: Job, identity_path: Path) -> bool:
    path = job.phase_dir / "merged" / "manifest.json"
    if not path.exists():
        return False
    try:
        value = read_json(path)
        protocol = value["protocol"]
        identity = value["model_identity"]
        return (
            value["status"] == "complete"
            and value["case"] == job.case
            and protocol["protocol"] == "literature_2048"
            and protocol["full_split"] == (job.limit == 0)
            and identity["checkpoint_name"] == job.spec.name
            and identity["fingerprint_sha256"] == identity_fingerprint(identity_path)
        )
    except Exception:
        return False


def worker_is_valid(worker_dir: Path, job: Job, identity_path: Path) -> bool:
    path = worker_dir / "manifest.json"
    if not path.exists():
        return False
    try:
        value = read_json(path)
        return (
            value["status"] == "complete"
            and value["case"] == job.case
            and value["protocol"]["full_split"] == (job.limit == 0)
            and value["model_identity"]["fingerprint_sha256"]
            == identity_fingerprint(identity_path)
            and set(value["tasks"]) == set(ALL_TASKS.split(","))
        )
    except Exception:
        return False


def next_worker_dir(job: Job, gpu: int, identity_path: Path) -> Path:
    job.phase_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(job.phase_dir.glob("worker_gpu*_attempt*"))
    for candidate in existing:
        if worker_is_valid(candidate, job, identity_path):
            return candidate
    attempt = len(existing) + 1
    return job.phase_dir / f"worker_gpu{gpu}_attempt{attempt:03d}"


def merge_worker(args: argparse.Namespace, job: Job, worker_dir: Path) -> None:
    run_checked([
        args.python,
        str(THIS_DIR / "merge_eval_shards.py"),
        "--source", str(worker_dir),
        "--output", str(job.phase_dir / "merged"),
    ])


def run_job(
    args: argparse.Namespace,
    job: Job,
    gpu: int,
    identity_path: Path,
) -> dict[str, Any]:
    started = time.time()
    if merged_is_valid(job, identity_path):
        announce(f"cache hit {job.label}")
        return {"label": job.label, "status": "cached", "gpu": gpu, "elapsed_sec": 0.0}
    worker_dir = next_worker_dir(job, gpu, identity_path)
    if worker_is_valid(worker_dir, job, identity_path):
        merge_worker(args, job, worker_dir)
        if not merged_is_valid(job, identity_path):
            raise RuntimeError(f"merged validation failed for cached worker {job.label}")
        return {"label": job.label, "status": "merged_cached_worker", "gpu": gpu, "elapsed_sec": 0.0}
    worker_dir.mkdir(parents=True, exist_ok=True)
    batch_sizes = []
    current = max(1, int(args.batch_size))
    while current not in batch_sizes:
        batch_sizes.append(current)
        if current == 1:
            break
        current = max(1, current // 2)
    model = args.model_root / job.spec.directory
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    for attempt_index, batch_size in enumerate(batch_sizes, 1):
        log_path = job.phase_dir / f"gpu{gpu}_attempt{attempt_index:03d}.log"
        announce(f"start {job.label} on GPU{gpu}, batch={batch_size}")
        command = [
            args.python,
            str(THIS_DIR / "run_eval_worker.py"),
            "--case", job.case,
            "--protocol", "literature_2048",
            "--tasks", ALL_TASKS,
            "--model", str(model),
            "--model-identity", str(identity_path),
            "--output", str(worker_dir),
            "--device", "cuda:0",
            "--batch-size", str(batch_size),
            "--ppl-batch-size", str(args.ppl_batch_size),
            "--limit", str(job.limit),
            "--seed", str(args.seed),
        ]
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        if process.returncode == 0 and worker_is_valid(worker_dir, job, identity_path):
            merge_worker(args, job, worker_dir)
            if not merged_is_valid(job, identity_path):
                raise RuntimeError(f"merged validation failed for {job.label}")
            elapsed = time.time() - started
            announce(f"complete {job.label} on GPU{gpu} in {elapsed:.1f}s")
            return {"label": job.label, "status": "complete", "gpu": gpu, "elapsed_sec": elapsed}
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        oom = "out of memory" in log_text.lower()
        if oom and batch_size > 1:
            announce(f"OOM {job.label} on GPU{gpu}; retry with smaller batch")
            continue
        tail = "\n".join(log_text.splitlines()[-20:])
        raise RuntimeError(
            f"worker failed for {job.label} on GPU{gpu}, log={log_path}:\n{tail}"
        )
    raise RuntimeError(f"all batch-size retries failed for {job.label}")


def job_priority(job: Job) -> tuple[int, int]:
    # Longest processing time first improves two-GPU queue balance.
    case_weight = 3 if job.case != "bf16" else 1
    return (case_weight * job.spec.layers, job.spec.layers)


def run_queue(
    args: argparse.Namespace,
    jobs: list[Job],
    identities: dict[str, Path],
    state: dict[str, Any],
) -> None:
    pending = sorted(jobs, key=job_priority, reverse=True)
    queue_lock = threading.Lock()
    results_lock = threading.Lock()
    failures: list[str] = []

    def gpu_loop(gpu: int) -> None:
        while True:
            with queue_lock:
                if not pending:
                    return
                job = pending.pop(0)
            try:
                result = run_job(args, job, gpu, identities[job.spec.name])
                with results_lock:
                    state["jobs"][job.label] = result
                    write_state(args.output, state)
            except Exception as exc:
                message = f"{job.label}: {type(exc).__name__}: {exc}"
                announce(f"FAILED {message}")
                with results_lock:
                    failures.append(message)
                    state["jobs"][job.label] = {
                        "label": job.label,
                        "status": "failed",
                        "gpu": gpu,
                        "error": str(exc),
                    }
                    write_state(args.output, state)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(gpu_loop, gpu) for gpu in (0, 1)]
        for future in as_completed(futures):
            future.result()
    if failures:
        raise RuntimeError("job failures:\n" + "\n".join(failures))


def main() -> None:
    args = parse_args()
    args.model_root = args.model_root.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    check_gpu_count()
    state: dict[str, Any] = {
        "schema": "scalellm_six_model_runner_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "preparing",
        "stage": args.stage,
        "model_root": str(args.model_root),
        "output": str(args.output),
        "jobs": {},
    }
    write_state(args.output, state)
    data_command = [args.python, str(THIS_DIR / "prepare_standard_data.py")]
    if args.offline_data:
        data_command.append("--offline")
    with (args.output / "data_manifest.json").open("w", encoding="utf-8") as output:
        run_checked(data_command, stdout=output)
    run_checked([args.python, str(THIS_DIR / "test_protocol.py")])
    identities = prepare_identities(args)
    prepare_boundary_audits(args, identities)

    if args.stage in {"all", "smoke"}:
        state["status"] = "smoke"
        write_state(args.output, state)
        smoke_root = args.output / "smoke"
        smoke_jobs = [
            Job(spec, case, 1, smoke_root)
            for spec in MODEL_SPECS
            for case in CASES
        ]
        run_queue(args, smoke_jobs, identities, state)
    if args.stage in {"all", "full"}:
        if args.stage == "full":
            smoke_root = args.output / "smoke"
            missing_smoke = [
                job.label
                for spec in MODEL_SPECS
                for case in CASES
                for job in [Job(spec, case, 1, smoke_root)]
                if not merged_is_valid(job, identities[spec.name])
            ]
            if missing_smoke:
                raise RuntimeError(
                    "full stage requires completed smoke gates: " + ", ".join(missing_smoke)
                )
        state["status"] = "full"
        write_state(args.output, state)
        full_jobs = [
            Job(spec, case, 0, args.output)
            for spec in MODEL_SPECS
            for case in CASES
        ]
        run_queue(args, full_jobs, identities, state)

    if args.stage in {"all", "full"}:
        run_checked([
            args.python,
            str(THIS_DIR / "summarize_six_models.py"),
            "--root", str(args.output),
        ])
    state["status"] = "complete"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_state(args.output, state)
    announce(f"six-model plan complete: {args.output}")


if __name__ == "__main__":
    main()
