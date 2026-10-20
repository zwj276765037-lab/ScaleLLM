#!/usr/bin/env python3
"""Run one owned Vivado stage with bounded resources and durable receipts."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

try:
    from . import m002_execution_profile as full_impl
except ImportError:
    import m002_execution_profile as full_impl

ROOT = Path(__file__).resolve().parents[2]
GIB = 1024 ** 3
LIMITS = {"create": 1800, "synth": 10800, "place": 7200, "route": 7200}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


def process_table():
    rows = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            raw = Path(entry.path, "stat").read_text()
            fields = raw[raw.rindex(")") + 2:].split()
            rows[int(entry.name)] = {
                "ppid": int(fields[1]), "pgrp": int(fields[2]),
                "start_ticks": int(fields[19]), "rss_bytes": int(fields[21]) * os.sysconf("SC_PAGE_SIZE"),
                "cpu_ticks": int(fields[11]) + int(fields[12]), "nice": int(fields[16]),
            }
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
            pass
    return rows


def owned_processes(table, leader, tracked):
    owned = {pid: row for pid, row in table.items()
             if row["pgrp"] == leader or tracked.get(pid) == row["start_ticks"]}
    changed = True
    while changed:
        changed = False
        for pid, row in table.items():
            if pid not in owned and row["ppid"] in owned:
                owned[pid] = row
                changed = True
    tracked.update({pid: row["start_ticks"] for pid, row in owned.items()})
    return owned


def mem_available():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable is unavailable")


def terminate_owned(leader, tracked):
    for sig, delay in ((signal.SIGTERM, 5), (signal.SIGKILL, 0)):
        rows = owned_processes(process_table(), leader, tracked)
        for pid in rows:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        if rows and delay:
            time.sleep(delay)
    return sorted(owned_processes(process_table(), leader, tracked))


def terminate_and_reap(proc, tracked):
    """Distinguish a not-yet-reaped leader from actual final survivors."""
    before_reap = terminate_owned(proc.pid, tracked)
    native_rc = proc.wait()
    remaining = sorted(owned_processes(process_table(), proc.pid, tracked))
    return native_rc, before_reap, remaining


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=LIMITS)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--synth-report", type=Path)
    parser.add_argument("--synth-attempt", type=Path)
    parser.add_argument("--place-report", type=Path)
    parser.add_argument("--init-report", type=Path)
    parser.add_argument("--opt-report", type=Path)
    parser.add_argument("--pre-place-report", type=Path)
    parser.add_argument("--execution-profile", choices=[full_impl.PROFILE])
    args = parser.parse_args()
    if sum(bool(x) for x in (args.init_report,args.opt_report,args.pre_place_report))>1:
        raise ValueError("Choose one exact recovery checkpoint phase")
    if (args.init_report or args.opt_report or args.pre_place_report) and args.stage != "place":
        raise ValueError("INIT/OPT checkpoint continuation is a place-stage input")
    attempt, project, report = (p.resolve() for p in (args.attempt, args.project, args.report))
    evidence_root = ROOT.parent / "E002_m002_synthesis_and_physical_baseline/experiment_results/runs"
    auth = full_impl.authorization(ROOT.parent.parent, args.stage, attempt, report) if args.execution_profile else None
    if attempt.exists() or (not auth and not attempt.is_relative_to(evidence_root)):
        raise ValueError("Attempt must be a new authorized run directory")
    if not project.is_relative_to(ROOT / "vivado/project") or not report.is_relative_to(ROOT / "vivado/reports"):
        raise ValueError("Project/report must remain in the hardware root")
    if report.exists() or (args.stage == "create" and project.exists()):
        raise ValueError("Project/report attempt already used")
    cpus = sorted(os.sched_getaffinity(0))[:8]
    if auth and cpus != list(range(8)):
        raise RuntimeError("E003 requires CPUs 0-7")
    if len(cpus) != 8:
        raise RuntimeError("Eight allowed logical CPUs are required")
    if mem_available() < 48 * GIB or shutil.disk_usage(ROOT).free < 30 * GIB:
        raise RuntimeError("Preflight memory/disk reserve is unavailable")
    lock = (ROOT / "vivado/.m002_eda.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    balance = full_impl.budget(ROOT.parent.parent, args.stage) if auth else None
    timeout = balance["effective_timeout_seconds"] if balance else LIMITS[args.stage]
    os.sched_setaffinity(0, cpus)
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    attempt.mkdir(parents=True)
    env = {**os.environ, "HAP_JOBS": "8" if args.stage in {"place", "route"} else "4", "HAP_SYNTH_JOBS": "1", "HAP_NICE_INCREMENT": "0",
           "HAP_PROJECT_DIR": str(project), "HAP_REPORT_DIR": str(report),
           "HAP_CURRENT_ATTEMPT_DIR": str(attempt),
           "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "1"}
    env.pop("HAP_EXECUTION_PROFILE", None)
    if auth:
        full_impl.save(attempt / "execution_authorization.json", auth)
        env["HAP_EXECUTION_PROFILE"] = full_impl.PROFILE
    env.pop("HAP_BD_VALIDATE_ONLY", None)
    if args.synth_report:
        env["HAP_SYNTH_REPORT_DIR"] = str(args.synth_report.resolve())
    if args.synth_attempt:
        env["HAP_SYNTH_ATTEMPT_DIR"] = str(args.synth_attempt.resolve())
    if args.place_report:
        env["HAP_PLACE_REPORT_DIR"] = str(args.place_report.resolve())
    if args.init_report:
        env["HAP_INIT_REPORT_DIR"] = str(args.init_report.resolve())
    if args.opt_report:
        env["HAP_OPT_REPORT_DIR"] = str(args.opt_report.resolve())
    if args.pre_place_report:
        env["HAP_PRE_PLACE_REPORT_DIR"] = str(args.pre_place_report.resolve())
    cmd = (["python3", str(ROOT / "vivado/scripts/run_m002_physical_stage.py"), args.stage]
           if args.stage in {"place", "route"}
           else [str(ROOT / "vivado/scripts/run_vcu118_board.sh"), args.stage])
    started = utc()
    metadata = {"stage": args.stage, "argv": cmd, "cwd": str(ROOT), "project": str(project),
                "report": str(report), "environment": {k: v for k, v in env.items() if k.startswith("HAP_")},
                "cpu_affinity": cpus, "nice": 5, "rss_limit_bytes": 192 * GIB,
                "mem_available_floor_bytes": 48 * GIB, "mem_low_grace_seconds": 30,
                "disk_free_floor_bytes": 30 * GIB, "timeout_seconds": timeout, "started_utc": started}
    if auth:
        metadata.update(execution_profile=full_impl.PROFILE, authorization=full_impl.identity(attempt/"execution_authorization.json"), budget=balance)
    write_json(attempt / "command.json", metadata)
    (attempt / "runner.sha256").write_text(f"{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}  {Path(__file__)}\n")
    tracked = {}
    stopped = None
    proc = None
    native_rc = None
    max_rss = 0
    minimum_mem = mem_available()
    minimum_disk = shutil.disk_usage(ROOT).free
    low_since = None
    start_mono = time.monotonic()

    def prepare_child():
        os.setsid()
        os.sched_setaffinity(0, cpus)
        os.setpriority(os.PRIO_PROCESS, 0, 5)

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with (attempt / "launcher.log").open("w") as log, (attempt / "resources.jsonl").open("w", buffering=1) as samples:
            proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    preexec_fn=prepare_child)
            metadata.update({"supervisor_pid": os.getpid(), "leader_pid": proc.pid, "process_group": proc.pid})
            write_json(attempt / "started.json", metadata)
            print(json.dumps({"started": True, "stage": args.stage, "pid": proc.pid,
                              "supervisor_pid": os.getpid(), "attempt": str(attempt), "report": str(report)}), flush=True)
            while True:
                rows = owned_processes(process_table(), proc.pid, tracked)
                for pid in rows:
                    try:
                        if not os.sched_getaffinity(pid).issubset(cpus):
                            os.sched_setaffinity(pid, cpus)
                    except ProcessLookupError:
                        pass
                rss = sum(row["rss_bytes"] for row in rows.values())
                available = mem_available()
                disk = shutil.disk_usage(ROOT).free
                elapsed = time.monotonic() - start_mono
                max_rss, minimum_mem, minimum_disk = max(max_rss, rss), min(minimum_mem, available), min(minimum_disk, disk)
                sample = {"utc": utc(), "elapsed_seconds": elapsed, "rss_bytes": rss,
                          "mem_available_bytes": available, "disk_free_bytes": disk, "processes": rows}
                samples.write(json.dumps(sample) + "\n")
                if available < 48 * GIB:
                    low_since = low_since or time.monotonic()
                else:
                    low_since = None
                if rss > 192 * GIB:
                    stopped = "task_tree_rss_above_192GiB"
                elif low_since is not None and time.monotonic() - low_since >= 30:
                    stopped = "system_mem_available_below_48GiB_for_30s"
                elif disk < 30 * GIB:
                    stopped = "disk_free_below_30GiB"
                elif elapsed >= timeout:
                    stopped = "stage_wall_timeout"
                if auth and (attempt / "actual_eda_started.json").exists():
                    anchor = json.loads((ROOT.parent.parent / full_impl.EXPERIMENT / "experiment_results/physical_budget_anchor.json").read_text())
                    global_deadline = full_impl.stamp(anchor["launched_utc"]) + dt.timedelta(seconds=full_impl.GLOBAL_SECONDS)
                    metadata["actual_global_deadline_utc"] = global_deadline.isoformat()
                    metadata["effective_deadline_utc"] = min(full_impl.stamp(started)+dt.timedelta(seconds=timeout),global_deadline).isoformat()
                    if not (attempt / "effective_budget.json").exists():
                        write_json(attempt / "effective_budget.json", {"budget":balance,"started_utc":started,"global_anchor":anchor, "actual_global_deadline_utc":metadata["actual_global_deadline_utc"], "effective_deadline_utc":metadata["effective_deadline_utc"]})
                    if full_impl.now() >= global_deadline:
                        stopped = "stage_wall_timeout"
                native_rc = proc.poll()
                if stopped or native_rc is not None:
                    break
                time.sleep(5)
    except BaseException as exc:
        stopped = f"supervisor_exception:{type(exc).__name__}:{exc}"
    finally:
        before_reap, remaining = [], []
        if proc:
            native_rc, before_reap, remaining = terminate_and_reap(proc, tracked)
        rc = native_rc if not stopped and native_rc is not None else 124 if stopped == "stage_wall_timeout" else 125
        write_json(attempt / "status.json", {**metadata, "execution_state": "completed", "ended_utc": utc(),
                   "native_exit_code": native_rc, "exit_code": rc, "stop_reason": stopped,
                   "max_tree_rss_bytes": max_rss, "minimum_mem_available_bytes": minimum_mem,
                   "minimum_disk_free_bytes": minimum_disk, "owned_before_reap": before_reap,
                   "owned_survivors": remaining})
        print(json.dumps({"completed": True, "stage": args.stage, "exit_code": rc,
                          "stop_reason": stopped, "owned_survivors": remaining}), flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
