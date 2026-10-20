"""Independent CPU validation of immutable R010 raw scalar audit; no model/GPU."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
import ast,hashlib,json,math,sys
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
S=ROOT/'project/software/0_Software/rounding_precision/experiment'
RUNS=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs'
AT=RUNS/'R010/attempts/AT001_original_two_exit_scalar_audit';OUT=RUNS/'R010/independent_review'
TH=[('0.1',1000),('1',100),('5',20),('10',10)]
def ident(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def equalfloat(x,y):return math.isclose(x,y,rel_tol=2e-12,abs_tol=1e-20)
def gold_away(x):
 a=abs(x);q,r=divmod(a.numerator,a.denominator)
 return (-1 if x<0 else 1)*(q+int(2*r>=a.denominator))
def ast_production_copy():
 prod=ast.parse((ROOT/'project/software/0_Software/FPtoQ/experiment/v5_fullchain.py').read_text())
 new=ast.parse((S/'rounding_optimization/r010_audit_kernels.py').read_text())
 p=next(f for f in prod.body if isinstance(f,ast.FunctionDef) and f.name=='_v5_grouped_linear_kernel')
 n=next(f for f in new.body if isinstance(f,ast.FunctionDef) and f.name=='_r010_observed_kernel')
 extra={'pre_exit_accumulator_ptr','active_shift_hist_ptr','nonzero_remainder_hist_ptr','discarded_one_bits_ptr'}
 names={'active_shift_hist','nonzero_remainder_hist','discarded_one_bits','observed_pair','safe_right','lost','active_bins','lost_bins','ones','hi'}
 class Prune(ast.NodeTransformer):
  def visit_Assign(self,node):return None if any(isinstance(t,ast.Name) and t.id in names for t in node.targets) else self.generic_visit(node)
  def visit_AugAssign(self,node):return None if isinstance(node.target,ast.Name) and node.target.id in names else self.generic_visit(node)
  def visit_Expr(self,node):
   if isinstance(node.value,ast.Call) and node.value.args and any(isinstance(t,ast.Name) and t.id in extra for t in ast.walk(node.value.args[0])):return None
   return self.generic_visit(node)
 n=Prune().visit(n);n.name=p.name;n.args.args=[a for a in n.args.args if a.arg not in extra]
 assert ast.dump(p,include_attributes=False)==ast.dump(n,include_attributes=False),'observed kernel arithmetic differs beyond observer exports'
 return True

def main():
 started=datetime.now(timezone.utc).isoformat();manifest=json.loads((AT/'manifest.json').read_text());result=json.loads((AT/'result.json').read_text());receipt=json.loads((AT/'execution_receipt.json').read_text())
 assert result['execution_state']=='completed' and result['source_unchanged'] and result['all_hard_checks_passed'] and receipt['native_exit_code']==0
 assert json.loads((AT/'gpu_qualification.json').read_text())['passed'] and json.loads((AT/'cpu_qualification.json').read_text())['passed']
 for e in manifest['source']:assert ident(Path(e['path']))['sha256']==e['sha256']
 source_ast=ast_production_copy();docs=manifest['documents'];assert len(docs)==15 and len({d['doc_id'] for d in docs})==15 and sum(d['tokens'] for d in docs)==1746
 records=[json.loads(s) for s in (AT/'operator_records.jsonl').read_text().splitlines()];assert len(records)==30
 assert {(x['doc_index'],x['op'])for x in records}=={(i,op)for i in range(15)for op in ('o_proj','down_proj')}
 count=0;sample_checks=0;checks=[];examples=[];threshold_tails={}
 for rec in records:
  doc=docs[rec['doc_index']];op=rec['op'];assert rec['doc_id']==doc['doc_id']
  raw=Path(rec['raw']['path']);assert ident(raw)['sha256']==rec['raw']['sha256']
  with np.load(raw,allow_pickle=False) as z:arr={k:z[k].copy() for k in z.files}
  assert set(arr)=={'accumulator','current_code','reference_code','exact_quotient','exact_remainder'}
  for k,a in arr.items():
   spec=rec['arrays'][k];assert list(a.shape)==spec['shape'] and str(a.dtype)==spec['dtype'] and hashlib.sha256(a.tobytes()).hexdigest()==spec['sha256']
  A=arr['accumulator'].astype(np.int64);C=arr['current_code'].astype(np.int64);R=arr['reference_code'].astype(np.int64);Q=arr['exact_quotient'].astype(np.int64);r=arr['exact_remainder'].astype(np.int64)
  bits=rec['common_bits'];D=1<<bits;N=C.size;assert N==rec['count']==doc['tokens']*4096 and bits==(31 if op=='o_proj' else 28)
  assert ((r>=0)&(r<D)).all();aq=A//256;ar=A-aq*256
  rounded=aq+np.where(aq>=0,ar>=128,ar>128).astype(np.int64)
  width=24 if op=='o_proj' else 32;lo=-(1<<(width-1));hi=(1<<(width-1))-1
  assert np.array_equal(C,np.clip(rounded,lo,hi))
  rq=Q+np.where(Q>=0,2*r>=D,2*r>D).astype(np.int64)
  assert np.array_equal(R,np.clip(rq,lo,hi)) and rec['reference_saturation']==0 and rec['observer_counters']==[0]*5
  assert np.abs(Q).max()<np.iinfo(np.int64).max//D-1 and np.abs(C).max()<np.iinfo(np.int64).max//D-1
  B=Q*D+r
  definitions={'final_cut8':(A,rounded*256-A,1<<24),'total_rounding':(B,C*D-B,D*65536),'additional_intermediate':(R,C-R,65536),'saturation':(rounded,C-rounded,65536)}
  for kind,(before,diff,denominator) in definitions.items():
   report=rec['statistics'][kind];bn=before.reshape(-1);dn=diff.reshape(-1);nz=bn!=0;zero0=int(((~nz)&(dn==0)).sum());zerobad=int(((~nz)&(dn!=0)).sum());changed=int((dn!=0).sum())
   assert report['count']==N and report['original_nonzero']==int(nz.sum()) and report['zero_original_current_zero']==zero0 and report['zero_original_current_nonzero']==zerobad and report['changed_count']==changed
   ref=bn.astype(np.float64)/denominator;delta=dn.astype(np.float64)/denominator;absd=np.abs(dn);absb=np.abs(bn);assert (absd>=0).all() and (absb>=0).all() and absd.max(initial=0)<=np.iinfo(np.int64).max//1000
   E=float(np.sum(delta*delta,dtype=np.float64));signal=float(np.sum(ref*ref,dtype=np.float64));rms=math.sqrt(signal/N)
   assert equalfloat(E,report['error_energy']) and equalfloat(signal,report['signal_energy']) and equalfloat(float(np.max(np.abs(delta))),report['absolute_max'])
   assert equalfloat(float(np.mean(delta)),report['signed_mean']) and equalfloat(math.sqrt(E/N),report['absolute_rmse'])
   for label,tden in TH:
    mask=nz&(absd*tden>absb);n=int(mask.sum());e=float(np.sum(delta[mask]**2));t=report['relative_thresholds'][label]
    assert n==t['count'] and int(nz.sum())==t['nonzero_original_denominator'] and equalfloat(e,t['error_energy'])
    assert t['percent_of_nonzero'] is None if not nz.any() else equalfloat(100*n/int(nz.sum()),t['percent_of_nonzero'])
    if E:assert equalfloat(100*e/E,t['error_energy_share_percent'])
    rmask=np.abs(delta)>rms/tden;rt=report['rms_normalized_thresholds'][label]
    assert int(rmask.sum())==rt['count'] and rt['all_output_denominator']==N and equalfloat(100*int(rmask.sum())/N,rt['percent'])
    if E:assert equalfloat(100*float(np.sum(delta[rmask]**2))/E,rt['error_energy_share_percent'])
   if kind=='total_rounding':
    tail=report['relative_thresholds']['1'];threshold_tails[f'{rec["doc_index"]}:{op}']={'above_1pct_count':tail['count'],'above_1pct_error_energy_share_percent':tail['error_energy_share_percent'],'max_relative_percent':report['relative_quantiles_percent']['1.0'],'zero_original_nonzero_after':zerobad,'reference_rms':rms,'max_abs':report['absolute_max']}
  # FP32 decode is assessed separately, never mixed into the integer rounding loss.
  host=C.astype(np.float32)/np.float32(65536);hd=host.astype(np.float64)-C.astype(np.float64)/65536;h=rec['host_fp32_decode_audit']
  assert h['count']==N and h['changed_count']==int(np.count_nonzero(hd)) and h['absolute_max']==float(np.abs(hd).max()) and equalfloat(h['error_energy'],float(np.sum(hd*hd)))
  # Full saved same-input R006 metrics must match the additional-intermediate comparison.
  local=doc['local_metrics'][op]['metrics']['current_vs_reference'];additional=rec['statistics']['additional_intermediate']
  assert N==local['total_elements'] and equalfloat(additional['error_energy'],local['error_energy']) and equalfloat(additional['signal_energy'],local['signal_energy']) and additional['absolute_max']==local['absolute_max']
  # Check selected complete original dependencies using fresh Python Fraction arithmetic.
  wr=doc['witnesses'][op];wp=Path(wr['absolute_path']);assert ident(wp)['sha256']==wr['sha256']
  with np.load(wp,allow_pickle=False) as z:w={k:z[k].copy() for k in z.files}
  ids=w['_witness_output_flat_indices'].reshape(-1)
  assert np.array_equal(C.reshape(-1)[ids],w['_witness_current_code'].reshape(-1)) and np.array_equal(R.reshape(-1)[ids],w['_witness_reference_code'].reshape(-1))
  for j in (0,len(ids)-1):
   idx=int(ids[j]);dot=((w['q_a'][j].astype(np.int64)-w['zero_point'][j,:,None].astype(np.int64))*w['q_w'][j].astype(np.int64)).sum(axis=1,dtype=np.int64)
   exact=Fraction(0);acc=0;aw=42 if op=='o_proj' else 54
   for g,corr in enumerate(dot):
    rawv=int(corr)*int(w['act_code'][j,g])*int(w['weight_code'][j,g]);shift=int(w['act_shift'][j,g])+int(w['weight_shift'][j,g]);active=int(w['act_code'][j,g])!=0 and int(w['weight_code'][j,g])!=0
    if active:
     exact+=Fraction(rawv,1<<shift);term=(rawv>>max(shift-24,0))<<max(24-shift,0)
    else:term=0
    acc=(acc+term+(1<<(aw-1)))%(1<<aw)-(1<<(aw-1))
   assert acc==int(A.reshape(-1)[idx])
   x=exact*65536;q=x.numerator//x.denominator;re=(x-q)*D
   assert re.denominator==1 and q==int(Q.reshape(-1)[idx]) and int(re)==int(r.reshape(-1)[idx])
   assert gold_away(Fraction(acc,256))==int(C.reshape(-1)[idx]) and gold_away(x)==int(R.reshape(-1)[idx])
   sample_checks+=1
  # Histogram closure is independent of the scalar-output denominator.
  g=rec['group_histograms'];total=g['total_shift_bits'];right=[0]*32;left=[0]*25
  for s,n in enumerate(total):
   if n:right[max(s-24,0)]+=n;left[max(24-s,0)]+=n
  assert right==g['rightshift_bits'] and left==g['leftshift_bits'] and sum(right)==g['active_pairs']
  assert g['active_pairs']+g['inactive_pairs']==N*(128 if op=='o_proj' else 448)
  lost=g['nonzero_discarded_remainder_by_rightshift'];assert lost[0]==0 and all(0<=a<=b for a,b in zip(lost,right))
  assert sum(lost)<=g['discarded_one_bits']<=sum(i*n for i,n in enumerate(lost))
  count+=N;checks.append({'doc_id':rec['doc_id'],'op':op,'count':N,'all_integer_threshold_counts_and_zero_cases_verified':True,'energy_and_RMS_thresholds_verified':True,'host_decode_separate_verified':True,'R006_same_input_aggregate_verified':True,'source_NPZ':ident(raw)})
 assert count==14303232 and sample_checks==60
 review={'execution_state':'completed','review':'limited_actual_scalar_evidence_verified','started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),'gpu_or_model_forward':False,'documents':15,'operator_tensors':30,'scalar_outputs':count,'outputs_per_operator':count//2,'independent_Fraction_complete_dependency_spots':sample_checks,'observed_kernel_AST_identical_after_removing_observer_exports':source_ast,'all_threshold_counts_energies_zero_cases_and_host_checks_passed':True,'method_effect_verdict':'not_applicable_no_optimization','scope':'Full scalars of two layer31 operator tensors on 15 predeclared R006 audit documents; not all1024 pointwise ratios or whole-layer causal attribution','zero_error_energy_share_note':'Original metric writes0 for empty error energy; its ratio is mathematically undefined and must be presented as null/not applicable, never evidence of a measured0% causal share. Counts remain valid.','relative_tail_by_tensor':threshold_tails,'checks':checks,'sources':[ident(AT/n) for n in ('manifest.json','result.json','execution_receipt.json','cpu_qualification.json','gpu_qualification.json','operator_records.jsonl')],'script':ident(Path(__file__))}
 (OUT/'scalar_audit_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:review[k]for k in ('execution_state','documents','operator_tensors','scalar_outputs','independent_Fraction_complete_dependency_spots')},indent=2));print('review_sha256',ident(OUT/'scalar_audit_review.json')['sha256'])
if __name__=='__main__':main()
