"""Bounded CPU assets and FP32 boundaries for actual checkpoint inference.

No device or GPU API is imported. All matrices remain read-only mmaps.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from host.scalellm_hostops import rms_norm, LlamaNormWeights

CHECKPOINT_SHA='8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d'
HIDDEN=4096
VOCAB=128256


def file_sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(1<<20),b''):h.update(data)
    return h.hexdigest()


class HostAssets:
    def __init__(self,path,verify=True):
        self.path=Path(path).resolve();self.manifest=json.loads(self.path.read_text())
        m=self.manifest
        if m.get('schema')!='scalellm_llama31_host_assets_v1' or m['state']!='COMPLETE' or m['checkpoint_sha256']!=CHECKPOINT_SHA or m['layer_count']!=32 or m['hidden_size']!=4096 or m['vocab_size']!=128256:
            raise ValueError('Host assets identity/shape mismatch')
        for name,entry in m['files'].items():
            p=(self.path.parent/entry['path']).resolve();p.relative_to(self.path.parent)
            if p.stat().st_size!=entry['size'] or (verify and file_sha(p)!=entry['sha256']):raise ValueError('Host asset hash/size mismatch: '+name)
        def mmap(name,shape):
            entry=m['files'][name]
            if entry['dtype']!='<f4' or entry['shape']!=list(shape):raise ValueError('Host asset array layout mismatch: '+name)
            return np.memmap(self.path.parent/entry['path'],mode='r',dtype='<f4',shape=shape)
        self.embedding=mmap('embedding',(VOCAB,HIDDEN));self.lm_head=mmap('lm_head',(VOCAB,HIDDEN))
        self.weights=LlamaNormWeights(np.asarray(mmap('input_norm',(32,HIDDEN))).copy(),
                                     np.asarray(mmap('post_norm',(32,HIDDEN))).copy(),
                                     np.asarray(mmap('final_norm',(HIDDEN,))).copy(),epsilon=1e-5)
        self.config=json.loads(self.file('config').read_text())
        if self.config.get('rms_norm_eps')!=1e-5 or self.config.get('hidden_size')!=HIDDEN or self.config.get('num_hidden_layers')!=32 or self.config.get('vocab_size')!=VOCAB:
            raise ValueError('Original Host model config mismatch')
        self.tokenizer_config=json.loads(self.file('tokenizer_config').read_text())
        self.generation_config=json.loads(self.file('generation_config').read_text())
    def file(self,name):return self.path.parent/self.manifest['files'][name]['path']
    def embed(self,ids):
        original=np.asarray(ids)
        if original.dtype.kind not in 'iu':raise ValueError('Embedding IDs must be integers')
        ids=np.asarray(original,dtype=np.int64)
        if ids.shape!=(16,) or np.any(ids<0) or np.any(ids>=VOCAB):raise ValueError('Embedding requires16 vocabulary IDs')
        values=np.ascontiguousarray(self.embedding[ids],dtype=np.float32)
        if not np.all(np.isfinite(values)):raise ValueError('Nonfinite source embedding')
        return values
    def final_normalized(self,hidden):return rms_norm(hidden,self.weights.final_norm,1e-5)


def actual_requests(assets,prompts=('Hi','Hello'),max_new_tokens=2):
    if type(max_new_tokens) is not int or not 1<=max_new_tokens<16:
        raise ValueError('Generation limit must be an integer in1..15')
    if len(prompts)!=2 or not all(isinstance(text,str) and text for text in prompts):
        raise ValueError('Two nonempty real prompts are required')
    from tokenizers import Tokenizer
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    tokenizer=Tokenizer.from_file(str(assets.file('tokenizer')))
    environment=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
    def fail(message):raise ValueError(message)
    environment.globals['raise_exception']=fail
    config=assets.tokenizer_config
    def content(x):return x.get('content') if isinstance(x,dict) else x
    template=environment.from_string(config['chat_template'])
    padding=tokenizer.token_to_id('<|finetune_right_pad_id|>');bos=tokenizer.token_to_id('<|begin_of_text|>')
    if padding is None or bos is None:raise ValueError('Original tokenizer lacks required explicit special tokens')
    stops=set()
    for metadata in (assets.config,assets.generation_config):
        value=metadata.get('eos_token_id',[]);stops.update(value if isinstance(value,list) else [value])
    stops.add(tokenizer.token_to_id(content(config['eos_token'])))
    if None in stops or not all(type(x) is int and 0<=x<VOCAB for x in stops):raise ValueError('Invalid original EOS metadata')
    requests=[]
    for index,text in enumerate(prompts):
        rendered=template.render(messages=[{'role':'user','content':text}],bos_token=content(config['bos_token']),eos_token=content(config['eos_token']),add_generation_prompt=True)
        ids=tokenizer.encode(rendered,add_special_tokens=False).ids
        if ids.count(bos)!=1 or not 1<=len(ids)<=16-max_new_tokens:raise ValueError('Prompt BOS/context limit mismatch')
        requests.append({'external_request_id':'request_'+str(index),'prompt_text':text,'rendered_chat':rendered,
                         'initial_token_ids':ids,'max_new_tokens':max_new_tokens,'padding_token_id':padding,
                         'eos_token_ids':sorted(stops),'generated_ids':[],'decoded_generated_text':'','stop_reason':None})
    return tokenizer,requests


def stream_logits(final_normalized,last_valid_row,weights,chunk_rows=2048):
    """Same FP32 block product as existing streaming_lm_head, retaining all logits."""
    hidden=np.asarray(final_normalized,dtype=np.float32)
    if hidden.ndim!=2 or hidden.shape[1]<1 or type(last_valid_row) is not int or not 0<=last_valid_row<len(hidden) or getattr(weights,'ndim',None)!=2 or weights.shape[0]<1 or weights.shape[1]!=hidden.shape[1] or type(chunk_rows) is not int or not 1<=chunk_rows<=4096:
        raise ValueError('LM-head row/shape/chunk mismatch')
    if not np.all(np.isfinite(hidden)):raise ValueError('Nonfinite final-normalized hidden')
    values=np.ascontiguousarray(hidden[last_valid_row:last_valid_row+1],dtype=np.float32)
    logits=np.empty(weights.shape[0],dtype='<f4')
    for start in range(0,len(logits),chunk_rows):
        stop=min(start+chunk_rows,len(logits));block=np.asarray(weights[start:stop],dtype=np.float32)
        if not np.all(np.isfinite(block)):raise ValueError('Nonfinite original LM-head weights')
        logits[start:stop]=np.asarray(values@block.T,dtype=np.float32)[0]
    if not np.all(np.isfinite(logits)):raise ValueError('Nonfinite LM-head logits')
    # np.argmax returns the first maximum: deterministic lower-token-ID tie.
    return logits,int(np.argmax(logits))
