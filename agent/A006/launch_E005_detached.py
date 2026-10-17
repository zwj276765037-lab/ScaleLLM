#!/usr/bin/env python3
"""Launch the installed E005 supervisor with independent session and file IO."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    label, *arguments = sys.argv[1:]
    assert re.fullmatch(r'R\d{3}_AT\d{3}_[a-zA-Z0-9_]+', label)
    assert arguments and arguments[0] in {'preflight','xsim','create','synth','place','route'}
    attempt = Path(arguments[arguments.index('--attempt')+1]).resolve()
    report = Path(arguments[arguments.index('--report')+1]).resolve()
    assert attempt.is_relative_to(ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs')
    assert report.is_relative_to(ROOT/'project/hardware/vivado/reports')
    assert not attempt.exists() and not report.exists()
    base = Path(__file__).parent
    receipt = base/f'detached_{label}.json'
    log = base/f'detached_{label}.log'
    assert not receipt.exists() and not log.exists()
    argv = ['/usr/bin/python3', str(ROOT/'project/hardware/vivado/scripts/run_m002_optimized.py'), *arguments]
    with log.open('xb') as output:
        child = subprocess.Popen(argv, cwd=ROOT, start_new_session=True, close_fds=True,
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
    time.sleep(.2)
    try:
        fields=Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()
        identity=dict(ppid=int(fields[1]), pgrp=int(fields[2]), start_ticks=int(fields[19]),
                      rss_bytes=int(fields[21])*4096, cpu_ticks=int(fields[11])+int(fields[12]), nice=int(fields[16]))
    except FileNotFoundError:
        identity=None
    value=dict(launched_utc=datetime.now(timezone.utc).isoformat(), argv=argv, cwd=str(ROOT),
        supervisor_pid=child.pid, supervisor_proc_identity=identity,
        mechanism='installed Python subprocess.Popen(start_new_session=True,close_fds=True,stdin=DEVNULL,stdout/stderr=file)',
        independent_session=bool(identity and identity['pgrp']==child.pid),
        stdio_log=str(log), attempt=str(attempt), report=str(report), poll=child.poll(),
        launcher_source=dict(path=str(Path(__file__)),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        limitation='actual launch only; inspect current PID/start, original status and lock; not an absolute persistence guarantee')
    with receipt.open('x') as output:
        json.dump(value,output,indent=2);output.write('\n')
    print(json.dumps(dict(receipt=str(receipt), **value),indent=2))


if __name__=='__main__':
    main()
