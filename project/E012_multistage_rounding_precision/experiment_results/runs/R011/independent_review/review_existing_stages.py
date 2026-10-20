"""Bounded CPU-only review of actual existing R006 paired stages, not interventions."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,math
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');RUNS=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs'
R6=RUNS/'R006';OUT=RUNS/'R011/independent_review'
def identity(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def summarize(rows):
 assert len(rows)==1024
 ans={'documents':len(rows),'scalar_outputs':sum(x['total_elements']for x in rows)}
 for key in ('relative_l2_percent','signal_rms','absolute_rmse','absolute_max'):
  a=np.array([r[key]for r in rows]);assert np.isfinite(a).all()
  ans[key]={str(q):float(np.quantile(a,q))for q in (.5,.95,.99,1.)}
 E=math.fsum(x['error_energy']for x in rows);S=math.fsum(x['signal_energy']for x in rows)
 ans.update(error_energy=E,reference_signal_energy=S,pooled_relative_l2_percent=100*math.sqrt(E/S))
 return ans

def main():
 mp=R6/'session_S001/analysis_manifest.json';manifest=json.loads(mp.read_text());expected=set(manifest['expected_doc_ids']);assert len(expected)==1024
 layers={i:{}for i in range(32)};stages=defaultdict(dict);local=defaultdict(dict);norm={};cross={};sources=[]
 paired={'mlp_residual_input_propagation','mlp_branch_propagation','mlp_residual_sum_propagation'}
 sameinput={'whole_mlp_local','mlp_fixed_residual_local'}
 for group in manifest['ordered_groups']:
  p=Path(group['attempt_path']);path=p/'tensor_metrics.jsonl';digest=hashlib.sha256()
  with path.open('rb')as f:
   for line in f:
    digest.update(line);x=json.loads(line);assert x['trajectory']=='v5_continuous_paired' and x['node']=='decoder_hidden';i=x['layer'];doc=x['doc_id'];assert doc not in layers[i];layers[i][doc]=x['metrics']['current_vs_reference']
  sources.append({'path':str(path),'sha256':digest.hexdigest()})
  path=p/'mlp_metrics.jsonl';digest=hashlib.sha256()
  with path.open('rb')as f:
   for line in f:
    digest.update(line)
    if b'"layer": 31,'not in line:continue
    x=json.loads(line)
    if x['layer']!=31:continue
    doc=x['doc_id'];op=x['op'];m=x['metrics']
    if op in paired:
     assert x['arm']=='paired'and x['trajectory']=='v5_free_paired' and doc not in stages[op];stages[op][doc]=m
     if op=='mlp_residual_sum_propagation':cross[doc]=x['metadata']['residual_branch_error_inner_product']
    elif op in sameinput:
     assert x['trajectory']=='same_input_local_shadow';local[op][doc]=m
  sources.append({'path':str(path),'sha256':digest.hexdigest()})
  for path in (p/'documents').glob('doc*/final_norm_comparison.json'):
   x=json.loads(path.read_text());assert x['trajectory']=='v5_continuous_paired';assert x['doc_id']not in norm;norm[x['doc_id']]=x['metrics']['current_vs_reference']
 for data in [*layers.values(),*stages.values(),*local.values(),norm]:assert set(data)==expected
 for doc in expected:
  a=layers[31][doc];b=stages['mlp_residual_sum_propagation'][doc]
  assert all(math.isclose(a[k],b[k],rel_tol=2e-12,abs_tol=1e-20)for k in ('error_energy','signal_energy','absolute_rmse','relative_l2_percent'))
 layer_stats={str(i+1):summarize(list(rows.values()))for i,rows in layers.items()}
 jumps=[]
 for i in range(1,32):
  per=[layers[i][d]['relative_l2_percent']-layers[i-1][d]['relative_l2_percent']for d in expected]
  jumps.append({'from_layer':i,'to_layer':i+1,'p95_curve_difference_percentage_points':layer_stats[str(i+1)]['relative_l2_percent']['0.95']-layer_stats[str(i)]['relative_l2_percent']['0.95'],'median_per_document_relative_change_percentage_points':float(np.median(per)),'documents_relative_error_increases':sum(x>0 for x in per)})
 staged={'layer31_input_previous_block':layer_stats['31'],**{op:summarize(list(v.values()))for op,v in stages.items()},'final_norm':summarize(list(norm.values()))}
 rows=[]
 for doc in sorted(expected):
  er=stages['mlp_residual_input_propagation'][doc]['error_energy'];eb=stages['mlp_branch_propagation'][doc]['error_energy'];es=stages['mlp_residual_sum_propagation'][doc]['error_energy'];crossv=cross[doc]
  rows.append({'doc_id':doc,'error_energy_before_layer32':layers[30][doc]['error_energy'],'error_energy_after_attention_residual':er,'MLP_branch_error_energy':eb,'error_energy_after_MLP_residual':es,'residual_branch_error_inner_product':crossv,'residual_addition_rounding_energy_identity_remainder':es-er-eb-2*crossv,'relative_change_layer31_to_32_percentage_points':layers[31][doc]['relative_l2_percent']-layers[30][doc]['relative_l2_percent']})
 summed={k:math.fsum(x[k]for x in rows)for k in rows[0]if k!='doc_id'}
 pooled_norm=norm
 norms_ratio=np.array([norm[d]['relative_l2_percent']/layers[31][d]['relative_l2_percent']for d in expected])
 r9path=RUNS/'R009/attempts/AT003_true_exit_precision_dev36/result.json';r9=json.loads(r9path.read_text())
 result={'scope':'Existing 1024-document fixed-quota descriptive paired-trajectory evidence only; no GPU/model/intervention','source_manifest':identity(mp),'sources':sources,'layers':layer_stats,'ranked_curve_jumps':sorted(jumps,key=lambda x:x['p95_curve_difference_percentage_points'],reverse=True),'layer32_existing_stages':staged,'same_input_local_MLP_separate':{k:summarize(list(v.values()))for k,v in local.items()},'paired_error_energy_decomposition_sums':summed,'paired_doc_rows':rows,'finalnorm_perdoc_relative_ratio_median':float(np.median(norms_ratio)),'missing_stages':['layer32 first RMSNorm input/output','attention branch before first residual sum','paired q/k/v projections, RoPE, KV quantization, QK, Softmax, PV, o_proj','paired post-attention RMSNorm output/MLP input','paired gate/up/SiLU/product/down internal stages'],'limitations':['Same-input local rows cannot locate a freely propagated error jump inside Attention.','Quantiles of stage distributions are not per-document causal contributions; percentage-point differences cannot be subtracted as additive attribution.','MLP error-energy decomposition is descriptive; cross term and FP32 residual-addition remainder retained.','R008 operator diagnostic was canceled before GPU and contributes no empirical intervention evidence.'],'R009_development_only':{'source':identity(r9path),'documents':36,'common_ref4':{arm:{key:r[key]['document_median_percent']for key in ('layer32_pre_norm','final_hidden','logits')}for arm,r in r9['common_fixed'].items()},'interpretation':'Only final o/down exit precision changed on repeated development docs; no broad improvement and not a1024 stage attribution.'},'script':identity(Path(__file__))}
 path=OUT/'existing_stage_review.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print('TOP_CURVE_JUMPS',json.dumps(result['ranked_curve_jumps'][:5]))
 for key,value in staged.items():print('STAGE',key,json.dumps(value))
 print('DECOMP',json.dumps(summed));print('LOCAL',json.dumps(result['same_input_local_MLP_separate']));print('NORM_RATIO',result['finalnorm_perdoc_relative_ratio_median']);print('sha256',identity(path)['sha256'])
if __name__=='__main__':main()
