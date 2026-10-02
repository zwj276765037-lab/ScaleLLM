#!/usr/bin/env python3
"""Regression wrappers for the authoritative production RTL static gates."""

from __future__ import annotations

import subprocess
from pathlib import Path
import unittest


WORKSPACE = Path("/home/user/EDA-202/zhuowenjun")
HAP = WORKSPACE / "fpga_llm_project/0_fix_newdataflow_Hadamard/HAP"
SCRIPTS = HAP / "vivado/scripts"


class FormatV3StaticContractTests(unittest.TestCase):
    def run_gate(self, script_name: str, pass_token: str) -> None:
        script = SCRIPTS / script_name
        process = subprocess.run(
            ["bash", str(script)],
            cwd=HAP,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout)
        self.assertIn(pass_token, process.stdout)

    def test_mlp_format_v3_source_closure(self) -> None:
        self.run_gate(
            "check_mlp_v5_format_v3_static.sh",
            "MLP_V5_FORMAT_V3_STATIC_PASS",
        )

    def test_cohort16_production_source_closure(self) -> None:
        self.run_gate(
            "check_attention_mlp_production_v5_cohort16_static.sh",
            "V5_COHORT16_STATIC_CONTRACT_PASS",
        )


if __name__ == "__main__":
    unittest.main()
