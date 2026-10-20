#!/usr/bin/env python3
"""One isolated layer25 up_proj GEMM, fixed operands and output-allocation controls.

Train-only diagnosis. Does not alter production source, flags, model weights,
verification thresholds, system libraries, or the matrix scheduler.
"""
from __future__ import annotations
import argparse
import copy
import fcntl
import hashlib
import os
from pathlib import Path
import sys
import time
import traceback
from gsm8k_protocol import atomic_json, prepare_requests, sha256_file
from run_gsm8k_worker import encode_prompt, logits_comparison, now, resolve_generation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.device, args.case = 'cuda:0', 'bf16'
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'source_snapshot.py').write_bytes(Path(__file__).resolve().read_bytes())
    state = {'schema':'scalellm_isolated_up_proj_v1','state':'starting',
             'started_at':now(),'pid':os.getpid(),'command':sys.argv,
             'cpu_affinity':sorted(os.sched_getaffinity(0)),
             'gpu_uuid_requested':os.environ.get('CUDA_VISIBLE_DEVICES'),
             'source_sha256':sha256_file(Path(__file__).resolve()),
             'plan_sha256':sha256_file(args.plan),'model':str(args.model),
             'scope':'Single layer25 up_proj, train:0000 only; no formal qualification',
             'native_calls':[],'isolated_calls':[]}
    def save(): atomic_json(args.output / 'diagnosis.json', state)
    save()
    lock = None
    try:
        if set(os.sched_getaffinity(0)) != {18,19}:
            raise RuntimeError('requires exactly CPU18,19')
        gpu = os.environ.get('CUDA_VISIBLE_DEVICES')
        if gpu != 'GPU-d87ce710-76bf-872d-9739-f0d7c9b52533':
            raise RuntimeError('requires assigned GPU1 UUID only')
        available = next(int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:'))
        if available < 80*1024*1024:
            raise RuntimeError('MemAvailable below 80 GiB reserve')
        root = Path(__file__).resolve().parent.parent
        lock_path = root/'results/gsm8k_full_completion/resource_locks'/(gpu+'.lock')
        lock = lock_path.open('a+')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state.update(state='loading_model', lock=str(lock_path), lock_acquired_at=now())
        save()
        import torch
        import torch.nn.functional as F
        from run_eval_worker import configure_reproducibility, load_model, package_versions
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        configure_reproducibility(20260913)
        torch.cuda.set_device(args.device)
        free,total = torch.cuda.mem_get_info(args.device)
        if free < 24*(1<<30):
            raise RuntimeError('GPU1 free memory below 24 GiB before loading')
        state.update(gpu_uuid_actual=str(torch.cuda.get_device_properties(args.device).uuid),
                     gpu_memory_before={'free':free,'total':total},package_versions=package_versions(),
                     runtime_flags={'tf32':torch.backends.cuda.matmul.allow_tf32,
                                    'bf16_reduced_precision':torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
                                    'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
                                    'CUBLAS_WORKSPACE_CONFIG':os.environ.get('CUBLAS_WORKSPACE_CONFIG')})
        start=time.perf_counter()
        model,tokenizer,method,audit=load_model(args)
        model.config.use_cache=True
        model.eval()
        module=model.model.layers[25].mlp.up_proj
        if module.bias is not None: raise RuntimeError('unexpected non-null up_proj bias')
        request=prepare_requests(args.plan,'smoke')[0]
        if request['sample_id'] != 'train:0000':raise RuntimeError('unexpected first train sample')
        inputs=torch.tensor([encode_prompt(tokenizer,request['prompt'])],device=args.device)
        attention=torch.ones_like(inputs)
        config,generation=resolve_generation(model,tokenizer,1)
        config.output_logits=True
        state.update(state='native_operand_capture',load_seconds=time.perf_counter()-start,
                     method=method,generation=generation,sample_id=request['sample_id'],
                     prompt_sha256=request['prompt_sha256'],input_tokens=int(inputs.shape[1]),
                     module_class=type(module).__module__+'.'+type(module).__name__)
        save()
        raw={}
        def cpu(t):return t.detach().cpu().contiguous().clone()
        def digest(t):return hashlib.sha256(t.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()).hexdigest()
        def info(t):
            ptr=int(t.data_ptr()); base=int(t.untyped_storage().data_ptr())
            return {'shape':list(t.shape),'stride':list(t.stride()),'dtype':str(t.dtype),
                    'device':str(t.device),'storage_offset':t.storage_offset(),
                    'contiguous':t.is_contiguous(),'data_ptr':ptr,'storage_base_ptr':base,
                    'ptr_mod_256':ptr%256,'ptr_mod_128':ptr%128,'ptr_mod_16':ptr%16,
                    'storage_nbytes':t.untyped_storage().nbytes(),'sha256':digest(t)}
        weight_sha_before=digest(module.weight)
        state['weight_before']=info(module.weight)
        active=[None]
        fixed=[None]
        def pre(_module,items):
            row=active[0]
            if row is None:return
            if len(items)!=1:raise RuntimeError('unexpected up_proj arguments')
            x=items[0]
            if x.shape[1]!=inputs.shape[1]:raise RuntimeError('unexpected decode invocation')
            row['input']=info(x)
            row['weight']=info(module.weight)
            raw[row['key']+'_input']=cpu(x)
            if fixed[0] is None:
                # Exact original GPU layout preserved (contiguous in this model).
                fixed[0]=x.detach().clone(memory_format=torch.preserve_format)
        def post(_module,items,out):
            row=active[0]
            if row is None:return
            row['output']=info(out)
            raw[row['key']+'_output']=cpu(out)
        h1=module.register_forward_pre_hook(pre)
        h2=module.register_forward_hook(post)
        with torch.inference_mode():
            for index in range(4):
                row={'key':f'native_{index}','index':index}
                active[0]=row
                configure_reproducibility(20260913)
                generated=model.generate(input_ids=inputs.clone(),attention_mask=attention.clone(),generation_config=copy.deepcopy(config))
                row['generated_ids']=generated.sequences[0,inputs.shape[1]:].detach().cpu().tolist()
                raw[row['key']+'_logits']=cpu(generated.logits[0])
                row['logits_sha256']=digest(generated.logits[0])
                state['native_calls'].append(row)
                active[0]=None
                del generated
                save()
            h1.remove();h2.remove()
            x=fixed[0]
            w=module.weight.detach()
            x2=x.reshape(-1,x.shape[-1])
            wt=w.t()
            state.update(state='isolated_gemm',fixed_input=info(x),flat_input=info(x2),
                         transposed_weight=info(wt),operand_control='same GPU objects and bytes for every isolated call')
            raw['fixed_input']=cpu(x)
            raw['fixed_weight']=cpu(w)
            save()
            def record(name,index,out,before=None):
                key=f'{name}_{index}'
                row={'key':key,'series':name,'index':index,'input_sha256':digest(x),
                     'weight_sha256':digest(w),'output':info(out)}
                if before is not None:row['buffer_before']=before
                raw[key]=cpu(out)
                state['isolated_calls'].append(row)
                save()
            for index in range(6):
                out=F.linear(x,w,None)
                record('functional_linear',index,out)
                del out
            reuse=torch.empty((x2.shape[0],w.shape[0]),dtype=x.dtype,device=x.device)
            for index,fill in enumerate([0.,1.,float('nan'),-1.,0.,1.]):
                reuse.fill_(fill)
                before={'fill':str(fill),'descriptor':info(reuse)}
                torch.mm(x2,wt,out=reuse)
                record('mm_reused_output',index,reuse,before)
            fresh=[]
            for index in range(6):
                out=torch.empty_like(reuse)
                # Keep outputs alive so this series has distinct fresh allocations.
                before={'allocation':'new torch.empty_like, retained through series',
                        'descriptor':info(out)}
                torch.mm(x2,wt,out=out)
                record('mm_fresh_output',index,out,before)
                fresh.append(out)
            state['fixed_input_after']=info(x)
            state['weight_after']=info(w)
        state.update(state='comparing',weight_bytes_unchanged=weight_sha_before==digest(module.weight))
        save()
        def comparison(a,b):return logits_comparison(a.reshape(1,-1).float(),b.reshape(1,-1).float())
        native0=raw['native_0_output']
        state['comparisons']={'native_output_repeats':[], 'native_logits_repeats':[],
                              'native_input_repeats':[], 'isolated_vs_native0':[],
                              'within_series':{},'cross_series':[]}
        for i in range(4):
            state['comparisons']['native_output_repeats'].append(comparison(native0,raw[f'native_{i}_output']))
            state['comparisons']['native_logits_repeats'].append(comparison(raw['native_0_logits'],raw[f'native_{i}_logits']))
            state['comparisons']['native_input_repeats'].append(comparison(raw['native_0_input'],raw[f'native_{i}_input']))
        for row in state['isolated_calls']:
            key=row['key']
            state['comparisons']['isolated_vs_native0'].append({'key':key,**comparison(native0,raw[key])})
        for name in ['functional_linear','mm_reused_output','mm_fresh_output']:
            state['comparisons']['within_series'][name]=[comparison(raw[name+'_0'],raw[f'{name}_{i}']) for i in range(6)]
            state['comparisons']['cross_series'].append({'series':name,**comparison(raw['functional_linear_0'],raw[name+'_0'])})
        tensors=args.output/'raw_operands_and_outputs.pt'
        torch.save(raw,tensors)
        state['raw_tensors']={'path':str(tensors),'sha256':sha256_file(tensors),'keys':sorted(raw)}
        state['operand_checks']={'native_inputs_identical':len({row['input']['sha256'] for row in state['native_calls']})==1,
                                 'native_weights_identical':len({row['weight']['sha256'] for row in state['native_calls']})==1,
                                 'fixed_input_unchanged':state['fixed_input']['sha256']==state['fixed_input_after']['sha256'],
                                 'all_isolated_operands_identical':all(row['input_sha256']==state['fixed_input']['sha256'] and row['weight_sha256']==state['weight_before']['sha256'] for row in state['isolated_calls']),
                                 'distinct_fresh_output_pointers':len({row['output']['data_ptr'] for row in state['isolated_calls'] if row['series']=='mm_fresh_output'})==6}
        state.update(state='complete',ended_at=now(),verdict='diagnostic_only; requires interpretation and independent review')
        save()
    except BaseException as exc:
        state.update(state='failed',ended_at=now(),error=repr(exc),traceback=traceback.format_exc())
        save()
        raise
    finally:
        if lock is not None:
            state['lock_released_at']=now()
            save()
            fcntl.flock(lock,fcntl.LOCK_UN)
            lock.close()

if __name__=='__main__':main()
