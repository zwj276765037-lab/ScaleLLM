"""Exact S32 Down: FP32 integer dot, original int64 scaling and shifts.

Each product/any partial sum is integer with abs<=255*8*32=65280<2**24.
CPU FP32 dot therefore has no rounding error. This does not use float scales
or apply a scale after the448-group sum. A row memo matches actual wire bytes.
"""
import hashlib
import threading
import time
import numpy as np
from host.scalellm_mlp_gu_only import _activation,HostDownFormatError


class DownContext:
    def __init__(self,weights):
        self.weights=weights
        self.source=tuple(weights.source_sha256)
        self.w=np.ascontiguousarray(weights.values.transpose(0,2,1),dtype=np.float32)
        self.codes=np.asarray(weights.codes,dtype=np.int64)
        self.shifts=np.asarray(weights.shifts,dtype=np.int64)
        for a in (self.w,self.codes,self.shifts):a.setflags(write=False)


def exact_down_rows(q,metadata,context,rows=None,*,column_block=256,group_block=64):
    centered,ac,ash=_activation(q,metadata)
    indices=np.asarray(tuple(range(16)) if rows is None else tuple(rows),dtype=np.intp)
    if indices.ndim!=1 or len(set(indices.tolist()))!=len(indices) or np.any(indices<0) or np.any(indices>=16):raise ValueError('Unique rows0..15 required')
    if type(column_block)is not int or type(group_block)is not int or not 1<=column_block<=4096 or not 1<=group_block<=448:raise ValueError('Invalid block shape')
    columns=context.weights.columns
    out=np.zeros((len(indices),columns),dtype=np.int64)
    if len(indices)==0:return out
    a=np.ascontiguousarray(centered[indices].transpose(1,0,2),dtype=np.float32)
    activation_code=ac[indices].T[...,None];activation_shift=ash[indices].T[...,None]
    for col in range(0,columns,column_block):
        end=min(columns,col+column_block);acc=np.zeros((len(indices),end-col),dtype=np.int64)
        for start in range(0,448,group_block):
            stop=min(448,start+group_block)
            dot=np.matmul(a[start:stop],context.w[start:stop,:,col:end])
            if not np.all(np.isfinite(dot)) or np.any(dot!=np.rint(dot)) or np.any(dot<-(1<<16)) or np.any(dot>=(1<<16)):raise HostDownFormatError('FP32 integer dot proof/range failed')
            dot=dot.astype(np.int64)
            acode=activation_code[start:stop];wcode=context.codes[start:stop,None,col:end]
            total=activation_shift[start:stop]+context.shifts[start:stop,None,col:end]
            live=(acode!=0)&(wcode!=0)
            if np.any(live&((total<12)|(total>44))):raise HostDownFormatError('Nonzero Down total shift outside12..44')
            raw=dot*acode*wcode
            if np.any(raw<-(1<<32)) or np.any(raw>=(1<<32)):raise HostDownFormatError('raw outsideS33')
            total=np.where(live,total,24)
            guard=np.left_shift(raw,np.maximum(24-total,0));guard=np.right_shift(guard,np.maximum(total-24,0))
            if np.any(guard<-(1<<44)) or np.any(guard>=(1<<44)):raise HostDownFormatError('guard outsideS45')
            acc+=guard.sum(axis=0,dtype=np.int64)
            if np.any(acc<-(1<<53)) or np.any(acc>=(1<<53)):raise HostDownFormatError('accumulator outsideS54')
        magnitude=(np.abs(acc)+128)>>8;rounded=np.where(acc<0,-magnitude,magnitude)
        out[:,col:end]=np.clip(rounded,-2147483648,2147483647)
    return out


def wire_row_hashes(payload):
    raw=np.frombuffer(payload,dtype=np.uint8)
    if raw.size!=1376256:raise ValueError('Full GU S24 output required')
    wire=raw.reshape(896,2,16,16,3)
    return [hashlib.sha256(wire[:,:,r].tobytes()).hexdigest() for r in range(16)]


class DownMemo:
    """Only reuses rows whose layer/weights/cohort/actual GU wire bytes match."""
    def __init__(self):self.rows={};self.lock=threading.RLock()
    def compute(self,layer,cohort,payload,q,metadata,context,allowed_reuse=()):
        started=time.perf_counter();hashes=wire_row_hashes(payload);out=np.empty((16,context.weights.columns),dtype=np.int64);reused=[];todo=[]
        allowed=set(allowed_reuse)
        for row in range(16):
            with self.lock:entry=self.rows.get((layer,cohort,row)) if row in allowed else None
            old=entry[2] if entry is not None and entry[:2]==(context.source,hashes[row]) else None
            if old is None:todo.append(row)
            else:out[row]=old;reused.append(row)
        if todo:out[todo]=exact_down_rows(q,metadata,context,todo)
        for row in range(16):
            # One prior generation per (layer,cohort,row), bounded to16MiB.
            value=np.asarray(out[row],dtype=np.int32).copy();value.setflags(write=False)
            with self.lock:self.rows[(layer,cohort,row)]=(context.source,hashes[row],value)
        return out,{'seconds':time.perf_counter()-started,'computed_rows':todo,'reused_rows':reused,'actual_gu_row_sha256':hashes,'dot':'CPU FP32 exact integer partial sums<2^24; all scale/guard/reduce int64'}
