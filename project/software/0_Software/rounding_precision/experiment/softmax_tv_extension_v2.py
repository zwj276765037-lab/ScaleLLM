"""R006 actual temperature-one total variation over the entire vocabulary.

The decoder and frozen R005 logit measurement are unchanged. A second head
pass uses the same FP32 GEMM geometry and its already measured FP64 logsumexp.
Probability arithmetic/reductions use FP64; no artificial epsilon clipping.
"""
from __future__ import annotations
import math
import logit_numerical_extension as frozen
from logit_numerical_extension import load_output_head,qualify_chunks,fp32_head_context

NORMALIZATION_ATOL=1e-10

def probability_mass_tv(chunks,lse_current,lse_reference,tokens,vocabulary):
    """One contiguous, complete vocabulary traversal; CPU/GPU torch tensors."""
    import torch
    lsea=torch.as_tensor(lse_current,dtype=torch.float64)
    lseb=torch.as_tensor(lse_reference,dtype=torch.float64,device=lsea.device)
    if tuple(lsea.shape)!=(tokens,) or tuple(lseb.shape)!=(tokens,):raise ValueError('normalizer geometry')
    mass_a=torch.zeros_like(lsea);mass_b=torch.zeros_like(lsea);distance=torch.zeros_like(lsea)
    cursor=0;coverage=[];zero_a=0;zero_b=0
    for start,stop,current,reference in chunks:
        if start!=cursor or not start<stop<=vocabulary:raise ValueError('vocabulary gap/overlap')
        if tuple(current.shape)!=(tokens,stop-start) or current.shape!=reference.shape:raise ValueError('score geometry')
        a=current.to(device=lsea.device,dtype=torch.float64);b=reference.to(device=lsea.device,dtype=torch.float64)
        if not bool(torch.isfinite(a).all() and torch.isfinite(b).all()):raise ValueError('nonfinite score')
        pa=torch.exp(a-lsea[:,None]);pb=torch.exp(b-lseb[:,None])
        zero_a+=int((pa==0).sum());zero_b+=int((pb==0).sum())
        mass_a+=pa.sum(1);mass_b+=pb.sum(1);distance+=(pa-pb).abs().sum(1)
        cursor=stop;coverage.append([start,stop])
    if cursor!=vocabulary:raise ValueError('missing vocabulary suffix')
    tv=distance*.5
    if not bool(torch.isfinite(tv).all() and torch.isfinite(mass_a).all() and torch.isfinite(mass_b).all()):raise ValueError('nonfinite probability statistic')
    if not bool(((mass_a-1).abs()<=NORMALIZATION_ATOL).all() and ((mass_b-1).abs()<=NORMALIZATION_ATOL).all()):raise ValueError('probability mass not normalized')
    if not bool(((tv>=0)&(tv<=1+NORMALIZATION_ATOL)).all()):raise ValueError('TV outside probability range')
    def values(x):return x.detach().cpu().tolist()
    return dict(schema='m005_r006_softmax_tv_v2',temperature=1.,tokens=tokens,vocab_size=vocabulary,
        probability_pairs=tokens*vocabulary,vocab_chunks=coverage,complete=True,nonfinite=0,missing_positions=0,
        natural_exp_underflow_entries_current=zero_a,natural_exp_underflow_entries_reference=zero_b,
        tv=values(tv),probability_mass_current=values(mass_a),probability_mass_reference=values(mass_b),
        document_mean=float(tv.mean()),document_max=float(tv.max()),
        max_normalization_error_current=float((mass_a-1).abs().max()),
        max_normalization_error_reference=float((mass_b-1).abs().max()),
        normalization_check_atol=NORMALIZATION_ATOL,
        arithmetic='FP64 exp(logit - frozen FP64 logsumexp), FP64 sums; same FP32 head chunk geometry',
        definition='0.5 * sum over full vocabulary abs(softmax(current)-softmax(reference)); no vocabulary averaging or epsilon clipping',
        units='probability mass fraction; multiply by100 for percent, distinct from relative L2 percent')

def measure_logits(current_final,reference_final,head,doc):
    import torch
    row=frozen.measure_logits(current_final,reference_final,head,doc)
    current=frozen._hidden(current_final,head);reference=frozen._hidden(reference_final,head)
    T=current.shape[0];V=head.weight.shape[0];device=current.device
    raw=None
    if doc.get('_logit_audit_dir'):
        import numpy as np
        from pathlib import Path
        raw=np.load(Path(doc['_logit_audit_dir'])/'logit_raw_audit.npz',allow_pickle=False)
    def chunks():
        for start in range(0,V,head.chunk_size):
            stop=min(start+head.chunk_size,V);weight=head.weight[start:stop]
            a=current@weight.T;b=reference@weight.T
            if raw is not None:
                positions=raw['token_positions'].tolist()
                if a[positions].cpu().numpy().tobytes()!=raw['logits_current'][:,start:stop].tobytes() or b[positions].cpu().numpy().tobytes()!=raw['logits_reference'][:,start:stop].tobytes():raise ValueError('second TV head pass differs from witnessed first-pass logits')
            yield start,stop,a,b
    with fp32_head_context(device):
        row['softmax_tv']=probability_mass_tv(chunks(),
            torch.tensor(row['per_token']['logsumexp_current'],device=device,dtype=torch.float64),
            torch.tensor(row['per_token']['logsumexp_reference'],device=device,dtype=torch.float64),T,V)
    row['softmax_tv']['second_pass_raw_equal']=True if raw is not None else None
    row['softmax_tv']['second_pass_witness_positions']=raw['token_positions'].tolist() if raw is not None else []
    if raw is not None:raw.close()
    return row
