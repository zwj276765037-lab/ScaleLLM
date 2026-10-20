#!/usr/bin/env python3
"""R012 true CURRENT/OUTPUT_ONLY free-generation runner; Root admits GPU use.

No remote model, BF16 decoder control, hidden teacher-forcing, or shared answer
prefix is used. Both arms retain the same quantized weights and host FP32 head.
"""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
sys.path.insert(0, str(EXPERIMENT))
from generation_core import decode_arm, generation_budget, pair_summary, read_prompts, token_identity


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write_new(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def event(directory, stage, **fields):
    with (directory/'stages.jsonl').open('a', encoding='utf8') as stream:
        stream.write(json.dumps(dict(at=now(), stage=stage, **fields), ensure_ascii=False, allow_nan=False)+'\n')


def code_identities():
    from run_paired_numerical_model import code_identities as numerical_code
    paths = [HERE/'generation_core.py', HERE/'cached_adapter.py', HERE/'run_generation.py',
             EXPERIMENT/'logit_numerical_extension.py', HERE/'supervise.py']
    return numerical_code() + [identity(p) for p in paths]


def prompt_tokens(tokenizer, history):
    rendered = tokenizer.apply_chat_template(history, tokenize=False, add_generation_prompt=True)
    ids = tokenizer(rendered, add_special_tokens=False)['input_ids']
    return rendered, [int(x) for x in ids]


def stopping_ids(tokenizer, model_dir):
    config = json.loads((model_dir/'generation_config.json').read_text()) if (model_dir/'generation_config.json').exists() else {}
    ids = config.get('eos_token_id', tokenizer.eos_token_id)
    ids = [] if ids is None else ids if isinstance(ids, list) else [ids]
    for token in ('<|eot_id|>', '<|end_of_text|>'):
        value = tokenizer.get_vocab().get(token)
        if value is not None:
            ids.append(value)
    if not ids:
        raise ValueError('No EOS/eot token could be identified')
    return sorted(set(int(x) for x in ids))


def preflight(args, directory):
    from transformers import AutoTokenizer
    config = json.loads((args.model_dir/'config.json').read_text())
    expected = dict(num_hidden_layers=32, hidden_size=4096, num_attention_heads=32,
                    num_key_value_heads=8, intermediate_size=14336)
    if any(config.get(k) != v for k,v in expected.items()):
        raise ValueError('Requires the previously qualified Llama-3.1-8B geometry')
    rows = read_prompts(args.prompts)
    if args.limit:
        rows = rows[:args.limit]
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_dir), local_files_only=True, trust_remote_code=False)
    if not tokenizer.chat_template:
        raise ValueError('Checkpoint lacks a native chat template')
    stops = stopping_ids(tokenizer, args.model_dir)
    lengths = []
    for row in rows:
        turns = row.get('turns', [row['prompt']])
        if not turns or any(not isinstance(t,str) or not t.strip() for t in turns):
            raise ValueError('turns must be nonempty strings')
        rendered, ids = prompt_tokens(tokenizer, [dict(role='user',content=turns[0])])
        generation_budget(len(ids), args.max_context, args.max_new_tokens)
        lengths.append(dict(id=row['prompt_id'], turn0_tokens=len(ids), turns=len(turns),
                            token_identity=token_identity(ids), prompt_token_ids=ids, rendered=rendered))
    record = dict(schema='r012_generation_preflight_v1', created_at=now(),
                  prompts=identity(args.prompts), selected_ids=[r['prompt_id'] for r in rows],
                  model_dir=str(args.model_dir), config=identity(args.model_dir/'config.json'),
                  checkpoint_index=identity(args.model_dir/'model.safetensors.index.json'),
                  tokenizer_files=[identity(p) for p in sorted(args.model_dir.iterdir()) if p.is_file() and
                                   (p.name.startswith('token') or p.name in ('special_tokens_map.json','generation_config.json'))],
                  stop_token_ids=stops, max_context=args.max_context, max_new_tokens=args.max_new_tokens,
                  prompt_truncation=False, decoding='greedy; torch.argmax tie breaks smallest ID',
                  item_lengths=lengths, first_turn_budget_valid=True,
                  second_turn_budget='validated at execution from each arm own actual history',
                  source=code_identities(), gpu_initialized=__import__('torch').cuda.is_initialized())
    write_new(directory/'preflight.json', record)
    return rows, tokenizer, stops, record


def forward(model, tokens, device, offset=0, native=False, capture=None):
    import torch
    encoded = torch.tensor([tokens], dtype=torch.long, device=device)
    positions = torch.arange(offset, offset+len(tokens), device=device)[None,:]
    handles = []
    if capture is not None:
        for i, layer in enumerate(model.layers):
            def hook(_m, _a, value, i=i):
                v = value[0] if isinstance(value,tuple) else value
                capture[i] = v[:,-1,:].detach().cpu().clone()
            handles.append(layer.register_forward_hook(hook))
    try:
        with torch.inference_mode():
            if native:
                value = model(input_ids=encoded, attention_mask=torch.ones_like(encoded),
                              position_ids=positions, use_cache=False, return_dict=True).last_hidden_state
            else:
                # Same HF layer/residual/RMSNorm sequence, with adapter-owned
                # absolute causal mask and no unused HF floating RoPE operation.
                value = model.embed_tokens(encoded)
                for layer in model.layers:
                    value = layer(value, position_ids=positions, attention_mask=None, use_cache=False)
                value = model.norm(value)
            return value[:,-1,:].contiguous()
    finally:
        for h in handles:
            h.remove()


def logits(hidden, head):
    import torch
    from logit_numerical_extension import fp32_head_context
    with fp32_head_context(hidden.device):
        result = hidden @ head.weight.T
    if not bool(torch.isfinite(result).all()):
        raise ValueError('Nonfinite output logits')
    return result


def cache_forward(model, cache, ids, device, chunk=128, capture=None):
    value = None
    for start in range(0,len(ids),chunk):
        offset = cache.length()
        value = forward(model, ids[start:start+chunk], device, offset,
                        capture=capture if start+chunk>=len(ids) else None)
    return value


def qualify(model, cache, v5, head, ids, args, directory):
    import torch
    from numerical_reference.gpu_reference import arithmetic_context
    from numerical_reference.policy import OUTPUT_ONLY
    from cached_adapter import array_hash
    # No repeated prompt padding in quality data. This deterministic synthetic
    # token fixture is used only to qualify tensor/cache geometry at >128 keys.
    fixture_length = min(512,args.max_context)
    fixture = (ids * (fixture_length//len(ids)+1))[:fixture_length]
    reports = []
    for arm in ('current','output_only'):
        with arithmetic_context(v5,OUTPUT_ONLY) if arm=='output_only' else nullcontext():
            for length, native in ((17,True),(130,False),(min(512,args.max_context),False)):
                selected = fixture[:length]
                cache.reset(False)
                cache.original_mode(native)
                expected_layers = {}
                a = forward(model, selected, head.weight.device, native=native, capture=expected_layers)
                scores_a = logits(a,head)
                cache.original_mode(False)
                if native:
                    cache.reset(False)
                    adapter_full = forward(model,selected,head.weight.device)
                    if not torch.equal(a,adapter_full):
                        raise ValueError('Native and extended adapter no-cache differ at <=128')
                cache.reset(True)
                # Split at the last token, forcing actual reuse of all old KV12.
                cache_forward(model,cache,selected[:-1],head.weight.device,chunk=args.prefill_chunk)
                actual_layers = {}
                b = cache_forward(model,cache,selected[-1:],head.weight.device,chunk=1,capture=actual_layers)
                scores_b = logits(b,head)
                per_layer = [dict(layer=i, equal=torch.equal(expected_layers[i],actual_layers[i]),
                                  expected_sha256=array_hash(expected_layers[i]),actual_sha256=array_hash(actual_layers[i]),
                                  max_abs=float((expected_layers[i]-actual_layers[i]).abs().max())) for i in range(32)]
                row = dict(arm=arm,tokens=length,baseline='unchanged native V5/HF forward' if native else 'extended adapter full-prefix no-cache',
                           all32_last_hidden_bitwise_equal=all(x['equal'] for x in per_layer),layers=per_layer,
                           final_norm_bitwise_equal=torch.equal(a,b),logits_bitwise_equal=torch.equal(scores_a,scores_b),
                           max_abs_logit_difference=float((scores_a-scores_b).abs().max()),
                           native_top1=int(scores_a.argmax()),cache_top1=int(scores_b.argmax()),
                           cache=cache.cache_identity())
                reports.append(row)
                event(directory,'cache_qualification_case',arm=arm,tokens=length,passed=row['all32_last_hidden_bitwise_equal'] and row['logits_bitwise_equal'])
                if not (row['all32_last_hidden_bitwise_equal'] and row['final_norm_bitwise_equal'] and row['logits_bitwise_equal']):
                    write_new(directory/'qualification_failed.json',dict(cases=reports))
                    raise ValueError('Cache qualification changed hidden/logits; stop before quality generation')
    cache.reset(True)
    result = dict(schema='r012_cache_qualification_v1',passed=True,cases=reports,rope=cache.rope_identity,
                  coverage='both arms, 32 layers, last hidden/final norm/all vocab logits; native17/adapter17 and extended130/512; finite qualification only')
    write_new(directory/'qualification.json',result)
    return result


def generate(args, rows, tokenizer, stops, preflight_record, directory):
    import torch
    import torch.nn as nn
    from capture_real_inputs import load_streamed_bf16_model
    from numerical_reference.model_compat import attach_v5_fullchain_compatible, production_module
    from numerical_reference.chunked_quantization import chunked_weight_context
    from numerical_reference.gpu_reference import arithmetic_context
    from numerical_reference.policy import OUTPUT_ONLY
    from run_paired_numerical_model import validate_attach, reset_audit, audit_report, buffer_signature
    from logit_numerical_extension import load_output_head
    from cached_adapter import CacheManager, array_hash
    if os.environ.get('CUDA_VISIBLE_DEVICES') != args.expected_gpu_uuid:
        raise ValueError('Only Root-selected exact GPU UUID may be visible')
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    device = torch.device('cuda:0')
    torch.cuda.set_device(device)
    props = torch.cuda.get_device_properties(device)
    write_new(directory/'actual_runtime.json',dict(pid=os.getpid(),started_at=now(),command=sys.argv,
              cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),gpu_name=props.name,
              gpu_total_bytes=props.total_memory,cpu_threads=torch.get_num_threads(),
              versions={p:importlib.metadata.version(p) for p in ('torch','transformers','accelerate','triton','numpy','safetensors')}))
    event(directory,'loading_model')
    started = time.monotonic()
    base = load_streamed_bf16_model(args.model_dir,'cuda:0',directory)
    class Facade(nn.Module):
        def __init__(self,base):
            super().__init__(); self.model=base; self.lm_head=nn.Identity(); self.config=base.config
    facade=Facade(base);v5=production_module()
    with chunked_weight_context(v5,128):
        metadata,audit=attach_v5_fullchain_compatible(facade,checkpoint_dir=args.model_dir,device=device,
            strict_total_shift=True,software_extended=False,trace_layers=None,down_output_width=32,down_shift12_candidate=True)
    validate_attach(metadata)
    write_new(directory/'v5_attach_metadata.json',metadata)
    facade.eval();torch.cuda.empty_cache()
    event(directory,'v5_attached',seconds=time.monotonic()-started,allocated_bytes=torch.cuda.memory_allocated())
    head=load_output_head(args.model_dir,device,directory)
    # Full byte hashes of quantized weight/code/shift/LUT buffers. Cache storage
    # is not a model buffer, and every arm uses these same immutable allocations.
    quantized=[dict(name=n,shape=list(b.shape),dtype=str(b.dtype),sha256=array_hash(b))
               for n,b in facade.named_buffers()]
    write_new(directory/'quantized_buffers.json',dict(buffers=quantized,
               sha256=hashlib.sha256(json.dumps(quantized,sort_keys=True).encode()).hexdigest()))
    cache=CacheManager(base,v5,json.loads((args.model_dir/'config.json').read_text()),args.max_context,device)
    signature=buffer_signature(facade)
    write_new(directory/'rope_extension.json',cache.rope_identity)
    _,fixture=prompt_tokens(tokenizer,[dict(role='user',content=rows[0]['prompt'])])
    qualify(base,cache,v5,head,fixture,args,directory)
    if args.qualification_only:
        return dict(execution_state='completed',qualification_only=True,quality_pairs=0)
    source_hash=hashlib.sha256(json.dumps(preflight_record['source'],sort_keys=True).encode()).hexdigest()
    pair_count=0
    for row in rows:
        histories={arm:[] for arm in ('current','output_only')}
        for turn_index,user in enumerate(row.get('turns',[row['prompt']])):
            answers={}
            for arm in ('current','output_only'):
                histories[arm].append(dict(role='user',content=user))
                rendered,ids=prompt_tokens(tokenizer,histories[arm])
                generation_budget(len(ids),args.max_context,args.max_new_tokens)
                cache.reset(True);reset_audit(audit)
                begin=time.monotonic();prefill_seconds=None
                def step(prefix, first):
                    nonlocal prefill_seconds
                    tick=time.monotonic()
                    if first:
                        h=cache_forward(base,cache,prefix,device,args.prefill_chunk)
                        torch.cuda.synchronize();prefill_seconds=time.monotonic()-tick
                    else:
                        if cache.length()!=len(prefix)-1:
                            raise ValueError('Cache does not belong to this independent prefix')
                        h=cache_forward(base,cache,prefix[-1:],device,1)
                    score=logits(h,head)
                    token=int(score.argmax())
                    top=torch.topk(score[0],2).values
                    torch.cuda.synchronize()
                    return token,dict(seconds=time.monotonic()-tick,cache_tokens=cache.length(),
                                      top1_logit=float(top[0]),top1_margin=float(top[0]-top[1]))
                def token_event(index,token,diagnostic):
                    with (directory/'tokens.jsonl').open('a',encoding='utf8') as stream:
                        stream.write(json.dumps(dict(id=row['prompt_id'],turn_index=turn_index,arm=arm,
                            index=index,token_id=token,**diagnostic),allow_nan=False)+'\n')
                event(directory,'generation_started',id=row['prompt_id'],turn_index=turn_index,arm=arm,prompt_tokens=len(ids))
                with torch.inference_mode(), arithmetic_context(v5,OUTPUT_ONLY) if arm=='output_only' else torch.inference_mode():
                    answer=decode_arm(ids,step,set(stops),args.max_new_tokens,args.max_context,token_event)
                text=tokenizer.decode(answer['generated_token_ids'],skip_special_tokens=True,clean_up_tokenization_spaces=False)
                answer.update(text=text,raw_text=tokenizer.decode(answer['generated_token_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False),
                    prompt_token_ids=ids,prompt_token_identity=token_identity(ids),prompt_rendered=rendered,
                    elapsed_seconds=time.monotonic()-begin,prefill_seconds=prefill_seconds,
                    finish_reason=answer['stop_reason'],max_new_tokens=args.max_new_tokens,max_context=args.max_context,
                    stop_token_ids=stops,source_identity=source_hash,arm=arm,
                    audit=audit_report(audit,reference=arm=='output_only'))
                answers[arm]=answer
                histories[arm].append(dict(role='assistant',content=text))
                if buffer_signature(facade)!=signature:
                    raise ValueError('Shared model buffers changed')
                event(directory,'generation_completed',id=row['prompt_id'],turn_index=turn_index,arm=arm,
                      tokens=len(answer['generated_token_ids']),truncated=answer['truncated'],seconds=answer['elapsed_seconds'])
                cache.reset(True)
            if turn_index==0 and answers['current']['prompt_token_ids']!=answers['output_only']['prompt_token_ids']:
                raise ValueError('First-turn starting prompt differs between arms')
            result=dict(schema_version=1,id=row['prompt_id'],prompt_id=row['prompt_id'],
                        cluster_id=row.get('cluster_id',row['prompt_id']),dataset=row.get('dataset'),
                        source_revision=row.get('source_revision'),turn_index=turn_index,user_prompt=user,
                        prompt_sha256=hashlib.sha256(user.encode()).hexdigest(),responses=answers,
                        pair=pair_summary(answers['current'],answers['output_only']))
            with (directory/'responses.jsonl').open('a',encoding='utf8') as stream:
                stream.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n')
            pair_count+=1
    if preflight_record['source']!=code_identities():
        raise ValueError('Consumed source changed during run')
    return dict(execution_state='completed',quality_pairs=pair_count,source_unchanged=True,
                shared_buffers_unchanged=True,peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(),max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--prompts',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--max-context',type=int,default=2048)
    parser.add_argument('--max-new-tokens',type=int,default=512)
    parser.add_argument('--prefill-chunk',type=int,default=128)
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--cpu-check',action='store_true')
    parser.add_argument('--qualification-only',action='store_true')
    parser.add_argument('--expected-gpu-uuid',default='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6')
    args=parser.parse_args()
    if not 130<=args.max_context<=32768 or not 1<=args.prefill_chunk<=128 or args.limit<0:
        parser.error('context 130..32768, prefill chunk 1..128 and nonnegative limit required')
    directory=args.output_dir.resolve()
    directory.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    try:
        rows,tokenizer,stops,record=preflight(args,directory)
        result=dict(execution_state='completed',cpu_check=True,quality_pairs=0) if args.cpu_check else generate(args,rows,tokenizer,stops,record,directory)
        result.update(ended_at=now(),wall_seconds=time.monotonic()-start)
        write_new(directory/'result.json',result)
        event(directory,'completed',**result)
        return 0
    except Exception as error:
        write_new(directory/'failure.json',dict(execution_state='failed',ended_at=now(),
                  error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),wall_seconds=time.monotonic()-start))
        event(directory,'failed',error=str(error))
        raise

if __name__=='__main__':
    raise SystemExit(main())
