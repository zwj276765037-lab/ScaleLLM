#!/usr/bin/env python3
"""Read-only stage observer; separate from native supervision and EDA ownership."""
from pathlib import Path
import datetime, json, os, time
A=Path(__file__).resolve().parent
os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
last=None
with (A/'observer_events.jsonl').open('x',buffering=1) as stream:
    while True:
        log=A/'evidence/native/vivado.log';stage='NATIVE_LOG_PENDING'
        if log.exists():
            with log.open('rb') as f:
                f.seek(max(0,log.stat().st_size-24000));tail=f.read().decode(errors='replace')
            markers=[line for line in tail.splitlines() if line.startswith('SM013 ')]
            if markers:stage=markers[-1]
            elif last is not None:stage=last
        terminal=A/'status.json'
        if terminal.exists():stage='SUPERVISOR_TERMINAL'
        if stage!=last:
            record=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observer_pid=os.getpid(),stage=stage,native_control=False)
            resource=A/'resources.jsonl'
            if resource.exists():
                with resource.open('rb') as f:
                    f.seek(max(0,resource.stat().st_size-24000));rs=f.read().decode().splitlines()
                if rs:
                    r=json.loads(rs[-1]);record['resources']={k:r[k] for k in ['utc','rss_bytes','MemAvailable','disk_free']}
            if terminal.exists():
                s=json.loads(terminal.read_text());record['terminal']={k:s.get(k) for k in ['execution_state','native_exit_code','exit_code','stop_reason','owned_survivors','post_integrity_error']}
            stream.write(json.dumps(record)+'\n')
            temp=A/'observer_latest.json.tmp';temp.write_text(json.dumps(record,indent=2)+'\n');temp.replace(A/'observer_latest.json')
            print(json.dumps(record),flush=True);last=stage
        if terminal.exists():break
        time.sleep(15)
print('READONLY_OBSERVER_EXIT_0',flush=True)
