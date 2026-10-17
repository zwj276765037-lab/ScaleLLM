#!/usr/bin/env python3
"""Detach a single actually-authorized R005; never queue or stop an older owner."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import time
import run_directed_attribution as runner
from directed_evidence import identity,save

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['attempt','report','authorization']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve();auth=args.authorization.resolve()
    assert attempt.parent==runner.E006/'experiment_results/runs/R005/attempts'
    assert report.parent==runner.ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E006_R005_')
    runner.require_fresh_or_planned_attempt(attempt,report);runner.verify_preparation()
    decision=json.loads(auth.read_text())
    assert decision.get('execution_authorized') is True and decision.get('decision')=='readonly_two_candidate_directed_cut'
    assert decision['scope_revision']==identity(runner.CONTRACT) and decision['prepared_source_manifest']==identity(runner.HERE/'prepared_source_manifest.json')
    # Fail now if occupied; the supervisor independently takes the same nonblocking lock.
    with (runner.ROOT/'project/hardware/vivado/.m002_eda.lock').open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);runner.actual_prior_closure(decision);fcntl.flock(lock,fcntl.LOCK_UN)
    tag='E006_R005_'+attempt.name
    log=runner.ROOT/'agent/A006'/(tag+'_supervisor.log')
    receipt=runner.ROOT/'agent/A006'/('detached_'+tag+'.json')
    assert not receipt.exists() and not log.exists(),'Never overwrite launch evidence'
    argv=['taskset','-c','0-7','nice','-n','5','/usr/bin/python3',str(runner.HERE/'run_directed_attribution.py'),
          '--attempt',str(attempt),'--report',str(report),'--authorization',str(auth)]
    with log.open('xb') as stream:
        child=subprocess.Popen(argv,cwd=runner.ROOT,start_new_session=True,close_fds=True,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
    time.sleep(0.3)
    try:
        fields=Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()
        owner=dict(pid=child.pid,start_ticks=int(fields[19]),ppid=int(fields[1]),pgrp=int(fields[2]),nice=int(fields[16]))
    except FileNotFoundError:owner=None
    value=dict(launched_utc=datetime.now(timezone.utc).isoformat(),argv=argv,cwd=str(runner.ROOT),attempt=str(attempt),report=str(report),
               supervisor_pid=child.pid,supervisor_proc_identity=owner,poll=child.poll(),stdio_log=str(log),source=identity(__file__),
               execution_authorization=identity(auth),limitation='Launch receipt only; actual native start, unique lane and closure must be independently verified')
    save(receipt,value);print(json.dumps(dict(receipt=str(receipt),**value)))

if __name__=='__main__':main()
