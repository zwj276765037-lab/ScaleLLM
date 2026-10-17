"""One default E003 physical chain: managed place/physopt then qualified route."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import subprocess
import sys
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HARDWARE=ROOT/'project/hardware'
RESULTS=ROOT/'project/E003_m002_full_implementation/experiment_results'
HERE=Path(__file__).resolve().parent
runner=HARDWARE/'vivado/scripts/run_managed_eda.py'
place=HARDWARE/'vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt'
route=HARDWARE/'vivado/reports/m002_E003_R003_AT001_full_route'
place_attempt=RESULTS/'runs/R002/attempts/AT001_full_pre_place_restore_place_physopt'
route_attempt=RESULTS/'runs/R003/attempts/AT001_full_route'
common=['--execution-profile','m002_full_implementation','--project',str(HARDWARE/'vivado/project/m002_E002_R001_AT001_fresh'),
        '--synth-report',str(HARDWARE/'vivado/reports/m002_E002_R001_AT002_fresh_synth'),
        '--synth-attempt',str(ROOT/'project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth')]
commands=[['python3',str(runner),'place','--attempt',str(place_attempt),'--report',str(place),'--pre-place-report',str(HARDWARE/'vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt'),*common],
          ['python3',str(runner),'route','--attempt',str(route_attempt),'--report',str(route),'--place-report',str(place),*common]]
record=dict(started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cwd=str(ROOT),commands=commands,completed_stages=[],execution_state='running')
def save():
    target=HERE/'implementation_chain.json';temp=target.with_suffix('.json.tmp');temp.write_text(json.dumps(record,indent=2)+'\n');temp.replace(target)
save()
for command in commands:
    rc=subprocess.run(command,cwd=ROOT).returncode
    stage=command[2]
    record['completed_stages'].append(dict(stage=stage,exit_code=rc,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat()));save()
    if rc:
        record.update(execution_state='failed',exit_code=rc,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());save();sys.exit(rc)
    attempt=place_attempt if stage=='place' else route_attempt
    status=json.loads((attempt/'status.json').read_text())
    assert status['exit_code']==0 and status['native_exit_code']==0 and not status['stop_reason'] and not status['owned_survivors']
record.update(execution_state='completed',exit_code=0,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());save()
