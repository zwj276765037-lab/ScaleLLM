"""Finite actual16doc cost qualification, exact baseline audit and budget model."""
from pathlib import Path
import argparse,json,math,time
import numpy as np
from aggregate_softmax_tv_v2 import audit_pair,identity,require,dump,read

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root;run=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R006';old=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R005';attempt=run/'attempts/AT066_formal_firstgroup_cost_qualification';gpu=read(attempt/'gpu_receipt.json');out=run/'qualification/formal_cost_acceptance.json'
    if gpu.get('native_exit_code')!=0 or gpu.get('exit_code')!=0 or not gpu.get('worker_reaped') or not gpu.get('source_unchanged') or gpu.get('stop_reason') is not None:
        dump(out,dict(execution_state='failed',full_budget_qualified=False,full_launch_authorized=False,gpu=identity(attempt/'gpu_receipt.json'),reason='Actual qualification native/resource/source completion failed'));return 1
    baseline_plan=read(old/'qualification/persistent_source_v1/session_plan_final.json');group=baseline_plan['groups'][0];previous=Path(group['attempt_path']);result=read(attempt/'paired_result.json')
    require([d['doc_id'] for d in result['documents']]==group['doc_ids'] and len(result['documents'])==16,'all original first16 docs')
    rows=[];raw=[]
    for i,d in enumerate(result['documents']):
        row,tv,defect,witness=audit_pair(attempt/'documents'/f'doc{i:04d}',previous/'documents'/f'doc{i:04d}')
        require(d['coverage']['complete'] and d['mlp_coverage']['complete'] and d['logit_coverage']['complete'],'full old numerical coverage')
        rows.append(dict(doc_id=row['doc_id'],tokens=row['tokens'],seconds=d['seconds'],audited=d['audited'],mean_tv=tv['document_mean'],max_tv=tv['document_max'],max_mass_defect=defect))
        if witness:raw.append(witness)
    stages=[json.loads(line) for line in (attempt/'paired_stages.jsonl').read_text().splitlines()];assembly=sum(d['seconds'] for d in stages if d['stage'] in ['model_loaded','v5_attached','output_head_loaded'])
    ordinary=[d for d in rows if not d['audited']];design=np.asarray([[1,d['tokens']] for d in ordinary],dtype=np.float64);elapsed=np.asarray([d['seconds'] for d in ordinary]);coef=np.linalg.lstsq(design,elapsed,rcond=None)[0]
    intercept=max(0.,float(coef[0]));slope=max(0.,float(coef[1]));residual=max(0.,max(d['seconds']-intercept-slope*d['tokens'] for d in ordinary))
    prediction=lambda tokens:intercept+slope*tokens+residual
    audit_extra=max([0.]+[d['seconds']-prediction(d['tokens']) for d in rows if d['audited']])
    group_overhead=max(0.,gpu['wall_seconds']-assembly-sum(d['seconds'] for d in rows))
    old_stage=read(old/'session_S001/session_receipt.json');old_gpu=read(old/'session_S001/session_gpu_receipt.json');finalizer=old_stage['wall_seconds']-old_gpu['wall_seconds']
    modeled=assembly+1024*(intercept+residual)+103700*slope+15*audit_extra+64*group_overhead+finalizer+60
    estimate=modeled*1.1
    max_group=max(sum(prediction(t) for t in g['actual_token_lengths'])+(audit_extra if g['audit_doc_ids'] else 0)+group_overhead for g in baseline_plan['groups'])
    total_bytes=sum(p.stat().st_size for p in run.rglob('*') if p.is_file());old_group_sizes=[sum(p.stat().st_size for p in Path(g['attempt_path']).rglob('*') if p.is_file()) for g in baseline_plan['groups']];evidence_estimate=total_bytes+sum(old_group_sizes)+300*(1<<20)
    within=estimate<=14400 and max_group<=900 and evidence_estimate<=6144*(1<<20) and max(old_group_sizes)+(1<<20)<=256*(1<<20)
    check=dict(schema='m005_r006_formal_cost_qualification_v3',execution_state='completed',qualification_passed=True,full_budget_qualified=within,full_launch_authorized=False,
        scope='Actual original B00116doc cost qualification only; not counted as any formal full1024 completion',gpu=identity(attempt/'gpu_receipt.json'),source=identity(__file__),documents=rows,raw_witnesses=raw,all_old_head_fields_final_hidden_and_raw_arrays_equal=True,
        model=dict(intercept_seconds=intercept,slope_seconds_per_token=slope,max_observed_positive_residual_seconds=residual,assembly_seconds=assembly,max_raw_audit_increment_seconds=audit_extra,
            per_group_overhead_seconds=group_overhead,prior_full_cpu_finalizer_seconds=finalizer,cleanup_seconds=60,modeled_full_seconds=modeled,margin_factor=1.1,conservative_full_estimate_seconds=estimate,max_group_estimate_seconds=max_group,
            estimated_evidence_bytes=evidence_estimate,estimated_max_group_bytes=max(old_group_sizes)+(1<<20),
            method='Nonnegative linear elapsed-vs-token fit plus maximum observed positive residual envelopes all15 ordinary docs. Apply exact1024 docs/103700tokens and15 maximal raw audit increments; conservatively repeat entire measured first-group non-document overhead64times; add actual assembly/prior finalizers/cleanup and10percent margin.',
            limitation='Measured finite cost model, not guarantee for every future input/system load; unchanged native resource guards remain authoritative.'),
        rejected_conditions=[] if within else ['Full finite cost/storage estimate exceeds at least one unchanged bound; full launch remains forbidden'])
    dump(out,check)
    old_acceptance=run/'qualification/pilot_acceptance.json';prior=run/'qualification/pilot_acceptance_before_formal_cost.json';require(not prior.exists(),'never overwrite cost acceptance history');prior.write_bytes(old_acceptance.read_bytes());value=read(old_acceptance);value.update(full_budget_qualified=within,full_launch_authorized=False,prior_acceptance=identity(prior),formal_cost_qualification=identity(out),blocker=None if within else 'Actual formal16 cost model exceeds unchanged bound',accepted_cost_model=check['model'])
    old_acceptance.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(full_budget_qualified=within,estimate_seconds=estimate,max_group_estimate_seconds=max_group,evidence_mib=evidence_estimate/(1<<20))))
    return 0 if within else 2

if __name__=='__main__':raise SystemExit(main())
