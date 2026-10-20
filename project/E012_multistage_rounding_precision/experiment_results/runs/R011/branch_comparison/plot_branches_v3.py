"""Presentation-only branch comparison wording v3; all original data/source retained."""
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
fig.text(.5,.92,'Current vs reference trajectories  |  3 saved diagnostic documents / 299 tokens  |  1,224,704 values per branch',ha='center',fontsize=11)
specs=[('absolute_rmse','Absolute RMSE','real units'),('reference_rms','Reference output RMS','real units'),('relative_l2_percent','Relative L2','percent')]
colors=['#2563eb','#ea580c']
for j,(key,title,ylabel) in enumerate(specs):
 ax=axs[0,j];values=[branches[n][key] for n in branches];bars=ax.bar([0,1],values,color=colors,width=.56);ax.set_xticks([0,1],['Attention output','MLP output']);ax.set_title(title+'\nMLP / Attention = '+f'{ratios[key]:.4f}x',fontsize=12);ax.set_ylabel(ylabel);ax.set_ylim(0,max(values)*1.25)
 for bar,v in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,v+max(values)*.035,f'{v:.7f}',ha='center',va='bottom',fontsize=11)
 ax=axs[1,j]
 if key=='relative_l2_percent':
  ns=['gated_product','prepare3_dequant','down_proj'];vals=[mlp[n]['AB_cross'][key] for n in ns]
  ax.plot(range(3),vals,color='#dc2626',marker='o',linewidth=2.5,markersize=7);ax.set_xticks(range(3),['Product','H32 + U8 requant','Down output']);ax.set_title('MLP relative L2: product to Down',fontsize=12);ax.set_ylabel('percent');ax.set_ylim(0,max(vals)*1.3);ax.margins(x=.12)
  for i,v in enumerate(vals):ax.annotate(f'{v:.6f}%',(i,v),xytext=(0,12),textcoords='offset points',ha='center',fontsize=11)
 else:
  vals=[mlp[n]['AB_cross'][key] for n in STAGES];bars=ax.bar(range(len(STAGES)),vals,color='#475569',width=.72);ax.set_xticks(range(len(STAGES)),LABELS,rotation=50,ha='right');ax.set_title('MLP stages: '+title.lower(),fontsize=12);ax.set_ylabel(ylabel);ax.set_ylim(0,max(vals)*1.26)
  for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+max(vals)*.025,f'{v:.4f}',ha='center',va='bottom',rotation=65,fontsize=8)
fig.text(.5,.025,'Both branch outputs are measured before residual addition. Gate and Up are parallel projections.\nMetrics are pooled over these 3 diagnostic documents.',ha='center',fontsize=10,color='#334155')
fig.savefig(HERE/'pure_branch_comparison_v3.png',dpi=180);plt.close(fig)
