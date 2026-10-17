#!/usr/bin/env python3
"""CPU-only R005 control/guard skeleton; no exporter admission or EDA launch."""
from pathlib import Path
import ast
import hashlib
import json
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=HERE.parent/'E006_exact_candidates'


def main():
    assert not (HERE/'run_directed_attribution.py').exists()
    old=(BASE/'run_attribution_lean.py').read_text()
    tail=old[old.index('    proc=None;tracked={};stop=None;peak=0;low_since=None'):]
    prefix='''#!/usr/bin/env python3
"""Prepared R005 directed candidate comparison. No queued or automatic launch."""
from pathlib import Path
import argparse
import datetime as dt
import csv
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SCRIPTS=ROOT/'project/hardware/vivado/scripts'
sys.path.insert(0,str(ROOT/'agent/A006/E006_lean_candidate'))
from run_attribution_lean import identity,freeze_check,prior_registered_identities,require_registered_closed,require,utc,save
sys.path.insert(0,str(SCRIPTS))
import run_m002_no_wall as guard
CONTRACT=ROOT/'mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md'
PARENT=ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt'
PRIOR=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/attempts/AT001_exact_candidate_comparison'
E006=ROOT/'project/E006_m002_slr1_congestion_attribution'


def interrupted(signum,frame):raise KeyboardInterrupt(f'signal {signum}')


def require_fresh_or_planned_attempt(attempt,report):
    require(not report.exists(),'Report already contains evidence')
    if not attempt.exists():return None
    import re
    match=re.fullmatch(r'(AT[0-9]{3})_(.+)',attempt.name)
    require(match and attempt.is_dir() and not attempt.is_symlink(),'Invalid planned attempt')
    require({p.name for p in attempt.iterdir()}=={'run.json','report.md','evidence'},'Attempt already contains runtime products')
    for name in ['run.json','report.md']:
        require((attempt/name).is_file() and not (attempt/name).is_symlink(),'Invalid planned metadata')
    require((attempt/'evidence').is_dir() and not (attempt/'evidence').is_symlink() and not any((attempt/'evidence').iterdir()),'Planned evidence is not empty')
    expected=dict(execution_state='planned',schema=1,id=match[1],experiment='E006',run='R005',title=match[2])
    require(json.loads((attempt/'run.json').read_text())==expected,'Wrong planned R005 metadata')
    require((attempt/'report.md').read_text()=='# '+match[1]+' · '+match[2]+'\\n\\n记录目的、实际结果、适用范围、限制及原始证据。登记不代表已执行或通过。\\n','Planned report changed')
    return dict(run=identity(attempt/'run.json'),report=identity(attempt/'report.md'),evidence_empty=True)


def verify_external_inputs(expected):
    actual={key:identity(row['path']) for key,row in expected.items()}
    require(actual==expected,'External directed scope/protocol/target/evidence changed')
    return actual


def verify_preparation():
    path=HERE/'prepared_source_manifest.json'
    require(path.is_file(),'Directed source/protocol has not been admitted')
    manifest=json.loads(path.read_text())
    require(manifest.get('status')=='CPU_PREPARED_NOT_EXECUTED' and manifest.get('EDA_executed') is False,'Not an unexecuted preparation manifest')
    require(manifest.get('exporter_protocol_complete') is True,'Directed exporter protocol/source incomplete')
    for row in manifest['source_files']+manifest['CPU_checks']:
        require(identity(row['path'])==row,'Prepared source/check changed')
    verify_external_inputs(manifest['external_inputs'])
    require(manifest['scope_revision']==identity(CONTRACT),'Wrong actual scope revision')
    return manifest


def actual_prior_closure(authorization):
    row=authorization['prior_terminal_status'];require(identity(row['path'])==row and Path(row['path'])==PRIOR/'status.json','Wrong actual R004 terminal')
    status=json.loads(Path(row['path']).read_text());started=json.loads((PRIOR/'started.json').read_text())
    require(status.get('execution_state')=='completed' and not status.get('owned_survivors'),'R004 has not actually closed')
    require_registered_closed(prior_registered_identities(status,started))
    facts_row=authorization['prior_terminal_facts'];require(identity(facts_row['path'])==facts_row,'Prior terminal audit changed')
    facts=json.loads(Path(facts_row['path']).read_text());require(facts['status']==row,'Prior audit does not bind actual terminal')
    closure_checks=['no_survivors','no_original_live','lane_released','production_144_unchanged','source_physopt_DCP_unchanged',
        'archived_8_sources_unchanged','all_bound_external_targets_sources_unchanged','all_bound_reused_closed_inputs_unchanged',
        'replacement_authorization_unchanged','contract_unchanged','resource_helper_unchanged','no_post_integrity_error',
        'wrapper_after_freeze_agrees','no_physical_commands','no_checkpoint_write','resource_extrema_agree']
    require(all(facts['checks'].get(key) is True for key in closure_checks),'Prior R004 ownership/integrity closure is incomplete')
    if status['stop_reason'] is None:
        require(status['native_natural_terminal_observed'],'R004 natural terminal not observed')
    else:
        stop_row=authorization.get('controlled_stop_evidence')
        require(stop_row and identity(stop_row['path'])==stop_row,'A new explicit R004 user stop exception is required')
        stop=json.loads(Path(stop_row['path']).read_text())
        require(stop.get('approval_kind')=='user_explicit_controlled_stop' and stop.get('authorized_stop_attempt')==str(PRIOR),
                'This stop is not explicitly authorized for the current R004 attempt')
    # All real previous E006 owners must have gone, including historical R001.
    for path in sorted((E006/'experiment_results/runs').glob('R*/attempts/AT*/started.json')):
        terminal=path.parent/'status.json';require(terminal.is_file(),'A previous E006 owner is unclosed')
        ended=json.loads(terminal.read_text());require(ended.get('execution_state')=='completed' and not ended.get('owned_survivors'),'Prior E006 owns processes')
        require_registered_closed(prior_registered_identities(ended,json.loads(path.read_text())))
    return dict(status=row,facts=facts_row)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--authorization',type=Path,required=True)
    args=parser.parse_args();attempt=args.attempt.resolve();report=args.report.resolve();authorization_path=args.authorization.resolve()
    require(attempt.parent==E006/'experiment_results/runs/R005/attempts','Wrong R005 attempt root')
    require(report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E006_R005_'),'Wrong R005 report root')
    planned_scaffold=require_fresh_or_planned_attempt(attempt,report)
    manifest=verify_preparation()
    authorization=json.loads(authorization_path.read_text())
    require(authorization.get('execution_authorized') is True and authorization.get('decision')=='readonly_two_candidate_directed_cut','No actual R005 directed execution binding')
    require(authorization.get('scope_revision')==identity(CONTRACT),'Execution binding does not adopt actual scope revision')
    require(authorization.get('prepared_source_manifest')==identity(HERE/'prepared_source_manifest.json'),'Wrong actual source binding')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    # Nonblocking: never queue behind or control R004.
    lock=(ROOT/'project/hardware/vivado/.m002_eda.lock').open('r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    prior_closure=actual_prior_closure(authorization)
    before_freeze=freeze_check();checkpoint=identity(PARENT/'physopt.dcp')
    require(checkpoint['sha256']=='766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d','Wrong source physopt graph')
    checkpoints={'physopt':checkpoint}
    reuse=json.loads((HERE/'reuse_manifest.json').read_text());reused_inputs=reuse['artifacts']
    verify_external_inputs(reused_inputs)
    external_inputs=dict(manifest['external_inputs'])
    for key,row in authorization.items():
        if isinstance(row,dict) and {'path','bytes','sha256'}.issubset(row):external_inputs['execution_binding_'+key]=row
    verify_external_inputs(external_inputs)
    require(guard.mem_available()>=48*guard.GIB and shutil.disk_usage(ROOT).free>=30*guard.GIB,'Resource reserve unavailable')
    planned_scaffold=require_fresh_or_planned_attempt(attempt,report)
    attempt.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True);archive=attempt/'sources';archive.mkdir()
    for name in manifest['runtime_source_names']:shutil.copy2(HERE/name,archive/name)
    source_bindings=[identity(p) for p in sorted(archive.iterdir())]
    inputs=dict(contract=identity(CONTRACT),checkpoint=checkpoint,checkpoints=checkpoints,planned_management_scaffold=planned_scaffold,
        prior_R004_closure=prior_closure,external_inputs=external_inputs,reused_closed_inputs=reused_inputs,
        replacement_authorization=identity(authorization_path),preparation_manifest=identity(HERE/'prepared_source_manifest.json'),
        frozen_inputs=before_freeze,sources=source_bindings,resource_helper=identity(SCRIPTS/'run_m002_no_wall.py'))
    save(attempt/'input_bindings.json',inputs)
    cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace',
        '-source',str(archive/'attribution_directed.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou')]
    env={k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E005_SUPPLEMENT_','E006_','DIRECTED_'))}
    env.update(E006_DCP=str(checkpoint['path']),E006_OUT=str(report),E006_TARGETS=str(archive/'targets.tcl'),
        E006_CANDIDATE_ADAPTER=str(archive/'directed_evidence.py'),DIRECTED_REUSE=str(archive/'reuse_manifest.json'),
        OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    supervisor_start=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    metadata=dict(stage='readonly_candidate_directed_cut',started_utc=utc(),supervisor_pid=os.getpid(),supervisor_start_ticks=supervisor_start,
        argv=cmd,cwd=str(report),report=str(report),project=str(ROOT/'project/hardware/vivado/project/m002_E005_R002_AT006_fresh'),
        cpu_affinity=list(range(8)),nice=5,max_threads=8,timeout_seconds=None,no_output_timeout_seconds=None,
        wall_clock_stop_disabled=True,rss_limit_bytes=192*guard.GIB,mem_available_floor_bytes=48*guard.GIB,
        mem_low_grace_seconds=30,disk_free_floor_bytes=30*guard.GIB,inputs=identity(attempt/'input_bindings.json'),
        environment={k:v for k,v in env.items() if k.startswith(('E006_','DIRECTED_'))})
    save(attempt/'command.json',metadata)
'''
    (HERE/'run_directed_attribution.py').write_text(prefix+tail)
    # The native lifetime/resource/post-integrity tail is byte-for-byte retained.
    assert (HERE/'run_directed_attribution.py').read_text().split('    proc=None;tracked={};stop=None;peak=0;low_since=None',1)[1]==old.split('    proc=None;tracked={};stop=None;peak=0;low_since=None',1)[1]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    print('R005 guarded skeleton written; final manifest/exporter/protocol/launch authorization absent')


if __name__=='__main__':main()
