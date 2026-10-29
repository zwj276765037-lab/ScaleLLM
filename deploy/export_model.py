#!/usr/bin/env python3
"""Strict original hardware export plus portable exact BF16->FP32 Host assets."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def load():
    from scalellm import vendor_check, bootstrap
    vendor_check();bootstrap()
    path=HERE.parent/'project/hardware/model/export_scalellm_llama31_artifacts.py'
    spec=importlib.util.spec_from_file_location('strict_exporter',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()


def stream_fp32_matrix(checkpoint,tensor,path,rows,columns,block_rows=256):
    """Bounded exact conversion through the original safetensors reader."""
    import numpy as np
    if min(rows,columns,block_rows)<=0:raise ValueError('Positive matrix/block dimensions required')
    with Path(path).open('xb') as f:
        for start in range(0,rows,block_rows):
            block=np.ascontiguousarray(checkpoint.float32(tensor,rows=slice(start,min(start+block_rows,rows))),dtype='<f4')
            if block.shape!=(min(block_rows,rows-start),columns) or not np.all(np.isfinite(block)):raise ValueError('Invalid/nonfinite source matrix block')
            f.write(memoryview(block).cast('B'))


def host_assets(checkpoint,out,expected,block_rows=256):
    import numpy as np
    export=load();directory=out/'host_assets';directory.mkdir(exist_ok=False);files={}
    def record(name,path,**extra):
        files[name]={'path':path.name,'size':path.stat().st_size,'bytes':path.stat().st_size,'sha256':sha(path),**extra}
    def array(name,data,source):
        data=np.ascontiguousarray(data,dtype='<f4')
        if not np.all(np.isfinite(data)):raise ValueError('Nonfinite source asset: '+name)
        path=directory/(name+'.f32');path.write_bytes(data.tobytes());record(name,path,shape=list(data.shape),dtype='<f4',source_tensor=source,source_dtype='BF16')
    for key,suffix in [('input_norm','input_layernorm.weight'),('post_norm','post_attention_layernorm.weight')]:
        names=['model.layers.%d.%s'%(i,suffix) for i in range(32)];array(key,np.stack([checkpoint.float32(n) for n in names]),names)
    array('final_norm',checkpoint.float32('model.norm.weight'),'model.norm.weight')
    for name,tensor in [('embedding','model.embed_tokens.weight'),('lm_head','lm_head.weight')]:
        path=directory/(name+'.f32')
        stream_fp32_matrix(checkpoint,tensor,path,128256,4096,block_rows)
        record(name,path,shape=[128256,4096],dtype='<f4',source_tensor=tensor,source_dtype='BF16',conversion='exact BF16 bits<<16 viewedFP32')
    generation=json.loads((checkpoint.model_dir/'generation_config.json').read_text(encoding='utf-8'))
    if generation.get('eos_token_id')!=checkpoint.config['eos_token_id']:raise ValueError('Generation EOS IDs must match original model config')
    for name in ('config','tokenizer','tokenizer_config','special_tokens_map','generation_config'):
        path=directory/(name+'.json');shutil.copyfile(checkpoint.model_dir/path.name,path);record(name,path,source_file=path.name)
    path=directory/'chat_template.jinja';path.write_text(checkpoint.tokenizer_config['chat_template'],encoding='utf-8');record('chat_template',path,source_file='tokenizer_config.json')
    manifest={'schema':'scalellm_llama31_host_assets_v1','state':'COMPLETE','model_id':export.MODEL_ID,'checkpoint_sha256':expected,'checkpoint_id':expected,'hidden_size':4096,'vocab_size':128256,'layer_count':32,'rms_norm_eps':1e-5,'files':files}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('identity','export'));p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--expected-checkpoint-sha256');p.add_argument('--resume',action='store_true');a=p.parse_args()
    exporter=load();checkpoint=exporter.LlamaCheckpoint(a.model_dir);identity,data=checkpoint.source_identity()
    if a.action=='identity':print(json.dumps({'checkpoint_sha256':identity,'source_identity':data},indent=2));return
    from final.common import CHECKPOINT_SHA
    if not a.output or identity!=a.expected_checkpoint_sha256 or identity!=CHECKPOINT_SHA:raise ValueError('Explicit output and the documented verified checkpoint identity are required for this release')
    generation=json.loads((checkpoint.model_dir/'generation_config.json').read_text(encoding='utf-8'))
    if generation.get('eos_token_id')!=checkpoint.config['eos_token_id']:raise ValueError('Generation EOS IDs must match original model config')
    a.output=a.output.resolve()
    if a.output==checkpoint.model_dir or a.output.is_relative_to(checkpoint.model_dir):raise ValueError('Export output must be outside the source model directory')
    if (a.output/'host_assets').exists():raise FileExistsError('Host assets already exist; use a new output directory')
    if a.output.exists() and not a.resume:raise FileExistsError('Export output must be new, or explicitly use --resume')
    argv=[sys.executable,str(HERE.parent/'project/hardware/model/export_scalellm_llama31_artifacts.py'),'--model-dir',str(a.model_dir.resolve()),'--output-dir',str(a.output.resolve()),'--expected-checkpoint-sha256',identity]
    if a.resume:argv+=['--resume']
    subprocess.run(argv,check=True)
    assets=a.output/'host_assets'
    if assets.exists():raise FileExistsError('Host assets already exist; verify them separately, do not overwrite')
    host_assets(checkpoint,a.output,identity)
    final,_=checkpoint.source_identity()
    if final!=identity:raise RuntimeError('Checkpoint changed during export')
    print(json.dumps({'verdict':'PASS','checkpoint_sha256':identity,'artifacts':str(a.output/'scalecode_manifest.json'),'host_assets':str(assets/'manifest.json')},indent=2))

if __name__=='__main__':main()
