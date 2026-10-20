"""CPU-only independent raw-hidden/JSON checks and complete R007 comparison PNG."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os
from pathlib import Path
import numpy as np

LABELS={'baseline':'Baseline','linear_last1':'Linear last1','linear_all32':'Linear all32','linear_pv_all32':'Linear+PV all32'}

def write(path,obj):
    p=Path(path);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');os.replace(t,p)

def independent_metric(a,b):
    d=a.astype(np.float64)-b.astype(np.float64);r=b.astype(np.float64)
    e=float(np.sum(d*d,dtype=np.float64));s=float(np.sum(r*r,dtype=np.float64))
    return dict(error_energy=e,signal_energy=s,relative_l2_percent=100*math.sqrt(e/s),absolute_max=float(np.max(abs(d))),signed_error_sum=float(np.sum(d)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    result=json.loads((a.input/'result.json').read_text());manifest=json.loads((a.input/'manifest.json').read_text())
    rows=[json.loads(x) for x in (a.input/'metrics.jsonl').read_text().splitlines()]
    checks=[];max_l2diff=0.;max_energy_relative=0.;position_rows=[]
    for row in rows:
        directory=a.input/'documents'/f"doc{row['index']:03d}"
        with np.load(directory/f"{row['arm']}_hidden.npz",allow_pickle=False) as cur,np.load(directory/'reference_hidden.npz',allow_pickle=False) as ref:
            for raw,key in [('pre_norm','layer32_pre_norm'),('final','final_hidden')]:
                value=independent_metric(cur[raw],ref[raw]);stored=row[key]
                ld=abs(value['relative_l2_percent']-stored['relative_l2_percent']);max_l2diff=max(max_l2diff,ld)
                er=abs(value['error_energy']-stored['error_energy'])/max(1,stored['error_energy']);max_energy_relative=max(max_energy_relative,er)
                if ld>1e-10 or er>1e-11:raise AssertionError('hidden recomputation mismatch')
            f=cur['final'].reshape(-1,4096);rf=ref['final'].reshape(-1,4096)
            ids=row['logits']['final_hidden_identity']
            assert hashlib.sha256(f.tobytes()).hexdigest()==ids['current']['sha256']
            assert hashlib.sha256(rf.tobytes()).hexdigest()==ids['reference']['sha256']
        logit=row['logits'];per=logit['per_token'];tv=logit['softmax_tv']
        matches=[x==y for x,y in zip(per['current_top1_ids'],per['reference_top1_ids'])]
        assert matches==per['top1_matches'] and sum(matches)==logit['top1_match_count']
        assert len(matches)==len(tv['tv'])==row['tokens']
        assert abs(float(np.mean(tv['tv']))-tv['document_mean'])<1e-14
        assert all(0<=x<=1+1e-10 for x in tv['tv'])
        assert all(abs(x-1)<=1e-10 for name in ['probability_mass_current','probability_mass_reference'] for x in tv[name])
        for position,(v,m) in enumerate(zip(tv['tv'],matches)):
            position_rows.append(dict(partition=row['partition'],doc_id=row['doc_id'],arm=row['arm'],position=position,tv=v,top1_match=m))
        checks.append(dict(index=row['index'],doc_id=row['doc_id'],arm=row['arm'],hidden_recomputed=True,head_input_hashes_equal=True,top1_ids_recomputed=True,tv_range_mass_mean_checked=True))
    assert len({r['index'] for r in rows if r['partition']=='selection4'})==4
    if result['winner'] is not None:assert len({r['index'] for r in rows if r['partition']=='validation32'})==32
    for partition,summ in [('selection4',result['selection']),('validation32',result['validation'])]:
        for arm,stored in summ.items():
            rr=[r for r in rows if r['partition']==partition and r['arm']==arm]
            tv=np.array([x for r in rr for x in r['logits']['softmax_tv']['tv']])
            assert abs(float(tv.mean())-stored['tv']['pooled_mean'])<1e-14
            assert abs(float(np.quantile(tv,.95))-stored['tv']['position_p95'])<1e-14
            assert sum(r['tokens']-r['logits']['top1_match_count'] for r in rr)==stored['top1_errors']
    verdict={}
    doc_deltas=[]
    for partition,summ in [('selection4',result['selection']),('validation32',result['validation'])]:
        if not summ:continue
        base=summ['baseline'];arms=[x for x in summ if x!='baseline']
        verdict[partition]={}
        bykey={(r['index'],r['arm']):r for r in rows if r['partition']==partition}
        for arm in arms:
            x=summ[arm]
            def pct(b,c):return 100*(b-c)/b if b else None
            v=dict(tv_mean_relative_reduction_percent=pct(base['tv']['pooled_mean'],x['tv']['pooled_mean']),layer32_median_relative_reduction_percent=pct(base['layer32_pre_norm']['document_median_percent'],x['layer32_pre_norm']['document_median_percent']),finalhidden_median_relative_reduction_percent=pct(base['final_hidden']['document_median_percent'],x['final_hidden']['document_median_percent']),logit_median_relative_reduction_percent=pct(base['logits']['document_median_percent'],x['logits']['document_median_percent']),top1_error_change=x['top1_errors']-base['top1_errors'],tv_p95_change=x['tv']['position_p95']-base['tv']['position_p95'],tv_max_change=x['tv']['position_max']-base['tv']['position_max'])
            counts={name:dict(improved=0,equal=0,worse=0) for name in ['layer32_pre_norm','final_hidden','logits','tv','top1_errors']}
            for index in sorted({r['index'] for r in rows if r['partition']==partition}):
                b=bykey[index,'baseline'];c=bykey[index,arm]
                metrics={k:(b[k]['relative_l2_percent'],c[k]['relative_l2_percent']) for k in ['layer32_pre_norm','final_hidden','logits']}
                metrics.update(tv=(b['logits']['softmax_tv']['document_mean'],c['logits']['softmax_tv']['document_mean']),top1_errors=(b['tokens']-b['logits']['top1_match_count'],c['tokens']-c['logits']['top1_match_count']))
                for name,(bv,cv) in metrics.items():
                    counts[name]['improved' if cv<bv else 'worse' if cv>bv else 'equal']+=1
                    doc_deltas.append(dict(partition=partition,doc_id=b['doc_id'],arm=arm,metric=name,baseline=bv,candidate=cv,delta=cv-bv))
            v['per_document_direction_counts']=counts;verdict[partition][arm]=v
    write(a.output/'independent_checks.json',dict(passed=True,compared_rows=len(rows),max_hidden_relative_l2_abs_difference=max_l2diff,max_hidden_error_energy_relative_difference=max_energy_relative,checks=checks,scope='Independent NPZ hidden energies/hash checks and raw JSON aggregate/Top1/TV mass/range checks; full-vocab TV implementation was reused, not independently regenerated from missing full raw logits.'))
    write(a.output/'comparison_deltas.json',verdict)
    for name,data in [('per_document_deltas.csv',doc_deltas),('per_position_metrics.csv',position_rows)]:
        with (a.output/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9})
    fig,axs=plt.subplots(2,4,figsize=(15,8));fig.suptitle('R007 equal-width RNE: paired numerical fidelity against common output-only reference',fontsize=13)
    for rowidx,(part,summ,title) in enumerate([('selection4',result['selection'],'Selection: first4 dev documents'),('validation32',result['validation'],'Validation: next32 dev documents')]):
        if not summ:
            for ax in axs[rowidx]:ax.axis('off');ax.text(.5,.5,'No eligible candidate; validation not run',ha='center',va='center')
            continue
        arms=list(summ)
        for col,(key,name) in enumerate([('layer32_pre_norm','Layer32 before final norm'),('final_hidden','Final hidden'),('logits','Full-vocabulary logits'),('tv','Softmax TV, temperature1')]):
            ax=axs[rowidx,col];vals=[summ[arm][key]['document_median_percent'] if key!='tv' else summ[arm]['tv']['pooled_mean']*100 for arm in arms]
            bars=ax.bar(range(len(arms)),vals,color=['#777777' if x=='baseline' else '#2070b4' for x in arms]);ax.set_xticks(range(len(arms)),[LABELS[x] for x in arms],rotation=24,ha='right');ax.set_title(title+'\n'+name,fontsize=10)
            ax.set_ylabel('Document median relative L2 (%)' if key!='tv' else 'Pooled mean TV (%)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
            for bar,value in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,bar.get_height(),f'{value:.5f}',ha='center',va='bottom',fontsize=8)
            ax.set_ylim(0,max(vals)*1.17)
    tails=[]
    for part,summ in [('selection4',result['selection']),('validation32',result['validation'])]:
        for arm,x in summ.items():tails.append(f"{part} | {LABELS[arm]}: TV p95/p99/max={100*x['tv']['position_p95']:.4f}/{100*x['tv']['position_p99']:.4f}/{100*x['tv']['position_max']:.4f}%; Top1 errors={x['top1_errors']}/{x['positions']}")
    fig.text(.02,.012,'\n'.join(tails)+'\nDevelopment evidence only. All real positions retained. No RTL timing or task ACC/PPL conclusion.',fontsize=7.6,family='monospace',va='bottom')
    fig.tight_layout(rect=(0,.23,1,.95));fig.savefig(a.output/'rounding_comparison.png',dpi=160);plt.close(fig)
    resources=[json.loads(x) for x in (a.input/'resources.jsonl').read_text().splitlines()]
    write(a.output/'analysis_manifest.json',dict(source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),input_result_sha256=hashlib.sha256((a.input/'result.json').read_bytes()).hexdigest(),raw_metrics_sha256=hashlib.sha256((a.input/'metrics.jsonl').read_bytes()).hexdigest(),documents=result['measured_selection_documents']+result['measured_validation_documents'],gpu_wall_seconds=result['gpu_wall_seconds'],max_sampled_rss_bytes=max(x['rss_bytes'] for x in resources),min_sampled_gpu_free_bytes=min(x['gpu_free_bytes'] for x in resources),peak_gpu_allocated_bytes=result['peak_gpu_allocated_bytes'],candidate_source_sha256=next(x['sha256'] for x in manifest['source'] if x['path'].endswith('/candidate.py')),independent_checks_passed=True,plot='rounding_comparison.png',scope=result['scope']))
    print(json.dumps(dict(checks='PASS',winner=result['winner'],deltas=verdict)))

if __name__=='__main__':main()
