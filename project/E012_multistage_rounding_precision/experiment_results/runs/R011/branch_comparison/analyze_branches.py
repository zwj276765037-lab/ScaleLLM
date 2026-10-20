"""CPU-only R011 pure-branch comparison; no model or CUDA import."""
from pathlib import Path
import csv,hashlib,json,math,os,time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;RUN=HERE.parent;AT=RUN/'attempts/AT002_singleblock_fourway_v2'
STAGES=['post_attention_norm','gate_proj','up_proj','silu','gated_product','prepare3_hadamard','prepare3_dequant','down_proj','mlp_output']
LABELS=['MLP norm','Gate','Up','SiLU','Product','H32','H32 + U8','Down','MLP FP32']
PAIRS=['AB_cross','AC_same_input_local','CB_inherited']
def identity(p):
 p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def savecsv(p,rows):
 with p.open('x') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def stats(a,b):
 d=a-b;e=float(np.sum(d*d,dtype=np.float64));s=float(np.sum(b*b,dtype=np.float64));n=a.size
 return dict(count=n,error_energy=e,signal_energy=s,absolute_rmse=math.sqrt(e/n),reference_rms=math.sqrt(s/n),relative_l2_percent=100*math.sqrt(e/s),max_absolute_error=float(np.max(np.abs(d))))
def pooled(rows):
 n=sum(x['count'] for x in rows);e=sum(x['error_energy'] for x in rows);s=sum(x['signal_energy'] for x in rows)
 return dict(count=n,error_energy=e,signal_energy=s,absolute_rmse=math.sqrt(e/n),reference_rms=math.sqrt(s/n),relative_l2_percent=100*math.sqrt(e/s),max_absolute_error=max(x['max_absolute_error'] for x in rows))
def close(a,b):assert math.isclose(a,b,rel_tol=2e-11,abs_tol=1e-18),(a,b)
def main():
 start=time.monotonic();manifest=json.loads((AT/'manifest.json').read_text());old=json.loads((RUN/'attempts/AT003_cpu_causal_analysis/analysis/causal_summary.json').read_text());allrows=[json.loads(s) for s in (AT/'stage_metrics.jsonl').read_text().splitlines()];index={(x['doc_index'],x['stage']):x for x in allrows}
 sourcepaths=[AT/'manifest.json',AT/'stage_metrics.jsonl',RUN/'attempts/AT003_cpu_causal_analysis/analysis/causal_summary.json',RUN/'independent_review/actual_singleblock_review.json',RUN/'independent_review/existing_stage_review.json'];inputs=[];rawstats={};perdoc=[];checks=[];mult=[]
 needed=['attention_output',*STAGES]
 for doc in manifest['documents']:
  directory=AT/'documents'/f'doc{doc["index"]:03d}';data={};bits={}
  for arm in ['A','B']:
   p=directory/f'{arm}_trace.npz';inputs.append(identity(p));meta=json.loads((directory/f'{arm}_trace_metadata.json').read_text());inputs.append(identity(directory/f'{arm}_trace_metadata.json'));bits[arm]=meta['bits']
   with np.load(p) as z:data[arm]={k:z[k].copy() for k in needed}
   for k,a in data[arm].items():assert hashlib.sha256(a.tobytes()).hexdigest()==meta['all_stage_identity'][k]['sha256']
  for name in needed:
   a=data['A'][name].astype(np.float64)*(2.**-bits['A'][name]);b=data['B'][name].astype(np.float64)*(2.**-bits['B'][name]);m=stats(a,b);stored=index[(doc['index'],name)]['comparisons']['AB_cross']
   for k in ['error_energy','signal_energy','absolute_rmse','reference_rms','relative_l2_percent']:close(m[k],stored[k])
   assert m['count']==stored['count'];rawstats.setdefault(name,[]).append(m);checks.append(dict(doc_index=doc['index'],stage=name,AB_raw_identities_and_metrics_equal=True))
   if name in ['attention_output','mlp_output']:perdoc.append(dict(doc_index=doc['index'],doc_id=doc['doc_id'],tokens=doc['tokens'] if 'tokens' in doc else int(a.shape[1]),branch=name,**m))
  # Same-coordinate exact integer propagation identity for the gated product.
  sa=data['A']['silu'].astype(np.int64);sb=data['B']['silu'].astype(np.int64);ua=data['A']['up_proj'].astype(np.int64);ub=data['B']['up_proj'].astype(np.int64)
  ds=sa-sb;du=ua-ub;t1=ds*ub;t2=sb*du;t3=ds*du;exact=sa*ua-sb*ub;assert np.array_equal(t1+t2+t3,exact)
  actual=data['A']['gated_product'].astype(np.int64)-data['B']['gated_product'].astype(np.int64);rounding=actual*65536-exact;assert np.max(np.abs(rounding))<=65536
  terms=[x.astype(np.float64)/(1<<32) for x in [t1,t2,t3,exact,rounding]];energies=[float(np.sum(x*x)) for x in terms];pairs=[2*float(np.sum(terms[i]*terms[j])) for i,j in [(0,1),(0,2),(1,2)]]
  mult.append(dict(doc_index=doc['index'],silu_input_difference_term_energy=energies[0],up_input_difference_term_energy=energies[1],interaction_term_energy=energies[2],pairwise_cross_terms=pairs,exact_unrounded_product_error_energy=energies[3],product_roundoff_difference_energy=energies[4],product_actual_error_energy=float(np.sum((actual.astype(np.float64)/65536)**2)),integer_vector_identity=True,maximum_product_roundoff_difference=float(np.max(np.abs(rounding)))/(1<<32)))
  del data
 branches={n:pooled(rawstats[n]) for n in ['attention_output','mlp_output']};mlp={}
 for name in STAGES:
  mlp[name]={pair:pooled([index[(d['index'],name)]['comparisons'][pair] for d in manifest['documents']]) for pair in PAIRS}
  for k,v in pooled(rawstats[name]).items():close(v,mlp[name]['AB_cross'][k])
 a=branches['attention_output'];m=branches['mlp_output'];ratios={k:m[k]/a[k] for k in ['absolute_rmse','reference_rms','relative_l2_percent']}
 transitions={}
 for l,r in [('gated_product','prepare3_dequant'),('prepare3_dequant','down_proj')]:
  transitions[l+'__to__'+r]={k:mlp[r]['AB_cross'][k]/mlp[l]['AB_cross'][k] for k in ['absolute_rmse','reference_rms','relative_l2_percent']}
 availability=json.loads((RUN/'independent_review/existing_stage_review.json').read_text())['missing_stages'];assert 'attention branch before first residual sum' in availability
 summary=dict(scope='CPU only; same layer31,3saved diagnostic documents,299token positions; pure outputs before residual; not a1024 branch comparison',comparisons={'AB':'CURRENT(Hc) versus OUTPUT_ONLY(Hr), full paired trajectories','AC':'CURRENT(Hc) versus OUTPUT_ONLY(Hc), same layer entrance but later inputs may diverge','CB':'OUTPUT_ONLY(Hc) versus OUTPUT_ONLY(Hr), inherited-input trajectories'},pooled_branches_AB=branches,MLP_over_attention_ratios_AB=ratios,MLP_stages=mlp,AB_stage_transitions=transitions,gated_product_input_error_decomposition=mult,full1024_comparable_attention_branch_available=False,full1024_missing_source_evidence=availability,raw_validation=checks,source=[identity(p) for p in sourcepaths],raw_inputs=inputs,script=identity(Path(__file__)),cuda_or_model_used=False)
 write(HERE/'summary.json',summary);savecsv(HERE/'pure_branch_AB.csv',[dict(branch=n,**v) for n,v in branches.items()]);savecsv(HERE/'per_document_pure_branch_AB.csv',perdoc);savecsv(HERE/'mlp_AB_stages.csv',[dict(stage=n,**mlp[n]['AB_cross']) for n in STAGES]);savecsv(HERE/'mlp_separate_trajectories.csv',[dict(stage=n,comparison=p,**mlp[n][p]) for p in PAIRS for n in STAGES])
 # Plot A/B only so the AC re-encoding response cannot be confused with AB.
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','axes.grid':True,'grid.alpha':.18,'axes.axisbelow':True})
 fig,axs=plt.subplots(2,3,figsize=(16,9.4));fig.subplots_adjust(left=.065,right=.98,top=.84,bottom=.13,wspace=.28,hspace=.52)
 fig.suptitle('Layer 32 pure branches: absolute error and signal amplitude',fontsize=19,y=.97)
 fig.text(.5,.92,'A/B full trajectories only  |  3 saved diagnostic documents / 299 tokens  |  1,224,704 values per branch',ha='center',fontsize=11)
 specs=[('absolute_rmse','Absolute RMSE','real units'),('reference_rms','Reference output RMS','real units'),('relative_l2_percent','Relative L2','percent')]
 colors=['#2563eb','#ea580c']
 for j,(key,title,ylabel) in enumerate(specs):
  ax=axs[0,j];values=[branches[n][key] for n in branches];bars=ax.bar([0,1],values,color=colors,width=.56);ax.set_xticks([0,1],['Attention output','MLP output']);ax.set_title(title+'\nMLP / Attention = '+f'{ratios[key]:.4f}x',fontsize=12);ax.set_ylabel(ylabel);ax.set_ylim(0,max(values)*1.25)
  for bar,v in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,v+max(values)*.035,f'{v:.7f}',ha='center',va='bottom',fontsize=11)
  ax=axs[1,j]
  if key=='relative_l2_percent':
   ns=['gated_product','prepare3_dequant','down_proj'];vals=[mlp[n]['AB_cross'][key] for n in ns]
   ax.plot(range(3),vals,color='#dc2626',marker='o',linewidth=2.5,markersize=7);ax.set_xticks(range(3),['Product','H32 + U8 requant','Down output']);ax.set_title('MLP A/B relative L2: product to Down',fontsize=12);ax.set_ylabel('percent');ax.set_ylim(0,max(vals)*1.3);ax.margins(x=.12)
   for i,v in enumerate(vals):ax.annotate(f'{v:.6f}%',(i,v),xytext=(0,12),textcoords='offset points',ha='center',fontsize=11)
  else:
   vals=[mlp[n]['AB_cross'][key] for n in STAGES];bars=ax.bar(range(len(STAGES)),vals,color='#475569',width=.72);ax.set_xticks(range(len(STAGES)),LABELS,rotation=50,ha='right');ax.set_title('MLP stages: A/B '+title.lower(),fontsize=12);ax.set_ylabel(ylabel);ax.set_ylim(0,max(vals)*1.26)
   for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+max(vals)*.025,f'{v:.4f}',ha='center',va='bottom',rotation=65,fontsize=8)
 fig.text(.5,.04,'Branch outputs are measured before residual addition. Gate and Up are parallel projections.\nA/C and C/B are reported in separate tables; no GPU/model rerun and no 1024-document extrapolation.',ha='center',fontsize=10,color='#334155')
 fig.savefig(HERE/'pure_branch_comparison.png',dpi=180);plt.close(fig)
 report=['# Attention 与 MLP 纯分支输出比较','','范围：第32层、同3篇保存诊断文档/299位置，残差相加前的实际FP32纯分支输出；每分支1,224,704个数值。同一批输入轨迹A/B，不是1024篇结论。所有图中数值已从保存raw重算，原冻结源和已发布三摘要未修改。','','| 纯分支 A/B | 绝对RMSE | 参考RMS | 相对L2% |','|---|---:|---:|---:|']
 for n,x in branches.items():report.append(f'| {n} | {x["absolute_rmse"]:.11f} | {x["reference_rms"]:.11f} | {x["relative_l2_percent"]:.8f} |')
 report+=['',f'MLP绝对RMSE为Attention的{ratios["absolute_rmse"]:.5f}倍，同时参考输出RMS为{ratios["reference_rms"]:.5f}倍；相对L2为{ratios["relative_l2_percent"]:.5f}倍，反而较低。因而“MLP更高”只在这批数据的绝对误差上成立，不能描述为相对误差更高。','','## MLP全轨迹A/B逐stage','','| stage | 输出数值N | 绝对RMSE | 参考RMS | 相对L2% |','|---|---:|---:|---:|---:|']
 for n in STAGES:
  x=mlp[n]['AB_cross'];report.append(f'| {n} | {x["count"]} | {x["absolute_rmse"]:.10f} | {x["reference_rms"]:.10f} | {x["relative_l2_percent"]:.8f} |')
 report+=['','AB中product→Hadamard+U8反量化相对L2为1.33382373%→1.42492964%，对应绝对RMSE0.00755094→0.00806775；这是本轮全轨迹差。Down之后绝对RMSE升至0.01190025，但参考RMS也升至1.26632737，因此相对L2下降至0.93974515%。不能把Down绝对误差变大直接解释成其舍入质量变差。','','SiLU/up两路已有输入差经过门乘组合；整数恒等式逐数核验将门乘传播项与门乘本身roundoff差分开，详见summary.json。基础动态量化/LUT规则仍在参考中；A/B沿不同输入传播，不能唯一归因某个舍入点。','','## A/C与C/B：独立口径，不能移植为A/B效应','','| stage | A/B相对L2% | A/C同层入口L2% | C/B继承输入L2% |','|---|---:|---:|---:|']
 for n in STAGES:report.append(f'| {n} | '+ ' | '.join(f'{mlp[n][p]["relative_l2_percent"]:.8f}' for p in PAIRS)+' |')
 report+=['','CB纯MLP相对L2=0.93896357%，与AB=0.93974511%几乎相同：在这3篇诊断中，保留上游输入差异、使用参考块的输出仍保留该分支差。这支持传播差主导，但不确定全32层某个量化算子的全局因果占比。OUTPUT_ONLY仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口及Host。','','A/C的product0.17894192%→prepare3dequant0.39201502%属于相同层入口下、层内已经分化的算术/重编码响应；不是A/B的放大倍数。A/C、C/B的完整绝对RMSE/参考RMS/能量分别保存在mlp_separate_trajectories.csv；未保存C raw的stage只引用冻结指标和来源身份，不虚称全raw独立重算。','','## 数据边界','','R006全1024有纯MLP自由轨迹分支统计，但缺少第一次残差相加前的纯Attention自由轨迹分支统计。o_proj同输入局部误差行不能代替该纯分支A/B。因此当前不能做全1024的同口径两分支比较，也不把3篇结果推广为1024篇。','','![Python纯分支比较](pure_branch_comparison.png)','','[机器统计与源SHA](summary.json) · [纯分支表](pure_branch_AB.csv) · [逐文档](per_document_pure_branch_AB.csv) · [MLP AB表](mlp_AB_stages.csv) · [AC/CB分开表](mlp_separate_trajectories.csv)']
 (HERE/'report.md').write_text('\n'.join(report)+'\n');write(HERE/'artifact_manifest.json',dict(created_by=identity(Path(__file__)),inputs=[identity(p) for p in sourcepaths],outputs=[identity(HERE/n) for n in ['summary.json','pure_branch_AB.csv','per_document_pure_branch_AB.csv','mlp_AB_stages.csv','mlp_separate_trajectories.csv','pure_branch_comparison.png','report.md']],wall_seconds=time.monotonic()-start))
 print(json.dumps(dict(branches=branches,ratios=ratios,AB_stage_transitions=transitions,raw_stage_pairs_checked=len(checks))),flush=True)
if __name__=='__main__':main()
