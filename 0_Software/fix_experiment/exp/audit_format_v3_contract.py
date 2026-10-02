#!/usr/bin/env python3
"""Audit format-v3 constants across RTL, host, software twin and artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


WORKSPACE = Path("/home/user/EDA-202/zhuowenjun")
HAP = WORKSPACE / "fpga_llm_project" / "0_fix_newdataflow_Hadamard" / "HAP"
SOFTWARE = WORKSPACE / "ScaleLLM" / "0_Software" / "FPtoQ" / "experiment"
DEFAULT_RESULT_ROOT = (
    WORKSPACE
    / "ScaleLLM"
    / "0_Software"
    / "fix_experiment"
    / "results"
    / "llama31_rope_softmax_fixedpoint_hardware128_v3"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--require-deployment-ready", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    output_root = args.output_root.resolve()
    checks: list[dict[str, Any]] = []

    def text_check(
        *,
        check_id: str,
        component: str,
        path: Path,
        expected: str,
        severity: str = "core",
    ) -> None:
        source = read_text(path)
        checks.append(
            {
                "check_id": check_id,
                "component": component,
                "severity": severity,
                "expected": expected,
                "observed": expected if expected in source else "missing",
                "pass": expected in source,
                "source": str(path),
            }
        )

    mlp_pkg = HAP / "rtl" / "mlp" / "hap_mlp_pkg.sv"
    mlp_lane = HAP / "rtl" / "mlp" / "hap_a8w4_group32_lane2_s37.sv"
    mlp_down = HAP / "rtl" / "mlp" / "hap_mlp_down_group_major_accum_s46.sv"
    attention_pkg = HAP / "rtl" / "attention" / "hap_fixbit_v2_pkg.sv"
    attention_lane = HAP / "rtl" / "attention" / "hap_a8w8_group32_lane_s42.sv"
    attention_control = HAP / "rtl" / "attention" / "hap_attention_axil_control.sv"
    attention_accum = HAP / "rtl" / "attention" / "hap_linear_tile_accum_s42.sv"
    rope = HAP / "rtl" / "attention" / "hap_rope_pair_s24.sv"
    kv12 = HAP / "rtl" / "attention" / "hap_kv12_quantizer.sv"
    score = HAP / "rtl" / "attention" / "hap_score_accum4_s20.sv"
    softmax_prob = HAP / "rtl" / "attention" / "hap_softmax_prob_u16.sv"
    softmax_row = HAP / "rtl" / "attention" / "hap_softmax_row_128.sv"
    pv = HAP / "rtl" / "attention" / "hap_pv_tile16_s43.sv"
    swiglu = HAP / "rtl" / "mlp" / "hap_mlp_silu_mul.sv"
    production_manifest = (
        HAP / "vivado" / "manifests" / "attention_mlp_resource_top_v5_sources.list"
    )
    mlp_control = HAP / "rtl" / "integration" / "hap_mlp_axil_control.sv"
    host = HAP / "host" / "scalellm_hardware.py"
    exporter = HAP / "model" / "export_scalellm_llama31_artifacts.py"
    twin = SOFTWARE / "v5_fullchain.py"

    for check_id, component, path, expected in (
        (
            "mlp_rtl_format_id",
            "RTL MLP",
            mlp_pkg,
            "HAP_FULL_FIXBIT_V3_FORMAT_ID = 32'h4838_4603",
        ),
        ("mlp_rtl_guard_width", "RTL MLP", mlp_pkg, "MLP_GROUP_GUARD_W = 37"),
        (
            "mlp_rtl_gate_up_accum_width",
            "RTL MLP",
            mlp_pkg,
            "MLP_GATE_UP_ACCUM_W = 44",
        ),
        (
            "mlp_rtl_down_accum_width",
            "RTL MLP",
            mlp_pkg,
            "MLP_DOWN_ACCUM_W = 46",
        ),
        (
            "mlp_rtl_shift_min",
            "RTL MLP",
            mlp_lane,
            "total_shift_u7 < 7'd20",
        ),
        (
            "mlp_rtl_shift_max",
            "RTL MLP",
            mlp_lane,
            "total_shift_u7 > 7'd44",
        ),
        (
            "mlp_rtl_down_output_s24",
            "RTL MLP",
            mlp_down,
            "output wire signed [LANES*24-1:0]   out_projection_s24",
        ),
        (
            "attention_rtl_format_id_pkg",
            "RTL Attention",
            attention_pkg,
            "HAP_ATTN_FIXBIT_V3_FORMAT_ID = 32'h4838_4103",
        ),
        (
            "attention_rtl_format_id_control",
            "RTL Attention",
            attention_control,
            "FORMAT_ID = 32'h4838_4103",
        ),
        (
            "attention_rtl_shift_min",
            "RTL Attention",
            attention_lane,
            ") < 26 ||",
        ),
        (
            "attention_rtl_shift_max",
            "RTL Attention",
            attention_lane,
            ") > 47)))",
        ),
        (
            "attention_rtl_linear_output_s24",
            "RTL Attention",
            attention_accum,
            "output wire [LANES*24-1:0]          out_s24",
        ),
        (
            "attention_rtl_rope_io_s24",
            "RTL Attention",
            rope,
            "output wire signed [23:0]    out_y0_s24",
        ),
        (
            "attention_rtl_kv_input_s24",
            "RTL Attention",
            kv12,
            "input  wire [32*24-1:0]      in_s24",
        ),
        (
            "attention_rtl_qk_score_s20_f14",
            "RTL Attention",
            score,
            "output wire signed [19:0]    out_score_q14_s20",
        ),
        (
            "attention_rtl_qk_explicit_pm16_clamp",
            "RTL Attention",
            score,
            "value > 37'sd262144",
        ),
        (
            "attention_rtl_softmax_probability_u16",
            "RTL Attention",
            softmax_prob,
            "output wire [15:0]   out_prob_u16",
        ),
        (
            "attention_rtl_softmax_clamp_counter_unexported",
            "RTL Attention observability",
            softmax_row,
            "wire [31:0] prob_clamp_count_unused",
        ),
        (
            "attention_rtl_pv_accumulator_s43",
            "RTL Attention",
            pv,
            "reg signed [42:0] accum_s43_r [0:15]",
        ),
        (
            "attention_rtl_pv_output_s24",
            "RTL Attention",
            pv,
            "output wire [16*24-1:0]      out_context16_s24",
        ),
        (
            "mlp_rtl_swiglu_product_s32_f16",
            "RTL MLP",
            swiglu,
            "output reg signed [31:0]    out_product_s32",
        ),
        (
            "mlp_control_format_id",
            "RTL/AXI control",
            mlp_control,
            "FULL_FORMAT_ID = 32'h4838_4603",
        ),
        (
            "host_attention_format_id",
            "Host runtime",
            host,
            "ATTENTION_FORMAT_ID = 0x4838_4103",
        ),
        (
            "host_mlp_format_id",
            "Host runtime",
            host,
            "MLP_FORMAT_ID = 0x4838_4603",
        ),
        (
            "exporter_mlp_format_id",
            "Artifact exporter",
            exporter,
            "MLP_FORMAT_ID = 0x4838_4603",
        ),
        (
            "software_attention_format_id",
            "Software integer twin",
            twin,
            '"attention_format_id": "0x48384103"',
        ),
        (
            "software_mlp_format_id",
            "Software integer twin",
            twin,
            '"mlp_full_format_id": "0x48384603"',
        ),
        (
            "software_mlp_shift_range",
            "Software integer twin",
            twin,
            '"mlp_total_shift_range": [20, 44]',
        ),
        (
            "software_mlp_guard_width",
            "Software integer twin",
            twin,
            '"mlp_group_guard_compute_width": 37',
        ),
        (
            "software_gate_up_accum_width",
            "Software integer twin",
            twin,
            '"mlp_gate_up_accumulator_compute_width": 44',
        ),
        (
            "software_down_accum_width",
            "Software integer twin",
            twin,
            '"mlp_down_accumulator_compute_width": 46',
        ),
        (
            "software_attention_shift_policy",
            "Software integer twin",
            twin,
            "low_limit = 26 if self.op_name in {",
        ),
        (
            "software_s24_fractional_scale",
            "Software integer twin",
            twin,
            "Q16 = 1 << 16",
        ),
        (
            "software_kv12_magnitude",
            "Software integer twin",
            twin,
            "KV_QMAX = 2_047",
        ),
        (
            "software_qk_pm16_clamp",
            "Software integer twin",
            twin,
            "SCORE_LIMIT_Q14 = 16 << 14",
        ),
        (
            "production_manifest_attention_s42",
            "Production source closure",
            production_manifest,
            "rtl/attention/hap_a8w8_group32_lane_s42.sv",
        ),
        (
            "production_manifest_mlp_s37",
            "Production source closure",
            production_manifest,
            "rtl/mlp/hap_a8w4_group32_lane2_s37.sv",
        ),
        (
            "production_manifest_mlp_s44_s46",
            "Production source closure",
            production_manifest,
            "rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s46.sv",
        ),
    ):
        text_check(
            check_id=check_id,
            component=component,
            path=path,
            expected=expected,
        )

    artifact_path = HAP / "artifacts" / "llama31_8b_scalellm_v5" / "scalecode_manifest.json"
    artifact = json.loads(read_text(artifact_path))
    for check_id, field, expected in (
        ("artifact_attention_format_id", "attention_format_id", 0x48384103),
        ("artifact_mlp_format_id", "mlp_format_id", 0x48384603),
    ):
        observed = int(artifact[field])
        checks.append(
            {
                "check_id": check_id,
                "component": "Checked-in deployment artifact",
                "severity": "deployment",
                "expected": f"0x{expected:08x}",
                "observed": f"0x{observed:08x}",
                "pass": observed == expected,
                "source": str(artifact_path),
            }
        )

    core_pass = all(row["pass"] for row in checks if row["severity"] == "core")
    deployment_pass = all(
        row["pass"] for row in checks if row["severity"] == "deployment"
    )
    if core_pass and deployment_pass:
        status = "aligned_and_deployment_ready"
    elif core_pass:
        status = "core_aligned_deployment_artifact_mismatch"
    else:
        status = "core_contract_mismatch"
    report = {
        "schema": "scalellm_format_v3_contract_audit_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "core_contract_aligned": core_pass,
        "deployment_artifact_ready": deployment_pass,
        "checks": checks,
    }
    atomic_json(output_root / "format_v3_contract_audit.json", report)
    csv_path = output_root / "format_v3_contract_audit.csv"
    temporary = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "check_id",
                "component",
                "severity",
                "expected",
                "observed",
                "pass",
                "source",
            ),
        )
        writer.writeheader()
        writer.writerows(checks)
    temporary.replace(csv_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not core_pass or (args.require_deployment_ready and not deployment_pass):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
