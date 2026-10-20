"""Existing same-coordinate residual/MLP paired energy decomposition; CPU only."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,math
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');OUT=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R011/independent_review'
def ident(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def quant(xs):
 a=np.array(xs,dtype=np.float64);assert np.isfinite(a).all()
 return {str(q):float(np.quantile(a,q))for q in(.5,.95,.99,1.)}
def main():
 old=OUT/'existing_stage_review.json';review=json.loads(old.read_text());st=defaultdict(dict);sources=[];ops={'mlp_residual_input_propagation','mlp_branch_propagation','mlp_residual_sum_propagation'}
 for spec in review['sources']:
  p=Path(spec['path'])
  if p.name!='mlp_metrics.jsonl':continue
  h=hashlib.sha256()
  with p.open('rb')as f:
   for line in f:
    h.update(line)
    if b'"layer": 31,'not in line:continue
    x=json.loads(line)
    if x['layer']==31 and x['op']in ops:
     assert x['arm']=='paired'and x['trajectory']=='v5_free_paired';st[x['doc_id']][x['op']]=x
  assert h.hexdigest()==spec['sha256'];sources.append(spec)
 assert len(st)==1024
 rows=[];u=2.**-24
 for doc,items in st.items():
  assert set(items)==ops
  ar=items['mlp_residual_input_propagation'];br=items['mlp_branch_propagation'];fr=items['mlp_residual_sum_propagation'];a=ar['metrics'];b=br['metrics'];f=fr['metrics'];N=a['total_elements'];assert N==b['total_elements']==f['total_elements']
  Ea,Eb,Ef=[m['error_energy']for m in(a,b,f)];Sa,Sb,Sf=[m['signal_energy']for m in(a,b,f)];Ce=(Ef-Ea-Eb)/2;Cs=(Sf-Sa-Sb)/2;Ce_saved=fr['metadata']['residual_branch_error_inner_product']
  add_energy_remainder=Ef-Ea-Eb-2*Ce_saved
  err_cos=Ce_saved/math.sqrt(Ea*Eb);err_cos_recovered=Ce/math.sqrt(Ea*Eb);sig_cos=Cs/math.sqrt(Sa*Sb)
  # IEEE FP32 residual-add rounding bounds; tiny absolute term covers subnormals.
  tiny=math.sqrt(N)*2.**-150;signal_add_bound=u*(math.sqrt(Sa)+math.sqrt(Sb))+tiny
  signal_cross_bias_bound=(math.sqrt(Sa)+math.sqrt(Sb))*signal_add_bound+.5*signal_add_bound**2
  pair_add_bound=u*(2*math.sqrt(Sa)+2*math.sqrt(Sb)+math.sqrt(Ea)+math.sqrt(Eb))+2*tiny
  error_cross_bias_bound=(math.sqrt(Ea)+math.sqrt(Eb))*pair_add_bound+.5*pair_add_bound**2
  assert abs(Ce-Ce_saved)<=error_cross_bias_bound+1e-10 and abs(err_cos)<=1+1e-12 and abs(sig_cos)<=1+signal_cross_bias_bound/math.sqrt(Sa*Sb)
  ma=a['signed_error_sum'];mb=b['signed_error_sum'];ve=Ea-ma*ma/N;vb=Eb-mb*mb/N
  pearson=(Ce_saved-ma*mb/N)/math.sqrt(ve*vb) if ve>0 and vb>0 else None
  row={'doc_id':doc,'scalar_count':N,'Ea':Ea,'Em':Eb,'Ef':Ef,'Sa':Sa,'Sm':Sb,'Sf':Sf,'error_cross_recovered':Ce,'error_cross_saved_direct':Ce_saved,'signal_cross_recovered':Cs,'error_cosine_direct':err_cos,'error_cosine_recovered':err_cos_recovered,'error_Pearson_centered':pearson,'signal_cosine_recovered':sig_cos,'signal_Pearson_centered':None,'error_energy_terms_over_final':{'attention_residual':Ea/Ef,'MLP_branch':Eb/Ef,'cross_saved':2*Ce_saved/Ef,'FP32_addition_identity_remainder':add_energy_remainder/Ef},'signal_energy_terms_over_final':{'attention_residual':Sa/Sf,'MLP_branch':Sb/Sf,'cross_recovered_including_add_rounding':2*Cs/Sf},'error_cancellation_fraction_of_component_sum':-2*Ce_saved/(Ea+Eb),'signal_cancellation_fraction_of_component_sum':-2*Cs/(Sa+Sb),'FP32_addition_error_energy_identity_remainder':add_energy_remainder,'signal_cross_FP32_rounding_absolute_bias_bound':signal_cross_bias_bound,'error_cross_recovery_FP32_rounding_absolute_bias_bound':error_cross_bias_bound}
  rows.append(row)
 sums={k:math.fsum(r[k]for r in rows)for k in('Ea','Em','Ef','Sa','Sm','Sf','error_cross_saved_direct','FP32_addition_error_energy_identity_remainder')}
 Ea,Em,Ef=[sums[k]for k in('Ea','Em','Ef')];Sa,Sm,Sf=[sums[k]for k in('Sa','Sm','Sf')];Ce=sums['error_cross_saved_direct'];Cs=(Sf-Sa-Sm)/2
 pooled={**sums,'error_cross_recovered':(Ef-Ea-Em)/2,'signal_cross_recovered':Cs,'error_cosine_direct':Ce/math.sqrt(Ea*Em),'signal_cosine_recovered':Cs/math.sqrt(Sa*Sm),'error_cancellation_fraction_of_component_sum':-2*Ce/(Ea+Em),'signal_cancellation_fraction_of_component_sum':-2*Cs/(Sa+Sm),'error_energy_terms_over_final':{'attention_residual':Ea/Ef,'MLP_branch':Em/Ef,'cross_saved':2*Ce/Ef,'FP32_addition_identity_remainder':sums['FP32_addition_error_energy_identity_remainder']/Ef},'signal_energy_terms_over_final':{'attention_residual':Sa/Sf,'MLP_branch':Sm/Sf,'cross_recovered':2*Cs/Sf},'relative_L2_percent':100*math.sqrt(Ef/Sf),'uncorrelated_component_energy_baseline_relative_L2_percent':100*math.sqrt((Ea+Em)/(Sa+Sm)),'signal_cross_FP32_rounding_absolute_bias_bound_sum':math.fsum(r['signal_cross_FP32_rounding_absolute_bias_bound']for r in rows)}
 dist={k:quant([r[k]for r in rows])for k in('error_cosine_direct','error_cosine_recovered','error_Pearson_centered','signal_cosine_recovered','error_cancellation_fraction_of_component_sum','signal_cancellation_fraction_of_component_sum','FP32_addition_error_energy_identity_remainder')}
 counts={'signal_cross_negative':sum(r['signal_cross_recovered']<0 for r in rows),'error_cross_negative':sum(r['error_cross_saved_direct']<0 for r in rows),'signal_more_cancellation_than_error':sum(r['signal_cancellation_fraction_of_component_sum']>r['error_cancellation_fraction_of_component_sum']for r in rows)}
 output={'execution_state':'completed','scope':'Existing 1024 documents, layer31, same aligned4096-channel paired residual/MLP/sum stages; no intervention/GPU','definitions':{'Ea':'sum||current second-residual base - reference second-residual base||²','Em':'sum||current MLP branch - reference MLP branch||²','Ef':'sum||actual current FP32 residual sum - actual reference FP32 residual sum||²','signal':'reference path vectors at corresponding stages','cross_recovered':'(sum_energy-component_energies)/2; includes FP32 addition contribution','cosine':'uncentered cross/sqrt(component energies), not a Pearson coefficient','signal_Pearson':'Unavailable: component reference signed sums were not saved. Error centered Pearson is available from signed_error_sum.'},'pooled':pooled,'per_document_distributions':dist,'counts':counts,'per_document':rows,'limitations':['Algebraic energy terms are signed descriptive terms, not causal percentages of rounding sources.','Different stage dimensions must not be ranked by total energy; these three stages share coordinates and units.','Signal recovered cross includes reference FP32-add rounding. Its magnitude is bounded using u=2^-24 plus subnormal absolute term.','Error saved direct cross permits a measured scalar energy-identity remainder. That remainder equals2<ea+em,delta_add>+||delta_add||² and is not the add-round error energy alone.','No full1024 residual/branch raw vectors exist to measure add-round vector norm exactly; conservative bounds are supplied.'],'sources':sources,'prior_stage_review':ident(old),'script':ident(Path(__file__))}
 path=OUT/'residual_cross_review.json';path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print('POOLED',json.dumps(pooled));print('DIST',json.dumps(dist));print('COUNTS',counts);print('sha256',ident(path)['sha256'])
if __name__=='__main__':main()
