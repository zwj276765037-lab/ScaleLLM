"""R009 CPU-only independent raw-array checks, aggregate comparisons and PNG."""
import argparse,csv,hashlib,json,math,os
from pathlib import Path
import numpy as np

ARMS=['baseline_b0','candidate_b2','candidate_b4','output_only_reference_b0','output_only_reference_b2','output_only_reference_b4']
LABELS={'baseline_b0':'Baseline F16','candidate_b2':'+2 bits F18','candidate_b4':'+4 bits F20','output_only_reference_b0':'Reference F16','output_only_reference_b2':'Reference F18'}

def write(p,x):
    p=Path(p);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');os.replace(t,p)

def load_raw(inp,index,arm,verify_link=True):
    directory=inp/'documents'/f'doc{index:03d}';link=directory/f'{arm}_raw_link.json'
    if link.exists():
        entry=json.loads(link.read_text());source=Path(entry['source']['path'])
        if verify_link:assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['source']['sha256']
        with np.load(source,allow_pickle=False) as raw:return {k:raw[k].copy() for k in ['final','pre_norm']}
    with np.load(directory/f'{arm}_hidden.npz',allow_pickle=False) as raw:return {k:raw[k].copy() for k in raw.files}

def energy(a,b):
    delta=a.astype(np.float64)-b.astype(np.float64);signal=b.astype(np.float64)
    e=float(np.sum(delta*delta));s=float(np.sum(signal*signal))
    return dict(error_energy=e,signal_energy=s,relative_l2_percent=100*math.sqrt(e/s),absolute_max=float(abs(delta).max()))

def select(rows,relation):
    r=[x for x in rows if x['relation']==relation]
    if relation=='matched_format':r += [x for x in rows if x['relation']=='common_fixed' and x['arm']=='candidate_b4']
    return r

def independent_summary(rows):
    ans={}
    for arm in dict.fromkeys(r['arm'] for r in rows):
        rr=[r for r in rows if r['arm']==arm];n=sum(r['tokens'] for r in rr);metrics={}
        for key in ['layer32_pre_norm','final_hidden','logits']:
            vals=np.array([r[key]['relative_l2_percent'] for r in rr]);e=sum(r[key]['error_energy'] for r in rr);s=sum(r[key].get('signal_energy',r[key].get('reference_signal_energy',0)) for r in rr)
            metrics[key]=dict(document_median_percent=float(np.median(vals)),document_mean_percent=float(vals.mean()),document_p95_percent=float(np.quantile(vals,.95)),document_max_percent=float(vals.max()),pooled_relative_l2_percent=100*math.sqrt(e/s))
        tv=np.array([v for r in rr for v in r['logits']['softmax_tv']['tv']]);errors=sum(r['tokens']-r['logits']['top1_match_count'] for r in rr)
        metrics.update(documents=len(rr),positions=n,top1_errors=errors,top1_agreement=1-errors/n,tv=dict(pooled_mean=float(tv.mean()),position_median=float(np.median(tv)),position_p95=float(np.quantile(tv,.95)),position_p99=float(np.quantile(tv,.99)),position_max=float(tv.max()),positions_above_1pct=int((tv>.01).sum()),positions_above_5pct=int((tv>.05).sum()),positions_above_10pct=int((tv>.1).sum())))
        ans[arm]=metrics
    return ans

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    result=json.loads((a.input/'result.json').read_text());rows=[json.loads(x) for x in (a.input/'metrics.jsonl').read_text().splitlines()];assert len(rows)==252
    coordinates=[(r['index'],r['relation'],r['arm'],r['reference_arm']) for r in rows];assert len(set(coordinates))==252 and set(r['index'] for r in rows)==set(range(36))
    final_count=0;pre_count=0;max_l2=0.;max_erel=0.;prefix_count=0;scale_count=0;allchecks=[];positions=[]
    for index in range(36):
        raw={arm:load_raw(a.input,index,arm) for arm in ARMS}
        records={arm:json.loads((a.input/'documents'/f'doc{index:03d}'/f'{arm}_record.json').read_text()) for arm in ARMS}
        for arm,base in [('candidate_b2','baseline_b0'),('candidate_b4','baseline_b0'),('output_only_reference_b2','output_only_reference_b0'),('output_only_reference_b4','output_only_reference_b0')]:
            assert records[arm]['prefix_hashes']==records[base]['prefix_hashes'];prefix_count+=31
        for arm,record in records.items():
            assert record['attributes_and_functions_restored']
            events=record['output_boundary_events'];b=record['b']
            if b:
                assert sorted((e['kind'],e['op']) for e in events)==sorted((kind,op) for kind in ['wide_projection','host_scale'] for op in ['o_proj','down_proj'])
                assert all(e['input_dtype']==e['output_dtype']=='torch.float32' and e['scale']==2.**(-b) for e in events if e['kind']=='host_scale');scale_count+=2
            else:assert not events
        for row in [r for r in rows if r['index']==index]:
            cur=raw[row['arm']];ref=raw[row['reference_arm']]
            for array,key in [('final','final_hidden'),('pre_norm','layer32_pre_norm')]:
                if array not in cur or array not in ref:continue
                metric=energy(cur[array],ref[array]);stored=row[key];d=abs(metric['relative_l2_percent']-stored['relative_l2_percent']);er=abs(metric['error_energy']-stored['error_energy'])/max(1,stored['error_energy']);max_l2=max(max_l2,d);max_erel=max(max_erel,er);assert d<1e-10 and er<1e-11
                if array=='final':final_count+=1
                else:pre_count+=1
            lm=row['logits'];ident=lm['final_hidden_identity']
            for side,value in [('current',cur['final']),('reference',ref['final'])]:assert hashlib.sha256(value.reshape(-1,4096).tobytes()).hexdigest()==ident[side]['sha256']
            matches=[x==y for x,y in zip(lm['per_token']['current_top1_ids'],lm['per_token']['reference_top1_ids'])];tv=lm['softmax_tv'];assert matches==lm['per_token']['top1_matches'] and sum(matches)==lm['top1_match_count'];assert len(tv['tv'])==row['tokens']
            assert all(0<=x<=1+1e-10 for x in tv['tv']);assert all(abs(x-1)<1e-10 for k in ['probability_mass_current','probability_mass_reference'] for x in tv[k]);assert abs(float(np.mean(tv['tv']))-tv['document_mean'])<1e-14
            allchecks.append(dict(index=index,relation=row['relation'],arm=row['arm'],final_hidden_recomputed=True,pre_norm_recomputed='pre_norm' in cur and 'pre_norm' in ref,head_input_hashes_equal=True,top1_ids_equal=True,tv_mass_range_valid=True))
            for t,(v,m) in enumerate(zip(tv['tv'],matches)):positions.append(dict(index=index,doc_id=row['doc_id'],partition=row['partition'],relation=row['relation'],arm=row['arm'],reference_arm=row['reference_arm'],position=t,tv=v,top1_match=m))
    summaries={relation:independent_summary(select(rows,relation)) for relation in ['common_fixed','matched_format','reference_drift']}
    for relation,summary in summaries.items():
        for arm,metrics in summary.items():
            stored=result[relation][arm]
            for key in ['layer32_pre_norm','final_hidden','logits']:
                for stat,value in metrics[key].items():assert abs(value-stored[key][stat])<1e-10
            assert metrics['top1_errors']==stored['top1_errors']
            for key,value in metrics['tv'].items():assert abs(value-stored['tv'][key])<1e-13
    write(a.output/'independent_checks.json',dict(passed=True,comparison_rows=252,final_hidden_npz_pairs_recomputed=final_count,pre_norm_npz_pairs_recomputed=pre_count,prefix_layer_hash_comparisons=prefix_count,host_scale_once_events_verified=scale_count,max_hidden_l2_abs_difference=max_l2,max_hidden_error_energy_relative_difference=max_erel,checks=allchecks,scope='All finalhidden raw pairs; pre-norm only available raw per protocol plus legacy b0 pair; all JSON Top1/TV mass/range/aggregate/prefix/binding records. Independent head witnesses separate.'))
    write(a.output/'independent_summary.json',summaries)
    deltas=[];document_rows=[];common=summaries['common_fixed'];base=common['baseline_b0']
    for arm in ['candidate_b2','candidate_b4']:
        x=common[arm];directions={name:dict(improved=0,worse=0,equal=0) for name in ['layer32_pre_norm','final_hidden','logits','tv','top1_errors']}
        for index in range(36):
            pairs={r['arm']:r for r in rows if r['index']==index and r['relation']=='common_fixed'};br=pairs['baseline_b0'];cr=pairs[arm]
            vals={key:(br[key]['relative_l2_percent'],cr[key]['relative_l2_percent']) for key in ['layer32_pre_norm','final_hidden','logits']};vals.update(tv=(br['logits']['softmax_tv']['document_mean'],cr['logits']['softmax_tv']['document_mean']),top1_errors=(br['tokens']-br['logits']['top1_match_count'],cr['tokens']-cr['logits']['top1_match_count']))
            for name,(bv,cv) in vals.items():
                directions[name]['improved' if cv<bv else 'worse' if cv>bv else 'equal']+=1;document_rows.append(dict(index=index,doc_id=br['doc_id'],partition=br['partition'],arm=arm,metric=name,baseline=bv,candidate=cv,delta=cv-bv))
        reduction=lambda bv,cv:100*(bv-cv)/bv if bv else None
        deltas.append(dict(arm=arm,mean_tv_relative_reduction_percent=reduction(base['tv']['pooled_mean'],x['tv']['pooled_mean']),l32_median_relative_reduction_percent=reduction(base['layer32_pre_norm']['document_median_percent'],x['layer32_pre_norm']['document_median_percent']),finalhidden_median_relative_reduction_percent=reduction(base['final_hidden']['document_median_percent'],x['final_hidden']['document_median_percent']),logit_median_relative_reduction_percent=reduction(base['logits']['document_median_percent'],x['logits']['document_median_percent']),top1_error_change=x['top1_errors']-base['top1_errors'],tv_p95_change=x['tv']['position_p95']-base['tv']['position_p95'],tv_p99_change=x['tv']['position_p99']-base['tv']['position_p99'],tv_max_change=x['tv']['position_max']-base['tv']['position_max'],directions=directions))
    write(a.output/'comparison_deltas.json',dict(common_reference='output_only_reference_b4',deltas=deltas))
    for filename,rr in [('per_document_deltas.csv',document_rows),('per_position_metrics.csv',positions)]:
        with (a.output/filename).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(3,3,figsize=(14,11));fig.suptitle('R009: true last-layer F18/F20 outputs; common reference F20, all36 development documents',fontsize=13)
    def bars(ax,summary,key,stat,title,multiplier=1):
        arms=list(summary);values=[summary[x][key][stat]*multiplier for x in arms] if key else [summary[x][stat]*multiplier for x in arms]
        ax.bar(range(len(arms)),values,color=['#777' if x=='baseline_b0' else '#2171b5' if 'candidate' in x else '#6b8e23' for x in arms]);ax.set_xticks(range(len(arms)),[LABELS[x] for x in arms],rotation=15,ha='right');ax.set_title(title,fontsize=10);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        for i,v in enumerate(values):ax.text(i,v,f'{v:.6f}' if abs(v)<10 else f'{v:.3f}',ha='center',va='bottom',fontsize=8)
        ax.set_ylim(0,max(values)*1.18 if max(values)>0 else 1)
    for col,(key,title) in enumerate([('layer32_pre_norm','Layer32 before final norm: median L2 (%)'),('final_hidden','Final hidden: median L2 (%)'),('logits','Full-vocabulary logits: median L2 (%)')]):bars(axs[0,col],common,key,'document_median_percent',title)
    bars(axs[1,0],common,'tv','pooled_mean','Common ref4: pooled mean TV (%)',100);bars(axs[1,1],common,'tv','position_p99','Common ref4: position P99 TV (%)',100);bars(axs[1,2],common,None,'top1_errors','Common ref4: Top1 disagreements /4494')
    bars(axs[2,0],summaries['matched_format'],'final_hidden','document_median_percent','Matched-format refs: final hidden median L2 (%)');bars(axs[2,1],summaries['matched_format'],'tv','pooled_mean','Matched-format refs: mean TV (%)',100);bars(axs[2,2],summaries['reference_drift'],'tv','pooled_mean','Reference drift to ref4: mean TV (%)',100)
    tails=[]
    for arm,x in common.items():tails.append(f"{LABELS[arm]}: TV P95/P99/max={100*x['tv']['position_p95']:.6f}/{100*x['tv']['position_p99']:.6f}/{100*x['tv']['position_max']:.6f}%; Top1 errors={x['top1_errors']}/4494")
    fig.text(.02,.008,'\n'.join(tails)+'\nRepeated development data, all candidates retained. Endpoint format changes only at layer31 o_proj/down_proj. No task/RTL timing claim.',fontsize=8,family='monospace',va='bottom');fig.tight_layout(rect=(0,.1,1,.95));fig.savefig(a.output/'r009_precision_comparison.png',dpi=160);plt.close(fig)
    write(a.output/'analysis_manifest.json',dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),input_result_sha256=hashlib.sha256((a.input/'result.json').read_bytes()).hexdigest(),metrics_sha256=hashlib.sha256((a.input/'metrics.jsonl').read_bytes()).hexdigest(),checks_passed=True,rows=252,documents=36,positions=4494,plot='r009_precision_comparison.png'))
    print(json.dumps(dict(passed=True,final_pairs=final_count,pre_pairs=pre_count,deltas=deltas)))

if __name__=='__main__':main()
