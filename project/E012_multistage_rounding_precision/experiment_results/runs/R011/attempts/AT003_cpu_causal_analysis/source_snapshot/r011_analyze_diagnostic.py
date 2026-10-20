"""CPU-only R011 raw verification and bounded causal-stage report."""
import argparse,csv,hashlib,json,math,os,time
from pathlib import Path
import numpy as np

def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def identity(p):
 p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def energy(x):return float(np.sum(x*x,dtype=np.float64))
def checkclose(x,y):assert math.isclose(x,y,rel_tol=2e-11,abs_tol=1e-18),(x,y)
def analyze(at,out):
 begin=time.monotonic();receipt=json.loads((at/'external_wait_receipt.json').read_text());assert receipt['native_exit_code']==0 and receipt['child_reaped'] and receipt['worker_proc_absent'] and not receipt['gpu_owned_process_rows']
 out.mkdir(exist_ok=False);manifest=json.loads((at/'manifest.json').read_text());result=json.loads((at/'result.json').read_text());assert result['all_R006_hidden_and_dynamic_parity_passed'] and result['source_unchanged']
 stages=[json.loads(s) for s in (at/'stage_metrics.jsonl').read_text().splitlines()];inter=[json.loads(s) for s in (at/'interventions.jsonl').read_text().splitlines()];assert len(stages)==108 and len(inter)==6
 checks=[];documents=[];dyn={};residuals=[]
 for doc in manifest['documents']:
  directory=at/'documents'/f'doc{doc["index"]:03d}';summary=json.loads((directory/'primary_summary.json').read_text());arrays={};bits={}
  for arm in ['A','B','C','D']:
   meta=json.loads((directory/f'{arm}_trace_metadata.json').read_text());bits[arm]=meta['bits']
   with np.load(directory/f'{arm}_trace.npz') as z:arrays[arm]={k:z[k].copy() for k in z.files if not k.startswith('dynamic__')}
   for k,a in arrays[arm].items():assert hashlib.sha256(a.tobytes()).hexdigest()==meta['all_stage_identity'][k]['sha256']
  def real(arm,k):return arrays[arm][k].astype(np.float64)*(2.**-bits[arm][k])
  for name in set.intersection(*(set(arrays[x]) for x in arrays)):
   stage=next(s for s in summary['stages'] if s['stage']==name)
   for key,x,y in [('AB_cross','A','B'),('AC_same_input_local','A','C'),('CB_inherited','C','B'),('DB_same_reference_input_local','D','B'),('AD_inherited_current_arithmetic','A','D')]:
    a=real(x,name);b=real(y,name);m=stage['comparisons'][key];checkclose(energy(a-b),m['error_energy']);checkclose(energy(b),m['signal_energy']);assert a.size==m['count']
   a,b,c=(real(x,name) for x in ['A','B','C']);u=a-c;v=c-b;w=a-b;assert np.max(np.abs(w-u-v))<1e-12
   d=stage.get('decomposition')
   if d:checkclose(energy(u),d['same_input_local_error_energy']);checkclose(energy(v),d['inherited_input_error_energy']);checkclose(2*float(np.sum(u*v)),d['cross_term'])
   checks.append(dict(doc_index=doc['index'],stage=name,all_five_comparisons_from_raw=True,vector_energy_identity=True))
  for label,left,branch,end in [('attention','input','attention_output','attention_residual'),('mlp','attention_residual','mlp_output','final_residual')]:
   u=real('A',left)-real('B',left);v=real('A',branch)-real('B',branch);w=real('A',end)-real('B',end);r=summary['residual_decomposition'][label]
   checkclose(energy(u),r['input_error_energy']);checkclose(energy(v),r['branch_error_energy']);checkclose(2*float(np.sum(u*v)),r['input_branch_error_cross']);checkclose(energy(w-u-v),r['FP32_addition_roundoff_difference_energy']);checkclose(energy(w),r['output_error_energy'])
  with np.load(directory/'cut_down_proj_outputs.npz') as z:
   assert np.array_equal(z['mlp_output'],arrays['B']['mlp_output'])
   assert np.array_equal(z['final_residual'],arrays['A']['attention_residual']+arrays['B']['mlp_output'])
  documents.append(summary);residuals.append(summary['residual_decomposition'])
  for d in summary['dynamic']:
   key=d['coordinate']+':'+d['field'];entry=dyn.setdefault(key,dict(count=0,AB_changed=0,AC_changed=0))
   for n in entry:entry[n]+=d[n]
 pooled={}
 for name in dict.fromkeys(s['stage'] for s in stages):
  rr=[s for s in stages if s['stage']==name];p={}
  for pair in rr[0]['comparisons']:
   ms=[s['comparisons'][pair] for s in rr];e=sum(m['error_energy'] for m in ms);sig=sum(m['signal_energy'] for m in ms);n=sum(m['count'] for m in ms)
   p[pair]=dict(error_energy=e,signal_energy=sig,count=n,absolute_rmse=math.sqrt(e/n),reference_rms=math.sqrt(sig/n),relative_l2_percent=100*math.sqrt(e/sig),max_absolute_error=max(m['max_absolute_error'] for m in ms))
  if 'decomposition' in rr[0]:
   keys=['total_error_energy','same_input_local_error_energy','inherited_input_error_energy','cross_term','energy_identity_residual'];p['decomposition']={k:sum(r['decomposition'][k] for r in rr) for k in keys}
   p['decomposition']['vector_identity_max_absolute']=max(r['decomposition']['vector_identity_max_absolute'] for r in rr)
  pooled[name]=p
 pooled_res={}
 for name in ['attention','mlp']:
  keys=[k for k in residuals[0][name] if k!='signal_cancellation_ratio' and not k.endswith('_max')]
  pooled_res[name]={k:sum(r[name][k] for r in residuals) for k in keys};pooled_res[name]['FP32_addition_roundoff_difference_max']=max(r[name]['FP32_addition_roundoff_difference_max'] for r in residuals)
  rr=pooled_res[name];rr['signal_cancellation_ratio']=rr['signal_output_energy']/(rr['signal_left_energy']+rr['signal_branch_energy'])
 pooled_inter={}
 for cut in ['gated_product','down_proj']:
  rr=[r for r in inter if r['cut']==cut];base=sum(r['baseline_final_error_energy'] for r in rr);e=sum(r['comparisons']['final_residual']['error_energy'] for r in rr)
  pooled_inter[cut]=dict(baseline_final_error_energy=base,intervention_final_error_energy=e,conditional_error_energy_reduction_percent=100*(1-e/base),per_document=[dict(doc_index=r['doc_index'],reduction_percent=r['conditional_final_error_energy_reduction_percent'],final_error_energy=r['comparisons']['final_residual']['error_energy'],final_relative_l2_percent=r['comparisons']['final_residual']['relative_l2_percent']) for r in rr])
 output=dict(scope='Three predeclared diagnostic cases,299positions; only block31/finalnorm. No formal1024 causal-population or unique/additive attribution.',documents=3,tokens=299,pooled_stages=pooled,residual_decomposition=pooled_res,conditional_interventions=pooled_inter,dynamic_changes=dyn)
 write(out/'causal_summary.json',output);write(out/'independent_raw_checks.json',dict(passed=True,raw_stage_comparison_groups=len(checks),five_comparisons_each=True,per_stage=checks,down_cut_equals_current_skip_plus_reference_branch_all3=True,source=identity(Path(__file__)),input_manifest=identity(at/'manifest.json'),seconds=time.monotonic()-begin))
 csvrows=[dict(doc_index=r['doc_index'],doc_id=r['doc_id'],stage=r['stage'],comparison=p,**m) for r in stages for p,m in r['comparisons'].items()]
 with (out/'stage_metrics.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
 report=['# R011：第32层误差跳变定位','','仅3篇预声明保存输入/299位置、单decoder31及final norm。四轨迹A=CURRENT(Hc)、B=OUTPUT_ONLY(Hr)、C=OUTPUT_ONLY(Hc)、D=CURRENT(Hr)，前31层未加载或执行。A/B的hidden31/finalnorm和全部保存的动态编码逐值复现R006。','','## 三篇合池逐阶段','','| 阶段 | A/B误差能量 | 参考信号能量 | A/B相对L2% | A/B绝对RMSE | 参考RMS | 同Hc下A/C相对L2% | 继承输入C/B相对L2% |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for name in ['input','input_norm','attention_output','attention_residual','post_attention_norm','gate_proj','up_proj','silu','gated_product','prepare3_hadamard','prepare3_dequant','down_proj','mlp_output','final_residual','final_norm']:
  p=pooled[name];m=p['AB_cross'];report.append(f'| {name} | {m["error_energy"]:.9g} | {m["signal_energy"]:.9g} | {m["relative_l2_percent"]:.8f} | {m["absolute_rmse"]:.9g} | {m["reference_rms"]:.9g} | {p["AC_same_input_local"]["relative_l2_percent"]:.8f} | {p["CB_inherited"]["relative_l2_percent"]:.8f} |')
 r=pooled_res['mlp'];d=pooled['final_residual']['decomposition'];report+=['','## MLP残差合并：误差与真实信号的两种相消','',f'误差能量：skip {r["input_error_energy"]:.12g} + MLP branch {r["branch_error_energy"]:.12g} + 交叉项 {r["input_branch_error_cross"]:.12g} → 输出 {r["output_error_energy"]:.12g}。FP32加法舍入差的能量仅{r["FP32_addition_roundoff_difference_energy"]:.12g}，最大逐值差{r["FP32_addition_roundoff_difference_max"]:.12g}。',f'真实信号：skip {r["signal_left_energy"]:.12g} + branch {r["signal_branch_energy"]:.12g} + 交叉项 {r["signal_cross"]:.12g} → 输出 {r["signal_output_energy"]:.12g}；相消比值{r["signal_cancellation_ratio"]:.9g}。因此相对指标跳变须同时看误差分子和信号分母，不等于加法本身舍入产生了这些差。','','## 四轨迹：本层新增误差与继承输入差','',f'finalres精确向量分解A−B=(A−C)+(C−B)：总能量{d["total_error_energy"]:.12g}，同输入本层算术差A−C能量{d["same_input_local_error_energy"]:.12g}，继承输入差C−B能量{d["inherited_input_error_energy"]:.12g}，交叉项{d["cross_term"]:.12g}。这些含交互，不能作为互斥因果占比或相减relativeL2百分数。','','## 条件下游干预','','| 替换点 | 替换前final误差能量 | 替换后 | 条件降低% |','|---|---:|---:|---:|']
 for cut,p in pooled_inter.items():report.append(f'| {cut} | {p["baseline_final_error_energy"]:.9g} | {p["intervention_final_error_energy"]:.9g} | {p["conditional_error_energy_reduction_percent"]:.8f} |')
 report+=['','替换值均来自B参考轨迹同stage，使用CURRENT重算所有下游。down输出替换后三篇均逐位等于“当前attention残差+参考MLP分支输出”的FP32求和，排除把大跳归因于最终加法舍入。gated_product替换仍使用原Down整数舍入，效果与down输出替换接近；这支持主要差异已在MLP分支上游传播，并非Down出口最后cut8自身造成。条件修复不是部署优化，也不能证明某单算子是唯一根因。','','## 逐篇保留','','| doc | 输入L2% | attention残差后 | MLP残差后 | final norm后 |','|---|---:|---:|---:|---:|']
 for doc in documents:
  mm={r['stage']:r['comparisons']['AB_cross']['relative_l2_percent'] for r in doc['stages']};report.append(f'| {doc["doc_id"]} | {mm["input"]:.8f} | {mm["attention_residual"]:.8f} | {mm["final_residual"]:.8f} | {mm["final_norm"]:.8f} |')
 report+=['','全部36stage×5比较×3篇、动态code/shift/LUT地址变化及所有干预/不利指标保留在CSV/JSON。观察器v1在资格阶段因重建Hadamard漏int64提升自然失败，未进入真实样本；v2修正后所有资格/复现检查通过，失败原样保存。软件重放不提供RTL时序/ACC/PPL或全1024因果群体结论。','','[完整统计](causal_summary.json) · [所有stage CSV](stage_metrics.csv) · [独立CPU raw检查](independent_raw_checks.json) · [原始GPU结果](../../AT002_singleblock_fourway_v2/result.json) · [父进程真实退出](../../AT002_singleblock_fourway_v2/external_wait_receipt.json)']
 (out/'report.md').write_text('\n'.join(report)+'\n');write(out/'artifact_manifest.json',dict(source=identity(Path(__file__)),files=[identity(p) for p in out.iterdir() if p.is_file()]))
 print(json.dumps(dict(passed=True,final_decomposition=d,residual=r,interventions=pooled_inter)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();analyze(a.attempt,a.output)
