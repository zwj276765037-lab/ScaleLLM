"""Execute only a finite Root-frozen E012/R004 plan, one bounded GPU group at a time.

This entry point never chooses documents, retries a group, changes a budget, or
interprets successful execution as a precision verdict. --validate-only is CPU.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
PROJECT_ROOT=HERE.parents[4]
GPU_UUID='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
ATTEMPTS='project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts'
STOP_RESERVE=30
STOP_REQUESTED=None


def request_stop(signum,frame):
    global STOP_REQUESTED
    STOP_REQUESTED='queue interrupted by signal '+str(signum)


def now():return datetime.now(timezone.utc).isoformat()


def identity(path):
    path=Path(path).resolve()
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256') if hasattr(hashlib,'file_digest') else None
        if digest is None:
            digest=hashlib.sha256()
            for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    return dict(path=str(path),sha256=digest.hexdigest())


def verify(item):
    if identity(item['path'])['sha256']!=item['sha256']:raise ValueError('identity changed: '+item['path'])
    return Path(item['path']).resolve()


def read_json(path):return json.loads(Path(path).read_text())


def write_new(path,value):
    with Path(path).open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def replace_option(argv,option,value):
    aliases=['--batch-id','--batch-ids'] if option=='--batch-ids' else [option]
    indices=[i for i,arg in enumerate(argv) if arg in aliases]
    if len(indices)!=1 or indices[0]+1>=len(argv):raise ValueError('worker option absent/duplicated: '+option)
    result=list(argv);index=indices[0];result[index]=option;result[index+1]=str(value)
    return result


def completed_documents(attempt,expected,batch_ids,require_group=True):
    """Durable identity/coverage ledger, separate from independent numerical audit."""
    attempt=Path(attempt);completed=[]
    for index,doc in enumerate(expected):
        path=attempt/'documents'/f'doc{index:04d}'/'document_result.json'
        if not path.exists():continue
        row=read_json(path);coverage=row.get('coverage',{})
        if row.get('doc_id')!=doc['doc_id'] or row.get('tokens')!=doc['tokens']:
            raise ValueError('durable completed document identity mismatch')
        if not coverage.get('complete') or any(coverage.get(key)!=value for key,value in
            [('hidden_unique_layers',32),('local_unique_coordinates',384),('dynamic_unique_coordinates_per_arm',192),
             ('per_layer_dynamic_activation_calls',4),('per_layer_dynamic_kv_calls',2)]):
            raise ValueError('durable completed document coverage insufficient')
        completed.append(row)
    if require_group:
        receipt=read_json(attempt/'gpu_receipt.json');result=read_json(attempt/'paired_result.json')
        if (receipt.get('execution_state')!='completed' or receipt.get('exit_code')!=0 or
            not receipt.get('worker_reaped') or not receipt.get('source_unchanged')):
            raise ValueError('GPU receipt is not successful, reaped, unchanged execution')
        if result.get('execution_state')!='completed' or result.get('formal_batch_ids')!=batch_ids:
            raise ValueError('paired result batch identity/status mismatch')
        if result.get('documents')!=completed or len(completed)!=len(expected):
            raise ValueError('not every predeclared document completed exactly once')
        if result.get('formal_eval_documents')!=len(expected) or not result.get('source_unchanged'):
            raise ValueError('paired result formal denominator/source mismatch')
    return [row['doc_id'] for row in completed]


def validate_plan(path,project_root=PROJECT_ROOT,expected_counts=None):
    from formal_numerical_inputs import load_batch_group
    path=Path(path).resolve();plan_identity=identity(path);plan=read_json(path);root=Path(project_root).resolve()
    if plan.get('schema')!='m005_formal_numerical_queue_v1' or Path(plan['project_root']).resolve()!=root:
        raise ValueError('wrong queue schema/project')
    if plan.get('experiment')!='E012' or plan.get('run')!='R004':raise ValueError('queue restricted to E012/R004')
    if type(plan.get('register_attempts')) is not bool:raise ValueError('explicit registration policy required')
    if type(plan.get('total_wall_seconds')) is not int or plan['total_wall_seconds']<=STOP_RESERVE:
        raise ValueError('explicit finite total wall bound required')
    groups=plan['groups']
    if not groups or plan.get('group_count')!=len(groups):raise ValueError('explicit nonempty total group count required')
    if len({group['group_id'] for group in groups})!=len(groups) or any(not re.fullmatch(r'[A-Za-z0-9_]+',group['group_id']) for group in groups):
        raise ValueError('unique simple group IDs required')
    ready_path=verify(plan['source_ready']);ready=read_json(ready_path)
    sources=ready['code_identities']
    if len(sources)!=22 or len({row['path'] for row in sources})!=22:raise ValueError('expected22 distinct frozen numerical sources')
    frozen=[plan['source_ready'],plan['queue_source'],plan['bounded_supervisor'],*sources,*ready['input_identities']]
    if plan['queue_source']['path']!=str(Path(__file__).resolve()):raise ValueError('queue source path mismatch')
    if plan['register_attempts']:frozen.append(plan['organize_script'])
    for command in plan.get('finalize_commands',[]):
        if (not command.get('argv') or any(not isinstance(value,str) or not value for value in command['argv']) or
            type(command.get('wall_seconds')) is not int or not 1<=command['wall_seconds']<=300 or not command.get('source_identities')):
            raise ValueError('finalize command requires argv, source identities and finite CPU wall<=300')
        frozen+=command['source_identities']
    for item in frozen:verify(item)
    inputs={Path(row['path']).name:row for row in ready['input_identities']}
    input_plan=verify(inputs['formal_batch_plan.json']);storage=verify(inputs['formal_storage_plan.json'])
    formal=read_json(input_plan);frozen.append(formal['input_stream_manifest']);verify(frozen[-1])
    all_batches=[row['batch_id'] for row in formal['batches']]
    prior_ids=[];prior_docs=[]
    for previous in plan.get('precompleted',[]):
        verify(previous['gpu_receipt']);verify(previous['paired_result'])
        selected=load_batch_group(input_plan,previous['batch_ids'],storage_plan=storage,expected_counts=expected_counts)
        prior_ids+=previous['batch_ids']
        prior_docs+=completed_documents(previous['attempt_path'],selected['documents'],previous['batch_ids'])
        frozen += [previous['gpu_receipt'],previous['paired_result']]
    planned_ids=[];queue_docs=[];seen_attempts=set();prepared=[]
    for group in groups:
        if not re.fullmatch(r'AT\d{3,}',group['attempt_id']) or not re.fullmatch(r'[A-Za-z0-9_]+',group['title']):
            raise ValueError('invalid predeclared attempt identity')
        attempt=(root/ATTEMPTS/(group['attempt_id']+'_'+group['title'])).resolve()
        if Path(group['attempt_path']).resolve()!=attempt or attempt in seen_attempts:raise ValueError('attempt path reused/outside R004')
        seen_attempts.add(attempt)
        if (attempt/'gpu_launch_manifest.json').exists() or (attempt/'documents').exists():raise ValueError('attempt already consumed; retries require new plan/AT')
        if (attempt/'run.json').exists() and read_json(attempt/'run.json').get('execution_state')!='planned':
            raise ValueError('attempt is not fresh/planned')
        if type(group.get('wall_seconds')) is not int or not 1<=group['wall_seconds']<=900:
            raise ValueError('each group requires explicit wall bound<=900')
        contract_path=verify(group['stage_contract']);contract=read_json(contract_path)
        if (contract.get('kind')!='m005_bounded_gpu_stage' or contract.get('gpu_uuid')!=GPU_UUID or
            not group['wall_seconds']<=contract.get('max_wall_seconds',0)<=900):raise ValueError('wrong finite stage contract')
        for key,value in [('cpu_threads',1),('max_rss_gib',8),('max_gpu_gib',24),('evidence_mib',256)]:
            if contract.get(key)!=value:raise ValueError('stage budget mismatch: '+key)
        selected=load_batch_group(input_plan,group['batch_ids'],storage_plan=storage,expected_counts=expected_counts)
        docs=selected['documents'];contract_input=contract['input']
        if contract_input['logical_batch_ids']!=group['batch_ids'] or contract_input['doc_ids']!=[row['doc_id'] for row in docs]:
            raise ValueError('stage contract members differ from frozen group')
        if contract.get('audit',{}).get('doc_ids')!=selected['audit_doc_ids']:
            raise ValueError('stage contract raw audit membership mismatch')
        for key,actual in [('selected_documents',len(docs)),('actual_token_lengths',[row['tokens'] for row in docs]),
                           ('total_tokens',sum(row['tokens'] for row in docs))]:
            if key in contract_input and contract_input[key]!=actual:raise ValueError('stage contract token/count mismatch')
        planned_ids+=group['batch_ids'];queue_docs+=docs
        command=replace_option(ready['worker_command'],'--batch-ids',','.join(group['batch_ids']))
        command=replace_option(command,'--output-dir',attempt)
        prepared.append({**group,'attempt_path':str(attempt),'documents':docs,'worker_command':command})
        frozen.append(group['stage_contract'])
    if prior_ids+planned_ids!=all_batches:raise ValueError('precompleted+queue must partition the whole frozen batch order exactly')
    target=[doc for group in prepared for doc in group['documents']]
    all_ids=prior_docs+[doc['doc_id'] for doc in target]
    if len(all_ids)!=formal['full_target_documents'] or len(set(all_ids))!=len(all_ids):raise ValueError('full target document ledger incomplete/duplicated')
    # Too-short total bounds are valid stop-only plans: no group is launched without
    # its complete stage budget plus cleanup reserve remaining.
    verify(plan_identity)
    return dict(plan=plan,plan_identity=plan_identity,frozen=frozen,groups=prepared,prior_doc_ids=prior_docs,
                target_doc_ids=all_ids,queue_doc_ids=[doc['doc_id'] for doc in target],root=str(root),
                expected_counts=expected_counts)


def process_identity(pid):
    try:
        directory=Path('/proc')/str(pid);tail=(directory/'stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=pid,ppid=int(tail[1]),pgid=int(tail[2]),starttime=int(tail[19]),
                    argv=[os.fsdecode(value) for value in (directory/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')])
    except (OSError,ValueError,IndexError):return None


def same_process(proof):
    current=process_identity(proof['pid']) if proof else None
    return bool(current and all(current[key]==proof[key] for key in ['pid','pgid','starttime','argv']))


def launched_identity(process,argv):
    # /proc/cmdline can briefly be empty during exec. It is not a verified
    # command identity; wait for the exact argv before accepting the process.
    end=time.monotonic()+1
    while time.monotonic()<end:
        proof=process_identity(process.pid)
        if proof and proof['pgid']==process.pid and proof['argv']==argv:return proof
        if process.poll() is not None:break
        time.sleep(.005)
    raise RuntimeError('supervisor runtime identity unavailable/mismatched')


def reap_direct_child(process):
    """Popen owns this unreaped child even if exec identity could not be read."""
    if process.poll() is None:process.terminate()
    try:return process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill();return process.wait(timeout=3)


def discover_worker(supervisor_proof,expected_argv,attempt):
    """Only a recorded PID or a direct child of our own supervisor is considered."""
    candidates=[];pid=supervisor_proof['pid']
    worker_file=Path(attempt)/'gpu_worker.json'
    try:candidates.append(read_json(worker_file)['pid'])
    except (OSError,ValueError,KeyError,TypeError):pass
    try:candidates += [int(value) for value in Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
    except OSError:pass
    for candidate_pid in candidates:
        proof=process_identity(candidate_pid)
        if (proof and proof['ppid']==pid and proof['pgid']==candidate_pid and proof['argv']==expected_argv and
            proof['starttime']>=supervisor_proof['starttime']):return proof
    return None


def stop_owned(supervisor,supervisor_proof,worker_proof,group):
    """No GPU-occupancy based process selection; require PID/starttime/PGID/argv."""
    # Freeze only our supervisor while discovering its direct worker; this closes
    # the spawn/file-write race without selecting any process by GPU occupancy.
    if same_process(supervisor_proof):os.kill(supervisor.pid,signal.SIGSTOP)
    worker_proof=worker_proof or discover_worker(supervisor_proof,group['worker_command'],group['attempt_path'])
    for proof in [worker_proof]:
        if same_process(proof) and proof['pgid']==proof['pid']:os.killpg(proof['pid'],signal.SIGTERM)
    if same_process(supervisor_proof):
        if worker_proof is None:os.killpg(supervisor.pid,signal.SIGTERM)
        os.kill(supervisor.pid,signal.SIGCONT)
    try:supervisor.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if same_process(worker_proof) and worker_proof['pgid']==worker_proof['pid']:os.killpg(worker_proof['pid'],signal.SIGKILL)
        if same_process(supervisor_proof):os.killpg(supervisor.pid,signal.SIGTERM)
        try:supervisor.wait(timeout=4)
        except subprocess.TimeoutExpired:
            if same_process(supervisor_proof):os.killpg(supervisor.pid,signal.SIGKILL)
            supervisor.wait(timeout=4)
    if same_process(worker_proof):raise RuntimeError('owned worker survived cleanup; queue stopped')


def read_progress(path,cursor):
    rows=[]
    with Path(path).open() as stream:
        stream.seek(cursor)
        while True:
            line=stream.readline()
            if not line or not line.endswith('\n'):break
            rows.append(json.loads(line));cursor=stream.tell()
    return rows,cursor


def run_supervisor(argv,group,logdir,deadline,emit):
    attempt=Path(group['attempt_path']);worker_proof=None;cursor=0;stopping=None
    with (logdir/'supervisor_stdout.log').open('x') as stdout,(logdir/'supervisor_stderr.log').open('x') as stderr:
        process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True)
        try:supervisor_proof=launched_identity(process,argv)
        except Exception:
            initial=process_identity(process.pid)
            worker=discover_worker(initial,group['worker_command'],attempt) if initial else None
            if same_process(worker) and worker['pgid']==worker['pid']:os.killpg(worker['pid'],signal.SIGTERM)
            reap_direct_child(process)
            if same_process(worker):os.killpg(worker['pid'],signal.SIGKILL)
            raise
        write_new(logdir/'owned_supervisor.json',supervisor_proof)
        try:
            while process.poll() is None:
                if worker_proof is None:
                    candidate=discover_worker(supervisor_proof,group['worker_command'],attempt)
                    if candidate:
                        worker_proof=candidate;write_new(logdir/'owned_worker.json',candidate)
                stages=attempt/'paired_stages.jsonl'
                if stages.exists():
                    rows,cursor=read_progress(stages,cursor)
                    for row in rows:
                        if row.get('stage')=='document_completed':emit('document_completed',group_id=group['group_id'],doc_id=row['doc_id'])
                if STOP_REQUESTED or time.monotonic()>=deadline-STOP_RESERVE:
                    stopping=STOP_REQUESTED or 'total queue wall budget';break
                time.sleep(.2)
        except BaseException:
            stop_owned(process,supervisor_proof,worker_proof,group);raise
        if stopping:stop_owned(process,supervisor_proof,worker_proof,group)
        code=process.wait()
        # An unexpected supervisor failure must not allow an observed own worker
        # to outlive the group or overlap the next model.
        if same_process(worker_proof):stop_owned(process,supervisor_proof,worker_proof,group)
    return dict(exit_code=code,stop_reason=stopping,supervisor_pid=process.pid,worker_identity=worker_proof)


def register(validated,group,payload,logdir,label):
    if not validated['plan']['register_attempts']:return
    path=logdir/(label+'_payload.json');write_new(path,payload)
    argv=[sys.executable,'-B',validated['plan']['organize_script']['path'],'attempt','--root',validated['root'],
          '--experiment','E012','--run','R004','--id',group['attempt_id'],'--title',group['title'],'--input',str(path)]
    with (logdir/(label+'_registration_stdout.log')).open('x') as stdout,(logdir/(label+'_registration_stderr.log')).open('x') as stderr:
        result=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=30,check=False)
    if result.returncode:raise RuntimeError(label+' registration failed')


def finalize(command,directory,deadline):
    """Root-frozen CPU postprocessing, no shell and no numerical pass inference."""
    directory.mkdir();begin=time.monotonic();env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=''
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[key]='1'
    if begin+command['wall_seconds']+STOP_RESERVE>=deadline:raise TimeoutError('insufficient total time for finalize command')
    for item in command['source_identities']:verify(item)
    with (directory/'stdout.log').open('x') as stdout,(directory/'stderr.log').open('x') as stderr:
        process=subprocess.Popen(command['argv'],stdout=stdout,stderr=stderr,env=env,start_new_session=True)
        proof=None;reason=None;peak=0
        try:
            proof=launched_identity(process,command['argv']);write_new(directory/'owned_process.json',proof)
            while process.poll() is None:
                try:rss=next(int(line.split()[1])*1024 for line in Path(f'/proc/{process.pid}/status').read_text().splitlines() if line.startswith('VmRSS:'))
                except (OSError,StopIteration):rss=0
                peak=max(peak,rss)
                if STOP_REQUESTED:reason=STOP_REQUESTED
                elif rss>8<<30:reason='finalize RSS budget'
                elif time.monotonic()-begin>=command['wall_seconds']:reason='finalize wall budget'
                if reason:break
                time.sleep(.1)
        except (Exception,KeyboardInterrupt) as exc:reason=str(exc)
        finally:
            if process.poll() is None and same_process(proof) and proof['pgid']==proof['pid']:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if same_process(proof):os.killpg(process.pid,signal.SIGKILL)
            code=reap_direct_child(process)
    try:
        for item in command['source_identities']:verify(item)
    except Exception as exc:reason=str(exc)
    result=dict(argv=command['argv'],exit_code=code,stop_reason=reason,wall_seconds=time.monotonic()-begin,
                max_observed_rss_bytes=peak,worker_pid=process.pid,worker_reaped=True)
    write_new(directory/'receipt.json',result)
    if code or reason:raise RuntimeError('finalize command failed: '+str(result))
    return result


def execute(validated,output_dir,supervise=run_supervisor,clock=time.monotonic,started_monotonic=None):
    directory=Path(output_dir).resolve();directory.mkdir(parents=True,exist_ok=True)
    if not directory.is_relative_to(Path(validated['root'])/'project/E012_multistage_rounding_precision/experiment_results/runs/R004'):
        raise ValueError('queue evidence must remain within E012/R004')
    begin=clock() if started_monotonic is None else started_monotonic
    deadline=begin+validated['plan']['total_wall_seconds'];started=now()
    write_new(directory/'queue_manifest.json',dict(started_at=started,plan=validated['plan_identity'],
        source=identity(__file__),command=sys.argv,group_count=len(validated['groups']),
        total_wall_seconds=validated['plan']['total_wall_seconds'],precompleted_document_ids=validated['prior_doc_ids']))
    results=[];done=list(validated['prior_doc_ids']);stop=None
    def emit(event,**values):
        row=dict(at=now(),event=event,**values)
        with (directory/'queue_events.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    for group in validated['groups']:
        logdir=directory/group['group_id'];logdir.mkdir()
        attempt=Path(group['attempt_path']);group_started=now();launch=None;state='failed';error=None;completed=[]
        try:
            if STOP_REQUESTED:raise InterruptedError(STOP_REQUESTED)
            if clock()+group['wall_seconds']+STOP_RESERVE>=deadline:
                raise TimeoutError('insufficient total queue time for full next stage plus cleanup')
            verify(validated['plan_identity'])
            for item in validated['frozen']:verify(item)
            # Repeat token/plan qualification just before each group, not only at
            # queue startup. The numerical worker also checks each NPZ on use.
            from formal_numerical_inputs import load_batch_group
            ready=read_json(validated['plan']['source_ready']['path']);inputs={Path(row['path']).name:row['path'] for row in ready['input_identities']}
            load_batch_group(inputs['formal_batch_plan.json'],group['batch_ids'],storage_plan=inputs['formal_storage_plan.json'],
                             expected_counts=validated.get('expected_counts'))
            attempt.mkdir(parents=True,exist_ok=True)
            register(validated,group,dict(execution_state='running',started_at=group_started,scope='finite formal numerical group; not numerical acceptance'),logdir,'running')
            if STOP_REQUESTED:raise InterruptedError(STOP_REQUESTED)
            if clock()+group['wall_seconds']+STOP_RESERVE>=deadline:
                raise TimeoutError('insufficient queue time after registration; GPU not launched')
            argv=[sys.executable,'-B',validated['plan']['bounded_supervisor']['path'],'--output-dir',str(attempt),
                  '--wall-seconds',str(group['wall_seconds']),'--max-gpu-gib','24','--stage-contract',group['stage_contract']['path']]
            for item in [*validated['frozen'],validated['plan_identity'],identity(__file__)]:argv+=['--source',item['path']]
            argv+=['--',*group['worker_command']]
            write_new(logdir/'launch_plan.json',dict(supervisor_argv=argv,worker_argv=group['worker_command'],
                command_display=shlex.join(argv),batch_ids=group['batch_ids'],expected_doc_ids=[doc['doc_id'] for doc in group['documents']],started_at=group_started))
            emit('group_started',group_id=group['group_id'],batch_ids=group['batch_ids'],attempt_path=str(attempt))
            launch=supervise(argv,group,logdir,deadline,emit)
            if launch['exit_code']!=0 or launch.get('stop_reason'):raise RuntimeError('bounded supervisor failed/stopped: '+str(launch))
            for item in validated['frozen']:verify(item)
            completed=completed_documents(attempt,group['documents'],group['batch_ids'])
            state='completed'
        except (Exception,KeyboardInterrupt) as exc:
            error=str(exc);stop=error
            if launch is None and (logdir/'owned_supervisor.json').exists():
                launch=dict(exit_code=130,stop_reason=error,supervisor_identity=read_json(logdir/'owned_supervisor.json'),
                            worker_identity=read_json(logdir/'owned_worker.json') if (logdir/'owned_worker.json').exists() else None)
            if (attempt/'gpu_receipt.json').exists():
                raw=read_json(attempt/'gpu_receipt.json')
                if raw.get('execution_state')=='cost_stop':state='cost_stop'
            try:completed=completed_documents(attempt,group['documents'],group['batch_ids'],require_group=False)
            except Exception as partial:completed=[];error+='; partial ledger: '+str(partial)
        finished=now();done+=completed
        result=dict(group_id=group['group_id'],batch_ids=group['batch_ids'],attempt_path=str(attempt),execution_state=state,
                    started_at=group_started,ended_at=finished,launch=launch,error=error,completed_document_ids=completed,
                    not_completed_document_ids=[doc['doc_id'] for doc in group['documents'] if doc['doc_id'] not in completed])
        write_new(logdir/'queue_group_receipt.json',result);results.append(result)
        if attempt.exists():
            evidence=[str((logdir/'queue_group_receipt.json').relative_to(validated['root']))]
            for name in ['gpu_launch_manifest.json','gpu_receipt.json','paired_result.json']:
                if (attempt/name).exists():evidence.append(str((attempt/name).relative_to(validated['root'])))
            payload=dict(execution_state=state,command=shlex.join(group['worker_command']),
                         code_identity=json.dumps(validated['frozen']),input_identity=json.dumps(dict(batch_ids=group['batch_ids'],doc_ids=[doc['doc_id'] for doc in group['documents']])),
                         started_at=group_started,finished_at=finished,exit_status=0 if state=='completed' else ((launch['exit_code'] or 76) if launch else None),
                         scope='execution only; five numerical nodes plus propagation; independent numerical verdict pending',evidence=evidence)
            write_new(attempt/'terminal_payload.json',payload)
            try:register(validated,group,payload,logdir,'terminal')
            except (Exception,KeyboardInterrupt) as exc:stop=str(exc);result['registration_error']=str(exc)
        if STOP_REQUESTED:stop=STOP_REQUESTED
        emit('group_finished',group_id=group['group_id'],execution_state=state,completed_documents=len(completed),stop_reason=stop)
        if stop:break
    remaining=[value for value in validated['target_doc_ids'] if value not in set(done)]
    analysis_results=[];analysis_failed=False
    if stop is None and not remaining:
        for index,command in enumerate(validated['plan'].get('finalize_commands',[])):
            try:analysis_results.append(finalize(command,directory/f'finalize{index:03d}',deadline))
            except (Exception,KeyboardInterrupt) as exc:stop=str(exc);analysis_failed=True;break
    receipt=dict(execution_state='analysis_failed' if analysis_failed else ('completed' if stop is None else 'stopped'),started_at=started,ended_at=now(),
                 wall_seconds=clock()-begin,stop_reason=stop,planned_groups=len(validated['groups']),finished_groups=len(results),
                 groups=results,completed_document_ids=done,not_completed_document_ids=remaining,
                 full_target_execution_coverage_verified=not remaining and all(row['execution_state']=='completed' for row in results),
                 model_execution_completed=not remaining and all(row['execution_state']=='completed' for row in results),
                 analysis_results=analysis_results,numerical_verdict='not_evaluated',
                 completion_basis='precompleted identities plus per-document durable32/384/192 coverage; never process exit alone')
    write_new(directory/'queue_receipt.json',receipt);emit('queue_finished',execution_state=receipt['execution_state'],completed_documents=len(done),not_completed_documents=len(remaining))
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    started=time.monotonic()
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    validated=validate_plan(args.plan)
    if args.validate_only:
        print(json.dumps(dict(validation='passed',groups=len(validated['groups']),queue_documents=len(validated['queue_doc_ids']),
                              precompleted_documents=len(validated['prior_doc_ids']),gpu_started=False)));return 0
    receipt=execute(validated,args.output_dir,started_monotonic=started)
    return 0 if receipt['execution_state']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
