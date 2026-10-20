#!/usr/bin/env python3
"""Parent-owned resource guard for a bounded synthetic GPU0 diagnostic.

No model or ACC queue can be launched through this entry point. CUDA is only
initialized by the reviewed child after its UUID, sources and resources pass.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
E010 = ROOT / 'project/E010_gsm8k_six_model_completion'
EXP = ROOT / 'project/software/0_Software/fix_experiment/exp'
BASE = EXP.parent / 'results/gsm8k_full_completion'
GPU = 'GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
PYTHON = '/home/user/anaconda3/envs/zhouwenjun/bin/python'
SCRIPT = EXP / 'benchmark_bytewise_integrity.py'
GIB = 2 ** 30


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, data):
    with Path(path).open('x') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def option(argv, name):
    if argv.count(name) != 1 or argv.index(name) + 1 >= len(argv):
        raise ValueError('Exactly one argument is required: ' + name)
    return argv[argv.index(name) + 1]


def validate_spec(spec, output):
    if spec.get('kind') != 'synthetic_gpu0' or spec.get('gpu_uuid') != GPU:
        raise ValueError('Only the fixed GPU0 synthetic probe is supported')
    command = spec['command']
    entry = Path(spec.get('entrypoint', str(SCRIPT))).resolve()
    snapshot_entry = (entry.is_relative_to(E010 / 'experiment_results/performance_repair')
                      and entry.name == SCRIPT.name)
    if entry != SCRIPT.resolve() and not snapshot_entry:
        raise ValueError('Only the diagnostic entry or its bound E010 snapshot is allowed')
    if command[:3] != [PYTHON, '-B', str(entry)]:
        raise ValueError('Unexpected executable or diagnostic entry point')
    if option(command, '--device') != 'cuda:0' or option(command, '--gpu-uuid') != GPU:
        raise ValueError('CUDA device/physical UUID binding is invalid')
    if Path(option(command, '--output')).resolve() != (output / 'payload.json').resolve():
        raise ValueError('Payload evidence must be inside the fresh receipt directory')
    mib, repeats = int(option(command, '--mib')), int(option(command, '--repeats'))
    if not 1 <= mib <= 64 or not 1 <= repeats <= 5:
        raise ValueError('Synthetic probe exceeds the 64 MiB / five-repeat budget')
    if not 1 <= int(option(command, '--chunk-mib')) <= 16:
        raise ValueError('Staging exceeds the 16 MiB budget')
    shared = spec.get('shared_diagnostic') is True
    if shared:
        if command.count('--diagnostic-shared-gpu0') != 1 or '--exclusive-gpu0-slot' in command:
            raise ValueError('Shared diagnosis must never claim an exclusive slot')
    elif command.count('--exclusive-gpu0-slot') != 1 or '--diagnostic-shared-gpu0' in command:
        raise ValueError('Exclusive probe requires its explicit mode')
    required = {str(entry), str(entry.parent / 'gsm8k_integrity_bytewise.py'),
                str(entry.parent / 'gsm8k_weight_integrity.py'),
                str(entry.parent / 'gsm8k_protocol.py')}
    if not required.issubset(spec.get('source_hashes', {})):
        raise ValueError('Diagnostic and both integrity implementations must be source-bound')
    for path, expected in spec['source_hashes'].items():
        if digest(path) != expected:
            raise ValueError('Diagnostic source changed: ' + path)
    return shared


def command_read(argv, records):
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    records.append({'argv': argv, 'captured_at': now(), 'exit_code': result.returncode,
                    'stdout': result.stdout, 'stderr': result.stderr})
    if result.returncode:
        raise RuntimeError('Resource query failed: ' + repr(argv))
    return result.stdout


def resources(spec, records):
    clients = command_read(['/usr/bin/nvidia-smi', '-i', GPU,
                            '--query-compute-apps=pid,process_name,used_memory',
                            '--format=csv,noheader,nounits'], records)
    pids = {int(line.split(',')[0].strip()) for line in clients.splitlines() if line.strip()}
    allowed = set(spec.get('acknowledged_external_client_pids', []))
    if spec.get('shared_diagnostic') is True:
        if not pids.issubset(allowed):
            raise RuntimeError('An unacknowledged external GPU0 compute client is present')
    elif pids:
        raise RuntimeError('Exclusive GPU0 slot unavailable; existing clients are untouched')
    text = command_read(['/usr/bin/nvidia-smi', '-i', GPU,
                         '--query-gpu=index,uuid,memory.free',
                         '--format=csv,noheader,nounits'], records)
    index, uuid, free = [part.strip() for part in text.strip().split(',')]
    if index != '0' or uuid != GPU or int(free) * 2**20 < 8 * GIB:
        raise RuntimeError('GPU0 identity or 8 GiB free-memory reserve is unavailable')
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    if available < 80 * GIB + 256 * 2**20:
        raise RuntimeError('Host memory reserve is unavailable')
    return {'external_client_pids': sorted(pids), 'gpu_free_bytes': int(free) * 2**20,
            'host_available_bytes': available, 'shared_diagnostic': bool(spec['shared_diagnostic']),
            'formal_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--receipt-dir', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    spec_path, output = args.spec.resolve(), args.receipt_dir.resolve()
    permitted = E010 / 'experiment_results/performance_repair'
    if not spec_path.is_relative_to(permitted) or not output.is_relative_to(permitted):
        raise ValueError('Probe control and evidence must remain inside E010 performance repair')
    output.mkdir(parents=True, exist_ok=False)
    result = {'started_at': now(), 'execute_requested': args.execute, 'state': 'checking',
              'gpu_uuid': GPU, 'commands': [], 'CUDA_initialized_by_guard': False,
              'process_control_actions_on_other_tasks': []}
    child = None
    try:
        spec = json.loads(spec_path.read_text())
        shared = validate_spec(spec, output)
        result.update(spec_sha256=digest(spec_path), shared_diagnostic=shared)
        with (BASE / 'resource_locks' / (GPU + '.lock')).open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result['resource_observation'] = resources(spec, result['commands'])
            if not args.execute:
                result['state'] = 'checked_no_CUDA_actions'
            else:
                validate_spec(spec, output)
                before_path = output / 'resource_guard_before.json'
                write_new(before_path, {'observed_at': now(),
                          'resource_observation': result['resource_observation'],
                          'query_records': result['commands'], 'spec_sha256': result['spec_sha256'],
                          'project_lock_held': True, 'GPU0_uuid': GPU})
                env = dict(os.environ)
                env.pop('LD_LIBRARY_PATH', None)
                env.pop('PYTHONOPTIMIZE', None)
                env.update(CUDA_VISIBLE_DEVICES=GPU, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                           OPENBLAS_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
                with (output / 'stdout.log').open('x') as out, (output / 'stderr.log').open('x') as err:
                    child = subprocess.Popen(['taskset', '-c', '16,17', *spec['command']],
                                             env=env, cwd=EXP, stdout=out, stderr=err,
                                             start_new_session=True, pass_fds=(lock.fileno(),))
                    write_new(output / 'started.json', {'started_at': now(), 'pid': child.pid,
                              'command': spec['command'], 'spec_sha256': result['spec_sha256'],
                              'gpu_uuid': GPU, 'shared_diagnostic': shared,
                              'scope': 'bounded synthetic diagnostic; no model or ACC generation'})
                    result['child_pid'] = child.pid
                    result['child_exit_code'] = child.wait()
                if result['child_exit_code']:
                    raise RuntimeError('Synthetic diagnostic failed; see preserved payload logs')
                payload = json.loads((output / 'payload.json').read_text())
                if payload.get('actual_gpu_uuid') != GPU or payload.get('model_or_ACC_qualified') is not False:
                    raise RuntimeError('Payload physical GPU or diagnostic scope binding failed')
                if shared and (payload.get('shared_diagnostic_only') is not True
                               or payload.get('exclusive_verified') is not False):
                    raise RuntimeError('Shared payload falsely claims exclusive qualification')
                if payload.get('memory', {}).get('peak_memory_allocated_bytes', 2 * GIB) > GIB:
                    raise RuntimeError('Payload exceeded the one-GiB owned allocation budget')
                command_read(['/usr/bin/nvidia-smi', '-i', GPU,
                              '--query-compute-apps=pid,process_name,used_memory',
                              '--format=csv,noheader,nounits'], result['commands'])
                result['payload_sha256'] = digest(output / 'payload.json')
                result['state'] = 'synthetic_diagnostic_complete_not_formal_qualification'
    except BaseException as exc:
        result.update(state='refused_or_failed', error=repr(exc))
        # Keep the shared lock until our finite child returns; never kill other tasks.
        if child is not None and child.poll() is None:
            result['child_exit_code'] = child.wait()
    finally:
        result['ended_at'] = now()
        write_new(output / 'result.json', result)
    print(json.dumps(result, ensure_ascii=False))
    if result['state'] == 'refused_or_failed':
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
