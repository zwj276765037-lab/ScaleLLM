"""CPU-only raw validation of R011 v2 saved stages/cuts, without model execution."""
from pathlib import Path
import hashlib,json,math
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');R=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R011';AT=R/'attempts/AT002_singleblock_fourway_v2';O=R/'independent_review'
def identity(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def close(x,y):return math.isclose(x,y,rel_tol=3e-12,abs_tol=1e-14)
def load(p):
 with np.load(p,allow_pickle=False)as z:return {k:z[k].copy()for k in z.files}
def calc(a,b):
 a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);d=a-b;E=float(np.sum(d*d));S=float(np.sum(b*b));N=d.size
 return {'count':N,'error_energy':E,'signal_energy':S,'current_signal_energy':float(np.sum(a*a)),'absolute_rmse':math.sqrt(E/N),'reference_rms':math.sqrt(S/N),'relative_l2_percent':100*math.sqrt(E/S)if S else None,'max_absolute_error':float(np.max(np.abs(d))),'max_reference_magnitude':float(np.max(np.abs(b))),'changed_count':int(np.count_nonzero(d))}
def compare(gold,saved):
 for k,x in gold.items():
  if x is None:assert saved[k]is None
  elif isinstance(x,int):assert x==saved[k],(k,x,saved[k])
  else:assert close(x,saved[k]),(k,x,saved[k])
def main():
 manifest=json.loads((AT/'manifest.json').read_text());result=json.loads((AT/'result.json').read_text());wait=json.loads((AT/'external_wait_receipt.json').read_text())
 assert result['execution_state']=='completed'and result['documents']==3 and result['tokens']==299 and result['source_unchanged']and result['all_R006_hidden_and_dynamic_parity_passed']
 assert wait['native_exit_code']==0 and wait['child_reaped']and wait['actual_parent_waitpid']and wait['worker_proc_absent']
 for src in manifest['source']:assert identity(Path(src['path']))['sha256']==src['sha256']
 hashes={Path(x['path']).name:x['sha256']for x in manifest['source']}
 assert hashes['r011_single_block_v2.py']=='642061cffaa7a36e70f265abc09b9fb05c21908172b6ae7a7d7fd6643b0d160b'and hashes['r011_run_diagnostic_v2.py']=='f81ceb4ab4f8f19b4b8c2a53fb4af5cbd560f0b2cf7aec1bc4f7f1af4ba6f618'
 assert json.loads((AT/'cpu_qualification.json').read_text())['large_int32_to_S35_observer_probe']
 qual=json.loads((AT/'gpu_qualification.json').read_text());assert qual['passed']and qual['native_vs_observed_bitwise_equal']and qual['named_stage_count']==36 and qual['exception_restoration']and qual['buffers_unchanged']
 docs=manifest['documents'];assert len(docs)==3 and len({d['doc_id']for d in docs})==3
 pairs={'AB_cross':('A','B'),'AC_same_input_local':('A','C'),'CB_inherited':('C','B'),'DB_same_reference_input_local':('D','B'),'AD_inherited_current_arithmetic':('A','D')}
 checked_metrics=checked_decompositions=dynamic_files=old_output_arrays=0;rows=[];cuts=[];residuals=[]
 for doc in docs:
  directory=AT/'documents'/f'doc{doc["index"]:03d}';s=json.loads((directory/'primary_summary.json').read_text());stage={r['stage']:r for r in s['stages']};tr={};bits={}
  dm=json.loads((directory/'document_manifest.json').read_text())
  for src in dm['files']:assert identity(Path(src['path']))['sha256']==src['sha256']
  for arm in 'ABCD':
   tr[arm]=load(directory/f'{arm}_trace.npz');md=json.loads((directory/f'{arm}_trace_metadata.json').read_text());bits[arm]=md['bits']
   for name in md['saved_stages']:
    a=tr[arm][name];spec=md['all_stage_identity'][name];assert list(a.shape)==spec['shape']and str(a.dtype)==spec['dtype']and hashlib.sha256(a.tobytes()).hexdigest()==spec['sha256']
   if arm in 'AB':
    inp='current'if arm=='A'else'reference';oldinputs=load(Path(doc['input']['path']));oldout=load(Path(doc['saved_output']['path']));oldfinal=load(Path(doc['directory'])/f'final_hidden_{inp}.npz')
    assert np.array_equal(tr[arm]['input'],oldinputs[inp])and np.array_equal(tr[arm]['final_residual'],oldout[inp])and np.array_equal(tr[arm]['final_norm'],oldfinal['hidden']);old_output_arrays+=3
    for name in md['dynamic_coordinates']:
     if name=='silu':continue
     typ='prepare_fixed_activation'if name.startswith('prepare')else'_kv12_quantize';ordinal=int(name[-1]);p=Path(doc['directory'])/f'dynamic_{inp}_layer31_{typ}_{ordinal:02d}.npz';gold=load(p)
     assert all(np.array_equal(tr[arm][f'dynamic__{name}__{k}'],a)for k,a in gold.items());dynamic_files+=1
  def real(arm,name):return tr[arm][name].astype(np.float64)*2.**(-bits[arm][name])
  for name,row in stage.items():
   for key,(a,b)in pairs.items():
    if name in tr[a]and name in tr[b]:compare(calc(real(a,name),real(b,name)),row['comparisons'][key]);checked_metrics+=1
   if'decomposition'in row and all(name in tr[a]for a in 'ABC'):
    a,b,c=[real(arm,name)for arm in 'ABC'];full=a-b;local=a-c;inherited=c-b;E=float(np.sum(full*full));L=float(np.sum(local*local));I=float(np.sum(inherited*inherited));X=2*float(np.sum(local*inherited));d=row['decomposition']
    for k,v in {'total_error_energy':E,'same_input_local_error_energy':L,'inherited_input_error_energy':I,'cross_term':X,'energy_identity_residual':E-L-I-X,'vector_identity_max_absolute':float(np.max(np.abs(full-local-inherited)))}.items():assert close(v,d[k])
    checked_decompositions+=1
  for label,left,branch,total in [('attention','input','attention_output','attention_residual'),('mlp','attention_residual','mlp_output','final_residual')]:
   Lc,Lr=real('A',left),real('B',left);Mc,Mr=real('A',branch),real('B',branch);Fc,Fr=real('A',total),real('B',total);eL=Lc-Lr;eM=Mc-Mr;eF=Fc-Fr;add=eF-eL-eM;rr=s['residual_decomposition'][label]
   gold={'input_error_energy':float(np.sum(eL*eL)),'branch_error_energy':float(np.sum(eM*eM)),'input_branch_error_cross':2*float(np.sum(eL*eM)),'output_error_energy':float(np.sum(eF*eF)),'FP32_addition_roundoff_difference_energy':float(np.sum(add*add)),'FP32_addition_roundoff_difference_max':float(np.max(np.abs(add))),'signal_left_energy':float(np.sum(Lr*Lr)),'signal_branch_energy':float(np.sum(Mr*Mr)),'signal_cross':2*float(np.sum(Lr*Mr)),'signal_output_energy':float(np.sum(Fr*Fr))}
   for k,v in gold.items():assert close(v,rr[k])
   sigmaC=Fc-(Lc+Mc);sigmaR=Fr-(Lr+Mr);assert np.max(np.abs(add-(sigmaC-sigmaR)))<=1e-12
   residuals.append({'doc_index':doc['index'],'stage':label,**gold})
  for cut in ('gated_product','down_proj'):
   raw=load(directory/f'cut_{cut}_outputs.npz');inter=json.loads((directory/f'cut_{cut}_summary.json').read_text())
   assert np.array_equal((tr['A']['attention_residual']+raw['mlp_output']).astype(np.float32),raw['final_residual'])
   if cut=='down_proj':assert np.array_equal(raw['mlp_output'],tr['B']['mlp_output'])and inter['FP32_residual_from_current_skip_plus_reference_branch_bitwise_equal']
   for name in ('mlp_output','final_residual','final_norm'):compare(calc(raw[name],tr['B'][name]),inter['comparisons'][name])
   compare(calc(tr['A']['attention_residual'],tr['B']['attention_residual']),inter['comparisons']['attention_residual'])
   baseline=calc(tr['A']['final_residual'],tr['B']['final_residual'])['error_energy'];reduction=100*(1-inter['comparisons']['final_residual']['error_energy']/baseline);assert close(reduction,inter['conditional_final_error_energy_reduction_percent'])
   cuts.append({'doc_index':doc['index'],'cut':cut,'conditional_error_energy_reduction_percent':reduction,'final_relative_l2_percent':inter['comparisons']['final_residual']['relative_l2_percent'],'current_skip_preserved_raw_checked':True,'reference_branch_bitwise_checked':cut=='down_proj'})
  selected={name:stage[name]for name in('input','attention_residual','gated_product','down_proj','mlp_output','final_residual','final_norm')};rows.append({'doc_index':doc['index'],'doc_id':doc['doc_id'],'stages':selected})
 summary={}
 for name in('input','attention_residual','gated_product','down_proj','mlp_output','final_residual','final_norm'):
  comps={}
  for key in pairs:
   E=math.fsum(x['stages'][name]['comparisons'][key]['error_energy']for x in rows);S=math.fsum(x['stages'][name]['comparisons'][key]['signal_energy']for x in rows);N=sum(x['stages'][name]['comparisons'][key]['count']for x in rows)
   comps[key]={'count':N,'error_energy':E,'reference_signal_energy':S,'absolute_rmse':math.sqrt(E/N),'reference_rms':math.sqrt(S/N),'pooled_relative_l2_percent':100*math.sqrt(E/S)if S else None}
  decomps={k:math.fsum(x['stages'][name]['decomposition'][k]for x in rows)for k in('total_error_energy','same_input_local_error_energy','inherited_input_error_energy','cross_term')};summary[name]={'comparisons':comps,'layer_entrance_decomposition':decomps}
 report={'execution_state':'completed','review':'limited_actual_three_document_single_block_evidence_verified','documents':3,'real_token_positions':299,'source_unchanged_verified':True,'native_exit0_parent_reaped':True,'dtype_patch':'raw.to(torch.int64) before FWHT/INV_SQRT32/half-away/S35 clamp; observed GPU qualification passed','prior_AT001_failure':'observer-only int32 reconstruction overflow, not a method result','saved_stage_metric_objects_recomputed':checked_metrics,'saved_ABC_stage_decompositions_recomputed':checked_decompositions,'old_R006_input_hidden31_final_arrays_bitwise_verified':old_output_arrays,'old_R006_dynamic_prepared_KV_files_bitwise_verified':dynamic_files,'residual_raw_FP32_add_roundoff_vectors_verified':residuals,'conditional_cuts_verified':cuts,'saved_stage_pooled_summary':summary,'limitations':['AC/DB same-input labels mean same layer entrance, not identical perstage inputs after earlier stage divergence.','B(Hr) teacher-forcing cuts also remove inherited input changes; improvement is not unique local-rounding causation.','Only raw saved subsets are independently recomputed:15 A/B stages and7 C/D stages; remaining36stage metrics retain source/hash provenance only.','Three predeclared diagnostic docs cannot establish full1024 intervention or ACC/PPL claims.'],'sources':[identity(AT/n)for n in('manifest.json','result.json','cpu_qualification.json','gpu_qualification.json','execution_receipt.json','external_wait_receipt.json')],'script':identity(Path(__file__))}
 p=O/'actual_singleblock_review.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('COUNTS',checked_metrics,checked_decompositions,old_output_arrays,dynamic_files);print('FINAL',json.dumps(summary['final_residual']));print('CUTS',json.dumps(cuts));print('sha256',identity(p)['sha256'])
if __name__=='__main__':main()
