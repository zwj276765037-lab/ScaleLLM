"""Execute only the explicit 2026-10-19 AT020 one-time switch authorization."""
from pathlib import Path
import datetime,fcntl,hashlib,json,os,shutil,signal,sys,time
ROOT=Path(__file__).resolve().parents[3];HW=ROOT/'project/hardware';sys.path.insert(0,str(HW/'vivado/scripts'));import run_managed_eda as owned
AT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT020_fresh_core_state_source_semantics';OUT=AT/'evidence/user_authorized_switch_20261019';REPORT=HW/'vivado/reports/m003_E011_R002_AT020_fresh_core_state_source_semantics';AUTH=ROOT/'.research-agent/decision_inputs/M003_AT020_optimized_switch_authorized_20261019.json'
EXPECTED={86002:3111217,86005:3111300,86024:3111303,86095:3111314};GUARD=(137896,5431142)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def dump(name,x):(OUT/name).write_text(json.dumps(x,indent=2)+'\n')
def snapshot_dir(source,target):
 target.mkdir();rows=[]
 for p in sorted(source.iterdir()):
  if p.is_file():
   # Snapshot exactly the observed size; active append may continue until signal.
   n=p.stat().st_size;q=target/p.name
   with p.open('rb') as f,q.open('xb') as g:
    remaining=n
    while remaining:
     b=f.read(min(8*1024*1024,remaining));assert b,'source shortened';g.write(b);remaining-=len(b)
   rows.append(dict(source=str(p),observed_bytes=n,snapshot=identity(q)))
 return rows
assert AUTH.is_file(),'Explicit recorded user authorization required';authorization=json.loads(AUTH.read_text());assert '允许结束本次 AT020' in AUTH.read_text()
table=owned.process_table()
for pid,start in EXPECTED.items():assert table.get(pid,{}).get('start_ticks')==start and table[pid]['pgrp']==86002,f'PID/start/group mismatch {pid}'
assert table.get(GUARD[0],{}).get('start_ticks')==GUARD[1]
OUT.mkdir();dump('authorization_and_before.json',dict(observed_utc=utc(),authorization=identity(AUTH),authorization_content=authorization,owned_before={pid:table[pid] for pid in EXPECTED},guard_before=table[GUARD[0]],original_native_exit_code=None,reason='user_authorized_switch'))
before=snapshot_dir(REPORT,OUT/'report_before_stop');dump('preserved_before_stop.json',before)
tracked=dict(EXPECTED);events=[]
for sig,grace in ((signal.SIGTERM,5),(signal.SIGKILL,0)):
 rows=owned.owned_processes(owned.process_table(),86002,tracked)
 for pid,r in rows.items():
  actual=owned.process_table().get(pid)
  if actual is None:continue
  assert actual['start_ticks']==r['start_ticks'],f'PID reused before signal {pid}'
  os.kill(pid,sig);events.append(dict(utc=utc(),pid=pid,start_ticks=r['start_ticks'],signal=int(sig)))
 dump('signal_events.json',events)
 if rows and grace:time.sleep(grace)
for i in range(20):
 rows=owned.owned_processes(owned.process_table(),86002,tracked)
 if not rows:break
 time.sleep(1)
after=snapshot_dir(REPORT,OUT/'report_after_stop');dump('preserved_after_stop.json',after)
clock=REPORT/'uram_clock_sources.jsonl.partial';raw=clock.read_bytes();complete=raw[:raw.rfind(b'\n')+1];tail=raw[len(complete):]
(OUT/'clock_complete_rows.jsonl').write_bytes(complete);(OUT/'clock_incomplete_tail.raw').write_bytes(tail)
valid=0
for line in complete.splitlines():json.loads(line);valid+=1
for i in range(10):
 if (AT/'evidence/adopted_supervision_v1/lock_released.json').exists():break
 time.sleep(1)
lock=(HW/'vivado/.m002_eda.lock').open('a+')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);released=True;fcntl.flock(lock,fcntl.LOCK_UN)
except BlockingIOError:released=False
lock.close();rows=owned.owned_processes(owned.process_table(),86002,tracked)
receipt=dict(observed_utc=utc(),execution_state='user_authorized_switch_stopped' if not rows and released else 'switch_stop_incomplete',stop_reason='user_authorized_switch',original_native_exit_code=None,original_exit_code_status='UNKNOWN_original_supervisor_missing_foreign_launcher_unreapable',natural_success=False,owned_survivors=rows,tracked_PID_start_identities=tracked,actual_complete_clock_rows=valid,total_clock_bytes=len(raw),incomplete_tail_bytes=len(tail),EDA_lock_released_probe=released,guard_status=identity(AT/'evidence/adopted_supervision_v1/status.json') if (AT/'evidence/adopted_supervision_v1/status.json').exists() else None,no_new_EDA=True,source_inputs_unchanged=True,scope='Preserved full/partial raw artifacts; controlled only authorized exact owned tree; old original job status remains absent')
dump('controlled_switch_stop_receipt.json',receipt);print(json.dumps(receipt));sys.exit(0 if receipt['execution_state']=='user_authorized_switch_stopped' else 1)
