#!/usr/bin/env python3
"""Directed regression for the experiment-local Min/Max A8 contract."""
from __future__ import annotations

import random
import unittest

import minmax_a8


class MinMaxA8Test(unittest.TestCase):
    def test_zero(self) -> None:
        result = minmax_a8.quantize_s27([0] * 32)
        self.assertEqual(result.values, (0,) * 32)
        self.assertEqual(result.metadata, 0)

    def test_same_positive_and_negative(self) -> None:
        positive = minmax_a8.quantize_s27([12345] * 32)
        negative = minmax_a8.quantize_s27([-12345] * 32)
        self.assertEqual((positive.low, positive.high), (0, 12345))
        self.assertEqual(positive.values, (255,) * 32)
        self.assertEqual((negative.low, negative.high), (-12345, 0))
        self.assertEqual(negative.zero_point, 255)
        self.assertEqual(negative.values, (0,) * 32)

    def test_notice_counterexample(self) -> None:
        values = [-2965760, 5746160] + [0] * 30
        result = minmax_a8.quantize_s27(values)
        self.assertEqual(result.low, -2965760)
        self.assertEqual(result.high, 5746160)
        self.assertEqual(result.high - result.low, 8711920)

    def test_single_outliers_are_not_clipped(self) -> None:
        positive = minmax_a8.quantize_s27([1] * 31 + [1 << 25])
        negative = minmax_a8.quantize_s27([-1] * 31 + [-(1 << 25)])
        self.assertEqual(positive.high, 1 << 25)
        self.assertEqual(negative.low, -(1 << 25))

    def test_half_ties_are_even(self) -> None:
        self.assertEqual(minmax_a8.round_div_even(1, 2), 0)
        self.assertEqual(minmax_a8.round_div_even(3, 2), 2)
        self.assertEqual(minmax_a8.round_div_even(5, 2), 2)
        self.assertEqual(minmax_a8.round_signed_ratio_even(-3, 2), -2)

    def test_lane_half_tie_rounds_complete_affine_expression(self) -> None:
        result = minmax_a8.quantize_s27([-2, -1] + [-2] * 30)
        self.assertEqual(result.zero_point, 255)
        self.assertEqual(result.values[0], 0)
        self.assertEqual(result.values[1], 128)

    def test_s27_full_range_fits_metadata(self) -> None:
        values = [-(1 << 26), (1 << 26) - 1] + [0] * 30
        result = minmax_a8.quantize_s27(values)
        self.assertFalse(result.scale_format_overflow)

    def test_s35_full_range_reports_metadata_overflow(self) -> None:
        values = [-(1 << 34), (1 << 34) - 1] + [0] * 30
        result = minmax_a8.quantize_s35(values)
        self.assertTrue(result.scale_format_overflow)
        self.assertEqual(result.low, -(1 << 34))
        self.assertEqual(result.high, (1 << 34) - 1)

    def test_sc_and_fp_share_ideal_u8(self) -> None:
        rng = random.Random(0xA8_2026)
        for _ in range(1000):
            values = [rng.randint(-(1 << 26), (1 << 26) - 1)
                      for _ in range(32)]
            sc = minmax_a8.quantize_s27(values)
            fp, zp, _scale, low, high = minmax_a8.native_fp_a8_s27(values)
            self.assertEqual(tuple(fp), sc.values)
            self.assertEqual((zp, low, high),
                             (sc.zero_point, sc.low, sc.high))


if __name__ == "__main__":
    unittest.main()
