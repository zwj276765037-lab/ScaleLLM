"""Predeclared two-phase cost model: first16 exact, second16 envelope future.

All32 measured TV/old head arrays are independently checked. Slow first-segment
costs are retained exactly once in the full persistent trajectory, not omitted.
"""
from pathlib import Path
import argparse,json,math
import numpy as np
from aggregate_softmax_tv_v2 import audit_pair,identity,require,dump,read

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root;run=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R006';old=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R005';session=run/'qualification/two_group_cost_session_v4';gpu=read(session/'gpu_receipt.json');out=run/'qualification/two_group_cost_acceptance_v4.json'
    if gpu.get('native_exit_code')!=0 or gpu.get('exit_code')!=0 or not gpu.get('worker_reaped') or not gpu.get('source_unchanged') or gpu.get('stop_reason') is not None:
        dump(out,dict(execution_state='failed',full_budget_qualified=False,gpu=identity(session/'gpu_receipt.json'),reason='Actual shared qualification did not complete'));return 1
    worker=read(session/'qualification_worker_result.json');require(worker['assembly_loaded_once'] and worker['shared_worker_identity']==gpu['shared_worker_identity'],'one actual model assembly/shared worker')
    plan=read(run/'qualification/two_group_cost_source_v4/plan.json');baseline=read(old/'qualification/persistent_source_v1/session_plan_final.json');allrows=[];raw=[];groups=[];assembly=0.
    for index,(g,b) in enumerate(zip(plan['groups'],baseline['groups'][:2])):
        directory=Path(g['attempt_path']);previous=Path(b['attempt_path']);result=read(directory/'paired_result.json');require([d['doc_id'] for d in result['documents']]==b['doc_ids'],'same ordered original16 group')
        rows=[]
        for i,d in enumerate(result['documents']):
            row,tv,defect,witness=audit_pair(directory/'documents'/f'doc{i:04d}',previous/'documents'/f'doc{i:04d}')
            require(d['coverage']['complete'] and d['mlp_coverage']['complete'] and d['logit_coverage']['complete'],'complete numerical coverage')
            item=dict(group_index=index,doc_id=row['doc_id'],tokens=row['tokens'],seconds=d['seconds'],audited=d['audited'],mean_tv=tv['document_mean'],max_tv=tv['document_max'],max_mass_defect=defect);rows.append(item);allrows.append(item)
            if witness:raw.append(witness)
        stages=[json.loads(line) for line in (directory/'paired_stages.jsonl').read_text().splitlines()];group_assembly=sum(x['seconds'] for x in stages if x['stage'] in ['model_loaded','v5_attached','output_head_loaded']);assembly+=group_assembly
        receipt=read(directory/'qualification_segment_receipt.json');require(receipt['shared_worker_identity']==gpu['shared_worker_identity'],'same actual segment worker')
        groups.append(dict(index=index,wall_seconds=receipt['wall_seconds'],assembly_seconds=group_assembly,rows=rows,non_document_seconds=max(0.,receipt['wall_seconds']-group_assembly-sum(d['seconds'] for d in rows))))
    require(len(allrows)==32 and len(raw)==1 and all(not d['audited'] for d in groups[1]['rows']),'predeclared second16 has no raw audit')
    steady=groups[1]['rows'];X=np.asarray([[1,d['tokens']] for d in steady]);Y=np.asarray([d['seconds'] for d in steady]);coef=np.linalg.lstsq(X,Y,rcond=None)[0];intercept=max(0.,float(coef[0]));slope=max(0.,float(coef[1]));residual=max(0.,max(d['seconds']-intercept-slope*d['tokens'] for d in steady));prediction=lambda tokens:intercept+slope*tokens+residual
    audit_extra=max([0.]+[d['seconds']-prediction(d['tokens']) for d in groups[0]['rows'] if d['audited']])
    remaining=baseline['groups'][1:];remaining_tokens=sum(sum(g['actual_token_lengths']) for g in remaining);remaining_audits=sum(len(g['audit_doc_ids']) for g in remaining)
    first_document_seconds=sum(d['seconds'] for d in groups[0]['rows']);overhead=max(g['non_document_seconds'] for g in groups);fixed=max(0.,gpu['wall_seconds']-sum(g['wall_seconds'] for g in groups))
    old_total=read(old/'session_S001/session_receipt.json')['wall_seconds'];old_gpu=read(old/'session_S001/session_gpu_receipt.json')['wall_seconds'];finalizers=old_total-old_gpu
    modeled=assembly+fixed+first_document_seconds+1008*(intercept+residual)+remaining_tokens*slope+remaining_audits*audit_extra+64*overhead+finalizers+60;estimate=modeled*1.1
    max_group=max(sum(prediction(t) for t in g['actual_token_lengths'])+(audit_extra if g['audit_doc_ids'] else 0)+overhead for g in baseline['groups'])
    current_bytes=sum(p.stat().st_size for p in run.rglob('*') if p.is_file());old_sizes=[sum(p.stat().st_size for p in Path(g['attempt_path']).rglob('*') if p.is_file()) for g in baseline['groups']];storage=current_bytes+sum(old_sizes)+300*(1<<20)
    within=estimate<=14400 and max_group<=900 and storage<=6144*(1<<20) and max(old_sizes)+(1<<20)<=256*(1<<20)
    value=dict(schema='m005_r006_two_group_cost_qualification_v4',execution_state='completed',qualification_passed=True,full_budget_qualified=within,full_launch_authorized=False,scope='OriginalB001+B00232docs,oneassembly,two genuine segments; not reused as formal1024 measurement',gpu=identity(session/'gpu_receipt.json'),worker=identity(session/'qualification_worker_result.json'),source=identity(__file__),plan=identity(run/'qualification/two_group_cost_source_v4/plan.json'),documents=allrows,raw_witnesses=raw,all_old_head_fields_final_hidden_and_raw_arrays_equal=True,
        model=dict(first_group_document_seconds=first_document_seconds,second_group_envelope_intercept_seconds=intercept,second_group_envelope_slope_seconds_per_token=slope,second_group_max_positive_residual_seconds=residual,assembly_seconds=assembly,one_time_non_group_seconds=fixed,per_group_overhead_seconds=overhead,max_raw_audit_increment_seconds=audit_extra,remaining_documents=1008,remaining_positions=remaining_tokens,remaining_raw_audits=remaining_audits,prior_full_cpu_finalizer_seconds=finalizers,cleanup_seconds=60,modeled_full_seconds=modeled,margin_factor=1.1,conservative_full_estimate_seconds=estimate,max_group_estimate_seconds=max_group,estimated_evidence_bytes=storage,estimated_max_group_bytes=max(old_sizes)+(1<<20),
            method='Predeclared first16 exact measured document costs retained once; second16 nonnegative elapsed-vs-token fit plus max positive residual envelopes every second-group document, applied to all remaining1008 exact input lengths. All14 remaining audit docs get maximal measured full-raw overhead. Maximum observed non-document overhead repeats64times, plus once-only assembly/import, measured prior finalizers,cleanup and10percent margin.',
            limitation='Finite actual cost model conditional on observed second-group regime continuing; no causal warmup claim, guarantee or change to native resource stops. All first-phase slow timings remain in evidence/model.'),rejected_conditions=[] if within else ['Full estimate exceeds unchanged bound; no further GPU qualification or automatic full launch'])
    dump(out,value)
    accept=run/'qualification/pilot_acceptance.json';history=run/'qualification/pilot_acceptance_before_two_group_v4.json';require(not history.exists(),'preserve acceptance history');history.write_bytes(accept.read_bytes());latest=read(accept);latest.update(full_budget_qualified=within,full_launch_authorized=False,prior_acceptance_v4=identity(history),formal_cost_qualification=identity(out),accepted_cost_model=value['model'],blocker=None if within else 'Two-group predeclared cost model exceeds unchanged bound');accept.write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(full_budget_qualified=within,estimate_seconds=estimate,max_group_estimate_seconds=max_group,evidence_mib=storage/(1<<20))));return 0 if within else 2

if __name__=='__main__':raise SystemExit(main())
