#!/usr/bin/env python3
"""Train-only native generate parity and rebuilt-cache controls."""
import argparse
import copy
import fcntl
import os
from pathlib import Path
import torch
from gsm8k_protocol import atomic_json, prepare_requests, sha256_file
from run_gsm8k_worker import encode_prompt, resolve_generation, now
from run_eval_worker import configure_reproducibility, load_model
from diagnose_gsm8k_cache import statistics


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--output', type=Path, required=True)
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
    result = dict(started_at=now(), case=args.case, model=str(args.model), gpu=gpu,
                  plan_sha256=sha256_file(args.plan), source_sha256=sha256_file(Path(__file__)), records=[])
    config, _ = resolve_generation(model, tokenizer, 17)
    config.output_logits = True
    for request in prepare_requests(args.plan, 'smoke')[:2]:
        inputs = torch.tensor([encode_prompt(tokenizer, request['prompt'])], device=args.device)
        prefix = inputs
        past = None
        with torch.inference_mode():
            native = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs), generation_config=config)
            tokens = native.sequences[:, inputs.shape[1]:]
            row = dict(sample_id=request['sample_id'], prompt_sha256=request['prompt_sha256'], steps=[])
            for step in range(len(native.logits)):
                if step == len(native.logits)-1:
                    corrupted = copy.deepcopy(past)
                    for layer in corrupted.layers:
                        layer.keys.zero_(); layer.values.zero_()
                    bad = model(input_ids=prefix[:, -1:], attention_mask=torch.ones_like(prefix),
                                past_key_values=corrupted, use_cache=True, logits_to_keep=1).logits[:, -1]
                cached = model(input_ids=prefix if past is None else prefix[:, -1:],
                               attention_mask=torch.ones_like(prefix), past_key_values=past,
                               use_cache=True, logits_to_keep=1)
                record = dict(step=step, native_generate=statistics(cached.logits[:, -1], native.logits[step]))
                if step == len(native.logits)-1:
                    rebuilt = None
                    for j in range(step+1):
                        segment = inputs if j == 0 else tokens[:, j-1:j]
                        out = model(input_ids=segment, attention_mask=torch.ones((1, inputs.shape[1]+j),dtype=torch.long,device=args.device),
                                    past_key_values=rebuilt, use_cache=True, logits_to_keep=1)
                        rebuilt = out.past_key_values
                    record['rebuilt_cache'] = statistics(cached.logits[:, -1],out.logits[:, -1])
                    record['corrupted_cache'] = statistics(cached.logits[:, -1],bad)
                row['steps'].append(record)
                past = cached.past_key_values
                prefix = torch.cat((prefix,tokens[:, step:step+1]), dim=1)
            result['records'].append(row)
            atomic_json(args.output/'diagnosis.json', result)
    result['finished_at'] = now()
    atomic_json(args.output/'diagnosis.json', result)


if __name__ == '__main__':
    main()
