#!/usr/bin/env python3
"""CPU-only parse/control/reuse checks; never starts or signals EDA."""
import ast
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from directed_evidence import identity,save,qualify_membership
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='CT002_final_control_membership.json');args=parser.parse_args()
    out=HERE/'CPU_checks';out.mkdir(exist_ok=True)
    assert Path(args.output).name==args.output
    target=out/args.output;assert not target.exists()
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    checks={};sources=[]
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_text(),filename=str(path));sources.append(identity(path))
    checks['all_current_python_AST']=True
    tcl_paths=sorted(HERE.glob('*.tcl'))
    script='foreach path $argv {set h [open $path];set source [read $h];close $h;if {![info complete $source]} {error "Incomplete Tcl: $path"};puts $path}'
    result=subprocess.run(['tclsh','/dev/stdin',*[str(p) for p in tcl_paths]],input=script,text=True,capture_output=True)
    assert result.returncode==0,(result.stdout,result.stderr);checks['all_current_Tcl_info_complete']=True
    old=(ROOT/'agent/A006/E006_exact_candidates/run_attribution_lean.py').read_text();new=(HERE/'run_directed_attribution.py').read_text()
    mark='    proc=None;tracked={};stop=None;peak=0;low_since=None'
    assert old[old.index(mark):]==new[new.index(mark):];checks['actual_process_resource_integrity_tail_exact_R004']=True
    facts={}
    report=ROOT/'project/hardware/vivado/reports/m002_E006_R004_AT001_exact_candidate_comparison'
    with tempfile.TemporaryDirectory(prefix='R005_CPU_membership_') as temporary:
        work=Path(temporary)
        for point in ['C01','C02']:
            for tag in ['RAW','S','P','membership','physical_members','site_members']:
                path=report/f'candidate_{tag}_{point}.tsv';text=path.read_text()
                if tag in ['membership','physical_members','site_members']:
                    lines=text.splitlines();width=len(lines[0].split('\t'));values=[line.split(' ') for line in lines[1:]]
                    assert all(len(row)==width for row in values);text=lines[0]+'\n'+'\n'.join('\t'.join(row) for row in values)+'\n'
                (work/path.name).write_text(text)
            path=report/f'candidate_membership_{point}_closed.txt';shutil.copy2(path,work/path.name)
            result=qualify_membership(point,work)
            facts[point]={tag:result['current'][tag]['count'] for tag in ['RAW','S','P']}
            produced=work/f'candidate_membership_qualification_{point}.json';before=identity(produced)
            try:qualify_membership(point,work)
            except ValueError as error:assert 'overwrite' in str(error)
            else:raise AssertionError('Overwrite accepted')
            assert identity(produced)==before
            produced.unlink()
            p=work/f'candidate_P_{point}.tsv';text=p.read_text();p.write_text(text.replace('\t','\tINVALID_REF_',1))
            try:qualify_membership(point,work)
            except ValueError:pass
            else:raise AssertionError('Changed physical identity accepted')
        checks['both_actual_closed_R004_membership_ledgers_match']=True
        checks['duplicate_output_rejected_before_overwrite']=True
        checks['changed_P_identity_rejected']=True
    reuse=json.loads((HERE/'reuse_manifest.json').read_text())
    assert all('all_primitive_locations.tsv' not in row['path'] for row in reuse['artifacts'].values())
    assert all(identity(row['path'])==row for row in reuse['artifacts'].values());checks['all_narrow_reuse_actual_identities']=True
    checks['no_full_primitive_scan_or_binding']=True
    assert len(reuse['candidates'])==2
    save(target,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution='CPU_checks_completed',EDA_executed=False,
        native_class_or_design_qualification=False,checks=checks,closed_membership_counts=facts,
        actual_CPU_affinity=sorted(os.sched_getaffinity(0)),actual_nice=os.getpriority(os.PRIO_PROCESS,0),
        source_files=sources+[identity(p) for p in tcl_paths],reuse_manifest=identity(HERE/'reuse_manifest.json'),producer=identity(__file__),
        limitations=['Transformed CPU fixture uses corrected delimiters while original R004 bytes remain unchanged',
                     'Closed R004 memberships used as CPU fixtures; this is not fresh native R005 membership qualification',
                     'Tcl info complete is syntax completeness, not native command qualification',
                     'No EDA launch, lock control, stop or signal performed']))
    print(json.dumps(identity(target)))

if __name__=='__main__':main()
