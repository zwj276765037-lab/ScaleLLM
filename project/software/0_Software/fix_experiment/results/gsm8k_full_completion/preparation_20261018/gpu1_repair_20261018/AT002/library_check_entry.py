"""Verify process-local CUDA driver identity before initializing any device."""
import ctypes,datetime,hashlib,json,os,runpy,sys
from pathlib import Path
out=Path(__file__).resolve().parent
libdir=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/nvml_local_recovery_20261018/cuda_lib')
lib=(libdir/'libcuda.so.1').resolve()
expected='3a3cf81c03a39008b3da4320bbc2cc8194dcfe91e8eef7c05dfc46febe2d1aac'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert os.environ.get('LD_LIBRARY_PATH')==str(libdir)
assert sha(lib)==expected
handle=ctypes.CDLL('libcuda.so.1')
maps=Path('/proc/self/maps').read_text();lines=[r for r in maps.splitlines()if 'libcuda.so' in r];paths=sorted({str(Path(r.split()[-1]).resolve())for r in lines})
record={'schema':'scalellm_actual_cuda_library_capture_v1','captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'worker_pid':os.getpid(),'bootstrap_source_sha256':sha(__file__),'LD_LIBRARY_PATH':os.environ.get('LD_LIBRARY_PATH'),'expected_path':str(lib),'expected_sha256':expected,'cuda_maps_lines':lines,'mapped_libraries':[{'path':r,'sha256':sha(r),'size_bytes':Path(r).stat().st_size}for r in paths],'kernel_driver_version':Path('/proc/driver/nvidia/version').read_text(),'scope':'Process-local library selection only, before CUDA init. No system modification.'}
record['actual_identity_verified']=len(paths)==1 and paths[0]==str(lib) and record['mapped_libraries'][0]['sha256']==expected
(out/'actual_cuda_library.json').write_text(json.dumps(record,indent=2)+'\n')
assert record['actual_identity_verified'],'actual libcuda path or SHA mismatch'
source=out/'source_snapshot.py';sys.argv=[str(source),'--output',str(out),'--order','forward','--total-gib','20'];runpy.run_path(str(source),run_name='__main__')
