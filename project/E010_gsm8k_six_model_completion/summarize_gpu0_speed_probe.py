#!/usr/bin/env python3
"""Independently compare a completed four-train-question diagnostic to R003."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
from run_gpu0_model_speed_probe import (EXP, OLD, GPU, METHOD, MODEL, digest, now, write_new)

sys.path.insert(0, str(EXP))
from gsm8k_protocol import canonical_hash, validate_integrity_evidence
from run_gsm8k_matrix import validate_actual_gpu, validate_generation_verification


def load(path):
    return json.loads(path.read_text())


def analyze(case, worker):
    previous = OLD / 'smoke' / MODEL.name / case / 'AT001'
    def validate_raw_bindings(directory):
        m = load(directory / 'manifest.json')
        assert canonical_hash(m['identity']) == m['identity_sha256']
        for name, expected in m['artifacts'].items():
            assert Path(name).name == name and digest(directory / name) == expected
        requests = load(directory / 'requests.json')
        assert [r['sample_id'] for r in requests] == ['train:0000', 'train:0001', 'train:0002', 'train:0003']
        assert canonical_hash(requests) == m['identity']['requests_sha256']
        assert load(directory / 'summary.json')['identity_sha256'] == m['identity_sha256']
        assert load(directory / 'verification.json') == m['generation_verification']
        return m
    old_manifest = validate_raw_bindings(previous)
    validate_raw_bindings(worker)
    assert (worker / 'requests.json').read_bytes() == (previous / 'requests.json').read_bytes()
    manifest, summary, verification = [load(worker / name) for name in
                                       ['manifest.json', 'summary.json', 'verification.json']]
    assert manifest['state'] == summary['state'] == 'complete'
    assert manifest['stage'] == summary['stage'] == 'smoke'
    assert summary['n_completed'] == 4 and summary['full_split'] is False
    validate_actual_gpu(manifest, GPU)
    validate_generation_verification(verification, 'native_cache_call_parity_v2', manifest)
    rows = [json.loads(s) for s in (worker / 'generation.jsonl').read_text().splitlines()]
    old_rows = [json.loads(s) for s in (previous / 'generation.jsonl').read_text().splitlines()]
    assert len(rows) == len(old_rows) == 4
    parity = []
    for old, row in zip(old_rows, rows):
        fields = ['sample_id', 'split', 'prompt_sha256', 'question_sha256', 'fewshot_train_indices',
                  'input_token_ids_sha256', 'input_tokens', 'new_token_ids', 'output_tokens',
                  'raw_text', 'scoring_text', 'stop_reason', 'length_capped']
        assert old['identity_sha256'] == old_manifest['identity_sha256']
        assert row['identity_sha256'] == manifest['identity_sha256']
        equal = {key: old[key] == row[key] for key in fields}
        assert all(equal.values()), equal
        parity.append({'sample_id': row['sample_id'], 'all_prompt_tokens_and_raw_generation_equal': True,
                       'output_tokens': row['output_tokens'],
                       'native_generation_seconds': row['elapsed_seconds'],
                       'actual_before_plus_after_guard_seconds': row['performance_timing']['integrity_total_seconds'],
                       'actual_sample_before_commit_seconds': row['performance_timing']['sample_before_commit_seconds']})
    ids = [row['sample_id'] for row in rows]
    validate_integrity_evidence(worker, manifest, 'checkpoint_static_content_v1', sample_ids=ids,
                                expected_gpu=GPU, summary=summary, expected_implementation=METHOD)
    validate_integrity_evidence(previous, old_manifest, 'checkpoint_static_content_v1', sample_ids=ids,
                                expected_gpu=GPU, summary=load(previous / 'summary.json'), expected_implementation=None)
    new_integrity, old_integrity = load(worker / 'integrity.json'), load(previous / 'integrity.json')
    assert new_integrity['baseline_manifest'] == old_integrity['baseline_manifest']
    assert new_integrity['baseline_root_sha256'] == old_integrity['baseline_root_sha256']
    assert [p['label'] for p in new_integrity['phase_checks']] == [p['label'] for p in old_integrity['phase_checks']]
    assert len(new_integrity['phase_checks']) == 15
    assert all(p['exact'] and p['complete'] for p in new_integrity['phase_checks'])
    old_verification = load(previous / 'verification.json')
    for old, row in zip(old_verification['records'], verification['records']):
        assert old['repeatability_prefix_32_token_ids'] == row['repeatability_prefix_32_token_ids']
    # completed_at is recorded by generate_one before the postcheck in both
    # versions. Successive gaps include previous postcheck + next precheck +
    # next generation and persistence. Use the same observable for both.
    def gaps(values):
        dates = [datetime.fromisoformat(row['completed_at']) for row in values]
        return [(b-a).total_seconds() for a,b in zip(dates,dates[1:])]
    old_gap, new_gap = gaps(old_rows), gaps(rows)
    old_summary = load(previous / 'summary.json')
    return {'case': case, 'scope': 'observed_shared_four_train_question_speed_diagnostic_not_ACC',
            'exclusive_verified': False, 'formal_progression_eligible': False,
            'baseline_resource_caveat': 'R003 baseline was earlier on same GPU/driver; current run shares GPU0 with yqh. Observed speed ratios are not a controlled exclusive throughput qualification.',
            'baseline_worker': str(previous), 'new_worker': str(worker),
            'manifest_sha256': digest(worker / 'manifest.json'),
            'summary_sha256': digest(worker / 'summary.json'),
            'canonical_identities_and_all_declared_artifact_hashes_checked': True,
            'fixed_four_requests_byte_identical_to_baseline': True,
            'token_and_text_parity': parity,
            'same_two_native_verification_32_token_prefixes': True,
            'same_complete_static_baseline_and_root': True,
            'unchanged_15_phase_order_and_all_exact': True,
            'old_completion_gaps_seconds': old_gap, 'new_completion_gaps_seconds': new_gap,
            'old_median_completion_gap_seconds': statistics.median(old_gap),
            'new_median_completion_gap_seconds': statistics.median(new_gap),
            'observed_steady_cycle_speedup': statistics.median(old_gap) / statistics.median(new_gap),
            'old_worker_wall_seconds': old_summary['elapsed_seconds'],
            'new_worker_wall_seconds': summary['elapsed_seconds'],
            'observed_short_worker_wall_speedup': old_summary['elapsed_seconds']/summary['elapsed_seconds'],
            'old_native_generation_total_seconds': sum(r['elapsed_seconds'] for r in old_rows),
            'new_native_generation_total_seconds': sum(r['elapsed_seconds'] for r in rows),
            'new_timing_breakdown': summary['performance_timing'],
            'new_peak_memory_reserved_bytes': summary['peak_memory_reserved_bytes'],
            'immutable_capture_bytes': new_integrity['immutable_runtime_baseline']['unique_immutable_baseline_bytes']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('bf16', 'a8w4_fp32'), required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'checked_at': now(), 'result': analyze(args.case, args.worker.resolve())}
    write_new(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
