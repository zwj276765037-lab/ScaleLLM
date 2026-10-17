#!/usr/bin/env python3
"""Only an evidence-bound new user exception can signal the exact R004 supervisor."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
from directed_evidence import identity, require, save
from run_directed_attribution import ROOT, PRIOR, CONTRACT, verify_preparation
EXPECTED_PID=1253852
EXPECTED_START=930758582


def proc_identity(pid):
    data=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,start_ticks=int(data[19]),ppid=int(data[1]),pgrp=int(data[2]),state=data[0])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization',type=Path,required=True)
    parser.add_argument('--execute',action='store_true',help='Without this flag, read-only identity/binding preflight only')
    args=parser.parse_args();path=args.authorization.resolve();auth=json.loads(path.read_text())
    verify_preparation()
    require(auth.get('execution_authorized') is True and auth.get('approval_kind')=='user_explicit_controlled_stop','No new explicit user stop authorization')
    require(auth.get('authorized_stop_attempt')==str(PRIOR),'Stop exception is not for the active exact R004 attempt')
    require(auth.get('scope_revision')==identity(CONTRACT),'Stop binding scope changed')
    require(auth.get('prepared_source_manifest')==identity(Path(__file__).with_name('prepared_source_manifest.json')),'Stop binding source changed')
    decision=auth['decision_evidence'];require(identity(decision['path'])==decision,'Actual new user decision evidence changed')
    require(Path(decision['path']).resolve()!=ROOT/'.research-agent/decision_inputs/E006_20261017_user_allowed_readonly_switch.json','Historical R001 stop exception cannot be reused')
    require(not (PRIOR/'status.json').exists(),'R004 already terminal; no stop required')
    started=json.loads((PRIOR/'started.json').read_text())
    require(started['supervisor_pid']==EXPECTED_PID and started['supervisor_start_ticks']==EXPECTED_START,'Registered active owner changed')
    observed=proc_identity(EXPECTED_PID)
    require(observed['start_ticks']==EXPECTED_START and observed['state']!='Z','Exact active supervisor is absent')
    cmd=Path(f'/proc/{EXPECTED_PID}/cmdline').read_bytes().replace(b'\0',b' ').decode()
    require('E006_exact_candidates/run_attribution_lean.py' in cmd and str(PRIOR) in cmd,'Unexpected supervisor command identity')
    intent_path=PRIOR/'authorized_controlled_stop_intent_R005_switch.json'
    signal_path=PRIOR/'authorized_controlled_stop_signal_R005_switch.json'
    require(not intent_path.exists() and not signal_path.exists(),'Never repeat or overwrite a stop signal')
    intent=dict(observed_utc=datetime.now(timezone.utc).isoformat(),authorization=identity(path),decision=decision,
                target=observed,started=identity(PRIOR/'started.json'),supervisor_command=cmd,
                prepared_source_manifest=auth['prepared_source_manifest'],scope_revision=auth['scope_revision'],
                mechanism='pidfd SIGTERM to exact existing supervisor; existing handler owns terminate/reap/144-input/lane closure',
                source=identity(__file__),no_direct_native_signal=True)
    if not args.execute:
        print(json.dumps(dict(preflight=True,signal_sent=False,intent=intent)));return
    fd=os.pidfd_open(EXPECTED_PID,0)
    try:
        require(proc_identity(EXPECTED_PID)['start_ticks']==EXPECTED_START,'Owner identity changed before signal')
        save(intent_path,intent)
        signal.pidfd_send_signal(fd,signal.SIGTERM,None,0)
        save(signal_path,dict(sent_utc=datetime.now(timezone.utc).isoformat(),signal_sent=True,signal='SIGTERM',
                              target_pid=EXPECTED_PID,target_start_ticks=EXPECTED_START,intent=identity(intent_path),authorization=identity(path),decision=decision))
    finally:os.close(fd)
    print(json.dumps(dict(signal_sent=True,receipt=str(signal_path),closure='PENDING_ACTUAL_SUPERVISOR_TERMINAL')))

if __name__=='__main__':main()
