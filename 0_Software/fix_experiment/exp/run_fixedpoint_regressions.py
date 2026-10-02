#!/usr/bin/env python3
"""Run and record the software/host format-v3 regression suites."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


WORKSPACE = Path("/home/user/EDA-202/zhuowenjun")
HAP = WORKSPACE / "fpga_llm_project/0_fix_newdataflow_Hadamard/HAP"
DEFAULT_ROOT = (
    WORKSPACE
    / "ScaleLLM/0_Software/fix_experiment/results"
    / "llama31_rope_softmax_fixedpoint_hardware128_v3"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--include-gpu", action="store_true")
    parser.add_argument(
        "--defer-gpu-reason",
        choices=("gpu_busy", "user_pause"),
        default="gpu_busy",
        help="Recorded reason when --include-gpu is not selected.",
    )
    return parser.parse_args()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    suites = [
        (
            "fptoq_frontend",
            WORKSPACE / "ScaleLLM/0_Software/FPtoQ/experiment/test_fptoq_core.py",
            8,
            False,
        ),
        (
            "evaluation_protocol",
            WORKSPACE / "ScaleLLM/0_Software/fix_experiment/exp/test_protocol.py",
            6,
            False,
        ),
        (
            "tokenizer_boundary",
            WORKSPACE
            / "ScaleLLM/0_Software/fix_experiment/exp/test_tokenizer_boundary.py",
            2,
            False,
        ),
        (
            "format_v3_rtl_static_contract",
            WORKSPACE
            / "ScaleLLM/0_Software/fix_experiment/exp"
            / "test_format_v3_static_contract.py",
            2,
            False,
        ),
        ("mlp_scalar_model", HAP / "tests/test_mlp_fixed.py", 11, False),
        ("artifact_contract", HAP / "tests/test_scalellm_artifacts.py", 8, False),
        ("host_hardware_contract", HAP / "tests/test_scalellm_hardware.py", 5, False),
        (
            "v5_cuda_integer_twin",
            WORKSPACE / "ScaleLLM/0_Software/FPtoQ/experiment/test_v5_fullchain.py",
            15,
            True,
        ),
    ]
    rows: list[dict[str, Any]] = []
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(HAP), environment.get("PYTHONPATH")))
    )
    for name, path, expected, gpu in suites:
        if gpu and not args.include_gpu:
            deferred_status = f"deferred_{args.defer_gpu_reason}"
            deferred_output = (
                "GPU conformance was not run because the validation was "
                "paused at the user's request."
                if args.defer_gpu_reason == "user_pause"
                else "GPU conformance is intentionally deferred until ACC "
                "workers release both devices."
            )
            rows.append(
                {
                    "suite": name,
                    "status": deferred_status,
                    "expected_tests": expected,
                    "observed_tests": None,
                    "returncode": None,
                    "command": [sys.executable, str(path), "-q"],
                    "output": deferred_output,
                }
            )
            continue
        process = subprocess.run(
            [sys.executable, str(path), "-q"],
            cwd=WORKSPACE,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        match = re.search(r"Ran (\d+) tests?", process.stdout)
        observed = int(match.group(1)) if match else None
        passed = process.returncode == 0 and observed == expected
        rows.append(
            {
                "suite": name,
                "status": "pass" if passed else "fail",
                "expected_tests": expected,
                "observed_tests": observed,
                "returncode": process.returncode,
                "command": [sys.executable, str(path), "-q"],
                "output": process.stdout[-12000:],
            }
        )
    required = [
        row for row in rows if not str(row["status"]).startswith("deferred_")
    ]
    complete = all(row["status"] == "pass" for row in rows)
    cpu_pass = all(row["status"] == "pass" for row in required)
    report = {
        "schema": "scalellm_fixedpoint_regression_evidence_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.executable,
        "include_gpu": bool(args.include_gpu),
        "status": (
            "complete_pass"
            if complete
            else ("cpu_pass_gpu_deferred" if cpu_pass else "fail")
        ),
        "passed_tests": sum(
            int(row["observed_tests"] or 0)
            for row in rows
            if row["status"] == "pass"
        ),
        "expected_tests": sum(int(row["expected_tests"]) for row in rows),
        "suites": rows,
    }
    output = args.output_root.resolve() / "regression_evidence.json"
    atomic_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not cpu_pass or (args.include_gpu and not complete):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
