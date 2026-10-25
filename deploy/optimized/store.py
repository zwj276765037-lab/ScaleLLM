"""Verified same-session DDR residency and bounded next-layer CPU preparation."""
import dataclasses
import hashlib
import time
from .layout import layer_spans,Span
from .down import DownContext


def sha(data):return hashlib.sha256(data).hexdigest()


class ResidentStore:
    def __init__(self,session,artifacts,evidence,guard,bindings=None):
        self.session,self.artifacts,self.evidence,self.guard=session,artifacts,evidence,guard
        self.records=[];self.ready=False;self.bindings=bindings or {}
    def _load(self,name,record,span):
        self.guard();data=record.read_verified()
        if len(data)!=span.size:raise ValueError('Resident artifact size mismatch')
        start=time.perf_counter();count=self.session.h2c_write_local(span.channel,data,span.address,1<<20)
        if count!=span.size:raise IOError('Short resident H2C')
        actual=self.session.c2h_read_local(span.channel,span.size,span.address,1<<20)
        item=dict(dataclasses.asdict(span),artifact=name,source_sha256=record.sha256,readback_sha256=sha(actual),started_s=start,finished_s=time.perf_counter())
        self.records.append(item);self.evidence.replace_json('resident_load_progress.json',self.records)
        if len(actual)!=span.size or item['readback_sha256']!=record.sha256:raise IOError('Resident DDR readback mismatch: '+name)
    def load(self):
        if self.ready:raise RuntimeError('Residency cannot be assumed/reloaded in a new owner')
        started=time.perf_counter()
        for layer in range(32):
            for name,span in layer_spans(layer).items():self._load('layer%d/%s'%(layer,name),self.artifacts.original.layer_artifact(layer,name),span)
        self._load('rope',self.artifacts.original.rope,Span('rope',0,0x57000000,8192))
        self.ready=True
        result={'same_session_only':True,'bindings':self.bindings,'artifact_manifest_sha256':self.artifacts.manifest_sha256,'checkpoint_sha256':self.artifacts.original.checkpoint_sha256,'load_started_s':started,'load_finished_s':time.perf_counter(),'records':self.records,'h2c_bytes':sum(x['size'] for x in self.records),'c2h_bytes':sum(x['size'] for x in self.records),'GU_weights_not_resident':'RTL canonical bases require current56MiB window per layer'}
        self.evidence.write_json('resident_manifest.json',result);return result
    def require(self):
        if not self.ready:raise RuntimeError('Same-session full resident readback required')


def prepare_layer(artifacts,layer,guard):
    """No device calls; one current+one next layer, immutable worker inputs."""
    start=time.perf_counter();guard()
    data=tuple(artifacts.original.layer_artifact(layer,name).read_verified() for name in ('mlp_gate_up_c0','mlp_gate_up_c1'))
    weights=artifacts.down_weights(layer);context=DownContext(weights);guard()
    return {'layer':layer,'gu_payloads':data,'down_context':context,'prepared_s':time.perf_counter(),'prepare_seconds':time.perf_counter()-start}
