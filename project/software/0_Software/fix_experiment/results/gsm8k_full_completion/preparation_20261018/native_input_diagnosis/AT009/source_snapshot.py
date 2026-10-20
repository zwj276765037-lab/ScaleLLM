#!/usr/bin/env python3
"""Bounded layer25 BF16 weight lifecycle on one assigned GPU; diagnostic only."""
from __future__ import annotations
import argparse,copy,fcntl,hashlib,inspect,json,os,sys,time,traceback
from pathlib import Path
from gsm8k_protocol import atomic_json,prepare_requests,sha256_file
from run_gsm8k_worker import encode_prompt,now,resolve_generation

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--plan',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--gpu-uuid',required=True)
 p.add_argument('--cpus',required=True)
 args=p.parse_args();args.case,args.device='bf16','cuda:0'
 assigned=[int(x) for x in args.cpus.split(',')]
 args.output.mkdir(parents=True,exist_ok=False)
 (args.output/'source_snapshot.py').write_bytes(Path(__file__).resolve().read_bytes())
 s={'schema':'scalellm_weight_lifecycle_v1','state':'starting','started_at':now(),'pid':os.getpid(),
    'command':sys.argv,'source_sha256':sha256_file(Path(__file__).resolve()),'plan_sha256':sha256_file(args.plan),
    'model':str(args.model),'cpu_affinity':sorted(os.sched_getaffinity(0)),
    'gpu_uuid_requested':os.environ.get('CUDA_VISIBLE_DEVICES'),'snapshots':[],
    'scope':'Only layer25.up_proj, train:0000, original BF16 native eager; no formal qualification or source repair'}
 def save():atomic_json(args.output/'diagnosis.json',s)
 save();lock=None
 try:
  allocations={'GPU-d87ce710-76bf-872d-9739-f0d7c9b52533':[18,19],
               'GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6':[16,17]}
  if args.gpu_uuid not in allocations or sorted(assigned)!=allocations[args.gpu_uuid]:raise RuntimeError('unexpected GPU/CPU assignment')
  if s['cpu_affinity']!=sorted(assigned) or s['gpu_uuid_requested']!=args.gpu_uuid:raise RuntimeError('actual resource allocation mismatch')
  available=next(int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:'))
  s['host_mem_available_start_bytes']=available*1024
  if available<80*1024*1024:raise RuntimeError('MemAvailable below 80GiB reserve')
  base=Path(__file__).resolve().parent.parent
  lock_path=base/'results/gsm8k_full_completion/resource_locks'/(args.gpu_uuid+'.lock')
  lock=lock_path.open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  s.update(state='loading_checkpoint_cpu',lock=str(lock_path),lock_acquired_at=now());save()
  import torch
  from torch.nn.utils import parametrize
  from safetensors import safe_open
  from run_eval_worker import configure_reproducibility,load_model,package_versions
  torch.set_num_threads(2);torch.set_num_interop_threads(2)
  def cpu(t):return t.detach().cpu().contiguous().clone()
  def sha(t):return hashlib.sha256(t.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes()).hexdigest()
  def info(t,hash_value=True):
   ptr=int(t.data_ptr())
   try:version=int(t._version)
   except RuntimeError:version=None
   out={'shape':list(t.shape),'stride':list(t.stride()),'dtype':str(t.dtype),'device':str(t.device),
        'storage_offset':t.storage_offset(),'data_ptr':ptr,'storage_base_ptr':int(t.untyped_storage().data_ptr()),
        'storage_nbytes':t.untyped_storage().nbytes(),'ptr_mod_256':ptr%256,'ptr_mod_128':ptr%128,
        'version':version,'contiguous':t.is_contiguous()}
   if hash_value:out['sha256']=sha(t)
   return out
  key='model.layers.25.mlp.up_proj.weight'
  index=args.model/'model.safetensors.index.json'
  shard=args.model/json.loads(index.read_text())['weight_map'][key]
  with safe_open(str(shard),framework='pt',device='cpu') as f:original=f.get_tensor(key).contiguous().clone()
  torch.save(original,args.output/'checkpoint_weight.pt')
  s['checkpoint']={'key':key,'shard':str(shard),'index_sha256':sha256_file(index),
                   'tensor':info(original),'saved_sha256':sha256_file(args.output/'checkpoint_weight.pt')}
  configure_reproducibility(20260913);torch.cuda.set_device(args.device)
  free,total=torch.cuda.mem_get_info(args.device)
  if free<24*(1<<30):raise RuntimeError('assigned GPU free memory below24GiB')
  s.update(state='loading_model',gpu_uuid_actual=str(torch.cuda.get_device_properties(args.device).uuid),
           gpu_memory_before={'free':free,'total':total},package_versions=package_versions(),
           runtime_flags={'tf32':torch.backends.cuda.matmul.allow_tf32,'bf16_reduced_precision':torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
                          'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),'CUBLAS_WORKSPACE_CONFIG':os.environ.get('CUBLAS_WORKSPACE_CONFIG')});save()
  t=time.perf_counter();model,tokenizer,method,audit=load_model(args)
  # Snapshot immediately after loader, before model config changes or generation preparation.
  module=model.model.layers[25].mlp.up_proj
  s.update(state='loaded_weight_snapshots',load_seconds=time.perf_counter()-t,method=method,module_class=type(module).__module__+'.'+type(module).__qualname__)
  previous=[None]
  def snapshot(label,tensor=module.weight,group='model_weight'):
   torch.cuda.synchronize(args.device)
   descriptor=info(tensor,False);values=cpu(tensor)
   row={'label':label,'group':group,'gpu':descriptor,'cpu':info(values),'captured_at':now(),
        'copy_semantics':'cuda.synchronize then blocking detach().cpu().contiguous().clone(); independent CPU storage'}
   fname=label+'.pt';torch.save(values,args.output/fname)
   row['file']={'path':fname,'sha256':sha256_file(args.output/fname)}
   different=values.view(torch.int16)!=original.view(torch.int16)
   coords=different.nonzero();row['checkpoint_equal']=coords.shape[0]==0;row['changed_elements']=int(coords.shape[0])
   row['changed_bytes']=int((values.view(torch.uint8)!=original.view(torch.uint8)).sum())
   if coords.shape[0]:
    a=(original.view(torch.int16)[different].int()&65535);b=(values.view(torch.int16)[different].int()&65535)
    diffname=label+'_diff.pt';torch.save({'coordinates':coords,'original_bf16_words':a,'observed_bf16_words':b},args.output/diffname)
    row['diff_file']={'path':diffname,'sha256':sha256_file(args.output/diffname)}
    row['max_abs_difference']=float((values.float()-original.float()).abs().max())
   if group=='model_weight':
    if previous[0] is not None:row['changed_from_previous_elements']=int((values.view(torch.int16)!=previous[0].view(torch.int16)).sum())
    previous[0]=values
   s['snapshots'].append(row);save();return values
  loaded0=snapshot('loaded_0');snapshot('loaded_1');snapshot('loaded_2')
  def hook_info(h):
   return {'type':type(h).__module__+'.'+type(h).__qualname__,'qualname':getattr(h,'__qualname__',None),
           'source_file':inspect.getsourcefile(h) if inspect.isfunction(h) or inspect.ismethod(h) else None}
  inventory={}
  for name,obj in [('model',model),('model.model',model.model),('layer25',model.model.layers[25]),('layer25.mlp',model.model.layers[25].mlp),('layer25.up_proj',module)]:
   fn=getattr(obj.forward,'__func__',obj.forward)
   inventory[name]={'class':type(obj).__module__+'.'+type(obj).__qualname__,
                    'forward_qualname':getattr(fn,'__qualname__',None),'forward_file':inspect.getsourcefile(fn),
                    'forward_pre_hooks':{str(k):hook_info(v) for k,v in obj._forward_pre_hooks.items()},
                    'forward_hooks':{str(k):hook_info(v) for k,v in obj._forward_hooks.items()},
                    'is_parametrized':parametrize.is_parametrized(obj),
                    'parameter_versions':{n:int(v._version) for n,v in obj.named_parameters(recurse=False)}}
  import torch.nn.modules.module as module_impl
  inventory['global']={'forward_pre_hooks':{str(k):hook_info(v) for k,v in module_impl._global_forward_pre_hooks.items()},
                       'forward_hooks':{str(k):hook_info(v) for k,v in module_impl._global_forward_hooks.items()}}
  s['pre_diagnostic_hook_inventory']=inventory;model.config.use_cache=True;model.eval()
  request=prepare_requests(args.plan,'smoke')[0]
  if request['sample_id']!='train:0000':raise RuntimeError('unexpected first sample')
  inputs=torch.tensor([encode_prompt(tokenizer,request['prompt'])],device=args.device)
  attention=torch.ones_like(inputs);config,generation=resolve_generation(model,tokenizer,1);config.output_logits=True
  s.update(state='native_prefill_snapshots',sample_id=request['sample_id'],prompt_sha256=request['prompt_sha256'],input_tokens=int(inputs.shape[1]),generation=generation,native_calls=[]);save()
  active=[None]
  def pre(_module,items):
   row=active[0]
   if row is None:return
   if items[0].shape[1]!=inputs.shape[1]:raise RuntimeError('unexpected decode invocation')
   snapshot(row['key']+'_target_pre')
   row['input']=info(items[0]);inputfile=row['key']+'_input.pt';torch.save(cpu(items[0]),args.output/inputfile)
   row['input_file']={'path':inputfile,'sha256':sha256_file(args.output/inputfile)}
  def post(_module,items,out):
   row=active[0]
   if row is None:return
   row['output']=info(out);outputfile=row['key']+'_output.pt';torch.save(cpu(out),args.output/outputfile)
   row['output_file']={'path':outputfile,'sha256':sha256_file(args.output/outputfile)}
   snapshot(row['key']+'_target_post')
  h1=module.register_forward_pre_hook(pre);h2=module.register_forward_hook(post)
  with torch.inference_mode():
   for n in range(2):
    keyname=f'native_{n}';snapshot(keyname+'_before_seed');configure_reproducibility(20260913);snapshot(keyname+'_after_seed')
    row={'key':keyname};s['native_calls'].append(row);active[0]=row
    result=model.generate(input_ids=inputs.clone(),attention_mask=attention.clone(),generation_config=copy.deepcopy(config))
    row['generated_ids']=result.sequences[0,inputs.shape[1]:].detach().cpu().tolist();row['logits_sha256']=sha(result.logits[0])
    torch.save(cpu(result.logits[0]),args.output/(keyname+'_logits.pt'));active[0]=None;del result
    snapshot(keyname+'_after_generate')
   h1.remove();h2.remove()
   s['state']='independent_checkpoint_roundtrip';save()
   independent=torch.empty_like(module.weight)
   independent.copy_(original,non_blocking=False)
   s['independent_gpu_tensor']=info(independent,False)
   for n in range(3):snapshot(f'independent_roundtrip_{n}',independent,'independent_correct_weight')
   snapshot('model_weight_after_roundtrip')
  s.update(state='complete',ended_at=now(),verdict='bounded evidence only; interpretation and independent review required');save()
 except BaseException as exc:
  s.update(state='failed',ended_at=now(),error=repr(exc),traceback=traceback.format_exc());save();raise
 finally:
  if lock is not None:
   s['lock_released_at']=now();save();fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
if __name__=='__main__':main()
