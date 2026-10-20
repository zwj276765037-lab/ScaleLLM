#!/usr/bin/env python3
"""Finite GPU-internal native CUDA byte observer plus full CPU readback; no torch/transformers."""
import argparse,ctypes,fcntl,hashlib,json,os,platform,socket,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone

def now():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,obj):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--order',choices=['forward','reverse'],default='forward');p.add_argument('--total-gib',type=int,default=20);args=p.parse_args()
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 uuid='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533';root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');base=root/'project/software/0_Software/fix_experiment'
 state={'schema':'scalellm_gpu1_gpu_internal_byte_observer_v1','execution_state':'running','stage':'preflight','started_at':now(),'pid':os.getpid(),'ppid':os.getppid(),'hostname':socket.gethostname(),'platform':platform.platform(),'python':sys.executable,'python_version':sys.version,'source_file':str(Path(__file__).resolve()),'source_sha256':sha(__file__),'argv':sys.argv,'cwd':str(Path.cwd()),'cpu_affinity':sorted(os.sched_getaffinity(0)),'requested_gpu_uuid':uuid,'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'allocation_order':args.order,'total_gib_requested':args.total_gib,'libraries_imported':'ctypes CUDA Driver API, numpy CPU only; no torch or transformers','tests':[],'allocations':[],'scope':'Finite raw memory/copy diagnostic only; no model qualification, no hardware repair claim.'}
 lock=None;ctx=None;ptrs=[];cuda=None
 def save():atomic(out/'status.json',state)
 def available():return next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
 def reserve():
  n=available()
  if n<80*(1<<30):raise RuntimeError('host MemAvailable below 80GiB')
  return n
 save()
 try:
  if state['cpu_affinity']!=[18,19] or state['cuda_visible_devices']!=uuid:raise RuntimeError('GPU/CPU allocation mismatch')
  if args.total_gib not in [20]:raise RuntimeError('this version permits only finite20GiB scope')
  lockpath=base/'results/gsm8k_full_completion/resource_locks'/(uuid+'.lock');lock=lockpath.open('r+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  state.update(lock_path=str(lockpath),lock_acquired_at=now(),host_available_start_bytes=reserve());save()
  import numpy as np
  cuda=ctypes.CDLL('libcuda.so.1');int_t=ctypes.c_int;size_t=ctypes.c_size_t;ptr_t=ctypes.c_uint64
  def bind(name,args):
   fn=getattr(cuda,name);fn.argtypes=args;fn.restype=int_t;return fn
  funcs={'cuInit':bind('cuInit',[ctypes.c_uint]),'cuDeviceGetCount':bind('cuDeviceGetCount',[ctypes.POINTER(int_t)]),'cuDeviceGet':bind('cuDeviceGet',[ctypes.POINTER(int_t),int_t]),'cuDeviceGetName':bind('cuDeviceGetName',[ctypes.c_void_p,int_t,int_t]),'cuDeviceGetUuid':bind('cuDeviceGetUuid_v2',[ctypes.c_void_p,int_t]),'cuDriverGetVersion':bind('cuDriverGetVersion',[ctypes.POINTER(int_t)]),'cuCtxCreate':bind('cuCtxCreate_v2',[ctypes.POINTER(ctypes.c_void_p),ctypes.c_uint,int_t]),'cuCtxDestroy':bind('cuCtxDestroy_v2',[ctypes.c_void_p]),'cuCtxSynchronize':bind('cuCtxSynchronize',[]),'cuMemGetInfo':bind('cuMemGetInfo_v2',[ctypes.POINTER(size_t),ctypes.POINTER(size_t)]),'cuMemAlloc':bind('cuMemAlloc_v2',[ctypes.POINTER(ptr_t),size_t]),'cuMemFree':bind('cuMemFree_v2',[ptr_t]),'cuMemcpyHtoD':bind('cuMemcpyHtoD_v2',[ptr_t,ctypes.c_void_p,size_t]),'cuMemcpyDtoH':bind('cuMemcpyDtoH_v2',[ctypes.c_void_p,ptr_t,size_t]),'cuMemsetD8':bind('cuMemsetD8_v2',[ptr_t,ctypes.c_ubyte,size_t])}
  def call(name,*vals):
   rc=funcs[name](*vals)
   if rc:raise RuntimeError(f'{name} CUDA error {rc}')
  def gpu_mem():
   free=size_t();total=size_t();call('cuMemGetInfo',ctypes.byref(free),ctypes.byref(total));return {'free_bytes':free.value,'total_bytes':total.value}
  call('cuInit',0);count=int_t();call('cuDeviceGetCount',ctypes.byref(count))
  if count.value!=1:raise RuntimeError('expected exactly one visible CUDA device')
  dev=int_t();call('cuDeviceGet',ctypes.byref(dev),0);name=ctypes.create_string_buffer(256);call('cuDeviceGetName',name,256,dev)
  rawuuid=(ctypes.c_ubyte*16)();call('cuDeviceGetUuid',rawuuid,dev);u=bytes(rawuuid).hex();actual='GPU-'+u[:8]+'-'+u[8:12]+'-'+u[12:16]+'-'+u[16:20]+'-'+u[20:]
  if actual!=uuid:raise RuntimeError('actual CUDA device UUID mismatch: '+actual)
  version=int_t();call('cuDriverGetVersion',ctypes.byref(version));ctx=ctypes.c_void_p();call('cuCtxCreate',ctypes.byref(ctx),0,dev)
  state.update(gpu_uuid_actual=actual,gpu_name=name.value.decode(),cuda_driver_api_version=version.value,gpu_memory_start=gpu_mem(),driver_proc=Path('/proc/driver/nvidia/version').read_text(),numpy_version=np.__version__,stage='allocating');save()
  chunk=256*(1<<20);n=args.total_gib*4
  def checkreserve(nextbytes=0):
   m=gpu_mem()
   if m['free_bytes']-nextbytes<8*(1<<30):raise RuntimeError('GPU8GiB reserve would be violated')
   reserve();return m
  for index in range(n):
   checkreserve(chunk);ptr=ptr_t();call('cuMemAlloc',ctypes.byref(ptr),chunk);ptrs.append(ptr.value)
   state['allocations'].append({'allocation_index':index,'ptr':ptr.value,'ptr_hex':hex(ptr.value),'size_bytes':chunk,'shape':[chunk],'stride_bytes':[1],'allocation_working_set_offset_bytes':index*chunk,'cuda_api':'cuMemAlloc_v2'})
  state.update(stage='byte_pattern_tests',allocated_bytes=sum(x['size_bytes'] for x in state['allocations']),gpu_memory_after_allocations=gpu_mem());save()
  expected=np.empty(chunk,dtype=np.uint8);observed=np.empty(chunk,dtype=np.uint8);previous=np.empty(chunk,dtype=np.uint8);ramp=np.resize(np.arange(256,dtype=np.uint8),chunk)
  # Load CPU-compiled native cubin, avoiding PTX JIT helper/library selection.
  receipt=json.loads((out/'compile_receipt.json').read_text())
  if sha(out/'observer.cubin')!=receipt['cubin_sha256'] or sha(out/'observer.cu')!=receipt['kernel_source_sha256']:raise RuntimeError('kernel identity mismatch')
  funcs['cuModuleLoad']=bind('cuModuleLoad',[ctypes.POINTER(ctypes.c_void_p),ctypes.c_char_p])
  funcs['cuModuleGetFunction']=bind('cuModuleGetFunction',[ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.c_char_p])
  funcs['cuLaunchKernel']=bind('cuLaunchKernel',[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p])
  module=ctypes.c_void_p();call('cuModuleLoad',ctypes.byref(module),str(out/'observer.cubin').encode())
  countfn=ctypes.c_void_p();fetchfn=ctypes.c_void_p();call('cuModuleGetFunction',ctypes.byref(countfn),module,b'count_bytes');call('cuModuleGetFunction',ctypes.byref(fetchfn),module,b'fetch_first')
  counters=[]
  for j in range(2):
   checkreserve(40);counter=ptr_t();call('cuMemAlloc',ctypes.byref(counter),40);ptrs.append(counter.value);counters.append(counter.value)
  state['gpu_observer']={'compiled_cubin_sha256':receipt['cubin_sha256'],'kernel_source_sha256':receipt['kernel_source_sha256'],'compiler_receipt_sha256':sha(out/'compile_receipt.json'),'counter_ptrs':counters,'counter_size_bytes':40,'fields':['mismatch_byte_count','first_mismatch_byte_offset_or_uint64max','set_bit_byte_count','cleared_bit_byte_count','first_observed_byte_or_uint64max'],'actual_allocated_bytes':n*chunk+80,'self_tests':[]}
  def observe(index,value,counter_index):
   cp=counters[counter_index];initial=np.array([0,2**64-1,0,0,2**64-1],dtype=np.uint64);pre=np.empty(5,dtype=np.uint64)
   call('cuMemcpyHtoD',cp,initial.ctypes.data,40);call('cuMemcpyDtoH',pre.ctypes.data,cp,40)
   if not np.array_equal(initial,pre):raise RuntimeError('small counter precondition roundtrip mismatch')
   dataarg=ptr_t(ptrs[index]);sizearg=ctypes.c_uint64(chunk);valuearg=ctypes.c_uint32(value);outarg=ptr_t(cp)
   params=(ctypes.c_void_p*4)(ctypes.addressof(dataarg),ctypes.addressof(sizearg),ctypes.addressof(valuearg),ctypes.addressof(outarg))
   call('cuLaunchKernel',countfn,4096,1,1,256,1,1,0,None,params,None)
   fetchparams=(ctypes.c_void_p*2)(ctypes.addressof(dataarg),ctypes.addressof(outarg));call('cuLaunchKernel',fetchfn,1,1,1,1,1,1,0,None,fetchparams,None);call('cuCtxSynchronize')
   a=np.empty(5,dtype=np.uint64);b=np.empty(5,dtype=np.uint64);call('cuMemcpyDtoH',a.ctypes.data,cp,40);call('cuMemcpyDtoH',b.ctypes.data,cp,40)
   return {'counter_index':counter_index,'counter_ptr':cp,'small_result_words':a.tolist(),'small_result_repeated_words':b.tolist(),'small_result_reads_equal':bool(np.array_equal(a,b)),'mismatch_byte_count':int(a[0]),'first_mismatch_byte_offset':None if int(a[1])==2**64-1 else int(a[1]),'set_bit_byte_count':int(a[2]),'cleared_bit_byte_count':int(a[3]),'first_observed_byte':None if int(a[4])==2**64-1 else int(a[4]),'captured_at':now()}
  # Independent positive/negative controls before any diagnosis: inject a known byte.
  for value,flipped in [(0,255),(255,0)]:
   call('cuMemsetD8',ptrs[0],value,chunk);clean=observe(0,value,0)
   if clean['mismatch_byte_count']!=0 or not clean['small_result_reads_equal']:raise RuntimeError('observer clean control failed')
   inject=np.array([flipped],dtype=np.uint8);call('cuMemcpyHtoD',ptrs[0]+12345,inject.ctypes.data,1);bad=observe(0,value,1)
   expected_set=1 if value==0 else 0;expected_clear=1 if value==255 else 0
   if [bad['mismatch_byte_count'],bad['first_mismatch_byte_offset'],bad['first_observed_byte'],bad['set_bit_byte_count'],bad['cleared_bit_byte_count']]!=[1,12345,flipped,expected_set,expected_clear] or not bad['small_result_reads_equal']:raise RuntimeError('observer known-bad control failed')
   state['gpu_observer']['self_tests'].append({'expected_byte':value,'injected_byte':flipped,'injected_byte_offset':12345,'clean':clean,'injected':bad,'passed':True});save()
  patterns=[('device_memset','00',0),('device_memset','ff',255)]
  sequence=list(range(n)) if args.order=='forward' else list(reversed(range(n)))
  for route,label,value in patterns:
   test={'test_id':route+'_'+label,'route':route,'pattern':label,'started_at':now(),'reads':[],'write_sequence':sequence,'repeat_count_per_chunk':2,'cpu_expected':'constant byte value' if value is not None else '(byte_offset_in_chunk +17*allocation_index)mod256; independent numpy CPU construction'};state['tests'].append(test);save()
   for index in sequence:
    checkreserve()
    if value is None:np.add(ramp,np.uint8((17*index)%256),out=expected)
    else:expected.fill(value)
    if route=='h2d':call('cuMemcpyHtoD',ptrs[index],expected.ctypes.data,chunk)
    else:call('cuMemsetD8',ptrs[index],value,chunk)
   call('cuCtxSynchronize');test['writes_completed_at']=now();save()
   for index in sequence:
    if value is None:np.add(ramp,np.uint8((17*index)%256),out=expected)
    else:expected.fill(value)
    for repeat in range(2):
     device_observer=observe(index,value,repeat)
     checkreserve();call('cuCtxSynchronize');call('cuMemcpyDtoH',observed.ctypes.data,ptrs[index],chunk)
     bad=observed!=expected;countbad=int(np.count_nonzero(bad));row={'allocation_index':index,'repeat':repeat,'ptr':ptrs[index],'size_bytes':chunk,'captured_at':now(),'changed_bytes':countbad,'exact_cpu_expected':countbad==0,'gpu_internal_observer':device_observer,'gpu_cpu_mismatch_counts_equal':device_observer['mismatch_byte_count']==countbad}
     if repeat:row['changed_bytes_from_previous_read']=int(np.count_nonzero(observed!=previous))
     if countbad:
      coords=np.flatnonzero(bad);a=expected[coords];b=observed[coords];xor=np.bitwise_xor(a,b);row.update(first_32_byte_offsets=coords[:32].tolist(),last_32_byte_offsets=coords[-32:].tolist(),first_32_expected=a[:32].tolist(),first_32_observed=b[:32].tolist(),first_32_xor=xor[:32].tolist(),set_bit_bytes=int(np.count_nonzero(np.bitwise_and(np.bitwise_not(a),b))),cleared_bit_bytes=int(np.count_nonzero(np.bitwise_and(a,np.bitwise_not(b)))),xor_histogram={str(int(v)):int(c) for v,c in zip(*np.unique(xor,return_counts=True))},expected_sha256=hashlib.sha256(expected).hexdigest(),observed_sha256=hashlib.sha256(observed).hexdigest())
      cap=1000000;chosen=coords[:cap];name=f'{route}_{label}_chunk{index:03d}_read{repeat}_diff.npz';np.savez_compressed(out/name,byte_offsets=chosen,expected=expected[chosen],observed=observed[chosen],xor=np.bitwise_xor(expected[chosen],observed[chosen]));row.update(raw_diff_file=name,raw_diff_sha256=sha(out/name),raw_diff_coordinates_complete=countbad<=cap,raw_diff_coordinate_cap=cap)
      pages,counts=np.unique(coords//4096,return_counts=True);np.savez_compressed(out/f'{route}_{label}_chunk{index:03d}_read{repeat}_pages.npz',page_offset=pages,changed_byte_counts=counts)
      print(json.dumps({'event':'byte_mismatch','test':test['test_id'],'index':index,'repeat':repeat,'changed_bytes':countbad,'ptr':ptrs[index]}),flush=True)
     np.copyto(previous,observed);test['reads'].append(row);save()
   test.update(ended_at=now(),changed_bytes=sum(x['changed_bytes'] for x in test['reads']),failing_reads=sum(x['changed_bytes']>0 for x in test['reads']));save();print(json.dumps({'event':'test_complete','test':test['test_id'],'changed_bytes':test['changed_bytes'],'failing_reads':test['failing_reads']}),flush=True)
  state.update(execution_state='completed',stage='complete',ended_at=now(),verdict='raw CUDA byte preservation failed' if any(x['failing_reads'] for x in state['tests']) else 'bounded raw CUDA byte preservation passed',host_available_end_bytes=available(),gpu_memory_before_free=gpu_mem());save()
 except BaseException as exc:
  state.update(execution_state='failed',stage='exception',ended_at=now(),error=repr(exc),traceback=traceback.format_exc());save();raise
 finally:
  if cuda is not None and ptrs:
   freefn=cuda.cuMemFree_v2;freefn.argtypes=[ctypes.c_uint64];freefn.restype=ctypes.c_int
   state['allocation_free_return_codes']=[int(freefn(p)) for p in reversed(ptrs)]
  if ctx is not None:
   fn=cuda.cuCtxDestroy_v2;fn.argtypes=[ctypes.c_void_p];fn.restype=ctypes.c_int;state['context_destroy_return_code']=int(fn(ctx))
  if lock is not None:fcntl.flock(lock,fcntl.LOCK_UN);lock.close();state['lock_released_at']=now()
  state['cleanup_completed_at']=now();save()
if __name__=='__main__':main()
