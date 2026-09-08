#!/usr/bin/env python3

import math
import unittest

from model.mlp_fixed import (
    FULL_FORMAT_ID, MLP_FORMAT_ID, SILU_LIMIT_Q16, S32_MAX, S32_MIN,
    a8w4_group32_two_column,
    a8w4_two_column_packed,
    architecture_summary, build_silu_lut,
    hadamard32_product_normalized,
    robust_a8_quantize_s35,
    round_shift_away_zero, silu_lut_q16, swiglu_product_s32,
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
        self.assertEqual(item["schema"],
                         "hap_attention_mlp_architecture_model_v2")
        self.assertEqual(item["cohort"]["logical_rows"], 16)
        self.assertEqual(item["cohort"]["active_rows"], 32)
        self.assertEqual(item["mlp"]["kernel_dsp48e2"], 3_072)
        self.assertEqual(item["mlp"]["columns"], 12)
        self.assertEqual(item["weights"]["matrix_bytes_32layer"],
                         3_968 * (1 << 20))
        self.assertTrue(item["weights"]["all_matrix_payload_resident"])
        self.assertFalse(item["weights"]["external_ddr_format_changed"])
        self.assertAlmostEqual(
            item["throughput"]["serial_diagnostic"]["tokens_per_second"],
            60.70, places=2)
        self.assertAlmostEqual(
            item["throughput"]["dual_cohort_pipeline"]["tokens_per_second"],
            105.87, places=2)
        targets = item["ddr_roofline"]["targets"]
        self.assertAlmostEqual(targets[0]["useful_gbps"], 23.404,
                               places=3)
        self.assertAlmostEqual(targets[1]["useful_gbps"], 24.704,
                               places=3)
        self.assertAlmostEqual(targets[2]["useful_gbps"], 26.005,
                               places=3)
        self.assertFalse(item["board_measured"])

    def test_v2_format_ids(self):
        self.assertEqual(MLP_FORMAT_ID, 0x4838_4D02)
        self.assertEqual(FULL_FORMAT_ID, 0x4838_4602)

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
        self.assertEqual(robust_a8_quantize_s35([0] * 32).metadata, 0)
        item = robust_a8_quantize_s35(
            [-(16384 << 16) if lane & 1 else (16384 << 16)-1
             for lane in range(32)])
        self.assertTrue(all(0 <= value <= 255 for value in item.values))
        self.assertTrue(0 <= item.scale_shift <= 63)
        with self.assertRaises(ValueError):
            robust_a8_quantize_s35(
                [-(1 << 34) if lane & 1 else (1 << 34)-1
                 for lane in range(32)])


if __name__ == "__main__":
    unittest.main()
