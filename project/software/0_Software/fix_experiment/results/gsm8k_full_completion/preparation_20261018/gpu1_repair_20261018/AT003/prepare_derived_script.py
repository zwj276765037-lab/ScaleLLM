from pathlib import Path
p=Path(__file__).resolve().parent
source=(p.parent/'AT001/source_snapshot.py').read_text()
source=source.replace('Finite raw CUDA Driver API byte-preservation probe; no torch/transformers.','Finite GPU-internal native CUDA byte observer plus full CPU readback; no torch/transformers.')
source=source.replace("'schema':'scalellm_gpu1_raw_cuda_byte_probe_v1'","'schema':'scalellm_gpu1_gpu_internal_byte_observer_v1'")
source=source.replace("patterns=[('h2d','00',0),('h2d','ff',255),('h2d','55',85),('h2d','aa',170),('h2d','ramp',None),('device_memset','00',0),('device_memset','ff',255),('device_memset','55',85),('device_memset','aa',170)]","patterns=[('device_memset','00',0),('device_memset','ff',255)]")
anchor="  patterns=[('device_memset','00',0),('device_memset','ff',255)]"
new='''  # Load CPU-compiled native cubin, avoiding PTX JIT helper/library selection.
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
  patterns=[('device_memset','00',0),('device_memset','ff',255)]'''
assert source.count(anchor)==1;source=source.replace(anchor,new)
source=source.replace("     checkreserve();call('cuCtxSynchronize');call('cuMemcpyDtoH',observed.ctypes.data,ptrs[index],chunk)","     device_observer=observe(index,value,repeat)\n     checkreserve();call('cuCtxSynchronize');call('cuMemcpyDtoH',observed.ctypes.data,ptrs[index],chunk)")
source=source.replace("'exact_cpu_expected':countbad==0}","'exact_cpu_expected':countbad==0,'gpu_internal_observer':device_observer,'gpu_cpu_mismatch_counts_equal':device_observer['mismatch_byte_count']==countbad}")
(p/'source_snapshot.py').write_text(source)
(p/'library_check_entry.py').write_text((p.parent/'AT002/library_check_entry.py').read_text())
(p/'launch.py').write_text((p.parent/'AT002/launch.py').read_text())
