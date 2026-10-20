"""CPU CSV cross-check and Chinese Python figure; original R006 data read-only."""
from pathlib import Path
import csv,hashlib,json,math,time
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
HERE=Path(__file__).resolve().parent

def identity(p):
 p=Path(p).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 started=time.monotonic();s=json.loads((HERE/'summary.json').read_text());positions=list(csv.DictReader((HERE/'positions.csv').open()));flips=list(csv.DictReader((HERE/'top1_flips.csv').open()));docs=list(csv.DictReader((HERE/'document_checks.csv').open()));assert len(positions)==103700 and len(flips)==1053 and len(docs)==1024
 m=np.asarray([float(x['reference_top1_margin']) for x in positions]);f=np.asarray([int(x['top1_flip']) for x in positions],dtype=np.int64);edges=np.array([0,.01,.05,.1,.2,.5,1,2,np.inf]);assert np.isfinite(m).all() and (m>=0).all()
 counts,_=np.histogram(m,edges);flipcounts,_=np.histogram(m,edges,weights=f)
 bydoc=defaultdict(lambda:[0,0]);keys=set()
 for x in positions:
  key=x['doc_id'],int(x['position']);assert key not in keys;keys.add(key);flip=int(x['top1_flip']);assert flip==int(x['current_top1_id']!=x['reference_top1_id']);bydoc[x['doc_id']][0]+=1;bydoc[x['doc_id']][1]+=flip
  assert x['softmax_tv']!='' and math.isfinite(float(x['softmax_tv'])) and 0<=float(x['softmax_tv'])<=1
 for d in docs:assert bydoc[d['doc_id']]==[int(d['positions']),int(d['flip_count'])]
 for i,b in enumerate(s['buckets']):assert int(counts[i])==b['positions'] and int(flipcounts[i])==b['flips']
 assert sum(counts)==103700 and sum(flipcounts)==1053 and set((x['doc_id'],int(x['position'])) for x in flips)=={(x['doc_id'],int(x['position'])) for x in positions if int(x['top1_flip'])}
 for q,v in s['flip_margin_quantiles'].items():assert math.isclose(float(np.quantile(m[f!=0],float(q))),v,rel_tol=0,abs_tol=1e-14)
 high=list(csv.DictReader((HERE/'high_margin_flips_ge1.csv').open()));assert len(high)==int(np.count_nonzero(m[f!=0]>=1))==s['high_margin_flip_count']
 # Independent fixed-boundary cases include each exact left endpoint.
 test=np.asarray([0,.009,.01,.049,.05,.099,.1,.199,.2,.499,.5,.999,1,1.999,2,10.]);tc,_=np.histogram(test,edges);assert tc.tolist()==[2]*8
 src=json.loads((HERE/'source_manifest.json').read_text());assert all(identity(x['path'])['sha256']==x['sha256'] for x in src['sources'])
 write(HERE/'independent_csv_checks.json',dict(passed=True,positions=103700,flips=1053,documents=1024,exact_bucket_boundary_cases_passed=True,CSV_positions_unique_and_complete=True,CSV_flip_ids_and_flags_equal=True,all_document_counts_recomputed=True,numpy_histogram_matches_summary=True,quantiles_recomputed=True,TV_key_aligned_only_no_extra_inference=True,source_hashes_unchanged=True,seconds=time.monotonic()-started))
 font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';assert Path(font).exists();font_manager.fontManager.addfont(font);family=font_manager.FontProperties(fname=font).get_name()
 plt.rcParams.update({'font.family':family,'font.size':11,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'axes.axisbelow':True,'grid.alpha':.18})
 fig,axs=plt.subplots(1,2,figsize=(16,6.7));fig.subplots_adjust(left=.065,right=.98,bottom=.24,top=.76,wspace=.23)
 fig.suptitle('参考 Logit Margin 分层：Top1 翻转分布',fontsize=20,y=.97)
 fig.text(.5,.895,'Margin = 参考最高 logit − 参考第二高 logit（原始 logit 单位，未经 softmax）',ha='center',fontsize=12)
 fig.text(.5,.845,'1024 篇正式文档 · 103700 个位置 · 1053 次翻转 · 总翻转率 1.01543%',ha='center',fontsize=11)
 labels=['[0,.01)','[.01,.05)','[.05,.1)','[.1,.2)','[.2,.5)','[.5,1)','[1,2)','[2,∞)'];x=np.arange(8);n=counts.tolist();y=flipcounts.tolist();rates=[100*a/b if b else np.nan for a,b in zip(y,n)]
 ticks=[f'{lab}\nN={N}' for lab,N in zip(labels,n)]
 colors=['#c2410c' if a else '#94a3b8' for a in y]
 ax=axs[0];ax.bar(x,y,color=colors,width=.68);ax.set_title('翻转数量',fontsize=16,pad=14);ax.set_ylabel('Top1 翻转位置数');ax.set_ylim(0,max(y)*1.22);ax.grid(axis='y')
 for i,v in enumerate(y):ax.text(i,v+max(y)*.025,str(v),ha='center',va='bottom',fontsize=12)
 ax=axs[1];ax.bar(x,[r if np.isfinite(r) else 0 for r in rates],color=colors,width=.68);ax.set_title('桶内翻转率 = 该桶翻转数 ÷ 该桶位置数',fontsize=15,pad=14);ax.set_ylabel('桶内翻转率（%）');ax.set_ylim(0,max(r for r in rates if np.isfinite(r))*1.22);ax.grid(axis='y')
 for i,v in enumerate(rates):
  label='NA' if not np.isfinite(v) else ('0%' if v==0 else (f'{v:.2f}%' if v>=1 else f'{v:.4f}%'))
  ax.text(i,(v if np.isfinite(v) else 0)+max(r for r in rates if np.isfinite(r))*.025,label,ha='center',va='bottom',fontsize=11)
 for ax in axs:ax.set_xticks(x,ticks,fontsize=10);ax.set_xlabel('参考 Logit Margin 分桶（左闭右开）；N 为桶内总位置数',labelpad=12)
 fig.text(.5,.065,'Margin 不是概率差，也不是百分比；翻转指 current 与 reference 的 Top1 ID 不同。\n所有预定桶均保留。空桶翻转率为 NA；非空零翻转桶为 0%。逐位置描述性统计，未假设 token 相互独立。',ha='center',fontsize=10,color='#334155')
 fig.savefig(HERE/'reference_logit_margin_top1_flips.png',dpi=180);plt.close(fig)
 def pct(v):return 'NA' if v is None else f'{v:.6f}%'
 report=['# 按参考 Logit Margin 分层的 Top1 翻转','','Margin定义：参考版本最高logit减去第二高logit，温度1、未经softmax的原始logit单位，不是概率差或百分比。Top1翻转指current/reference Top1 ID不同，采用原数据的最小词表ID并列规则。','','数据只来自R006/session_S001/analysis_manifest.json指定的64个正式组；未扫描/纳入qualification或重复attempt。全部1024文档、103700位置、1053翻转核对通过，总翻转率1.01542912%。每篇原top1_match_count、逐位置ID与matches、原margin certificate全部一致。','','## 固定分桶主表','','| 参考Margin桶 | 总位置数 | 翻转数 | 桶内翻转率 | 占1053翻转比例 | 累计翻转数 | 累计翻转比例 |','|---|---:|---:|---:|---:|---:|---:|']
 for b in s['buckets']:report.append(f'| {b["margin_bucket"]} | {b["positions"]} | {b["flips"]} | {pct(b["within_bucket_flip_rate_percent"])} | {pct(b["share_of_all_flips_percent"])} | {b["cumulative_flips"]} | {pct(b["cumulative_share_of_all_flips_percent"])} |')
 report+=['','累计比例按Margin从小到大累加1053次翻转。全部桶非空；若空桶则率应为NA，不能写0%。分桶方案在读取全量结果前固定于protocol.json。','','83.190883%的翻转位于Margin<0.05，92.592593%位于<0.1，99.810066%位于<0.5。Margin≥1的位置共有50456个，观察到0次翻转；这是该冻结数据集的描述，不是对其他输入的不翻转保证。','','## 零Margin及非法值','','恰好Margin=0（参考Top1并列）0位置、0翻转，翻转率NA（无样本）。此项为首桶的重叠子集，不能再加入总数。负Margin0、非有限Margin0；Margin=0与原reference_top1_tie_counts>1逐位置一致。全部103700条TV仅按doc_id+position键对齐保留，未扩大推理或进行额外模型计算。','','## 翻转位置Margin分位数','','| 分位数 | 原始logit Margin |','|---|---:|']
 for q,v in s['flip_margin_quantiles'].items():report.append(f'| {float(q)*100:g}% | {v:.12g} |')
 report+=['',f'最大翻转Margin={s["flip_margin_max"]:.12g}，平均={s["flip_margin_mean"]:.12g}。高Margin清单预定义为margin≥1.0（最后两个桶）；共0条，high_margin_flips_ge1.csv仍保留表头。另将全部翻转按Margin降序排列，保留最高20条，避免高Margin为空时隐藏最大案例。','','## Margin最大的翻转案例','','| 文档ID | 位置(0起) | 参考Margin | reference Top1 ID | current Top1 ID | 对齐TV |','|---|---:|---:|---:|---:|---:|']
 for p in s['top20_highest_margin_flips'][:10]:report.append(f'| {p["doc_id"]} | {p["position"]} | {p["reference_top1_margin"]:.10g} | {p["reference_top1_id"]} | {p["current_top1_id"]} | {p["softmax_tv"]:.10g} |')
 report+=['','结论仅描述该冻结集合：翻转集中在参考前两名logit较接近的位置。翻转不等于任务标签判错，也未确定是哪一层/算子导致。未新增置信区间或独立token假设。没有GPU/模型重跑，未改历史源或三摘要。','','![参考Logit Margin分层](reference_logit_margin_top1_flips.png)','','[主表CSV](buckets.csv) · [全部103700位置CSV](positions.csv) · [1053翻转CSV](top1_flips.csv) · [高Margin≥1清单](high_margin_flips_ge1.csv) · [最高Margin20条](highest_margin_flips_top20.csv) · [源SHA](source_manifest.json) · [独立CSV复核](independent_csv_checks.json) · [固定方案](protocol.json)']
 (HERE/'report.md').write_text('\n'.join(report)+'\n')
 write(HERE/'artifact_manifest.json',dict(renderer_source=identity(Path(__file__)),analysis_source=identity(HERE/'stratify.py'),protocol=identity(HERE/'protocol.json'),outputs=[identity(HERE/n) for n in ['summary.json','validation.json','source_manifest.json','independent_csv_checks.json','buckets.csv','positions.csv','top1_flips.csv','document_checks.csv','high_margin_flips_ge1.csv','highest_margin_flips_top20.csv','report.md','reference_logit_margin_top1_flips.png']],wall_seconds=time.monotonic()-started))
 print(json.dumps(dict(passed=True,counts=counts.tolist(),flips=flipcounts.tolist(),output=str(HERE/'reference_logit_margin_top1_flips.png')),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
