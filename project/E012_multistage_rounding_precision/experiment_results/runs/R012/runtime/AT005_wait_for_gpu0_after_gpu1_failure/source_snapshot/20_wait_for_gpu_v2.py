#!/usr/bin/env python3
"""Root-admitted finite one-shot GPU0 queue after the failed GPU1 trial. Uses v2 input-SHA/external-conflict supervision; no GPU1 fallback.

Wait at most six hours. Query GPU0 processes every30s; after three consecutive
empty observations, revalidate source/input SHA and launch the same1800s pilot
once. No external PID is signalled. No automatic retry or wider benchmark.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
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
GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
sys.path.insert(0,str(HERE))


def now():return datetime.now(timezone.utc).isoformat()
def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def status(directory,phase,**fields):
    row=dict(at=now(),phase=phase,pid=os.getpid(),**fields)
    with (directory/'wait_stages.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    temporary=directory/'current_status.json.tmp'
    temporary.write_text(json.dumps(row,indent=2)+'\n')
    temporary.replace(directory/'current_status.json')
def file_id(path):
    path=Path(path).resolve(strict=True)
    digest=hashlib.sha256()
    with path.open('rb') as f:
        while True:
            block=f.read(16*(1<<20))
            if not block:break
            digest.update(block)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest.hexdigest())
def revalidate(records):
    changed=[]
    for item in records:
        try:actual=file_id(item['path'])
        except OSError as error:
            changed.append(dict(path=item['path'],error=str(error)));continue
        if actual!=item:changed.append(dict(expected=item,actual=actual))
    return changed

def inputs(model_dir,prompts,admission):
    index=json.loads((model_dir/'model.safetensors.index.json').read_text())
    paths={prompts.resolve(),admission.resolve()}
    paths.update(p.resolve() for p in model_dir.iterdir() if p.is_file() and p.suffix in ('.json','.jinja','.model'))
    for name in set(index['weight_map'].values()):
        shard=(model_dir/name).resolve(strict=True);shard.relative_to(model_dir.resolve());paths.add(shard)
    return sorted(paths)

def gpu_state():
    result=subprocess.run(['nvidia-smi','-i',GPU,'--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],
                          text=True,capture_output=True,check=True,timeout=10)
    processes=[]
    for line in result.stdout.splitlines():
        if line.strip():
            pid,memory=line.split(',');processes.append(dict(pid=int(pid),used_bytes=int(memory.strip())*(1<<20)))
    row=dict(at=now(),gpu_uuid=GPU,processes=processes,available_ram_bytes=psutil.virtual_memory().available)
    if not processes:
        free=subprocess.run(['nvidia-smi','-i',GPU,'--query-gpu=memory.free','--format=csv,noheader,nounits'],
                            text=True,capture_output=True,check=True,timeout=10)
        row['free_gpu_bytes']=int(free.stdout.strip())*(1<<20)
    return row


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-output',type=Path,required=True)
    parser.add_argument('--worker-output',type=Path,required=True)
    parser.add_argument('--prompts',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--admission',type=Path,required=True)
    args=parser.parse_args()
    directory=args.runtime_output.resolve();directory.mkdir(parents=True,exist_ok=True)
    if (directory/'started.json').exists():raise RuntimeError('Independent AT directory required')
    started=time.monotonic();cancelled=False;child=None;reason=None
    def cancel(_signum,_frame):
        nonlocal cancelled
        cancelled=True
    signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
    write_new(directory/'started.json',dict(at=now(),pid=os.getpid(),pgid=os.getpgid(0),create_time=psutil.Process().create_time(),
        command=sys.argv,runtime_id='collaboration:/root/response_quality_generation',gpu_uuid=GPU,
        wait_seconds=21600,poll_seconds=30,required_empty_observations=3,query_failure_limit=3,pilot_seconds=1800,
        pilot_only=True,formal_benchmark_automatic_start=False))
    status(directory,'freezing_source_and_inputs')
    try:
        import run_generation_v2 as run_generation
        source_records=run_generation.code_identities()
        source_paths={Path(x['path']) for x in source_records}|{Path(__file__),HERE/'supervise_v2.py'}
        sources=[file_id(p) for p in sorted(source_paths)]
        weights=inputs(args.model_dir.resolve(),args.prompts.resolve(),args.admission.resolve())
        input_records=[]
        for path in weights:
            if cancelled:reason='cancelled';break
            input_records.append(file_id(path))
            status(directory,'freezing_source_and_inputs',completed_inputs=len(input_records),total_inputs=len(weights))
        if reason is None:
            manifest=dict(schema=1,source=sources,inputs=input_records)
            write_new(directory/'frozen_manifest.json',manifest)
            snapshot=directory/'source_snapshot';snapshot.mkdir()
            for i,item in enumerate(sources):
                target=snapshot/f'{i:02d}_{Path(item["path"]).name}'
                shutil.copyfile(item['path'],target)
                if file_id(target)['sha256']!=item['sha256']:raise RuntimeError('Source changed during snapshot')
            empty=failures=observations=0
            next_poll=time.monotonic()
            while reason is None and child is None:
                if cancelled:reason='cancelled';break
                if time.monotonic()-started>=21600:reason='wait_deadline';break
                if time.monotonic()<next_poll:
                    time.sleep(min(1,next_poll-time.monotonic()));continue
                # Cheap sources and small input identities also detect external
                # edits during the wait. Large checkpoint shards are rehashed
                # only at freeze and final launch admission boundaries.
                cheap=[x for x in sources+input_records if x['bytes']<=64*(1<<20)]
                changes=revalidate(cheap)
                if changes:
                    write_new(directory/'changed_inputs_or_source.json',dict(changes=changes));reason='source_or_input_changed';break
                next_poll=time.monotonic()+30
                try:
                    state=gpu_state();observations+=1;failures=0
                    eligible=not state['processes'] and state['available_ram_bytes']>=32*(1<<30) and state.get('free_gpu_bytes',0)>=30*(1<<30)
                    empty=empty+1 if eligible else 0
                    status(directory,'waiting_for_gpu0',elapsed_wait_seconds=time.monotonic()-started,
                           observation=observations,consecutive_empty=empty,device=state)
                except Exception as error:
                    failures+=1;empty=0
                    status(directory,'device_query_failed',consecutive_failures=failures,error=type(error).__name__+':'+str(error))
                    if failures>=3:reason='persistent_device_query_failure'
                    continue
                if empty<3:continue
                status(directory,'revalidating_all_source_and_input_sha_before_one_shot_launch')
                changes=revalidate(sources+input_records)
                if changes:
                    write_new(directory/'changed_inputs_or_source.json',dict(changes=changes));reason='source_or_input_changed';break
                if cancelled:reason='cancelled';break
                command=[sys.executable,'-B',str(HERE/'supervise_v2.py'),'--worker-output',str(args.worker_output.resolve()),
                    '--runtime-output',str(directory/'supervisor'),'--model-dir',str(args.model_dir.resolve()),
                    '--prompts',str(args.prompts.resolve()),'--admission',str(args.admission.resolve()),'--gpu-uuid',GPU,'--max-context','2048','--max-new-tokens','512','--prefill-chunk','128','--seconds','1800']
                with (directory/'supervisor.stdout.log').open('xb') as log:
                    child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                        env={**os.environ,'CUDA_VISIBLE_DEVICES':GPU,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'})
                write_new(directory/'one_shot_launch.json',dict(at=now(),supervisor_pid=child.pid,create_time=psutil.Process(child.pid).create_time(),
                    command=command,wait_seconds=time.monotonic()-started,all_source_and_input_sha_revalidated=True))
                status(directory,'pilot_supervisor_running',supervisor_pid=child.pid)
                while child.poll() is None:
                    if cancelled:
                        # Only this direct child is signalled. Its own supervisor
                        # owns and reaps the isolated worker process group.
                        child.send_signal(signal.SIGTERM)
                        reason='cancelled_after_pilot_launch'
                    time.sleep(1)
                code=child.wait()
                reason=reason or ('pilot_completed' if code==0 else 'pilot_failed_no_automatic_retry')
                write_new(directory/'child_wait_receipt.json',dict(at=now(),supervisor_pid=child.pid,reaped=True,exit_code=code,
                    proc_absent=not Path(f'/proc/{child.pid}').exists()))
    except Exception as error:
        reason='waiter_error:'+type(error).__name__+':'+str(error)
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM);child.wait()
    receipt=dict(at=now(),pid=os.getpid(),ended=True,reason=reason,wall_seconds=time.monotonic()-started,
        pilot_launched=child is not None,pilot_exit_code=child.returncode if child is not None else None,
        automatic_retries=0,formal_benchmark_launched=False)
    write_new(directory/'waiter_exit_receipt.json',receipt)
    status(directory,'ended',**{k:v for k,v in receipt.items() if k!='at' and k!='pid'})
    return 0 if reason=='pilot_completed' else 1

if __name__=='__main__':raise SystemExit(main())
