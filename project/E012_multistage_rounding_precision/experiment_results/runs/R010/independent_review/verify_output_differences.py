"""Independent read-only recovery validation against R006 source moments."""
from pathlib import Path
from fractions import Fraction
from collections import defaultdict
from datetime import datetime,timezone
import csv,hashlib,json,math
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
RUNS=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs'
A=RUNS/'R010/analysis_existing';O=RUNS/'R010/independent_review'
def ident(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify_identity(x):
 p=Path(x['path']);assert ident(p)['sha256']==x['sha256'];return p
def exact_scaled(x,b):
 f=Fraction.from_float(x)*(1<<b);assert f.denominator==1;return f.numerator
def main():
 started=datetime.now(timezone.utc).isoformat();result=json.loads((A/'full1024_output_differences.json').read_text())
 manifest_path=verify_identity(result['source_manifest']);m=json.loads(manifest_path.read_text())
 assert m['model_execution_complete'] is True and m['completed_documents']==1024
 expected=set(m['expected_doc_ids']);assert len(expected)==1024 and set(m['actual_doc_ids'])==expected and not m['missing_doc_ids']
 with (A/'full1024_output_differences_per_document.csv').open(newline='') as f:csvrows=list(csv.DictReader(f))
 csvmap={(x['operator'],x['doc_id']):x for x in csvrows};assert len(csvmap)==len(csvrows)==2048
 expected_rows={(op,d) for op in ('o_proj','down_proj') for d in expected}
 assert set(csvmap)==expected_rows
 sources={s['path']:s for s in result['sources']};seen=set();tot=defaultdict(lambda:defaultdict(int));energies=defaultdict(list);signals=defaultdict(list);source_evidence=[];maxcodes=set();code_ids={}
 for group in m['ordered_groups']:
  p=Path(group['attempt_path']);rp=p/'execution_receipt.json';receipt=json.loads(rp.read_text());src=sources[str(p/'local_tensor_metrics.jsonl')]
  assert ident(rp)['sha256']==src['receipt_sha256']==group['receipt']['sha256']
  assert receipt['execution_state']=='completed' and receipt['exit_code']==0 and receipt['source_unchanged'] is True and receipt['coverage_complete'] is True
  worker=json.loads((p/'paired_worker_manifest.json').read_text())
  for entry in worker['code']:
   if Path(entry['path']).name in ('local_observer.py','gpu_reference.py','v5_fullchain.py'):
    assert ident(Path(entry['path']))['sha256']==entry['sha256']
    prior=code_ids.setdefault(entry['path'],entry);assert prior==entry
  digest=hashlib.sha256()
  with (p/'local_tensor_metrics.jsonl').open('rb') as f:
   for line in f:
    digest.update(line)
    if b'"layer": 31,' not in line:continue
    x=json.loads(line)
    if x['layer']!=31 or x['op'] not in ('o_proj','down_proj'):continue
    key=(x['op'],x['doc_id']);assert key in expected_rows and key not in seen;seen.add(key)
    n=x['node_metadata'];N=x['counts']['accepted_metric_elements'];assert x['node']=='linear' and x['trajectory']=='v5_current_local_paired'
    assert n['fractional_bits']==16 and n['comparison']=='current_vs_output_only_common_exit' and n['exact_pre_output_comparison'] is False
    assert n['audit_reference_delta']['saturation_count']==0
    assert N==n['count']==x['counts']['total_elements']
    assert all(n['audit_current_delta'][name]==0 for name in ('saturation_count','group_guard_overflow_count','software_group_guard_overflow_count','accumulator_overflow_count','software_accumulator_overflow_count'))
    M=Fraction.from_float(n['max_abs'])*(1<<16);assert M==1;maxcodes.add(int(M))
    D=exact_scaled(n['sum_diff'],16);Q=exact_scaled(n['sum_diff2'],32)
    # No floor monotonicity assumed; recover all three signed masses.
    assert 0<=Q<=N and abs(D)<=Q and (Q+D)%2==0
    P=(Q+D)//2;B=(Q-D)//2;Z=N-Q;assert min(P,B,Z)>=0 and P+B+Z==N
    row=csvmap[key]
    fields={'scalar_count':N,'identical_count':Z,'minus_one_step_count':B,'plus_one_step_count':P,'changed_count':Q}
    assert row['group']==group['group_id']
    assert all(int(row[k])==v for k,v in fields.items())
    for k,v in fields.items():tot[x['op']][k]+=v
    tot[x['op']]['document_count']+=1
    expected_float={'changed_percent':100*Q/N,'maximum_absolute_difference':n['max_abs'],'error_energy':n['sum_diff2'],'signal_energy':n['sum_signal2'],'relative_l2_percent':n['relative_l2_percent']}
    assert all(float(row[k])==v for k,v in expected_float.items())
    assert x['metrics']['current_vs_reference']['error_energy']==n['sum_diff2'] and x['metrics']['current_vs_reference']['signal_energy']==n['sum_signal2']
    energies[x['op']].append(n['sum_diff2']);signals[x['op']].append(n['sum_signal2'])
  assert digest.hexdigest()==src['sha256'];source_evidence.append({'path':str(p/'local_tensor_metrics.jsonl'),'sha256':digest.hexdigest(),'receipt_sha256':src['receipt_sha256']})
 assert seen==expected_rows and len(source_evidence)==64
 outputs={}
 for op,values in tot.items():
  report=result['per_operator'][op];assert all(report[k]==v for k,v in values.items())
  E=math.fsum(energies[op]);S=math.fsum(signals[op]);N=values['scalar_count']
  assert values['plus_one_step_count']==0
  change=100*values['changed_count']/N;rel=100*math.sqrt(E/S)
  assert report['changed_percent']==change
  assert math.isclose(report['error_energy'],E,rel_tol=1e-14,abs_tol=1e-16)
  assert math.isclose(report['signal_energy'],S,rel_tol=1e-14)
  assert math.isclose(report['pooled_relative_l2_percent'],rel,rel_tol=1e-14)
  outputs[op]={**dict(values),'changed_percent':change,'pooled_relative_l2_percent_fsum':rel,'positive_difference_count':values['plus_one_step_count'],'all_nonzero_differences':-1/65536}
 assert result['analysis_source_sha256']==ident(A/'recover_output_differences.py')['sha256']
 review={'execution_state':'completed','review':'existing_discrete_output_difference_recovery_verified','started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),'read_only_raw_data':True,'gpu_or_model_forward':False,'groups_verified':64,'documents_verified':1024,'tensor_rows_verified':2048,'max_abs_code_difference_set':sorted(maxcodes),'integer_counts_exact':True,'csv_row_and_full_planned_document_set_verified':True,'all_current_overflow_and_saturation_counters_zero':True,'per_operator':outputs,'comparison':'same-current-input production output minus OUTPUT_ONLY common F16 exit; no sign assumption needed for recovery','not_established':['pre-final-cut total loss','pointwise relative-error threshold fractions','causal contribution to full model output error'],'interpretation':'changed_percent is fraction of scalar outputs with a one-step discrepancy, not the size of their relative error; pooled relative L2 uses tensor energy pooling','inputs':[ident(A/n)for n in ('recover_output_differences.py','full1024_output_differences.json','full1024_output_differences_per_document.csv')],'source_manifest':ident(manifest_path),'semantic_code_identities':list(code_ids.values()),'raw_sources':source_evidence,'script':ident(Path(__file__))}
 review['derived_bound']={'kind':'mathematical_triangle_bound_not_new_pointwise_measurement','h':2.**-16,'integer_exit_absolute_error_upper_bound':1.5*2.**-16,'reference_saturation_zero_verified_tensor_rows':2048,'reference_definition':'Independent exact Group32 sum rounded half-away once to common F16; no reference saturation','derivation':'|current_integer_exit-exact_unrounded_sum| <= |current-reference| + |reference-exact_unrounded_sum| <= h+h/2','applicable_outputs':['layer31 o_proj integer exit','layer31 down_proj integer exit'],'o_proj_host_scope':'Also covers the decoded branch value before residual addition: signed S24 integers convert exactly to FP32 and power-of-two scaling is exact. It does not include residual addition or later RMSNorm.','down_proj_host_scope':'Integer exit only. S32-to-FP32 may add rounding, so 1.5h is not asserted for the actual Host branch without an additional per-value range/conversion check.','exact_pre_output_comparison_false_interpretation':'No pre-exit exact values were saved/measured; this derived bound follows from the verified common-exit discrepancy plus the exact-reference rounding definition.'}
 (O/'output_differences_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:review[k]for k in ('execution_state','groups_verified','documents_verified','tensor_rows_verified','per_operator')},ensure_ascii=False,indent=2))
 print('review_sha256',ident(O/'output_differences_review.json')['sha256'])
if __name__=='__main__':main()
