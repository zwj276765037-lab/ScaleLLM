"""Existing three-doc stage/dynamic evidence only; no model or GPU execution."""
from pathlib import Path
import hashlib,json,math
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');R=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R011';AT=R/'attempts/AT002_singleblock_fourway_v2';O=R/'independent_review'
def ident(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def main():
 prim=[json.loads((AT/'documents'/f'doc{i:03d}'/'primary_summary.json').read_text())for i in range(3)];stage_names=list(prim[0]['stages'][j]['stage']for j in range(36));stage={};dynamic=[]
 for name in stage_names:
  row={}
  for comparison in ('AB_cross','AC_same_input_local','CB_inherited'):
   m=[next(x for x in doc['stages']if x['stage']==name)['comparisons'][comparison]for doc in prim];E=math.fsum(x['error_energy']for x in m);S=math.fsum(x['signal_energy']for x in m);N=sum(x['count']for x in m)
   row[comparison]={'count':N,'changed_count':sum(x['changed_count']for x in m),'error_energy':E,'reference_signal_energy':S,'absolute_rmse':math.sqrt(E/N),'reference_rms':math.sqrt(S/N),'pooled_relative_l2_percent':100*math.sqrt(E/S)if S else None}
  stage[name]=row
 for coord,field in sorted({(x['coordinate'],x['field'])for d in prim for x in d['dynamic']}):
  m=[x for d in prim for x in d['dynamic']if(x['coordinate'],x['field'])==(coord,field)];N=sum(x['count']for x in m);ac=sum(x['AC_changed']for x in m);ab=sum(x['AB_changed']for x in m)
  dynamic.append({'coordinate':coord,'field':field,'denominator':N,'AC_changed':ac,'AC_percent':100*ac/N,'AB_changed':ab,'AB_percent':100*ab/N})
 # Independently reconstruct saved A8 physical values for the two MLP re-encodings.
 rebuilt={};address_differences=[];sources=[]
 for i in range(3):
  paths={a:AT/'documents'/f'doc{i:03d}'/f'{a}_trace.npz'for a in('A','C')};z={a:np.load(p,allow_pickle=False)for a,p in paths.items()}
  try:
   for which in ('prepare2','prepare3'):
    phys={};scale={}
    for arm in ('A','C'):
     get=lambda field:z[arm][f'dynamic__{which}__{field}']
     q=get('values_u8').astype(np.float64);zp=get('zero_points_u8').astype(np.float64);code=get('codes_u8').astype(np.float64);shift=get('shifts_u8').astype(np.int32)
     scale[arm]=np.ldexp(code,-shift);phys[arm]=(q-zp[...,None])*scale[arm][...,None]
    e=phys['A']-phys['C'];E=float(np.sum(e*e));S=float(np.sum(phys['C']*phys['C']));N=e.size
    point={'doc_index':i,'count':N,'physical_changed_count':int(np.count_nonzero(e)),'physical_error_energy':E,'physical_reference_energy':S,'physical_RMSE':math.sqrt(E/N),'physical_reference_RMS':math.sqrt(S/N),'physical_relative_L2_percent':100*math.sqrt(E/S),'scale_group_count':scale['A'].size,'physical_scale_changed_groups':int(np.count_nonzero(scale['A']!=scale['C']))}
    saved=next(x for x in prim[i]['stages']if x['stage']==which+'_dequant')['comparisons']['AC_same_input_local'];assert math.isclose(E,saved['error_energy'],rel_tol=2e-12)and math.isclose(S,saved['signal_energy'],rel_tol=2e-12)and point['physical_changed_count']==saved['changed_count'];rebuilt.setdefault(which,[]).append(point)
   addrA=z['A']['dynamic__silu__lut_address'].astype(np.int32);addrC=z['C']['dynamic__silu__lut_address'].astype(np.int32);d=np.abs(addrA-addrC);vals,counts=np.unique(d,return_counts=True);address_differences.append({'doc_index':i,'count':d.size,'absolute_address_difference_histogram':{str(v):int(c)for v,c in zip(vals,counts)}})
  finally:
   for x in z.values():x.close()
  sources.extend(ident(p)for p in paths.values())
 amp={}
 for which in ('prepare1','prepare2','prepare3'):
  before=stage[which+'_hadamard']['AC_same_input_local'];after=stage[which+'_dequant']['AC_same_input_local'];amp[which]={'before':before,'after':after,'RMSE_factor':after['absolute_rmse']/before['absolute_rmse'],'relative_L2_factor':after['pooled_relative_l2_percent']/before['pooled_relative_l2_percent'],'reference_RMS_factor':after['reference_rms']/before['reference_rms']}
 hist={}
 for item in address_differences:
  for key,value in item['absolute_address_difference_histogram'].items():hist[key]=hist.get(key,0)+value
 result={'execution_state':'completed','scope':'Only existing3 predeclared diagnostic docs/299positions; same layer entrance A/C, no GPU/model run','arm_definition':{'A':'CURRENT(Hcurrent)','B':'OUTPUT_ONLY(Hreference)','C':'OUTPUT_ONLY(Hcurrent)'},'stages':stage,'dynamic_representation_changes':dynamic,'MLP_A8_physical_reconstruction_independently_recomputed':rebuilt,'SiLU_absolute_address_difference_histogram':hist,'requantization_amplification_AC':amp,'interpretation':['A/C layer entrance, input norm and first prepare0 arrays are identical; small arithmetic changes later meet discontinuous existing quantizer thresholds.','Differences in quantized bytes, code, shift or zero point are representation changes; physical reconstructions must use(q-zero_point)*code*2^-shift. Independent physical error/RMS checks are included.','prepare3 Hadamard to dequant AC RMSE increases with essentially unchanged reference RMS; this is an observed physical-difference amplification, not only a denominator artifact.','The same quantizer rule is used in both paths. These data do not prove the quantizer is incorrectly implemented or that its local approximation loss alone is the cause.','SiLU address differences do not equal relative numerical error. Shared same-LUT and common product出口 rules remain; gated_product AC includes upstream input differences.','These3doc last-layer observations do not establish that dynamic quantization or signed floor accumulation dominates the complete32layer1024doc end-to-end discrepancy.','AC at internal stages is accumulated divergence from a common layer entrance, not perstage same-input local arithmetic error.','Whole-network weighted transforms, nonlinear functions, re-encoding and residual geometry prevent adding single-node relative percentages as if they were independent scalar errors.'],'sources':[ident(AT/'manifest.json'),*sources,*[ident(AT/'documents'/f'doc{i:03d}'/'primary_summary.json')for i in range(3)]],'script':ident(Path(__file__))}
 p=O/'accumulation_explanation.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('AMP',json.dumps(amp));print('SILU_ADDRESS_HIST',json.dumps(hist));print('PHYS',json.dumps(rebuilt));print('sha256',ident(p)['sha256'])
if __name__=='__main__':main()
