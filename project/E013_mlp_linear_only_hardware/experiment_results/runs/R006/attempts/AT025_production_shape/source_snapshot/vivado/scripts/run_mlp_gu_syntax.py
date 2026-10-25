#!/usr/bin/env python3
"""Bounded two-CPU syntax analysis; no elaboration or functional claims."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

HW = Path(__file__).resolve().parents[2]
ROOT = HW.parents[1]
BIN = Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/xvlog')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def processes():
    rows = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            rows[int(entry.name)] = dict(sid=int(raw[3]), birth=int(raw[19]),
                                         rss=int(raw[21])*os.sysconf('SC_PAGE_SIZE'))
        except (OSError, ValueError, IndexError):
            pass
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt')
    parser.add_argument('sources', nargs='+')
    args = parser.parse_args()
    out = ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R006/attempts'/args.attempt
    out.mkdir(parents=True, exist_ok=False)
    sources = [HW / p for p in args.sources]
    identity = {str(p): sha(p) for p in sources}
    for p in sources:
        target = out/'source_snapshot'/p.relative_to(HW)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    identity[str(Path(__file__).resolve())] = sha(Path(__file__).resolve())
    (out/'inputs.json').write_text(json.dumps(identity, indent=2)+'\n')
    lock = (HW/'vivado/.m006_gu_syntax.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    cpus = sorted(os.sched_getaffinity(0))[:32][-2:]
    command = [str(BIN), '-sv', '-L', 'xpm', '-L', 'unisims_ver', *map(str, sources)]

    def setup():
        os.setsid()
        os.sched_setaffinity(0, cpus)
        os.nice(5)

    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    peak = 0
    stop = None
    low_since = None
    with (out/'xvlog.log').open('w') as log:
        proc = subprocess.Popen(command, cwd=out, stdout=log, stderr=subprocess.STDOUT,
                                preexec_fn=setup)
        birth = processes().get(proc.pid, {}).get('birth')
        if birth is None:
            raise RuntimeError('cannot bind compiler PID birth')
        owned_history = {}
        while True:
            table = processes()
            owned = {pid: row for pid, row in table.items()
                     if row['sid'] == proc.pid and row['birth'] >= birth}
            owned_history.update(owned)
            rss = sum(row['rss'] for row in owned.values())
            peak = max(peak, rss)
            available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                                 if line.startswith('MemAvailable:')))*1024
            low_since = low_since or time.monotonic() if available < 64*1024**3 else None
            reason = ('compiler_tree_RSS_4GiB' if rss > 4*1024**3 else
                      'MemAvailable_64GiB_30s' if low_since and time.monotonic()-low_since >= 30 else
                      'disk_below_30GiB' if shutil.disk_usage(out).free < 30*1024**3 else None)
            if reason and stop is None:
                stop = reason
                for pid, row in owned.items():
                    if processes().get(pid, {}).get('birth') == row['birth']:
                        os.kill(pid, signal.SIGTERM)
            rc = proc.poll()
            if rc is not None and not owned:
                break
            if stop:
                for pid, row in owned.items():
                    if processes().get(pid, {}).get('birth') == row['birth']:
                        os.kill(pid, signal.SIGKILL)
            time.sleep(0.1)
    changed = [p for p, h in identity.items() if sha(Path(p)) != h]
    result = dict(started=started, ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  native_returncode=rc, command=command, actual_affinity=cpus,
                  rss_limit_bytes=4*1024**3, peak_tree_rss_bytes=peak,
                  stop=stop, changed_inputs=changed, owned_processes=owned_history,
                  owned_survivors=[], scope='syntax analysis only; no elaboration/simulation',
                  verdict='PASS' if rc == 0 and stop is None and not changed else 'FAIL')
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result['verdict'], out)
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
