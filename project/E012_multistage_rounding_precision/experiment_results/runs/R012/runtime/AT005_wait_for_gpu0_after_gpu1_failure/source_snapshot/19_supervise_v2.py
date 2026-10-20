#!/usr/bin/env python3
"""R012 device-parameterized owned pilot supervisor, revision2.

User's latest GPU1 trial authorization supersedes the earlier GPU1 preference.
GPU selection is explicit; no driver/reset/maintenance or external PID control.
Input SHA is checked before and after; external GPU occupancy ends only our job.
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

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[5]
GPUS={'GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6','GPU-d87ce710-76bf-872d-9739-f0d7c9b52533'}


def now():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value)+'\n')
def file_id(path):
    path=Path(path).resolve(strict=True);digest=hashlib.sha256()
    with path.open('rb') as f:
        while True:
            data=f.read(16*(1<<20))
            if not data:break
            digest.update(data)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest.hexdigest())
def input_paths(model_dir,prompts,admission):
    model_dir=model_dir.resolve()
    index=json.loads((model_dir/'model.safetensors.index.json').read_text())
    paths={prompts.resolve(),admission.resolve()}
    paths.update(p.resolve() for p in model_dir.iterdir() if p.is_file() and p.suffix in ('.json','.jinja','.model'))
    for name in set(index['weight_map'].values()):
        shard=(model_dir/name).resolve(strict=True);shard.relative_to(model_dir);paths.add(shard)
    return sorted(paths)
def compare(records):
    changed=[]
    for expected in records:
        try:actual=file_id(expected['path'])
        except OSError as error:
            changed.append(dict(path=expected['path'],error=str(error)));continue
        if actual!=expected:changed.append(dict(expected=expected,actual=actual))
    return changed

def gpu_free(uuid):
    result=subprocess.run(['nvidia-smi','-i',uuid,'--query-gpu=memory.free','--format=csv,noheader,nounits'],
                          text=True,capture_output=True,check=True,timeout=10)
    return int(result.stdout.strip())*(1<<20)
def gpu_processes(uuid):
    result=subprocess.run(['nvidia-smi','-i',uuid,'--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],
                          text=True,capture_output=True,check=True,timeout=10)
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

def stop_owned(proc,group):
    if proc.poll() is None:
        os.killpg(group,signal.SIGTERM)
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if group_members(group):os.killpg(group,signal.SIGKILL)
            proc.wait()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker-output',type=Path,required=True)
    parser.add_argument('--runtime-output',type=Path,required=True)
    parser.add_argument('--prompts',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--admission',type=Path,required=True)
    parser.add_argument('--gpu-uuid',choices=sorted(GPUS),required=True)
    parser.add_argument('--seconds',type=int,default=1800)
    parser.add_argument('--max-context',type=int,default=2048)
    parser.add_argument('--max-new-tokens',type=int,default=512)
    parser.add_argument('--prefill-chunk',type=int,default=128)
    parser.add_argument('--qualification-only',action='store_true')
    args=parser.parse_args()
    if not 1<=args.seconds<=1800:parser.error('Pilot budget must be1..1800 seconds')
    runtime=args.runtime_output.resolve();runtime.mkdir(parents=True,exist_ok=True)
    worker_out=args.worker_output.resolve()
    if worker_out.exists() and any(worker_out.iterdir()):raise RuntimeError('Independent worker AT directory required')
    write(runtime/'supervisor_started.json',dict(at=now(),pid=os.getpid(),create_time=psutil.Process().create_time(),
        command=sys.argv,gpu_uuid=args.gpu_uuid,version='v2_device_input_sha_external_conflict'))
    uuid=args.gpu_uuid
    reason=None;proc=None;group=None;code=None;sources=[];inputs=[];worker_start=None;worker_seconds=None
    def requested_stop(_signal,_frame):
        nonlocal reason
        reason=reason or 'supervisor_received_signal'
    signal.signal(signal.SIGTERM,requested_stop);signal.signal(signal.SIGINT,requested_stop)
    lock_path=Path('/tmp/scalellm_r012_'+uuid+'.lock')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            sys.path.insert(0,str(HERE));import run_generation_v2
            sources=run_generation_v2.code_identities()
            snapshot=runtime/'source_snapshot';snapshot.mkdir()
            for i,item in enumerate(sources):
                target=snapshot/f'{i:02d}_{Path(item["path"]).name}'
                shutil.copyfile(item['path'],target)
                if file_id(target)['sha256']!=item['sha256']:raise RuntimeError('Source changed during freeze')
            write(runtime/'source_manifest.json',dict(sources=sources))
            for path in input_paths(args.model_dir,args.prompts,args.admission):
                if reason:raise RuntimeError('Cancelled before worker launch')
                inputs.append(file_id(path))
            write(runtime/'input_manifest_before.json',dict(inputs=inputs,complete=True))
            before=dict(at=now(),gpu_uuid=uuid,free_gpu_bytes=gpu_free(uuid),gpu_processes=gpu_processes(uuid),
                        available_ram_bytes=psutil.virtual_memory().available)
            write(runtime/'resource_admission.json',before)
            if before['gpu_processes'] or before['free_gpu_bytes']<30*(1<<30) or before['available_ram_bytes']<32*(1<<30):
                raise RuntimeError('GPU/RAM admission denied; no external process changed')
            if compare(sources):raise RuntimeError('Source changed before worker launch')
            command=[sys.executable,'-B',str(HERE/'run_generation_v2.py'),'--model-dir',str(args.model_dir.resolve()),
                '--prompts',str(args.prompts.resolve()),'--output-dir',str(worker_out),'--max-context',str(args.max_context),
                '--max-new-tokens',str(args.max_new_tokens),'--prefill-chunk',str(args.prefill_chunk),'--expected-gpu-uuid',uuid]
            if args.qualification_only:command.append('--qualification-only')
            env={**os.environ,'CUDA_VISIBLE_DEVICES':uuid,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
                 'NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'}
            budget=dict(seconds=args.seconds,cpu_threads=1,rss_bytes=8*(1<<30),gpu_bytes=24*(1<<30),
                min_gpu_free_bytes=8*(1<<30),min_ram_available_bytes=32*(1<<30),evidence_bytes=512*(1<<20),
                external_gpu_process_policy='Stop only owned worker group immediately on detection; preserve external PID')
            with (runtime/'worker.stdout.log').open('xb') as log:
                worker_start=time.monotonic()
                proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                group=os.getpgid(proc.pid)
                write(runtime/'actual_launch.json',dict(pid=proc.pid,pgid=group,starttime=psutil.Process(proc.pid).create_time(),
                    supervisor_pid=os.getpid(),launched_at=now(),command=command,budget=budget,cuda_visible_devices=uuid))
                while proc.poll() is None:
                    try:
                        process=psutil.Process(proc.pid)
                        rss=process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running())
                        gpu=gpu_processes(uuid);owned=group_members(group)
                        external=[p for p in gpu if p['pid'] not in owned]
                        used=sum(p['used_bytes'] for p in gpu if p['pid'] in owned)
                        evidence=sum(p.stat().st_size for base in (runtime,worker_out) if base.exists() for p in base.rglob('*') if p.is_file())
                        sample=dict(at=now(),elapsed_seconds=time.monotonic()-worker_start,rss_bytes=rss,gpu_owned_bytes=used,
                            gpu_free_bytes=gpu_free(uuid),ram_available_bytes=psutil.virtual_memory().available,evidence_bytes=evidence,
                            worker_pid=proc.pid,owned_group_pids=owned,external_gpu_processes=external)
                        append(runtime/'resources.jsonl',sample)
                        if external:reason=reason or 'external_gpu_process_present'
                        for field,limit in (('elapsed_seconds',budget['seconds']),('rss_bytes',budget['rss_bytes']),
                                           ('gpu_owned_bytes',budget['gpu_bytes']),('evidence_bytes',budget['evidence_bytes'])):
                            if sample[field]>limit:reason=reason or 'budget_'+field
                        if sample['gpu_free_bytes']<budget['min_gpu_free_bytes']:reason=reason or 'minimum_gpu_free'
                        if sample['ram_available_bytes']<budget['min_ram_available_bytes']:reason=reason or 'minimum_ram_available'
                    except psutil.NoSuchProcess:pass
                    except Exception as error:reason=reason or 'resource_monitor_error:'+type(error).__name__+':'+str(error)
                    if reason:
                        stop_owned(proc,group);break
                    time.sleep(2)
                code=proc.wait();worker_seconds=time.monotonic()-worker_start
        except Exception as error:
            reason=reason or 'supervisor_error:'+type(error).__name__+':'+str(error)
            if proc is not None and group is not None:stop_owned(proc,group);code=proc.wait()
        survivors=[] if group is None else group_members(group)
        if survivors:
            reason=reason or 'orphaned_owned_group_after_worker_exit'
            os.killpg(group,signal.SIGTERM)
            deadline=time.monotonic()+10
            while group_members(group) and time.monotonic()<deadline:time.sleep(.2)
            if group_members(group):os.killpg(group,signal.SIGKILL)
            survivors=group_members(group)
        source_changes=compare(sources)
        input_changes=compare(inputs)
        write(runtime/'input_revalidation_after.json',dict(at=now(),checked_inputs=len(inputs),all_input_sha_unchanged=not input_changes,
              changes=input_changes,stage='after actual worker wait and owned-group cleanup'))
        try:final_gpu=dict(gpu_processes_after=gpu_processes(uuid),free_gpu_bytes_after=gpu_free(uuid))
        except Exception as error:final_gpu=dict(final_device_query_error=type(error).__name__+':'+str(error))
        receipt=dict(ended_at=now(),native_exit_code=code,worker_launched=proc is not None,worker_reaped=proc is not None,
            pid=None if proc is None else proc.pid,worker_proc_absent=proc is None or not Path(f'/proc/{proc.pid}').exists(),
            stop_reason=reason,surviving_owned_group_pids=survivors,source_unchanged=not source_changes,source_changes=source_changes,
            all_input_sha_unchanged=not input_changes,worker_seconds=worker_seconds,gpu_uuid=uuid,**final_gpu)
        write(runtime/'external_wait_receipt.json',receipt)
        return 0 if code==0 and reason is None and not survivors and not source_changes and not input_changes else 1

if __name__=='__main__':raise SystemExit(main())
