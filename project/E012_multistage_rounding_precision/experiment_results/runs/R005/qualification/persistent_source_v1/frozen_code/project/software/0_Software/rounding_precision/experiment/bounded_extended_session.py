"""Root-frozen finite R005 resident session supervisor; GPU0, CPU1, RSS8/GPU24.

This is a new stage entry, never an extension or restart of Q001/AT002. A plan
must explicitly freeze total time/storage and all1024 member groups. Only one
real GPU launch/receipt is emitted; group execution segments keep their own IDs.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import traceback
import run_formal_numerical_queue as owned
from capture_real_inputs import GPU0_UUID,GIB,gpu_snapshot,own_gpu_bytes,rss_bytes,now
from run_extended_numerical_session import validate_plan,read,write_new,group_coverage
from run_numerical_fidelity import identity

STOP=None

def request_stop(signum,frame):
    global STOP
    STOP='supervisor interrupted by signal '+str(signum)
    owned.STOP_REQUESTED=STOP


def directory_bytes(path):
    total=0
    for item in Path(path).rglob('*'):
        try:metadata=item.stat()
        except FileNotFoundError:continue # an atomic .partial file may just have been replaced
        if stat.S_ISREG(metadata.st_mode):total+=metadata.st_size
    return total


def evidence_bytes(directory,groups):
    candidates={Path(directory).resolve(),*[Path(g['attempt_path']).resolve() for g in groups]}
    roots=[p for p in candidates if not any(parent in candidates for parent in p.parents)]
    return sum(directory_bytes(path) for path in roots)


def stop_child(process,proof):
    """A group is signaled only while full PID/starttime/PGID/argv still match."""
    if proof is None:
        # This unreaped direct child is owned by Popen even during an exec identity race.
        # Signal its PID only; group signaling requires the full verified proof below.
        return owned.reap_direct_child(process)
    if process.poll() is None and owned.same_process(proof) and proof['pgid']==proof['pid']:
        os.killpg(process.pid,signal.SIGTERM)
        try:return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if owned.same_process(proof):os.killpg(process.pid,signal.SIGKILL)
    return owned.reap_direct_child(process)


def monitor(process,proof,prepared,directory,started,*,sample=None,clock=time.monotonic,sleep=time.sleep):
    """Resource loop injectable for CPU dummy qualification; never selects GPU PIDs."""
    plan=prepared['plan'];limits=plan['limits'];reason=None;peak_rss=peak_gpu=0
    sample=sample or (lambda:dict(rss=rss_bytes(process.pid),gpu=own_gpu_bytes(process.pid),device=gpu_snapshot()))
    with (directory/'session_resources.jsonl').open('x') as log:
        while process.poll() is None:
            if STOP:reason=STOP
            try:metrics=sample()
            except Exception:metrics=dict(rss=None,gpu=None,device=None)
            rss,gpu,device=metrics['rss'],metrics['gpu'],metrics['device']
            peak_rss=max(peak_rss,rss or 0);peak_gpu=max(peak_gpu,gpu or 0)
            elapsed=clock()-started
            log.write(json.dumps(dict(at=now(),elapsed_seconds=elapsed,rss_bytes=rss,gpu_bytes=gpu,
                gpu_free_bytes=None if device is None else device['free_bytes']))+'\n');log.flush()
            if process.poll() is not None:break
            if reason:pass
            elif rss is None or gpu is None or device is None:reason='resource telemetry unavailable'
            elif rss>8*GIB:reason='own worker RSS exceeded8GiB'
            elif gpu>24*GIB:reason='own worker GPU exceeded24GiB'
            elif device['free_bytes']<8*GIB:reason='shared GPU free space below8GiB'
            elif elapsed>=limits['total_wall_seconds']-limits['cleanup_reserve_seconds']:reason='assigned global wall budget reached'
            elif evidence_bytes(directory,prepared['groups'])>limits['total_evidence_mib']*(1<<20):reason='assigned total evidence budget reached'
            progress=directory/'group_progress.json'
            if not reason and progress.exists():
                try:
                    state=read(progress)
                    if state.get('execution_state')=='running':
                        if clock()-state['group_started_monotonic']>=limits['group_wall_seconds']-5:reason='assigned logical group wall budget reached'
                        elif directory_bytes(state['attempt_path'])>256*(1<<20):reason='logical group evidence exceeded256MiB'
                except (OSError,ValueError,KeyError):pass # atomic writer may be between replace operations
            if reason:break
            sleep(.5)
    native=stop_child(process,proof)
    return dict(native_exit_code=native,exit_code=124 if reason else native,stop_reason=reason,
        max_observed_rss_bytes=peak_rss,max_observed_gpu_bytes=peak_gpu,worker_reaped=True)


def completion_ledger(prepared):
    terminal=[];durable=[]
    for g in prepared['groups']:
        attempt=Path(g['attempt_path']);receipt=attempt/'execution_receipt.json'
        if receipt.exists():
            try:
                r=read(receipt)
                if r.get('execution_state')=='completed' and r.get('coverage_complete'):
                    terminal.extend(r.get('completed_doc_ids',[]))
            except (OSError,ValueError):pass
        for i,doc_id in enumerate(g['doc_ids']):
            path=attempt/'documents'/f'doc{i:04d}'/'document_result.json'
            if not path.exists():continue
            try:
                d=read(path)
                if d.get('doc_id')==doc_id and all(d.get(k,{}).get('complete') for k in ['coverage','mlp_coverage','logit_coverage']):durable.append(doc_id)
            except (OSError,ValueError):pass
    target=prepared['expected_doc_ids'];terminal_set=set(terminal);durable_set=set(durable)
    return dict(completed_group_document_ids=[d for d in target if d in terminal_set],
        durable_document_ids=[d for d in target if d in durable_set],
        incomplete_group_document_ids=[d for d in target if d not in terminal_set],
        unmeasured_document_ids=[d for d in target if d not in durable_set],
        coverage_scope='group/durable execution counts are provisional until global native0/reap and independent audit')


def finalize_manifest(prepared,directory,receipt):
    actual=[];groups=[]
    for g in prepared['groups']:
        group_coverage(g);path=Path(g['attempt_path'])/'execution_receipt.json';r=read(path)
        if r.get('execution_state')!='completed' or not r.get('source_unchanged') or not r.get('coverage_complete'):
            raise ValueError('group execution receipt not complete')
        actual.extend(r['completed_doc_ids']);groups.append(dict(group_id=g['group_id'],attempt_path=g['attempt_path'],receipt=identity(path)))
    if actual!=prepared['expected_doc_ids'] or len(set(actual))!=1024:raise ValueError('full1024 coverage missing/duplicated')
    manifest=dict(schema='m005_r005_analysis_manifest_v1',model_execution_complete=True,expected_documents=1024,completed_documents=1024,
        expected_doc_ids=prepared['expected_doc_ids'],actual_doc_ids=actual,missing_doc_ids=[],ordered_groups=groups,
        session_gpu_receipt=identity(directory/'session_gpu_receipt.json'),session_launch_manifest=identity(directory/'session_launch_manifest.json'),
        shared_worker_identity=read(directory/'session_worker.json')['shared_worker_identity'],
        shared_head_source=identity(directory/'output_head/output_head_identity.json'),plan=prepared['plan_identity'],
        inference_state='pending independent audit/final aggregation',precision_verdict='not_evaluated')
    write_new(directory/'analysis_manifest.json',manifest)
    return manifest


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--validate-only',action='store_true');a=p.parse_args(argv)
    prepared=validate_plan(a.plan);plan=prepared['plan'];directory=a.output_dir.resolve()
    if directory!=Path(plan['session_directory']).resolve():raise ValueError('session directory differs from frozen plan')
    if a.validate_only:
        print(json.dumps(dict(validation='passed',gpu_started=False,groups=len(prepared['groups']),documents=1024)));return 0
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'session_launch_manifest.json').exists():raise ValueError('prior session cannot be silently retried')
    signal.signal(signal.SIGINT,request_stop);signal.signal(signal.SIGTERM,request_stop)
    started=time.monotonic();started_at=now()
    command=[sys.executable,'-B',str(Path(__file__).with_name('run_extended_numerical_session.py')),'--worker','--plan',str(a.plan.resolve()),'--output-dir',str(directory)]
    sources=[*plan['source_identities'],prepared['plan_identity'],plan['stage_contract'],plan['formal_batch_plan'],plan['formal_storage_plan']]
    for item in sources:owned.verify(item)
    preflight=gpu_snapshot();available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    launch=dict(schema='m005_r005_persistent_launch_v1',started_at=started_at,command=command,cwd=str(Path.cwd()),gpu_uuid=GPU0_UUID,
        source_identity=sources,preflight=preflight,available_ram_bytes=available,limits=plan['limits'],plan=prepared['plan_identity'],
        supervisor_identity=owned.process_identity(os.getpid()),budget_started_monotonic=started)
    if preflight['free_bytes']<30*GIB or available<32*GIB or STOP:
        launch['shared_worker_identity']=None;write_new(directory/'session_launch_manifest.json',launch)
        write_new(directory/'session_gpu_receipt.json',dict(execution_state='cost_stop',started_at=started_at,ended_at=now(),exit_code=75,native_exit_code=None,
            worker_launched=False,worker_reaped=True,source_unchanged=True,stop_reason=STOP or 'preflight resource admission failed'))
        return 75
    env=os.environ.copy()
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[key]='1'
    env.update(CUDA_VISIBLE_DEVICES=GPU0_UUID,PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DEACTIVATE_ASYNC_LOAD='1')
    proof=None
    with (directory/'session_stdout.log').open('x') as stdout,(directory/'session_stderr.log').open('x') as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
        try:
            proof=owned.launched_identity(child,command)
            launch['shared_worker_identity']=proof;write_new(directory/'session_launch_manifest.json',launch)
            write_new(directory/'session_worker.json',dict(shared_worker_identity=proof,started_at=now()))
            result=monitor(child,proof,prepared,directory,started)
        except BaseException as error:
            native=stop_child(child,proof)
            result=dict(native_exit_code=native,exit_code=1,stop_reason=repr(error),worker_reaped=True)
    unchanged=True
    try:
        for item in sources:owned.verify(item)
    except Exception as error:unchanged=False;result.update(exit_code=76,stop_reason=str(error))
    if result['exit_code']==0:
        try:
            worker=read(directory/'session_worker_result.json')
            if worker.get('execution_state')!='completed' or worker.get('completed_doc_ids')!=prepared['expected_doc_ids'] or len(set(worker['completed_doc_ids']))!=1024:
                raise ValueError('worker full-target ledger incomplete')
            if read(directory/'session_cache_summary.json').get('assembly_loaded_once') is not True:raise ValueError('model not assembled exactly once')
        except Exception as error:result.update(exit_code=1,stop_reason=str(error))
    state='completed' if result['exit_code']==0 else ('cost_stop' if result['exit_code']==124 else 'failed')
    receipt=dict(**result,execution_state=state,started_at=started_at,ended_at=now(),wall_seconds=time.monotonic()-started,
        worker_pid=child.pid,shared_worker_identity=proof,source_unchanged=unchanged,expected_documents=1024,
        precision_verdict='not_evaluated',**completion_ledger(prepared))
    write_new(directory/'session_gpu_receipt.json',receipt)
    overall=dict(model_execution_state=state,analysis_state='not_started',numerical_verdict='inconclusive')
    if state=='completed':
        try:
            finalize_manifest(prepared,directory,receipt)
            for i,command in enumerate(plan.get('finalize_commands',[])):
                owned.finalize(command,directory/f'finalize_{i:03d}',started+plan['limits']['total_wall_seconds']-max(0,plan['limits']['cleanup_reserve_seconds']-owned.STOP_RESERVE))
            overall['analysis_state']='completed' if plan.get('finalize_commands') else 'pending'
        except BaseException as error:overall.update(analysis_state='failed',error=repr(error))
    overall.update(started_at=started_at,ended_at=now(),wall_seconds=time.monotonic()-started,global_gpu_receipt=identity(directory/'session_gpu_receipt.json'))
    write_new(directory/'session_receipt.json',overall)
    return 0 if state=='completed' and overall['analysis_state'] in ['completed','pending'] else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:traceback.print_exc();raise SystemExit(1)
