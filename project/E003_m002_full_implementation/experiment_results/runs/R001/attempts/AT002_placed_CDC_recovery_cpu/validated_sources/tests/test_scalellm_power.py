#!/usr/bin/env python3

import math
from pathlib import Path
import tempfile
import time
import unittest

from host.scalellm_power import (
    FilePowerSampler,
    PowerSample,
    power_samples_for_window,
    summarize_power_samples,
)
from host.scalellm_runtime import RuntimeContractError


class ScaleLLMPowerTest(unittest.TestCase):
    def test_trapezoidal_energy_and_token_per_joule(self):
        report = summarize_power_samples(
            (
                PowerSample(1_000_000_000, 10.0),
                PowerSample(2_000_000_000, 20.0),
                PowerSample(3_000_000_000, 10.0),
            ),
            300,
            source_path=Path("/sys/test/power1_input"),
            source_label="VCU118 total input",
            scale_to_watts=1e-6,
            sample_interval_s=1.0,
        )
        self.assertEqual(report["sample_count"], 3)
        self.assertEqual(report["elapsed_ns"], 2_000_000_000)
        self.assertTrue(math.isclose(report["energy_joules"], 30.0))
        self.assertTrue(math.isclose(report["mean_watts"], 15.0))
        self.assertTrue(math.isclose(
            report["processed_tokens_per_joule"], 10.0
        ))

    def test_invalid_samples_are_rejected(self):
        common = {
            "processed_tokens": 1,
            "source_path": Path("/sys/test/power1_input"),
            "source_label": "VCU118 total input",
            "scale_to_watts": 1e-6,
            "sample_interval_s": 1.0,
        }
        with self.assertRaisesRegex(RuntimeContractError, "at least two"):
            summarize_power_samples((PowerSample(1, 10.0),), **common)
        with self.assertRaisesRegex(RuntimeContractError, "strictly increasing"):
            summarize_power_samples(
                (PowerSample(2, 10.0), PowerSample(2, 10.0)), **common
            )
        with self.assertRaisesRegex(RuntimeContractError, "outside"):
            summarize_power_samples(
                (PowerSample(1, 0.0), PowerSample(2, 10.0)), **common
            )

    def test_run_window_interpolates_boundaries_before_integration(self):
        samples = (
            PowerSample(1_000_000_000, 10.0),
            PowerSample(2_000_000_000, 20.0),
            PowerSample(3_000_000_000, 10.0),
        )
        window = power_samples_for_window(
            samples, 1_500_000_000, 2_500_000_000
        )
        self.assertEqual(
            [sample.monotonic_ns for sample in window],
            [1_500_000_000, 2_000_000_000, 2_500_000_000],
        )
        self.assertEqual([sample.watts for sample in window], [15.0, 20.0, 15.0])
        report = summarize_power_samples(
            window, 175,
            source_path=Path("/sys/test/power1_input"),
            source_label="VCU118 total input",
            scale_to_watts=1e-6,
            sample_interval_s=1.0,
        )
        self.assertTrue(math.isclose(report["energy_joules"], 17.5))
        self.assertTrue(math.isclose(report["processed_tokens_per_joule"], 10.0))

    def test_file_sampler_records_real_timestamps_and_scaled_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "power1_input"
            source.write_text("10000000\n", encoding="ascii")
            sampler = FilePowerSampler(
                source, "test board total", scale_to_watts=1e-6,
                sample_interval_s=0.001,
            )
            with sampler:
                time.sleep(0.004)
            report = sampler.report(2)
        self.assertGreaterEqual(report["sample_count"], 2)
        self.assertTrue(math.isclose(report["minimum_watts"], 10.0))
        self.assertTrue(math.isclose(report["maximum_watts"], 10.0))
        self.assertGreater(report["energy_joules"], 0.0)
        self.assertGreater(report["processed_tokens_per_joule"], 0.0)


if __name__ == "__main__":
    unittest.main()
