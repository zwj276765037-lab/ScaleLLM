#!/usr/bin/env python3
"""Resumable two-GPU scheduler for the six-model/five-config PPL extension."""

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

from run_extended_ppl_worker import TASK_ORDER
from six_model_matrix import FIVE_CONFIG_CASES, MODEL_SPECS, ModelSpec


THIS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = THIS_DIR.parents[3]
DEFAULT_MODEL_ROOT = WORKSPACE_ROOT / "fpga_llm_project" / "configs" / "models"
DEFAULT_PARENT = THIS_DIR.parent / "results" / "six_model_algorithm_literature_2048"
DEFAULT_OUTPUT = DEFAULT_PARENT / "extended_ppl_2048"
DEFAULT_IDENTITIES = DEFAULT_PARENT / "model_identities"
PRINT_LOCK = threading.Lock()


@dataclass(frozen=True)
class Job:
    spec: ModelSpec
    case: str

    @property
    def label(self) -> str:
        return f"{self.spec.name}/{self.case}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--identity-root", type=Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--python", default="/home/user/anaconda3/envs/zhouwenjun/bin/python")
    parser.add_argument("--tasks", default=",".join(TASK_ORDER))
    parser.add_argument("--ppl-batch-size", type=int, default=1)
    parser.add_argument("--limit-blocks", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260913)
    return parser.parse_args()


def announce(message: str) -> None:
    with PRINT_LOCK:
        print(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {message}", flush=True)


def atomic_state(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def manifest_valid(path: Path, job: Job, tasks: list[str], full_split: bool) -> bool:
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        results = {str(row["task"]): row for row in value["results"]}
        return (
            value.get("status") == "complete"
            and value.get("case") == job.case
            and value.get("model_spec", {}).get("name") == job.spec.name
            and bool(value.get("full_split")) == full_split
            and set(results) == set(tasks)
            and all(row.get("status") == "complete" for row in results.values())
        )
    except Exception:
        return False


def run_job(args: argparse.Namespace, job: Job, gpu: int, tasks: list[str]) -> dict[str, Any]:
    started = time.time()
    output = args.output / job.spec.name / job.case
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.json"
    full_split = args.limit_blocks <= 0
    if manifest_valid(manifest, job, tasks, full_split):
        announce(f"cache hit {job.label}")
        return {"label": job.label, "status": "cached", "gpu": gpu, "elapsed_sec": 0.0}
    identity = args.identity_root / f"{job.spec.name}.json"
    if not identity.is_file():
        raise FileNotFoundError(identity)
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    batch_sizes: list[int] = []
    current = max(1, int(args.ppl_batch_size))
    while current not in batch_sizes:
        batch_sizes.append(current)
        if current == 1:
            break
        current = max(1, current // 2)
    failure_tail = ""
    for attempt, batch_size in enumerate(batch_sizes, 1):
        log_path = output / f"gpu{gpu}_batch{batch_size}_attempt{attempt}.log"
        command = [
            args.python,
            str(THIS_DIR / "run_extended_ppl_worker.py"),
            "--case", job.case,
            "--model", str(args.model_root / job.spec.directory),
            "--model-identity", str(identity),
            "--output", str(output),
            "--tasks", ",".join(tasks),
            "--device", "cuda:0",
            "--block-size", "2048",
            "--ppl-batch-size", str(batch_size),
            "--limit-blocks", str(args.limit_blocks),
            "--seed", str(args.seed),
        ]
        announce(f"start {job.label} on GPU{gpu}, PPL batch={batch_size}")
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
        if process.returncode == 0 and manifest_valid(manifest, job, tasks, full_split):
            elapsed = time.time() - started
            announce(f"complete {job.label} on GPU{gpu}, batch={batch_size}, in {elapsed:.1f}s")
            return {
                "label": job.label,
                "status": "complete",
                "gpu": gpu,
                "ppl_batch_size": batch_size,
                "elapsed_sec": elapsed,
            }
        failure_tail = "\n".join(
            log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
        )
        if batch_size > 1:
            announce(f"retry {job.label} on GPU{gpu}: batch {batch_size} failed")
            continue
        raise RuntimeError(f"worker failed for {job.label}, log={log_path}:\n{failure_tail}")
    raise RuntimeError(f"worker failed for {job.label}:\n{failure_tail}")


def job_priority(job: Job) -> tuple[int, int]:
    case_weight = 3 if job.case != "bf16" else 1
    return case_weight * job.spec.layers, job.spec.layers


def main() -> None:
    args = parse_args()
    args.model_root = args.model_root.resolve()
    args.identity_root = args.identity_root.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    tasks = [part.strip() for part in args.tasks.split(",") if part.strip()]
    invalid = set(tasks) - set(TASK_ORDER)
    if invalid or len(tasks) != len(set(tasks)):
        raise ValueError(f"invalid/duplicate tasks: {sorted(invalid)}")
    gpu_query = subprocess.run(
        ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    )
    if len([line for line in gpu_query.stdout.splitlines() if line.strip()]) < 2:
        raise RuntimeError("two CUDA GPUs are required")
    state: dict[str, Any] = {
        "schema": "scalellm_extended_ppl_runner_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "model_root": str(args.model_root),
        "output": str(args.output),
        "tasks": tasks,
        "limit_blocks": None if args.limit_blocks <= 0 else args.limit_blocks,
        "jobs": {},
    }
    state_path = args.output / "runner_state.json"
    atomic_state(state_path, state)
    pending = sorted(
        [Job(spec, case) for spec in MODEL_SPECS for case in FIVE_CONFIG_CASES],
        key=job_priority,
        reverse=True,
    )
    queue_lock = threading.Lock()
    state_lock = threading.Lock()
    failures: list[str] = []

    def gpu_loop(gpu: int) -> None:
        while True:
            with queue_lock:
                if not pending:
                    return
                job = pending.pop(0)
            try:
                result = run_job(args, job, gpu, tasks)
            except Exception as exc:
                result = {"label": job.label, "status": "failed", "gpu": gpu, "error": str(exc)}
                failures.append(job.label)
                announce(f"FAILED {job.label}: {exc}")
            with state_lock:
                state["jobs"][job.label] = result
                atomic_state(state_path, state)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(gpu_loop, gpu) for gpu in (0, 1)]
        for future in as_completed(futures):
            future.result()
    state["status"] = "failed" if failures else "complete"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    state["failures"] = failures
    atomic_state(state_path, state)
    if failures:
        raise RuntimeError(f"extended PPL failures: {failures}")
    announce(f"extended PPL matrix complete: {args.output}")


if __name__ == "__main__":
    main()
