"""Vector int64 exact arithmetic; independent of all production round helpers."""
from __future__ import annotations
import numpy as np
from .policy import PROFILES


def binary_sum(numerator, shift):
    """Exact last-axis sum in quotient/nonnegative-remainder form."""
    n, k = np.broadcast_arrays(numerator.astype(np.int64), shift.astype(np.int64))
    right, left = np.maximum(k, 0), np.maximum(-k, 0)
    quotient = (n >> right) << left
    remainder = np.where(k > 0, n - ((n >> right) << right), 0)
    maximum = np.max(right, axis=-1)
    residual = np.sum(remainder << (maximum[..., None] - right), axis=-1, dtype=np.int64)
    denominator = np.left_shift(np.int64(1), maximum)
    whole = np.sum(quotient, axis=-1, dtype=np.int64) + residual // denominator
    return whole, residual % denominator, denominator


def round_away(q, r, d):
    return q + np.where(q >= 0, 2*r >= d, 2*r > d).astype(np.int64)


def ratio(numerator, denominator):
    numerator, denominator = np.broadcast_arrays(numerator, denominator)
    return numerator // denominator, numerator % denominator, denominator


def exact_record(q, r, d, bits):
    q, r, d = np.broadcast_arrays(q, r, d)
    return dict(quotient_floor=q.astype(np.int64), remainder=r.astype(np.int64),
                denominator=d.astype(np.int64), fractional_bits=int(bits))


def _finish(q, r, d, bits=16, width=None, floor=False):
    pre = q.copy() if floor else round_away(q,r,d)
    code = pre.copy()
    saturation = np.zeros(code.shape, dtype=bool)
    if width is not None:
        code = np.clip(pre, -(1 << (width-1)), (1 << (width-1))-1)
        saturation = pre != code
    return dict(code=code, pre_clip_code=pre, exact=exact_record(q,r,d,bits), saturation_mask=saturation)


def _bounds(result, numerator, denominator, pair_numerator=None, pair_denominator=None):
    shape=result['code'].shape
    result['bound_numerator']=np.broadcast_to(np.asarray(numerator,dtype=np.int64),shape).copy()
    result['bound_denominator']=np.broadcast_to(np.asarray(denominator,dtype=np.int64),shape).copy()
    result['reference_bound_numerator']=np.broadcast_to(np.asarray(numerator if pair_numerator is None else pair_numerator,dtype=np.int64),shape).copy()
    result['reference_bound_denominator']=np.broadcast_to(np.asarray(denominator if pair_denominator is None else pair_denominator,dtype=np.int64),shape).copy()
    return result


def _softmax_terms(a, interpolation_round=False):
    score, valid, lut=a['score_q14'],a['valid_mask'],a['lut_u17']
    row_has=np.any(valid,axis=-1,keepdims=True)
    maximum=np.max(np.where(valid,score,-(1<<19)),axis=-1,keepdims=True)
    magnitude=-np.clip(score-maximum,-(16<<14),0)
    index, fraction=magnitude//1024,magnitude%1024
    high,low=lut[index],lut[np.minimum(index+1,256)]
    if interpolation_round:
        # Production rounds the subtracted interpolation, not E itself.
        exponent=(high-((high-low)*fraction+512)//1024)*1024
    else:
        exponent=high*1024-(high-low)*fraction
    exponent=np.where(valid,exponent,0)
    total=np.sum(exponent,axis=-1,keepdims=True,dtype=np.int64)
    return exponent,np.where(row_has,total,np.int64(1<<26)),row_has


def selected_softmax_code(a, policy):
    exponent,total,has=_softmax_terms(a,policy.softmax_interpolation_round)
    if policy.softmax_reciprocal_round:
        inv=((1<<42)+total//2)//total
        n,d=exponent*inv,np.int64(1<<26)
    else:
        n,d=exponent*np.int64(65536),total
    q,r,d=ratio(n,d)
    return np.where(has,np.minimum(q+(2*r>=d),65535),0).astype(np.int64)


def evaluate_reference(node,a,config):
    if node=='linear':
        spec=PROFILES[config['profile']]
        n=a['dot']*a['act_code']*a['weight_code']
        active=(a['act_code']!=0)&(a['weight_code']!=0)
        k=np.where(active,a['act_shift']+a['weight_shift']-16,0)
        q,r,d=binary_sum(n,k)
        result=_finish(q,r,d,width=spec['output_width'])
        g=np.sum((a['act_code']!=0)&(a['weight_code']!=0)&(k>8),axis=-1,dtype=np.int64)
        result['g_right']=g
        return _bounds(result,g+128,256,g+256,256)
    if node=='rope':
        x,y=a['raw_pair'][:,0],a['raw_pair'][:,1]
        c,s=a['cos_q16'],a['sin_q16']
        n=np.stack((x*c-y*s,x*s+y*c),axis=-1)
        q,r,d=ratio(n,np.int64(65536))
        return _bounds(_finish(q,r,d,width=24),1,1,3,2)
    if node=='qk':
        active=a['kv_code']!=0
        n=a['dot']*a['kv_code']*np.int64(5793)
        k=np.where(active,a['kv_shift']+18,0)
        q,r,d=binary_sum(n,k)
        raw_exact=exact_record(q,r,d,14)
        low,high=-(16<<14),16<<14
        below=(q<low)
        above=(q>high)|((q==high)&(r!=0))
        q=np.clip(q,low,high)
        r=np.where(below|above,0,r)
        result=_finish(q,r,d,bits=14,floor=True)
        result['exact_unclipped']=raw_exact
        result['clip_mask']=below|above
        result.pop('saturation_mask')
        return _bounds(result,4,1,3,1)
    if node=='pv':
        n=a['probability_u16']*a['value_s12']*a['kv_code']
        k=np.where(a['kv_code']!=0,a['kv_shift'],0)
        q,r,d=binary_sum(n,k)
        g=np.sum((a['kv_code']!=0)&(a['kv_shift']>8),axis=-1,dtype=np.int64)
        result=_finish(q,r,d,width=24)
        result['g_right']=g
        return _bounds(result,g+128,256,g+256,256)
    if node=='softmax':
        n,total,has=_softmax_terms(a,False)
        q,r,d=ratio(n*np.int64(65536),total)
        result=_finish(q,r,d)
        code=np.minimum(result['code'],65535)
        result['clip_mask']=result['code']!=code
        result['code']=np.where(has,code,0)
        result['software_padding_mask']=np.broadcast_to(~has,code.shape).copy()
        # Coarse consequence of the v3 deterministic bound: |eps_i|<=1/2,
        # S,S'>=65536, E_i,E_i'<=65536, and endpoint-cap distance<=1 LSB.
        # Bnorm<=(K+1)/2, Brecip<=1/2, final round<=1/2.
        keys=a['score_q14'].shape[1]
        return _bounds(result,keys+5,2,keys+4,2)
    if node=='swiglu':
        gate,up=a['gate_s24'],a['up_s24']
        address=np.clip((gate+(16<<16)+128)>>8,0,8192)
        silu=np.where(gate<=-(16<<16),0,np.where(gate>=(16<<16),gate,a['lut_s24'][address]))
        q,r,d=ratio(silu*up,np.int64(65536))
        result=_finish(q,r,d)
        result['overflow_mask']=(result['code']<-(1<<31))|(result['code']>(1<<31)-1)
        return _bounds(result,1,2,0,1)
    if node in ('host','host_fp32'):
        raw=a['raw_s32']
        result=dict(code=raw.astype(np.float32).astype(np.int64),exact=exact_record(raw,np.zeros(raw.shape,dtype=np.int64),np.ones(raw.shape,dtype=np.int64),16))
        return _bounds(result,0 if config.get('input_width',32)==24 else 64,1,0,1)
    raise ValueError('unknown reference node '+str(node))
