#!/usr/bin/env python3
"""E004 single read-only checkpoint diagnostic with original resource guards."""
from pathlib import Path
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'project/hardware/vivado/scripts'
sys.path.insert(0, str(SCRIPTS))
import run_m002_no_wall as guard

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def identity(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())

def save(name, value):
    p = OUT / name
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(p)

def interrupted(signum, frame):
    raise KeyboardInterrupt(f'signal {signum}')

def main():
    assert not (OUT / 'started.json').exists(), 'one immutable actual invocation'
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    lock = (ROOT / 'project/hardware/vivado/.m002_eda.lock').open('r')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    dcp = ROOT / 'project/hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/physopt.dcp'
    bound = identity(dcp)
    assert bound['sha256'] == 'c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91'
    assert guard.mem_available() >= 48 * guard.GIB
    assert shutil.disk_usage(OUT).free >= 30 * guard.GIB
    contract = ROOT / 'mission/M002_ddr_separation_and_timing_recovery/routability_analysis_contract_2026-10-16.md'
    pre = dict(checkpoint=bound, contract=identity(contract), query=identity(OUT/'readonly_query.tcl'),
               targets=identity(OUT/'query_targets.tcl'), target_manifest=identity(OUT/'query_target_manifest.json'),
               supervisor=identity(Path(__file__)), resource_helper=identity(SCRIPTS/'run_m002_no_wall.py'))
    save('input_bindings.json', pre)
    cmd = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado', '-mode', 'batch',
           '-notrace', '-source', str(OUT/'readonly_query.tcl'), '-log', str(OUT/'vivado.log'),
           '-journal', str(OUT/'vivado.jou')]
    env = {**os.environ, 'E004_CHECKPOINT': str(dcp), 'PYTHONDONTWRITEBYTECODE': '1',
           'OMP_NUM_THREADS': '4', 'OPENBLAS_NUM_THREADS': '1'}
    metadata = dict(started_utc=utc(), supervisor_pid=os.getpid(), argv=cmd, cwd=str(OUT),
                    cpu_affinity=list(range(8)), nice=5, max_threads=8, timeout_seconds=None,
                    no_output_timeout_seconds=None, rss_limit_bytes=192*guard.GIB,
                    MemAvailable_floor_bytes=48*guard.GIB, MemAvailable_grace_seconds=30,
                    disk_floor_bytes=30*guard.GIB, mode='readonly_open_report_get', inputs=pre)
    proc = None
    tracked = {}
    stop = None
    peak = 0
    min_mem = guard.mem_available()
    min_disk = shutil.disk_usage(OUT).free
    low_since = None
    begin = time.monotonic()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with (OUT/'launcher.log').open('w') as log, (OUT/'resources.jsonl').open('w', buffering=1) as resources:
            proc = subprocess.Popen(cmd, cwd=OUT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            metadata.update(leader_pid=proc.pid, process_group=proc.pid)
            save('started.json', metadata)
            print(json.dumps(dict(started=True, **{k:metadata[k] for k in ('started_utc','supervisor_pid','leader_pid')})), flush=True)
            while True:
                rows = guard.owned_processes(guard.process_table(), proc.pid, tracked)
                rss = sum(row['rss_bytes'] for row in rows.values())
                mem = guard.mem_available()
                disk = shutil.disk_usage(OUT).free
                peak = max(peak, rss); min_mem = min(min_mem, mem); min_disk = min(min_disk, disk)
                resources.write(json.dumps(dict(utc=utc(), elapsed_seconds=time.monotonic()-begin,
                    rss_bytes=rss, mem_available_bytes=mem, disk_free_bytes=disk, processes=rows))+'\n')
                low_since = (low_since if low_since is not None else time.monotonic()) if mem < 48*guard.GIB else None
                if rss > 192*guard.GIB: stop = 'tree_RSS_above_192GiB'
                elif low_since is not None and time.monotonic()-low_since >= 30: stop = 'MemAvailable_below_48GiB_30s'
                elif disk < 30*guard.GIB: stop = 'disk_below_30GiB'
                if proc.poll() is not None or stop: break
                time.sleep(5)
    except BaseException as exc:
        stop = f'{type(exc).__name__}:{exc}'
    finally:
        rc, before, remain = guard.terminate_and_reap(proc, tracked) if proc else (None, [], [])
        after_stat = dcp.stat()
        status = dict(**metadata, ended_utc=utc(), execution_state='completed',
                      native_exit_code=rc, exit_code=rc if stop is None and rc is not None else 125,
                      stop_reason=stop, max_tree_rss_bytes=peak, minimum_mem_available_bytes=min_mem,
                      minimum_disk_free_bytes=min_disk, tracked_identities=tracked,
                      owned_before_reap=before, owned_survivors=remain,
                      original_DCP_bytes_after=after_stat.st_size, original_DCP_mtime_ns_after=after_stat.st_mtime_ns)
        save('status.json', status)
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        print(json.dumps(dict(completed=True, exit_code=status['exit_code'], stop_reason=stop, survivors=remain)), flush=True)
    return status['exit_code']

if __name__ == '__main__':
    raise SystemExit(main())
