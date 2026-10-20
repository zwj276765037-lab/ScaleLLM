#!/usr/bin/env python3
"""Independent, CPU-only checks; deliberately never opens answer artifacts."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'project/software/0_Software/rounding_precision/experiment/response_quality'
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = [SOURCE / name for name in ('generation_core.py', 'cached_adapter.py', 'run_generation.py')]
    before = {str(p.relative_to(ROOT)): sha(p) for p in files}
    spec = importlib.util.spec_from_file_location('independent_generation_controls', SOURCE / 'generation_core.py')
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def decode(sequence):
        seen = []
        def step(prefix, first):
            seen.append((list(prefix), first))
            return sequence[len(seen)-1], {}
        answer = core.decode_arm([10, 20], step, {99}, 4, 256)
        return answer, seen

    a, seen_a = decode([31, 99])
    b, seen_b = decode([32, 33, 34, 35])
    check('stop_token_retained_and_immediate', a['generated_token_ids'] == [31, 99] and len(seen_a) == 2)
    check('natural_stop_not_truncation', a['eos_seen'] and not a['truncated'])
    check('other_arm_keeps_full_common_budget', b['generated_token_ids'] == [32, 33, 34, 35] and b['truncated'])
    check('identical_initial_prompt', seen_a[0][0] == seen_b[0][0] == [10, 20])
    check('independent_free_prefix_after_divergence', seen_a[1][0] == [10, 20, 31] and seen_b[1][0] == [10, 20, 32])
    check('first_flag_only_initial_step', seen_b[0][1] and not any(x[1] for x in seen_b[1:]))
    check('first_divergence_reported', core.pair_summary(a, b)['first_divergence_index'] == 0)
    check('identical_sequences_reported', core.pair_summary(a, a)['identical_token_sequences'])
    try:
        core.generation_budget(253, 256, 4)
    except ValueError:
        checks.append('insufficient_full_budget_rejected_without_truncation')
    else:
        raise AssertionError('budget was silently reduced')

    # Loose integer bounds intentionally avoid relying on softmax mass sums.
    context = 32768
    raw_qk = (1 << 23) * 2047 * 32 * 255 * 5793
    pv_product = 65535 * 2047 * 255
    bounds = dict(context_keys=context,
        qk_integer_dot_abs=(1 << 23) * 2047 * 32,
        qk_scaled_abs=raw_qk,
        qk_exact_remainder_sum_exclusive=4 * (1 << 50),
        pv_product_abs=pv_product,
        pv_current_sum_abs=context * pv_product,
        pv_exact_quotient_sum_abs=context * pv_product,
        pv_exact_remainder_sum_exclusive=context * (1 << 32),
        softmax_current_row_sum=context * 65536,
        softmax_exact_row_sum=context * (65536 << 10),
        softmax_exact_numerator_max=(65536 << 10) << 16,
        int64_max=(1 << 63)-1)
    check('all_sequence_dependent_integer_bounds_fit_int64', all(
        value < (1 << 63) for key, value in bounds.items() if key not in ('int64_max',)))
    check('qk_dot_exact_in_fp64', bounds['qk_integer_dot_abs'] < (1 << 53))
    # The reference reciprocal-round=False branch uses integer division. The
    # current branch has exponent<=65536 and reciprocal<=65536, product<=2^32.
    bounds['softmax_current_exponent_times_reciprocal_max'] = 1 << 32
    bounds['pv_one_int64_temporary_bytes_q128_k32768_headchunk4'] = 128 * context * 4 * 32 * 8
    after = {str(p.relative_to(ROOT)): sha(p) for p in files}
    check('reviewed_sources_unchanged_during_cpu_checks', before == after)
    result = dict(schema='independent_response_quality_cpu_controls_v1',
        created_at=datetime.now(timezone.utc).isoformat(), execution_state='completed',
        passed=True, checks=checks, source_sha256=before, bounds=bounds,
        runtime_identity='collaboration:/root/rounding_optimization_runner',
        desired_model='gpt-6.1-sol', desired_effort='xhigh', actual_model='unverified',
        scope='CPU control semantics and conservative integer bounds; no GPU, no model inference, no answers or anonymous maps read',
        limitations=['Not a cache arithmetic qualification', 'Not GPU memory admission',
                     'No generated-response quality judgment', 'Sources may still be under implementation'])
    destination = OUT / 'cpu_controls_result.json'
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps(dict(passed=True, checks=len(checks), path=str(destination), bounds=bounds)))


if __name__ == '__main__':
    main()
