"""CPU-only independent FP64 output-head witnesses on fixed document/token indices.
This changes host-head arithmetic for the audit and does not claim bitwise FP32
GEMM equivalence. It checks the numerical TV/Top1 direction at fixed witnesses.
"""
import argparse,json,os,hashlib,time
from pathlib import Path
import numpy as np

def main():
    import torch
    from safetensors import safe_open
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1);started=time.monotonic();m=json.loads((a.input/'manifest.json').read_text());model=Path(m['checkpoint_dir']);index=json.loads((model/'model.safetensors.index.json').read_text());shard=model/index['weight_map']['lm_head.weight']
    rows=[json.loads(x) for x in (a.input/'metrics.jsonl').read_text().splitlines()];lookup={(r['index'],r['arm']):r for r in rows}
    selected=[i for i in [0,4,35] if (i,'baseline') in lookup]
    plan=dict(document_indices=selected,positions='sorted unique [0,T//2,T-1]',arms=['baseline','linear_last1','reference'],choice='Fixed ordinal witnesses [0,4,35]; declared during validation, never selected by observed error',arithmetic='CPU FP64 hidden@BF16-as-FP64 head, stable full-vocabulary softmax; differs from production FP32 head arithmetic',comparison_tv_atol=1e-5)
    (a.output/'head_witness_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    tests=[]
    with safe_open(str(shard),framework='pt',device='cpu') as reader:
        view=reader.get_slice('lm_head.weight');V,D=view.get_shape()
        for i in selected:
            directory=a.input/'documents'/f'doc{i:03d}';T=lookup[i,'baseline']['tokens'];positions=sorted(set([0,T//2,T-1]));hidden=[]
            for arm in plan['arms']:
                with np.load(directory/f'{arm}_hidden.npz',allow_pickle=False) as raw:hidden.append(raw['final'].reshape(T,D)[positions].astype(np.float64))
            inputs=torch.from_numpy(np.concatenate(hidden,axis=0));scores=np.empty((len(inputs),V),dtype=np.float64)
            for first in range(0,V,4096):
                last=min(V,first+4096);w=view[first:last].to(torch.float64)
                scores[:,first:last]=(inputs@w.T).numpy();del w
            chunks=np.split(scores,3,axis=0);reference=chunks[-1]
            def softmax(x):
                z=np.exp(x-x.max(axis=1,keepdims=True));return z/z.sum(axis=1,keepdims=True)
            rp=softmax(reference);rid=reference.argmax(axis=1)
            for arm,score in zip(plan['arms'][:-1],chunks[:-1]):
                probability=softmax(score);tv=.5*np.abs(probability-rp).sum(axis=1);ids=score.argmax(axis=1);old=lookup[i,arm]['logits'];actual=old['softmax_tv']['tv'];rmse=np.sqrt(((score-reference)**2).mean(axis=1))
                for j,t in enumerate(positions):
                    diff=abs(float(tv[j])-actual[t]);expected_ids=[old['per_token']['current_top1_ids'][t],old['per_token']['reference_top1_ids'][t]]
                    tests.append(dict(index=i,doc_id=lookup[i,arm]['doc_id'],arm=arm,position=t,fp64_head_tv=float(tv[j]),production_fp32_head_tv=actual[t],tv_abs_difference=diff,tv_within_audit_atol=diff<=1e-5,fp64_head_top1_ids=[int(ids[j]),int(rid[j])],production_fp32_head_top1_ids=expected_ids,top1_ids_equal=[int(ids[j]),int(rid[j])]==expected_ids,fp64_head_logit_rmse=float(rmse[j]),production_fp32_head_logit_rmse=old['per_token']['logit_rmse'][t],probability_mass_defect=float(max(abs(probability[j].sum()-1),abs(rp[j].sum()-1)))))
    result=dict(schema='r007_independent_cpu_fp64_head_witness_v1',plan=plan,witness_count=len(tests),passed=all(r['tv_within_audit_atol'] for r in tests),max_tv_abs_difference=max(r['tv_abs_difference'] for r in tests),all_top1_ids_equal=all(r['top1_ids_equal'] for r in tests),max_probability_mass_defect=max(r['probability_mass_defect'] for r in tests),wall_seconds=time.monotonic()-started,head_checkpoint_shard=str(shard),checkpoint_index_sha256=hashlib.sha256((model/'model.safetensors.index.json').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),witnesses=tests,limitation='FP64 independent audit of18 selected token/arm pairs, not all measured positions and not bitwise proof of production FP32 GEMM.')
    (a.output/'independent_head_witness.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['witnesses','plan']}))

if __name__=='__main__':main()
