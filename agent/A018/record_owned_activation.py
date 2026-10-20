"""One bounded observation of an existing owned job; no launch, polling or process control."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,sys
p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True);p.add_argument('--job',required=True);a=p.parse_args();root=Path.cwd();hw=root/'project/hardware';at=a.attempt.resolve();assert at.is_relative_to(root/'project/E011_m003_joint_routability_implementation/experiment_results/runs');ev=at/'evidence';job=ev/'jobs'/a.job
if (job/'status.json').exists():print((job/'status.json').read_text());sys.exit(2)
s=json.loads((job/'started.json').read_text())
def ident(p):
 p=Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def proc(pid):
 p=Path(f'/proc/{pid}');t=p.joinpath('stat').read_text().rsplit(')',1)[1].split();return dict(pid=int(pid),start_ticks=int(t[19]),command=p.joinpath('cmdline').read_text().replace('\0',' '),CPU_affinity=sorted(os.sched_getaffinity(int(pid))),nice=os.getpriority(os.PRIO_PROCESS,int(pid)))
with (job/'resources.jsonl').open('rb') as f:f.seek(max(0,(job/'resources.jsonl').stat().st_size-32000));sample=json.loads(f.read().splitlines()[-1])
rows=[proc(pid) for pid in sample['processes']];native=[r for r in rows if '/bin/unwrapped/' in r['command'] and 'vivado ' in r['command']];assert len(native)==1;supervisor=proc(s['supervisor_pid']);launch=json.loads((ev/'detached_owned_supervisor_launch.json').read_text());assert supervisor['start_ticks']==launch['start_ticks'];assert native[0]['CPU_affinity']==list(range(8)) and native[0]['nice']==5
assert s['rss_limit_bytes']==192*1024**3 and s['mem_available_floor_bytes']==48*1024**3 and s['mem_low_grace_seconds']==30 and s['disk_floor_bytes']==30*1024**3 and s['timeout_seconds'] is None and s['no_output_timeout_seconds'] is None
lockpath=hw/'vivado/.m002_eda.lock';ino=lockpath.stat().st_ino
with lockpath.open('a+') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:held=True
 else:held=False;fcntl.flock(lock,fcntl.LOCK_UN)
locks=[line for line in Path('/proc/locks').read_text().splitlines() if f':{ino} ' in line];assert held and any(line.split()[4]==str(supervisor['pid']) for line in locks)
archive=json.loads((job/'source_archive.json').read_text())['bindings'];checks=[dict(path=r['original']['path'],current_matches=ident(r['original']['path'])==r['original'],archive_matches=ident(r['preserved']['path'])==r['preserved']) for r in archive];assert all(r['current_matches'] and r['archive_matches'] for r in checks)
sys.path.insert(0,str(hw/'vivado/scripts'));import m003_entry;core=m003_entry.check_sources()['sources'];actual=[s['command'][i+1] for i,x in enumerate(s['command'][:-1]) if x=='--archive-source'];assert len(actual)==len(set(actual));assert not actual or {r['path'] for r in core}<=set(actual)
receipt=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution_state='running',started=ident(job/'started.json'),supervisor=supervisor,native=native[0],processes=rows,EDA_lock_held=True,EDA_lock_record=locks,source_archive=ident(job/'source_archive.json'),archive_bindings=len(checks),all_current_and_archived_inputs_match=True,runtime_sources=len(actual) if actual else len(core),frozen_core_sources=len(core),resource_sample=sample,limits={k:s[k] for k in ['cpu_affinity','nice','rss_limit_bytes','mem_available_floor_bytes','mem_low_grace_seconds','disk_floor_bytes','timeout_seconds','no_output_timeout_seconds']},continuous_event_wait_next=True)
with (ev/'actual_native_activation.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
r=json.loads((at/'run.json').read_text());r.update(execution_state='running',started_at=s['started_utc']);r.setdefault('evidence',[]).extend(str(q.relative_to(root)) for q in [ev/'actual_native_activation.json',job/'started.json']);(at/'run.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(AT=r['id'],started_utc=s['started_utc'],supervisor=supervisor['pid'],supervisor_start=supervisor['start_ticks'],native=native[0]['pid'],native_start=native[0]['start_ticks'],archive_bindings=len(checks),runtime_sources=receipt['runtime_sources'],lock_held=True)))
