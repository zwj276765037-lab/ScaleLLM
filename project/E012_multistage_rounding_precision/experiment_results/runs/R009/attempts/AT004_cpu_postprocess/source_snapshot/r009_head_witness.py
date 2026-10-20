"""Fixed ordinal CPU FP64 full-vocabulary head witnesses for R009 pairs."""
import argparse,json,hashlib,time
from pathlib import Path
import numpy as np
from r009_analyze_lastlayer import ARMS,load_raw

def main():
    import torch
    from safetensors import safe_open
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);torch.set_num_threads(1);started=time.monotonic()
    manifest=json.loads((a.input/'manifest.json').read_text());model=Path(manifest['checkpoint_dir']);index=json.loads((model/'model.safetensors.index.json').read_text());shard=model/index['weight_map']['lm_head.weight'];rows=[json.loads(x) for x in (a.input/'metrics.jsonl').read_text().splitlines()];tests=[]
    plan=dict(document_indices=[0,4,35],positions='sorted unique [0,T//2,T-1]',arms=ARMS,all_seven_measured_pairs_per_document=True,declared_before_gpu_model_results=True,arithmetic='Independent CPU FP64 hidden@BF16-as-FP64 head with stable full-vocab softmax; not bitwise production FP32 GEMM',tv_comparison_atol=1e-5)
    (a.output/'witness_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    with safe_open(str(shard),framework='pt',device='cpu') as reader:
        view=reader.get_slice('lm_head.weight');V,D=view.get_shape()
        for doc in plan['document_indices']:
            rr=[r for r in rows if r['index']==doc];T=rr[0]['tokens'];positions=sorted(set([0,T//2,T-1]));raw={arm:load_raw(a.input,doc,arm)['final'].reshape(T,D)[positions].astype(np.float64) for arm in ARMS};inputs=torch.from_numpy(np.concatenate([raw[x] for x in ARMS]));scores=np.empty((len(inputs),V),dtype=np.float64)
            for start in range(0,V,4096):
                stop=min(V,start+4096);w=view[start:stop].to(torch.float64);scores[:,start:stop]=(inputs@w.T).numpy();del w
            byarm=dict(zip(ARMS,np.split(scores,len(ARMS))));prob={};ids={}
            for arm,x in byarm.items():
                ex=np.exp(x-x.max(axis=1,keepdims=True));prob[arm]=ex/ex.sum(axis=1,keepdims=True);ids[arm]=x.argmax(axis=1)
            for r in rr:
                cur=r['arm'];ref=r['reference_arm'];tv=.5*np.abs(prob[cur]-prob[ref]).sum(axis=1);lm=r['logits']
                for j,t in enumerate(positions):
                    diff=abs(float(tv[j])-lm['softmax_tv']['tv'][t]);actual_ids=[int(ids[cur][j]),int(ids[ref][j])];expected_ids=[lm['per_token']['current_top1_ids'][t],lm['per_token']['reference_top1_ids'][t]]
                    tests.append(dict(index=doc,position=t,relation=r['relation'],arm=cur,reference_arm=ref,fp64_head_tv=float(tv[j]),production_fp32_head_tv=lm['softmax_tv']['tv'][t],tv_abs_difference=diff,tv_within_atol=diff<=1e-5,fp64_top1_ids=actual_ids,production_top1_ids=expected_ids,top1_ids_equal=actual_ids==expected_ids,probability_mass_defect=float(max(abs(prob[cur][j].sum()-1),abs(prob[ref][j].sum()-1)))))
    result=dict(passed=all(x['tv_within_atol'] for x in tests),witness_count=len(tests),max_tv_abs_difference=max(x['tv_abs_difference'] for x in tests),all_top1_ids_equal=all(x['top1_ids_equal'] for x in tests),max_probability_mass_defect=max(x['probability_mass_defect'] for x in tests),wall_seconds=time.monotonic()-started,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),plan=plan,witnesses=tests,scope='Fixed63 position/pair witnesses with independent higher precision head, not all positions/bitwise proof.')
    (a.output/'head_witness.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['witnesses','plan']}))

if __name__=='__main__':main()
