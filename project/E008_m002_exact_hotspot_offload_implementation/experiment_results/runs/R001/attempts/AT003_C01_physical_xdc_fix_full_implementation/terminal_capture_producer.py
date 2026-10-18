#!/usr/bin/env python3
"""Audit actually-ended E008 ownership/input/resource/physical evidence; read-only."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'agent/A006/directed_candidate_cut'))
from directed_evidence import identity,save,require
sys.path.insert(0,str(ROOT/'project/hardware/vivado/scripts'))
import m002_physical_evidence as e


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--attempt',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();at=args.attempt.resolve();report=args.report.resolve()
    require(at.parent==ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts','Wrong E008 attempt')
    require(report.parent==ROOT/'project/hardware/vivado/reports' and report.name.startswith('m002_E008_R001_'),'Wrong E008 report')
    target=at/'terminal_facts.json';summary=at/'terminal_summary.json';producer=at/'terminal_capture_producer.py'
    require(not any(path.exists() for path in [target,summary,producer]),'Never overwrite terminal audit or producer')
    status=json.loads((at/'status.json').read_text());require(status['execution_state']=='completed' and status['ended_utc'],'Supervisor is not terminal')
    started=json.loads((at/'started.json').read_text());inputs_id=identity(at/'input_bindings.json');require(status['inputs']==started['inputs']==inputs_id,'Actual startup/input binding changed')
    inputs=json.loads((at/'input_bindings.json').read_text());registered={int(pid):tick for pid,tick in status['tracked_identities'].items()}
    for role in ['supervisor','leader']:
        if role+'_start_ticks' in started:registered[started[role+'_pid']]=started[role+'_start_ticks']
    processes=[]
    for pid,tick in sorted(registered.items()):
        row=dict(pid=pid,expected_start_ticks=tick,original_identity_live=False)
        try:
            fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();row.update(current_start_ticks=int(fields[19]),state=fields[0])
            row['original_identity_live']=int(fields[19])==tick and fields[0]!='Z'
        except FileNotFoundError:pass
        processes.append(row)
    require(not any(row['original_identity_live'] for row in processes),'Original E008 owner still lives')
    lane=dict(path=str(ROOT/'project/hardware/vivado/.m002_eda.lock'),free=False)
    with Path(lane['path']).open('r') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:lane['free']=True;fcntl.flock(stream,fcntl.LOCK_UN)
    freeze=inputs['frozen_inputs']['freeze'];require(identity(freeze['path'])==freeze,'Production freeze changed')
    frozen=json.loads(Path(freeze['path']).read_text())['files'];mismatches=[]
    for row in frozen:
        actual=identity(row['path'])
        if actual!=row:mismatches.append(dict(expected=row,actual=actual))
    manifest=json.loads(Path(inputs['preparation_manifest']['path']).read_text());manifest_ok=identity(inputs['preparation_manifest']['path'])==inputs['preparation_manifest']
    source_mismatches=[]
    for row in manifest['own_sources']+manifest['reused_sources']+manifest['CPU_checks']+manifest.get('documentation',[]):
        actual=identity(row['path'])
        if actual!=row:source_mismatches.append(dict(expected=row,actual=actual))
    stage_manifest=report/'stage_inputs.sha256';stage_identity=identity(stage_manifest);stage_error=None
    try:e.input_manifest(stage_manifest)
    except Exception as error:stage_error=repr(error)
    attr=inputs['attribution'];closeout_path=Path(attr['closeout']['path']);closeout=json.loads(closeout_path.read_text());dependency_mismatches=[]
    for row in [attr['closeout'],*attr['terminal_statuses'],closeout['terminal_status'],*closeout['evidence']]:
        actual=identity(row['path'])
        if actual!=row:dependency_mismatches.append(dict(expected=row,actual=actual))
    peak=0;minimum_mem=None;minimum_disk=None;samples=0;first=None;last=None;max_gap=0
    with (at/'resources.jsonl').open() as stream:
        for line in stream:
            row=json.loads(line);samples+=1
            if first is None:first=row['utc']
            if last:max_gap=max(max_gap,(datetime.fromisoformat(row['utc'])-datetime.fromisoformat(last)).total_seconds())
            last=row['utc'];peak=max(peak,row['rss_bytes'])
            minimum_mem=row['mem_available_bytes'] if minimum_mem is None else min(minimum_mem,row['mem_available_bytes'])
            minimum_disk=row['disk_free_bytes'] if minimum_disk is None else min(minimum_disk,row['disk_free_bytes'])
    phases={}
    for phase in ['place','physopt','route']:
        receipt=report/f'candidate_phase_{phase}_status.txt'
        if receipt.is_file():
            phases[phase]=dict(native_receipt=e.key_values(receipt),receipt=identity(receipt),
                independently_captured_stage=identity(at/f'{phase}_closed_stage_facts.json') if (at/f'{phase}_closed_stage_facts.json').is_file() else None)
    physical_path=report/'E008_physical_evidence.json';physical=json.loads(physical_path.read_text()) if physical_path.is_file() else None
    checks=dict(no_survivors=not status['owned_survivors'],no_original_live=not any(row['original_identity_live'] for row in processes),lane_released=lane['free'],
        production_144_unchanged=len(frozen)==144 and not mismatches,wrapper_after_freeze_agrees=status['frozen_inputs_after']==inputs['frozen_inputs'],
        preparation_manifest_unchanged=manifest_ok,all_bound_source_CPU_and_docs_unchanged=not source_mismatches,
        stage_manifest_unchanged=stage_identity==inputs['stage_inputs'],stage_manifest_all_actual_input_hashes_match=stage_error is None,
        source_contract_unchanged=identity(inputs['contract']['path'])==inputs['contract'],scope_revision_unchanged=identity(inputs['scope_revision']['path'])==inputs['scope_revision'],
        attribution_selection_evidence_unchanged=not dependency_mismatches,no_post_integrity_error=status['post_integrity_error'] is None,
        resource_extrema_agree=peak==status['max_tree_rss_bytes'] and minimum_mem>=status['minimum_mem_available_bytes'] and minimum_disk>=status['minimum_disk_free_bytes'])
    execution_checks=dict(native_zero=status['native_exit_code']==0,supervisor_zero=status['exit_code']==0,natural_terminal=status['native_natural_terminal_observed'],
        no_stop=status['stop_reason'] is None,no_cleanup=not status['cleanup_was_required'],three_phases_closed=set(phases)=={'place','physopt','route'},
        all_closed_phase_codes_zero=all(all(value['native_receipt'][key]=='0' for key in ['post_code','locality_code']) for value in phases.values()),
        final_physical_evidence_available=physical is not None)
    shutil.copy2(Path(__file__),producer)
    value=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),execution_state='actual_supervisor_ended',closure_verified=all(checks.values()),
        engineering_execution_verified=all(checks.values()) and all(execution_checks.values()),checks=checks,execution_checks=execution_checks,
        started_utc=status['started_utc'],ended_utc=status['ended_utc'],native_exit_code=status['native_exit_code'],supervisor_exit_code=status['exit_code'],stop_reason=status['stop_reason'],
        status=identity(at/'status.json'),input_bindings=inputs_id,preparation_manifest=inputs['preparation_manifest'],base_contract=inputs['contract'],scope_revision=inputs['scope_revision'],
        selected_candidate=attr['selected_candidate'],coverage_version='candidate_directed_cut_v1',
        processes=processes,lane_lock_probe=lane,production_mismatches=mismatches,source_mismatches=source_mismatches,dependency_mismatches=dependency_mismatches,
        stage_manifest=stage_identity,stage_manifest_error=stage_error,closed_phases=phases,physical_evidence=physical,
        physical_evidence_identity=identity(physical_path) if physical_path.is_file() else None,
        resources=dict(samples=samples,first=first,last=last,peak_tree_RSS_bytes=peak,minimum_MemAvailable_bytes=minimum_mem,minimum_disk_free_bytes=minimum_disk,maximum_sample_gap_seconds=max_gap),
        producer=identity(producer),formal_signoff=False,claim='Execution, legal route, setup/hold/PW timing verdict, safety applicability and user review remain separate; native success alone is not formal signoff')
    save(target,value);short={key:value[key] for key in ['recorded_utc','execution_state','closure_verified','engineering_execution_verified','checks','execution_checks','started_utc','ended_utc','native_exit_code','supervisor_exit_code','stop_reason','selected_candidate','coverage_version','resources','formal_signoff','claim']};short['facts']=identity(target);save(summary,short)
    print(json.dumps(dict(facts=identity(target),summary=identity(summary),closure_verified=value['closure_verified'],engineering_execution_verified=value['engineering_execution_verified'])))

if __name__=='__main__':main()
