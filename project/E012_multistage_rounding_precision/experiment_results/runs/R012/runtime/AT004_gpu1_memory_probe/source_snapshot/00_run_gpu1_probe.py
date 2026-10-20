#!/usr/bin/env python3
"""Owned300s supervisor for the user-authorized GPU1 memory/compute probe."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import psutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[5]
sys.path.insert(0,str(HERE))
from supervise_v2 import gpu_free,gpu_processes,group_members,stop_owned,file_id
GPU='GPU-d87ce710-76bf-872d-9739-f0d7c9b52533'
def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value)+'\n')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--admission',type=Path,required=True);args=parser.parse_args()
    directory=args.output_dir.resolve();directory.mkdir(parents=True,exist_ok=True)
    worker=directory/'probe';worker.mkdir()
    source_paths=[Path(__file__),HERE/'gpu1_memory_probe.py',HERE/'supervise_v2.py']
    sources=[file_id(p) for p in source_paths];admission=file_id(args.admission)
    snapshot=directory/'source_snapshot';snapshot.mkdir()
    for i,p in enumerate(source_paths):shutil.copyfile(p,snapshot/f'{i:02d}_{p.name}')
    write(directory/'source_manifest.json',dict(source=sources,admission=admission))
    reason=None;proc=None;group=None;code=None
    def cancel(_signal,_frame):
        nonlocal reason
        reason=reason or 'supervisor_received_signal'
    signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
    before=dict(at=now(),gpu_uuid=GPU,free_gpu_bytes=gpu_free(GPU),gpu_processes=gpu_processes(GPU),
                available_ram_bytes=psutil.virtual_memory().available)
    write(directory/'nvidia_before.json',before)
    if before['gpu_processes'] or before['free_gpu_bytes']<30*(1<<30) or before['available_ram_bytes']<32*(1<<30):
        write(directory/'external_wait_receipt.json',dict(native_exit_code=None,worker_launched=False,stop_reason='GPU1/RAM admission denied',worker_reaped=False))
        return 1
    with Path('/tmp/scalellm_r012_'+GPU+'.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        command=[sys.executable,'-B',str(HERE/'gpu1_memory_probe.py'),'--output-dir',str(worker)]
        env={**os.environ,'CUDA_VISIBLE_DEVICES':GPU,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'}
        started=time.monotonic()
        with (directory/'worker.stdout.log').open('xb') as log:
            proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            group=os.getpgid(proc.pid)
            write(directory/'actual_launch.json',dict(at=now(),pid=proc.pid,pgid=group,create_time=psutil.Process(proc.pid).create_time(),
                supervisor_pid=os.getpid(),command=command,cuda_visible_devices=GPU,budget=dict(seconds=300,gpu_gib=24,rss_gib=8,host_data_gib=1,resident_data_gib=16)))
            while proc.poll() is None:
                try:
                    p=psutil.Process(proc.pid);rss=p.memory_info().rss+sum(c.memory_info().rss for c in p.children(recursive=True) if c.is_running())
                    owned=group_members(group);gpu=gpu_processes(GPU);external=[p for p in gpu if p['pid'] not in owned]
                    used=sum(p['used_bytes'] for p in gpu if p['pid'] in owned)
                    sample=dict(at=now(),elapsed_seconds=time.monotonic()-started,rss_bytes=rss,gpu_owned_bytes=used,gpu_free_bytes=gpu_free(GPU),
                                ram_available_bytes=psutil.virtual_memory().available,external_gpu_processes=external)
                    append(directory/'resources.jsonl',sample)
                    if external:reason=reason or 'external_gpu_process_present'
                    if sample['elapsed_seconds']>300:reason=reason or '300s_probe_limit'
                    if rss>8*(1<<30) or used>24*(1<<30):reason=reason or 'resource_limit'
                    if sample['gpu_free_bytes']<8*(1<<30) or sample['ram_available_bytes']<32*(1<<30):reason=reason or 'minimum_free_reserve'
                except psutil.NoSuchProcess:pass
                except Exception as error:reason=reason or 'monitor_error:'+type(error).__name__+':'+str(error)
                if reason:stop_owned(proc,group);break
                time.sleep(2)
            code=proc.wait()
        survivors=group_members(group)
        if survivors:
            reason=reason or 'owned_group_survivors'
            os.killpg(group,signal.SIGTERM)
            deadline=time.monotonic()+10
            while group_members(group) and time.monotonic()<deadline:time.sleep(.2)
            if group_members(group):os.killpg(group,signal.SIGKILL)
            survivors=group_members(group)
        unchanged=sources==[file_id(p) for p in source_paths] and admission==file_id(args.admission)
        try:after=dict(at=now(),gpu_uuid=GPU,free_gpu_bytes=gpu_free(GPU),gpu_processes=gpu_processes(GPU))
        except Exception as error:after=dict(at=now(),device_query_error=str(error))
        write(directory/'nvidia_after.json',after)
        result=json.loads((worker/'result.json').read_text()) if (worker/'result.json').exists() else None
        receipt=dict(at=now(),native_exit_code=code,worker_launched=True,worker_reaped=True,pid=proc.pid,
            worker_proc_absent=not Path(f'/proc/{proc.pid}').exists(),stop_reason=reason,surviving_owned_group_pids=survivors,
            source_and_admission_unchanged=unchanged,wall_seconds=time.monotonic()-started,probe_passed=result is not None and result.get('passed',False),
            no_model_launched=True,gpu_uuid=GPU)
        write(directory/'external_wait_receipt.json',receipt)
        return 0 if code==0 and reason is None and not survivors and unchanged and receipt['probe_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
