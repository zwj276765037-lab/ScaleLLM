"""Bounded read-only inspection, with an explicitly observed (not heartbeat) snapshot."""
from pathlib import Path
import datetime as dt
import json
import os
import re
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RESULTS=ROOT/'project/E003_m002_full_implementation/experiment_results'

def tail(path,maximum=262144):
    if not path.exists():return ''
    with path.open('rb') as handle:
        handle.seek(max(0,os.fstat(handle.fileno()).st_size-maximum))
        return handle.read().decode(errors='replace')

def proc(pid):
    try:
        raw=(Path('/proc')/str(pid)/'stat').read_text();f=raw[raw.rindex(')')+2:].split()
        return dict(pid=pid,state=f[0],ppid=int(f[1]),pgrp=int(f[2]),start_ticks=int(f[19]),cpu_ticks=int(f[11])+int(f[12]))
    except FileNotFoundError:return None

result={'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'one bounded read-only observation; no continuous agent heartbeat claim','stages':[]}
for run,name,report_name in [('R002','AT001_full_pre_place_restore_place_physopt','m002_E003_R002_AT001_full_pre_place_restore_place_physopt'),('R003','AT001_full_route','m002_E003_R003_AT001_full_route')]:
    attempt=RESULTS/'runs'/run/'attempts'/name;report=ROOT/'project/hardware/vivado/reports'/report_name
    if not attempt.exists():continue
    text=tail(report/'vivado.log');phases=re.findall(r'^Phase .*$',text,re.M)
    resources=tail(attempt/'continuation_resources.jsonl',32768).splitlines()
    last=json.loads(resources[-1]) if resources else None
    row=dict(run=run,attempt=str(attempt),report=str(report),last_phase_in_bounded_log=phases[-1] if phases else None,last_log_lines='\n'.join(text.splitlines()[-7:]),
             checkpoint_files_observed=[dict(name=p.name,bytes=p.stat().st_size,scope='file observed; native completion and package closure still require qualification') for p in report.glob('*.dcp')],resource=None,
             status=json.loads((attempt/'status.json').read_text()) if (attempt/'status.json').exists() else None)
    if last:
        row['resource']={k:last[k] for k in ('utc','rss_bytes','mem_available_bytes','disk_free_bytes')}
        row['tracked_live_processes']=[proc(int(pid)) for pid in last['processes']]
    handoff=attempt/'supervision_handoff'
    row['control_exceptions']=[str(p.relative_to(attempt)) for base in (attempt,handoff) for p in base.glob('*exception*.json')]
    row['resource_stop']=(attempt/'continuation_resource_stop.json').exists()
    if run=='R002':row['old_supervisor']=proc(3677862);row['watchdog']=proc(3687878)
    result['stages'].append(row)
path=RESULTS/'physical_observation.json';temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(path)
print(json.dumps(result))
