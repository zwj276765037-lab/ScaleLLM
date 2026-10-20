"""Supervise one explicitly scoped experiment on GPU0; stop own group only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from capture_real_inputs import (GPU0_UUID, GIB, gpu_snapshot, own_gpu_bytes,
                                 rss_bytes, terminate_owned_group, now)


def write_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def identities(paths):
    return [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(set(paths))]


def stage_contract(path,wall_seconds,max_gpu_gib):
    """Read the unchanged Root persistent contract's explicit900s qualification.

    This new qualification adapter changes no contract and never starts formal
    full1024. It is used only for the original first16doc cost qualification.
    """
    if path is None:raise ValueError('Root contract required')
    contract=json.loads(path.read_text());limits=contract.get('limits',{})
    if contract.get('kind')!='m005_persistent_numerical_stage' or contract.get('gpu_uuid')!=GPU0_UUID:raise ValueError('wrong Root contract')
    if not wall_seconds<=contract.get('qualification_gpu_wall_seconds',0)<=900:raise ValueError('qualification bound exceeded')
    if max_gpu_gib>limits.get('max_gpu_gib',0) or limits.get('cpu_threads')!=1 or limits.get('max_rss_gib')!=8:raise ValueError('qualification resource contract differs')
    if limits.get('launch_free_gpu_gib')!=30 or limits.get('runtime_free_gpu_gib')!=8:raise ValueError('qualification free space guards differ')
    return dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),value=contract,
        applicability='Original formal B00116doc bounded cost qualification only; does not count toward formal1024; explicit unchanged Root900s qualification allocation')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--wall-seconds', type=int, default=300)
    p.add_argument('--max-gpu-gib', type=float, default=24)
    p.add_argument('--source', type=Path, action='append', default=[])
    p.add_argument('--stage-contract', type=Path)
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command or not 1 <= a.wall_seconds <= 900 or not 0 < a.max_gpu_gib <= 24:
        p.error('explicit command, finite wall <=900 seconds and GPU <=24 GiB required')
    contract = stage_contract(a.stage_contract, a.wall_seconds, a.max_gpu_gib)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    if (a.output_dir / 'gpu_launch_manifest.json').exists():
        raise FileExistsError('use a new attempt; prior launch evidence is immutable')
    source_files = [Path(__file__).resolve(), *a.source, *([a.stage_contract] if a.stage_contract else [])]
    source_identity = identities(source_files)
    started = now()
    preflight = gpu_snapshot()
    apps = subprocess.run(['nvidia-smi', '-i', GPU0_UUID,
        '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=3, check=True).stdout
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    write_new(a.output_dir / 'gpu_launch_manifest.json', dict(started_at=started, command=command,
        cwd=str(Path.cwd()), source_identity=source_identity, preflight=preflight, external_compute_apps=apps,
        available_ram_bytes=available, gpu_uuid=GPU0_UUID, threads=1, max_rss_bytes=8*GIB,
        max_gpu_bytes=int(a.max_gpu_gib*GIB), minimum_free_gpu_bytes=8*GIB,
        wall_seconds=a.wall_seconds, stage_contract=contract))
    if preflight['free_bytes'] < 30*GIB or available < 32*GIB:
        write_new(a.output_dir / 'gpu_receipt.json', dict(execution_state='cost_stop', started_at=started,
            ended_at=now(), exit_code=None, worker_launched=False, stop_reason='preflight resource admission failed'))
        return 75
    env = os.environ.copy()
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        env[key] = '1'
    env.update(CUDA_VISIBLE_DEVICES=GPU0_UUID, NUMERICAL_TEST_DEVICE='cuda:0',
               PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DEACTIVATE_ASYNC_LOAD='1')
    max_rss = max_gpu = 0
    stop = None
    begin = time.monotonic()
    with (a.output_dir/'gpu_stdout.log').open('x') as stdout, \
         (a.output_dir/'gpu_stderr.log').open('x') as stderr, \
         (a.output_dir/'gpu_resources.jsonl').open('x') as samples:
        worker = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
        write_new(a.output_dir/'gpu_worker.json', dict(pid=worker.pid, started_at=now()))
        try:
            while worker.poll() is None:
                rss, gpu = rss_bytes(worker.pid), own_gpu_bytes(worker.pid)
                try: device = gpu_snapshot()
                except Exception: device = None
                elapsed = time.monotonic() - begin
                max_rss, max_gpu = max(max_rss, rss or 0), max(max_gpu, gpu or 0)
                samples.write(json.dumps(dict(at=now(), elapsed_seconds=elapsed, rss_bytes=rss,
                    gpu_bytes=gpu, gpu_free_bytes=None if device is None else device['free_bytes']))+'\n')
                samples.flush()
                if worker.poll() is not None: break
                if rss is not None and rss > 8*GIB: stop = 'own worker RSS exceeded 8 GiB'
                elif gpu is not None and gpu > a.max_gpu_gib*GIB: stop = 'own worker GPU exceeded assigned cap'
                elif gpu is None or device is None: stop = 'GPU telemetry unavailable'
                elif device['free_bytes'] < 8*GIB: stop = 'shared GPU free space below 8 GiB'
                elif elapsed >= max(1, a.wall_seconds-5): stop = 'assigned wall budget reached'
                elif sum(x.stat().st_size for x in a.output_dir.rglob('*') if x.is_file()) > 256*(1 << 20):
                    stop = 'evidence exceeded 256 MiB'
                if stop:
                    terminate_owned_group(worker)
                    break
                time.sleep(.5)
        finally:
            terminate_owned_group(worker)
        native = worker.wait()
    unchanged = source_identity == identities(source_files)
    exit_code = 124 if stop else native
    if exit_code == 0 and not unchanged:
        exit_code, stop = 76, 'source changed during experiment'
    state = 'completed' if exit_code == 0 else ('cost_stop' if exit_code == 124 else 'failed')
    receipt = dict(execution_state=state, started_at=started, ended_at=now(),
        wall_seconds=time.monotonic()-begin, exit_code=exit_code, native_exit_code=native,
        stop_reason=stop, max_observed_rss_bytes=max_rss, max_observed_gpu_bytes=max_gpu,
        worker_pid=worker.pid, worker_reaped=True, source_unchanged=unchanged)
    write_new(a.output_dir/'gpu_receipt.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
