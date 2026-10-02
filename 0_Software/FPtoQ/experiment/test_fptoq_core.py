#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

from fptoq_core import (
    GROUP_SIZE,
    Q_SCALE,
    compare_groups,
    fp_to_s24_q16,
    fp_to_s32_q16,
    hardware_a8_qdq,
    hardware_hadamard_s24,
    hardware_hadamard_s32,
    software_hadamard,
)
from run_experiment import run_analysis


class FPToQCoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).resolve().parents[3] / "model" / "fixbit_v2.py"
        spec = importlib.util.spec_from_file_location("scalellm_fixbit_v2", path)
        assert spec is not None and spec.loader is not None
        cls.reference = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.reference
        spec.loader.exec_module(cls.reference)

        mlp_path = Path(__file__).resolve().parents[3] / "model" / "mlp_fixed.py"
        mlp_spec = importlib.util.spec_from_file_location("scalellm_mlp_fixed", mlp_path)
        assert mlp_spec is not None and mlp_spec.loader is not None
        cls.mlp_reference = importlib.util.module_from_spec(mlp_spec)
        sys.modules[mlp_spec.name] = cls.mlp_reference
        mlp_spec.loader.exec_module(cls.mlp_reference)

    def test_host_rounding_and_saturation(self) -> None:
        values = np.zeros((1, GROUP_SIZE), dtype=np.float64)
        values[0, :8] = [
            -200.0, -128.0, -1.5 / Q_SCALE, -0.5 / Q_SCALE,
            0.5 / Q_SCALE, 1.5 / Q_SCALE, 127.0, 200.0,
        ]
        raw, saturated = fp_to_s24_q16(values)
        self.assertEqual(
            raw[0, :8].tolist(),
            [-(1 << 23), -(1 << 23), -2, -1, 1, 2, 127 * Q_SCALE,
             (1 << 23) - 1],
        )
        self.assertEqual(int(saturated.sum()), 2)

    def test_hadamard_matches_canonical_bit_exact_model(self) -> None:
        rng = np.random.default_rng(20260911)
        raw = rng.integers(-(1 << 20), 1 << 20, size=(64, GROUP_SIZE),
                           dtype=np.int64)
        actual, saturated = hardware_hadamard_s24(raw)
        self.assertFalse(np.any(saturated))
        for row, result in zip(raw, actual, strict=True):
            expected = self.reference.hadamard32_normalized(row.tolist())
            self.assertEqual(result.tolist(), list(expected.values))
            self.assertEqual(expected.saturation_count, 0)

    def test_a8_matches_canonical_bit_exact_model(self) -> None:
        rng = np.random.default_rng(20260912)
        raw = rng.integers(-(1 << 22), 1 << 22, size=(128, GROUP_SIZE),
                           dtype=np.int64)
        actual = hardware_a8_qdq(raw)
        for index, row in enumerate(raw):
            expected = self.reference.minmax_a8_quantize(row.tolist())
            self.assertEqual(actual.q[index].tolist(), list(expected.values))
            self.assertEqual(int(actual.scale_code[index]), expected.scale_code)
            self.assertEqual(int(actual.scale_shift[index]), expected.scale_shift)
            self.assertEqual(int(actual.zero_point[index]), expected.zero_point)

    def test_orthogonal_transform_preserves_preq_l2_error(self) -> None:
        rng = np.random.default_rng(20260913)
        source = rng.normal(size=(1024, GROUP_SIZE))
        raw, _ = fp_to_s24_q16(source)
        fixed = raw / Q_SCALE
        before = np.linalg.norm(fixed - source, axis=1)
        after = np.linalg.norm(
            software_hadamard(fixed) - software_hadamard(source), axis=1)
        np.testing.assert_allclose(after, before, rtol=1e-10, atol=1e-14)

    def test_derived_l2_bound_has_no_violation(self) -> None:
        rng = np.random.default_rng(20260914)
        source = rng.uniform(-127.99, 127.99, (4096, GROUP_SIZE))
        summary = compare_groups(source)
        self.assertEqual(summary["input_saturation_elements"], 0)
        self.assertEqual(summary["hadamard_saturation_elements"], 0)
        self.assertEqual(summary["theorem_checked_groups"], source.shape[0])
        self.assertEqual(summary["theorem_violation_groups"], 0)

    def test_torch_rtl_frontend_matches_numpy(self) -> None:
        try:
            import torch
            from torch_frontend import rtl_activation_qdq
        except ImportError:
            self.skipTest("PyTorch is not installed")
        rng = np.random.default_rng(20260915)
        source = rng.normal(0.0, 3.0, (257, GROUP_SIZE)).astype(np.float32)
        raw, _ = fp_to_s24_q16(source)
        raw_h, _ = hardware_hadamard_s24(raw)
        expected = hardware_a8_qdq(raw_h).dq.astype(np.float32)
        actual = rtl_activation_qdq(torch.from_numpy(source)).numpy()
        np.testing.assert_array_equal(actual, expected)

        # The MLP down path is S32 Q16.16 -> S35 Q19.16. In-range values have
        # identical numerics; the wider format only changes overflow limits.
        actual_s32 = rtl_activation_qdq(
            torch.from_numpy(source), input_width=32, output_width=35).numpy()
        np.testing.assert_array_equal(actual_s32, expected)

    def test_torch_s32_path_matches_mlp_bit_exact_model(self) -> None:
        try:
            import torch
            from torch_frontend import fp_to_q16_raw, rtl_activation_qdq
        except ImportError:
            self.skipTest("PyTorch is not installed")
        rng = np.random.default_rng(20260916)
        source = rng.normal(0.0, 4096.0, (32, GROUP_SIZE)).astype(np.float32)
        tensor = torch.from_numpy(source)
        raw = fp_to_q16_raw(tensor, 32).numpy()
        expected_rows = []
        for row in raw:
            transformed = self.mlp_reference.hadamard32_product_normalized(row.tolist())
            quantized = self.mlp_reference.minmax_a8_quantize_s35(transformed.values)
            scale = np.ldexp(float(quantized.scale_code), -quantized.scale_shift)
            expected_rows.append([
                (value - quantized.zero_point) * scale for value in quantized.values
            ])
        expected = np.asarray(expected_rows, dtype=np.float32)
        actual = rtl_activation_qdq(
            tensor, input_width=32, output_width=35).numpy()
        np.testing.assert_array_equal(actual, expected)

    def test_capture_analysis_routes_large_down_proj_input_to_s32(self) -> None:
        groups = np.zeros((2, GROUP_SIZE), dtype=np.float64)
        groups[0] = np.linspace(-1.0, 1.0, GROUP_SIZE)
        # This cannot fit S24 Q8.16 (real range ends just below +128), but it
        # comfortably fits the down_proj S32 Q16.16 contract.
        groups[1, :4] = [4096.0, -4096.0, 8192.0, -8192.0]
        labels = np.asarray(["q_proj", "down_proj"], dtype="U16")

        raw_s24, saturated_s24 = fp_to_s24_q16(groups[1:])
        self.assertGreater(int(saturated_s24.sum()), 0)
        raw_s32, saturated_s32 = fp_to_s32_q16(groups[1:])
        self.assertEqual(int(saturated_s32.sum()), 0)
        actual_h, actual_h_saturation = hardware_hadamard_s32(raw_s32)
        self.assertEqual(int(actual_h_saturation.sum()), 0)
        self.assertGreater(np.max(np.abs(actual_h)), (1 << 26) - 1)
        self.assertTrue(np.all(np.abs(raw_s24) <= (1 << 23)))
        expected_h = self.mlp_reference.hadamard32_product_normalized(
            raw_s32[0].tolist())
        self.assertEqual(actual_h[0].tolist(), list(expected_h.values))
        expected_a8 = self.mlp_reference.minmax_a8_quantize_s35(
            expected_h.values)
        actual_a8 = hardware_a8_qdq(actual_h)
        self.assertEqual(actual_a8.q[0].tolist(), list(expected_a8.values))
        self.assertEqual(int(actual_a8.scale_code[0]), expected_a8.scale_code)
        self.assertEqual(int(actual_a8.scale_shift[0]), expected_a8.scale_shift)
        self.assertEqual(int(actual_a8.zero_point[0]), expected_a8.zero_point)

        with tempfile.TemporaryDirectory() as directory:
            manifest = run_analysis(
                groups,
                labels,
                output_dir=Path(directory),
                source="unit-test mixed captured trace",
                seed=None,
            )

        rows = {row["slice"]: row for row in manifest["rows"]}
        down = rows["down_proj"]
        self.assertEqual(down["format_profile"], "S32 Q16.16 -> S35 Q19.16")
        self.assertEqual(down["s32_to_s35_groups"], 1)
        self.assertEqual(down["input_saturation_elements"], 0)
        self.assertLessEqual(down["input_fp_to_q16_max_abs"], 0.5 / Q_SCALE)

        overall = rows["__all__"]
        self.assertIn("mixed:", overall["format_profile"])
        self.assertEqual(overall["s24_to_s27_groups"], 1)
        self.assertEqual(overall["s32_to_s35_groups"], 1)
        self.assertEqual(overall["input_saturation_elements"], 0)


if __name__ == "__main__":
    unittest.main()
