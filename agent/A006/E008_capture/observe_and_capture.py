#!/usr/bin/env python3
"""Observe one actually started E008; capture closed stages, never control EDA."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();at=args.attempt.resolve();report=args.report.resolve()
    assert at.parent==ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts'
    assert (at/'started.json').is_file()
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    outcomes={};last=0
    with (at/'automatic_stage_capture_observations.jsonl').open('x',buffering=1) as journal:
        while True:
            for point in ['pre_place','place','physopt','route','route_failed']:
                tag=point+'_native_index';closed=report/f'candidate_top_port_index_closed_{point}.json'
                if tag not in outcomes and closed.is_file():
                    try:qualified=json.loads(closed.read_text()).get('qualified') is True
                    except (OSError,ValueError):qualified=False
                    if qualified:
                        command=[sys.executable,str(ROOT/'agent/A006/E008_capture/capture_index.py'),point,'--attempt',str(at),'--report',str(report)]
                        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
                        event=dict(observed_utc=datetime.now(timezone.utc).isoformat(),stage=tag,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
                        journal.write(json.dumps(event)+'\n');print(json.dumps(event),flush=True);outcomes[tag]=result.returncode
            for phase in ['place','physopt','route']:
                if phase not in outcomes and (report/f'candidate_phase_{phase}_status.txt').is_file():
                    command=[sys.executable,str(ROOT/'agent/A006/E008_capture/capture_phase.py'),'--stage',phase,'--attempt',str(at),'--report',str(report)]
                    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
                    event=dict(observed_utc=datetime.now(timezone.utc).isoformat(),stage=phase,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
                    journal.write(json.dumps(event)+'\n');print(json.dumps(event),flush=True);outcomes[phase]=result.returncode
            if time.monotonic()-last>=60 or (at/'status.json').is_file():
                print(json.dumps(dict(observed_utc=datetime.now(timezone.utc).isoformat(),passive=True,captured=outcomes,supervisor_terminal=(at/'status.json').is_file())),flush=True);last=time.monotonic()
            if (at/'status.json').is_file():break
            time.sleep(5)


if __name__=='__main__':main()
