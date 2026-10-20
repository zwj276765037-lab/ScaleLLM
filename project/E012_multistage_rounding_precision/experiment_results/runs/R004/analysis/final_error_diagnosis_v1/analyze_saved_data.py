"""Read-only N=16 descriptive diagnosis; saved-array decomposition is N=1 audit."""
import json,hashlib,math,sys,time
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import numpy as np

ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
AT=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical'
OUT=Path(__file__).resolve().parent
started=datetime.now(timezone.utc).isoformat();begin=time.monotonic();sources={}
def ident(path):
 p=Path(path).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return dict(path=str(p),sha256=h.hexdigest())
def record(path):
 x=ident(path);sources[x['path']]=x;return x
def read(path):record(path);return json.loads(Path(path).read_text())
def rows(path):record(path);return [json.loads(s) for s in Path(path).read_text().splitlines()]
def stats(v):
 v=np.array(v,dtype=np.float64)
 return dict(n=len(v),minimum=float(v.min()),p50=float(np.quantile(v,.5)),p95=float(np.quantile(v,.95)),maximum=float(v.max()))
def metric(row):return row['metrics']['current_vs_reference']
result=read(AT/'paired_result.json');hidden=rows(AT/'tensor_metrics.jsonl');local=rows(AT/'local_tensor_metrics.jsonl');dynamic=rows(AT/'dynamic_metadata.jsonl')
ids=[r['doc_id'] for r in result['documents']];byh={(r['doc_id'],r['layer']):metric(r) for r in hidden};directories={}
final={};inputs=[]
for d in sorted((AT/'documents').glob('doc*')):
 inp=read(d/'input_identity.json');doc=inp['doc_id'];directories[doc]=d;final[doc]=metric(read(d/'final_norm_comparison.json'))
 path=Path(inp['token_artifact']['path']);saved=record(path)
 with np.load(path,allow_pickle=False) as z:
  same_ids=np.array_equal(np.array(inp['input_ids'])[0],z['input_ids']);same_mask=np.array_equal(np.array(inp['attention_mask'])[0],z['attention_mask'])
  positions=np.array_equal(z['position_ids'],np.arange(inp['tokens']))
 inputs.append(dict(doc_id=doc,tokens=inp['tokens'],token_sha_matches=saved['sha256']==inp['token_artifact']['sha256'],input_ids_match=same_ids,mask_match=same_mask,positions_original=positions,retokenized=inp['retokenized']))
assert len(ids)==len(set(ids))==16 and len(byh)==512 and all(x['token_sha_matches'] and x['input_ids_match'] and x['mask_match'] and x['positions_original'] and not x['retokenized'] for x in inputs)
fields=['relative_l2_percent','signal_rms','absolute_rmse','error_energy','signal_energy','normalized_signed_bias_percent','absolute_max']
layer_stats=[dict(layer=l,one_based_layer=l+1,**{k:stats([byh[doc,l][k] for doc in ids]) for k in fields}) for l in range(32)]
formula=[]
for row in [*hidden,*local]:
 m=metric(row)
 if m['signal_energy']>0:formula.append(abs(m['relative_l2_percent']-100*math.sqrt(m['error_energy']/m['signal_energy'])))
for m in final.values():formula.append(abs(m['relative_l2_percent']-100*math.sqrt(m['error_energy']/m['signal_energy'])))
transitions=[];milestones=[]
for doc in ids:
 milestones.append(dict(doc_id=doc,tokens=next(x['tokens'] for x in inputs if x['doc_id']==doc),
  relative_l2_percent={str(l):byh[doc,l]['relative_l2_percent'] for l in [0,7,15,23,31]},final_relative_l2_percent=final[doc]['relative_l2_percent'],
  final_over_last_relative_ratio=final[doc]['relative_l2_percent']/byh[doc,31]['relative_l2_percent']))
 for a,b in [(0,1),(30,31),(31,'final')]:
  ma=byh[doc,a];mb=final[doc] if b=='final' else byh[doc,b]
  transitions.append(dict(doc_id=doc,from_layer=a,to_layer=b,relative_ratio=mb['relative_l2_percent']/ma['relative_l2_percent'],
   error_rmse_ratio=mb['absolute_rmse']/ma['absolute_rmse'],signal_rms_ratio=mb['signal_rms']/ma['signal_rms'],
   error_energy_difference=mb['error_energy']-ma['error_energy'],signal_energy_difference=mb['signal_energy']-ma['signal_energy'],
   interpretation='algebraic change of existing paired error,not an independent noise increment or causal gain'))
local_max=[];families=defaultdict(list)
for doc in ids:
 selected=[r for r in local if r['doc_id']==doc and metric(r)['relative_l2_percent'] is not None]
 top=max(selected,key=lambda r:metric(r)['relative_l2_percent']);local_max.append(dict(doc_id=doc,layer=top['layer'],op=top['op'],node=top['node'],**metric(top)))
 for node in ['linear','rope','qk','softmax','pv']:
  top=max((r for r in selected if r['node']==node),key=lambda r:metric(r)['relative_l2_percent'])
  families[node].append(dict(doc_id=doc,layer=top['layer'],op=top['op'],relative_l2_percent=metric(top)['relative_l2_percent']))
def array_analysis(c,r,per_token=False):
 c=np.asarray(c,dtype=np.float64).reshape(-1,c.shape[-1]);r=np.asarray(r,dtype=np.float64).reshape(c.shape);e=c-r
 E=np.sum(e*e,axis=1);S=np.sum(r*r,axis=1);C=np.sum(c*c,axis=1);dot=np.sum(c*r,axis=1)
 a=np.divide(dot,S);parallel=(a-1)**2*S;perp=np.maximum(0,C-dot*dot/S)
 cosine=np.clip(dot/np.sqrt(S*C),-1,1);amp=(np.sqrt(C)-np.sqrt(S))**2;direction=2*np.sqrt(C*S)*(1-cosine)
 totalE=float(E.sum());totalS=float(S.sum());n=e.size
 flat=np.unravel_index(np.argmax(r*r),r.shape)
 out=dict(error_energy=totalE,signal_energy=totalS,relative_l2_percent=100*math.sqrt(totalE/totalS),signal_rms=math.sqrt(totalS/n),
  error_rmse=math.sqrt(totalE/n),normalized_signed_bias_percent=100*float(e.sum())/math.sqrt(n*totalS),
  token_relative_l2_percent=stats(100*np.sqrt(E/S)),token_signal_rms=stats(np.sqrt(S/r.shape[1])),
  token_cosine=stats(cosine),token_projection_scale=stats(a),
  parallel_error_energy_share=float(parallel.sum()/totalE),orthogonal_error_energy_share=float(perp.sum()/totalE),
  norm_amplitude_error_energy_share=float(amp.sum()/totalE),norm_direction_error_energy_share=float(direction.sum()/totalE),
  projection_decomposition_residual=float((parallel.sum()+perp.sum()-totalE)/totalE),
  max_token_error_energy_share=float(E.max()/totalE),max_token_error_index=int(E.argmax()),
  max_token_signal_energy_share=float(S.max()/totalS),max_token_signal_index=int(S.argmax()),
  max_coordinate_signal_energy_share=float(np.max(r*r)/totalS),max_coordinate_signal_position=list(map(int,flat)))
 if per_token:
  out['tokens']=[dict(token=i,relative_l2_percent=float(100*math.sqrt(E[i]/S[i])),signal_rms=float(math.sqrt(S[i]/r.shape[1])),error_rmse=float(math.sqrt(E[i]/r.shape[1])),
    error_energy_share=float(E[i]/totalE),signal_energy_share=float(S[i]/totalS),cosine=float(cosine[i]),projection_scale=float(a[i])) for i in range(len(E))]
 return out
raw_audits=[]
for inp in inputs:
 doc=inp['doc_id'];d=directories[doc]
 if not read(d/'input_identity.json')['audited']:continue
 arrays=[]
 for l in range(32):
  path=d/f'hidden_layer{l:02d}.npz';record(path)
  with np.load(path,allow_pickle=False) as z:analysis=array_analysis(z['current'],z['reference'],l in [0,1,30,31])
  analysis['layer']=l;analysis['saved_metric_difference']=analysis['relative_l2_percent']-byh[doc,l]['relative_l2_percent'];arrays.append(analysis)
 fc=d/'final_hidden_current.npz';fr=d/'final_hidden_reference.npz';record(fc);record(fr)
 with np.load(fc,allow_pickle=False) as cz,np.load(fr,allow_pickle=False) as rz:fa=array_analysis(cz['hidden'],rz['hidden'],True)
 dynamic_rows=[r for r in dynamic if r['doc_id']==doc];lookup={(r['arm'],r['layer'],r['function'],r['ordinal']):r for r in dynamic_rows};changes=[]
 for l in range(32):
  changed=Counter();total=Counter()
  for function,count in [('prepare_fixed_activation',4),('_kv12_quantize',2)]:
   for ordinal in range(count):
    cr=lookup['current',l,function,ordinal];rr=lookup['reference',l,function,ordinal];cp=Path(cr['artifact']['path']);rp=Path(rr['artifact']['path']);record(cp);record(rp)
    with np.load(cp,allow_pickle=False) as cz,np.load(rp,allow_pickle=False) as rz:
     for key in cz.files:changed[key]+=int(np.count_nonzero(cz[key]!=rz[key]));total[key]+=int(cz[key].size)
  changes.append(dict(layer=l,changed=dict(changed),total=dict(total),fractions={key:changed[key]/total[key] for key in total},value_scope='saved values only at0/15/31; metadata all32'))
 raw_audits.append(dict(doc_id=doc,independent_documents=1,layers=arrays,final=fa,dynamic_changes=changes,scope='only preselected saved raw audit document; no population generalization'))
aggregate=read(AT/'aggregate_v1/formal_aggregate.json');loader=read(AT/'stream_loader_validation.json');manifest=read(AT/'paired_worker_manifest.json');gpu=read(AT/'gpu_receipt.json')
output=dict(schema='m005_saved_final_error_diagnosis_v1',scope=dict(attempt=str(AT),documents=16,token_total=sum(x['tokens'] for x in inputs),raw_audit_documents=len(raw_audits),quantiles='NumPy linear descriptive P50/P95,not CIs',other_queue_untouched=True),
 layers=layer_stats,final={k:stats([final[doc][k] for doc in ids]) for k in fields},milestone_documents=milestones,paired_transitions=transitions,
 transition_summary={f'{a}_to_{b}':{key:stats([x[key] for x in transitions if x['from_layer']==a and x['to_layer']==b]) for key in ['relative_ratio','error_rmse_ratio','signal_rms_ratio','error_energy_difference']} for a,b in [(0,1),(30,31),(31,'final')]},
 local_max_documents=local_max,local_max_locations=[dict(op=op,layer=layer,documents=count) for (op,layer),count in Counter((x['op'],x['layer']) for x in local_max).items()],
 local_family_max=families,raw_audit=raw_audits,formula_check=dict(compared_tensor_ratios=len(formula),max_absolute_percentage_difference=max(formula),formula='100sqrt(sum((current-reference)^2)/sum(reference^2));100 applied once'),
 paired_input_checks=inputs,paired_model_evidence=dict(shared_weight_buffers_unchanged=result['shared_weight_buffers_unchanged'],source_unchanged=gpu['source_unchanged'],
  consumed_base_model_identity_sha256=loader['consumed_base_model_identity_sha256'],manifest_code_sources=len(manifest['code']),aggregate_core_identity_present=bool(aggregate['accepted_attempts']),
  scope='existing loader/shared-weight checks,not a new independent whole-checkpoint hash'),
 facts=['Saved final signal RMS is finite and tightly ranged across all16 documents; no zero denominator.',
 'Layer transitions are paired metric changes,not causal gains or independently added rounding noise.',
 'All16 local maxima are early o_proj; this does not identify which local error causes downstream propagation.'],
 hypotheses=['Dynamic metadata changes and repeated nonlinear path differences may mediate propagation; saved flips alone do not establish causality.'],
 missing_ablations=['Per-node/site one-at-a-time policy intervention on identical input and fixed weights.','Freeze versus recompute dynamic metadata under paired paths.','Separate final-layer Attention/MLP/residual contributions.','Final norm with matched normalization statistics versus each-path statistics.'],
 source_files=list(sources.values()),analysis_source=ident(__file__),execution=dict(started_at=started,ended_at=datetime.now(timezone.utc).isoformat(),wall_seconds=time.monotonic()-begin,command=sys.argv,cpu_threads=1,no_model_forward=True,no_gpu=True))
for source in output['source_files']:
 assert ident(source['path'])['sha256']==source['sha256'],'input changed during analysis'
with (OUT/'data_diagnosis.json').open('x') as f:json.dump(output,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
lines=['# 现存16文档最终误差归因（只读数据）','',f"CPU分析耗时{output['execution']['wall_seconds']:.3f}秒，无GPU、无模型前向；Q001不改、不停。N=16文档，原始数组分解仅预定audit N=1。",'',
'## 已核事实','',f"最终相对L2 P50/P95={output['final']['relative_l2_percent']['p50']:.8f}%/{output['final']['relative_l2_percent']['p95']:.8f}%；范围{output['final']['relative_l2_percent']['minimum']:.8f}%–{output['final']['relative_l2_percent']['maximum']:.8f}%。这些不是任务准确率损失。",'',
'层号以下为0-based。分位数为16篇文档的描述值，非置信区间。','',
'|层|相对L2 P50%|P95%|范围%|signal RMS P50|error RMSE P50|', '|---|---:|---:|---:|---:|---:|']
for l in layer_stats:
 q=l['relative_l2_percent'];lines.append(f"|{l['layer']}|{q['p50']:.6f}|{q['p95']:.6f}|{q['minimum']:.6f}–{q['maximum']:.6f}|{l['signal_rms']['p50']:.8g}|{l['absolute_rmse']['p50']:.8g}|")
lines+=['','## 同文档转折分解','', '比值由每篇文档先算再汇总，不能把分位数之比当配对比值；error能量差包含传播和交叉项，不是独立新增噪声。','',
'|转折|相对比值P50/范围|error RMSE比值P50|signal RMS比值P50|', '|---|---:|---:|---:|']
for key,t in output['transition_summary'].items():
 q=t['relative_ratio'];lines.append(f"|{key}|{q['p50']:.5f} / {q['minimum']:.5f}–{q['maximum']:.5f}|{t['error_rmse_ratio']['p50']:.5f}|{t['signal_rms_ratio']['p50']:.5f}|")
lines+=['','## 逐文档里程碑与final前后','', '|doc_id|tokens|L0%|L7%|L15%|L23%|L31%|final%|final/L31|','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in milestones:
 vals=[r['relative_l2_percent'][str(l)] for l in [0,7,15,23,31]]
 lines.append('|'+r['doc_id']+'|'+str(r['tokens'])+'|'+ '|'.join(f'{v:.6f}' for v in [*vals,r['final_relative_l2_percent'],r['final_over_last_relative_ratio']])+'|')
lines+=['','## 局部最大与分母','',str(output['local_max_locations']), '',
 f"final reference signal RMS范围{output['final']['signal_rms']['minimum']:.6f}–{output['final']['signal_rms']['maximum']:.6f}；均非零。max/尾部支持见JSON每文档表，不能以小分母概括全部final误差。局部最大位置仅描述同码误差，不是传播因果归因。",'',
'## 保存数组独立分解（仅预定audit N=1）','']
for audit in raw_audits:
 lines += [f"审计文档{audit['doc_id']}。方向/幅度按每token向量分解后合能量；平行/正交按参考向量投影。分解是代数，不定位产生误差的算子。",'',
 '|层|relativeL2%|signed bias%|最大token信号份额|最大token误差份额|正交误差能量份额|', '|---|---:|---:|---:|---:|---:|']
 for a in [audit['layers'][l] for l in [0,1,7,15,23,30,31]]+[dict(audit['final'],layer='final')]:
  lines.append(f"|{a['layer']}|{a['relative_l2_percent']:.6f}|{a['normalized_signed_bias_percent']:.6f}|{a['max_token_signal_energy_share']:.6f}|{a['max_token_error_energy_share']:.6f}|{a['orthogonal_error_energy_share']:.6f}|")
 fa=audit['final'];lines += ['',f"final每token相对L2 P50/P95={fa['token_relative_l2_percent']['p50']:.6f}%/{fa['token_relative_l2_percent']['p95']:.6f}%；最大token误差份额{fa['max_token_error_energy_share']:.6f}。方向能量份额{fa['norm_direction_error_energy_share']:.6f}，幅度份额{fa['norm_amplitude_error_energy_share']:.6f}。其余层与128个token原始分解见JSON，N=1不能外推。",'',
 '动态code/shift/zp差异按全部32层保存NPZ独立数出；value整数只保存0/15/31，二者不能混分母。逐层changed/total/fraction见JSON。']
lines+=['','## 公式与配对证据','',f"{len(formula)}条ratio按100sqrt(E/S)重算，最大差{max(formula):.3g}个百分点，未重复乘100。16篇token SHA/ID/mask/positions均核对；现存共享权重与source未变证据附JSON，不重新哈希整模型。",'',
'## 推测与尚缺实验','',*['- 推测：'+x for x in output['hypotheses']],*['- 未做ablation：'+x for x in output['missing_ablations']], '',
'这些是后续可证伪实验方向，本分析不启动模型、不调整Q001、不从现存比值宣称因果或精度通过。']
(OUT/'data_diagnosis.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(output=str(OUT),seconds=output['execution']['wall_seconds'],transitions=output['transition_summary'],audit_final=raw_audits[0]['final'],audit_layer1={k:v for k,v in raw_audits[0]['layers'][1].items() if k!='tokens'})))
