#!/usr/bin/env python3
"""Render the README's FPGA-only performance and all 16 recorded responses."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,textwrap
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'docs/evidence/kv128_chat16'
NAVY='#17324D'; TEAL='#159A9C'; BLUE='#2E6FAD'; GRAY='#627386'; BG='#F5F8FC'; EDGE='#DFE7EF'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.labelcolor':NAVY,
 'text.color':NAVY,'xtick.color':GRAY,'ytick.color':GRAY,'svg.fonttype':'none',
 'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,
 'axes.spines.bottom':False,'axes.axisbelow':True,'savefig.facecolor':'white'})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def save(fig,stem):
 for ext in ['svg','png']:fig.savefig(stem.with_suffix('.'+ext),dpi=170,bbox_inches='tight',pad_inches=.12)
 plt.close(fig)
def wrap(s,width):
 lines=[]
 for paragraph in s.expandtabs(4).split('\n'):
  lines.extend(textwrap.wrap(paragraph,width=width,break_long_words=False,break_on_hyphens=False) or [''])
 return lines

def derive(native_run):
 commands=list(csv.DictReader((DATA/'results/commands.csv').open()))
 model=json.loads(native_run.read_text());by_round=defaultdict(list)
 for r in commands:by_round[int(r['round'])].append(r)
 rows=[]
 for step in model['steps']:
  n=step['index']+1;rs=by_round[n]
  assert len(rs)==64 and all(int(r['active_count'])==16 and int(r['common_kv'])==n for r in rs)
  ac=sum(int(r['done_cycles']) for r in rs if r['opcode']=='Attention')
  mc=sum(int(r['done_cycles']) for r in rs if r['opcode']=='MLP')
  assert ac+mc==step['fpga_cycles']
  emitted=len(step['emitted']);secs=(ac+mc)/80e6
  rows.append({'round':n,'position':n-1,'kv_length':n,'active_requests':16,
   'actual_emitted_tokens':emitted,'attention_done_cycles':ac,'mlp_done_cycles':mc,
   'total_done_cycles':ac+mc,'attention_fpga_s':ac/80e6,'mlp_fpga_s':mc/80e6,
   'total_fpga_s':secs,'decode16_fpga_time_normalized_token_per_s':16/secs if emitted==16 else ''})
 assert len(rows)==128 and sum(r['actual_emitted_tokens'] for r in rows)==1784
 out=DATA/'results/fpga_performance_rounds.csv'
 with out.open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 dump(DATA/'results/fpga_performance_provenance.json',{
  'schema':'scalellm_fpga_showcase_source_v1','evidence_kind':'BOARD_COMMAND_COUNTERS',
  'core_hz':80_000_000,'commands_sha256':sha(DATA/'results/commands.csv'),
  'model_run_archive_path':'board/native/run_002/device/run.json','model_run_sha256':sha(native_run),
  'csv_sha256':sha(out),'rows':128,'decode16_rows':sum(r['actual_emitted_tokens']==16 for r in rows),
  'formula':'FPGA time = sum(DONE_CYCLES)/80e6; decode throughput = actual 16 emitted tokens / FPGA time',
  'exclusions':['CPU Down and LM head','other host processing','transfers/waits outside hardware commands'],
  'not_end_to_end_model_throughput':True})

def performance():
 rows=list(csv.DictReader((DATA/'results/fpga_performance_rounds.csv').open()))
 selected=[r for r in rows if int(r['actual_emitted_tokens'])==16]
 assert len(selected)==110 and int(selected[0]['kv_length'])==19
 x=[int(r['kv_length']) for r in selected]
 a=[float(r['attention_fpga_s']) for r in selected];m=[float(r['mlp_fpga_s']) for r in selected]
 rate=[float(r['decode16_fpga_time_normalized_token_per_s']) for r in selected]
 fig,axes=plt.subplots(1,2,figsize=(11.6,4.65),gridspec_kw={'wspace':.30})
 fig.subplots_adjust(top=.73,bottom=.19,left=.07,right=.98)
 fig.text(.055,.96,'FPGA decode performance',fontsize=22,weight='bold',va='top')
 fig.text(.055,.865,'Llama-3.1-8B-Instruct   /   16 active requests   /   VCU118   /   80 MHz',fontsize=10.5,color=GRAY)
 ax=axes[0];ax.stackplot(x,m,a,labels=['MLP frontend','Attention'],colors=[TEAL,NAVY],alpha=.94)
 ax.set_title('Execution time per 16-request step',loc='left',fontsize=12,pad=13,weight='bold')
 ax.set(xlim=(19,128),ylim=(0,2.25),xlabel='KV length',ylabel='FPGA command time (s)')
 ax.set_xticks([19,32,64,96,128]);ax.grid(axis='y',color=EDGE,linewidth=.8)
 ax.legend(frameon=False,ncol=2,loc='upper left',fontsize=9.5)
 ax=axes[1];ax.plot(x,rate,color=BLUE,linewidth=2.8)
 ax.set_title('Aggregate throughput over FPGA time',loc='left',fontsize=12,pad=13,weight='bold')
 ax.set(xlim=(19,128),ylim=(0,16),xlabel='KV length',ylabel='Generated tokens / FPGA second')
 ax.set_xticks([19,32,64,96,128]);ax.set_yticks([0,4,8,12,16]);ax.grid(axis='y',color=EDGE,linewidth=.8)
 for kv,dx,dy in [(32,8,18),(128,-8,18)]:
  r=next(r for r in selected if int(r['kv_length'])==kv);v=float(r['decode16_fpga_time_normalized_token_per_s'])
  ax.scatter([kv],[v],s=42,color=BLUE,zorder=4)
  ax.annotate(f'KV {kv}  ·  {v:.3f} tok/s',(kv,v),xytext=(dx,dy),textcoords='offset points',fontsize=9.8,weight='bold',color=BLUE,ha='right' if kv==128 else 'left')
 fig.text(.055,.035,'Measured DONE_CYCLES across 32 Attention + 32 MLP commands per step. CPU work and command-external transfers excluded.',fontsize=8.6,color=GRAY)
 save(fig,DATA/'showcase/fpga_performance')
 return {str(k):next(r for r in selected if int(r['kv_length'])==k) for k in [32,128]}

def responses(tokens):
 pattern=re.compile(r'^<\|begin_of_text\|><\|start_header_id\|>user<\|end_header_id\|>\n\n(.*?)<\|eot_id\|><\|start_header_id\|>assistant<\|end_header_id\|>\n\n$',re.S)
 records=[]
 for slot in range(16):
  r=tokens['slots'][str(slot)];match=pattern.fullmatch(r['prompt_text']);assert match
  records.append({'slot':slot,'request':slot+1,'prompt':match.group(1),'output':r['generated_text'],'tokens':r['generated_count']})
 assert sum(r['tokens'] for r in records)==1784
 for start in range(0,16,4):
  batch=records[start:start+4]
  for r in batch:r['plines']=wrap(r['prompt'],47);r['lines']=wrap(r['output'],54)
  heights=[max(1.08+.217*len(r['plines'])+.205*len(r['lines']) for r in batch[j:j+2]) for j in [0,2]]
  total=sum(heights)+1.15
  fig=plt.figure(figsize=(10.6,total));fig.patch.set_facecolor('white')
  fig.text(.035,1-.05/total,f'Recorded requests {start+1:02d}–{start+4:02d}',fontsize=17,weight='bold',va='top')
  fig.text(.035,1-.36/total,'Actual board-run responses · full captured text · fixed KV128 stopping boundary',fontsize=9.7,color=GRAY,va='top')
  top=total-.72
  for row in range(2):
   h=heights[row]
   for col in range(2):
    r=batch[2*row+col];x=.035+col*.49;w=.455;y=(top-h)/total
    patch=FancyBboxPatch((x,y),w,h/total,boxstyle='round,pad=0.006,rounding_size=0.012',transform=fig.transFigure,facecolor=BG,edgecolor=EDGE,linewidth=.8,zorder=0)
    fig.add_artist(patch);left=x+.018;cy=top-.16
    fig.text(left,cy/total,f'REQUEST {r["request"]:02d}',fontsize=9.8,color=TEAL,weight='bold',va='top')
    fig.text(x+w-.018,cy/total,f'{r["tokens"]} tokens',fontsize=9.7,color=GRAY,ha='right',va='top')
    cy-=.30
    for line in r['plines']:
     fig.text(left,cy/total,line,fontsize=12.1,weight='bold',va='top',parse_math=False);cy-=.217
    cy-=.20
    for line in r['lines']:
     fig.text(left,cy/total,line,fontsize=10.9,color=NAVY,va='top',parse_math=False);cy-=.205
    assert cy>=top-h+.12,(r['slot'],cy,top-h)
   top-=h+.23
  save(fig,DATA/f'showcase/requests_{start:02d}_{start+3:02d}')
 text=['# All 16 recorded requests and outputs','',
       'Actual KV128 board run: 1,784 generated tokens. Prompt chat-template markers are hidden below; generated text is unchanged. The fixed stopping boundary can leave responses incomplete. Exact token IDs remain in `results/tokens.json`.','']
 for r in records:
  text.extend([f'## Request {r["request"]:02d} · slot {r["slot"]} · {r["tokens"]} generated tokens','',r['prompt'],'','```text',r['output'],'```',''])
 (DATA/'REQUESTS_AND_OUTPUTS.md').write_text('\n'.join(text),encoding='utf-8')
 return [{k:r[k] for k in ['slot','request','tokens']} for r in records]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native-run',type=Path,help='Optional archived device/run.json to regenerate the 128-row FPGA CSV')
 args=p.parse_args();(DATA/'showcase').mkdir(exist_ok=True)
 if args.native_run:derive(args.native_run)
 tokens=json.loads((DATA/'results/tokens.json').read_text());targets=performance();counts=responses(tokens)
 dump(DATA/'showcase/metadata.json',{'schema':'scalellm_readme_showcase_v1','evidence_kind':'BOARD_MEASUREMENT',
  'tokens_sha256':sha(DATA/'results/tokens.json'),'performance_csv_sha256':sha(DATA/'results/fpga_performance_rounds.csv'),
  'script_sha256':sha(Path(__file__)),'targets':targets,'requests':counts,
  'text_policy':'Full generated text retained; only chat-template framing is removed from displayed prompts; wrapping/tabs formatted for display. Fixed-length truncation is not repaired.',
  'speed_scope':'FPGA command counters only; excludes CPU processing and transfers outside hardware commands',
  'files':{f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted((DATA/'showcase').iterdir()) if f.suffix in {'.svg','.png'}}})
 print(json.dumps({'status':'PASS','requests':16,'generated_tokens':1784,'decode_steps':110,'targets':targets},indent=2))
if __name__=='__main__':main()
