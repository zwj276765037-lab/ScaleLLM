"""R011 only decoder31: original seven V5 linears, norms and unchanged arithmetic.
Observers and conditional output substitutions are process-local and restored.
"""
from __future__ import annotations
from contextlib import contextmanager
from types import SimpleNamespace
import numpy as np
import torch
from torch import nn
from numerical_reference.model_compat import production_module
from numerical_reference.chunked_quantization import chunked_weight_context
from numerical_reference.gpu_reference import arithmetic_context
v5=production_module()

class SingleBlock(nn.Module):
    def __init__(self,checkpoint,device,progress):
        super().__init__();self.audit=v5.V5Audit(device);mods={}
        for op in ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']:
            attention=op in ['q_proj','k_proj','v_proj','o_proj'];name=f'model.layers.31.{"self_attn" if attention else "mlp"}.{op}.weight';progress('loading_weight',op=op)
            with chunked_weight_context(v5,128):mods[op]=v5._quantized_linear_from_checkpoint(checkpoint=checkpoint,tensor_name=name,op_name=op,weight_bits=8 if attention else 4,input_width=32 if op=='down_proj' else 24,hadamard_width=35 if op=='down_proj' else 27,output_width=32 if op=='down_proj' else 24,device=device,audit=self.audit,strict_total_shift=True,software_extended=False,down_shift12_candidate=op=='down_proj')
        self.linears=mods
        cfg=checkpoint.config;proxy=SimpleNamespace(config=SimpleNamespace(**cfg),layer_idx=31,num_heads=32,num_key_value_heads=8,num_key_value_groups=4,head_dim=128,hidden_size=4096)
        cos,sin=v5._rope_tables(cfg,device)
        self.attention=v5.V5Attention(proxy,*(mods[k] for k in ['q_proj','k_proj','v_proj','o_proj']),self.audit,cos,sin)
        self.mlp=v5.V5MLP(*(mods[k] for k in ['gate_proj','up_proj','down_proj']),device,self.audit,layer_idx=31)
        def norm(name):
            original=SimpleNamespace(weight=torch.from_numpy(checkpoint.float32(name)),variance_epsilon=1e-5)
            return v5.HostFP32RMSNorm(original,device)
        self.norm1=norm('model.layers.31.input_layernorm.weight');self.norm2=norm('model.layers.31.post_attention_layernorm.weight');self.final_norm=norm('model.norm.weight')
        self.eval()

    def forward(self,x,trace):
        x=trace.emit('input',x);n=trace.emit('input_norm',self.norm1(x))
        attention=self.attention(n,use_cache=False)[0];attention=trace.emit('attention_output',attention)
        residual=trace.emit('attention_residual',x+attention)
        n=trace.emit('post_attention_norm',self.norm2(residual))
        mlp=trace.emit('mlp_output',self.mlp(n));result=trace.emit('final_residual',residual+mlp)
        final=trace.emit('final_norm',self.final_norm(result))
        return result,final

class Trace:
    def __init__(self,substitutions=None):self.data={};self.bits={};self.dynamic={};self.ordinal={};self.substitutions=substitutions or {};self.replaced=[]
    def emit(self,name,value,bits=0):
        if name in self.substitutions:
            saved=self.substitutions[name];assert tuple(saved.shape)==tuple(value.shape)
            value=torch.from_numpy(saved).to(device=value.device,dtype=value.dtype);self.replaced.append(name)
        assert name not in self.data,name
        self.data[name]=np.ascontiguousarray(value.detach().cpu().numpy()).copy();self.bits[name]=bits
        return value
    def next(self,name):n=self.ordinal.get(name,0);self.ordinal[name]=n+1;return n
    def real(self,name):return self.data[name].astype(np.float64)*(2.**-self.bits[name])

@contextmanager
def tracing(block,trace):
    names=['prepare_fixed_activation','_fixed_rope','_kv12_quantize','_qk_scores_s20','_softmax_u16','_pv_s24','_swiglu_s32']
    original={n:getattr(v5,n) for n in names};methods={k:(m,'project_prepared' in m.__dict__,m.__dict__.get('project_prepared'),m.project_prepared) for k,m in block.linears.items()}
    def prepare(*args,**kw):
        n=trace.next('prepare');result=original['prepare_fixed_activation'](*args,**kw);raw=args[0];trace.emit(f'prepare{n}_input',raw,16)
        normalized=v5._round_shift_away(v5._fwht32_int(raw.to(torch.int64).reshape(-1,raw.shape[-1]//32,32).clone())*v5.INV_SQRT32_Q16,16);hw=kw['hadamard_width'];normalized=normalized.clamp(-(1<<(hw-1)),(1<<(hw-1))-1)
        trace.emit(f'prepare{n}_hadamard',normalized,16)
        deq=(result.values_u8.to(torch.float64)-result.zero_points_u8[...,None].to(torch.float64))*result.codes_u8[...,None].to(torch.float64)
        deq=torch.ldexp(deq,-result.shifts_u8[...,None].to(torch.int32));trace.emit(f'prepare{n}_dequant',deq)
        trace.dynamic[f'prepare{n}']={k:np.ascontiguousarray(getattr(result,k).cpu().numpy()).copy() for k in ['values_u8','codes_u8','shifts_u8','zero_points_u8']}
        return result
    def rope(*args,**kw):
        n=trace.next('rope');return trace.emit('query_rope' if n==0 else 'key_rope',original['_fixed_rope'](*args,**kw),16)
    def kv(*args,**kw):
        n=trace.next('kv');result=original['_kv12_quantize'](*args,**kw);deq=result.values_s12.to(torch.float64)*result.codes_u8[...,None].to(torch.float64)
        deq=torch.ldexp(deq,-result.shifts_u8[...,None].to(torch.int32));trace.emit('key_cache_dequant' if n==0 else 'value_cache_dequant',deq)
        trace.dynamic[f'kv{n}']={k:np.ascontiguousarray(getattr(result,k).cpu().numpy()).copy() for k in ['values_s12','codes_u8','shifts_u8']};return result
    def simple(name,label,bits):
        def call(*a,**kw):return trace.emit(label,original[name](*a,**kw),bits)
        return call
    def swiglu(*args,**kw):
        gate,up,table=args[:3];g=gate.to(torch.int64);g=torch.where((g>v5.S24_MAX)&(g<=(1<<24)-1),g-(1<<24),g)
        address=((g+v5.SILU_LIMIT_Q16+128)>>8).clamp(0,8192);silu=torch.where(g<=-v5.SILU_LIMIT_Q16,torch.zeros_like(g),torch.where(g>=v5.SILU_LIMIT_Q16,g,table[address].to(torch.int64)))
        trace.emit('silu',silu,16);trace.dynamic['silu']={'lut_address':address.cpu().numpy().astype(np.int16)}
        return trace.emit('gated_product',original['_swiglu_s32'](*args,**kw),16)
    try:
        for op,(module,had,saved,method) in methods.items():
            def observed(*a,op=op,method=method,**kw):return trace.emit(op,method(*a,**kw),16)
            module.project_prepared=observed
        v5.prepare_fixed_activation=prepare;v5._fixed_rope=rope;v5._kv12_quantize=kv;v5._qk_scores_s20=simple('_qk_scores_s20','qk_scores',14);v5._softmax_u16=simple('_softmax_u16','attention_softmax',16);v5._pv_s24=simple('_pv_s24','pv_context',16);v5._swiglu_s32=swiglu
        yield
    finally:
        for n,f in original.items():setattr(v5,n,f)
        for module,had,saved,method in methods.values():
            if had:module.project_prepared=saved
            else:module.__dict__.pop('project_prepared',None)
        assert all(getattr(v5,n) is f for n,f in original.items())
        assert all(('project_prepared' in m.__dict__)==had and (not had or m.__dict__['project_prepared'] is saved) for m,had,saved,method in methods.values())

def run_block(block,x,policy,substitutions=None):
    trace=Trace(substitutions)
    with torch.inference_mode(),arithmetic_context(v5,policy),tracing(block,trace):result,final=block(x,trace)
    assert trace.ordinal==dict(prepare=4,rope=2,kv=2),trace.ordinal
    assert len(trace.data)==36,(len(trace.data),list(trace.data))
    assert not hasattr(v5,'_m005_arithmetic_context_active')
    assert set(trace.replaced)==set(trace.substitutions)
    return trace,result,final

def cpu_checks():
    from r008_operator_diagnostic import policies
    from numerical_reference.gpu_reference import arithmetic_context
    functions=['grouped_linear_s24','_fixed_rope','_qk_scores_s20','_softmax_u16','_pv_s24'];n=0
    for p in policies().values():
        fake=SimpleNamespace(**{k:object() for k in functions});original={k:getattr(fake,k) for k in functions}
        for fail in [False,True]:
            try:
                with arithmetic_context(fake,p):
                    if fail:raise ValueError('restoration')
            except ValueError:pass
            assert all(getattr(fake,k) is f for k,f in original.items()) and not hasattr(fake,'_m005_arithmetic_context_active');n+=1
    a=np.array([1.,2.,-3.]);b=np.array([.5,-2.,1.]);c=np.array([3.,1.,-4.]);assert np.array_equal(a-b,(a-c)+(c-b))
    assert np.dot(a-b,a-b)==np.dot(a-c,a-c)+np.dot(c-b,c-b)+2*np.dot(a-c,c-b)
    probe=torch.full((1,32),1<<29,dtype=torch.int32)
    normalized=v5._round_shift_away(v5._fwht32_int(probe.to(torch.int64).reshape(-1,1,32).clone())*v5.INV_SQRT32_Q16,16).clamp(-(1<<34),(1<<34)-1)
    assert normalized.dtype==torch.int64 and int(normalized.max())>2**31-1
    assert not torch.cuda.is_initialized()
    return dict(large_int32_to_S35_observer_probe=True,passed=True,policy_restoration_checks=n,vector_energy_identity=True,cuda_initialized=False)
