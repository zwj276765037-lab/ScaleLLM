#!/usr/bin/env python3
"""Independent actual authorized E006 closure; no signals, EDA or status rewrite."""
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[3]
AT=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution'
REPORT=ROOT/'project/hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution'


def identity(path):
    path=Path(path);before=path.stat();digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return dict(path=str(path),bytes=after.st_size,sha256=digest.hexdigest())


def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def table(path):
    if not path.is_file() or not path.stat().st_size:return []
    with path.open() as stream:return list(csv.DictReader(stream,delimiter='\t',quoting=csv.QUOTE_NONE))


def main():
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    status=json.loads((AT/'status.json').read_text());started=json.loads((AT/'started.json').read_text())
    decision_path=ROOT/'.research-agent/decision_inputs/E006_20261017_user_allowed_readonly_switch.json'
    decision=identity(decision_path)
    assert decision['sha256']=='0a87602f7f69cb909bcc9c725db0d4082293197f77eb1519429e328fd70e6a50'
    authorization=json.loads(decision_path.read_text())
    assert authorization['execution_authorized'] is True and authorization['approval_kind']=='user_explicit_controlled_stop'
    assert status['execution_state']=='completed' and status['native_exit_code']==-15 and status['exit_code']==125
    assert status['stop_reason']=='KeyboardInterrupt:signal 15' and status['native_natural_terminal_observed'] is False
    assert status['post_integrity_error']=="NameError: name 'new_peak_sources' is not defined"
    bindings=identity(AT/'input_bindings.json');assert bindings==status['inputs']==started['inputs']
    inputs=json.loads((AT/'input_bindings.json').read_text())
    ids={str(pid):int(start) for pid,start in status['tracked_identities'].items()}
    ids[str(status['supervisor_pid'])]=status['supervisor_start_ticks']
    resume=json.loads((ROOT/'agent/A006/resume_E006.json').read_text())['active']
    for row in resume['native_processes']:
        pid=str(row['pid']);tick=row['expected_start_ticks'];assert pid not in ids or ids[pid]==tick;ids[pid]=tick
    observed=[]
    for pid,tick in sorted(ids.items(),key=lambda x:int(x[0])):
        row=dict(pid=int(pid),expected_start_ticks=tick,original_identity_present=False,original_live=False)
        try:
            f=Path('/proc',pid,'stat').read_text().rsplit(')',1)[1].split()
            row.update(current_start_ticks=int(f[19]),state=f[0]);row['original_identity_present']=row['current_start_ticks']==tick
            row['original_live']=row['original_identity_present'] and row['state']!='Z'
        except FileNotFoundError:pass
        observed.append(row)
    pgroup=[]
    for entry in os.scandir('/proc'):
        if not entry.name.isdigit():continue
        try:
            f=Path(entry.path,'stat').read_text().rsplit(')',1)[1].split()
            if int(f[2])==942061 and f[0]!='Z':pgroup.append(dict(pid=int(entry.name),start_ticks=int(f[19]),state=f[0]))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    freeze=inputs['frozen_inputs']['freeze'];assert identity(freeze['path'])==freeze
    frozen=json.loads(Path(freeze['path']).read_text())['files']
    mismatches=[r for r in frozen if identity(r['path'])!=r]
    checkpoints={k:identity(v['path']) for k,v in inputs['checkpoints'].items()}
    external={k:identity(v['path']) for k,v in inputs['external_inputs'].items()}
    archived=[identity(v['path']) for v in inputs['sources']]
    reuse_manifest=ROOT/'agent/A006/E006_lean_candidate/reuse_manifest.json'
    reuse=json.loads(reuse_manifest.read_text())
    reused={k:identity(v['path']) for k,v in reuse['artifacts'].items()}
    samples=0;peak=0;minimum_mem=None;minimum_disk=None;first=None;last=None;gap=0.0
    with (AT/'resources.jsonl').open() as stream:
        for line in stream:
            row=json.loads(line);first=first or row['utc']
            if last:gap=max(gap,(datetime.fromisoformat(row['utc'])-datetime.fromisoformat(last)).total_seconds())
            last=row['utc'];samples+=1;peak=max(peak,row['rss_bytes'])
            minimum_mem=row['mem_available_bytes'] if minimum_mem is None else min(minimum_mem,row['mem_available_bytes'])
            minimum_disk=row['disk_free_bytes'] if minimum_disk is None else min(minimum_disk,row['disk_free_bytes'])
    lock_path=ROOT/'project/hardware/vivado/.m002_eda.lock'
    with lock_path.open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lock_result=dict(path=str(lock_path),probe='exclusive_nonblocking_acquire_succeeded',released_immediately=True)
        fcntl.flock(lock,fcntl.LOCK_UN)
    checks=dict(production_144_unchanged=len(frozen)==144 and not mismatches,
        bound_checkpoints_unchanged=checkpoints==inputs['checkpoints'],
        external_14_unchanged=len(external)==14 and external==inputs['external_inputs'],
        archived_4_unchanged=len(archived)==4 and archived==inputs['sources'],
        reused_17_closed_artifacts_unchanged=len(reused)==17 and reused==reuse['artifacts'],
        contract_unchanged=identity(inputs['contract']['path'])==inputs['contract'],
        no_registered_original_live=not any(r['original_live'] for r in observed),no_live_original_pgroup=not pgroup,
        original_guard_no_survivors=status['owned_survivors']==[],lane_released=True,
        sampled_peak_agrees=peak==status['max_tree_rss_bytes'],
        sampled_resource_minima_consistent=minimum_mem>=status['minimum_mem_available_bytes'] and minimum_disk>=status['minimum_disk_free_bytes'],
        no_physical_commands=status['physical_commands_executed'] is False,
        no_checkpoint_write=status['checkpoint_write_executed'] is False)
    assert all(checks.values()),checks
    queries=table(REPORT/'query_receipts.tsv');stages=table(REPORT/'stage_receipts.tsv')
    producer=AT/'controlled_terminal_audit_producer_20261017.py';shutil.copy2(Path(__file__),producer)
    facts=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),controlled_closure_verified=True,
        engineering_execution_verified=False,native_diagnostic_completed=False,execution_state='authorized_controlled_stop',
        decision=decision,status=identity(AT/'status.json'),signal=identity(AT/'authorized_controlled_stop_signal_20261017.json'),
        original_native_exit_code=status['native_exit_code'],original_supervisor_reported_exit_code=status['exit_code'],
        original_stop_reason=status['stop_reason'],original_post_integrity_error=status['post_integrity_error'],
        wrapper_error_interpretation='Original NameError is retained; it is not evidence that external inputs changed. Independent equality checks below are separate.',
        started_utc=status['started_utc'],ended_utc=status['ended_utc'],natural_terminal=False,
        checks=checks,input_bindings=bindings,production_files_checked=len(frozen),production_mismatches=mismatches,
        checkpoints=checkpoints,external_inputs=external,archived_sources=archived,
        reuse_manifest=identity(reuse_manifest),reused_closed_artifacts=reused,
        processes=observed,original_live_pgroup=pgroup,lane_lock_probe=lock_result,
        closed_queries=queries,closed_stages=stages,
        last_closed_query=queries[-1]['query'] if queries else None,
        interrupted_scope='module_resources incomplete after closed native_owner_debug; next interconnect remainder was not closed',
        source_log=identity(REPORT/'vivado.log'),query_receipts=identity(REPORT/'query_receipts.tsv'),
        stage_receipts=identity(REPORT/'stage_receipts.tsv'),result=identity(REPORT/'result.txt') if (REPORT/'result.txt').is_file() else None,
        resources=dict(samples=samples,first_sample=first,last_sample=last,maximum_sample_gap_seconds=gap,
            sampled_peak_tree_rss_bytes=peak,minimum_mem_available_bytes=minimum_mem,minimum_disk_free_bytes=minimum_disk),
        producer=identity(producer),physical_signoff=False)
    output=AT/'controlled_terminal_facts_20261017.json';save(output,facts)
    short={k:facts[k] for k in ('recorded_utc','controlled_closure_verified','engineering_execution_verified',
        'native_diagnostic_completed','execution_state','decision','status','original_native_exit_code',
        'original_supervisor_reported_exit_code','original_stop_reason','original_post_integrity_error',
        'started_utc','ended_utc','checks','last_closed_query','interrupted_scope','resources')}
    short['facts']=identity(output);summary=AT/'controlled_terminal_summary_20261017.json';save(summary,short)
    print(json.dumps(dict(facts=identity(output),summary=identity(summary),status=identity(AT/'status.json'),checks=checks)))


if __name__=='__main__':main()
