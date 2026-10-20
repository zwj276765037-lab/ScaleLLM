"""CPU-only independent old raw audit comparison; not new formal measurement."""
from pathlib import Path
import argparse,sys,json,time
import numpy as np
import torch
from run_numerical_fidelity import identity,write_json
from softmax_tv_extension_v2 import probability_mass_tv
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_softmax_tv_v2 import independent

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline-plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    begin=time.monotonic();plan=json.loads(a.baseline_plan.read_text());rows=[];documents=0
    for group in plan['groups']:
        for raw in sorted(Path(group['attempt_path']).glob('documents/doc*/logit_raw_audit.npz')):
            metric=json.loads(raw.with_name('logit_metrics.json').read_text());documents+=1
            with np.load(raw,allow_pickle=False) as data:
                ca=data['logits_current'];re=data['logits_reference'];positions=data['token_positions'].tolist()
                la=torch.tensor([metric['per_token']['logsumexp_current'][i] for i in positions],dtype=torch.float64)
                lb=torch.tensor([metric['per_token']['logsumexp_reference'][i] for i in positions],dtype=torch.float64)
                result=probability_mass_tv(((s,min(s+4096,ca.shape[1]),torch.from_numpy(ca[:,s:s+4096]),torch.from_numpy(re[:,s:s+4096])) for s in range(0,ca.shape[1],4096)),la,lb,len(positions),ca.shape[1])
                expected,masses=independent(ca,re);difference=np.max(np.abs(expected-np.asarray(result['tv'])))
                if difference>1e-12:raise ValueError('independent TV mismatch')
                rows.append(dict(doc_id=metric['doc_id'],positions=positions,raw=identity(raw),tv=result['tv'],independent_tv=expected.tolist(),max_abs_difference=float(difference),max_mass_defect=max(result['max_normalization_error_current'],result['max_normalization_error_reference'])))
    if documents!=15 or sum(len(r['positions']) for r in rows)!=45:raise ValueError('expected15formal auditdocs45rows')
    result=dict(schema='m005_r006_tv_cpu_qualification_v2',execution_state='completed',documents=documents,full_vocab_rows=45,vocabulary=128256,wall_seconds=time.monotonic()-begin,max_independent_abs_difference=max(r['max_abs_difference'] for r in rows),max_mass_defect=max(r['max_mass_defect'] for r in rows),rows=rows,baseline_plan=identity(a.baseline_plan),scope='Old R005 raw audit rows CPU qualification only; not full1024 TV supplementation')
    write_json(a.output,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'}))

if __name__=='__main__':main()
