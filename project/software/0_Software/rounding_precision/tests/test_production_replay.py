import ast
import importlib.util
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from production_replay import PROFILES, SOFTWARE_ROOT, production_source_identity, replay_linear, _validate_scalar_expression


def load_helper(name):
    spec = importlib.util.spec_from_file_location('rounding_test_' + name, SOFTWARE_ROOT / 'model' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MLP = load_helper('mlp_fixed')
ATTN = load_helper('fixbit_v2')


def group(dot, total, act_code=1, weight_code=1):
    return dict(dot=dot, act_code=act_code, weight_code=weight_code,
                act_shift=total // 2, weight_shift=total - total // 2)


class ProductionReplayTests(unittest.TestCase):
    def test_live_source_identity_and_guard_semantics(self):
        identity = production_source_identity()
        self.assertEqual(len(identity['sha256']), 64)
        self.assertEqual(identity['guard_semantics'], 'audit_only_no_guard_wrap')
        self.assertIn('aligned', identity['expression_lines'])
        result = replay_linear({'profile': 'mlp_gate_up', 'groups': [group(1 << 60, 20)]})
        self.assertGreater(result['error_counts']['guard_overflow'], 0)
        self.assertEqual(int(result['group_trace'][0]['guard_f24_code']), 1 << 64)
        self.assertEqual(int(result['accumulator_f24_code']), 0)

    def test_mlp_random_and_endpoint_conformance_to_live_helpers(self):
        rng = random.Random(715)
        for profile, helper in (('mlp_gate_up', MLP.mlp_recover_guard_s37),
                                ('mlp_down', MLP.mlp_recover_down_guard_s45)):
            config = PROFILES[profile]
            for trial in range(160):
                groups = [group(rng.randrange(-65280, 65281),
                                [config['shift_min'], 24, 44][trial % 3] if i == 0
                                else rng.randrange(config['shift_min'], 45),
                                rng.randrange(1, 256), rng.randrange(1, 256))
                          for i in range(rng.randrange(1, 40))]
                result = replay_linear({'profile': profile, 'groups': groups})
                expected_accumulator = 0
                width = config['accumulator_width']
                for g, trace in zip(groups, result['group_trace']):
                    aligned = helper(g['dot'] * g['act_code'] * g['weight_code'],
                                     g['act_shift'] + g['weight_shift'])
                    self.assertEqual(int(trace['aligned_f24_code']), aligned)
                    unsigned = (expected_accumulator + aligned) & ((1 << width) - 1)
                    expected_accumulator = unsigned - (1 << width) if unsigned & (1 << (width - 1)) else unsigned
                expected_rounded = MLP.round_shift_away_zero(expected_accumulator, 8)
                expected_output, _ = MLP.saturate_signed(expected_rounded, config['output_width'])
                self.assertEqual(result['pre_saturation_code'], expected_rounded)
                self.assertEqual(result['output_code'], expected_output)

    def test_attention_lane_dot_and_recovery_conformance(self):
        rng = random.Random(42)
        for trial in range(180):
            acts = [rng.randrange(256) for _ in range(32)]
            weights = [rng.randrange(-127, 128) for _ in range(32)]
            zp = rng.randrange(256)
            total = (26, 47, rng.randrange(26, 48))[trial % 3]
            g = group(sum((a - zp) * w for a, w in zip(acts, weights)), total,
                      rng.randrange(1, 256), rng.randrange(1, 256))
            expected = ATTN.a8w8_group32_guard_s42(acts, weights, zp, g['act_code'],
                                                 g['act_shift'], g['weight_code'], g['weight_shift'])
            result = replay_linear({'profile': 'attention', 'groups': [g]})
            self.assertEqual(int(result['group_trace'][0]['aligned_f24_code']), expected)
            self.assertEqual(result['output_code'], ATTN.round_sat_guard_s42_to_s24(expected)[0])

    def test_signed_floor_remainder_and_inactive_codes(self):
        for dot in (-3, -2, -1, 0, 1, 2, 3):
            result = replay_linear({'profile': 'mlp_gate_up', 'groups': [group(dot, 25)]})
            trace = result['group_trace'][0]
            self.assertEqual(int(trace['aligned_f24_code']), dot // 2)
            self.assertEqual(int(trace['floor_remainder']), dot % 2)
        inactive = dict(dot=0, act_code=0, act_shift=0, weight_code=255, weight_shift=63)
        result = replay_linear({'profile': 'mlp_gate_up', 'groups': [inactive]})
        self.assertTrue(result['accepted'])
        self.assertEqual(result['g_right'], 0)

    def test_strict_invalid_shift_keeps_zero_guard_diagnostic(self):
        result = replay_linear({'profile': 'mlp_down', 'groups': [group(10, 11)]})
        self.assertFalse(result['accepted'])
        self.assertIsNone(result['output_code'])
        self.assertEqual(result['error_counts']['invalid_active_shift'], 1)
        self.assertEqual(result['diagnostic_zero_guard_raw']['output_code'], 0)

    def test_accumulator_wrap_uses_declared_width_per_step(self):
        groups = [group(65280, 20, 255, 255)] * 130
        result = replay_linear({'profile': 'mlp_gate_up', 'groups': groups})
        self.assertEqual(result['error_counts']['accumulator_overflow'], 1)
        self.assertLess(int(result['accumulator_f24_code']), 0)
        self.assertEqual(result['output_code'], -(1 << 23))


    def test_production_ast_gate_rejects_unsupported_execution(self):
        for expression in ("__import__('os')", "tl.__class__", "raw ** 10", "[raw]", "sum([1])"):
            with self.assertRaises(ValueError):
                _validate_scalar_expression(ast.parse(expression, mode="eval"))


    def test_signed_final_half_ties_and_neighbors_all_profiles(self):
        for profile in PROFILES:
            total = 26 if profile == "attention" else 24
            multiplier = 4 if profile == "attention" else 1
            for sign in (-1, 1):
                for f24_code, expected in ((127, 0), (128, 1), (129, 1)):
                    result = replay_linear({"profile": profile,
                                            "groups": [group(sign * f24_code * multiplier, total)]})
                    self.assertEqual(result["output_code"], sign * expected)
                    self.assertEqual(result["error_counts"]["output_saturation"], 0)

    def test_intermediate_wrap_survives_final_cancellation_and_order_audit(self):
        positive = group(65280, 20, 255, 255)
        negative = group(-65280, 20, 255, 255)
        grouped = replay_linear({"profile": "mlp_gate_up",
                                  "groups": [positive] * 130 + [negative] * 130})
        interleaved = replay_linear({"profile": "mlp_gate_up",
                                      "groups": [positive, negative] * 130})
        self.assertEqual(grouped["output_code"], 0)
        self.assertEqual(interleaved["output_code"], 0)
        self.assertEqual(grouped["error_counts"]["accumulator_overflow"], 2)
        self.assertEqual(interleaved["error_counts"]["accumulator_overflow"], 0)
        self.assertEqual(grouped["error_counts"]["output_saturation"], 0)


if __name__ == '__main__':
    unittest.main()
