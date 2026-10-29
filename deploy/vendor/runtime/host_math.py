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
        self.path=Path(path).resolve();self.manifest=json.loads(self.path.read_text(encoding='utf-8'))
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
        self.config=json.loads(self.file('config').read_text(encoding='utf-8'))
        if self.config.get('rms_norm_eps')!=1e-5 or self.config.get('hidden_size')!=HIDDEN or self.config.get('num_hidden_layers')!=32 or self.config.get('vocab_size')!=VOCAB:
            raise ValueError('Original Host model config mismatch')
        self.tokenizer_config=json.loads(self.file('tokenizer_config').read_text(encoding='utf-8'))
        self.generation_config=json.loads(self.file('generation_config').read_text(encoding='utf-8'))
        if self.generation_config.get('eos_token_id')!=self.config.get('eos_token_id'):
            raise ValueError('Original model/generation EOS metadata disagree')
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
