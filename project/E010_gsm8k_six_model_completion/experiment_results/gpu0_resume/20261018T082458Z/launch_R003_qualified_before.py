#!/usr/bin/env python3
"""Parent-owned, one-shot R003 launch after both independently accepted GPU smokes."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'project/software/0_Software/fix_experiment/results/gsm8k_full_completion'
PREP = BASE / 'preparation_20261018'
RUN = BASE / 'R003_gsm8k_gpu0_weight_integrity'
GPU = 'GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, data):
    with path.open('x') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args()
    hold_path = RUN / 'maintenance_hold.json'
    hold = read(hold_path) if hold_path.exists() else {'active': False}
    if args.launch and hold.get('active'):
        raise RuntimeError('GPU maintenance handoff is active; do not launch a new matrix')
    freeze = read(RUN / 'freeze_preparation.json')
    readiness = read(RUN / 'prelaunch_readiness_candidate.json')
    prepared = read(RUN / 'launch_command_prepared.json')
    assert digest(RUN / 'frozen_inputs/plan.json') == freeze['plan_sha256'] == readiness['plan_sha256']
    assert read(RUN / 'frozen_inputs/plan.json')['paths']['user_display_results'] == str(BASE.parent)
    assert readiness['gpu_uuids'] == [GPU]
    for item in freeze['sources']:
        assert digest(Path(item['path'])) == digest(RUN / item['snapshot']) == item['sha256']
        assert readiness['source_hashes'][item['path']] == item['sha256']
    evidence = dict(readiness['evidence_hashes'])
    max_reserved = 0
    for case, label in [('bf16', 'bf16'), ('a8w4_fp32', 'qdq')]:
        review_path = PREP / f'protocol/integrity_v3_gpu_{label}_terminal_review_AT001.json'
        review = read(review_path)
        attempt = PREP / f'weight_integrity_v1_gpu_smoke/Llama-3.1-8B-Instruct/{case}/AT001'
        assert Path(review['attempt']) == attempt and review['case'] == case
        assert review['execution_state'] == 'completed_training_smoke_independently_accepted'
        assert review['plan_sha256'] == freeze['source_plan_sha256']
        assert review['all_phase_coverage_and_roots_verified'] is True
        assert review['all_original_v2_detailed_gates_verified'] is True
        assert review['raw_token_rows_independently_redecoded_rescored'] == 4
        assert review['integrity_reference']['qualified'] is True
        assert review['formal_results_accepted'] == 0
        for source, expected in review['source_sha256'].items():
            assert readiness['source_hashes'][source] == expected
        for name, expected in review['artifacts'].items():
            assert digest(attempt / name) == expected
            evidence[str(attempt / name)] = expected
        post = read(attempt / 'postrun_receipt.json')
        assert post['state'] == 'complete' and post['pid_absent'] is True
        assert post['source_hashes_unchanged'] is True and post['n_completed'] == 4
        assert post['verification_passed'] is True and post['integrity_qualified'] is True
        assert not Path(f"/proc/{post['pid']}").exists(), 'Preparation PID still present'
        summary = read(attempt / 'summary.json')
        assert summary['state'] == 'complete' and summary['n_completed'] == 4
        max_reserved = max(max_reserved, summary['peak_memory_reserved_bytes'])
        evidence[str(review_path)] = digest(review_path)
        evidence[str(attempt / 'postrun_receipt.json')] = digest(attempt / 'postrun_receipt.json')
    for path, expected in evidence.items():
        assert digest(Path(path)) == expected, f'Evidence changed: {path}'
    available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    assert available >= 80 * 2**30
    monitor = PREP / 'nvml_local_recovery_20261018/nvidia_smi_local.sh'
    clients = subprocess.run(['bash', str(monitor), '-i', GPU,
                              '--query-compute-apps=pid,process_name,used_memory',
                              '--format=csv,noheader,nounits'], check=True, capture_output=True, text=True)
    if clients.stdout.strip():
        raise RuntimeError('GPU0 has an existing compute client; wait for its owner to release it: ' +
                           clients.stdout.strip())
    query = subprocess.run(['bash', str(monitor), '-i', GPU, '--query-gpu=uuid,memory.free',
                            '--format=csv,noheader,nounits'], check=True, capture_output=True, text=True)
    uuid, free_mib = query.stdout.strip().split(',')
    free_bytes = int(free_mib.strip()) * 2**20
    assert uuid.strip() == GPU and free_bytes >= max(8 * 2**30, int(max_reserved * 1.2))
    with (BASE / 'resource_locks' / (GPU + '.lock')).open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock, fcntl.LOCK_UN)
    checks = {'checked_at': datetime.now(timezone.utc).isoformat(), 'all_prelaunch_checks_passed': True,
              'host_available_bytes': available, 'gpu_free_bytes': free_bytes,
              'maintenance_hold_active': bool(hold.get('active')),
              'scope': 'Permission to run all fresh R003 stages; not a formal accuracy result'}
    if not args.launch:
        print(json.dumps(checks))
        return
    assert not (RUN / 'launch_AT001.json').exists()
    assert not (RUN / 'current_state.json').exists()
    if hold_path.exists() and read(hold_path).get('active'):
        raise RuntimeError('GPU maintenance handoff became active before launch')
    readiness.update(ready=True, reviewed_at=checks['checked_at'], evidence_hashes=evidence,
                     scope='R003 GPU0 only; independently accepted BF16 and QDQ preparation; all 30 fresh smoke/pilot groups still required',
                     resource_observation=checks)
    save_new(RUN / 'prelaunch_readiness_AT001.json', readiness)
    env = dict(os.environ)
    env.pop('LD_LIBRARY_PATH', None)
    env.update(prepared['environment'])
    stdout = RUN / 'supervisor_AT001.stdout.log'
    stderr = RUN / 'supervisor_AT001.stderr.log'
    with stdout.open('x') as out, stderr.open('x') as err:
        proc = subprocess.Popen(prepared['command'], cwd=prepared['cwd'], env=env,
                                stdout=out, stderr=err, start_new_session=True)
    receipt = {'launched_at': datetime.now(timezone.utc).isoformat(), 'pid': proc.pid,
               'command': prepared['command'], 'cwd': prepared['cwd'], 'environment_overrides': prepared['environment'],
               'LD_LIBRARY_PATH': None, 'stdout': str(stdout), 'stderr': str(stderr),
               'supervisor_status': 'spawned_pending_worker_receipt', 'gpu_inference_claimed': False,
               'finalizer_mode': 'generated_pending_review; parent independently scores and checks plan binding before publication',
               'prelaunch_checks': checks, 'launcher_source_sha256': digest(Path(__file__))}
    stat = Path(f'/proc/{proc.pid}/stat')
    if stat.exists():
        receipt['proc_start_ticks'] = stat.read_text().split()[21]
    save_new(RUN / 'launch_AT001.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
