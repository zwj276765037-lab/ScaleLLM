"""One finite R005 GPU process, one assembly, ordered frozen formal groups.

Only the separate global supervisor starts this --worker. Group receipts describe
segments of that shared process; they are not independent GPU launch receipts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from run_numerical_fidelity import identity,write_json,timestamp
from run_formal_numerical_queue import process_identity,verify

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
ATTEMPTS=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R005/attempts'
SESSION_SCHEMA='m005_r005_persistent_plan_v1'
GROUP_SCHEMA='m005_r005_persistent_group_receipt_v1'


def read(path):return json.loads(Path(path).read_text())


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def atomic_replace_json(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.partial')
    with temporary.open('w') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def check_sequence(groups,expected_batch_ids,expected_doc_ids):
    batch_ids=[b for g in groups for b in g['logical_batch_ids']]
    doc_ids=[d for g in groups for d in g['doc_ids']]
    if batch_ids!=expected_batch_ids:raise ValueError('groups must partition all logical batches in the original order')
    if doc_ids!=expected_doc_ids or len(set(doc_ids))!=len(doc_ids):raise ValueError('groups must partition all documents without omission/duplicate/reorder')


def validate_plan(path,*,fresh=True):
    from formal_numerical_inputs import load_batch_group
    plan_path=Path(path).resolve();initial_plan_identity=identity(plan_path);plan=read(plan_path)
    if plan.get('schema')!=SESSION_SCHEMA or Path(plan['project_root']).resolve()!=ROOT:
        raise ValueError('wrong persistent session schema/project')
    if plan.get('expected_documents')!=1024 or plan.get('group_count')!=len(plan['groups']) or not plan['groups']:
        raise ValueError('explicit full1024 finite nonempty group roster required')
    limits=plan['limits']
    for key,value in [('cpu_threads',1),('max_rss_gib',8),('max_gpu_gib',24),('per_group_mib',256),('group_wall_seconds',900),('launch_free_gpu_gib',30),('runtime_free_gpu_gib',8)]:
        if limits.get(key)!=value:raise ValueError('persistent resource contract mismatch: '+key)
    for key in ['total_wall_seconds','total_evidence_mib']:
        if type(limits.get(key)) is not int or limits[key]<=0:raise ValueError('explicit finite total bound required: '+key)
    if type(limits.get('cleanup_reserve_seconds')) is not int or limits['cleanup_reserve_seconds']<15:
        raise ValueError('finite cleanup reserve at least15seconds required')
    contract_path=verify(plan['stage_contract']);contract=read(contract_path)
    if (contract.get('kind')!='m005_persistent_numerical_stage' or contract.get('limits')!=limits
        or contract.get('gpu_uuid')!='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'):
        raise ValueError('separate Root persistent stage contract must match exact limits')
    if not contract.get('basis_evidence') or any(not Path(p).is_file() for p in contract['basis_evidence']):
        raise ValueError('measured pilot evidence required before persistent launch')
    import run_extended_numerical as entry
    from types import SimpleNamespace
    required={r['path'] for r in entry.source_identities(SimpleNamespace(mlp_module='mlp_numerical_extension',logit_module='logit_numerical_extension'))}
    required.update(str((HERE/name).resolve()) for name in ['run_extended_numerical_session.py','extended_session_cache.py','bounded_extended_session.py','run_formal_numerical_queue.py'])
    declared=[str(Path(r['path']).resolve()) for r in plan['source_identities']]
    if len(set(declared))!=len(declared) or not required<=set(declared):raise ValueError('persistent source dependency omitted/duplicated')
    for source in plan['source_identities']:verify(source)
    if type(plan.get('register_attempts')) is not bool:raise ValueError('explicit registration policy required')
    if plan['register_attempts']:verify(plan['organize_script'])
    for command in plan.get('finalize_commands',[]):
        if (not isinstance(command.get('argv'),list) or not command['argv'] or
            any(not isinstance(value,str) or not value for value in command['argv'])):
            raise ValueError('finalizer requires exact nonempty argv list, never shell text')
        if type(command.get('wall_seconds')) is not int or not 1<=command['wall_seconds']<=300:
            raise ValueError('finalizer requires a finite CPU wall<=300')
        if not command.get('source_identities'):raise ValueError('finalizer source identities absent')
        for item in command['source_identities']:verify(item)
    formal=verify(plan['formal_batch_plan']);storage=verify(plan['formal_storage_plan'])
    frozen=read(formal);expected_batches=[b['batch_id'] for b in frozen['batches']]
    expected_docs=[d for b in frozen['batches'] for d in b['doc_ids']]
    if len(expected_docs)!=1024:raise ValueError('original full formal frame must remain1024')
    prepared=[];attempts=set();group_ids=set()
    for g in plan['groups']:
        if not re.fullmatch(r'AT\d{3,}',g['attempt_id']) or not re.fullmatch(r'[A-Za-z0-9_]+',g['title']):raise ValueError('invalid R005 attempt identity')
        attempt=(ATTEMPTS/(g['attempt_id']+'_'+g['title'])).resolve()
        if Path(g['attempt_path']).resolve()!=attempt or attempt in attempts:raise ValueError('group attempt reused/outside E012/R005')
        if g['group_id'] in group_ids:raise ValueError('duplicate group ID')
        if fresh and any((attempt/name).exists() for name in ['documents','paired_result.json','execution_receipt.json']):
            raise ValueError('consumed group cannot be silently retried')
        attempts.add(attempt);group_ids.add(g['group_id'])
        meta=load_batch_group(formal,g['logical_batch_ids'],storage_plan=storage)
        docs=meta['documents']
        if g['doc_ids']!=[d['doc_id'] for d in docs] or g['actual_token_lengths']!=[d['tokens'] for d in docs] or g['audit_doc_ids']!=meta['audit_doc_ids']:
            raise ValueError('group members/tokens/audit differ from frozen input')
        if not 1<=len(docs)<=80 or len(meta['audit_doc_ids'])>1:raise ValueError('bounded logical group exceeds80documents/oneaudit')
        prepared.append({**g,'metadata':meta,'documents':docs,'attempt_path':str(attempt)})
    check_sequence(prepared,expected_batches,expected_docs)
    if plan.get('expected_doc_ids')!=expected_docs:raise ValueError('explicit target identity roster mismatch')
    if identity(plan_path)!=initial_plan_identity:raise ValueError('plan identity changed during validation')
    return dict(plan=plan,plan_identity=initial_plan_identity,groups=prepared,expected_doc_ids=expected_docs)


def worker_args(plan,group):
    from run_extended_numerical import parser
    return parser().parse_args(['--worker','--model-dir',plan['model_dir'],'--formal-batch-plan',plan['formal_batch_plan']['path'],
        '--formal-storage-plan',plan['formal_storage_plan']['path'],'--batch-ids',','.join(group['logical_batch_ids']),
        '--tokens','128','--raw-value-audit-layers','0,15,31','--witness-max-doc-mib','64','--witness-max-at-mib','96',
        '--mlp-module','mlp_numerical_extension','--logit-module','logit_numerical_extension','--output-dir',group['attempt_path']])


def verify_sources(sources):
    for item in sources:verify(item)


def group_coverage(group):
    directory=Path(group['attempt_path']);result=read(directory/'paired_result.json')
    docs=result.get('documents',[])
    if (result.get('execution_state')!='completed' or not result.get('required_extension_complete') or not result.get('source_unchanged')
        or result.get('formal_eval_documents')!=len(group['doc_ids']) or result.get('formal_batch_ids')!=group['logical_batch_ids']
        or [d['doc_id'] for d in docs]!=group['doc_ids'] or [d['tokens'] for d in docs]!=group['actual_token_lengths']):
        raise ValueError('group result does not cover every frozen document')
    for d in docs:
        c=d['coverage'];m=d['mlp_coverage'];l=d['logit_coverage']
        if (not c.get('complete') or (c.get('hidden_unique_layers'),c.get('local_unique_coordinates'),c.get('dynamic_unique_coordinates_per_arm'))!=(32,384,192)
            or not m.get('complete') or m.get('unique_coordinates')!=416 or not l.get('complete')
            or l.get('real_positions')!=d['tokens'] or l.get('vocabulary')!=128256 or l.get('score_pairs')!=d['tokens']*128256):
            raise ValueError('group contains a document with incomplete extended coverage')
    for filename,per_doc in [('tensor_metrics.jsonl',32),('local_tensor_metrics.jsonl',384),('mlp_metrics.jsonl',416),('logit_metrics.jsonl',1),('dynamic_metadata.jsonl',384)]:
        counts=Counter(json.loads(line)['doc_id'] for line in (directory/filename).read_text().splitlines() if line)
        if counts!=Counter({d:per_doc for d in group['doc_ids']}):raise ValueError('raw row coverage mismatch: '+filename)
    return docs


def outputs(directory):
    # Management records may change during registration; only experiment data is signed.
    directory=Path(directory)
    roots={'documents','node_witnesses','output_head'}
    names={'paired_worker_manifest.json','paired_result.json','paired_stages.jsonl','tensor_metrics.jsonl',
           'local_tensor_metrics.jsonl','mlp_metrics.jsonl','logit_metrics.jsonl','dynamic_metadata.jsonl',
           'document_summary.json','local_document_summary.json','final_norm_document_summary.json',
           'v5_attach_metadata.json','shared_loader_reference.json','node_witness_policy.json','tokenizer_identity.json','stream_loader_validation.json'}
    return [identity(path) for path in sorted(directory.rglob('*')) if path.is_file()
            and (path.relative_to(directory).parts[0] in roots or path.name in names)]


def register_group(group,payload=None,script=None):
    script=Path(script) if script is not None else Path('/home/zwj/.codex/skills/research-agent/scripts/organize.py')
    argv=[sys.executable,str(script),'attempt','--root',str(ROOT),
          '--experiment','E012','--run','R005','--id',group['attempt_id'],'--title',group['title']]
    if payload:argv+=['--input',str(payload)]
    directory=Path(group['attempt_path']);directory.mkdir(parents=True,exist_ok=True)
    label='registration_terminal' if payload else 'registration_planned';started=timestamp()
    with (directory/(label+'_stdout.log')).open('x') as stdout,(directory/(label+'_stderr.log')).open('x') as stderr:
        result=subprocess.run(argv,check=False,timeout=45,stdout=stdout,stderr=stderr,text=True)
    write_new(directory/(label+'.json'),dict(argv=argv,source=identity(script),started_at=started,ended_at=timestamp(),exit_code=result.returncode))
    if result.returncode:raise RuntimeError('group management registration failed')


def execute_groups(prepared,directory,run_group,*,clock=time.monotonic,register=None):
    """CPU-injectable finite orchestration; run_group is the real frozen worker."""
    directory=Path(directory);plan=prepared['plan'];begin=read(directory/'session_launch_manifest.json')['budget_started_monotonic'];done=[];group_receipts=[];target=len(prepared['expected_doc_ids'])
    shared=read(directory/'session_worker.json')['shared_worker_identity']
    launch_identity=identity(directory/'session_launch_manifest.json')
    for g in prepared['groups']:
        if plan['limits']['total_wall_seconds']-(clock()-begin)<plan['limits']['group_wall_seconds']+plan['limits']['cleanup_reserve_seconds']:
            raise RuntimeError('insufficient remaining global budget to begin next fixed group')
        verify_sources(plan['source_identities']);verify(plan['formal_batch_plan']);verify(plan['formal_storage_plan'])
        if register:register(g)
        attempt=Path(g['attempt_path']);attempt.mkdir(parents=True,exist_ok=True)
        start=timestamp();group_begin=clock()
        atomic_replace_json(directory/'group_progress.json',dict(group_id=g['group_id'],attempt_path=str(attempt),group_started_monotonic=group_begin,
            execution_state='running',completed_documents=len(done),expected_documents=target))
        common=dict(schema=GROUP_SCHEMA,group_id=g['group_id'],canonical_group_path=str(attempt.resolve()),session_path=str(directory.resolve()),
            runtime_kind='segment_of_shared_gpu_worker',shared_worker_identity=shared,session_launch_identity=launch_identity,
            global_receipt_path=str((directory/'session_gpu_receipt.json').resolve()),logical_batch_ids=g['logical_batch_ids'],doc_ids=g['doc_ids'],
            actual_token_lengths=g['actual_token_lengths'],started_at=start,code=plan['source_identities'],
            input_identities=[plan['formal_batch_plan'],plan['formal_storage_plan']])
        try:
            native=run_group(g)
            if native!=0:raise RuntimeError('group worker failed with native exit '+str(native))
            verify_sources(plan['source_identities']);docs=group_coverage(g)
            for filename in ['paired_worker_manifest.json','paired_result.json']:
                path=attempt/filename;value=read(path);value.update(runtime_kind='segment_of_shared_gpu_worker',shared_session=str(directory.resolve()),shared_worker_identity=shared)
                atomic_replace_json(path,value)
            receipt={**common,'execution_state':'completed','exit_code':0,'ended_at':timestamp(),'wall_seconds':clock()-group_begin,
                'source_unchanged':True,'coverage_complete':True,'completed_doc_ids':[d['doc_id'] for d in docs],
                'output_identities':outputs(attempt),'numerical_verdict':'not_evaluated; independent audit and final collection analysis required'}
            write_new(attempt/'execution_receipt.json',receipt)
            done.extend(receipt['completed_doc_ids']);group_receipts.append(identity(attempt/'execution_receipt.json'))
            if register:
                payload=dict(execution_state='completed',command='shared persistent worker segment: '+g['group_id'],code_identity=json.dumps(plan['source_identities']),
                    input_identity=json.dumps(common['input_identities']),started_at=start,finished_at=receipt['ended_at'],exit_status=0,
                    scope='R005 shared-process group execution only; global/native0/full1024 and numerical independent audit separate',
                    evidence=[str((attempt/'execution_receipt.json').relative_to(ROOT)),str((attempt/'paired_result.json').relative_to(ROOT))])
                write_new(attempt/'terminal_payload.json',payload);register(g,attempt/'terminal_payload.json')
            atomic_replace_json(directory/'group_progress.json',dict(group_id=g['group_id'],execution_state='completed',completed_documents=len(done),expected_documents=target))
            print(json.dumps(dict(event='group_completed',group_id=g['group_id'],documents=len(docs),completed_documents=len(done),total_documents=target)),flush=True)
        except BaseException as error:
            if not (attempt/'execution_receipt.json').exists():
                write_new(attempt/'execution_receipt.json',{**common,'execution_state':'failed','ended_at':timestamp(),'wall_seconds':clock()-group_begin,
                    'source_unchanged':False if 'identity changed' in str(error) else None,'coverage_complete':False,'error':repr(error)})
            raise
    if done!=prepared['expected_doc_ids'] or len(done)!=target or len(set(done))!=target:raise ValueError('all1024 extended document coverage incomplete')
    value=dict(schema='m005_r005_persistent_worker_result_v1',execution_state='completed',completed_documents=len(done),
        expected_documents=target,completed_doc_ids=done,missing_doc_ids=[],source_unchanged=True,group_receipts=group_receipts,
        shared_worker_identity=shared,numerical_verdict='not_evaluated')
    write_new(directory/'session_worker_result.json',value)
    return value


def worker(plan_path,directory):
    prepared=validate_plan(plan_path);directory=Path(directory)
    import capture_real_inputs as loader
    from numerical_reference import model_compat as compat
    import logit_numerical_extension as head
    import run_extended_numerical as entry
    from extended_numerical_stream import extended_worker
    from extended_session_cache import ExtendedSessionCache
    import run_paired_numerical_model as prior
    # Supervisor creates immutable actual runtime identities before releasing us.
    deadline=time.monotonic()+5
    while not (directory/'session_worker.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('supervisor runtime identity not published')
        time.sleep(.01)
    if read(directory/'session_worker.json')['shared_worker_identity']!=process_identity(os.getpid()):raise ValueError('shared worker identity mismatch')
    cache=ExtendedSessionCache(directory,prepared['plan']['model_dir'])
    def run(g):
        args=worker_args(prepared['plan'],g)
        helpers={name:getattr(prior,name) for name in ['stage','read_document','validate_attach','reset_audit','audit_report','buffer_signature']}
        helpers.update(static_check=entry.static_check,code_identities=lambda:[identity(item['path']) for item in prepared['plan']['source_identities']])
        original_stage=helpers['stage']
        def progress(path,name,**details):
            original_stage(path,name,**details)
            if name=='document_completed':print(json.dumps(dict(event='document_completed',group_id=g['group_id'],**details)),flush=True)
        helpers['stage']=progress
        return extended_worker(args,helpers)
    with cache.context(loader,compat,head):
        register=(lambda group,payload=None:register_group(group,payload,script=verify(prepared['plan']['organize_script']))) if prepared['plan'].get('register_attempts') else None
        result=execute_groups(prepared,directory,run,register=register)
    write_json(directory/'session_cache_summary.json',dict(actual_loads=cache.loads,assembly_loaded_once=cache.loads==dict(base=1,attach=1,head=1)))
    if cache.loads!=dict(base=1,attach=1,head=1):raise ValueError('assembly cache did not load each object exactly once')
    return 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--worker',action='store_true');mode.add_argument('--validate-only',action='store_true')
    a=p.parse_args(argv)
    try:
        if a.validate_only:
            prep=validate_plan(a.plan)
            print(json.dumps(dict(validation='passed',gpu_started=False,group_count=len(prep['groups']),documents=len(prep['expected_doc_ids']))));return 0
        return worker(a.plan,a.output_dir)
    except BaseException:
        traceback.print_exc();return 1


if __name__=='__main__':raise SystemExit(main())
