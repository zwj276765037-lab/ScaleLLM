#!/usr/bin/env python3

import json
import math
import unittest
from pathlib import Path

from model.mlp_fixed import (
    FULL_FORMAT_ID, MLP_DOWN_ACCUM_WIDTH, MLP_DOWN_GUARD_WIDTH,
    MLP_DOWN_OUTPUT_WIDTH, MLP_DOWN_TOTAL_SHIFT_MIN, MLP_FORMAT_ID,
    MLP_GATE_UP_ACCUM_WIDTH, MLP_GATE_UP_GUARD_WIDTH,
    MLP_GATE_UP_TOTAL_SHIFT_MIN, MLP_RAW_S33_ABS_MAX, MLP_TOTAL_SHIFT_MAX,
    SILU_LIMIT_Q16, S32_MAX, S32_MIN,
    a8w4_group32_two_column,
    a8w4_two_column_packed,
    architecture_summary, build_silu_lut,
    hadamard32_product_normalized,
    minmax_a8_quantize_s35, mlp_recover_down_guard_s45,
    mlp_recover_guard_s37,
    round_shift_away_zero, silu_lut_q16, swiglu_product_s32,
)
from model.v5_schedule_contract import (
    LAYERS, SWIGLU_XSIM_MAX_GROUP_INTERVAL, build_v5_layer_model,
)


class MLPFixedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = build_silu_lut()

    def test_round_half_away(self):
        self.assertEqual(round_shift_away_zero(32768, 16), 1)
        self.assertEqual(round_shift_away_zero(-32768, 16), -1)
        self.assertEqual(round_shift_away_zero(32767, 16), 0)
        self.assertEqual(round_shift_away_zero(-32767, 16), 0)

    def test_silu_boundaries(self):
        self.assertEqual(silu_lut_q16(-SILU_LIMIT_Q16, self.table), 0)
        self.assertEqual(silu_lut_q16(SILU_LIMIT_Q16, self.table),
                         SILU_LIMIT_Q16)
        self.assertEqual(silu_lut_q16(0, self.table), 0)

    def test_swiglu_simple(self):
        # SiLU(0)=0 and SiLU(+16) uses the positive bypass.
        self.assertEqual(swiglu_product_s32(0, 1 << 16, self.table), 0)
        self.assertEqual(swiglu_product_s32(16 << 16, 2 << 16,
                                            self.table), 32 << 16)

    def test_a8w4_two_column_packed_exhaustive(self):
        for activation in range(-255, 256):
            for weight0 in range(-8, 8):
                for weight1 in range(-8, 8):
                    got0, got1 = a8w4_two_column_packed(
                        activation, weight0, weight1)
                    self.assertEqual(got0, activation * weight0)
                    self.assertEqual(got1, activation * weight1)

    def test_a8w4_group32_two_column_boundaries(self):
        dot0, dot1 = a8w4_group32_two_column(
            [-255] * 32, [-8] * 32, [7] * 32)
        self.assertEqual(dot0, 65_280)
        self.assertEqual(dot1, -57_120)
        dot0, dot1 = a8w4_group32_two_column(
            [255] * 32, [-8] * 32, [7] * 32)
        self.assertEqual(dot0, -65_280)
        self.assertEqual(dot1, 57_120)

    def test_architecture_model(self):
        item = architecture_summary()
        schedule = build_v5_layer_model()
        self.assertEqual(item["schema"],
                         "hap_attention_mlp_architecture_model_v3")
        self.assertEqual(item["cohort"]["logical_rows"], 16)
        self.assertEqual(item["cohort"]["active_rows"], 32)
        self.assertEqual(item["clock_hz"], 100_000_000)
        self.assertEqual(item["attention"]["projection_dsp48e2"], 2_240)
        self.assertEqual(item["mlp"]["kernel_dsp48e2"], 3_072)
        self.assertEqual(item["mlp"]["compact_input_dsp48e2"], 8)
        self.assertEqual(item["mlp"]["columns"], 12)
        self.assertEqual(item["mlp"]["full_format_id"], 0x4838_4605)
        self.assertEqual(item["mlp"]["gate_up_legal_total_shift"],
                         [20, 44])
        self.assertEqual(item["mlp"]["down_legal_total_shift"], [12, 44])
        self.assertEqual(item["mlp"]["gate_up_group_guard_width"], 37)
        self.assertEqual(item["mlp"]["down_group_guard_width"], 45)
        self.assertEqual(item["mlp"]["gate_up_accumulator_width"], 44)
        self.assertEqual(item["mlp"]["down_accumulator_width"], 54)
        self.assertEqual(item["mlp"]["down_output_width"], 32)
        self.assertEqual(item["mlp"]["swiglu_xsim_max_group_interval"],
                         SWIGLU_XSIM_MAX_GROUP_INTERVAL)
        self.assertEqual(
            item["throughput"]["mlp_stage"]["cycles_32layer_cohort16"],
            schedule.serial_mlp_cycles_per_layer * LAYERS)
        self.assertEqual(item["weights"]["matrix_bytes_32layer"],
                         3_968 * (1 << 20))
        self.assertTrue(item["weights"]["all_matrix_payload_resident"])
        self.assertFalse(item["weights"]["external_ddr_format_changed"])
        self.assertAlmostEqual(
            item["throughput"]["serial_diagnostic"]["tokens_per_second"],
            35.59, places=2)
        self.assertAlmostEqual(
            item["throughput"]["dual_cohort_pipeline"]["tokens_per_second"],
            70.58, places=2)
        targets = item["ddr_roofline"]["targets"]
        self.assertAlmostEqual(targets[0]["useful_gbps"], 15.603,
                               places=3)
        self.assertAlmostEqual(targets[1]["useful_gbps"], 16.903,
                               places=3)
        self.assertAlmostEqual(targets[2]["useful_gbps"], 18.203,
                               places=3)
        self.assertFalse(item["board_measured"])

    def test_checked_in_architecture_json_matches_model(self):
        path = Path(__file__).resolve().parents[1] / \
            "data" / "attention_mlp_architecture.json"
        with path.open(encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), architecture_summary())

    def test_v5_format_ids(self):
        self.assertEqual(MLP_FORMAT_ID, 0x4838_4D05)
        self.assertEqual(FULL_FORMAT_ID, 0x4838_4605)

    def test_v5_gate_up_and_down_recovery_contracts(self):
        self.assertEqual(MLP_GATE_UP_TOTAL_SHIFT_MIN, 20)
        self.assertEqual(MLP_DOWN_TOTAL_SHIFT_MIN, 12)
        self.assertEqual(MLP_TOTAL_SHIFT_MAX, 44)
        self.assertEqual(MLP_GATE_UP_GUARD_WIDTH, 37)
        self.assertEqual(MLP_DOWN_GUARD_WIDTH, 45)
        self.assertEqual(MLP_GATE_UP_ACCUM_WIDTH, 44)
        self.assertEqual(MLP_DOWN_ACCUM_WIDTH, 54)
        self.assertEqual(MLP_DOWN_OUTPUT_WIDTH, 32)
        max_guard = mlp_recover_guard_s37(MLP_RAW_S33_ABS_MAX, 20)
        self.assertEqual(max_guard, 67_917_312_000)
        self.assertGreater(max_guard, (1 << 35) - 1)
        self.assertLessEqual(max_guard, (1 << 36) - 1)

        raw_s33 = 32 * 100 * 141
        guard = mlp_recover_guard_s37(raw_s33, 20)
        self.assertEqual(guard, 7_219_200)
        self.assertEqual(round_shift_away_zero(2 * guard, 8), 56_400)
        with self.assertRaisesRegex(ValueError, r"\[20,44\]"):
            mlp_recover_guard_s37(raw_s33, 19)

        down_max_guard = mlp_recover_down_guard_s45(
            MLP_RAW_S33_ABS_MAX, 12)
        self.assertEqual(down_max_guard, 17_386_831_872_000)
        self.assertLessEqual(down_max_guard, (1 << 44) - 1)
        for shift in range(12, 20):
            self.assertNotEqual(mlp_recover_down_guard_s45(raw_s33, shift), 0)
        with self.assertRaisesRegex(ValueError, r"\[12,44\]"):
            mlp_recover_down_guard_s45(raw_s33, 11)
        with self.assertRaisesRegex(ValueError, r"\[12,44\]"):
            mlp_recover_down_guard_s45(raw_s33, 45)

    def test_product_hadamard_boundaries(self):
        impulse = hadamard32_product_normalized([S32_MAX] + [0] * 31)
        self.assertEqual(impulse.saturation_count, 0)
        self.assertEqual(len(set(impulse.values)), 1)
        all_max = hadamard32_product_normalized([S32_MAX] * 32)
        self.assertEqual(all_max.saturation_count, 0)
        self.assertTrue(all_max.values[0] > 0)
        self.assertEqual(all_max.values[1:], (0,) * 31)
        all_min = hadamard32_product_normalized([S32_MIN] * 32)
        self.assertEqual(all_min.saturation_count, 0)
        self.assertTrue(all_min.values[0] < 0)

    def test_product_a8_s35_boundaries(self):
        self.assertEqual(minmax_a8_quantize_s35([0] * 32).metadata, 0)
        item = minmax_a8_quantize_s35(
            [-(16384 << 16) if lane & 1 else (16384 << 16)-1
             for lane in range(32)])
        self.assertTrue(all(0 <= value <= 255 for value in item.values))
        self.assertTrue(0 <= item.scale_shift <= 63)
        full_range = minmax_a8_quantize_s35(
            [-(1 << 34) if lane & 1 else (1 << 34)-1
             for lane in range(32)])
        self.assertEqual((full_range.scale_code, full_range.scale_shift),
                         (255, 0))
        self.assertEqual(set(full_range.values), {0, 255})


if __name__ == "__main__":
    unittest.main()
