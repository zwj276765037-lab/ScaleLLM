"""Production-current arithmetic, separate from the exact reference implementation."""
from __future__ import annotations
import ast
from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path
import sys
import numpy as np

EXPERIMENT=Path(__file__).resolve().parents[1]
SOFTWARE=EXPERIMENT.parents[2]
V5=SOFTWARE/'0_Software/FPtoQ/experiment/v5_fullchain.py'

@lru_cache(maxsize=1)
def _v5():
    # Importing this CPU code does not initialize CUDA. No device selection,
    # CUDA query, allocation, or Triton launch is used by this module.
    for path in (SOFTWARE,V5.parent):
        if str(path) not in sys.path:
            sys.path.insert(0,str(path))
    import v5_fullchain
    return v5_fullchain

@lru_cache(maxsize=1)
def _linear_source():
    if str(EXPERIMENT) not in sys.path:
        sys.path.insert(0,str(EXPERIMENT))
    import production_replay
    return production_replay._production_expressions()

class _ArrayTL:
    maximum=staticmethod(np.maximum)
    minimum=staticmethod(np.minimum)
    where=staticmethod(np.where)

@lru_cache(maxsize=1)
def _qk_source():
    source=V5.read_text()
    function=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='_qk_scores_s20')
    assignments={x.targets[0].id:x.value for x in function.body if isinstance(x,ast.Assign) and len(x.targets)==1 and isinstance(x.targets[0],ast.Name)}
    # Exact array substitutions only adapt native [B,H,G,Q,K] broadcasting to
    # a batch of scalar score records [N,G]; arithmetic expressions stay live.
    class Broadcast(ast.NodeTransformer):
        def visit_Subscript(self,node):
            if isinstance(node.value,ast.Name) and node.value.id in ('codes','shifts'):
                return ast.copy_location(ast.Name(node.value.id,ast.Load()),node)
            return self.generic_visit(node)
    result={}
    for name in ('scaled_s61','group_q14'):
        value=Broadcast().visit(assignments[name])
        expression=ast.fix_missing_locations(ast.Expression(value))
        allowed=(ast.Expression,ast.Name,ast.Load,ast.Constant,ast.BinOp,ast.Mult,ast.Add,ast.RShift)
        if any(not isinstance(x,allowed) for x in ast.walk(expression)):
            raise ValueError('unsupported active QK AST')
        result[name]=compile(expression,str(V5),'eval')
    return result


@lru_cache(maxsize=1)
def _softmax_trace():
    # Instrument a private copy of this one trusted production function; the
    # installed production module and all numerical expressions are unchanged.
    source=V5.read_text()
    function=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='_softmax_u16')
    rewritten=[]
    found=False
    for statement in function.body:
        if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name) and statement.targets[0].id=='probability':
            call=statement.value
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or call.func.attr!='clamp_max':
                raise ValueError('active Softmax clamp AST changed')
            rewritten.append(ast.Assign(targets=[ast.Name('_pre_cap',ast.Store())],value=call.func.value))
            found=True
        if isinstance(statement,ast.Return):
            statement.value=ast.Tuple(elts=[statement.value,ast.Name('_pre_cap',ast.Load())],ctx=ast.Load())
        rewritten.append(statement)
    if not found:
        raise ValueError('active Softmax probability assignment missing')
    function.body=rewritten
    namespace=dict(vars(_v5()))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(V5),'exec'),namespace)
    return namespace['_softmax_u16']


def _numpy(value):
    return value.detach().cpu().numpy().astype(np.int64,copy=False)


def _identity():
    return dict(path=str(V5),sha256=hashlib.sha256(V5.read_bytes()).hexdigest(),
                arithmetic='active_V5_CPU_or_bounded_AST',gpu_executed=False)


def evaluate_current(node,a,config):
    from .policy import PROFILES
    if node=='linear':
        expressions,manifest=_linear_source()
        spec=PROFILES[config['profile']]
        n=a['dot'].shape[0]
        scope=dict(tl=_ArrayTL,accumulator=np.zeros(n,dtype=np.int64),
                   SHIFT_MIN=spec['shift_min'],SHIFT_MAX=spec['shift_max'],
                   COMPUTE_ACCUM_MIN=-(1<<(spec['accumulator_width']-1)),
                   COMPUTE_ACCUM_MASK=(1<<spec['accumulator_width'])-1,
                   OUTPUT_MIN=-(1<<(spec['output_width']-1)),OUTPUT_MAX=(1<<(spec['output_width']-1))-1)
        overflow=np.zeros(n,dtype=bool)
        guard_overflow=np.zeros(n,dtype=bool)
        events=np.zeros(n,dtype=np.int64)
        for g in range(a['dot'].shape[1]):
            scope.update(correlation=a['dot'][:,g],act_code=a['act_code'][:,g],weight_code=a['weight_code'][:,g],
                         act_shift=a['act_shift'][:,g],weight_shift=a['weight_shift'][:,g])
            for name in ('raw','delta','right','left','aligned','pair_active','legal_shift'):
                scope[name]=eval(expressions[name],{'__builtins__':{}},scope)
            # production_replay scalarizes tensor ~ to Python not. Array
            # input needs the tensor equivalent, using its original predicate.
            scope['guard']=np.where(scope['pair_active'] & ~scope['legal_shift'],0,scope['aligned'])
            guard_overflow|=(scope['aligned']<-(1<<(spec['guard_width']-1)))|(scope['aligned']>(1<<(spec['guard_width']-1))-1)
            scope['next_accumulator']=eval(expressions['next_accumulator'],{'__builtins__':{}},scope)
            event=(scope['next_accumulator']<scope['COMPUTE_ACCUM_MIN'])|(scope['next_accumulator']>-scope['COMPUTE_ACCUM_MIN']-1)
            overflow|=event
            events+=event
            scope['accumulator']=eval(expressions['accumulator'],{'__builtins__':{}},scope)
        for name in ('rounded','saturated'):
            scope[name]=eval(expressions[name],{'__builtins__':{}},scope)
        return dict(code=scope['saturated'],pre_clip_code=scope['rounded'],saturation_mask=scope['rounded']!=scope['saturated'],
                    overflow_mask=overflow|guard_overflow,error_counts=dict(accumulator_overflow=events,guard_overflow=guard_overflow.astype(np.int64)),source_identity=manifest)
    if node=='qk':
        expression=_qk_source()
        scope=dict(dot_s40=a['dot'],codes=a['kv_code'],shifts=np.where(a['kv_code']!=0,a['kv_shift'],0),HEAD_SCALE_Q16=5793)
        scope['scaled_s61']=eval(expression['scaled_s61'],{'__builtins__':{}},scope)
        group=eval(expression['group_q14'],{'__builtins__':{}},scope)
        pre=np.sum(group,axis=-1,dtype=np.int64)
        code=np.clip(pre,-(16<<14),16<<14)
        return dict(code=code,pre_clip_code=pre,clip_mask=pre!=code,source_identity=_identity())
    import torch
    v5=_v5()
    def tensor(value):
        return torch.from_numpy(np.array(value,copy=True))
    audit=v5.V5Audit(torch.device('cpu'))
    if node=='rope':
        count=a['raw_pair'].shape[0]
        raw=np.zeros((count,1,1,128),dtype=np.int64)
        raw[:,0,0,0]=a['raw_pair'][:,0]
        raw[:,0,0,64]=a['raw_pair'][:,1]
        cos=np.zeros((count,1,64),dtype=np.int64);sin=cos.copy()
        cos[:,0,0]=a['cos_q16'];sin[:,0,0]=a['sin_q16']
        out=_numpy(v5._fixed_rope(tensor(raw),tensor(cos),tensor(sin),audit))[:,0,0,:][:,[0,64]]
        # The active per-product round helper gives its actual pre-clamp code.
        x,y=tensor(a['raw_pair'][:,0]),tensor(a['raw_pair'][:,1])
        c,s=tensor(a['cos_q16']),tensor(a['sin_q16'])
        pre=_numpy(torch.stack((v5._round_shift_away(x*c,16)-v5._round_shift_away(y*s,16),
                               v5._round_shift_away(x*s,16)+v5._round_shift_away(y*c,16)),dim=-1))
        return dict(code=out,pre_clip_code=pre,saturation_mask=out!=pre,source_identity=_identity())
    if node=='softmax':
        output,pre=_softmax_trace()(tensor(a['score_q14']),tensor(a['valid_mask']),tensor(a['lut_u17']))
        code=_numpy(output);pre=_numpy(pre)
        return dict(code=code,pre_clip_code=pre,clip_mask=(pre>65535)&a['valid_mask'],source_identity=_identity())
    if node=='pv':
        count,keys=a['probability_u16'].shape
        values=np.zeros((count,keys,1,4,32),dtype=np.int16)
        codes=np.zeros((count,keys,1,4),dtype=np.uint8);shifts=codes.copy()
        values[:,:,0,0,0]=a['value_s12']
        codes[:,:,0,0]=a['kv_code'];shifts[:,:,0,0]=a['kv_shift']
        kv=v5.KV12(tensor(values),tensor(codes),tensor(shifts))
        code=_numpy(v5._pv_s24(tensor(a['probability_u16'][:,None,None,:]),kv,1,audit))[:,0,0,0]
        # Capture pre-clamp from the same active primitive, separate from ref.
        product=tensor(a['probability_u16']*a['value_s12']*a['kv_code'])
        shift=tensor(np.where(a['kv_code']!=0,a['kv_shift']-8,0))
        pre=_numpy(v5._round_shift_away(torch.sum(product>>shift,dim=-1),8))
        return dict(code=code,pre_clip_code=pre,saturation_mask=pre!=code,source_identity=_identity())
    if node=='swiglu':
        code=_numpy(v5._swiglu_s32(tensor(a['gate_s24']),tensor(a['up_s24']),tensor(a['lut_s24']),audit))
        return dict(code=code,source_identity=_identity())
    if node in ('host','host_fp32'):
        # Active V5MLP Host boundary is int32 -> float32 /2^16.
        code=_numpy(tensor(a['raw_s32']).to(torch.float32).to(torch.int64))
        return dict(code=code,source_identity=_identity())
    raise ValueError('unknown current node '+str(node))
