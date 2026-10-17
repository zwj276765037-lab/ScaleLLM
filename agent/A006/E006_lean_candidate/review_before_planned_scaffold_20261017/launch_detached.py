#!/usr/bin/env python3
"""Detach the authorized single-physopt E006 attribution supervisor."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import time

parser=argparse.ArgumentParser(description='Prepared independent lean launcher; run only after actual authorization and closed original lane')
parser.add_argument('--authorization',type=Path,required=True)
args=parser.parse_args()
ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
authorization=json.loads(args.authorization.resolve().read_text())
assert authorization.get('execution_authorized') is True and authorization.get('decision')=='allow_readonly_lean_replacement', 'No actual lean execution authorization'
attempt = ROOT / 'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/attempts/AT001_lean_physopt_attribution'
report = ROOT / 'project/hardware/vivado/reports/m002_E006_R003_AT001_lean_physopt_attribution'
receipt = ROOT / 'agent/A006/detached_E006_R003_AT001_lean_physopt_attribution.json'
log = ROOT / 'agent/A006/E006_R003_AT001_lean_physopt_attribution_supervisor.log'
assert not any(p.exists() for p in [attempt, report, receipt, log])
argv = ['taskset', '-c', '0-7', 'nice', '-n', '5', '/usr/bin/python3', str(SOURCE / 'run_attribution_lean.py'), '--attempt', str(attempt), '--report', str(report), '--authorization', str(args.authorization.resolve())]
with log.open('xb') as stream:
    child = subprocess.Popen(argv, cwd=ROOT, start_new_session=True, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
time.sleep(0.3)
try:
    fields = Path('/proc/' + str(child.pid) + '/stat').read_text().rsplit(')', 1)[1].split()
    proc = dict(pid=child.pid, start_ticks=int(fields[19]), ppid=int(fields[1]), pgrp=int(fields[2]), nice=int(fields[16]))
except FileNotFoundError:
    proc = None
value = dict(launched_utc=datetime.now(timezone.utc).isoformat(), argv=argv, cwd=str(ROOT), supervisor_pid=child.pid,
    supervisor_proc_identity=proc, poll=child.poll(), attempt=str(attempt), report=str(report), stdio_log=str(log),
    mechanism='Detached Popen independent session with DEVNULL stdin,file stdout/stderr,taskset0-7/nice5 from launch',
    launcher_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitation='Launch receipt only; independently verify actual native start and original process/lock identities')
with receipt.open('x') as stream:
    stream.write(json.dumps(value, indent=2) + '\n')
print(json.dumps(dict(receipt=str(receipt), **value), indent=2))
