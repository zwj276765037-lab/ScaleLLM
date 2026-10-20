#!/usr/bin/env python3
"""Bounded GPU1 Driver-API byte retention probe; no model or driver changes."""
from __future__ import annotations
import argparse
import ctypes
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
import numpy as np

GPU='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533'
CHUNK=256*(1<<20)
WINDOW=1*(1<<20)


def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value)+'\n')
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            data=f.read(16*(1<<20))
            if not data:break
            digest.update(data)
    return digest.hexdigest()
def mismatch(observed,expected):
    count=0;offsets=[];cap=65536
    for start in range(0,len(observed),WINDOW):
        actual=observed[start:start+WINDOW]
        want=expected if np.isscalar(expected) else expected[start:start+WINDOW]
        bad=actual!=want
        count+=int(np.count_nonzero(bad))
        if len(offsets)<cap:
            local=np.flatnonzero(bad)[:cap-len(offsets)]
            offsets.extend((local+start).tolist())
    return count,np.asarray(offsets,dtype=np.int64)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--cpu-check',action='store_true');args=parser.parse_args()
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.cpu_check:
        actual=np.asarray([0,0,7,0,9],dtype=np.uint8)
        n,ids=mismatch(actual,0)
        if n!=2 or ids.tolist()!=[2,4]:raise RuntimeError('CPU mismatch positive control failed')
        n,ids=mismatch(actual,actual.copy())
        if n!=0 or ids.size:raise RuntimeError('CPU mismatch negative control failed')
        write(out/'cpu_controls.json',dict(passed=True,positive_bad_count=2,positive_offsets=[2,4],negative_bad_count=0))
        return 0
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU:raise RuntimeError('Requires only the exact authorized GPU1 UUID')
    state=dict(schema='r012_gpu1_memory_probe_v1',started_at=now(),pid=os.getpid(),command=sys.argv,
        gpu_uuid_requested=GPU,cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
        simultaneous_allocations=64,chunk_bytes=CHUNK,resident_data_bytes=64*CHUNK,host_buffer_budget_bytes=1<<30,
        host_compare_window_bytes=WINDOW,planned_patterns=['device_memset_00','device_memset_ff','device_memset_55','device_memset_aa','h2d_incrementing'],
        reads_per_chunk=2,source_sha256=sha(__file__),allocations=[],historical_boundary='Covers allocation working-set offsets11.5..12.75GiB, not proven identical physical pages',
        no_model=True,no_driver_reset_or_maintenance=True)
    cuda=None;ctx=None;ptrs=[];funcs={};bad_found=False;failure=None;started=time.monotonic()
    try:
        cuda=ctypes.CDLL('libcuda.so.1');int_t=ctypes.c_int;size_t=ctypes.c_size_t;ptr_t=ctypes.c_uint64
        def bind(name,args):
            function=getattr(cuda,name);function.argtypes=args;function.restype=int_t;return function
        specs={'cuInit':[ctypes.c_uint],'cuDeviceGetCount':[ctypes.POINTER(int_t)],'cuDeviceGet':[ctypes.POINTER(int_t),int_t],
            'cuDeviceGetName':[ctypes.c_void_p,int_t,int_t],'cuDeviceGetUuid_v2':[ctypes.c_void_p,int_t],
            'cuDriverGetVersion':[ctypes.POINTER(int_t)],'cuCtxCreate_v2':[ctypes.POINTER(ctypes.c_void_p),ctypes.c_uint,int_t],
            'cuCtxDestroy_v2':[ctypes.c_void_p],'cuCtxSynchronize':[],'cuMemGetInfo_v2':[ctypes.POINTER(size_t),ctypes.POINTER(size_t)],
            'cuMemAlloc_v2':[ctypes.POINTER(ptr_t),size_t],'cuMemFree_v2':[ptr_t],
            'cuMemcpyHtoD_v2':[ptr_t,ctypes.c_void_p,size_t],'cuMemcpyDtoH_v2':[ctypes.c_void_p,ptr_t,size_t],
            'cuMemsetD8_v2':[ptr_t,ctypes.c_ubyte,size_t]}
        funcs={name:bind(name,signature) for name,signature in specs.items()}
        def call(name,*values):
            code=funcs[name](*values)
            if code:raise RuntimeError(f'{name} CUDA error{code}')
        def mem():
            free=size_t();total=size_t();call('cuMemGetInfo_v2',ctypes.byref(free),ctypes.byref(total))
            return dict(free_bytes=free.value,total_bytes=total.value)
        call('cuInit',0);count=int_t();call('cuDeviceGetCount',ctypes.byref(count))
        if count.value!=1:raise RuntimeError('Expected exactly one visible device')
        dev=int_t();call('cuDeviceGet',ctypes.byref(dev),0)
        raw=(ctypes.c_ubyte*16)();call('cuDeviceGetUuid_v2',raw,dev);u=bytes(raw).hex()
        actual='GPU-'+u[:8]+'-'+u[8:12]+'-'+u[12:16]+'-'+u[16:20]+'-'+u[20:]
        if actual!=GPU:raise RuntimeError('Actual CUDA UUID differs:'+actual)
        name=ctypes.create_string_buffer(256);call('cuDeviceGetName',name,256,dev)
        version=int_t();call('cuDriverGetVersion',ctypes.byref(version))
        ctx=ctypes.c_void_p();call('cuCtxCreate_v2',ctypes.byref(ctx),0,dev)
        maps=[x for x in Path('/proc/self/maps').read_text().splitlines() if 'libcuda.so' in x]
        libraries=sorted({x.split()[-1] for x in maps if x.split()[-1].startswith('/')})
        state.update(gpu_uuid_actual=actual,gpu_name=name.value.decode(),cuda_driver_api_version=version.value,
            kernel_driver=Path('/proc/driver/nvidia/version').read_text(),mapped_cuda_libraries=[dict(path=p,sha256=sha(p)) for p in libraries],
            memory_before=mem())
        for index in range(64):
            if mem()['free_bytes']-CHUNK<8*(1<<30):raise RuntimeError('GPU8GiB free reserve would be violated')
            pointer=ptr_t();call('cuMemAlloc_v2',ctypes.byref(pointer),CHUNK);ptrs.append(pointer.value)
            state['allocations'].append(dict(index=index,ptr=pointer.value,ptr_hex=hex(pointer.value),bytes=CHUNK,working_set_offset_bytes=index*CHUNK))
        state['memory_after_all64_allocated']=mem();state['all16gib_simultaneously_resident']=True
        write(out/'allocation_manifest.json',state)
        observed=np.empty(CHUNK,dtype=np.uint8);expected=np.empty(CHUNK,dtype=np.uint8)
        # Two256MiB host arrays plus at most small comparison/coordinate windows.
        state['maximum_host_data_array_bytes']=observed.nbytes+expected.nbytes+WINDOW*10
        patterns=[('device_memset_00',0),('device_memset_ff',255),('device_memset_55',85),('device_memset_aa',170),('h2d_incrementing',None)]
        ramp=np.tile(np.arange(256,dtype=np.uint8),WINDOW//256)
        for label,value in patterns:
            append(out/'stages.jsonl',dict(at=now(),stage='pattern_started',pattern=label,live_resident_bytes=64*CHUNK))
            for index,pointer in enumerate(ptrs):
                if value is None:
                    for start in range(0,CHUNK,WINDOW):np.add(ramp,np.uint8((17*index)%256),out=expected[start:start+WINDOW])
                    call('cuMemcpyHtoD_v2',pointer,expected.ctypes.data,CHUNK)
                else:call('cuMemsetD8_v2',pointer,value,CHUNK)
            call('cuCtxSynchronize')
            reads=0
            for index,pointer in enumerate(ptrs):
                if value is None:
                    for start in range(0,CHUNK,WINDOW):np.add(ramp,np.uint8((17*index)%256),out=expected[start:start+WINDOW])
                    want=expected
                else:want=value
                for repeat in range(2):
                    call('cuMemcpyDtoH_v2',observed.ctypes.data,pointer,CHUNK)
                    countbad,ids=mismatch(observed,want)
                    record=dict(at=now(),pattern=label,allocation_index=index,repeat=repeat,ptr=pointer,
                        bytes_checked=CHUNK,bad_bytes=countbad,exact=countbad==0)
                    append(out/'byte_checks.jsonl',record);reads+=1
                    if countbad:
                        desired=np.full(len(ids),value,dtype=np.uint8) if value is not None else expected[ids]
                        rawpath=out/'first_byte_mismatch.npz'
                        np.savez_compressed(rawpath,byte_offsets=ids,expected=desired,observed=observed[ids],cuda_virtual_addresses=ids.astype(np.uint64)+pointer)
                        write(out/'first_byte_mismatch.json',dict(**record,first_byte_offset=int(ids[0]),
                            first_cuda_virtual_address=hex(pointer+int(ids[0])),first_expected=int(desired[0]),first_observed=int(observed[ids[0]]),
                            captured_coordinates=len(ids),coordinates_complete=countbad<=len(ids),raw_file=rawpath.name,raw_sha256=sha(rawpath),
                            observed_chunk_sha256=hashlib.sha256(observed).hexdigest(),immediately_stopping_remaining_patterns_and_model=True))
                        bad_found=True;raise RuntimeError('Raw CUDA byte mismatch; model is disallowed')
            append(out/'stages.jsonl',dict(at=now(),stage='pattern_passed',pattern=label,reads=reads,bytes_checked=reads*CHUNK))
        del observed,expected,ramp
        state['all_memory_patterns_passed']=True
    except BaseException as error:
        failure=dict(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:
        if funcs and ptrs:state['allocation_free_codes']=[int(funcs['cuMemFree_v2'](pointer)) for pointer in reversed(ptrs)]
        if funcs and ctx is not None:state['context_destroy_code']=int(funcs['cuCtxDestroy_v2'](ctx))
        state['raw_cleanup_at']=now()
    if failure is None and (any(state.get('allocation_free_codes',[])) or state.get('context_destroy_code',0)!=0):
        failure=dict(error_type='CleanupError',error='Raw CUDA allocation/context cleanup returned nonzero')
    if failure is None:
        try:
            import torch
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            torch.backends.cuda.matmul.allow_tf32=False;torch.set_float32_matmul_precision('highest')
            a=np.arange(32*32,dtype=np.int64).reshape(32,32)%9-4
            b=np.arange(32*32,dtype=np.int64).reshape(32,32)%7-3
            expected=a@b
            ag=torch.from_numpy(a).to('cuda:0');bg=torch.from_numpy(b).to('cuda:0')
            integer=(ag[:,:,None]*bg[None,:,:]).sum(dim=1).cpu().numpy()
            fp=(ag.to(torch.float32)@bg.to(torch.float32)).cpu().numpy()
            tests=dict(integer_exact=bool(np.array_equal(integer,expected)),fp32_exact=bool(np.array_equal(fp,expected.astype(np.float32))),
                integer_bad_elements=int(np.count_nonzero(integer!=expected)),fp32_bad_elements=int(np.count_nonzero(fp!=expected)),
                fp32_max_abs=float(np.max(np.abs(fp-expected))),expected_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
                scope='small independent integer and exact-representable FP32 known-answer controls after raw16GiB memory test')
            write(out/'compute_controls.json',tests)
            if not tests['integer_exact'] or not tests['fp32_exact']:raise RuntimeError('Known-answer compute control failed')
            del ag,bg;torch.cuda.empty_cache();torch.cuda.synchronize()
            state['compute_controls_passed']=True
        except BaseException as error:failure=dict(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    state.update(ended_at=now(),wall_seconds=time.monotonic()-started,execution_state='completed' if failure is None else 'failed',
        passed=failure is None,byte_mismatch_found=bad_found,failure=failure,
        interpretation='Finite16GiB memory-region and small-compute qualification only; no permanent reliability or physical-page coverage claim')
    write(out/'result.json',state)
    return 0 if failure is None else 1

if __name__=='__main__':raise SystemExit(main())
