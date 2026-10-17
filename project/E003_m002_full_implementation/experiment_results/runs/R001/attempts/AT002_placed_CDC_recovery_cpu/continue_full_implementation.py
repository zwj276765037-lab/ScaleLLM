#!/usr/bin/env python3
"""New closed-place POST/physopt, then automatically qualified route; no timed manager."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HW=ROOT/'project/hardware';OUT=Path(__file__).parent
sys.path.insert(0,str(HW/'vivado/scripts'))
import m002_physical_evidence as evidence
import m002_execution_profile as profile
ATTEMPTS=ROOT/profile.EXPERIMENT/'experiment_results/runs'
PROJECT=HW/'vivado/project/m002_E002_R001_AT001_fresh'
SYNTH_REPORT=HW/'vivado/reports/m002_E002_R001_AT002_fresh_synth'
SYNTH_ATTEMPT=ROOT/'project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth'
SOURCE=HW/'vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt'
PLACE_ATTEMPT=ATTEMPTS/'R002/attempts/AT002_closed_place_POST_physopt'
PLACE_REPORT=HW/'vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt'
ROUTE_ATTEMPT=ATTEMPTS/'R003/attempts/AT001_full_route'
ROUTE_REPORT=HW/'vivado/reports/m002_E003_R003_AT001_full_route'
state={'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'execution_state':'running','supervision_profile':'m002_no_wall_continuation','wall_clock_stop_disabled':True,'driver':evidence.file_id(Path(__file__)),'stages':[]}
def save():profile.save(OUT/'implementation_chain.json',state)
def run(stage,attempt,report,extra):
    cmd=[sys.executable,str(HW/'vivado/scripts/run_m002_no_wall.py'),stage,'--attempt',str(attempt),'--project',str(PROJECT),'--report',str(report),'--synth-report',str(SYNTH_REPORT),'--synth-attempt',str(SYNTH_ATTEMPT),'--execution-profile',profile.PROFILE]+extra
    entry={'stage':stage,'argv':cmd,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'attempt':str(attempt),'report':str(report)}
    state['stages'].append(entry);save()
    child=subprocess.Popen(cmd,cwd=HW)
    entry['supervisor_pid']=child.pid;save();rc=child.wait()
    entry.update(exit_code=rc,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    if (attempt/'status.json').exists():entry['status']=evidence.file_id(attempt/'status.json')
    save();return rc
save()
try:
    rc=run('place',PLACE_ATTEMPT,PLACE_REPORT,['--physical-report',str(SOURCE)])
    if rc==0:
        lineage=evidence.synth_lineage(PROJECT,SYNTH_REPORT,SYNTH_ATTEMPT)
        accepted=evidence.parent_place(PLACE_REPORT/'diagnostic_evidence.json',PROJECT,lineage)
        state['qualified_physopt_parent']={'evidence':evidence.file_id(PLACE_REPORT/'diagnostic_evidence.json'),'checkpoint':accepted['checkpoint']};save()
        rc=run('route',ROUTE_ATTEMPT,ROUTE_REPORT,['--place-report',str(PLACE_REPORT)])
    state['exit_code']=rc;state['execution_state']='completed' if rc==0 else 'failed'
except BaseException as exc:
    state['execution_state']='failed';state['error']=f'{type(exc).__name__}: {exc}';state['exit_code']=1
    raise
finally:
    state['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat();save()
raise SystemExit(state['exit_code'])
