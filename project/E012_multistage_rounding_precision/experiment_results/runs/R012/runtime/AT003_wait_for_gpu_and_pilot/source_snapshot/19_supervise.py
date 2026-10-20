#!/usr/bin/env python3
"""Admitted R012 pilot owner: bounded resource monitor and real wait receipt.

Only a Root-authorized invocation may launch this supervisor. It never stops
another process or uses GPU1. The worker has its own process group.
"""
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

GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[5]


def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value)+'\n')
def gpu_free():
    result=subprocess.run(['nvidia-smi','-i',GPU,'--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True,capture_output=True,check=True,timeout=10)
    return int(result.stdout.strip())*(1<<20)
def gpu_processes():
    result=subprocess.run(['nvidia-smi','-i',GPU,'--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],text=True,capture_output=True,check=True,timeout=10)
    rows=[]
    for line in result.stdout.splitlines():
        if line.strip():
            pid,used=line.split(',');rows.append(dict(pid=int(pid),used_bytes=int(used.strip())*(1<<20)))
    return rows

def group_members(group):
    members=[]
    for p in psutil.process_iter(['pid','status']):
        try:
            if os.getpgid(p.pid)==group and p.info['status']!=psutil.STATUS_ZOMBIE:members.append(p.pid)
        except (ProcessLookupError,PermissionError,psutil.NoSuchProcess):pass
    return members


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker-output',type=Path,required=True)
    parser.add_argument('--runtime-output',type=Path,required=True)
    parser.add_argument('--prompts',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=1800)
    parser.add_argument('--max-context',type=int,default=2048)
    parser.add_argument('--max-new-tokens',type=int,default=512)
    parser.add_argument('--prefill-chunk',type=int,default=128)
    parser.add_argument('--qualification-only',action='store_true')
    args=parser.parse_args()
    if not 1<=args.seconds<=1800:parser.error('Pilot budget must be 1..1800 seconds')
    runtime=args.runtime_output.resolve();runtime.mkdir(parents=True,exist_ok=True)
    worker_out=args.worker_output.resolve()
    if worker_out.exists() and any(worker_out.iterdir()):raise RuntimeError('New independent worker AT directory is required')
    lock_path=Path('/tmp/scalellm_r012_gpu0.lock')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=dict(at=now(),gpu_uuid=GPU,free_gpu_bytes=gpu_free(),gpu_processes=gpu_processes(),available_ram_bytes=psutil.virtual_memory().available)
        write(runtime/'resource_admission.json',before)
        if before['gpu_processes'] or before['free_gpu_bytes']<30*(1<<30) or before['available_ram_bytes']<32*(1<<30):
            raise RuntimeError('GPU/RAM admission denied; no processes were changed')
        sys.path.insert(0,str(HERE));import run_generation
        sources=run_generation.code_identities()+[run_generation.identity(Path(__file__))]
        snapshot=runtime/'source_snapshot';snapshot.mkdir()
        for i,item in enumerate(sources):
            source=Path(item['path']);target=snapshot/f'{i:02d}_{source.name}'
            shutil.copyfile(source,target)
            if hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Source changed while freezing')
        write(runtime/'source_manifest.json',dict(sources=sources))
        command=[sys.executable,'-B',str(HERE/'run_generation.py'),'--model-dir',str(args.model_dir.resolve()),'--prompts',str(args.prompts.resolve()),
                 '--output-dir',str(worker_out),'--max-context',str(args.max_context),'--max-new-tokens',str(args.max_new_tokens),
                 '--prefill-chunk',str(args.prefill_chunk),'--expected-gpu-uuid',GPU]
        if args.qualification_only:command.append('--qualification-only')
        env={**os.environ,'CUDA_VISIBLE_DEVICES':GPU,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'}
        budget=dict(seconds=args.seconds,cpu_threads=1,rss_bytes=8*(1<<30),gpu_bytes=24*(1<<30),min_gpu_free_bytes=8*(1<<30),min_ram_available_bytes=32*(1<<30),evidence_bytes=512*(1<<20))
        started=time.monotonic();reason=None;proc=None
        def requested_stop(_signal,_frame):
            nonlocal reason
            reason='supervisor_received_signal'
        signal.signal(signal.SIGTERM,requested_stop);signal.signal(signal.SIGINT,requested_stop)
        with (runtime/'worker.stdout.log').open('xb') as log:
            proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            group=os.getpgid(proc.pid)
            write(runtime/'actual_launch.json',dict(pid=proc.pid,pgid=group,starttime=psutil.Process(proc.pid).create_time(),
                supervisor_pid=os.getpid(),launched_at=now(),command=command,budget=budget,cuda_visible_devices=GPU))
            while proc.poll() is None:
                try:
                    process=psutil.Process(proc.pid)
                    rss=process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running())
                    gpu=gpu_processes();owned=group_members(group)
                    used=sum(p['used_bytes'] for p in gpu if p['pid'] in owned)
                    evidence=sum(p.stat().st_size for base in (runtime,worker_out) if base.exists() for p in base.rglob('*') if p.is_file())
                    sample=dict(at=now(),elapsed_seconds=time.monotonic()-started,rss_bytes=rss,gpu_owned_bytes=used,
                        gpu_free_bytes=gpu_free(),ram_available_bytes=psutil.virtual_memory().available,evidence_bytes=evidence,
                        worker_pid=proc.pid,owned_group_pids=owned)
                    append(runtime/'resources.jsonl',sample)
                    for field,limit in (('elapsed_seconds',budget['seconds']),('rss_bytes',budget['rss_bytes']),('gpu_owned_bytes',budget['gpu_bytes']),('evidence_bytes',budget['evidence_bytes'])):
                        if sample[field]>limit:reason=reason or 'budget_'+field
                    if sample['gpu_free_bytes']<budget['min_gpu_free_bytes']:reason=reason or 'minimum_gpu_free'
                    if sample['ram_available_bytes']<budget['min_ram_available_bytes']:reason=reason or 'minimum_ram_available'
                except psutil.NoSuchProcess:
                    pass
                except Exception as error:
                    reason=reason or 'resource_monitor_error:'+type(error).__name__+':'+str(error)
                if reason:
                    if proc.poll() is None:os.killpg(group,signal.SIGTERM)
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        if group_members(group):os.killpg(group,signal.SIGKILL)
                        proc.wait()
                    break
                time.sleep(2)
            code=proc.wait()
        survivors=group_members(group)
        if survivors:
            reason=reason or 'orphaned_owned_group_after_worker_exit'
            os.killpg(group,signal.SIGTERM)
            deadline=time.monotonic()+10
            while group_members(group) and time.monotonic()<deadline:time.sleep(.2)
            if group_members(group):os.killpg(group,signal.SIGKILL)
            survivors=group_members(group)
        unchanged=sources==run_generation.code_identities()+[run_generation.identity(Path(__file__))]
        try:
            final_gpu=dict(gpu_processes_after=gpu_processes(),free_gpu_bytes_after=gpu_free())
        except Exception as error:
            final_gpu=dict(final_device_query_error=type(error).__name__+':'+str(error))
        receipt=dict(ended_at=now(),native_exit_code=code,worker_reaped=True,pid=proc.pid,worker_proc_absent=not Path(f'/proc/{proc.pid}').exists(),
            stop_reason=reason,surviving_owned_group_pids=survivors,source_unchanged=unchanged,
            wall_seconds=time.monotonic()-started,**final_gpu)
        write(runtime/'external_wait_receipt.json',receipt)
        return 0 if code==0 and reason is None and not survivors and unchanged else 1

if __name__=='__main__':raise SystemExit(main())
