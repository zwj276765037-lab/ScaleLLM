#!/usr/bin/env python3
"""Passive single-attempt stage capturer; never launches or controls EDA."""
import argparse
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--attempt',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve()
    assert attempt.parent==ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/attempts'
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    outcomes={};last_summary=0
    with (attempt/'automatic_stage_capture_observations.jsonl').open('x',buffering=1) as journal:
        while True:
            receipt=report/'stage_receipts.tsv'
            records=[]
            if receipt.is_file():
                with receipt.open() as stream:records=list(csv.DictReader(stream,delimiter='\t'))
            for point in ['C01','C02']:
                index_stage='candidate_'+point+'_native_port_index'
                index_receipt=report/('candidate_top_port_index_closed_'+point+'.json')
                if index_receipt.is_file() and index_stage not in outcomes:
                    try:closed_index=json.loads(index_receipt.read_text())
                    except (ValueError,OSError):closed_index=None
                    if closed_index and closed_index.get('qualified') is True:
                        result=subprocess.run(['/usr/bin/python3',str(ROOT/'agent/A006/top_port_index_capture/capture_index.py'),point,'--attempt',str(attempt),'--report',str(report)],cwd=ROOT,capture_output=True,text=True)
                        event=dict(observed_utc=datetime.now(timezone.utc).isoformat(),stage=index_stage,capture_returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
                        journal.write(json.dumps(event)+'\n');print(json.dumps(event),flush=True);outcomes[index_stage]=result.returncode
                for phase,suffix in [('membership','membership_qualification'),('cut','directed_cut'),('timing','bounded_timing')]:
                    stage='candidate_'+point+'_'+suffix
                    if stage in outcomes or not any(row.get('stage')==stage for row in records):continue
                    if (attempt/(stage+'_closed_facts.json')).is_file():outcomes[stage]='ALREADY_CAPTURED';continue
                    command=['/usr/bin/python3',str(ROOT/'agent/A006/top_port_index_capture/capture_stage.py'),point,phase,'--attempt',str(attempt),'--report',str(report)]
                    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
                    event=dict(observed_utc=datetime.now(timezone.utc).isoformat(),stage=stage,capture_returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
                    journal.write(json.dumps(event)+'\n');print(json.dumps(event),flush=True);outcomes[stage]=result.returncode
            if time.monotonic()-last_summary>=60:
                print(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),passive_capture=True,closed_stages=[r.get('stage') for r in records],captured=outcomes)),flush=True);last_summary=time.monotonic()
            if (attempt/'status.json').is_file():
                print(json.dumps(dict(actual_supervisor_status_observed=True,terminal_audit_still_required=True,captured=outcomes)),flush=True);break
            time.sleep(5)

if __name__=='__main__':main()
