#!/usr/bin/env python3
"""Read-only native evidence checks and one new terminal facts artifact; no EDA."""
from pathlib import Path
import datetime as dt
import json
import os
import sys
import zipfile
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
sys.path.insert(0,str(ROOT/'project/hardware/vivado/scripts'))
import m002_physical_evidence as m
attempt=Path(sys.argv[1]).resolve();target=attempt/'terminal_facts.json'
assert not target.exists(),'terminal evidence must never be overwritten'
status=json.loads((attempt/'status.json').read_text());report=Path(status['report']);assert status['execution_state']=='completed'
samples=[json.loads(x) for x in (attempt/'resources.jsonl').read_text().splitlines()]
combined={'samples':len(samples),'sampled_peak_tree_rss_bytes':max(x['rss_bytes'] for x in samples),'minimum_mem_available_bytes':min(x['mem_available_bytes'] for x in samples),'minimum_disk_free_bytes':min(x['disk_free_bytes'] for x in samples)}
assert combined['sampled_peak_tree_rss_bytes']==status['max_tree_rss_bytes']
assert combined['minimum_mem_available_bytes']==status['minimum_mem_available_bytes']
assert combined['minimum_disk_free_bytes']==status['minimum_disk_free_bytes']
processes={}
for pid,ticks in status['tracked_identities'].items():
 p=Path('/proc')/pid/'stat';current=None
 if p.exists():
  raw=p.read_text();f=raw[raw.rindex(')')+2:].split();current=int(f[19])
 processes[pid]={'expected_start_ticks':ticks,'current_start_ticks':current,'original_identity_present':current==ticks}
assert not any(x['original_identity_present'] for x in processes.values()) and not status['owned_survivors']
value={'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'collector_source':m.file_id(Path(__file__)),'attempt_status':m.file_id(attempt/'status.json'),'worker_launcher':m.file_id(report/'launcher_status.txt'),'native_Vivado_scope':m.key_values(report/'launcher_status.txt'),'stop_reason':status['stop_reason'],'supervision_profile':status['supervision_profile'],'wall_clock_stop_disabled':status['wall_clock_stop_disabled'],'resources':m.file_id(attempt/'resources.jsonl'),'independently_recomputed_resources':combined,'tracked_PID_identities':processes,'owned_survivors':status['owned_survivors'],'formal_reset_cdc_safety':'OPEN'}
if status['exit_code']==0:
 evidence=json.loads((report/'diagnostic_evidence.json').read_text());point='physopt' if status['stage']=='place' else 'route';dcp=report/(point+'.dcp');before=dcp.stat()
 prior=attempt/(point+'_checkpoint_facts.json');crc_source=None
 if prior.exists():
  checked=json.loads(prior.read_text());assert checked['checkpoint']==m.file_id(dcp) and checked['all_ZIP_member_CRC']=='PASS'
  members=checked['zip_members'];package=checked['package'];crc_source=m.file_id(prior)
 else:
  with zipfile.ZipFile(dcp) as archive:
   assert archive.testzip() is None;members=len(archive.namelist())
  package=m.checkpoint_package(dcp)
 after=dcp.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
 value['checkpoint_CRC_reuse_source']=crc_source
 value.update(execution='COMPLETED',diagnostic_evidence=m.file_id(report/'diagnostic_evidence.json'),checkpoint=m.file_id(dcp),checkpoint_all_member_CRC='PASS',checkpoint_ZIP_members=members,checkpoint_package=package,metrics=evidence['metrics_ns'],timing_verdict=evidence['timing_summary_verdict'],route_counts=evidence['route'],command_receipts=evidence['command_receipts'],historical_command_receipts=evidence.get('historical_command_receipts',{}),scope='actual completed physical stage and full POST; no timing/CDC/board signoff inferred')
else:
 value.update(execution='FAILED',scope='actual terminal stage failure; available DCP/native command/failure scope must be inspected separately')
target.write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'terminal_facts':m.file_id(target),'execution':value['execution'],'resources':combined,'metrics':value.get('metrics'),'route_counts':value.get('route_counts')},indent=2))
