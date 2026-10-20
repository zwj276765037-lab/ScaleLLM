#!/usr/bin/env python3
"""Fixed four-training-question GPU0 performance diagnostic; never runs a matrix."""
import argparse
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from run_gpu0_performance_probe import (ROOT, E010, EXP, BASE, GPU, PYTHON,
                                       GIB, digest, now, write_new, command_read)

OLD = BASE / 'R003_gsm8k_gpu0_weight_integrity'
WORKER = EXP / 'run_gsm8k_worker.py'
METHOD = 'immutable_cpu_chunks_memcmp_full_content_v1'
CASES = ('bf16', 'a8w4_fp32')
MODEL = Path('/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct')
IDENTITY = BASE / 'preparation_20261018/model_identities/Llama-3.1-8B-Instruct.json'
SCOPE = {'kind': 'shared_model_speed_diagnostic', 'exclusive_verified': False,
         'formal_progression_eligible': False, 'matrix_resume': False,
         'sample_ids': ['train:0000', 'train:0001', 'train:0002', 'train:0003'],
         'cases': list(CASES)}


def expected_plan():
    plan = json.loads((OLD / 'frozen_inputs/plan.json').read_text())
    plan['protocol']['integrity_implementation_id'] = METHOD
    # This is a separately identified diagnostic, with unchanged data/numerics.
    plan['protocol_id'] += '_bytewise_shared_speed_diag_v1'
    plan['diagnostic_scope'] = copy.deepcopy(SCOPE)
    # The old schedule path is relative to its frozen plan directory.
    schedule = Path(plan['protocol']['fewshot_schedule_file'])
    if not schedule.is_absolute():
        schedule = (OLD / 'frozen_inputs' / schedule).resolve()
    plan['protocol']['fewshot_schedule_file'] = str(schedule)
    return plan


def expected_command(plan, output, case):
    return [PYTHON, '-B', str(WORKER), '--plan', str(plan), '--stage', 'smoke',
            '--model', str(MODEL), '--case', case, '--model-identity', str(IDENTITY),
            '--output', str(output / 'worker'), '--device', 'cuda:0', '--batch-size', '1',
            '--context-length', '8192', '--max-gen-toks', '64', '--verify-generation']


def validate(spec, output):
    if (spec.get('scope') != SCOPE or spec.get('gpu_uuid') != GPU or
            spec.get('case') not in CASES):
        raise ValueError('Only bounded shared Llama8B training speed diagnostics are allowed')
    plan_path = Path(spec['plan']).resolve()
    if not plan_path.is_relative_to(E010 / 'experiment_results/performance_repair'):
        raise ValueError('Diagnostic plan must be inside E010 repair evidence')
    if digest(plan_path) != spec['plan_sha256'] or json.loads(plan_path.read_text()) != expected_plan():
        raise ValueError('Diagnostic data/numerics/scope differ from the bound protocol')
    if spec['command'] != expected_command(plan_path, output, spec['case']):
        raise ValueError('Only the exact four-question verified worker command is allowed')
    if spec['model_identity_sha256'] != digest(IDENTITY):
        raise ValueError('Model identity changed')
    frozen = json.loads((OLD / 'frozen_sources/manifest.json').read_text())
    required = {item['path'] for item in frozen}
    required.add(str(EXP / 'gsm8k_integrity_bytewise.py'))
    if set(spec['source_hashes']) != required or set(spec['source_snapshots']) != required:
        raise ValueError('Complete worker, numerical, consumer and integrity source set is required')
    for path, expected in spec['source_hashes'].items():
        snapshot = Path(spec['source_snapshots'][path]).resolve()
        if (not snapshot.is_relative_to(plan_path.parent) or digest(snapshot) != expected or
                digest(path) != expected):
            raise ValueError('Source/snapshot changed: ' + path)
    baseline = OLD / 'smoke' / MODEL.name / spec['case'] / 'AT001'
    if spec['baseline_summary_sha256'] != digest(baseline / 'summary.json'):
        raise ValueError('Baseline summary identity changed')
    if spec['baseline_manifest_sha256'] != digest(baseline / 'manifest.json'):
        raise ValueError('Baseline manifest identity changed')
    manifest = json.loads((baseline / 'manifest.json').read_text())
    summary = json.loads((baseline / 'summary.json').read_text())
    if manifest['state'] != 'complete':
        raise ValueError('Baseline must be a completed post-reboot smoke')
    peaks = [manifest['model_load_attach_peak_memory_reserved_bytes'],
             manifest['verification_peak_memory_reserved_bytes'], summary['peak_memory_reserved_bytes']]
    if any(type(value) is not int or value <= 0 for value in peaks):
        raise ValueError('Invalid measured baseline memory peaks')
    peak = max(peaks)
    return math.ceil(peak * 1.2) + 8 * GIB


def resources(spec, minimum, records):
    clients = command_read(['/usr/bin/nvidia-smi', '-i', GPU,
                            '--query-compute-apps=pid,process_name,used_memory',
                            '--format=csv,noheader,nounits'], records)
    pids = {int(row.split(',')[0].strip()) for row in clients.splitlines() if row.strip()}
    if not pids.issubset(set(spec['acknowledged_external_client_pids'])):
        raise RuntimeError('Unacknowledged GPU0 client; other tasks are never controlled')
    observed = command_read(['/usr/bin/nvidia-smi', '-i', GPU,
                             '--query-gpu=index,uuid,memory.free',
                             '--format=csv,noheader,nounits'], records)
    index, uuid, free = [s.strip() for s in observed.strip().split(',')]
    free = int(free) * 2**20
    if index != '0' or uuid != GPU or free < max(minimum, 24 * GIB):
        raise RuntimeError('GPU0 UUID/free memory insufficient for conservative shared-model guard')
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    if available < 120 * GIB:
        raise RuntimeError('Host available memory below 120GiB; capture also preserves 80GiB')
    return {'external_client_pids': sorted(pids), 'gpu_free_bytes': free,
            'minimum_gpu_free_bytes': minimum, 'host_available_bytes': available,
            'exclusive_verified': False, 'formal_progression_eligible': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    output = args.receipt_dir.resolve()
    permitted = E010 / 'experiment_results/performance_repair'
    if not output.is_relative_to(permitted) or not args.spec.resolve().is_relative_to(permitted):
        raise ValueError('Control/evidence must stay in E010 repair')
    output.mkdir(parents=True, exist_ok=False)
    result = {'started_at': now(), 'state': 'checking', 'scope': SCOPE, 'commands': [],
              'process_control_actions_on_other_tasks': [], 'execute_requested': args.execute,
              'guard_sha256': digest(__file__), 'spec_sha256': digest(args.spec)}
    child = None
    try:
        spec = json.loads(args.spec.read_text())
        minimum = validate(spec, output)
        with (BASE / 'resource_locks' / (GPU + '.lock')).open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result['resource_observation'] = resources(spec, minimum, result['commands'])
            if not args.execute:
                result['state'] = 'checked_no_CUDA_actions'
            else:
                validate(spec, output)
                write_new(output / 'resource_guard_before.json', result['resource_observation'])
                env = dict(os.environ)
                for key in ('LD_LIBRARY_PATH', 'PYTHONOPTIMIZE'):
                    env.pop(key, None)
                env.update(CUDA_VISIBLE_DEVICES=GPU, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                           OPENBLAS_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
                with (output / 'stdout.log').open('x') as out, (output / 'stderr.log').open('x') as err:
                    child = subprocess.Popen(['taskset', '-c', '16,17', *spec['command']],
                        cwd=EXP, env=env, stdout=out, stderr=err, start_new_session=True,
                        pass_fds=(lock.fileno(),))
                    result['child_pid'] = child.pid
                    write_new(output / 'started.json', {**result, 'command': spec['command']})
                    result['child_exit_code'] = child.wait()
                if result['child_exit_code']:
                    raise RuntimeError('Model diagnostic failed; preserve evidence and use a new attempt')
                validate(spec, output)
                manifest = json.loads((output / 'worker/manifest.json').read_text())
                summary = json.loads((output / 'worker/summary.json').read_text())
                if (manifest['state'] != 'complete' or manifest['n_completed'] != 4 or
                        summary['full_split'] is not False or summary['n_completed'] != 4 or
                        manifest['identity'].get('integrity_implementation_id') != METHOD or
                        str(manifest['environment']['gpu_uuid']).removeprefix('GPU-') != GPU.removeprefix('GPU-')):
                    raise RuntimeError('Worker completion/scope/physical UUID validation failed')
                result['manifest_sha256'] = digest(output / 'worker/manifest.json')
                result['summary_sha256'] = digest(output / 'worker/summary.json')
                command_read(['/usr/bin/nvidia-smi', '-i', GPU,
                              '--query-compute-apps=pid,process_name,used_memory',
                              '--format=csv,noheader,nounits'], result['commands'])
                result['state'] = 'shared_training_speed_diagnostic_complete_not_ACC'
    except BaseException as exc:
        result.update(state='refused_or_failed', error=repr(exc))
        # Wait for our finite worker, without signalling any other process.
        if child is not None and child.poll() is None:
            result['child_exit_code'] = child.wait()
    finally:
        result['ended_at'] = now()
        write_new(output / 'result.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return int(result['state'] == 'refused_or_failed')


if __name__ == '__main__':
    sys.exit(main())
