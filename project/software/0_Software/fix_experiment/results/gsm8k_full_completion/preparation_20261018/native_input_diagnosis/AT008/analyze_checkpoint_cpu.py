#!/usr/bin/env python3
"""CPU-only independent recomputation of AT008 final checkpoint weight diff."""
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import torch
from safetensors import safe_open

root=Path(__file__).resolve().parent
experiment=root.parents[4]
sys.path.insert(0,str(experiment/'exp'))
from run_eval_worker import load_model,configure_reproducibility
from transformers.models.llama.modeling_llama import LlamaMLP

def sha_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sha(t):return hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('CPU analysis requires explicitly empty CUDA_VISIBLE_DEVICES')
if set(os.sched_getaffinity(0))!={18,19}:raise RuntimeError('CPU affinity must be 18,19')
model=Path('/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct')
key='model.layers.25.mlp.up_proj.weight'
index=json.loads((model/'model.safetensors.index.json').read_text())
shard=model/index['weight_map'][key]
with safe_open(str(shard),framework='pt',device='cpu') as f: original=f.get_tensor(key).contiguous().clone()
raw=torch.load(root/'raw_operands_and_outputs.pt',map_location='cpu',weights_only=True)
observed=raw['fixed_weight']
a=original.view(torch.int16).int()&65535
b=observed.view(torch.int16).int()&65535
mask=a!=b
coordinates=mask.nonzero()
x,y=a[mask],b[mask]
words=[]
for r,c in coordinates[:16].tolist():
 p,q=int(a[r,c]),int(b[r,c])
 words.append({'row':r,'col':c,'original_float':float(original[r,c]),'observed_float':float(observed[r,c]),'original_bf16_hex':f'{p:04x}','observed_bf16_hex':f'{q:04x}','xor_hex':f'{p^q:04x}'})
report={'schema':'scalellm_up_proj_checkpoint_recomputation_v1','source_sha256':sha_file(Path(__file__)),
        'pid':os.getpid(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],
        'cuda_initialized':torch.cuda.is_initialized(),'checkpoint_shard':str(shard),'weight_key':key,
        'original':{'shape':list(original.shape),'dtype':str(original.dtype),'sha256':sha(original),'data_ptr':original.data_ptr()},
        'observed':{'shape':list(observed.shape),'dtype':str(observed.dtype),'sha256':sha(observed),'data_ptr':observed.data_ptr()},
        'changed_elements':int(mask.sum()),'changed_bytes':int((original.view(torch.uint8)!=observed.view(torch.uint8)).sum()),
        'max_abs_difference':float((original.float()-observed.float()).abs().max()),
        'bounds':{'row_min':int(coordinates[:,0].min()),'row_max':int(coordinates[:,0].max()),'col_min':int(coordinates[:,1].min()),'col_max':int(coordinates[:,1].max())},
        'row_counts':[{'row':int(r),'changed_elements':int(mask[r].sum())} for r in coordinates[:,0].unique()],
        'high_byte_changes':int(((x>>8)!=(y>>8)).sum()),
        'changed_new_low_byte_value_counts':dict(zip(*[t.tolist() for t in torch.unique(y&255,return_counts=True)])),
        'only_set_bits_all':bool(((x&~y)==0).all()),'cleared_bits_elements':int(((x&~y)!=0).sum()),
        'first_16_changed':words,
        'cpu_storage_independent':original.data_ptr()!=observed.data_ptr(),
        'sha_method':'SHA256 of contiguous BF16 CPU byte view numpy.tobytes; no dtype conversion',
        'capture_semantics':'GPU digest uses blocking tensor.detach().contiguous().cpu(); persisted cpu(t) uses detach().cpu().contiguous().clone(); no non_blocking=True.',
        'limitations':['Only final fixed GPU weight persisted as CPU tensor; native per-call weight tensors were not persisted, so bit trajectories/recovery are unavailable.',
                      'Native1/native2 same pre-weight SHA but differing output limits causal attribution.',
                      'AT008 did not persist actual loaded module hook/parametrization inventory or weight._version.']}
(root/'checkpoint_weight_comparison_recomputed.json').write_text(json.dumps(report,indent=2)+'\n')
snippets={name:inspect.getsource(obj) for name,obj in {'load_model':load_model,'configure_reproducibility':configure_reproducibility,'Linear.forward':torch.nn.Linear.forward,'LlamaMLP.forward':LlamaMLP.forward}.items()}
inspection={'source_snippets':snippets,'file_sha256':{},'conclusions':['AT008 records actual module class torch.nn.modules.linear.Linear.',
            'BF16 load_model bypasses all quantization/V5 branches and returns method.case=bf16.',
            'Installed Linear.forward calls F.linear(input,self.weight,self.bias); LlamaMLP.forward reads gate/up/down through modules.',
            'AT008 pre/post hooks capture CPU clones/hashes and have no explicit weight write.',
            'Runtime hook/parametrization absence cannot be proved because this attempt did not save that inventory.']}
for obj in [load_model,configure_reproducibility,torch.nn.Linear.forward,LlamaMLP.forward]:
 p=Path(inspect.getsourcefile(obj));inspection['file_sha256'][str(p)]=sha_file(p)
(root/'bf16_write_path_inspection_recomputed.json').write_text(json.dumps(inspection,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['changed_elements','changed_bytes','max_abs_difference','high_byte_changes','changed_new_low_byte_value_counts','cleared_bits_elements','cuda_initialized']},indent=2))
