"""Narrow CPU check of only the added Host-total definition and 45 changed points."""
from pathlib import Path
from fractions import Fraction
import csv,hashlib,json,math,struct
import numpy as np
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');R=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R010'
AT=R/'attempts/AT001_original_two_exit_scalar_audit';P=R/'attempts/AT002_cpu_full_raw_analysis/analysis';O=R/'independent_review'
def identity(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def close(a,b):return math.isclose(a,b,rel_tol=2e-12,abs_tol=1e-20)
def main():
 summary=json.loads((P/'scalar_summary.json').read_text());records=[json.loads(x)for x in(AT/'operator_records.jsonl').read_text().splitlines()]
 oldreview=json.loads((O/'scalar_audit_review.json').read_text());assert oldreview['all_threshold_counts_energies_zero_cases_and_host_checks_passed']
 with(P/'scalar_threshold_table.csv').open(newline='')as f:table={(r['op'],r['definition']):r for r in csv.DictReader(f)}
 with(P/'before_after_examples.csv').open(newline='')as f:examples=list(csv.DictReader(f))
 assert summary['o_proj']['metrics']['delivered_host_total']==summary['o_proj']['metrics']['total_rounding']
 assert summary['o_proj']['host_fp32_decode']['changed_count']==0
 for k,v in table['o_proj','delivered_host_total'].items():
  if k!='definition':assert v==table['o_proj','total_rounding'][k]
 oldenergy=[];energy_delta=[];abs_delta=[];signed_delta=[];hostenergy=[];changed=0;spots=[];threshold_delta={x:0 for x in ('0.1','1','5','10')};threshold_energy_delta={x:[] for x in threshold_delta};host_csv_checked=0
 for rec in records:
  if rec['op']!='down_proj':continue
  raw=Path(rec['raw']['path']);assert identity(raw)['sha256']==rec['raw']['sha256']
  with np.load(raw,allow_pickle=False)as z:C=z['current_code'].astype(np.int64).reshape(-1);Q=z['exact_quotient'].astype(np.int64).reshape(-1);r=z['exact_remainder'].astype(np.int64).reshape(-1)
  D=1<<rec['common_bits'];den=D*65536;H=C.astype(np.float32).astype(np.int64);ids=np.flatnonzero(H!=C);changed+=len(ids);oldenergy.append(rec['statistics']['total_rounding']['error_energy'])
  for idx in ids:
   idx=int(idx);cc=int(C[idx]);hh=int(H[idx]);B=int(Q[idx])*D+int(r[idx]);d0=cc*D-B;d1=hh*D-B
   # Independent scalar binary32 conversion verifies all45 discovered changes.
   assert int(struct.unpack('f',struct.pack('f',cc))[0])==hh
   e0=Fraction(d0,den);e1=Fraction(d1,den);hd=Fraction(hh-cc,65536)
   assert e1==e0+hd
   energy_delta.append(float(2*e0*hd+hd*hd));hostenergy.append(float(hd*hd));abs_delta.append(float(abs(e1)-abs(e0)));signed_delta.append(float(hd))
   for label,factor in [('0.1',1000),('1',100),('5',20),('10',10)]:
    before=(abs(d0)*factor>abs(B))and B!=0;after=(abs(d1)*factor>abs(B))and B!=0
    threshold_delta[label]+=int(after)-int(before);threshold_energy_delta[label].append(float((e1*e1 if after else 0)-(e0*e0 if before else 0)))
   spots.append({'doc_index':rec['doc_index'],'doc_id':rec['doc_id'],'flat_index':idx,'token':idx//4096,'channel':idx%4096,'exact_before_numerator':str(B),'common_denominator':den,'exact_before':float(Fraction(B,den)),'integer_exit_code':cc,'host_rounded_integer_code':hh,'host_returned_value':float(Fraction(hh,65536)),'integer_exit_total_difference':float(e0),'host_conversion_difference':float(hd),'delivered_total_difference':float(e1),'absolute_delivered_difference':float(abs(e1))})
  # All newly added Down CSV examples are checked directly, not just the max.
  for ex in examples:
   if ex['op']!='down_proj' or ex['definition']!='delivered_host_total' or int(ex['doc_index'])!=rec['doc_index']:continue
   i=int(ex['flat_index']);B=int(Q[i])*D+int(r[i]);diff=int(H[i])*D-B
   assert int(ex['before_integer_numerator'])==B and int(ex['difference_integer_numerator'])==diff and int(ex['common_denominator'])==den
   assert float(ex['before_real'])==float(Fraction(B,den)) and float(ex['after_real'])==float(Fraction(int(H[i]),65536)) and float(ex['absolute_error'])==float(Fraction(abs(diff),den));host_csv_checked+=1
 assert changed==45 and sum(r['host_fp32_decode_audit']['changed_count']for r in records if r['op']=='down_proj')==45
 N=summary['down_proj']['outputs'];old=summary['down_proj']['metrics']['total_rounding'];new=summary['down_proj']['metrics']['delivered_host_total']
 assert N==7151616 and new['original_nonzero']==old['original_nonzero']==N and new['zero_original_current_zero']==new['zero_original_current_nonzero']==0
 E=math.fsum(oldenergy)+math.fsum(energy_delta);assert close(E,new['error_energy']) and close(math.sqrt(E/N),new['absolute_rmse'])
 assert close(old['absolute_mean']+math.fsum(abs_delta)/N,new['absolute_mean']) and close(old['signed_mean']+math.fsum(signed_delta)/N,new['signed_mean'])
 worst=max(spots,key=lambda x:x['absolute_delivered_difference']);assert old['absolute_max']<worst['absolute_delivered_difference']==new['absolute_max']
 assert (worst['doc_index'],worst['token'],worst['channel'])==(0,0,788)
 assert close(math.fsum(hostenergy),summary['down_proj']['host_fp32_decode']['error_energy'])
 for label in threshold_delta:
  a=old['relative_thresholds'][label];b=new['relative_thresholds'][label]
  assert b['count']==a['count']+threshold_delta[label] and threshold_delta[label]==0
  assert close(a['error_energy']+math.fsum(threshold_energy_delta[label]),b['error_energy'])
  assert b['nonzero_original_denominator']==N
  t=table['down_proj','delivered_host_total'];assert int(t[f'relative_above_{label}_percent_count'])==b['count'] and close(float(t[f'relative_above_{label}_percent_proportion']),100*b['count']/N)
  assert new['absolute_max']<new['reference_rms']/(1000 if label=='0.1' else 100 if label=='1' else 20 if label=='5' else 10) and new['rms_normalized_thresholds'][label]['count']==0
 assert close(float(table['down_proj','delivered_host_total']['absolute_max']),new['absolute_max']) and close(float(table['down_proj','delivered_host_total']['absolute_rmse']),new['absolute_rmse'])
 result={'execution_state':'completed','scope':'Only newly added delivered_host_total; earlier full scalar checks reused, no full rerun/model/GPU','definition':'Actual returned FP32 branch before residual addition versus exact unrounded same-current-input Linear sum; includes original integer arithmetic and Host cast','down_host_changed_points_independently_checked':changed,'down_delivered_CSV_examples_checked':host_csv_checked,'error_composition':'e_delivered=e_integer+e_host; E_delivered=E_integer+2<e_integer,e_host>+E_host, correction evaluated only at45 changed points','down_error_energy_composed':E,'down_absolute_rmse':math.sqrt(E/N),'down_absolute_max':worst['absolute_delivered_difference'],'threshold_count_deltas':threshold_delta,'o_host_total_identical_to_integer_total':True,'max_point':worst,'host_changed_points':spots,'definition_not_equal_to':['final8bit cut alone','end-to-end freely propagated error','residual sum or final RMSNorm output'],'sources':[identity(P/n)for n in ('scalar_summary.json','scalar_threshold_table.csv','before_after_examples.csv','artifact_manifest.json')],'prior_independent_review':identity(O/'scalar_audit_review.json'),'script':identity(Path(__file__))}
 out=O/'delivered_host_review.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ('execution_state','down_host_changed_points_independently_checked','down_absolute_rmse','down_absolute_max','threshold_count_deltas','max_point')},ensure_ascii=False,indent=2));print('sha256',identity(out)['sha256'])
if __name__=='__main__':main()
