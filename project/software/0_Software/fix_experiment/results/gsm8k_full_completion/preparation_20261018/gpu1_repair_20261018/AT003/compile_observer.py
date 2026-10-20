import ctypes,hashlib,json,os,sys,datetime
from pathlib import Path
p=Path(__file__).resolve().parent
lib=Path('/home/user/anaconda3/envs/zhouwenjun/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib/libnvrtc.so.12')
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
nv=ctypes.CDLL(str(lib));prog=ctypes.c_void_p()
def call(name,args,*vals):
 f=getattr(nv,name);f.argtypes=args;f.restype=ctypes.c_int;rc=f(*vals)
 if rc:raise RuntimeError(name+': '+str(rc))
vp=ctypes.c_void_p;sz=ctypes.c_size_t;charp=ctypes.c_char_p
call('nvrtcCreateProgram',[ctypes.POINTER(vp),charp,charp,ctypes.c_int,vp,vp],ctypes.byref(prog),(p/'observer.cu').read_bytes(),b'observer.cu',0,None,None)
options=[b'--gpu-architecture=sm_86',b'--std=c++11',b'--fmad=false'];arr=(charp*len(options))(*options)
f=nv.nvrtcCompileProgram;f.argtypes=[vp,ctypes.c_int,ctypes.POINTER(charp)];f.restype=ctypes.c_int;rc=f(prog,len(options),arr)
logsize=sz();call('nvrtcGetProgramLogSize',[vp,ctypes.POINTER(sz)],prog,ctypes.byref(logsize));log=ctypes.create_string_buffer(logsize.value);call('nvrtcGetProgramLog',[vp,vp],prog,log);(p/'compiler.log').write_bytes(log.raw)
if rc:raise RuntimeError('nvrtcCompileProgram '+str(rc)+': '+log.value.decode())
size=sz();call('nvrtcGetCUBINSize',[vp,ctypes.POINTER(sz)],prog,ctypes.byref(size));buf=ctypes.create_string_buffer(size.value);call('nvrtcGetCUBIN',[vp,vp],prog,buf);(p/'observer.cubin').write_bytes(buf.raw)
a=ctypes.c_int();b=ctypes.c_int();call('nvrtcVersion',[ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)],ctypes.byref(a),ctypes.byref(b));call('nvrtcDestroyProgram',[ctypes.POINTER(vp)],ctypes.byref(prog))
r={'schema':'scalellm_gpu_byte_observer_compile_v1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'CPU_only':True,'cpu_affinity':sorted(os.sched_getaffinity(0)),'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'nvrtc_version':[a.value,b.value],'nvrtc_path':str(lib),'nvrtc_sha256':sha(lib),'kernel_source_sha256':sha(p/'observer.cu'),'compiler_script_sha256':sha(__file__),'cubin_sha256':sha(p/'observer.cubin'),'cubin_size':size.value,'target':'sm_86','options':[x.decode()for x in options],'compiler_return_code':rc,'cuda_driver_initialized':False};(p/'compile_receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
