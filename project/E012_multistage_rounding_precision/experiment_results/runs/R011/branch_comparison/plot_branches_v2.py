"""Presentation-only branch comparison layout v2; all original data/source retained."""
from pathlib import Path
import json,hashlib
from analyze_branches import STAGES,LABELS
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
summary=json.loads((HERE/'summary.json').read_text())
branches=summary['pooled_branches_AB'];mlp=summary['MLP_stages'];ratios=summary['MLP_over_attention_ratios_AB']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','axes.grid':True,'grid.alpha':.18,'axes.axisbelow':True})
fig,axs=plt.subplots(2,3,figsize=(16,9.4));fig.subplots_adjust(left=.065,right=.98,top=.84,bottom=.20,wspace=.28,hspace=.52)
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
fig.text(.5,.025,'Branch outputs are measured before residual addition. Gate and Up are parallel projections.\nA/C and C/B are reported in separate tables; no GPU/model rerun and no 1024-document extrapolation.',ha='center',fontsize=10,color='#334155')
fig.savefig(HERE/'pure_branch_comparison_v2.png',dpi=180);plt.close(fig)
report=(HERE/'report.md').read_text().replace('pure_branch_comparison.png','pure_branch_comparison_v2.png').replace('这支持传播差主导，但不确定全32层某个量化算子的全局因果占比。','这说明已有输入差异足以产生此量级的分支差；A/C项仍有交叉抵消，不能称其完全可忽略，也不能确定全32层某量化算子的全局因果占比。')
(HERE/'report_v2.md').write_text(report)
files=['summary.json','pure_branch_comparison.png','report.md','pure_branch_comparison_v2.png','report_v2.md','plot_branches_v2.py']
(HERE/'layout_v2_manifest.json').write_text(json.dumps(dict(scope='Presentation-only bottom spacing and qualified causal wording; original PNG/report/source preserved',files=[dict(path=str((HERE/n).resolve()),bytes=(HERE/n).stat().st_size,sha256=hashlib.sha256((HERE/n).read_bytes()).hexdigest()) for n in files]),indent=2)+'\n')
print('Generated final readable PNG/report v2; original analysis artifacts retained')
