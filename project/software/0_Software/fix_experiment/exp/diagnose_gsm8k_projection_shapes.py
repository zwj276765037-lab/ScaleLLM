#!/usr/bin/env python3
"""Compare one frozen activation row inside/full outside a QDQ module, no cache."""
import argparse
import fcntl
import os
from pathlib import Path
import torch
from gsm8k_protocol import atomic_json, prepare_requests, sha256_file
from run_gsm8k_worker import encode_prompt, now
from run_eval_worker import configure_reproducibility, load_model


def main():
    p = argparse.ArgumentParser()
    for arg in ('plan','model','output'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--case',required=True)
    args = p.parse_args();args.device='cuda:0'
    args.output.mkdir(parents=True,exist_ok=False)
    gpu=os.environ['CUDA_VISIBLE_DEVICES']
    lock=(Path(__file__).resolve().parent.parent/'results/gsm8k_full_completion/resource_locks'/f'{gpu}.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    configure_reproducibility(20260913)
    model,tokenizer,method,_=load_model(args)
    modules=dict(model.named_modules()); samples={}; hooks=[]
    names=['model.layers.0.self_attn.q_proj','model.layers.0.mlp.up_proj','model.layers.10.mlp.down_proj']
    for name in names:
        def capture(module, inputs, output, key=name):
            samples[key]=inputs[0].detach().clone()
        hooks.append(modules[name].register_forward_hook(capture))
    req=prepare_requests(args.plan,'smoke')[1]
    ids=torch.tensor([encode_prompt(tokenizer,req['prompt'])],device=args.device)
    with torch.inference_mode():
        model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,logits_to_keep=1)
    for hook in hooks:hook.remove()
    torch.save({n:x.cpu() for n,x in samples.items()},args.output/'frozen_activations.pt')
    result=dict(case=args.case,gpu=gpu,prompt_sha256=req['prompt_sha256'],source_sha256=sha256_file(Path(__file__)),
                activations_sha256=sha256_file(args.output/'frozen_activations.pt'),records=[],started_at=now())
    with torch.inference_mode():
        for name,x in samples.items():
            module=modules[name]; full=module(x); repeat=module(x)
            single=module(x[:,-1:,:].contiguous()); a=full[:,-1:,:].float();b=single.float()
            result['records'].append(dict(name=name,type=type(module).__name__,input_shape=list(x.shape),
                full_repeat_exact=torch.equal(full,repeat),same_last_input_row=True,
                row_shape_equal=torch.equal(a,b),max_abs=(a-b).abs().max().item(),
                different_output_count=(a!=b).sum().item(),rmse=(a-b).square().mean().sqrt().item()))
    result['finished_at']=now();atomic_json(args.output/'diagnosis.json',result)


if __name__=='__main__':main()
