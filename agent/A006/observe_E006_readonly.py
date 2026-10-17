#!/usr/bin/env python3
"""Passive bounded-output observer; never controls the detached native session."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.sched_setaffinity(0, set(range(8)))
os.setpriority(os.PRIO_PROCESS, 0, 5)
active = json.loads((ROOT / 'agent/A006/resume_E006.json').read_text())['active']
attempt = ROOT / active['attempt']
report = ROOT / active['report']
last = None
last_summary = 0.0
while True:
    receipt = report / 'stage_receipts.tsv'
    content = receipt.read_text() if receipt.exists() else None
    if content != last:
        print(json.dumps(dict(phase_receipt_observation=content)), flush=True)
        last = content
    if time.monotonic() - last_summary >= 60 or (attempt / 'status.json').exists():
        view = subprocess.run(['/usr/bin/python3', str(ROOT / 'agent/A006/inspect_E006_active.py'), '--brief'], capture_output=True, text=True)
        print(view.stdout, flush=True)
        if view.returncode:
            print(view.stderr, flush=True)
        last_summary = time.monotonic()
    if (attempt / 'status.json').exists():
        break
    time.sleep(20)
