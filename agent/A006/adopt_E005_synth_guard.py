#!/usr/bin/env python3
"""Adopt the existing E005 native tree without relaunching or rewriting raw evidence."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'project/hardware/vivado/scripts'))
import run_m002_no_wall as guard


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    destination = Path(sys.argv[1]).resolve()
    attempt = ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs/R003/attempts/AT001_fresh_synth'
    report = ROOT/'project/hardware/vivado/reports/m002_E005_R003_AT001_fresh_synth'
    assert destination.parent == attempt and not destination.exists()
    old = json.loads((attempt/'started.json').read_text())
    leader = old['leader_pid']
    last = json.loads((attempt/'resources.jsonl').read_text().splitlines()[-1])
    tracked = {int(pid): row['start_ticks'] for pid, row in last['processes'].items()}
    table = guard.process_table()
    assert old['supervisor_pid'] not in table, 'original supervisor is still present'
    assert table[leader]['start_ticks'] == tracked[leader], 'original leader identity changed'
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    lock = (ROOT/'project/hardware/vivado/.m002_eda.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    destination.mkdir()
    started = guard.utc()
    metadata = dict(started_utc=started, adoption_supervisor_pid=os.getpid(),
        original_supervisor_pid=old['supervisor_pid'], original_leader_pid=leader,
        original_leader_start_ticks=tracked[leader], original_last_resource_utc=last['utc'],
        resource_supervision_gap=True, gap_end_utc=started,
        native_process_restarted=False, original_records_modified=False,
        attempt=str(attempt), report=str(report),
        original_started_sha256=hashlib.sha256((attempt/'started.json').read_bytes()).hexdigest(),
        guard_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        cpu_affinity=list(range(8)),nice=5,rss_limit_bytes=192*guard.GIB,
        mem_available_floor_bytes=48*guard.GIB,mem_low_grace_seconds=30,
        disk_free_floor_bytes=30*guard.GIB,timeout_seconds=None,no_output_timeout_seconds=None)
    save(destination/'started.json', metadata)
    print(json.dumps(metadata), flush=True)
    peak = 0
    minimum_mem = guard.mem_available()
    minimum_disk = shutil.disk_usage(ROOT).free
    low_since = None
    stopped = None
    live = {}
    def interrupted(signum, frame):
        raise RuntimeError(f'adoption_guard_interrupted_signal_{signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with (destination/'resources.jsonl').open('x', buffering=1) as samples:
            while True:
                rows = guard.owned_processes(guard.process_table(), leader, tracked)
                live = {}
                for pid, row in rows.items():
                    try:
                        state = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
                        if state == 'Z':
                            continue
                        live[pid] = row
                        if not os.sched_getaffinity(pid).issubset(range(8)):
                            os.sched_setaffinity(pid, set(range(8)))
                    except (ProcessLookupError, FileNotFoundError):
                        continue
                rss = sum(row['rss_bytes'] for row in live.values())
                mem = guard.mem_available()
                disk = shutil.disk_usage(ROOT).free
                peak=max(peak,rss);minimum_mem=min(minimum_mem,mem);minimum_disk=min(minimum_disk,disk)
                samples.write(json.dumps(dict(utc=guard.utc(),rss_bytes=rss,
                    mem_available_bytes=mem,disk_free_bytes=disk,processes=rows,live_pids=sorted(live)))+'\n')
                low_since = (low_since if low_since is not None else time.monotonic()) if mem<48*guard.GIB else None
                if rss>192*guard.GIB: stopped='task_tree_rss_above_192GiB'
                elif low_since is not None and time.monotonic()-low_since>=30: stopped='MemAvailable_below_48GiB_30s'
                elif disk<30*guard.GIB: stopped='disk_free_below_30GiB'
                if stopped:
                    print(json.dumps(dict(resource_stop=stopped,utc=guard.utc())),flush=True)
                    guard.terminate_owned(leader,tracked)
                    break
                if not live:
                    break
                time.sleep(5)
    except BaseException as exc:
        stopped=f'{type(exc).__name__}:{exc}'
        print(stopped,flush=True)
    finally:
        final_rows=guard.owned_processes(guard.process_table(),leader,tracked)
        save(destination/'status.json',dict(**metadata,ended_utc=guard.utc(),stop_reason=stopped,
            native_exit_code=None,native_exit_not_waitable_after_orphaning=True,
            max_tree_rss_bytes=peak,minimum_mem_available_bytes=minimum_mem,
            minimum_disk_free_bytes=minimum_disk,final_owned_processes=final_rows,
            controller_launcher_status=(report/'launcher_status.txt').read_text() if (report/'launcher_status.txt').exists() else None))
        fcntl.flock(lock,fcntl.LOCK_UN)
        lock.close()


if __name__=='__main__':
    main()
