"""R005 full-vocabulary measurement using one shared, unquantized FP32 head.

This module never modifies the decoder. Source BF16 head values are represented
exactly in FP32; GEMM remains rounded host arithmetic and is audited separately.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from run_numerical_fidelity import identity, write_json

THRESHOLDS = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1., 2., 5.)

@dataclass
class OutputHead:
    weight: object
    source: dict
    evidence_dir: Path
    chunk_size: int = 4096

@contextmanager
def fp32_head_context(device):
    import torch
    old_tf32 = torch.backends.cuda.matmul.allow_tf32
    old_precision = torch.get_float32_matmul_precision()
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cuda.matmul.allow_tf32 = False
        with torch.autocast(device_type=device.type, enabled=False), torch.inference_mode():
            yield
    finally:
        torch.set_float32_matmul_precision(old_precision)
        torch.backends.cuda.matmul.allow_tf32 = old_tf32


def load_output_head(model_dir, device, evidence_dir):
    import torch
    from safetensors import safe_open
    model_dir=Path(model_dir).resolve(); evidence_dir=Path(evidence_dir)
    config=json.loads((model_dir/'config.json').read_text())
    index=json.loads((model_dir/'model.safetensors.index.json').read_text())
    if config.get('tie_word_embeddings') or 'lm_head.bias' in index['weight_map']:
        raise ValueError('R005 requires the explicitly untied, bias-free checkpoint head')
    key='lm_head.weight'; shard=(model_dir/index['weight_map'][key]).resolve()
    shard.relative_to(model_dir)
    with safe_open(str(shard),framework='pt',device='cpu') as reader:
        raw=reader.get_tensor(key)
        if raw.dtype!=torch.bfloat16 or tuple(raw.shape)!=(config['vocab_size'],config['hidden_size']):
            raise ValueError('head source shape/dtype differs')
        sha=hashlib.sha256(memoryview(raw.view(torch.uint8).numpy()).cast('B')).hexdigest()
        weight=raw.to(device=device,dtype=torch.float32,non_blocking=False).contiguous()
        # One source mapping at a time; no full-model or full-logit host copy.
        del raw
    if not bool(torch.isfinite(weight).all()):raise ValueError('nonfinite head')
    source=dict(checkpoint_key=key,checkpoint_shard=str(shard),checkpoint_shard_bytes=shard.stat().st_size,
                checkpoint_index=identity(model_dir/'model.safetensors.index.json'),config=identity(model_dir/'config.json'),
                consumed_tensor_sha256=sha,source_dtype='torch.bfloat16',computation_dtype='torch.float32',
                shape=list(weight.shape),bias=False,tied=False,chunk_size=4096,tf32=False,
                limitation='Shared FP32 GEMM roundoff is separately audited, not exact-rational head arithmetic.')
    evidence_dir.mkdir(parents=True,exist_ok=True)
    write_json(evidence_dir/'output_head_identity.json',source)
    return OutputHead(weight,source,evidence_dir)


def _hidden(value,head):
    import torch
    x=torch.as_tensor(value,device=head.weight.device)
    if x.ndim==3 and x.shape[0]==1:x=x[0]
    if x.ndim!=2 or x.shape[1]!=head.weight.shape[1] or x.dtype!=torch.float32:
        raise ValueError('head expects paired T,D float32 final-normalized hidden')
    if not bool(torch.isfinite(x).all()):raise ValueError('nonfinite head input')
    return x.contiguous()


def _new_state(tokens,device):
    import torch
    return dict(best=torch.full((tokens,),-float('inf'),device=device,dtype=torch.float64),
                second=torch.full((tokens,),-float('inf'),device=device,dtype=torch.float64),
                ids=torch.full((tokens,),-1,device=device,dtype=torch.int64),
                ties=torch.zeros(tokens,device=device,dtype=torch.int64),
                lse=torch.full((tokens,),-float('inf'),device=device,dtype=torch.float64))


def _update(state,score,offset):
    import torch
    values=score.to(torch.float64)
    top=torch.topk(values,k=min(2,values.shape[1]),dim=1).values
    block_best=top[:,0]
    # argmax returns first (smallest ID), unlike topk's unspecified tie order.
    block_id=values.argmax(dim=1)+offset
    block_ties=(values==block_best[:,None]).sum(dim=1)
    better=block_best>state['best']; equal=block_best==state['best']
    state['ids']=torch.where(better,block_id,state['ids'])
    state['ties']=torch.where(better,block_ties,torch.where(equal,state['ties']+block_ties,state['ties']))
    candidates=torch.cat((state['best'][:,None],state['second'][:,None],top),dim=1)
    merged=torch.topk(candidates,k=2,dim=1).values
    state['best']=merged[:,0];state['second']=merged[:,1]
    state['lse']=torch.logaddexp(state['lse'],torch.logsumexp(values,dim=1))


def _array_sha(value):
    value=np.ascontiguousarray(value)
    return dict(shape=list(value.shape),dtype=str(value.dtype),sha256=hashlib.sha256(value.tobytes()).hexdigest())


def measure_logits(current_final,reference_final,head,doc):
    import torch
    current=_hidden(current_final,head);reference=_hidden(reference_final,head)
    if current.shape!=reference.shape:raise ValueError('paired head shapes differ')
    T,D=current.shape;V=head.weight.shape[0];device=current.device
    states=[_new_state(T,device),_new_state(T,device)]
    delta_max=torch.full((T,),-float('inf'),device=device,dtype=torch.float64)
    delta_min=torch.full((T,),float('inf'),device=device,dtype=torch.float64)
    maxabs=torch.zeros(T,device=device,dtype=torch.float64)
    maxids=torch.zeros(T,device=device,dtype=torch.int64)
    sums=torch.zeros(T,device=device,dtype=torch.float64);sum2=sums.clone();signal2=sums.clone()
    counts=torch.zeros(len(THRESHOLDS),device=device,dtype=torch.int64)
    raw_dir=doc.get('_logit_audit_dir')
    positions=sorted(set([0,T//2,T-1])) if raw_dir else []
    raw_current=[];raw_reference=[];chunks=[]
    with fp32_head_context(device):
        for start in range(0,V,head.chunk_size):
            stop=min(start+head.chunk_size,V); w=head.weight[start:stop]
            a=current@w.T; b=reference@w.T
            if not bool(torch.isfinite(a).all() and torch.isfinite(b).all()):
                raise ValueError(f'nonfinite logits: vocab [{start},{stop})')
            _update(states[0],a,start);_update(states[1],b,start)
            delta=a.to(torch.float64)-b.to(torch.float64); absolute=delta.abs()
            block_max,block_id=absolute.max(dim=1);better=block_max>maxabs
            maxids=torch.where(better,block_id+start,maxids);maxabs=torch.maximum(maxabs,block_max)
            delta_max=torch.maximum(delta_max,delta.max(dim=1).values)
            delta_min=torch.minimum(delta_min,delta.min(dim=1).values)
            sums+=delta.sum(dim=1);sum2+=(delta*delta).sum(dim=1)
            signal2+=(b.to(torch.float64)**2).sum(dim=1)
            for i,epsilon in enumerate(THRESHOLDS):counts[i]+=(absolute<=epsilon).sum()
            if raw_dir:
                raw_current.append(a[positions].cpu().numpy().copy())
                raw_reference.append(b[positions].cpu().numpy().copy())
            chunks.append([start,stop])
        lse_delta=states[0]['lse']-states[1]['lse']
        logprob_max=torch.maximum((delta_max-lse_delta).abs(),(delta_min-lse_delta).abs())
        margin=states[1]['best']-states[1]['second']
        matches=states[0]['ids']==states[1]['ids'];certificate=margin>2*maxabs
    def vals(x):return x.detach().cpu().tolist()
    arrays={key:vals(value) for key,value in dict(max_abs_logit_delta=maxabs,max_abs_vocab_ids=maxids,
        delta_min=delta_min,delta_max=delta_max,mean_signed_delta=sums/V,
        logit_rmse=torch.sqrt(sum2/V),max_abs_logprob_delta=logprob_max,logsumexp_delta=lse_delta,
        logsumexp_current=states[0]['lse'],logsumexp_reference=states[1]['lse'],
        current_top1_ids=states[0]['ids'],reference_top1_ids=states[1]['ids'],
        current_top1_tie_counts=states[0]['ties'],reference_top1_tie_counts=states[1]['ties'],
        reference_top1_margin=margin,top1_matches=matches,margin_certified=certificate).items()}
    count=int(matches.sum()); max_token=int(maxabs.argmax())
    error_energy=float(sum2.sum());signal_energy=float(signal2.sum())
    ratio=100*math.sqrt(error_energy/signal_energy) if signal_energy>0 else None
    ratio_state='defined' if signal_energy>0 else ('exact_zero_match' if error_energy==0 else 'zero_signal_nonzero_error')
    row=dict(schema='m005_r005_full_vocab_v1',doc_id=doc['doc_id'],domain=doc.get('domain'),
        tokens=T,vocab_size=V,hidden_size=D,score_pairs=T*V,nonfinite=0,missing_positions=0,
        prediction_positions='all real prefix positions, including last-token next-word distribution; no labels',
        chunk_size=head.chunk_size,vocab_chunks=chunks,head_sha256=head.source['consumed_tensor_sha256'],
        max_abs_logit_delta=float(maxabs.max()),max_abs_token_position=max_token,
        max_abs_vocab_id=int(maxids[max_token]),max_abs_logprob_delta=float(logprob_max.max()),
        logit_rmse=float(torch.sqrt(sum2.sum()/(T*V))),error_energy=error_energy,reference_signal_energy=signal_energy,
        relative_l2_percent=ratio,relative_l2_state=ratio_state,top1_match_count=count,
        top1_total_count=T,top1_agreement=count/T,all_positions_top1_match=count==T,
        current_tied_positions=int((states[0]['ties']>1).sum()),reference_tied_positions=int((states[1]['ties']>1).sum()),
        margin_certified_count=int(certificate.sum()),tie_break='smallest vocabulary ID',
        score_thresholds=list(THRESHOLDS),score_within_threshold_counts=vals(counts),per_token=arrays,
        raw_audit=None,
        final_hidden_identity={'current':_array_sha(current.cpu().numpy()),'reference':_array_sha(reference.cpu().numpy())})
    if raw_dir:
        directory=Path(raw_dir);directory.mkdir(parents=True,exist_ok=True)
        ids=set([0,min(2048,V-1),min(4096,V-1),min(65536,V-1),V-1])
        for t in positions:
            ids.update([arrays['current_top1_ids'][t],arrays['reference_top1_ids'][t],arrays['max_abs_vocab_ids'][t]])
        ids=sorted(ids)
        payload=dict(token_positions=np.asarray(positions,dtype=np.int64),
            hidden_current=current[positions].cpu().numpy().copy(),hidden_reference=reference[positions].cpu().numpy().copy(),
            vocab_ids=np.asarray(ids,dtype=np.int64),head_rows=head.weight[ids].cpu().numpy().copy(),
            logits_current=np.concatenate(raw_current,axis=1),logits_reference=np.concatenate(raw_reference,axis=1))
        raw=directory/'logit_raw_audit.npz'
        with raw.open('xb') as out:np.savez_compressed(out,**payload)
        manifest=dict(schema='m005_r005_logit_raw_audit_v1',doc_id=doc['doc_id'],tokens=T,vocab_size=V,hidden_size=D,
            raw=identity(raw),head=head.source,arrays={k:_array_sha(v) for k,v in payload.items()},
            token_selection='predeclared unique [0,T//2,T-1]',
            vocab_selection='fixed [0,2048,4096,65536,V-1] union observed current/ref top1 and largest-delta IDs at audit tokens; diagnostic, not random',
            input_identity={k:doc.get(k) for k in ['text_sha256','duplicate_cluster','token_artifact']})
        write_json(directory/'logit_raw_audit_manifest.json',manifest)
        row['raw_audit']=identity(directory/'logit_raw_audit_manifest.json')
    return row


def qualify_chunks(current_final,reference_final,head,output_path,alternate=2048):
    """Pilot only: compare every FP32 score under two vocabulary block sizes."""
    import torch
    inputs=[_hidden(current_final,head),_hidden(reference_final,head)]
    V=head.weight.shape[0];T=inputs[0].shape[0];device=inputs[0].device
    primary=[[],[]];secondary=[[],[]]
    with fp32_head_context(device):
        for arm,x in enumerate(inputs):
            for step,buffer in [(head.chunk_size,primary[arm]),(alternate,secondary[arm])]:
                for start in range(0,V,step):
                    buffer.append((x@head.weight[start:min(start+step,V)].T).cpu())
    p=[torch.cat(x,dim=1).to(torch.float64) for x in primary]
    del primary
    s=[torch.cat(x,dim=1).to(torch.float64) for x in secondary]
    del secondary
    rows=[]
    for name,a,b in zip(['current','reference'],p,s):
        diff=a-b
        rows.append(dict(arm=name,max_abs_score_difference=float(diff.abs().max()),
            rms_score_difference=float(torch.sqrt((diff*diff).mean())),
            top1_changed_positions=int((a.argmax(1)!=b.argmax(1)).sum()),
            tie_count_changed_positions=int(((a==a.max(1).values[:,None]).sum(1)!=(b==b.max(1).values[:,None]).sum(1)).sum())))
    diff=(p[0]-p[1])-(s[0]-s[1])
    result=dict(schema='m005_r005_head_chunk_qualification_v1',primary_chunk=head.chunk_size,alternate_chunk=alternate,
        tokens=T,vocab_size=V,all_scores_compared=True,arms=rows,
        paired_delta_difference_max=float(diff.abs().max()),paired_delta_difference_rms=float(torch.sqrt((diff*diff).mean())),
        limitation='Qualification of this finite pilot geometry only; nonzero roundoff is reported, not relabeled as intermediate-rounding loss.')
    write_json(Path(output_path),result)
    return result
