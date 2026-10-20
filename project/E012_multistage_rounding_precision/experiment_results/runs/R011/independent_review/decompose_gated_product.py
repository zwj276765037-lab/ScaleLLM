"""Existing A/B gate product integer identity and signed energy terms; CPU only."""
from pathlib import Path
import hashlib,json,math
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');R=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R011';AT=R/'attempts/AT002_singleblock_fourway_v2';O=R/'independent_review'
NAMES=('up_ref_times_delta_silu','silu_ref_times_delta_up','delta_silu_times_delta_up')
def ident(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def energy(x):return float(np.sum(x*x,dtype=np.float64))
def main():
 docs=[];sources=[]
 for i in range(3):
  arrays={}
  for arm in('A','B'):
   p=AT/'documents'/f'doc{i:03d}'/f'{arm}_trace.npz'
   with np.load(p,allow_pickle=False)as z:arrays[arm]={k:z[k].astype(np.int64).reshape(-1)for k in('silu','up_proj','gated_product')}
   sources.append(ident(p))
  sa,ua,pa=[arrays['A'][k]for k in('silu','up_proj','gated_product')];sb,ub,pb=[arrays['B'][k]for k in('silu','up_proj','gated_product')];N=sa.size
  assert all(x.size==N for arm in arrays.values()for x in arm.values())
  assert max(int(np.max(np.abs(x)))for x in(sa,sb,ua,ub))<(1<<24)
  na=sa*ua;nb=sb*ub;ds=sa-sb;du=ua-ub;nums=[ub*ds,sb*du,ds*du]
  assert max(int(np.max(np.abs(x)))for x in nums)<np.iinfo(np.int64).max//4
  reconstruction=nums[0]+nums[1]+nums[2];exact_num=na-nb
  assert np.array_equal(reconstruction,exact_num)
  for n,p in[(na,pa),(nb,pb)]:
   expected=np.where(n>=0,(n+32768)//65536,-((-n+32768)//65536));assert np.array_equal(expected,p)
  observed_num=(pa-pb)*65536;round_num=observed_num-exact_num
  assert np.max(np.abs(round_num))<=65536 and np.array_equal(reconstruction+round_num,observed_num)
  terms=[x.astype(np.float64)/(1<<32)for x in nums];exact=exact_num.astype(np.float64)/(1<<32);observed=observed_num.astype(np.float64)/(1<<32);rounding=round_num.astype(np.float64)/(1<<32)
  E=[energy(x)for x in terms];X={f'{j+1}_{k+1}':2*float(np.sum(terms[j]*terms[k]))for j in range(3)for k in range(j+1,3)};Renergy=energy(rounding);RX=2*float(np.sum(exact*rounding))
  measured=json.loads((AT/'documents'/f'doc{i:03d}'/'primary_summary.json').read_text());g=next(x for x in measured['stages']if x['stage']=='gated_product')['comparisons']['AB_cross']
  assert math.isclose(energy(observed),g['error_energy'],rel_tol=3e-12)and math.isclose(math.sqrt(energy(observed)/N),g['absolute_rmse'],rel_tol=3e-12)
  docs.append({'doc_index':i,'doc_id':measured['doc_id'],'count':N,'term_energies':dict(zip(NAMES,E)),'term_RMSE':{name:math.sqrt(e/N)for name,e in zip(NAMES,E)},'twice_cross_terms':X,'exact_unrounded_product_difference_energy':energy(exact),'actual_shared_exit_product_difference_energy':energy(observed),'actual_shared_exit_product_difference_RMSE':math.sqrt(energy(observed)/N),'shared_output_rounding_difference_energy':Renergy,'shared_output_rounding_difference_RMSE':math.sqrt(Renergy/N),'twice_exact_product_error_vs_rounding_cross':RX,'integer_unrounded_identity_max_residual':0,'integer_observed_identity_max_residual':0,'float_energy_identity_residual':energy(exact)-sum(E)-sum(X.values()),'float_observed_energy_identity_residual':energy(observed)-energy(exact)-Renergy-RX})
 N=sum(x['count']for x in docs);E={name:math.fsum(x['term_energies'][name]for x in docs)for name in NAMES};X={k:math.fsum(x['twice_cross_terms'][k]for x in docs)for k in('1_2','1_3','2_3')};P=math.fsum(x['exact_unrounded_product_difference_energy']for x in docs);actual=math.fsum(x['actual_shared_exit_product_difference_energy']for x in docs);roundE=math.fsum(x['shared_output_rounding_difference_energy']for x in docs);roundX=math.fsum(x['twice_exact_product_error_vs_rounding_cross']for x in docs)
 pooled={'count':N,'term_energies':E,'term_RMSE':{k:math.sqrt(v/N)for k,v in E.items()},'twice_cross_terms':X,'exact_unrounded_product_difference_energy':P,'exact_unrounded_product_difference_RMSE':math.sqrt(P/N),'actual_shared_exit_product_difference_energy':actual,'actual_shared_exit_product_difference_RMSE':math.sqrt(actual/N),'shared_output_rounding_difference_energy':roundE,'shared_output_rounding_difference_RMSE':math.sqrt(roundE/N),'twice_exact_product_error_vs_rounding_cross':roundX,'energy_identity_residual':P-math.fsum(E.values())-math.fsum(X.values()),'observed_energy_identity_residual':actual-P-roundE-roundX,'standalone_weighted_up_vs_weighted_silu_energy_ratio':E[NAMES[1]]/E[NAMES[0]]}
 result={'execution_state':'completed','scope':'Existing3 diagnostic documents/299positions,decoder31 A/B,all4286464 MLP product scalars; no GPU/model run','definitions':{'s':'shared production same-LUT SiLU reconstructed from actual gate code and verified by actual product exit','u':'actual Up projection F16 output','delta':'A minus B; A=current(Hcurrent),B=OUTPUT_ONLY(Hreference),so includes inherited inputs','exact_identity':'delta(s*u)=u_B*delta_s+s_B*delta_u+delta_s*delta_u','observed_identity':'delta(gated_product_F16)=three exact product terms + difference of shared half-away product出口 rounding errors','cross_terms':'twice inner products, may be negative; all terms use the same coordinates/units'},'pooled':pooled,'per_document':docs,'limitations':['Term standalone energies are not additive causal percentages; retain all signed cross terms.','This describes A/B product perturbation, not isolated SiLU or Up local-rounding error.','A/B SiLU stage is a production-input/LUT reconstruction, not analytic floating SiLU or hardware intermediate capture.','The larger standalone weighted term can be identified, but correlation can cancel or reinforce it; no unique whole32layer mechanism follows.'],'sources':sources,'script':ident(Path(__file__))}
 p=O/'gated_product_decomposition.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('POOLED',json.dumps(pooled));print('PERDOC',json.dumps([{k:d[k]for k in('doc_index','term_RMSE','twice_cross_terms')}for d in docs]));print('sha256',ident(p)['sha256'])
if __name__=='__main__':main()
