#!/usr/bin/env python3
"""Detach one actually selected, evidence-bound E008 implementation supervisor."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import run_candidate as runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--e006-closeout', type=Path, required=True)
    args = parser.parse_args()
    attempt, report = args.attempt.resolve(), args.report.resolve()
    assert attempt.parent == runner.E008/'experiment_results/runs/R001/attempts'
    assert report.parent == runner.ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E008_R001_')
    runner.require_fresh_or_planned(attempt, report)
    runner.verify_manifest(runner.HERE/'prepared_manifest.json')
    runner.attribution_dependency(args.e006_closeout.resolve())
    tag = 'E008_R001_' + attempt.name
    receipt = runner.ROOT/'agent/A006'/('detached_'+tag+'.json')
    log = runner.ROOT/'agent/A006'/(tag+'_supervisor.log')
    assert not receipt.exists() and not log.exists(), 'Never overwrite launch evidence'
    argv = ['taskset', '-c', '0-7', 'nice', '-n', '5', '/usr/bin/python3', str(runner.HERE/'run_candidate.py'),
            '--attempt', str(attempt), '--report', str(report), '--e006-closeout', str(args.e006_closeout.resolve())]
    with log.open('xb') as stream:
        child = subprocess.Popen(argv, cwd=runner.ROOT, start_new_session=True, close_fds=True,
                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    time.sleep(0.3)
    try:
        fields = Path('/proc/'+str(child.pid)+'/stat').read_text().rsplit(')', 1)[1].split()
        proc = dict(pid=child.pid, start_ticks=int(fields[19]), ppid=int(fields[1]), pgrp=int(fields[2]), nice=int(fields[16]))
    except FileNotFoundError:
        proc = None
    value = dict(launched_utc=datetime.now(timezone.utc).isoformat(), argv=argv, cwd=str(runner.ROOT),
                 supervisor_pid=child.pid, supervisor_proc_identity=proc, poll=child.poll(), attempt=str(attempt),
                 report=str(report), stdio_log=str(log), launcher_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 limitation='Launch receipt only; actual native execution and unique lane must be independently verified.')
    with receipt.open('x') as stream: stream.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(receipt=str(receipt), **value), ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
