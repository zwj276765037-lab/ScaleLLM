#!/usr/bin/env python3
"""Controlled train-only cache comparison; never changes production settings."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import torch
from gsm8k_protocol import atomic_json, prepare_requests, sha256_file
from run_gsm8k_worker import encode_prompt, resolve_generation, now
from run_eval_worker import configure_reproducibility, load_model


def statistics(a, b):
    a, b = a.float(), b.float()
    diff = (a - b).abs()
    tolerance = .125 + .01 * b.abs()
    values, indices = a.topk(2)
    return dict(max_abs=diff.max().item(), rmse=(diff.square().mean().sqrt().item()),
                violation_count=(diff > tolerance).sum().item(),
                max_normalized_violation=(diff / tolerance).max().item(),
                allclose=torch.allclose(a, b, atol=.125, rtol=.01),
                top1_equal=a.argmax().item() == b.argmax().item(),
                left_top2=indices.tolist(), left_margin=(values[0,0]-values[0,1]).item(),
                finite=bool(torch.isfinite(a).all() and torch.isfinite(b).all()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    args = p.parse_args()
    args.device = 'cuda:0'
    args.output.mkdir(parents=True, exist_ok=False)
    gpu = os.environ['CUDA_VISIBLE_DEVICES']
    lock_path = Path(__file__).resolve().parent.parent/'results/gsm8k_full_completion/resource_locks'/f'{gpu}.lock'
    lock = lock_path.open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    configure_reproducibility(20260913)
    model, tokenizer, method, _ = load_model(args)
    model.config.use_cache = True
    references = json.loads(args.reference.read_text())['records']
    requests = prepare_requests(args.plan, 'smoke')[:2]
    result = dict(started_at=now(), case=args.case, model=str(args.model), gpu=gpu,
                  plan_sha256=sha256_file(args.plan), reference_sha256=sha256_file(args.reference),
                  source_sha256=sha256_file(Path(__file__)), records=[])
    config, _ = resolve_generation(model, tokenizer, 17)
    for reduced in (True, False):
        torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = reduced
        for keep in (0, 1):
            for request, reference in zip(requests, references):
                assert reference['prompt_sha256'] == request['prompt_sha256']
                prefix = torch.tensor([encode_prompt(tokenizer, request['prompt'])], device=args.device)
                past = None
                with torch.inference_mode():
                    for step in range(17):
                        cached = model(input_ids=prefix if past is None else prefix[:, -1:],
                                       attention_mask=torch.ones_like(prefix), past_key_values=past,
                                       use_cache=True, logits_to_keep=keep, output_hidden_states=True)
                        if step in (0,16):
                            plain = model(input_ids=prefix, attention_mask=torch.ones_like(prefix),
                                          use_cache=False, logits_to_keep=keep, output_hidden_states=True)
                            a, b = cached.logits[:, -1], plain.logits[:, -1]
                            ha, hb = cached.hidden_states[-1][:, -1], plain.hidden_states[-1][:, -1]
                            row = dict(sample_id=request['sample_id'], step=step, logits_to_keep=keep,
                                       reduced_precision=reduced, logits=statistics(a,b),
                                       same_shape_lm_head=statistics(model.lm_head(ha), model.lm_head(hb)),
                                       hidden_max_abs=(ha.float()-hb.float()).abs().max().item())
                            result['records'].append(row)
                            atomic_json(args.output/'diagnosis.json',result)
                        past = cached.past_key_values
                        if step < 16:
                            prefix = torch.cat((prefix,torch.tensor([[reference['cache_on_32_token_ids'][step]]],device=args.device)),dim=1)
    torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = True
    result['finished_at'] = now()
    atomic_json(args.output/'diagnosis.json', result)


if __name__ == '__main__':
    main()
