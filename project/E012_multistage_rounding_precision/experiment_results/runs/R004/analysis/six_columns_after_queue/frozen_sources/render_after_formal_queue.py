"""Finite CPU dependency task: render only after the original full Q001 succeeds.

This does not start, stop, retry, or modify the model queue. Root freezes the
plan and launches this separate task; --validate-only never waits or renders.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timedelta,timezone
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time

HERE=Path(__file__).resolve().parent
PROJECT_ROOT=HERE.parents[4]
STOP_REQUESTED=None
HELPER=None


def now():return datetime.now(timezone.utc)


def utc(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('deadline requires an explicit UTC offset')
    return result.astimezone(timezone.utc)


def identity(path):
    path=Path(path).resolve();digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    return dict(path=str(path),sha256=digest.hexdigest())


def verify(spec):
    result=identity(spec['path'])
    if result['sha256']!=spec['sha256']:raise ValueError('source/input identity changed: '+spec['path'])
    return Path(result['path'])


def read_json(path,max_bytes=128<<20):
    path=Path(path)
    if path.stat().st_size>max_bytes:raise ValueError('JSON exceeds finite input size budget')
    return json.loads(path.read_text())


def write_new(path,value):
    with Path(path).open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def request_stop(signum,frame):
    global STOP_REQUESTED
    STOP_REQUESTED='dependency task interrupted by signal '+str(signum)
    if HELPER is not None:HELPER.STOP_REQUESTED=STOP_REQUESTED


def validate_plan(path,project_root=PROJECT_ROOT):
    path=Path(path).resolve();plan_source=identity(path);plan=read_json(path);root=Path(project_root).resolve()
    if plan.get('schema')!='m005_render_after_formal_queue_v1' or Path(plan['project_root']).resolve()!=root:
        raise ValueError('wrong dependency task schema/project')
    if plan.get('render_wall_seconds')!=60 or plan.get('poll_seconds') not in [5,10]:
        raise ValueError('render wall must be60s; wait poll must be5 or10s')
    if Path(plan['driver']['path']).resolve()!=Path(__file__).resolve():raise ValueError('driver identity path mismatch')
    sources=[plan_source,plan['driver'],plan['renderer'],plan['queue_helper'],plan['queue_plan'],*plan['renderer_source_identities']]
    if not plan['renderer_source_identities'] or not any(row==plan['renderer'] for row in plan['renderer_source_identities']):
        raise ValueError('renderer itself must be in frozen renderer dependencies')
    for spec in sources:verify(spec)
    queue_plan=read_json(plan['queue_plan']['path'])
    if queue_plan.get('schema')!='m005_formal_numerical_queue_v1' or queue_plan.get('queue_source')!=plan['queue_helper']:
        raise ValueError('helper differs from the original frozen numerical queue')
    base=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R004'
    expected=dict(queue_receipt=base/'queues/Q001/queue_receipt.json',aggregate=base/'analysis/Q001/aggregate/formal_aggregate.json',
                  final_report_manifest=base/'analysis/Q001/report/report_manifest.json',output_dir=base/'analysis/figure_six_columns_final')
    if any(Path(plan[key]).resolve()!=value for key,value in expected.items()):raise ValueError('task paths must match original Q001/new figure destination')
    if Path(plan['output_dir']).exists():raise ValueError('render destination must be new; do not overwrite a figure')
    launch_path=expected['queue_receipt'].parent/'root_launch_receipt.json';launch=read_json(launch_path)
    if launch['owned_queue']!=plan['queue_process'] or launch['plan_sha256']!=plan['queue_plan']['sha256'] or Path(launch['plan']).resolve()!=Path(plan['queue_plan']['path']).resolve():
        raise ValueError('original queue runtime/plan identity mismatch')
    if utc(plan['utc_deadline'])!=utc(launch['started_at'])+timedelta(seconds=queue_plan['total_wall_seconds']+120):
        raise ValueError('absolute CPU dependency deadline differs from original queue bound plus120s')
    sources.append(identity(launch_path))
    spec=importlib.util.spec_from_file_location('m005_frozen_queue_dependency_helper',verify(plan['queue_helper']))
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    verify(plan_source)
    return dict(plan=plan,plan_source=plan_source,sources=sources,queue_plan=queue_plan,helper=helper,
                deadline=utc(plan['utc_deadline']),base=base)


def current_receipt(validated):
    path=Path(validated['plan']['queue_receipt'])
    if not path.exists():return None
    try:return read_json(path,max_bytes=16<<20)
    except json.JSONDecodeError:
        if validated['helper'].same_process(validated['plan']['queue_process']):return None
        raise ValueError('original queue exited with an incomplete receipt')


def require_completed_receipt(receipt,queue_plan):
    if receipt.get('execution_state')!='completed' or receipt.get('stop_reason') is not None:
        raise ValueError('original numerical queue did not complete successfully')
    ids=receipt.get('completed_document_ids',[])
    if (not receipt.get('full_target_execution_coverage_verified') or not receipt.get('model_execution_completed') or
        len(ids)!=1024 or len(set(ids))!=1024 or receipt.get('not_completed_document_ids')!=[]):
        raise ValueError('original queue lacks1024 unique completed documents with no missing IDs')
    groups=receipt.get('groups',[])
    if (receipt.get('planned_groups')!=len(queue_plan['groups']) or receipt.get('finished_groups')!=len(queue_plan['groups']) or
        [row.get('group_id') for row in groups]!=[row['group_id'] for row in queue_plan['groups']] or
        any(row.get('execution_state')!='completed' for row in groups)):
        raise ValueError('original queue group coverage is incomplete')
    analysis=receipt.get('analysis_results',[]);planned=queue_plan.get('finalize_commands',[])
    if not planned or len(analysis)!=len(planned) or any(row.get('argv')!=command['argv'] or row.get('exit_code')!=0 or
        row.get('stop_reason') is not None or not row.get('worker_reaped') for row,command in zip(analysis,planned)):
        raise ValueError('original queue analysis did not all finish successfully')
    return set(ids)


def completed_inputs(validated,receipt):
    """Check the completed report's identity chain, without rehashing large raw runs."""
    plan=validated['plan'];ids=require_completed_receipt(receipt,validated['queue_plan'])
    aggregate_path=Path(plan['aggregate']);aggregate_source=identity(aggregate_path);aggregate=read_json(aggregate_path)
    if (aggregate.get('schema')!='m005_formal_numerical_aggregate_v1' or aggregate.get('execution_state')!='completed' or
        not aggregate.get('collection_complete') or aggregate.get('planned_documents')!=1024 or
        aggregate.get('completed_documents')!=1024 or aggregate.get('missing_documents')!=0 or aggregate.get('missing_doc_ids')!=[]):
        raise ValueError('full formal aggregate is missing/incomplete')
    docs=aggregate.get('documents',[])
    if (len(docs)!=1024 or {row['doc_id'] for row in docs}!=ids or len({row['duplicate_cluster'] for row in docs})!=1024 or
        Counter(row['domain'] for row in docs)!=Counter(web=512,news=256,reviews=256)):
        raise ValueError('aggregate document identities/domain quotas differ from complete queue')
    if any(row.get('coverage')!=dict(hidden_layers=32,local_coordinates=384,dynamic_coordinates=384,final_norm=1) for row in docs):
        raise ValueError('aggregate per-document coverage incomplete')
    report_path=Path(plan['final_report_manifest']);report_source=identity(report_path);report=read_json(report_path)
    if report.get('schema')!='m005_numerical_report_identity_v1':raise ValueError('wrong original report manifest schema')
    inputs=report['source_files'];outputs=report['output_files']
    matching=[item for item in inputs if Path(item['path']).resolve()==aggregate_path.resolve()]
    if len(matching)!=1 or matching[0]['sha256']!=aggregate_source['sha256']:raise ValueError('original report does not bind the complete aggregate')
    for item in [*inputs,*outputs]:verify(item)
    summaries=[item for item in outputs if Path(item['path']).name=='summary.json']
    if len(summaries)!=1:raise ValueError('original report summary absent/duplicated')
    summary=read_json(summaries[0]['path'])
    if (summary.get('schema')!='m005_user_numerical_report_v1' or not summary.get('full_collection') or
        summary.get('report_kind')!='full_collection' or summary.get('planned_documents')!=1024 or
        summary.get('measured_documents')!=1024 or summary.get('missing_documents')!=0):
        raise ValueError('original readable report is only partial')
    verify(aggregate_source);verify(report_source)
    return dict(queue_receipt=identity(plan['queue_receipt']),aggregate=aggregate_source,original_report_manifest=report_source,
                qualification='full queue coverage plus original aggregate/report identity chain; no new model or numerical oracle execution')


def execute(validated,control_dir,sleep=time.sleep,clock=now,completion_check=completed_inputs):
    global HELPER
    HELPER=validated['helper'];control=Path(control_dir).resolve();plan=validated['plan'];started=clock()
    if (not control.is_relative_to(validated['base']) or control.is_relative_to(Path(plan['queue_receipt']).parent) or
        control==Path(plan['output_dir']).resolve() or Path(plan['output_dir']).resolve().is_relative_to(control)):
        raise ValueError('control must be a new separate directory within R004, outside original Q001/figure output')
    control.mkdir(parents=True,exist_ok=False)
    write_new(control/'manifest.json',dict(started_at=started.isoformat(),command=sys.argv,plan=validated['plan_source'],sources=validated['sources'],
        utc_deadline=plan['utc_deadline'],scope='wait for full original queue; CPU figure only; no model/GPU/notifications',original_queue_process=plan['queue_process']))
    reason=None;inputs=None;render=None;state='stopped'
    try:
        while True:
            for source in validated['sources']:verify(source)
            if STOP_REQUESTED:raise InterruptedError(STOP_REQUESTED)
            if clock()>=validated['deadline']:raise TimeoutError('absolute dependency deadline reached')
            receipt=current_receipt(validated)
            if receipt is not None:
                inputs=completion_check(validated,receipt);break
            if not HELPER.same_process(plan['queue_process']):raise RuntimeError('original queue exited/identity changed without a complete success receipt')
            sleep(min(plan['poll_seconds'],max(0,(validated['deadline']-clock()).total_seconds())))
        for source in validated['sources']:verify(source)
        remaining=(validated['deadline']-clock()).total_seconds()
        if remaining<=plan['render_wall_seconds']+HELPER.STOP_RESERVE:raise TimeoutError('insufficient absolute time for bounded render and cleanup')
        argv=[sys.executable,'-B',plan['renderer']['path'],'--aggregate',plan['aggregate'],'--output-dir',plan['output_dir']]
        command=dict(argv=argv,wall_seconds=plan['render_wall_seconds'],source_identities=plan['renderer_source_identities'])
        write_new(control/'render_command.json',dict(**command,completed_inputs=inputs))
        render=HELPER.finalize(command,control/'render_run',time.monotonic()+remaining)
        for source in validated['sources']:verify(source)
        for key in ['queue_receipt','aggregate','original_report_manifest']:verify(inputs[key])
        output=Path(plan['output_dir'])
        artifacts=[identity(output/name) for name in ['numerical_six_columns.png','numerical_six_columns.pdf','source_data.json']]
        write_new(control/'output_manifest.json',dict(outputs=artifacts,source_inputs=inputs))
        state='completed'
    except (Exception,KeyboardInterrupt) as exc:reason=str(exc)
    result=dict(execution_state=state,started_at=started.isoformat(),ended_at=clock().isoformat(),stop_reason=reason,
        plan=validated['plan_source'],completed_inputs=inputs,render_result=render,model_reexecuted=False,
        gpu_started=False,notification_sent=False,numerical_verdict='not_assigned')
    write_new(control/'receipt.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--control-dir',type=Path,required=True)
    parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    validated=validate_plan(args.plan);receipt=current_receipt(validated)
    if args.validate_only:
        if receipt is not None:completed_inputs(validated,receipt)
        elif not validated['helper'].same_process(validated['plan']['queue_process']):raise ValueError('queue is not alive and has no successful full receipt')
        print(json.dumps(dict(validation='passed',state='complete_dependency' if receipt else 'waiting_dependency',gpu_started=False,renderer_started=False)))
        return 0
    result=execute(validated,args.control_dir);print(json.dumps(result));return 0 if result['execution_state']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
