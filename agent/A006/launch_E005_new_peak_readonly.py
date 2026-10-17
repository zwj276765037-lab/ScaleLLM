#!/usr/bin/env python3
"""Detach the authorized bounded R006/AT003 supervisor after AT002 closure."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs'
prior = BASE / 'R006/attempts/AT002_closed_place_physopt_readonly'
status = json.loads((prior / 'status.json').read_text())
assert status['native_exit_code'] == status['exit_code'] == 0 and status['stop_reason'] is None
assert status['owned_survivors'] == [] and status['native_natural_terminal_observed']
terminal = json.loads((prior / 'readonly_terminal_facts.json').read_text())
assert terminal['engineering_execution_verified'] and terminal['checks']['lane_released']
wrapper = ROOT / 'agent/A006/new_worst_window_supplement/run_closed_comparison.py'
assert hashlib.sha256(wrapper.read_bytes()).hexdigest() == 'a4178f45767acc229b972d62c3826f651ea4ff382ee5115c65832cb9e0880ca0'
attempt = BASE / 'R006/attempts/AT003_new_peak_windows_readonly'
report = ROOT / 'project/hardware/vivado/reports/m002_E005_R006_AT003_new_peak_windows_readonly'
receipt = ROOT / 'agent/A006/detached_R006_AT003_new_peak_windows_readonly.json'
log = ROOT / 'agent/A006/R006_AT003_new_peak_windows_readonly_supervisor.log'
assert not any(p.exists() for p in [attempt, report, receipt, log])
argv = ['taskset', '-c', '0-7', 'nice', '-n', '5', '/usr/bin/python3', str(wrapper),
    '--attempt', str(attempt), '--report', str(report), '--route-attempt', str(BASE / 'R004/attempts/AT004_default_route')]
with log.open('xb') as stream:
    proc = subprocess.Popen(argv, cwd=ROOT, start_new_session=True, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
time.sleep(0.3)
try:
    fields = Path('/proc/' + str(proc.pid) + '/stat').read_text().rsplit(')', 1)[1].split()
    identity = dict(ppid=int(fields[1]), pgrp=int(fields[2]), start_ticks=int(fields[19]),
        rss_bytes=int(fields[21]) * 4096, cpu_ticks=int(fields[11]) + int(fields[12]), nice=int(fields[16]))
except FileNotFoundError:
    identity = None
value = dict(launched_utc=datetime.now(timezone.utc).isoformat(), argv=argv, cwd=str(ROOT),
    supervisor_pid=proc.pid, supervisor_proc_identity=identity,
    mechanism='Popen independent session,DEVNULL stdin,file stdout/stderr; taskset0-7/nice5 from launch',
    independent_session=bool(identity and identity['pgrp'] == proc.pid),
    stdio_log=str(log), attempt=str(attempt), report=str(report), poll=proc.poll(),
    prior_terminal_facts_sha256=hashlib.sha256((prior / 'readonly_terminal_facts.json').read_bytes()).hexdigest(),
    launcher_source=dict(path=str(Path(__file__)), sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
    limitation='Actual launch only; independently verify original PID/start,FLOCK,native open and final closure')
with receipt.open('x') as stream:
    stream.write(json.dumps(value, indent=2) + '\n')
print(json.dumps(dict(receipt=str(receipt), **value), indent=2))
