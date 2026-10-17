"""Observe terminal owned PIDs and seal actual closed outputs; does not run EDA."""
from pathlib import Path
import datetime as dt
import json
import sys
sys.dont_write_bytecode=True
here=Path(__file__).resolve().parent
sys.path.insert(0,str(here if (here/'m002_physical_evidence.py').is_file() else here/'vivado/scripts'))
import m002_physical_evidence as m
workspace=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
m.ROOT=workspace/'project/hardware'
m.require(len(sys.argv)==2,'expected exact source report directory')
source=Path(sys.argv[1]).resolve()
m.require(source.is_relative_to(m.ROOT/'vivado/reports'),'foreign physical source report')
command=json.loads((source/'command.json').read_text());attempt=Path(command['managed_attempt'])
status_path=attempt/'status.json';status=json.loads(status_path.read_text())
m.require(status.get('exit_code')==124 and status.get('native_exit_code')==-15 and
          status.get('stop_reason')=='stage_wall_timeout' and not status.get('owned_survivors'),
          'source has not ended in the qualified bounded timeout')
tracked={}
for line in (attempt/'resources.jsonl').read_text().splitlines():
    for pid,row in json.loads(line)['processes'].items():
        pid=int(pid);ticks=row['start_ticks']
        m.require(pid not in tracked or tracked[pid]==ticks,'ambiguous owned PID identity')
        tracked[pid]=ticks
checks=[]
for pid,ticks in sorted(tracked.items()):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text();fields=raw[raw.rindex(')')+2:].split()
        actual=int(fields[19]);state='reused_pid' if actual!=ticks else 'still_present'
    except (FileNotFoundError,ProcessLookupError):
        actual=None;state='not_present'
    m.require(state!='still_present',f'owned PID identity still present: {pid}')
    checks.append(dict(pid=pid,expected_start_ticks=ticks,observed_start_ticks=actual,state=state))
m.require(tracked,'no actual owned PID samples')
log=(source/'vivado.log').read_text(errors='replace')
checkpoints={};packages={};receipts={};posts={}
for point,native in (('place','place_design'),('physopt','phys_opt_design')):
    cp=source/f'{point}.dcp';receipt=source/f'{point}_command_result.txt'
    if cp.is_file() and receipt.is_file() and f"The checkpoint '{cp}' has been generated" in log:
        values=m.key_values(receipt)
        if values.get('phase')==point and values.get('command')==native and values.get('native_tcl_code')=='0':
            packages[point]=m.checkpoint_package(cp);checkpoints[point]=m.file_id(cp);receipts[point]=m.file_id(receipt)
    result=source/f'{point}_result.txt';integrity=source/f'integrity_{point}.json'
    if result.is_file() and integrity.is_file():
        values=m.key_values(result);proof=json.loads(integrity.read_text())
        if values.get('completed')=='1' and values.get('diagnostic_eligible')=='1' and values.get('phase')==point:
            m.require(values.get('blackboxes')=='0' and values.get('clock_coverage')=='COMPLETE_INTERNAL' and
                      proof.get('phase')==point and not proof.get('gate_issues'),'completed POST claims invalid coverage')
            m.verify_reset_proof(proof['reset_structure']);m.verify_cdc_proof(proof['cdc_classification'])
            posts[point]=dict(result=m.file_id(result),integrity=m.file_id(integrity))
m.require(checkpoints,'no closed successful native physical checkpoint; no further place restart')
manifest=attempt/'closed_physical_source.sha256';completion=attempt/'closed_physical_source_completion.json'
m.require(not manifest.exists() and not completion.exists(),'source closure already exists; preserve original')
rows=''.join(f'{m.sha256(p)}  {p}\n' for p in sorted(source.rglob('*')) if p.is_file())
manifest.write_text(rows)
value=dict(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    observation_scope='post-termination measurement of original outputs; no original EDA status/report rewritten',
    original_status=m.file_id(status_path),processes_gone=True,checks=checks,
    manifest=m.file_id(manifest),checkpoints=checkpoints,checkpoint_packages=packages,
    native_command_receipts=receipts,complete_posts=posts,formal_reset_cdc_safety='OPEN',physical_signoff=False)
completion.write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value,indent=2))
