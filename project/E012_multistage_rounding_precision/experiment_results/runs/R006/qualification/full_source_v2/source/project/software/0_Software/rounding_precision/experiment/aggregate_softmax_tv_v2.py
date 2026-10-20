"""Independently audit full R006 TV and exact R005 trajectory agreement.

No production TV formula is imported. Raw witnesses use centered NumPy softmax
and positive mass difference with math.fsum. Whole population production values
are checked for complete positions/vocabulary/mass, not independently rerun.
"""
from __future__ import annotations
import argparse,csv,copy,hashlib,json,math,time
from pathlib import Path
import numpy as np

def read(path):return json.loads(Path(path).read_text())
def require(value,message):
    if not value:raise ValueError(message)
def identity(path):
    path=Path(path).resolve();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=h.hexdigest())
def verify(item):
    actual=identity(item['path']);require(actual['sha256']==item['sha256'],'source/evidence identity changed: '+item['path']);return Path(item['path'])
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def independent(current,reference):
    results=[];defects=[]
    for a,b in zip(current.astype(np.float64),reference.astype(np.float64)):
        ea=np.exp(a-a.max());eb=np.exp(b-b.max())
        pa=ea/math.fsum(ea.tolist());pb=eb/math.fsum(eb.tolist())
        results.append(math.fsum(max(float(x-y),0.) for x,y in zip(pa,pb)))
        defects.extend([abs(math.fsum(pa.tolist())-1),abs(math.fsum(pb.tolist())-1)])
    return results,max(defects)
def audit_pair(new_directory,old_directory,*,formal=True):
    new_directory=Path(new_directory);old_directory=Path(old_directory)
    current=read(new_directory/'logit_metrics.json');old=read(old_directory/'logit_metrics.json')
    new_audit=current['raw_audit'];old_audit=old['raw_audit']
    tv=current['softmax_tv'];base=copy.deepcopy(current);del base['softmax_tv'];base.pop('raw_audit');old.pop('raw_audit')
    require(base==old,'R006 changed frozen R005 head metrics/finalhidden: '+current['doc_id'])
    T=current['tokens'];V=current['vocab_size']
    require(T>=1 and V==128256 and tv['temperature']==1. and tv['complete'] is True and tv['tokens']==T and tv['vocab_size']==V and tv['probability_pairs']==T*V,'TV geometry/temperature')
    require(tv['nonfinite']==tv['missing_positions']==0,'TV missing/nonfinite')
    require(tv['vocab_chunks']==current['vocab_chunks'],'full vocabulary chunk identity')
    for key in ['tv','probability_mass_current','probability_mass_reference']:
        require(len(tv[key])==T and all(math.isfinite(x) for x in tv[key]),'complete finite per-position '+key)
    require(all(0<=x<=1+1e-10 for x in tv['tv']),'TV range')
    defects=[abs(x-1) for key in ['probability_mass_current','probability_mass_reference'] for x in tv[key]]
    require(max(defects)<=1e-10,'probability mass normalization')
    require(math.isclose(math.fsum(tv['tv'])/T,tv['document_mean'],abs_tol=1e-15,rel_tol=1e-13) and max(tv['tv'])==tv['document_max'],'TV document aggregation')
    raw=new_directory/'logit_raw_audit.npz';raw_result=None
    require((new_audit is None)==(old_audit is None),'same preselected raw-audit population')
    if raw.exists():
        require(new_audit is not None and old_audit is not None,'raw audit manifests required')
        new_manifest=read(verify(new_audit));old_manifest=read(verify(old_audit))
        require(verify(new_manifest['raw']).resolve()==raw.resolve(),'canonical current raw audit file')
        old_raw=verify(old_manifest['raw']);require(old_raw.resolve()==(old_directory/'logit_raw_audit.npz').resolve(),'canonical baseline raw audit file')
        with np.load(raw,allow_pickle=False) as data,np.load(old_raw,allow_pickle=False) as previous:
            require(set(data.files)==set(previous.files)==set(new_manifest['arrays'])==set(old_manifest['arrays']),'old/new raw array membership')
            for name in data.files:
                left=data[name];right=previous[name]
                require(left.dtype==right.dtype and left.shape==right.shape and left.tobytes()==right.tobytes(),'old/new raw array byte equality: '+name)
                for array,manifest in [(left,new_manifest),(right,old_manifest)]:
                    spec=manifest['arrays'][name];require(str(array.dtype)==spec['dtype'] and list(array.shape)==spec['shape'] and hashlib.sha256(array.tobytes()).hexdigest()==spec['sha256'],'raw array manifest identity: '+name)
            positions=data['token_positions'].tolist();values,raw_defect=independent(data['logits_current'],data['logits_reference'])
            differences=[abs(x-tv['tv'][t]) for t,x in zip(positions,values)]
            require(max(differences)<=1e-12,'independent raw TV mismatch')
            require(tv['second_pass_raw_equal'] is True and tv['second_pass_witness_positions']==positions,'two-pass raw equality missing')
            raw_result=dict(doc_id=current['doc_id'],positions=positions,raw=identity(raw),independent_tv=values,max_absolute_difference=max(differences),max_independent_mass_defect=raw_defect,old_raw_equal=True,old_raw_source=identity(old_raw),equal_arrays=sorted(data.files),comparison='Every saved raw array dtype/shape/bytes exact; all selected full-vocabulary logits included')
    require(current['doc_id']==read(new_directory/'document_result.json')['doc_id'],'document identity')
    return current,tv,max(defects),raw_result

def statistics(values):
    values=np.asarray(values,dtype=np.float64);require(values.size>0 and np.isfinite(values).all(),'finite nonempty descriptive distribution')
    q=np.quantile(values,[.5,.95,.99],method='linear')
    return dict(n=int(values.size),p50=float(q[0]),p95=float(q[1]),p99=float(q[2]),max=float(values.max()),mean=float(values.mean()),units='TV probability mass fraction',quantile_method='NumPy linear empirical quantile; descriptive')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path);p.add_argument('--baseline-plan',type=Path);p.add_argument('--baseline-aggregate',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--pilot',type=Path);p.add_argument('--pilot-baseline',type=Path);a=p.parse_args(argv);begin=time.monotonic();out=a.output_dir
    require(not out.exists() or not any(out.iterdir()),'new empty audit/aggregate directory');out.mkdir(parents=True,exist_ok=True)
    if a.pilot:
        new=sorted(a.pilot.glob('documents/doc*'));old=sorted(a.pilot_baseline.glob('documents/doc*'));require(len(new)==len(old)==4,'fixed four development docs')
        rows=[];raw=[]
        for n,o in zip(new,old):
            row,tv,defect,witness=audit_pair(n,o,formal=False);rows.append(dict(doc_id=row['doc_id'],tokens=row['tokens'],mean_tv=tv['document_mean'],max_tv=tv['document_max'],mass_defect=defect))
            if witness:raw.append(witness)
        dump(out/'pilot_independent_tv_and_baseline.json',dict(execution_state='completed',documents=rows,raw_witnesses=raw,all_old_head_metrics_and_final_hidden_equal=True,wall_seconds=time.monotonic()-begin,scope='four development documents, not formal1024',source=identity(__file__)))
        return 0
    require(all([a.plan,a.baseline_plan,a.baseline_aggregate]),'formal plans and reviewed aggregate required')
    plan=read(a.plan);require(verify(plan['baseline_plan']).resolve()==a.baseline_plan.resolve(),'canonical frozen baseline plan')
    require(verify(plan['baseline_aggregate']).resolve()==a.baseline_aggregate.resolve(),'canonical frozen reviewed baseline aggregate')
    baseline=read(a.baseline_plan);session=Path(plan['session_directory']);receipt=read(session/'session_gpu_receipt.json')
    global_analysis=read(session/'analysis_manifest.json');require(global_analysis['schema']=='m005_r006_analysis_manifest_v1' and global_analysis['model_execution_complete'] and global_analysis['completed_documents']==global_analysis['expected_documents']==1024 and global_analysis['missing_doc_ids']==[],'canonical full global analysis')
    require(verify(global_analysis['plan']).resolve()==a.plan.resolve() and global_analysis['plan']==identity(a.plan),'frozen plan identity binding')
    require(global_analysis['actual_doc_ids']==global_analysis['expected_doc_ids']==plan['expected_doc_ids'],'global target roster')
    shared=receipt['shared_worker_identity'];require(shared==global_analysis['shared_worker_identity'],'one canonical shared worker')
    for key,name in [('session_gpu_receipt','session_gpu_receipt.json'),('session_launch_manifest','session_launch_manifest.json')]:require(verify(global_analysis[key]).resolve()==(session/name).resolve(),'canonical global '+key)
    require(read(session/'session_launch_manifest.json')['shared_worker_identity']==shared,'global actual launch shared process')
    frozen_auditors={item['path']:item['sha256'] for command in plan['finalize_commands'] for item in command['source_identities']}

    require(receipt['execution_state']=='completed' and receipt['native_exit_code']==receipt['exit_code']==0 and receipt['worker_reaped'] and receipt['source_unchanged'] and receipt['stop_reason'] is None,'full GPU completed native0/reaped/source unchanged')
    require(plan['expected_doc_ids']==baseline['expected_doc_ids'] and len(set(plan['expected_doc_ids']))==1024,'frozen full1024 roster')
    require(len(plan['groups'])==len(baseline['groups'])==64,'frozen64 groups')
    documents=[];raw_results=[];source=[];audits=[];maxdefect=0.;position_records=[];underflows={'current':0,'reference':0}
    for group,prior in zip(plan['groups'],baseline['groups']):
        require(group['doc_ids']==prior['doc_ids'] and group['actual_token_lengths']==prior['actual_token_lengths'],'same ordered group input')
        path=Path(group['attempt_path']);base=Path(prior['attempt_path']);group_receipt=read(path/'execution_receipt.json')
        require(group_receipt['execution_state']=='completed' and group_receipt['coverage_complete'] and group_receipt['source_unchanged'],'successful complete group segment')
        require(group_receipt['doc_ids']==group_receipt['completed_doc_ids']==group['doc_ids'] and group_receipt['shared_worker_identity']==shared,'group exact roster/shared identity')
        require(Path(group_receipt['canonical_group_path']).resolve()==path.resolve() and Path(group_receipt['session_path']).resolve()==session.resolve(),'canonical group path')
        matching=[g for g in global_analysis['ordered_groups'] if g['group_id']==group['group_id']]
        require(len(matching)==1 and Path(matching[0]['attempt_path']).resolve()==path.resolve() and verify(matching[0]['receipt']).resolve()==(path/'execution_receipt.json').resolve(),'group global roster/hash')
        for item in group_receipt['code']+group_receipt['input_identities']+group_receipt['output_identities']:verify(item)
        for kind in ['core','extended']:
            evidence=Path(plan['tv_audit_directory'])/(group['group_id']+'_'+kind+'.json');value=read(evidence)
            require(value['execution_state']=='completed' and Path(value['attempt']).resolve()==path.resolve(),'independent canonical '+kind+' audit')
            require(value['formal_eval_documents']==len(group['doc_ids']) and value['audit_doc_ids']==group['audit_doc_ids'],'audit exact formal/rawdoc scope')
            key='final_norm_by_doc' if kind=='core' else 'documents'
            require([d['doc_id'] for d in value[key]]==group['doc_ids'],'audit exact ordered document membership')
            source_id=value['source_identity'];verify(source_id);require(frozen_auditors.get(source_id['path'])==source_id['sha256'],'frozen auditor source SHA')
            if kind=='core':
                adapter=value['adapter_source_identity'];verify(adapter);require(frozen_auditors.get(adapter['path'])==adapter['sha256'],'frozen core adapter SHA')
            runtime=value['runtime_binding'];require(runtime['shared_worker_identity']==shared and runtime['shared_process'] and Path(runtime['canonical_group']).resolve()==path.resolve() and Path(runtime['session']).resolve()==session.resolve(),'audit canonical runtime binding')
            for binding,expected in [('group_receipt',path/'execution_receipt.json'),('global_receipt',session/'session_gpu_receipt.json'),('global_launch',session/'session_launch_manifest.json'),('analysis_manifest',session/'analysis_manifest.json')]:require(verify(runtime[binding]).resolve()==expected.resolve(),'audit hash binding '+binding)
            if kind=='extended':require(verify(value['core_audit']).resolve()==(Path(plan['tv_audit_directory'])/(group['group_id']+'_core.json')).resolve(),'extension-to-core actual audit hash')
            audits.append(identity(evidence))
        for i,docid in enumerate(group['doc_ids']):
            directory=path/'documents'/f'doc{i:04d}';old_directory=base/'documents'/f'doc{i:04d}'
            row,tv,defect,witness=audit_pair(directory,old_directory);require(row['doc_id']==docid,'formal doc order')
            maxdefect=max(maxdefect,defect)
            doc=dict(doc_id=docid,domain=row['domain'],tokens=row['tokens'],tv=tv['tv'],mean_tv=tv['document_mean'],max_tv=tv['document_max'],mass_defect=defect,
                final_hidden_identity=row['final_hidden_identity'],old_head_metrics_equal=True)
            documents.append(doc)
            if witness:raw_results.append(witness)
            for t,value in enumerate(tv['tv']):position_records.append(dict(doc_id=docid,domain=row['domain'],position=t,tv=value,tv_percent=100*value,probability_mass_current=tv['probability_mass_current'][t],probability_mass_reference=tv['probability_mass_reference'][t]))
            for arm in underflows:underflows[arm]+=tv['natural_exp_underflow_entries_'+arm]
            source.extend([identity(directory/'logit_metrics.json'),identity(old_directory/'logit_metrics.json'),identity(directory/'document_result.json')])
    require([d['doc_id'] for d in documents]==plan['expected_doc_ids'] and sum(d['tokens'] for d in documents)==103700,'all103700 real positions')
    require(len(raw_results)==15 and sum(len(w['positions']) for w in raw_results)==45,'same preselected15 rawdocs45rows')
    domain_counts={domain:sum(d['domain']==domain for d in documents) for domain in sorted({d['domain'] for d in documents})}
    require(sorted(domain_counts.values())==[256,256,512],'fixed domain quotas')
    distributions={}
    for domain in ['fixed_quota_pool',*domain_counts]:
        docs=documents if domain=='fixed_quota_pool' else [d for d in documents if d['domain']==domain]
        distributions[domain]=dict(documents=len(docs),document_mean_tv=statistics([d['mean_tv'] for d in docs]),document_max_tv=statistics([d['max_tv'] for d in docs]),
            position_weighted_tv=statistics([t for d in docs for t in d['tv']]))
    tvdata=dict(schema='m005_r006_complete_softmax_tv_aggregate_v2',execution_state='completed',target_complete=True,documents=documents,measured_documents=1024,real_positions=103700,vocabulary=128256,score_pairs=103700*128256,domain_counts=domain_counts,
        distributions=distributions,max_probability_mass_defect=maxdefect,natural_exp_underflow_entries=underflows,raw_independent_audit=raw_results,old_head_metrics_and_final_hidden_equal_all1024=True,old_head_comparison_excluded_fields=['raw_audit: new-run artifact identity/path only; no numeric head fields excluded'],
        noncomparable_runtime_fields='Document/worker elapsed times, launch timestamps and process identities are separately recorded, never claimed equal to R005',
        pooling='Document means and maxima: document is statistical unit; fixed quota pool descriptive only. Position distribution explicitly length weighted; positions/vocabulary not independent documents.',
        units='TV fractions in data; percent100*TV represents probability mass, not relative L2 percent',source=source,accepted_independent_audits=audits,
        source_identity=identity(__file__),plan=identity(a.plan),baseline_plan=identity(a.baseline_plan),global_gpu_receipt=identity(session/'session_gpu_receipt.json'),wall_seconds=time.monotonic()-begin,
        limitations='Single model,max128 real tokens,32layer prefill,fixed shared text prefixes. No taskACC/PPL,free generation or universal fidelity threshold. Full1024 production probabilities measured; independent full-V raw recomputation only45 positions/15 preselected docs.')
    dump(out/'tv_aggregate.json',tvdata)
    for filename,rows in [('per_position_tv.csv',position_records),('per_document_tv.csv',[{k:d[k] for k in ['doc_id','domain','tokens','mean_tv','max_tv','mass_defect']} for d in documents])]:
        with (out/filename).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    original=read(a.baseline_aggregate);require(original['target_complete'] and original['measured_documents']==1024,'reviewed complete prior aggregate')
    require({d['doc_id']:d['tokens'] for d in original['documents']}=={d['doc_id']:d['tokens'] for d in documents},'old13column document/token identity; retained original display order')
    integrated=copy.deepcopy(original);integrated['schema']='m005_r006_integrated_precision_aggregate_v2';integrated['softmax_tv']=tvdata
    integrated['r006_provenance']=dict(previous13column_logitcoverage_top1_source=identity(a.baseline_aggregate),tv_source=identity(out/'tv_aggregate.json'),merge_requirement='All1024 old head metrics and finalhidden SHA exact equality; no old raw files changed')
    dump(out/'integrated_aggregate.json',integrated)
    summary=distributions['fixed_quota_pool']
    (out/'report.md').write_text('# R006 Softmax TV measurement\n\nExecution completed:1024 documents,103700 real positions,128256 full vocabulary,temperature1. All1024 finalhidden identities and old head metrics exactly match frozen R005.\n\nDocument mean TV distribution:'+json.dumps(summary['document_mean_tv'])+'\n\nDocument maximum TV distribution:'+json.dumps(summary['document_max_tv'])+'\n\nMaximum probability mass defect:'+str(maxdefect)+'; independent raw witness rows45 in15 preselected documents.\n\nTV percent means100×probability mass fraction. Fixed quota descriptive statistics only; position weighted distribution separately stored. No taskACC/PPL or free-generation claim.\n')
    dump(out/'output_manifest.json',dict(aggregate=identity(out/'integrated_aggregate.json'),tv=identity(out/'tv_aggregate.json'),csv=[identity(out/'per_position_tv.csv'),identity(out/'per_document_tv.csv')],report=identity(out/'report.md')))
    print(json.dumps(dict(execution_state='completed',documents=1024,positions=103700,raw_rows=45,max_mass_defect=maxdefect,document_mean=summary['document_mean_tv'],document_max=summary['document_max_tv'])))
    return 0

if __name__=='__main__':raise SystemExit(main())
