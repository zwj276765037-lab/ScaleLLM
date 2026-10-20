"""Cache only three assembly APIs while the frozen R005 worker processes groups.

No numerical symbol is patched. The model, attached buffers and common output
head are reused in one real GPU process. Per-group observers/state remain owned
by the unchanged extended_worker and are released after its normal return.
"""
from __future__ import annotations
from contextlib import contextmanager
import copy
import json
from pathlib import Path
from run_numerical_fidelity import identity,write_json,timestamp


class ExtendedSessionCache:
    def __init__(self,directory,model_dir):
        self.directory=Path(directory);self.model_dir=Path(model_dir).resolve()
        self.base=self.audit=self.metadata=self.head=None
        self.loads=dict(base=0,attach=0,head=0)
        self._active=False;self.device=None;self.attach_options=None
        self.directory.mkdir(parents=True,exist_ok=True)

    def _event(self,api,cached,destination):
        with (self.directory/'session_cache_events.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(at=timestamp(),api=api,cached=cached,group_destination=str(destination),actual_loads=self.loads))+'\n')

    def _model_key(self,model_dir,device):
        if Path(model_dir).resolve()!=self.model_dir:raise ValueError('resident checkpoint changed')
        device=str(device)
        if self.device is None:self.device=device
        if device!=self.device:raise ValueError('resident device changed')

    @contextmanager
    def context(self,loader_module,compat_module,head_module):
        if self._active:raise RuntimeError('session cache contexts cannot nest')
        originals=(loader_module.load_streamed_bf16_model,compat_module.attach_v5_fullchain_compatible,head_module.load_output_head)
        cache=self
        def load_base(model_dir,device,directory):
            cache._model_key(model_dir,device);hit=cache.base is not None
            if not hit:
                cache.base=originals[0](model_dir,device,cache.directory)
                cache.loads['base']+=1
            destination=Path(directory);destination.mkdir(parents=True,exist_ok=True)
            write_json(destination/'shared_loader_reference.json',dict(runtime_kind='shared_resident_model',
                global_loader=identity(cache.directory/'stream_loader_validation.json')))
            cache._event('base_loader',hit,directory)
            return cache.base
        def attach(facade,*,checkpoint_dir,device,**options):
            cache._model_key(checkpoint_dir,device)
            if facade.model is not cache.base:raise ValueError('attach facade is not the resident base')
            hit=cache.metadata is not None
            if not hit:
                metadata,cache.audit=originals[1](facade,checkpoint_dir=checkpoint_dir,device=device,**options)
                cache.metadata=copy.deepcopy(metadata);cache.attach_options=copy.deepcopy(options)
                cache.loads['attach']+=1
            elif options!=cache.attach_options:raise ValueError('resident production format options changed')
            cache._event('v5_attach',hit,'resident model')
            return copy.deepcopy(cache.metadata),cache.audit
        def load_head(model_dir,device,evidence_dir):
            cache._model_key(model_dir,device);hit=cache.head is not None
            if not hit:
                cache.head=originals[2](model_dir,device,cache.directory/'output_head')
                cache.loads['head']+=1
            # A small identity copy is explicit; GPU head/launch evidence is shared.
            directory=Path(evidence_dir);directory.mkdir(parents=True,exist_ok=True)
            write_json(directory/'output_head_identity.json',cache.head.source)
            write_json(directory/'shared_head_reference.json',dict(runtime_kind='shared_resident_head',
                global_head=identity(cache.directory/'output_head/output_head_identity.json')))
            cache._event('head_loader',hit,directory)
            return cache.head
        try:
            self._active=True
            loader_module.load_streamed_bf16_model=load_base
            compat_module.attach_v5_fullchain_compatible=attach
            head_module.load_output_head=load_head
            yield self
        finally:
            loader_module.load_streamed_bf16_model,compat_module.attach_v5_fullchain_compatible,head_module.load_output_head=originals
            self._active=False
