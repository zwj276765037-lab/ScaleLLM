from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from exact_oracle import decode_fraction
from linear_recovery import evaluate_linear_sample
from metrics import summarize_results


def group(dot, total=25, code_a=1, code_w=1):
    return dict(dot=dot, act_code=code_a, act_shift=total // 2,
                weight_code=code_w, weight_shift=total - total // 2)


def sample(groups=None, profile='mlp_gate_up'):
    return dict(schema_version=1, sample_id='test', kernel='linear_recovery', profile=profile,
                groups=groups or [group(1)], provenance=dict(kind='synthetic', model=None, layer=None,
                op=None, source_files=[], source_format_id=None))


class MetricsTests(unittest.TestCase):
    def test_known_negative_bias_and_lsb_error(self):
        row = evaluate_linear_sample(sample([group(-255), group(-1)]))
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['output_only']['output_code'], -1)
        self.assertEqual(row['current']['output_code'], -1)
        self.assertEqual(row['metrics']['signed_error_current_vs_exact'], -1 / (1 << 17))
        self.assertEqual(row['metrics']['lsb_error_current_vs_exact'], -.5)
        self.assertFalse(row['metrics']['bounds']['violation_vs_exact'])
        # Positive tiny terms cross a half boundary only if they are summed first.
        row = evaluate_linear_sample(sample([group(255), group(1)]))
        self.assertEqual(row['output_only']['output_code'], 1)
        self.assertEqual(row['current']['output_code'], 0)
        self.assertEqual(row['metrics']['lsb_error_current_vs_output_only'], -1)

    def test_remainder_tightening_and_exact_bound(self):
        row = evaluate_linear_sample(sample([group(256), group(0)]))
        metrics = row['metrics']
        self.assertEqual(metrics['g_right'], 2)
        self.assertEqual(metrics['g_nonzero_remainder'], 0)
        self.assertEqual(decode_fraction(metrics['bounds']['tight_vs_exact']), Fraction(1, 1 << 17))

    def test_provenance_legacy_is_separate_from_theorem_eligibility(self):
        source = sample()
        source['provenance'].update(kind='real_trace', model='Llama-3.1-8B-Instruct',
                                    layer=0, op='q_proj', source_format_id='0x48384604')
        row = evaluate_linear_sample(source)
        self.assertEqual(row['status'], 'ok')
        self.assertTrue(row['metrics']['bounds']['applicable'])
        self.assertEqual(row['provenance_status'], 'legacy_input_replay')

    def test_syntax_does_not_coerce_float_or_bool(self):
        for key in ('dot', 'act_code', 'act_shift', 'weight_code', 'weight_shift'):
            for value in (True, 1.0, '1'):
                source = sample()
                source['groups'][0][key] = value
                self.assertEqual(evaluate_linear_sample(source)['status'], 'invalid_input')
        for source in (None, [], {'profile': {}}, {'profile': []}):
            self.assertEqual(evaluate_linear_sample(source)['status'], 'invalid_input')

    def test_physical_dot_limits_and_illegal_shift_excluded(self):
        for profile, limit in (('attention', 1036320), ('mlp_gate_up', 65280), ('mlp_down', 65280)):
            for sign in (-1, 1):
                source = sample([group(sign * (limit + 1), 30)], profile)
                row = evaluate_linear_sample(source)
                self.assertEqual(row['status'], 'out_of_contract')
                self.assertEqual(row['current']['error_counts']['dot_range'], 1)
                self.assertIsNone(row['metrics']['bounds']['violation_vs_exact'])
        row = evaluate_linear_sample(sample([group(1, 19)]))
        self.assertEqual(row['status'], 'out_of_contract')
        self.assertIsNone(row['current']['output_code'])
        self.assertIn('invalid_active_shift', row['metrics']['bounds']['excluded_reasons'])

    def test_inactive_code_metadata_hint_and_bounded_shift_validation(self):
        source = sample([dict(dot=0, act_code=0, act_shift=1, weight_code=1, weight_shift=20)])
        row = evaluate_linear_sample(source)
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['current']['metadata_hints']['zero_code_nonzero_shift'], 1)
        self.assertTrue(row['metrics']['bounds']['applicable'])
        source['groups'][0]['act_shift'] = 10**50
        row = evaluate_linear_sample(source)
        self.assertEqual(row['status'], 'out_of_contract')
        self.assertEqual(row['current']['error_counts']['metadata_range'], 1)

    def test_saturation_and_accumulator_overflow_have_separate_counts(self):
        row = evaluate_linear_sample(sample([group(65280, 20, 255, 255)]))
        self.assertEqual(row['current']['error_counts']['output_saturation'], 1)
        self.assertEqual(row['current']['error_counts']['accumulator_overflow'], 0)
        self.assertTrue(row['output_only']['saturated'])
        self.assertFalse(row['metrics']['bounds']['applicable'])

    def test_summary_keeps_denominators_bias_zero_nmse_and_histogram(self):
        zero = evaluate_linear_sample(sample([group(0)]))
        changed = evaluate_linear_sample(sample([group(255), group(1)]))
        invalid = evaluate_linear_sample(sample([group(1, 19)]))
        saturated = evaluate_linear_sample(sample([group(65280, 20, 255, 255)]))
        result = summarize_results([zero, changed, invalid, saturated])
        overall = result['overall']
        self.assertEqual(overall['sample_count'], 4)
        self.assertEqual(overall['bound_eligible_count'], 2)
        self.assertEqual(overall['bound_excluded_count'], 2)
        self.assertEqual(overall['status_counts'], {'ok': 2, 'out_of_contract': 2, 'invalid_input': 0})
        stats = overall['statistics']['eligible']['current_vs_output_only']
        self.assertEqual(stats['signed_mean'], -1 / (1 << 17))
        hist = overall['statistics']['eligible']['output_code_comparison']
        self.assertEqual(hist['signed_lsb_histogram'], {'-1': 1, '0': 1})
        self.assertEqual(hist['identical_fraction'], .5)
        zero_stats = summarize_results([zero])['overall']['statistics']['eligible']['current_vs_exact']
        self.assertIsNone(zero_stats['nmse'])
        self.assertFalse(zero_stats['nmse_defined'])
        json.dumps(result, allow_nan=False)

    def test_huge_out_of_contract_error_has_exact_fraction_and_no_nonfinite_json(self):
        row = evaluate_linear_sample(sample([group(10**400, 20)]))
        self.assertEqual(row['status'], 'out_of_contract')
        self.assertIsNone(row['metrics']['signed_error_current_vs_exact'])
        self.assertIn('signed_error_current_vs_exact', row['metrics']['exact_fractions'])
        json.dumps(row, allow_nan=False)
        json.dumps(summarize_results([row]), allow_nan=False)

    def test_deterministic_valid_samples_never_exceed_both_theorems(self):
        rng = random.Random(20261019)
        for profile, min_shift in (('attention', 26), ('mlp_gate_up', 20), ('mlp_down', 12)):
            for _ in range(200):
                # Keep magnitudes unsaturated while exercising positive/negative cancellation.
                groups = [group(rng.randrange(-1000, 1001), rng.randrange(max(24, min_shift), 45),
                                rng.randrange(1, 16), rng.randrange(1, 16)) for _ in range(rng.randrange(1, 90))]
                row = evaluate_linear_sample(sample(groups, profile))
                self.assertEqual(row['status'], 'ok')
                self.assertFalse(row['metrics']['bounds']['violation_vs_exact'])
                self.assertFalse(row['metrics']['bounds']['violation_vs_output_only'])
                self.assertFalse(row['metrics']['bounds']['tight_violation_vs_exact'])
                self.assertFalse(row['metrics']['bounds']['tight_violation_vs_output_only'])


    def test_group_resource_limit_and_optional_lane_evidence(self):
        self.assertEqual(evaluate_linear_sample(sample([group(0)] * 4097))["status"], "invalid_input")
        source = sample([group(-32)])
        source["groups"][0]["lane_evidence"] = dict(q_a=[1] * 32, q_w=[-1] * 32, zero_point=0)
        row = evaluate_linear_sample(source)
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["lane_verification"]["verified_groups"], 1)
        source["groups"][0]["dot"] = 0
        row = evaluate_linear_sample(source)
        self.assertEqual(row["status"], "out_of_contract")
        self.assertEqual(row["current"]["error_counts"]["lane_dot_mismatch"], 1)
        source["groups"][0]["lane_evidence"]["q_w"][0] = 8
        row = evaluate_linear_sample(source)
        self.assertEqual(row["current"]["error_counts"]["lane_domain"], 1)
        source["groups"][0]["lane_evidence"]["q_a"][0] = True
        self.assertEqual(evaluate_linear_sample(source)["status"], "invalid_input")

    def test_exact_truncation_identity_and_loss_bound(self):
        row = evaluate_linear_sample(sample([group(-3), group(2), group(1, 26)]))
        metrics = row["metrics"]
        loss = Fraction(1, 1 << 25) + Fraction(1, 1 << 26)
        self.assertEqual(decode_fraction(metrics["truncation_loss_D"]), loss)
        self.assertEqual(decode_fraction(metrics["pre_output_signed_error"]), -loss)
        self.assertTrue(metrics["truncation_identity_holds"])
        self.assertEqual(decode_fraction(metrics["bounds"]["tight_vs_exact"]), loss + Fraction(1, 1 << 17))

    def test_declared_real_source_never_self_certifies_and_bf16_separate(self):
        source = sample([group(0)] * 128)
        source["provenance"].update(kind="real_trace", model="Llama-3.1-8B-Instruct", layer=0,
                                    op="gate_proj", source_format_id="0x48384605", trajectory="v5_production",
                                    source_files=[dict(path="input.jsonl", sha256="0" * 64)])
        row = evaluate_linear_sample(source)
        self.assertFalse(row["eligible_current_format_evidence"])
        self.assertEqual(row["provenance_reasons"], ["source_identity_not_verified"])
        source["provenance"]["trajectory"] = "bf16"
        self.assertEqual(evaluate_linear_sample(source)["provenance_status"], "bf16_trajectory_local_replay")

    def test_all_invalid_or_empty_summary_has_null_error_statistics(self):
        for rows in ([], [evaluate_linear_sample(None)]):
            summary = summarize_results(rows)["overall"]
            self.assertEqual(summary["bound_eligible_count"], 0)
            self.assertIsNone(summary["statistics"]["eligible"]["current_vs_exact"]["signed_mean"])
            self.assertIsNone(summary["statistics"]["eligible"]["output_code_comparison"]["identical_fraction"])


if __name__ == '__main__':
    unittest.main()
