"""Close actual terminal facts and version identities; never kills or starts a process."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json
p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True);p.add_argument('--job',required=True);p.add_argument('--cause',required=True);a=p.parse_args();root=Path.cwd();at=a.attempt.resolve();assert at.is_relative_to(root/'project/E011_m003_joint_routability_implementation/experiment_results/runs');ev=at/'evidence';job=ev/'jobs'/a.job;state=json.loads((job/'status.json').read_text());assert state['execution_state'] in ['failed','completed'] and state['stop_reason'] is None and state['owned_survivors']=={} and state['core_RTL_unchanged_during_job'] is True

def ident(p):
 p=Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def ticks(pid):
 try:return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
active=json.loads((ev/'actual_native_activation.json').read_text()) if (ev/'actual_native_activation.json').exists() else None;launch=json.loads((ev/'detached_owned_supervisor_launch.json').read_text());expected={int(p):s for p,s in state['tracked_PID_start_identities'].items()};expected[launch['supervisor_pid']]=launch['start_ticks'];wait=ev/'continuous_terminal_waiter_started.json'
if wait.exists():
 w=json.loads(wait.read_text());expected[w['pid']]=w['start_ticks']
processes=[dict(pid=p,expected_start=s,actual_start=ticks(p),expected_alive=ticks(p)==s) for p,s in expected.items()];assert not any(p['expected_alive'] for p in processes)
with (root/'project/hardware/vivado/.m002_eda.lock').open('a+') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN)
archive=json.loads((job/'source_archive.json').read_text())['bindings'];checks=[dict(path=r['original']['path'],current_matches=ident(r['original']['path'])==r['original'],archive_matches=ident(r['preserved']['path'])==r['preserved']) for r in archive];assert all(r['current_matches'] and r['archive_matches'] for r in checks)
receipt=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=ident(job/'status.json'),terminal=state,processes=processes,lock_free=True,archive_bindings=len(checks),source_checks=checks,cause=a.cause,original_result_preserved=True,actual_native_activation_recorded=active is not None)
with (ev/'owner_terminal_and_source_closure.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
run=at/'run.json';prior=json.loads(run.read_text())
with (ev/'run_before_terminal_reconciliation.json').open('x') as f:json.dump(prior,f,indent=2);f.write('\n')
prior.update(execution_state=state['execution_state'],finished_at=state['ended_utc'],exit_status=state['native_exit_code'],terminal_cause=a.cause);prior.setdefault('evidence',[]).append(str((ev/'owner_terminal_and_source_closure.json').relative_to(root)));run.write_text(json.dumps(prior,indent=2)+'\n');print(json.dumps(dict(state=state['execution_state'],native=state['native_exit_code'],archive_bindings=len(checks),exited=len(processes),lock_free=True)))
