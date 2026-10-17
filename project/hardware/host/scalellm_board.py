#!/usr/bin/env python3
"""Strict VCU118 runner for the 32-layer ScaleLLM acceptance workload."""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Callable, Iterable, Mapping, Protocol, Sequence

import numpy as np

from model.export_scalellm_llama31_artifacts import (
    ATTENTION_ABI,
    ATTENTION_FORMAT_ID,
    GROUP as EXPORTER_GROUP,
    HIDDEN,
    LAYERS,
    MLP_ABI,
    MLP_FORMAT_ID,
    MODEL_ID,
    SCHEMA_VERSION,
    VOCAB_SIZE,
    LlamaCheckpoint,
)

from .scalellm_artifacts import (
    ScaleCodeArtifactManifest,
    XdmaLayerStager,
    preload_all_matrices,
    verify_resident_matrix_samples,
)
from .scalellm_hardware import (
    HardwareCommandTelemetry,
    ScaleLLMHardwareBackend,
)
from .scalellm_hostops import (
    ACTIVATION_SHAPE,
    LlamaNormWeights,
    PinnedActivationPool,
    ScaleLLMHostBoundaryOps,
)
from .scalellm_power import FilePowerSampler
from .scalellm_runtime import (
    DualCohortRuntime,
    PipelineReport,
    RuntimeContractError,
    XdmaSession,
)


WORKLOAD_SCHEMA_VERSION = 1
COHORT_ROWS = 16
QUANTIZATION_ID = (
    "hadamard32-scalecode-group32-attention-a8w8-mlp-a8w4-swiglu"
)
CURRENT_PROFILE = "core100_ddr200_format05"
LEGACY_PROFILE = "legacy_p16_fxp16_ddr300"
CURRENT_REFERENCE_SCHEMA = "scalellm_v5_integer_reference_v2"
CURRENT_REFERENCE_ID = (
    "scalellm-v5-integer-h32-group32-scalecode-down-s32-shift12-v2"
)
APPROVED_GOLDEN_SHA256 = (
    "58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898"
)
APPROVED_EXPORTER_NUMERIC_AST_SHA256 = (
    "a16d2b9f229ef1804e095243c96e62bae6cf0010efb6014609120a507372e196"
)
APPROVED_FIXBIT_SHA256 = (
    "fb4b34397edc9d14ed3ef4f0b46d60a61b545a52a7a47d15c2eec8ba7b6db271"
)
SOFTWARE_REFERENCE_SCHEMA = "scalellm_v5_algorithmic_reference_v1"
SOFTWARE_REFERENCE_ID = (
    "scalellm-hadamard-scalecode-a8w8-a8w4-fxp16q5p10-v1"
)
REFERENCE_LINEAR_COUNTS = {
    "q_proj": 32,
    "k_proj": 32,
    "v_proj": 32,
    "o_proj": 32,
    "gate_proj": 32,
    "up_proj": 32,
    "down_proj": 32,
}
REFERENCE_WEIGHT_BITS = {
    "q_proj": 8,
    "k_proj": 8,
    "v_proj": 8,
    "o_proj": 8,
    "gate_proj": 4,
    "up_proj": 4,
    "down_proj": 4,
}
REFERENCE_FIXEDPOINT = {
    "a8_quant": "dynamic_per_token_symmetric",
    "accumulator_width": 32,
    "activation_tail_policy": "zero_left_identity_right",
    "clamp_max": 8.0,
    "clamp_min": -8.0,
    "clipping": "symmetric_signed",
    "frac_bits": 10,
    "integer_bits": 5,
    "lut_entries": 16385,
    "lut_input_range": [-8.0, 8.0],
    "multiply_width": 32,
    "nonlinear_impl": "lut",
    "qmax": 32767,
    "qmin": -32768,
    "requant_mid_a8": False,
    "rounding": "nearest",
    "scale": 1024,
    "total_bits": 16,
    "variant": "FXP16-Q5.10-LUT",
}
CURRENT_NUMERIC_CONTRACT = {
    "hadamard_group": 32,
    "hadamard_inverse_sqrt32_q16": 11585,
    "activation_quantizer": "raw_minmax_including_zero_no_source_preclip",
    "activation_scale_rounding": "nearest_even",
    "scalecode_division_rounding": "nearest_even",
    "folded_weight_rounding": "half_away_terminal_w8_w4_saturation",
    "gate_up": {"input_width": 24, "group_guard_width": 37,
                "accumulator_width": 44, "output_width": 24,
                "total_shift_range": [20, 44]},
    "down": {"input_width": 32, "hadamard_width": 35,
             "group_guard_width": 45, "accumulator_width": 54,
             "output_width": 32, "total_shift_range": [12, 44]},
    "swiglu": "signed_packed_s24_internal_s32",
    "attention": "integer_rope_kv12_qk_softmax_pv_legitimate_clamps",
}
EXPECTED_MATRIX_BYTES = 1_280 << 20  # Resident DDR0 Attention; MLP is staged per command.
COMMANDS_PER_PAIR = LAYERS * 2 * 2
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BOARD_RTL_VARIANT = "P16_NOCLIP"
BOARD_TOTAL_DSP = 5449
BOARD_SLR_DSP = (1862, 1777, 1810)
BOARD_COMPLETE_INPUT_COUNT = 140
BOARD_IMMUTABLE_INPUT_COUNT = 139
BOARD_AUDIT_INPUT_COUNT = 20
P16_QUANTIZER3_PRIMITIVES = 14375
P16_REGION2_PRIMITIVES = 72896
CURRENT_PART = "xcvu9p-flga2104-2L-e"
CURRENT_FORMAT_ID = "0x48384605"
CURRENT_ABI = "0x00050000"
CURRENT_CLOCKS = {"core_mhz": 100, "ddr0_ui_mhz": 200,
                  "ddr1_ui_mhz": 200, "reference_ps": 4000}
CURRENT_ROUTE_REPORTS = (
    "timing_post_route.rpt", "check_timing_post_route.rpt",
    "clocks_post_route.rpt", "clock_interaction_post_route.rpt",
    "cdc_post_route.rpt", "drc_post_route.rpt",
    "route_status_post_route.rpt", "exceptions_post_route.rpt",
    "routed.dcp", "routed_checkpoint.sha256",
)
CURRENT_AUDIT_REPORTS = (
    "audit_summary.txt", "package_pins_reopened.txt",
    "timing_reopened.rpt", "check_timing_reopened.rpt",
    "clocks_reopened.rpt", "clock_interaction_reopened.rpt",
    "route_status_reopened.rpt", "drc_reopened.rpt", "cdc_reopened.rpt",
    "exceptions_reopened.rpt", "io_reopened.rpt", "pulse_width_reopened.rpt",
    "pulse_width_violators_reopened.rpt", "bus_skew_reopened.rpt",
    "dsp_status_paths_reopened.rpt",
)
CURRENT_FINAL_REPORTS = {
    "timing": "timing_bitgen.rpt",
    "check_timing": "check_timing_bitgen.rpt",
    "clocks": "clocks_bitgen.rpt",
    "clock_interaction": "clock_interaction_bitgen.rpt",
    "route": "route_status_bitgen.rpt",
    "drc": "drc_bitgen.rpt",
    "cdc": "cdc_bitgen.rpt",
    "pulse": "pulse_width_bitgen.rpt",
    "pulse_violators": "pulse_width_violators_bitgen.rpt",
    "bus_skew": "bus_skew_bitgen.rpt",
}

BOARD_REQUIRED_FILES = (
    "summary.txt",
    "post_route_gate_summary.txt",
    "launcher_status.txt",
    "OUTPUT_SHA256SUMS",
    "XDC_SOURCE_INVENTORY",
    "XDC_ACTIVE_INVENTORY",
    "INPUT_FILES",
    "INPUT_SHA256SUMS",
    "IMMUTABLE_INPUT_FILES",
    "IMMUTABLE_INPUT_SHA256SUMS",
    "RECURSIVE_SOURCE_MANIFEST_FILES",
    "RECURSIVE_RTL_SOURCE_FILES",
    "RECURSIVE_SOURCE_CLOSURE_FILES",
    "RECURSIVE_SOURCE_SHA256SUMS",
    "OOC_ROUTE_AUTHORIZATION_FILES",
    "OOC_ROUTE_AUTHORIZATION_SHA256SUMS",
    "attention_mlp_vcu118_v5.bit",
    "attention_mlp_vcu118_v5_post_route.dcp",
    "timing_post_route.rpt",
    "route_status_post_route.rpt",
    "drc_post_route.rpt",
    "bufg_topology_post_route.txt",
    "cdc_post_route.rpt",
    "selectors_post_route.txt",
    "attention_geometry_post_route.txt",
    "attention_geometry_placement_post_route.txt",
    "base_pblocks_post_route.txt",
    "p5_input_plan_post_route.txt",
    "p5_input_pblocks_post_route.txt",
    "p9_postprocess_plan_post_route.txt",
    "p9_postprocess_pblocks_post_route.txt",
    "p9_quantizer3_plan_post_route.txt",
    "p9_quantizer3_pblock_post_route.txt",
    "p14_region2_relief_plan_post_route.txt",
    "p14_region2_relief_pblock_post_route.txt",
    "p8_parent_ingress_boundary_post_route.txt",
    "architecture_boundaries_post_route.txt",
    "congestion_post_route.rpt",
    "exceptions_coverage_post_route.rpt",
    "exceptions_valid_post_route.xdc",
    "exceptions_merged_post_route.xdc",
    "utilization_post_route.rpt",
    "utilization_hier_post_route.rpt",
    "utilization_slr_post_route.rpt",
    "clock_interaction_post_route.rpt",
    "clock_utilization_post_route.rpt",
    "vivado.log",
    "vivado.jou",
)

BOARD_AUDIT_REQUIRED_FILES = (
    "summary.txt",
    "post_route_gate_summary.txt",
    "launcher_status.txt",
    "INPUT_FILES",
    "INPUT_SHA256SUMS",
    "OUTPUT_SHA256SUMS",
    "timing_post_route.rpt",
    "route_status_post_route.rpt",
    "drc_post_route.rpt",
    "congestion_post_route.rpt",
    "bufg_topology_post_route.txt",
    "cdc_post_route.rpt",
    "selectors_post_route.txt",
    "attention_geometry_post_route.txt",
    "attention_geometry_placement_post_route.txt",
    "base_pblocks_post_route.txt",
    "p5_input_plan_post_route.txt",
    "p5_input_pblocks_post_route.txt",
    "p9_postprocess_plan_post_route.txt",
    "p9_postprocess_pblocks_post_route.txt",
    "p9_quantizer3_plan_post_route.txt",
    "p9_quantizer3_pblock_post_route.txt",
    "p14_region2_relief_plan_post_route.txt",
    "p14_region2_relief_pblock_post_route.txt",
    "p8_parent_ingress_boundary_post_route.txt",
    "architecture_boundaries_post_route.txt",
    "exceptions_coverage_post_route.rpt",
    "exceptions_valid_post_route.xdc",
    "exceptions_merged_post_route.xdc",
    "utilization_post_route.rpt",
    "utilization_hier_post_route.rpt",
    "utilization_slr_post_route.rpt",
    "clock_interaction_post_route.rpt",
    "clock_utilization_post_route.rpt",
    "vivado.log",
    "vivado.jou",
)
BOARD_PROGRAM_REQUIRED_FILES = (
    "summary.txt",
    "launcher_status.txt",
    "INPUT_FILES",
    "INPUT_SHA256SUMS",
    "OUTPUT_SHA256SUMS",
    "vivado.log",
    "vivado.jou",
)

POST_ROUTE_CROSSCHECK_FIELDS = (
    "rtl_variant", "rtl_resource_variant", "region2_signature_source",
    "evidence_class", "core_clock_mhz", "ddr0_clock_mhz",
    "ddr1_clock_mhz", "v5_serial_instances", "old_serial_instances",
    "v5_shared_instances", "v5_branch_instances", "v5_kernel12_instances",
    "v4_kernel16_instances", "history2_repack_instances",
    "generic_repack_instances", "dsp48e2", "mlp_kernel_dsp48e2",
    "uram288", "projection_weight_capture_ok", "architecture_boundary_ok",
    "unplaced_primitives", "wrong_slr_primitives",
    "compute_clock_buffer_none_ok", "no_clock_endpoints",
    "unconstrained_paths", "timing_coverage_ok", "route_error_nets",
    "explicit_gap_nets", "unrouted_nets", "some_unrouted_pin_nets",
    "resource_conflict_nets", "antenna_island_nets", "route_status_partial",
    "route_status_conflicts", "route_clean", "drc_errors", "cdc_critical",
    "data_bufg", "congestion_level6_or_higher_windows",
    "exception_scope_policy_ok", "live_post_route_rediscovery_ok",
    "base_contract_variant", "p5_contract", "p9_postprocess_contract",
    "p9_quantizer3_contract", "p14_region2_relief_contract",
    "pblock_contract_variant",
    "pblock_contract_ok", "pblock_require_placed", "pblock_count",
    "canonical_pblock_count", "geometry_pblock_count",
    "p5_added_pblock_count", "p9_postprocess_added_pblock_count",
    "p9_quantizer3_added_pblock_count",
    "p14_region2_relief_added_pblock_count",
    "total_pblock_count", "completed_u8_ff",
    "completed_meta_ff", "input_capture_ff", "input_capture_controls",
    "p5_center_wrong_slr", "p5_outer_wrong_slr",
    "p9_postprocess_center_wrong_slr", "p9_postprocess_outer_wrong_slr",
    "p9_slr0_row_primitives", "p9_center_row_primitives",
    "p9_slr2_row_primitives", "p9_quantizer3_primitives",
    "p9_quantizer3_grid_range", "p9_quantizer3_wrong_region",
    "p9_quantizer3_unplaced", "p14_region2_relief_primitives",
    "p14_region2_relief_base_range", "p14_region2_relief_range",
    "p14_region2_expected_range", "p14_region2_relief_placed",
    "p14_region2_relief_wrong", "p14_region2_relief_unplaced",
    "parent_head_ff", "parent_tail_ff", "parent_count_ff",
    "parent_count_physical_ff", "parent_count_replica_ff",
    "parent_count_replica_equivalence_ok", "parent_pointer_ff",
    "local_clear_shared_upstream_ready_paths",
    "branch_credit_shared_upstream_ready_paths",
    "local_clear_gate_compute_ready_paths",
    "branch_credit_gate_compute_ready_paths",
    "local_clear_down_compute_ready_paths",
    "branch_credit_down_compute_ready_paths",
    "local_clear_input_cache_ready_paths",
    "branch_credit_input_cache_ready_paths",
    "geometry_region0_input_primitives", "geometry_region3_input_primitives",
    "geometry_owner_region2_weight_primitives", "geometry_region0_input_ok",
    "geometry_region3_input_ok", "geometry_owner_region2_weight_ok",
    "projected_slr_dsp48e2", "projected_slr_uram288", "slr0_dsp48e2",
    "slr1_dsp48e2", "slr2_dsp48e2", "slr0_uram288", "slr1_uram288",
    "slr2_uram288", "pblock_dsp_coverage", "pblock_uram_coverage",
    "pblock_wrong_slr", "physical_placement_ok", "physical_ok",
    "floorplan_contract_ok", "wns_ns", "whs_ns",
)


def sha256_file(path: Path, chunk_bytes: int = 8 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk_bytes):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeContractError(f"cannot parse JSON {path}: {exc}") from exc


def _load_key_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeContractError(f"cannot read key/value file {path}: {exc}") \
            from exc
    for line_number, line in enumerate(lines, 1):
        if not line:
            continue
        if "=" not in line:
            raise RuntimeContractError(
                f"invalid key/value line {path}:{line_number}"
            )
        key, value = line.split("=", 1)
        if not key or key in result:
            raise RuntimeContractError(
                f"duplicate/empty key in {path}:{line_number}"
            )
        result[key] = value
    return result


def _load_marker_key_values(path: Path, marker: str) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeContractError(f"cannot read marker report {path}: {exc}") \
            from exc
    if not lines or lines[0] != marker:
        raise RuntimeContractError(
            f"invalid marker report {path}: expected={marker!r}"
        )
    result: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:], 2):
        if not line:
            continue
        if "=" not in line:
            raise RuntimeContractError(
                f"invalid key/value line {path}:{line_number}"
            )
        key, value = line.split("=", 1)
        if not key or key in result:
            raise RuntimeContractError(
                f"duplicate/empty key in {path}:{line_number}"
            )
        result[key] = value
    return result


def _report_int(values: Mapping[str, str], key: str, label: str) -> int:
    try:
        return int(values[key])
    except (KeyError, ValueError) as exc:
        raise RuntimeContractError(
            f"{label} report has invalid integer: {key}={values.get(key)!r}"
        ) from exc


def _resolve_p16_lineage(
    summary: Mapping[str, str], label: str
) -> tuple[Path, Path, str]:
    if (summary.get("rtl_variant") != BOARD_RTL_VARIANT or
            summary.get("rtl_resource_variant") != BOARD_RTL_VARIANT):
        raise RuntimeContractError(
            f"{label} is not the frozen {BOARD_RTL_VARIANT} image"
        )

    resolved: dict[str, Path] = {}
    for path_key, sha_key in (
        ("p16_post_opt_summary", "p16_post_opt_summary_sha256"),
        ("p16_production_region2_summary",
         "p16_production_region2_summary_sha256"),
    ):
        expected_sha = _require_sha(summary.get(sha_key), f"{label} {sha_key}")
        try:
            unresolved = Path(summary[path_key])
            path = unresolved.resolve(strict=True)
        except (KeyError, OSError) as exc:
            raise RuntimeContractError(
                f"{label} has an invalid P16 lineage path: {path_key}"
            ) from exc
        if (not unresolved.is_absolute() or str(path) != str(unresolved) or
                unresolved.is_symlink() or not path.is_file() or
                path.stat().st_size == 0):
            raise RuntimeContractError(
                f"{label} P16 lineage is not a nonempty regular file: {path}"
            )
        if sha256_file(path) != expected_sha:
            raise RuntimeContractError(
                f"{label} P16 lineage SHA256 mismatch: {path_key}"
            )
        resolved[path_key] = path

    post_opt = _load_key_values(resolved["p16_post_opt_summary"])
    for key, expected in {
        "status": "PASS",
        "attention_lane_instances": "128",
        "local_dual_accumulator_instances": "6",
        "local_accumulator_contexts": "12",
        "dut_dsp48e2": "2240",
        "array_dsp48e2": "2176",
        "frontend_dsp48e2": "64",
        "frontend_quantizer_dsp48e2": "0",
        "place_authorized": "0",
        "route_authorized": "0",
    }.items():
        if post_opt.get(key) != expected:
            raise RuntimeContractError(
                f"{label} P16 post-opt lineage failed: {key}="
                f"{post_opt.get(key)!r}"
            )

    region2 = _load_key_values(resolved["p16_production_region2_summary"])
    for key, expected in {
        "status": "V5_P16_PRODUCTION_REGION2_POST_OPT_PROBE_PASS",
        "attention_lane_instances": "128",
        "local_dual_accumulator_instances": "6",
        "local_accumulator_contexts": "12",
        "dut_dsp48e2": "2240",
        "frontend_quantizer_dsp48e2": "0",
        "region2_lane_instances": "32",
        "region2_primitives": str(P16_REGION2_PRIMITIVES),
        "region2_dsp48e2": "544",
        "region2_rows0_3_primitives": "26800",
        "region2_rows0_3_dsp48e2": "272",
        "region2_rows4_7_primitives": "26800",
        "region2_rows4_7_dsp48e2": "272",
        "region2_residual_primitives": "19296",
        "region2_residual_dsp48e2": "0",
        "partition_exact_cover": "1",
        "drc_errors": "0",
        "implementation_commands_run": "0",
        "checkpoint_written": "0",
    }.items():
        if region2.get(key) != expected:
            raise RuntimeContractError(
                f"{label} P16 Region2 lineage failed: {key}="
                f"{region2.get(key)!r}"
            )
    production_dcp_sha = _require_sha(
        summary.get("p16_production_dcp_sha256"),
        f"{label} p16_production_dcp_sha256",
    )
    if region2.get("input_dcp_sha256") != production_dcp_sha:
        raise RuntimeContractError(
            f"{label} P16 production DCP lineage disagrees with Region2 probe"
        )
    signature = (
        "P16_PRODUCTION_POST_OPT_SHA256:"
        f"{summary['p16_production_region2_summary_sha256']}"
    )
    if summary.get("region2_signature_source") != signature:
        raise RuntimeContractError(
            f"{label} P16 Region2 signature source is not hash-bound"
        )
    return (
        resolved["p16_post_opt_summary"],
        resolved["p16_production_region2_summary"],
        signature,
    )


def _verify_p16_post_route_reports(
    root: Path, label: str, summary: Mapping[str, str]
) -> tuple[Path, Path, str]:
    lineage = _resolve_p16_lineage(summary, label)
    quantizer_primitives = _report_int(
        summary, "p9_quantizer3_primitives", label
    )
    relief_primitives = _report_int(
        summary, "p14_region2_relief_primitives", label
    )
    if quantizer_primitives != P16_QUANTIZER3_PRIMITIVES:
        raise RuntimeContractError(
            f"{label} P16 quantizer3 primitive identity drifted: "
            f"{quantizer_primitives}"
        )
    if relief_primitives not in {
        P16_REGION2_PRIMITIVES, P16_REGION2_PRIMITIVES - 1
    }:
        raise RuntimeContractError(
            f"{label} P16 Region2 optimizer delta is outside 0..1: "
            f"{relief_primitives}"
        )

    reports = (
        (
            root / "p9_postprocess_plan_post_route.txt",
            {
                "status": "V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PLAN_PASS",
                "contract": "P9_POSTPROCESS_SPLIT_6_4_6",
                "row_bank_count": "16",
                "all_row_primitives": "42784",
                "slr0_row_primitives": "16044",
                "center_row_primitives": "10696",
                "slr2_row_primitives": "16044",
                "per_row_primitives": "2674",
                "per_row_lut": "994",
                "per_row_ff": "1536",
            },
        ),
        (
            root / "p9_postprocess_pblocks_post_route.txt",
            {
                "status": "V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PBLOCKS_PASS",
                "ok": "1",
                "require_placed": "1",
                "pblock_count": "2",
                "center_missing": "0",
                "center_outer_overlap": "0",
                "center_wrong": "0",
                "outer_wrong": "0",
                "slr0_name": "pb_v5_p9_postprocess_rows0_5_slr0",
                "slr0_target": "0",
                "slr0_expected": "16044",
                "slr0_missing": "0",
                "slr0_wrong": "0",
                "slr0_hard": "dsp 0 uram 0 ramb36 0 ramb18 0",
                "slr2_name": "pb_v5_p9_postprocess_rows10_15_slr2",
                "slr2_target": "2",
                "slr2_expected": "16044",
                "slr2_missing": "0",
                "slr2_wrong": "0",
                "slr2_hard": "dsp 0 uram 0 ramb36 0 ramb18 0",
            },
        ),
        (
            root / "p9_quantizer3_plan_post_route.txt",
            {
                "status": "V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PLAN_PASS",
                "contract": "P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6",
                "primitive_count": str(quantizer_primitives),
                "lut": "9959",
                "ff": "3794",
                "pblock_name": "pb_v5_p9_swiglu_quantizer3_cr_x2y5_x3y6",
                "grid_range": "CLOCKREGION_X2Y5:CLOCKREGION_X3Y6",
                "allowed_regions": "X2Y5 X2Y6 X3Y5 X3Y6",
                "dsp": "0",
                "uram": "0",
                "ramb36": "0",
                "ramb18": "0",
            },
        ),
        (
            root / "p9_quantizer3_pblock_post_route.txt",
            {
                "status": "V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PBLOCK_PASS",
                "ok": "1",
                "require_placed": "1",
                "name": "pb_v5_p9_swiglu_quantizer3_cr_x2y5_x3y6",
                "contract": "P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6",
                "grid_range": "CLOCKREGION_X2Y5:CLOCKREGION_X3Y6",
                "expected": str(quantizer_primitives),
                "members": str(quantizer_primitives),
                "missing": "0",
                "extras": "0",
                "wrong": "0",
                "unplaced": "0",
            },
        ),
        (
            root / "p14_region2_relief_plan_post_route.txt",
            {
                "status": "V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PLAN_PASS",
                "contract": "P14_ATTN_REGION2_SHARED_X0_X2",
                "pblock_name": "p3_pb_projection_center_region2_shared_cr_x0y5_x1y9",
                "base_range": "CLOCKREGION_X0Y5:CLOCKREGION_X1Y9",
                "relief_range": "CLOCKREGION_X2Y5:CLOCKREGION_X2Y9",
                "expected_range": "CLOCKREGION_X0Y5:CLOCKREGION_X2Y9",
                "primitive_count": str(relief_primitives),
                "dsp": "544",
            },
        ),
        (
            root / "p14_region2_relief_pblock_post_route.txt",
            {
                "status": "V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PBLOCK_PASS",
                "ok": "1",
                "contract": "P14_ATTN_REGION2_SHARED_X0_X2",
                "require_placed": "1",
                "name": "p3_pb_projection_center_region2_shared_cr_x0y5_x1y9",
                "primitive_count": str(relief_primitives),
                "dsp": "544",
                "missing": "0",
                "wrong": "0",
                "unplaced": "0",
            },
        ),
    )
    for path, expected_fields in reports:
        values = _load_key_values(path)
        for key, expected in expected_fields.items():
            if values.get(key) != expected:
                raise RuntimeContractError(
                    f"{label} P16 report invariant failed: "
                    f"{path.name}:{key}={values.get(key)!r}"
                )

    p9_pblocks = _load_key_values(
        root / "p9_postprocess_pblocks_post_route.txt"
    )
    slr0_extras = _report_int(p9_pblocks, "slr0_extras", label)
    slr2_extras = _report_int(p9_pblocks, "slr2_extras", label)
    outer_extras = _report_int(p9_pblocks, "outer_extras", label)
    slr0_members = _report_int(p9_pblocks, "slr0_members", label)
    slr2_members = _report_int(p9_pblocks, "slr2_members", label)
    if (slr0_extras < 0 or slr2_extras < 0 or
            outer_extras != slr0_extras + slr2_extras or
            outer_extras > 4096 or slr0_members != 16044 + slr0_extras or
            slr2_members != 16044 + slr2_extras):
        raise RuntimeContractError(
            f"{label} P16 report invariant failed: P9 optimizer extras"
        )

    p14_pblock = _load_key_values(
        root / "p14_region2_relief_pblock_post_route.txt"
    )
    relief_placed = _report_int(p14_pblock, "relief_placed", label)
    if relief_placed < 0 or relief_placed > relief_primitives:
        raise RuntimeContractError(
            f"{label} P16 report invariant failed: relief_placed"
        )

    parent = _load_marker_key_values(
        root / "p8_parent_ingress_boundary_post_route.txt",
        "V5_BOARD_POST_ROUTE_P8_PARENT_INGRESS_BOUNDARY_PASS",
    )
    for key, expected in {
        "ok": "1", "parent_head_ff": "6560", "parent_tail_ff": "6560",
        "parent_count_ff": "2", "parent_count_replica_equivalence_ok": "1",
        "parent_pointer_ff": "0", "local_clear_ff": "2",
        "branch_ingress_count_ff": "4",
        "local_clear_shared_upstream_ready_paths": "0",
        "branch_credit_shared_upstream_ready_paths": "0",
        "local_clear_gate_compute_ready_paths": "0",
        "branch_credit_gate_compute_ready_paths": "0",
        "local_clear_down_compute_ready_paths": "0",
        "branch_credit_down_compute_ready_paths": "0",
        "local_clear_input_cache_ready_paths": "0",
        "branch_credit_input_cache_ready_paths": "0",
    }.items():
        if parent.get(key) != expected:
            raise RuntimeContractError(
                f"{label} P16 report invariant failed: "
                f"p8_parent_ingress_boundary_post_route.txt:{key}="
                f"{parent.get(key)!r}"
            )
    physical = _report_int(parent, "parent_count_physical_ff", label)
    replicas = _report_int(parent, "parent_count_replica_ff", label)
    bit0 = _report_int(parent, "parent_count_bit0_physical_ff", label)
    bit1 = _report_int(parent, "parent_count_bit1_physical_ff", label)
    if (physical < 2 or replicas != physical - 2 or bit0 < 1 or bit1 < 1 or
            bit0 + bit1 != physical):
        raise RuntimeContractError(
            f"{label} P16 report invariant failed: parent-count replicas"
        )
    return lineage


def _verify_exact_output_tree(
    root: Path, required_files: Sequence[str], label: str
) -> dict[Path, str]:
    for name in required_files:
        path = root / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise RuntimeContractError(f"missing/empty {label} evidence: {path}")

    manifested: dict[Path, str] = {}
    manifest_path = root / "OUTPUT_SHA256SUMS"
    for line_number, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        match = re.fullmatch(r"([0-9a-f]{64}) ([ *])(.+)", line)
        if match is None:
            raise RuntimeContractError(
                f"invalid {label} OUTPUT_SHA256SUMS line {line_number}"
            )
        candidate = Path(match.group(3)).resolve(strict=True)
        if candidate.parent != root or candidate.name == manifest_path.name:
            raise RuntimeContractError(
                f"{label} output manifest path is outside report root: "
                f"{candidate}"
            )
        if candidate in manifested:
            raise RuntimeContractError(
                f"duplicate {label} output manifest path: {candidate}"
            )
        manifested[candidate] = match.group(1)

    current = {
        path.resolve()
        for path in root.iterdir()
        if path.name != manifest_path.name and path.is_file()
        and not path.is_symlink() and path.stat().st_size > 0
    }
    if set(manifested) != current:
        raise RuntimeContractError(
            f"{label} OUTPUT_SHA256SUMS does not cover the exact output set"
        )
    for path, expected in manifested.items():
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeContractError(
                f"{label} output SHA256 mismatch: {path} "
                f"expected={expected} actual={actual}"
            )
    return manifested


def _verify_frozen_input_closure(
    input_files: Path, input_sha: Path, expected_count: int, label: str
) -> dict[Path, str]:
    listed: set[Path] = set()
    for line_number, row in enumerate(
        input_files.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not row:
            continue
        unresolved = Path(row)
        try:
            path = unresolved.resolve(strict=True)
        except OSError as exc:
            raise RuntimeContractError(
                f"{label} INPUT_FILES member is missing at line {line_number}"
            ) from exc
        if (not unresolved.is_absolute() or str(path) != row or
                path.is_symlink() or not path.is_file() or
                path.stat().st_size == 0 or path in listed):
            raise RuntimeContractError(
                f"invalid/duplicate {label} INPUT_FILES line {line_number}"
            )
        listed.add(path)

    manifested: dict[Path, str] = {}
    for line_number, row in enumerate(
        input_sha.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not row:
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) ([ *])(.+)", row)
        if match is None:
            raise RuntimeContractError(
                f"invalid {label} INPUT_SHA256SUMS line {line_number}"
            )
        unresolved = Path(match.group(3))
        try:
            path = unresolved.resolve(strict=True)
        except OSError as exc:
            raise RuntimeContractError(
                f"{label} frozen input is missing at line {line_number}"
            ) from exc
        if (not unresolved.is_absolute() or str(path) != match.group(3) or
                path in manifested):
            raise RuntimeContractError(
                f"noncanonical/duplicate {label} input at line {line_number}"
            )
        actual = sha256_file(path)
        if actual != match.group(1):
            raise RuntimeContractError(
                f"{label} frozen-input SHA256 mismatch: {path}"
            )
        manifested[path] = match.group(1)

    if (len(listed) != expected_count or len(manifested) != expected_count or
            listed != set(manifested)):
        raise RuntimeContractError(
            f"{label} frozen input closure mismatch: expected={expected_count} "
            f"listed={len(listed)} hashed={len(manifested)}"
        )
    return manifested


def _require_fields(raw: object, fields: set[str], label: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != fields:
        actual = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        raise RuntimeContractError(
            f"{label} fields mismatch: expected={sorted(fields)} actual={actual}"
        )
    return raw


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise RuntimeContractError(f"{label} must be a lowercase SHA256")
    return value


@dataclass(frozen=True)
class FrozenFile:
    path: Path
    size: int
    sha256: str

    @classmethod
    def parse(cls, raw: object, base: Path, label: str) -> "FrozenFile":
        item = _require_fields(raw, {"path", "size", "sha256"}, label)
        path_text = item["path"]
        if not isinstance(path_text, str) or not path_text:
            raise RuntimeContractError(f"{label} path must be nonempty")
        unresolved = Path(path_text)
        try:
            path = (unresolved if unresolved.is_absolute()
                    else base / unresolved).resolve(strict=True)
        except OSError as exc:
            raise RuntimeContractError(f"{label} file is missing: {path_text}") \
                from exc
        if path.is_symlink() or not path.is_file():
            raise RuntimeContractError(f"{label} must be a regular file: {path}")
        if type(item["size"]) is not int or item["size"] <= 0:
            raise RuntimeContractError(f"{label} size must be a positive integer")
        if path.stat().st_size != item["size"]:
            raise RuntimeContractError(
                f"{label} size mismatch: manifest={item['size']} "
                f"file={path.stat().st_size}"
            )
        return cls(path, item["size"], _require_sha(item["sha256"], label))

    def verify(self) -> None:
        actual = sha256_file(self.path)
        if actual != self.sha256:
            raise RuntimeContractError(
                f"frozen file SHA256 mismatch: {self.path} "
                f"expected={self.sha256} actual={actual}"
            )

    def as_dict(self) -> dict:
        return {"path": str(self.path), "size": self.size, "sha256": self.sha256}


@dataclass(frozen=True)
class BoardBuildEvidence:
    report_dir: Path
    rtl_variant: str
    bitstream: Path
    bitstream_sha256: str
    checkpoint_sha256: str
    wns_ns: float
    whs_ns: float
    output_count: int
    profile: str = LEGACY_PROFILE

    @classmethod
    def load(
        cls, report_dir: str | Path, *, profile: str = CURRENT_PROFILE,
    ) -> "BoardBuildEvidence":
        if profile == CURRENT_PROFILE:
            return _load_current_board_build(cls, report_dir)
        if profile != LEGACY_PROFILE:
            raise RuntimeContractError("unsupported board build evidence profile")
        root = Path(report_dir).resolve(strict=True)
        if not root.is_dir():
            raise RuntimeContractError(f"board report is not a directory: {root}")
        manifested = _verify_exact_output_tree(
            root, BOARD_REQUIRED_FILES, "board"
        )
        summary = _load_key_values(root / "summary.txt")
        _, _, region2_signature = _verify_p16_post_route_reports(
            root, "board", summary
        )

        launcher = _load_key_values(root / "launcher_status.txt")
        required_launcher = {
            "status": "PASS",
            "final_exit_code": "0",
            "vivado_exit_code": "0",
            "vivado_invoked": "1",
            "complete_input_manifest_sha_match": "1",
            "immutable_input_count": str(BOARD_IMMUTABLE_INPUT_COUNT),
            "immutable_input_manifest_sha_match": "1",
            "immutable_input_postcheck": "1",
            "recursive_source_post_build_sha_verified": "1",
            "ooc_route_authorization_post_build_verified": "1",
            "bitstream_generated": "1",
            "rtl_variant": BOARD_RTL_VARIANT,
        }
        for key, expected in required_launcher.items():
            if launcher.get(key) != expected:
                raise RuntimeContractError(
                    f"board launcher gate failed: {key}={launcher.get(key)!r}"
                )

        required_summary = {
            "status": "V5_BOARD_BITSTREAM_PASS",
            "post_route_gate_status": "V5_BOARD_POST_ROUTE_PASS",
            "rtl_variant": BOARD_RTL_VARIANT,
            "rtl_resource_variant": BOARD_RTL_VARIANT,
            "dsp48e2": str(BOARD_TOTAL_DSP),
            "mlp_kernel_dsp48e2": "3072",
            "uram288": "752",
            "complete_input_sha_verified": "1",
            "complete_input_count": str(BOARD_COMPLETE_INPUT_COUNT),
            "immutable_input_count": str(BOARD_IMMUTABLE_INPUT_COUNT),
            "immutable_input_sha_verified": "1",
            "recursive_source_sha_verified": "1",
            "ooc_route_authorization_verified": "1",
        }
        for key, expected in required_summary.items():
            if summary.get(key) != expected:
                raise RuntimeContractError(
                    f"board post-route gate failed: {key}={summary.get(key)!r}"
                )
        post_route = _load_key_values(root / "post_route_gate_summary.txt")
        if post_route.get("status") != "V5_BOARD_POST_ROUTE_PASS":
            raise RuntimeContractError(
                "board post-route gate report does not contain a PASS status"
            )
        common_post_route = {
            "evidence_class": "FULL_VCU118_BOARD_POST_ROUTE",
            "rtl_variant": BOARD_RTL_VARIANT,
            "rtl_resource_variant": BOARD_RTL_VARIANT,
            "region2_signature_source": region2_signature,
            "core_clock_mhz": "100",
            "ddr0_clock_mhz": "300",
            "ddr1_clock_mhz": "300",
            "v5_serial_instances": "1",
            "old_serial_instances": "0",
            "v5_shared_instances": "1",
            "v5_branch_instances": "2",
            "v5_kernel12_instances": "2",
            "v4_kernel16_instances": "0",
            "history2_repack_instances": "2",
            "generic_repack_instances": "0",
            "dsp48e2": str(BOARD_TOTAL_DSP),
            "mlp_kernel_dsp48e2": "3072",
            "uram288": "752",
            "projection_weight_capture_ok": "1",
            "architecture_boundary_ok": "1",
            "unplaced_primitives": "0",
            "wrong_slr_primitives": "0",
            "compute_clock_buffer_none_ok": "1",
            "no_clock_endpoints": "0",
            "unconstrained_paths": "0",
            "timing_coverage_ok": "1",
            "route_error_nets": "0",
            "explicit_gap_nets": "0",
            "unrouted_nets": "0",
            "some_unrouted_pin_nets": "0",
            "resource_conflict_nets": "0",
            "antenna_island_nets": "0",
            "route_status_partial": "0",
            "route_status_conflicts": "0",
            "route_clean": "1",
            "drc_errors": "0",
            "cdc_critical": "0",
            "data_bufg": "0",
            "congestion_level6_or_higher_windows": "0",
            "exception_scope_policy_ok": "1",
            "live_post_route_rediscovery_ok": "1",
            "base_contract_variant": "P2_COHORT16_COL2_12_2",
            "p5_contract": "P5_INPUT_HALF_LOCAL_8_8",
            "p9_postprocess_contract": "P9_POSTPROCESS_SPLIT_6_4_6",
            "p9_quantizer3_contract": "P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6",
            "p14_region2_relief_contract": "P14_ATTN_REGION2_SHARED_X0_X2",
            "pblock_contract_variant": "P2_COHORT16_COL2_12_2",
            "pblock_contract_ok": "1",
            "pblock_require_placed": "1",
            "pblock_count": "26",
            "canonical_pblock_count": "11",
            "geometry_pblock_count": "10",
            "p5_added_pblock_count": "2",
            "p9_postprocess_added_pblock_count": "2",
            "p9_quantizer3_added_pblock_count": "1",
            "p14_region2_relief_added_pblock_count": "0",
            "total_pblock_count": "26",
            "completed_u8_ff": "4096",
            "completed_meta_ff": "352",
            "input_capture_ff": "12288",
            "input_capture_controls": "48",
            "p5_center_wrong_slr": "0",
            "p5_outer_wrong_slr": "0",
            "p9_postprocess_center_wrong_slr": "0",
            "p9_postprocess_outer_wrong_slr": "0",
            "p9_slr0_row_primitives": "16044",
            "p9_center_row_primitives": "10696",
            "p9_slr2_row_primitives": "16044",
            "p9_quantizer3_primitives": str(P16_QUANTIZER3_PRIMITIVES),
            "p9_quantizer3_grid_range": "CLOCKREGION_X2Y5:CLOCKREGION_X3Y6",
            "p9_quantizer3_wrong_region": "0",
            "p9_quantizer3_unplaced": "0",
            "p14_region2_relief_primitives": summary[
                "p14_region2_relief_primitives"
            ],
            "p14_region2_relief_base_range": "CLOCKREGION_X0Y5:CLOCKREGION_X1Y9",
            "p14_region2_relief_range": "CLOCKREGION_X2Y5:CLOCKREGION_X2Y9",
            "p14_region2_expected_range": "CLOCKREGION_X0Y5:CLOCKREGION_X2Y9",
            "p14_region2_relief_wrong": "0",
            "p14_region2_relief_unplaced": "0",
            "parent_head_ff": "6560",
            "parent_tail_ff": "6560",
            "parent_count_ff": "2",
            "parent_count_replica_equivalence_ok": "1",
            "parent_pointer_ff": "0",
            "local_clear_shared_upstream_ready_paths": "0",
            "branch_credit_shared_upstream_ready_paths": "0",
            "local_clear_gate_compute_ready_paths": "0",
            "branch_credit_gate_compute_ready_paths": "0",
            "local_clear_down_compute_ready_paths": "0",
            "branch_credit_down_compute_ready_paths": "0",
            "local_clear_input_cache_ready_paths": "0",
            "branch_credit_input_cache_ready_paths": "0",
            "geometry_region0_input_primitives": "3136",
            "geometry_region3_input_primitives": "2112",
            "geometry_owner_region2_weight_primitives": "2048",
            "geometry_region0_input_ok": "1",
            "geometry_region3_input_ok": "1",
            "geometry_owner_region2_weight_ok": "1",
            "projected_slr_dsp48e2": " ".join(map(str, BOARD_SLR_DSP)),
            "projected_slr_uram288": "224 224 304",
            "slr0_dsp48e2": "1862",
            "slr1_dsp48e2": str(BOARD_SLR_DSP[1]),
            "slr2_dsp48e2": "1810",
            "slr0_uram288": "224",
            "slr1_uram288": "224",
            "slr2_uram288": "304",
            "pblock_dsp_coverage": str(BOARD_TOTAL_DSP),
            "pblock_uram_coverage": "752",
            "pblock_wrong_slr": "0",
            "physical_placement_ok": "1",
            "physical_ok": "1",
            "floorplan_contract_ok": "1",
        }
        for key, expected in common_post_route.items():
            for label, values in (("summary", summary),
                                  ("post-route gate", post_route)):
                if values.get(key) != expected:
                    raise RuntimeContractError(
                        f"board {label} invariant failed: "
                        f"{key}={values.get(key)!r}"
                    )
        try:
            wns = float(summary["wns_ns"])
            whs = float(summary["whs_ns"])
        except (KeyError, ValueError) as exc:
            raise RuntimeContractError("board summary has invalid WNS/WHS") from exc
        if not math.isfinite(wns) or not math.isfinite(whs) or wns < 0 or whs < 0:
            raise RuntimeContractError(
                f"board timing is not closed: WNS={wns} WHS={whs}"
            )
        if (post_route.get("wns_ns") != summary.get("wns_ns") or
                post_route.get("whs_ns") != summary.get("whs_ns")):
            raise RuntimeContractError(
                "board summary and post-route gate timing disagree"
            )

        bitstream = root / "attention_mlp_vcu118_v5.bit"
        bit_hash = _require_sha(summary.get("bitstream_sha256"),
                                "board bitstream_sha256")
        if post_route.get("bitstream_sha256") != bit_hash:
            raise RuntimeContractError(
                "board summary and post-route gate bitstream SHA disagree"
            )
        try:
            gated_bitstream = Path(post_route["bitstream"]).resolve(strict=True)
        except (KeyError, OSError) as exc:
            raise RuntimeContractError(
                "board post-route gate bitstream path is invalid"
            ) from exc
        if gated_bitstream != bitstream:
            raise RuntimeContractError(
                "board post-route gate names a different bitstream"
            )
        if manifested.get(bitstream) != bit_hash:
            raise RuntimeContractError("bitstream SHA lineage disagrees with summary")
        checkpoint = root / "attention_mlp_vcu118_v5_post_route.dcp"
        checkpoint_hash = _require_sha(summary.get("checkpoint_sha256"),
                                       "board checkpoint_sha256")
        if manifested.get(checkpoint) != checkpoint_hash:
            raise RuntimeContractError("checkpoint SHA lineage disagrees with summary")
        return cls(
            root, BOARD_RTL_VARIANT, bitstream, bit_hash, checkpoint_hash,
            wns, whs, len(manifested),
        )

    def as_dict(self) -> dict:
        result = asdict(self)
        result["report_dir"] = str(self.report_dir)
        result["bitstream"] = str(self.bitstream)
        return result


@dataclass(frozen=True)
class BoardAuditEvidence:
    report_dir: Path
    bitstream_sha256: str
    checkpoint_sha256: str
    input_manifest_sha256: str
    output_count: int
    profile: str = LEGACY_PROFILE

    @classmethod
    def load(
        cls, report_dir: str | Path, board: BoardBuildEvidence
    ) -> "BoardAuditEvidence":
        if board.profile == CURRENT_PROFILE:
            return _load_current_board_audit(cls, report_dir, board)
        if board.profile != LEGACY_PROFILE:
            raise RuntimeContractError("unsupported board audit evidence profile")
        root = Path(report_dir).resolve(strict=True)
        if not root.is_dir():
            raise RuntimeContractError(
                f"board audit report is not a directory: {root}"
            )
        manifested = _verify_exact_output_tree(
            root, BOARD_AUDIT_REQUIRED_FILES, "board audit"
        )
        summary = _load_key_values(root / "summary.txt")
        post_opt_summary, production_region2_summary, _ = \
            _verify_p16_post_route_reports(root, "board audit", summary)
        launcher = _load_key_values(root / "launcher_status.txt")
        for key, expected in {
            "status": "PASS",
            "final_exit_code": "0",
            "vivado_exit_code": "0",
            "vivado_invoked": "1",
            "input_sha_precheck": "1",
            "input_sha_postcheck": "1",
            "input_manifest_sha_match": "1",
            "rtl_variant": BOARD_RTL_VARIANT,
        }.items():
            if launcher.get(key) != expected:
                raise RuntimeContractError(
                    f"board audit launcher gate failed: "
                    f"{key}={launcher.get(key)!r}"
                )

        post_route = _load_key_values(root / "post_route_gate_summary.txt")
        if (summary.get("status") != "V5_BOARD_INDEPENDENT_AUDIT_PASS" or
                summary.get("post_route_gate_status") !=
                "V5_BOARD_POST_ROUTE_PASS" or
                summary.get("audit_input_manifest_entries") !=
                str(BOARD_AUDIT_INPUT_COUNT) or
                summary.get("audit_input_manifests_verified") != "1" or
                post_route.get("status") != "V5_BOARD_POST_ROUTE_PASS"):
            raise RuntimeContractError("independent board audit is not PASS")

        board_summary = _load_key_values(board.report_dir / "summary.txt")
        for key in POST_ROUTE_CROSSCHECK_FIELDS:
            expected = board_summary.get(key)
            if (expected is None or summary.get(key) != expected or
                    post_route.get(key) != expected):
                raise RuntimeContractError(
                    f"board audit P16 cross-check failed: {key}"
                )
        for key in (
            "p16_post_opt_summary", "p16_post_opt_summary_sha256",
            "p16_production_region2_summary",
            "p16_production_region2_summary_sha256",
            "p16_production_dcp_sha256",
        ):
            if summary.get(key) != board_summary.get(key):
                raise RuntimeContractError(
                    f"board audit P16 lineage cross-check failed: {key}"
                )

        input_sha = root / "INPUT_SHA256SUMS"
        input_manifest_sha = sha256_file(input_sha)
        if (summary.get("audit_input_manifest_sha256") !=
                input_manifest_sha or
                launcher.get("input_manifest_sha256") != input_manifest_sha):
            raise RuntimeContractError(
                "board audit input-manifest SHA256 lineage mismatch"
            )
        frozen_inputs = _verify_frozen_input_closure(
            root / "INPUT_FILES", input_sha, BOARD_AUDIT_INPUT_COUNT,
            "board audit",
        )
        checkpoint = board.report_dir / "attention_mlp_vcu118_v5_post_route.dcp"
        scripts = Path(__file__).resolve().parents[1] / "vivado" / "scripts"
        expected_inputs = {
            checkpoint.resolve(), board.bitstream.resolve(),
            (board.report_dir / "XDC_SOURCE_INVENTORY").resolve(),
            (board.report_dir / "summary.txt").resolve(),
            (scripts / "audit_attention_mlp_vcu118_v5_post_route.tcl").resolve(),
            (scripts / "attention_mlp_vcu118_v5_post_route_gate.tcl").resolve(),
            (scripts / "v5_production_floorplan_selectors.tcl").resolve(),
            (scripts /
             "projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl").resolve(),
            (scripts / "v5_production_p5_input_partition_floorplan.tcl").resolve(),
            (scripts /
             "v5_production_p9_postprocess_partition_floorplan.tcl").resolve(),
            (scripts /
             "v5_production_p16_noclip_quantizer3_locality_floorplan.tcl").resolve(),
            (scripts /
             "v5_production_p16_noclip_region2_x2_relief_floorplan.tcl").resolve(),
            (scripts /
             "audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl").resolve(),
            (scripts /
             "projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl").resolve(),
            (scripts /
             "projection_core16x16_w8_reuse_ooc_floorplan.tcl").resolve(),
            (scripts /
             "v5_production_p9_quantizer3_locality_floorplan.tcl").resolve(),
            (scripts /
             "v5_production_p14_region2_x2_relief_floorplan.tcl").resolve(),
            post_opt_summary.resolve(), production_region2_summary.resolve(),
            (scripts /
             "run_attention_mlp_vcu118_v5_post_route_audit.sh").resolve(),
        }
        if set(frozen_inputs) != expected_inputs:
            raise RuntimeContractError(
                "board audit does not bind the exact P16 board input set"
            )

        if (summary.get("bitstream_sha256") != board.bitstream_sha256 or
                summary.get("checkpoint_sha256") != board.checkpoint_sha256 or
                post_route.get("bitstream_sha256") != board.bitstream_sha256):
            raise RuntimeContractError(
                "board audit DCP/bitstream hashes disagree with board build"
            )
        try:
            audited_bitstream = Path(summary["bitstream"]).resolve(strict=True)
            gated_bitstream = Path(post_route["bitstream"]).resolve(strict=True)
            audited_checkpoint = Path(summary["checkpoint"]).resolve(
                strict=True
            )
        except (KeyError, OSError) as exc:
            raise RuntimeContractError(
                "board audit DCP/bitstream path is invalid"
            ) from exc
        if (audited_bitstream != board.bitstream or
                gated_bitstream != board.bitstream or
                audited_checkpoint != checkpoint):
            raise RuntimeContractError(
                "board audit names a different DCP or bitstream"
            )
        return cls(
            root, board.bitstream_sha256, board.checkpoint_sha256,
            input_manifest_sha, len(manifested),
        )

    def as_dict(self) -> dict:
        result = asdict(self)
        result["report_dir"] = str(self.report_dir)
        return result


@dataclass(frozen=True)
class BoardProgrammingEvidence:
    report_dir: Path
    bitstream_sha256: str
    input_manifest_sha256: str
    hw_server_url: str
    device: str
    part: str
    output_count: int
    profile: str = LEGACY_PROFILE

    @classmethod
    def load(
        cls, report_dir: str | Path, board: BoardBuildEvidence,
        audit: BoardAuditEvidence,
    ) -> "BoardProgrammingEvidence":
        if board.profile != audit.profile:
            raise RuntimeContractError("board/audit programming profiles disagree")
        if board.profile == CURRENT_PROFILE:
            return _load_current_board_programming(cls, report_dir, board, audit)
        if board.profile != LEGACY_PROFILE:
            raise RuntimeContractError("unsupported board programming profile")
        root = Path(report_dir).resolve(strict=True)
        if not root.is_dir():
            raise RuntimeContractError(
                f"board programming report is not a directory: {root}"
            )
        manifested = _verify_exact_output_tree(
            root, BOARD_PROGRAM_REQUIRED_FILES, "board programming"
        )
        launcher = _load_key_values(root / "launcher_status.txt")
        for key, expected in {
            "status": "PASS",
            "vivado_exit_code": "0",
            "input_sha_postcheck": "1",
            "input_manifest_sha_match": "1",
            "board_output_sha_postcheck": "1",
            "audit_output_sha_postcheck": "1",
        }.items():
            if launcher.get(key) != expected:
                raise RuntimeContractError(
                    f"board programming launcher gate failed: "
                    f"{key}={launcher.get(key)!r}"
                )
        input_sha = root / "INPUT_SHA256SUMS"
        input_manifest_sha = sha256_file(input_sha)
        if launcher.get("input_manifest_sha256") != input_manifest_sha:
            raise RuntimeContractError(
                "board programming input-manifest SHA256 mismatch"
            )

        program_tcl = Path(__file__).resolve().parents[1] / "vivado" / \
            "scripts" / "program_attention_mlp_vcu118_v5_bitstream.tcl"
        program_launcher = Path(__file__).resolve().parents[1] / "vivado" / \
            "scripts" / "run_program_attention_mlp_vcu118_v5_bitstream.sh"
        frozen_inputs = _verify_frozen_input_closure(
            root / "INPUT_FILES", input_sha, 5, "board programming"
        )
        expected_inputs = {
            board.bitstream,
            board.report_dir / "OUTPUT_SHA256SUMS",
            audit.report_dir / "OUTPUT_SHA256SUMS",
            program_tcl,
            program_launcher,
        }
        if set(frozen_inputs) != expected_inputs:
            raise RuntimeContractError(
                "board programming does not bind the exact audited input set"
            )

        summary = _load_key_values(root / "summary.txt")
        for key in ("hw_server_url", "hw_target", "device", "part"):
            if not summary.get(key):
                raise RuntimeContractError(
                    f"board programming summary has empty {key}"
                )
        if (summary.get("status") != "V5_VCU118_PROGRAM_PASS" or
                not summary.get("tool", "").startswith("2025.2") or
                "xcvu9p" not in summary["part"].lower() or
                summary.get("program_done") != "1"):
            raise RuntimeContractError("board programming summary is not PASS")
        try:
            programmed = Path(summary["program_file"]).resolve(strict=True)
            bitstream_size = int(summary["bitstream_size_bytes"])
        except (KeyError, OSError, ValueError) as exc:
            raise RuntimeContractError(
                "board programming bitstream identity is invalid"
            ) from exc
        if (programmed != board.bitstream or
                bitstream_size != board.bitstream.stat().st_size or
                summary.get("bitstream_sha256") != board.bitstream_sha256 or
                audit.bitstream_sha256 != board.bitstream_sha256):
            raise RuntimeContractError(
                "board programming bitstream SHA/size/path disagrees with audit"
            )
        return cls(
            root, board.bitstream_sha256, input_manifest_sha,
            summary["hw_server_url"], summary["device"], summary["part"],
            len(manifested),
        )

    def as_dict(self) -> dict:
        result = asdict(self)
        result["report_dir"] = str(self.report_dir)
        return result


def _current_file_id(
    raw: object, base: Path, label: str, *, expected: Path | None = None,
) -> FrozenFile:
    fields = _require_fields(raw, {"path", "bytes", "sha256"}, label)
    path_text = fields["path"]
    if not isinstance(path_text, str) or not Path(path_text).is_absolute():
        raise RuntimeContractError(f"{label} must have an absolute path")
    unresolved = Path(path_text)
    if unresolved.is_symlink():
        raise RuntimeContractError(f"{label} cannot be a symlink")
    try:
        canonical = unresolved.resolve(strict=True)
    except OSError as exc:
        raise RuntimeContractError(f"{label} file is missing") from exc
    if str(canonical) != path_text:
        raise RuntimeContractError(f"{label} path is not canonical")
    if not canonical.is_relative_to(Path(__file__).resolve().parents[1]):
        raise RuntimeContractError(f"{label} is outside the new hardware root")
    item = FrozenFile.parse({"path": path_text, "size": fields["bytes"],
                             "sha256": fields["sha256"]}, base, label)
    if expected is not None and item.path != expected.resolve(strict=True):
        raise RuntimeContractError(f"{label} does not name the expected report")
    item.verify()
    return item


def _current_input_manifest(
    file: FrozenFile, expected_count: int | None = None,
) -> dict[Path, str]:
    if expected_count is not None and (
        type(expected_count) is not int or expected_count <= 0
    ):
        raise RuntimeContractError("current input count is invalid")
    entries: dict[Path, str] = {}
    hardware_root = Path(__file__).resolve().parents[1]
    board_install = Path(
        "/home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/"
        "XilinxBoardStore/boards/Xilinx/vcu118/2.0"
    )
    for number, row in enumerate(file.path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (/.+)", row)
        if match is None:
            raise RuntimeContractError(f"current input manifest line {number} is invalid")
        unresolved = Path(match.group(2))
        try:
            path = unresolved.resolve(strict=True)
        except OSError as exc:
            raise RuntimeContractError(f"current input {number} is missing") from exc
        if (str(path) != match.group(2) or unresolved.is_symlink() or
                not path.is_file() or path.stat().st_size == 0 or path in entries or
                not (path.is_relative_to(hardware_root) or
                     path.is_relative_to(board_install))):
            raise RuntimeContractError(f"current input {number} is noncanonical/duplicate")
        if sha256_file(path) != match.group(1):
            raise RuntimeContractError(f"current input {number} hash mismatch")
        entries[path] = match.group(1)
    if not entries or (expected_count is not None and len(entries) != expected_count):
        raise RuntimeContractError("current input manifest count mismatch")
    return entries


def _current_stage_receipt(
    raw: object, stage: str, project: Path, label: str,
) -> FrozenFile:
    fields = _require_fields(raw, {"path", "bytes", "sha256", "exit_code"}, label)
    if type(fields["exit_code"]) is not int or fields["exit_code"] != 0:
        raise RuntimeContractError(f"{label} did not exit zero")
    item = _current_file_id(
        {key: fields[key] for key in ("path", "bytes", "sha256")},
        project.parent, label,
    )
    values = _load_key_values(item.path)
    if (values.get("stage") != stage or values.get("project") != str(project) or
            values.get("reports") != str(item.path.parent) or
            values.get("exit_code") != "0" or
            values.get("native_exit_code", "0") != "0"):
        raise RuntimeContractError(f"{label} does not bind the original {stage} exit")
    return item


def _current_report_ids(
    raw: object, root: Path, names: Sequence[str], label: str,
) -> dict[str, FrozenFile]:
    reports = _require_fields(raw, set(names), label)
    return {name: _current_file_id(reports[name], root, f"{label} {name}",
                                   expected=root / name) for name in names}


def _current_identity(raw: object, path: Path) -> None:
    expected = {
        "vivado": "2025.2", "part": "xcvu9p-flga2104-2L-e",
        "board": "xilinx.com:vcu118:part0:2.0",
        "top": "scalellm_vcu118_f05_bd_wrapper",
    }
    identity = _require_fields(raw, {*expected, "defines"}, "current build identity")
    values = _load_key_values(path)
    if any(identity[key] != value or values.get(key) != value
           for key, value in expected.items()):
        raise RuntimeContractError("current board part/tool/top identity mismatch")
    if values.get("project") != "scalellm_vcu118_f05":
        raise RuntimeContractError("current board project identity mismatch")
    defines = {
        "HAP_BOARD_BUILD", "HAP_BOARD_V5",
        "HAP_MLP_FULL_COMMAND_V5_MODULE=hap_mlp_full_command16_s54",
        "HAP_ATTENTION_BOARD_MODULE=hap_attention_board_cohort16_core",
    }
    if (not isinstance(identity["defines"], str) or
            set(identity["defines"].split()) != defines or
            identity["defines"] != values.get("defines")):
        raise RuntimeContractError("current board compile flags mismatch")


def _current_create_receipt(
    raw: object, project: Path, current_inputs: Mapping[Path, str],
) -> None:
    fields = _require_fields(raw, {"launcher", "input_manifest", "input_count",
                                   "summary"}, "current create receipt")
    launcher = _current_stage_receipt(fields["launcher"], "create", project,
                                      "current create launcher")
    manifest = _current_file_id(fields["input_manifest"], launcher.path.parent,
                                "current constructor inputs",
                                expected=launcher.path.parent / "constructor_inputs.sha256")
    original = _current_input_manifest(manifest, fields["input_count"])
    if any(current_inputs.get(path) != digest for path, digest in original.items()):
        raise RuntimeContractError("current build inputs drifted from constructor")
    _current_file_id(fields["summary"], launcher.path.parent,
                     "current constructor summary",
                     expected=launcher.path.parent / "constructor_summary.txt")


def _current_timing(path: Path) -> dict[str, float]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if all(token in line for token in (
                "WNS(ns)", "TNS(ns)", "WHS(ns)", "THS(ns)",
                "WPWS(ns)", "TPWS(ns)")):
            for candidate in lines[index + 1:index + 6]:
                fields = candidate.split()
                if len(fields) < 12:
                    continue
                try:
                    values = list(map(float, fields[:12]))
                except ValueError:
                    continue
                result = dict(zip((
                    "wns", "tns", "setup_failing", "setup_total",
                    "whs", "ths", "hold_failing", "hold_total",
                    "wpws", "tpws", "pulse_failing", "pulse_total",
                ), values, strict=True))
                if (result["wns"] < 0 or result["tns"] != 0 or
                        result["setup_failing"] != 0 or result["whs"] < 0 or
                        result["ths"] != 0 or result["hold_failing"] != 0 or
                        result["wpws"] < 0 or result["tpws"] != 0 or
                        result["pulse_failing"] != 0 or
                        result["setup_total"] <= 0 or result["hold_total"] <= 0):
                    raise RuntimeContractError(
                        f"current physical timing is not closed: {path}"
                    )
                return result
    raise RuntimeContractError(f"current timing summary is missing: {path}")


def _current_check_timing(path: Path) -> dict[str, int]:
    checks = {name: int(count) for name, count in re.findall(
        r"checking\s+([A-Za-z0-9_]+)\s+\((\d+)\)",
        path.read_text(encoding="utf-8"))}
    required = ("no_clock", "unconstrained_internal_endpoints", "multiple_clock",
                "generated_clocks", "loops", "latch_loops")
    if not all(checks.get(name) == 0 for name in required):
        raise RuntimeContractError(
            f"current check_timing coverage/blocker mismatch: {checks}"
        )
    return checks


def _current_route(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    labels = {
        "routable": r"# of routable nets\.*:\s*(\d+)",
        "fully_routed": r"# of fully routed nets\.*:\s*(\d+)",
        "routing_errors": r"# of nets with routing errors\.*:\s*(\d+)",
        "unrouted": r"# of unrouted nets\.*:\s*(\d+)",
        "partial": r"# of nets with some unrouted pins\.*:\s*(\d+)",
        "conflicts": r"# of nets with resource conflicts\.*:\s*(\d+)",
        "antenna": r"# of nets with antenna violations\.*:\s*(\d+)",
        "partial_antenna": r"# of nets with partial antenna violations\.*:\s*(\d+)",
    }
    values = {}
    for name, pattern in labels.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            raise RuntimeContractError(f"current route report lacks {name}: {path}")
        values[name] = int(match.group(1))
    if (values["routable"] <= 0 or values["fully_routed"] != values["routable"] or
            any(values[name] != 0 for name in (
                "routing_errors", "unrouted", "partial", "conflicts", "antenna",
                "partial_antenna"))):
        raise RuntimeContractError(f"current route is illegal: {values}")
    return values


def _current_parse_physical(directory: Path, *, final: bool) -> dict:
    names = CURRENT_FINAL_REPORTS if final else {
        "timing": "timing_reopened.rpt",
        "check_timing": "check_timing_reopened.rpt",
        "clocks": "clocks_reopened.rpt",
        "clock_interaction": "clock_interaction_reopened.rpt",
        "route": "route_status_reopened.rpt", "drc": "drc_reopened.rpt",
        "cdc": "cdc_reopened.rpt", "pulse": "pulse_width_reopened.rpt",
        "pulse_violators": "pulse_width_violators_reopened.rpt",
        "bus_skew": "bus_skew_reopened.rpt",
    }
    for name in names.values():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise RuntimeContractError(f"current physical report is missing: {path}")
    timing = _current_timing(directory / names["timing"])
    checks = _current_check_timing(directory / names["check_timing"])
    clocks = (directory / names["clocks"]).read_text(encoding="utf-8")
    for token in ("pcie_refclk", "default_250mhz_clk1_clk_p",
                  "default_250mhz_clk2_clk_p", "10.000", "5.000", "4.000"):
        if token not in clocks:
            raise RuntimeContractError(f"current clock report lacks {token}")
    interaction = (directory / names["clock_interaction"]).read_text(encoding="utf-8")
    if "VIOLATED" in interaction.upper():
        raise RuntimeContractError("current clock interaction report is violated")
    route = _current_route(directory / names["route"])
    drc = (directory / names["drc"]).read_text(encoding="utf-8")
    if (re.search(r"(?mi)^\s*(?:ERROR|CRITICAL WARNING)\b", drc) or
            re.search(r"(?i)(?:no|0)\s+DRC\s+violations", drc) is None):
        raise RuntimeContractError("current DRC report is not clean")
    cdc_text = (directory / names["cdc"]).read_text(encoding="utf-8")
    rows = re.findall(r"(?m)^\s*(CDC-\d+)\s+(Critical|Warning|Info)\s+(\d+)\s+",
                      cdc_text)
    if not rows and re.search(r"(?i)no\s+CDC\s+paths", cdc_text) is None:
        raise RuntimeContractError("current CDC summary is missing")
    cdc = {rule: int(count) for rule, _severity, count in rows}
    if any(severity == "Critical" and int(count) != 0
           for _rule, severity, count in rows):
        raise RuntimeContractError("current CDC report has critical findings")
    pulse = (directory / names["pulse_violators"]).read_text(encoding="utf-8")
    if ("VIOLATED" in pulse.upper() or
            re.search(r"(?i)(?:no|0)\s+(?:min\s+)?pulse(?:[- ]width)?\s+violations",
                      pulse) is None):
        raise RuntimeContractError("current pulse-width report is not clean")
    skew = (directory / names["bus_skew"]).read_text(encoding="utf-8")
    if ("BUS SKEW" not in skew.upper() or "VIOLATED" in skew.upper() or
            re.search(r"(?i)(all .*bus skew constraints are met|no bus[- ]skew violations)",
                      skew) is None):
        raise RuntimeContractError("current bus-skew report is not clean")
    return {"timing": timing, "check_timing": checks, "route": route, "cdc": cdc}


def _current_bound_summary(raw: object, label: str) -> tuple[Path, str]:
    if not isinstance(raw, dict) or set(raw) < {"path", "sha256"}:
        raise RuntimeContractError(f"{label} identity is incomplete")
    fields = raw
    if not isinstance(fields["path"], str):
        raise RuntimeContractError(f"{label} path is invalid")
    path = Path(fields["path"])
    if (path.is_symlink() or not path.resolve(strict=True).is_relative_to(
            Path(__file__).resolve().parents[1] / "vivado" / "reports") or
            sha256_file(path) != _require_sha(fields["sha256"], label)):
        raise RuntimeContractError(f"{label} identity drifted")
    return path.resolve(strict=True), fields["sha256"]


def _current_bitstream_package(report_dir: str | Path) -> dict:
    root = Path(report_dir).resolve(strict=True)
    hardware_root = Path(__file__).resolve().parents[1]
    reports_root = hardware_root / "vivado" / "reports"
    if (not root.is_dir() or not root.is_relative_to(reports_root)):
        raise RuntimeContractError("current bitstream report is outside the hardware root")
    evidence_path = root / "bitstream_evidence.json"
    raw = _require_fields(_load_json(evidence_path), {
        "schema", "status", "profile", "part", "format_id", "abi", "clocks",
        "preflight", "checkpoint", "bitstream", "bitgen_facts", "host_sources",
        "board_accessed",
    }, "current bitstream evidence")
    if (raw["schema"] != "scalellm_mission0005_bitstream_evidence_v1" or
            raw["status"] != "BITSTREAM_GENERATED_NOT_BOARD_TESTED" or
            raw["profile"] != CURRENT_PROFILE or raw["part"] != CURRENT_PART or
            raw["format_id"] != CURRENT_FORMAT_ID or raw["abi"] != CURRENT_ABI or
            raw["clocks"] != CURRENT_CLOCKS or raw["board_accessed"] is not False):
        raise RuntimeContractError("current bitstream evidence identity/status mismatch")
    preflight_file = _current_file_id(raw["preflight"], root, "current bitgen preflight",
                                      expected=root / "bitgen_preflight.json")
    preflight = _require_fields(_load_json(preflight_file.path), {
        "schema", "status", "profile", "part", "clocks", "format_id", "abi",
        "project", "route_dir", "audit_dir", "checkpoint", "route_input_manifest",
        "route_input_count", "audit_input_manifest", "audit_envelope",
        "route_envelope", "route_launcher", "audit_launcher", "build_identity",
        "physical", "joint", "full32", "host_sources", "global_deadline_epoch",
        "created_epoch",
    }, "current bitgen preflight")
    if (preflight["schema"] != "scalellm_mission0005_bitgen_preflight_v1" or
            preflight["status"] != "ELIGIBLE_FOR_LIVE_VIVADO_SIGNOFF_NOT_BITSTREAM" or
            preflight["profile"] != CURRENT_PROFILE or preflight["part"] != CURRENT_PART or
            preflight["format_id"] != CURRENT_FORMAT_ID or preflight["abi"] != CURRENT_ABI or
            preflight["clocks"] != CURRENT_CLOCKS):
        raise RuntimeContractError("current bitgen preflight identity/status mismatch")
    project = Path(preflight["project"]).resolve(strict=True)
    if not project.is_relative_to(hardware_root / "vivado" / "project"):
        raise RuntimeContractError("current bitgen project is outside the hardware root")
    route_dir = Path(preflight["route_dir"]).resolve(strict=True)
    audit_dir = Path(preflight["audit_dir"]).resolve(strict=True)
    if (not route_dir.is_relative_to(reports_root) or
            not audit_dir.is_relative_to(reports_root) or route_dir == audit_dir):
        raise RuntimeContractError("current route/audit report directory is invalid")
    route_envelope = _current_file_id(preflight["route_envelope"], root,
                                      "current route envelope",
                                      expected=route_dir / "board_evidence.json")
    audit_envelope = _current_file_id(preflight["audit_envelope"], root,
                                      "current audit envelope",
                                      expected=audit_dir / "audit_evidence.json")
    envelope_raw = {}
    for envelope, schema, stage, label in (
            (route_envelope, "scalellm_board_build_evidence_v2", "route", "route"),
            (audit_envelope, "scalellm_board_audit_evidence_v2", "audit", "audit")):
        item = _load_json(envelope.path)
        if (item.get("schema") != schema or item.get("profile") != CURRENT_PROFILE or
                item.get("stage") != stage or item.get("qualification") != "HOLD" or
                item.get("physical_signoff") is not False or item.get("bitstream") is not None):
            raise RuntimeContractError(f"current original {label} HOLD envelope was relabeled")
        envelope_raw[stage] = item
    for stage, names, directory in (
            ("route", CURRENT_ROUTE_REPORTS, route_dir),
            ("audit", CURRENT_AUDIT_REPORTS, audit_dir)):
        reports = envelope_raw[stage].get("reports")
        if not isinstance(reports, dict) or not set(names).issubset(reports):
            raise RuntimeContractError(f"current {stage} report identity set is incomplete")
        for name in names:
            _current_file_id(reports[name], directory, f"current {stage} report {name}",
                             expected=directory / name)
    route_manifest = _current_file_id(preflight["route_input_manifest"], root,
                                      "current route input manifest",
                                      expected=route_dir / "inputs.sha256")
    route_inputs = _current_input_manifest(route_manifest, preflight["route_input_count"])
    required_route_inputs = {
        hardware_root / "vivado/scripts/build_vcu118_board.tcl",
        hardware_root / "vivado/scripts/emit_current_board_evidence.py",
        hardware_root / "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
        hardware_root / "vivado/constraints/attention_mlp_vcu118_board_v5.xdc",
        hardware_root / "vivado/constraints/mission0005_coordinated_partition.xdc",
    }
    if not required_route_inputs.issubset(route_inputs):
        raise RuntimeContractError("current route input closure lacks production sources")
    audit_manifest = _current_file_id(preflight["audit_input_manifest"], root,
                                      "current audit input manifest",
                                      expected=audit_dir / "audit_inputs.sha256")
    audit_inputs = _current_input_manifest(audit_manifest)
    if any(audit_inputs.get(path.resolve(strict=True)) != sha256_file(path)
           for path in (route_dir / "inputs.sha256", route_dir / "build_identity.txt",
                        route_dir / "routed.dcp")):
        raise RuntimeContractError("current audit input closure does not bind the route")
    route_launcher = _current_file_id(preflight["route_launcher"], root,
                                      "current route launcher",
                                      expected=route_dir / "launcher_status.txt")
    audit_launcher = _current_file_id(preflight["audit_launcher"], root,
                                      "current audit launcher",
                                      expected=audit_dir / "launcher_status.txt")
    _current_stage_receipt({**preflight["route_launcher"], "exit_code": 0},
                           "route", project, "current route launcher")
    _current_stage_receipt({**preflight["audit_launcher"], "exit_code": 0},
                           "audit", project, "current audit launcher")
    identity_path = route_dir / "build_identity.txt"
    _current_identity(preflight["build_identity"], identity_path)
    checkpoint = _current_file_id(raw["checkpoint"], root, "current routed checkpoint",
                                  expected=route_dir / "routed.dcp")
    preflight_checkpoint = _current_file_id(preflight["checkpoint"], root,
                                            "current preflight checkpoint",
                                            expected=checkpoint.path)
    if checkpoint.sha256 != preflight_checkpoint.sha256:
        raise RuntimeContractError("current bitgen/preflight checkpoints disagree")
    bitstream = _current_file_id(raw["bitstream"], root, "current bitstream",
                                 expected=root / "scalellm_vcu118_f05_mission0005.bit")
    facts_file = _current_file_id(raw["bitgen_facts"], root, "current bitgen facts",
                                  expected=root / "bitgen_facts.txt")
    facts = _load_key_values(facts_file.path)
    required_facts = {
        "status": "MISSION0005_BITGEN_VIVADO_PASS", "part": CURRENT_PART,
        "profile": CURRENT_PROFILE, "format_id": CURRENT_FORMAT_ID,
        "abi": CURRENT_ABI, "core_mhz": "100", "ddr0_ui_mhz": "200",
        "ddr1_ui_mhz": "200", "reference_ps": "4000", "board_accessed": "0",
        "preflight_sha256": preflight_file.sha256,
        "checkpoint_sha256": checkpoint.sha256, "bitstream_sha256": bitstream.sha256,
    }
    if (any(facts.get(name) != value for name, value in required_facts.items()) or
            Path(facts.get("preflight", "")).resolve() != preflight_file.path or
            Path(facts.get("checkpoint", "")).resolve() != checkpoint.path or
            Path(facts.get("bitstream", "")).resolve() != bitstream.path):
        raise RuntimeContractError("current bitgen facts do not bind the package")
    physical = _current_parse_physical(root, final=True)
    try:
        facts_wns = float(facts["worst_setup_slack_ns"])
        facts_whs = float(facts["worst_hold_slack_ns"])
    except (KeyError, ValueError) as exc:
        raise RuntimeContractError("current bitgen facts have invalid timing") from exc
    if (abs(facts_wns - physical["timing"]["wns"]) > 0.001 or
            abs(facts_whs - physical["timing"]["whs"]) > 0.001):
        raise RuntimeContractError("current bitgen facts/raw timing disagree")
    if preflight["physical"] != _current_parse_physical(audit_dir, final=False):
        raise RuntimeContractError("current preflight/reopened physical evidence disagrees")
    joint_path, _joint_sha = _current_bound_summary(preflight["joint"], "current joint")
    full32_path, _full32_sha = _current_bound_summary(preflight["full32"], "current full32")
    norm = preflight["joint"].get("norm_adoption")
    if (preflight["joint"].get("boundaries") != 4 or not isinstance(norm, dict) or
            norm.get("cases") != 6 or norm.get("reuse_only") is not True or
            preflight["full32"].get("comparisons") != 128):
        raise RuntimeContractError("current joint/norm/full32 scope is incomplete")
    _current_bound_summary({"path": norm.get("path"), "sha256": norm.get("sha256")},
                           "current norm adoption")
    host_rows = raw["host_sources"]
    if host_rows != preflight["host_sources"] or not isinstance(host_rows, list):
        raise RuntimeContractError("current Host source closure differs from preflight")
    host_files = [_current_file_id(item, root, "current Host source") for item in host_rows]
    this_source = Path(__file__).resolve(strict=True)
    if not any(item.path == this_source for item in host_files):
        raise RuntimeContractError("current Host source closure omits scalellm_board.py")
    launcher = _load_key_values(root / "launcher_status.txt")
    if (launcher.get("stage") != "bitgen" or launcher.get("exit_code") != "0" or
            launcher.get("native_exit_code") != "0" or
            launcher.get("project") != str(project) or
            launcher.get("route_reports") != str(route_dir) or
            launcher.get("audit_reports") != str(audit_dir) or
            launcher.get("bitstream_generated") != "1" or
            launcher.get("board_accessed") != "0"):
        raise RuntimeContractError("current bitgen launcher receipt is incomplete")
    bitgen_inputs_file = FrozenFile.parse(
        {"path": str(root / "bitgen_inputs.sha256"),
         "size": (root / "bitgen_inputs.sha256").stat().st_size,
         "sha256": sha256_file(root / "bitgen_inputs.sha256")}, root,
        "current bitgen input manifest")
    bitgen_inputs = _current_input_manifest(bitgen_inputs_file, 7)
    required_bitgen_inputs = {
        hardware_root / "vivado/scripts/run_mission0005_bitgen.sh",
        hardware_root / "vivado/scripts/mission0005_post_route_gate.py",
        hardware_root / "vivado/scripts/mission0005_bitgen.tcl",
        hardware_root / "vivado/constraints/vcu118_ddr4_explicit_pins.xdc",
        preflight_file.path, checkpoint.path,
    }
    if not required_bitgen_inputs.issubset(bitgen_inputs):
        raise RuntimeContractError("current bitgen input closure is incomplete")
    return {"root": root, "project": project, "route_dir": route_dir,
            "audit_dir": audit_dir, "route_envelope": route_envelope,
            "audit_envelope": audit_envelope, "route_inputs": route_inputs,
            "audit_manifest": audit_manifest, "checkpoint": checkpoint,
            "bitstream": bitstream, "preflight": preflight,
            "physical": physical, "joint_path": joint_path,
            "full32_path": full32_path, "output_count": len(CURRENT_FINAL_REPORTS)}


def _load_current_board_build(cls, report_dir: str | Path) -> BoardBuildEvidence:
    package = _current_bitstream_package(report_dir)
    return cls(
        package["root"], "FORMAT05_CURRENT", package["bitstream"].path,
        package["bitstream"].sha256, package["checkpoint"].sha256,
        package["physical"]["timing"]["wns"],
        package["physical"]["timing"]["whs"], package["output_count"],
        CURRENT_PROFILE,
    )


def _load_current_board_audit(
    cls, report_dir: str | Path, board: BoardBuildEvidence,
) -> BoardAuditEvidence:
    package = _current_bitstream_package(board.report_dir)
    root = Path(report_dir).resolve(strict=True)
    if root != package["audit_dir"]:
        raise RuntimeContractError("current audit directory differs from bitgen preflight")
    raw = _load_json(root / "audit_evidence.json")
    required = {"schema", "profile", "stage", "qualification",
                "original_stage_exits", "project", "build", "input_manifest",
                "input_count", "reports", "bitstream", "physical_signoff",
                "source_synthesis", "source_route", "routed_checkpoint"}
    if not isinstance(raw, dict) or not required.issubset(raw):
        raise RuntimeContractError("current board audit envelope fields are incomplete")
    if (raw["schema"] != "scalellm_board_audit_evidence_v2" or
            raw["profile"] != CURRENT_PROFILE or raw["stage"] != "audit" or
            raw["qualification"] != "HOLD" or raw["physical_signoff"] is not False or
            raw["bitstream"] is not None or Path(raw["project"]).resolve() != package["project"]):
        raise RuntimeContractError("current original audit HOLD envelope was relabeled")
    _current_identity(raw["build"], package["route_dir"] / "build_identity.txt")
    input_file = _current_file_id(raw["input_manifest"], root,
                                  "current audit inputs",
                                  expected=root / "audit_inputs.sha256")
    inputs = _current_input_manifest(input_file, raw["input_count"])
    if input_file.sha256 != package["audit_manifest"].sha256:
        raise RuntimeContractError("current audit/preflight input manifests disagree")
    source_route = _require_fields(raw["source_route"], {
        "input_manifest", "build_identity", "board_evidence",
    }, "current audit routed source")
    for key, filename in (("input_manifest", "inputs.sha256"),
                          ("build_identity", "build_identity.txt"),
                          ("board_evidence", "board_evidence.json")):
        item = _current_file_id(source_route[key], root,
                                f"current audit route {key}",
                                expected=package["route_dir"] / filename)
        if key != "board_evidence" and inputs.get(item.path) != item.sha256:
            raise RuntimeContractError("current audit input does not bind route file")
    checkpoint = _current_file_id(raw["routed_checkpoint"], root,
                                  "current audit routed checkpoint",
                                  expected=package["checkpoint"].path)
    if (checkpoint.sha256 != board.checkpoint_sha256 or
            inputs.get(checkpoint.path) != checkpoint.sha256):
        raise RuntimeContractError("current audit DCP/input identity mismatch")
    reports = _current_report_ids(raw["reports"], root, CURRENT_AUDIT_REPORTS,
                                  "current reopened audit report")
    physical = _current_parse_physical(root, final=False)
    if physical != package["preflight"]["physical"]:
        raise RuntimeContractError("current reopened audit differs from preflight")
    summary = _load_key_values(root / "audit_summary.txt")
    if (summary.get("status") != "REOPENED_REPORTS_READY_SIGNOFF_HOLD" or
            summary.get("bitstream_generated") != "0" or
            summary.get("checkpoint_sha256") != checkpoint.sha256 or
            summary.get("part") != CURRENT_PART or
            summary.get("core_generated_ns") != "10.000" or
            summary.get("ddr_generated_ns") != "5.000" or
            summary.get("ddr_reference_ns") != "4.000" or
            summary.get("package_pin_count") != "234"):
        raise RuntimeContractError("current reopened audit summary identity mismatch")
    return cls(
        root, board.bitstream_sha256, checkpoint.sha256, input_file.sha256,
        len(reports), CURRENT_PROFILE,
    )


def _load_current_board_programming(
    cls, report_dir: str | Path, board: BoardBuildEvidence,
    audit: BoardAuditEvidence,
) -> BoardProgrammingEvidence:
    raise RuntimeContractError(
        "current board programming requires a future bitstream-bound receipt; "
        "legacy P16 programming evidence is ineligible"
    )


@dataclass(frozen=True)
class WorkloadSample:
    sample_id: str
    input_token_ids: tuple[int, ...]
    target_token_ids: tuple[int, ...]
    valid_tokens: int


@dataclass(frozen=True)
class WorkloadReference:
    software_id: str
    quantization: str
    metric: str
    expected_mean_nll: float
    absolute_tolerance: float
    seed: int
    evidence: FrozenFile
    profile: str = LEGACY_PROFILE

    def as_dict(self) -> dict:
        return {
            "software_id": self.software_id,
            "quantization": self.quantization,
            "metric": self.metric,
            "expected_mean_nll": self.expected_mean_nll,
            "absolute_tolerance": self.absolute_tolerance,
            "seed": self.seed,
            "evidence": self.evidence.as_dict(),
            "profile": self.profile,
        }


def _finite_number(value: object, label: str, *, nonnegative: bool) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise RuntimeContractError(f"{label} must be finite")
    result = float(value)
    if nonnegative and result < 0:
        raise RuntimeContractError(f"{label} must be nonnegative")
    return result


def _validate_legacy_reference_evidence(
    reference: WorkloadReference,
    checkpoint_sha256: str,
    dataset: FrozenFile,
    samples: Sequence[WorkloadSample],
) -> None:
    root = _require_fields(_load_json(reference.evidence.path), {
        "schema", "software_id", "model_id", "checkpoint_sha256",
        "artifact_manifest", "dataset", "seed", "sample_count",
        "valid_token_rows", "quantization", "runtime", "source_files",
        "metric", "nll_sum", "mean_nll", "records",
    }, "software reference evidence")
    exact_identity = {
        "schema": SOFTWARE_REFERENCE_SCHEMA,
        "software_id": SOFTWARE_REFERENCE_ID,
        "model_id": MODEL_ID,
        "checkpoint_sha256": checkpoint_sha256,
        "seed": reference.seed,
        "sample_count": len(samples),
        "valid_token_rows": len(samples) * COHORT_ROWS,
        "metric": "causal_nll",
    }
    for name, expected in exact_identity.items():
        if root[name] != expected:
            raise RuntimeContractError(
                f"software reference {name} mismatch: "
                f"expected={expected!r} actual={root[name]!r}"
            )
    if reference.software_id != SOFTWARE_REFERENCE_ID:
        raise RuntimeContractError("workload software reference ID drifted")
    if root["dataset"] != dataset.as_dict():
        raise RuntimeContractError("software reference dataset identity mismatch")

    artifact = FrozenFile.parse(
        root["artifact_manifest"], reference.evidence.path.parent,
        "software reference artifact manifest",
    )
    artifact.verify()
    artifact_raw = _load_json(artifact.path)
    if (not isinstance(artifact_raw, dict) or
            artifact_raw.get("model_id") != MODEL_ID or
            artifact_raw.get("layer_count") != LAYERS or
            artifact_raw.get("checkpoint_sha256") != checkpoint_sha256):
        raise RuntimeContractError(
            "software reference artifact manifest identity mismatch"
        )

    quantization = _require_fields(root["quantization"], {
        "attention", "mlp", "fixedpoint", "method",
    }, "software reference quantization")
    if quantization["attention"] != "Hadamard32 ScaleCode A8W8":
        raise RuntimeContractError("software reference Attention method drifted")
    if quantization["mlp"] != "Hadamard32 ScaleCode A8W4 SwiGLU":
        raise RuntimeContractError("software reference MLP method drifted")
    if quantization["fixedpoint"] != REFERENCE_FIXEDPOINT:
        raise RuntimeContractError("software reference fixed-point contract drifted")

    method = _require_fields(quantization["method"], {
        "case", "target_scope", "module_count", "per_arch",
        "linear_summary", "fixedpoint_config", "nonlinear_modules",
    }, "software reference method")
    if (method["case"] != "iah_scale_code_mlp_w4_fixedpoint_nonlinear" or
            method["module_count"] != LAYERS or
            method["per_arch"] != {"LlamaMLP": LAYERS} or
            method["fixedpoint_config"] != REFERENCE_FIXEDPOINT or
            method["nonlinear_modules"] != [
                f"model.layers.{index}.mlp" for index in range(LAYERS)
            ]):
        raise RuntimeContractError(
            "software reference 32-layer SwiGLU coverage drifted"
        )
    if not isinstance(method["target_scope"], str) or not method["target_scope"]:
        raise RuntimeContractError("software reference method scope is empty")

    linear = _require_fields(method["linear_summary"], {
        "case", "target_scope", "module_count", "per_op",
        "per_op_weight_bits", "hadamard_block", "group_size", "act_bits",
        "attention_weight_bits", "mlp_weight_bits", "scale_code_bits",
        "payload_format", "invariant",
    }, "software reference linear method")
    linear_exact = {
        "case": "iah_scale_code_mlp_w4_qdq_reference",
        "module_count": 224,
        "per_op": REFERENCE_LINEAR_COUNTS,
        "per_op_weight_bits": REFERENCE_WEIGHT_BITS,
        "hadamard_block": 32,
        "group_size": 32,
        "act_bits": 8,
        "attention_weight_bits": 8,
        "mlp_weight_bits": 4,
        "scale_code_bits": 8,
    }
    for name, expected in linear_exact.items():
        if linear[name] != expected:
            raise RuntimeContractError(
                f"software reference linear {name} drifted"
            )
    for name in ("target_scope", "payload_format", "invariant"):
        if not isinstance(linear[name], str) or not linear[name]:
            raise RuntimeContractError(
                f"software reference linear {name} is empty"
            )

    runtime = _require_fields(root["runtime"], {
        "torch", "cuda", "device", "gpu", "dtype", "batch_size",
        "cpu_threads", "deterministic_algorithms", "allow_tf32",
        "cublas_workspace_config", "model_attach_ns", "evaluation_ns",
    }, "software reference runtime")
    if (not isinstance(runtime["torch"], str) or not runtime["torch"] or
            not isinstance(runtime["cuda"], str) or not runtime["cuda"] or
            not isinstance(runtime["gpu"], str) or not runtime["gpu"] or
            not isinstance(runtime["device"], str) or
            not runtime["device"].startswith("cuda:") or
            runtime["dtype"] != "bfloat16" or runtime["batch_size"] != 2 or
            type(runtime["cpu_threads"]) is not int or
            not 1 <= runtime["cpu_threads"] <= 4 or
            runtime["deterministic_algorithms"] is not True or
            runtime["allow_tf32"] is not False or
            runtime["cublas_workspace_config"] not in {":4096:8", ":16:8"} or
            type(runtime["model_attach_ns"]) is not int or
            runtime["model_attach_ns"] <= 0 or
            type(runtime["evaluation_ns"]) is not int or
            runtime["evaluation_ns"] <= 0):
        raise RuntimeContractError("software reference runtime contract drifted")

    source_raw = root["source_files"]
    if not isinstance(source_raw, list) or len(source_raw) != 6:
        raise RuntimeContractError("software reference source closure must have 6 files")
    sources = tuple(
        FrozenFile.parse(item, reference.evidence.path.parent,
                         f"software reference source[{index}]")
        for index, item in enumerate(source_raw)
    )
    expected_source_names = {
        "generate_scalellm_workload_reference.py",
        "freeze_scalellm_workload.py",
        "fixedpoint_ops.py",
        "mlp4_fixedpoint_inference.py",
        "mlp4_method_inference.py",
        "scalepath4_method_inference.py",
    }
    if ({item.path.name for item in sources} != expected_source_names or
            len({item.path for item in sources}) != len(sources)):
        raise RuntimeContractError("software reference source closure drifted")
    for item in sources:
        item.verify()

    _validate_reference_records(root, reference, samples)


def _validate_reference_records(
    root: dict, reference: WorkloadReference,
    samples: Sequence[WorkloadSample],
) -> None:

    records = root["records"]
    if not isinstance(records, list) or len(records) != len(samples):
        raise RuntimeContractError("software reference record count mismatch")
    evidence_nll_sum = 0.0
    for index, (record_raw, sample) in enumerate(zip(records, samples)):
        record = _require_fields(record_raw, {
            "sample_id", "input_token_ids", "target_token_ids", "nll_sum",
            "mean_nll", "per_row_nll", "target_logits", "top_token_ids",
            "top_logits",
        }, f"software reference record[{index}]")
        if (record["sample_id"] != sample.sample_id or
                record["input_token_ids"] != list(sample.input_token_ids) or
                record["target_token_ids"] != list(sample.target_token_ids)):
            raise RuntimeContractError(
                f"software reference record[{index}] sample identity mismatch"
            )
        per_row = record["per_row_nll"]
        targets = record["target_logits"]
        top_ids = record["top_token_ids"]
        top_logits = record["top_logits"]
        if (not isinstance(per_row, list) or len(per_row) != COHORT_ROWS or
                not isinstance(targets, list) or len(targets) != COHORT_ROWS or
                not isinstance(top_ids, list) or len(top_ids) != COHORT_ROWS or
                not isinstance(top_logits, list) or
                len(top_logits) != COHORT_ROWS):
            raise RuntimeContractError(
                f"software reference record[{index}] row count mismatch"
            )
        per_row_values = [
            _finite_number(value, f"reference record[{index}] NLL", nonnegative=True)
            for value in per_row
        ]
        for value in targets:
            _finite_number(value, f"reference record[{index}] target logit",
                           nonnegative=False)
        for row in top_ids:
            if (not isinstance(row, list) or len(row) != 5 or any(
                type(token) is not int or not 0 <= token < VOCAB_SIZE
                for token in row
            )):
                raise RuntimeContractError(
                    f"software reference record[{index}] top IDs are invalid"
                )
        for row in top_logits:
            if not isinstance(row, list) or len(row) != 5:
                raise RuntimeContractError(
                    f"software reference record[{index}] top logits are invalid"
                )
            for value in row:
                _finite_number(
                    value, f"reference record[{index}] top logit",
                    nonnegative=False,
                )
        nll_sum = _finite_number(
            record["nll_sum"], f"reference record[{index}] nll_sum",
            nonnegative=True,
        )
        mean_nll = _finite_number(
            record["mean_nll"], f"reference record[{index}] mean_nll",
            nonnegative=True,
        )
        if (not math.isclose(nll_sum, sum(per_row_values), rel_tol=0,
                             abs_tol=1e-9) or
                not math.isclose(mean_nll, nll_sum / COHORT_ROWS, rel_tol=0,
                                 abs_tol=1e-9)):
            raise RuntimeContractError(
                f"software reference record[{index}] NLL aggregation mismatch"
            )
        evidence_nll_sum += nll_sum

    root_nll_sum = _finite_number(
        root["nll_sum"], "software reference nll_sum", nonnegative=True
    )
    root_mean_nll = _finite_number(
        root["mean_nll"], "software reference mean_nll", nonnegative=True
    )
    if (not math.isclose(root_nll_sum, evidence_nll_sum, rel_tol=0,
                         abs_tol=1e-9) or
            not math.isclose(
                root_mean_nll, root_nll_sum / (len(samples) * COHORT_ROWS),
                rel_tol=0, abs_tol=1e-9,
            ) or root_mean_nll != reference.expected_mean_nll):
        raise RuntimeContractError("software reference aggregate NLL mismatch")


def _validate_current_reference_evidence(
    reference: WorkloadReference, checkpoint_sha256: str,
    dataset: FrozenFile, samples: Sequence[WorkloadSample],
) -> None:
    if EXPORTER_GROUP != 32:
        raise RuntimeContractError("current exporter Hadamard group is not 32")
    root = _require_fields(_load_json(reference.evidence.path), {
        "schema", "profile", "software_id", "model_id", "checkpoint_sha256",
        "artifact_manifest", "dataset", "seed", "sample_count",
        "valid_token_rows", "quantization", "runtime", "source_files",
        "audit", "metric", "nll_sum", "mean_nll", "records",
    }, "current software reference evidence")
    expected_identity = {
        "schema": CURRENT_REFERENCE_SCHEMA,
        "profile": CURRENT_PROFILE,
        "software_id": CURRENT_REFERENCE_ID,
        "model_id": MODEL_ID,
        "checkpoint_sha256": checkpoint_sha256,
        "dataset": dataset.as_dict(),
        "seed": reference.seed,
        "sample_count": len(samples),
        "valid_token_rows": len(samples) * COHORT_ROWS,
        "metric": "causal_nll",
    }
    if any(root[key] != value for key, value in expected_identity.items()):
        raise RuntimeContractError("current software reference identity mismatch")
    if reference.software_id != CURRENT_REFERENCE_ID or reference.profile != CURRENT_PROFILE:
        raise RuntimeContractError("current workload reference profile/ID mismatch")
    artifact = FrozenFile.parse(
        root["artifact_manifest"], reference.evidence.path.parent,
        "current reference artifact manifest",
    )
    artifact.verify()
    artifact_raw = _load_json(artifact.path)
    artifact_identity = {
        "schema_version": SCHEMA_VERSION,
        "model_id": MODEL_ID,
        "layer_count": LAYERS,
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_id": checkpoint_sha256,
        "attention_format_id": ATTENTION_FORMAT_ID,
        "attention_abi": ATTENTION_ABI,
        "mlp_format_id": MLP_FORMAT_ID,
        "mlp_abi": MLP_ABI,
    }
    if not isinstance(artifact_raw, dict) or any(
        artifact_raw.get(key) != value for key, value in artifact_identity.items()
    ):
        raise RuntimeContractError("current reference artifact format/model mismatch")

    quantization = _require_fields(root["quantization"], {
        "attention", "mlp", "fixedpoint", "method",
    }, "current reference quantization")
    if (quantization["attention"] != "Hadamard32 ScaleCode A8W8" or
            quantization["mlp"] != "Hadamard32 ScaleCode A8W4 SwiGLU" or
            quantization["fixedpoint"] != CURRENT_NUMERIC_CONTRACT):
        raise RuntimeContractError("current reference numerical descriptor mismatch")
    method = quantization["method"]
    expected_method = {
        "case": "v5_production_fullchain",
        "manifest": "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list",
        "attention_format_id": "0x48384103",
        "mlp_full_format_id": "0x48384605",
        "layers": LAYERS, "max_context": 128, "cohort_rows": COHORT_ROWS,
        "attention_weight_bits": 8, "mlp_weight_bits": 4,
        "activation_bits": 8, "kv_bits": 12,
        "host_residual_rmsnorm": "FP32", "lm_head": "FP32 host",
        "strict_total_shift": True, "total_shift_policy": "strict_rtl",
        "software_reference_not_hardware": False,
        "node_trace_layers": [],
        "mlp_total_shift_range": [12, 44],
        "mlp_group_guard_compute_width": 45,
        "mlp_gate_up_accumulator_compute_width": 44,
        "mlp_down_accumulator_compute_width": 54,
        "mlp_down_output_width": 32,
    }
    if method != expected_method:
        raise RuntimeContractError("current reference is not the exact V5 fullchain method")

    runtime = _require_fields(root["runtime"], {
        "torch", "cuda", "device", "gpu", "dtype", "batch_size",
        "cpu_threads", "deterministic_algorithms", "allow_tf32",
        "cublas_workspace_config", "model_attach_ns", "evaluation_ns",
    }, "current reference runtime")
    if (not isinstance(runtime["torch"], str) or not runtime["torch"] or
            not isinstance(runtime["cuda"], str) or not runtime["cuda"] or
            not isinstance(runtime["gpu"], str) or not runtime["gpu"] or
            not isinstance(runtime["device"], str) or
            not runtime["device"].startswith("cuda:") or
            runtime["dtype"] != "bfloat16" or runtime["batch_size"] != 2 or
            type(runtime["cpu_threads"]) is not int or
            not 1 <= runtime["cpu_threads"] <= 4 or
            runtime["deterministic_algorithms"] is not True or
            runtime["allow_tf32"] is not False or
            runtime["cublas_workspace_config"] not in {":4096:8", ":16:8"} or
            type(runtime["model_attach_ns"]) is not int or
            runtime["model_attach_ns"] <= 0 or
            type(runtime["evaluation_ns"]) is not int or
            runtime["evaluation_ns"] <= 0):
        raise RuntimeContractError("current reference runtime contract drifted")

    source_raw = root["source_files"]
    hardware_root = Path(__file__).resolve().parents[1]
    scalellm_root = hardware_root.parent / "software"
    expected_paths = (
        hardware_root / "model" / "generate_scalellm_workload_reference.py",
        hardware_root / "model" / "freeze_scalellm_workload.py",
        scalellm_root / "0_Software" / "FPtoQ" / "experiment" / "v5_fullchain.py",
        hardware_root / "model" / "export_scalellm_llama31_artifacts.py",
        hardware_root / "model" / "fixbit_v2.py",
    )
    if not isinstance(source_raw, list) or len(source_raw) != len(expected_paths):
        raise RuntimeContractError("current reference source closure is incomplete")
    sources = tuple(FrozenFile.parse(
        item, reference.evidence.path.parent, f"current reference source[{index}]"
    ) for index, item in enumerate(source_raw))
    if tuple(item.path for item in sources) != tuple(
        path.resolve(strict=True) for path in expected_paths
    ):
        raise RuntimeContractError("current reference did not use approved V5 sources")
    if sources[2].sha256 != APPROVED_GOLDEN_SHA256:
        raise RuntimeContractError("current reference golden SHA256 is not approved")
    for item in sources:
        item.verify()
    names = ("llama3_inv_freq", "round_away", "fwht32_normalized",
             "encode_scales", "quantize_folded_rows")
    tree = ast.parse(sources[3].path.read_text(encoding="utf-8"))
    functions = {
        node.name: ast.dump(node, include_attributes=False)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }
    digest = hashlib.sha256(
        "\n".join(functions.get(name, "") for name in names).encode("utf-8")
    ).hexdigest()
    if (digest != APPROVED_EXPORTER_NUMERIC_AST_SHA256 or
            sources[4].sha256 != APPROVED_FIXBIT_SHA256):
        raise RuntimeContractError("current reference numerical helper identity drifted")

    audit = _require_fields(root["audit"], {"counters", "linear"},
                            "current reference audit")
    counter_names = {
        "activation_elements", "fp_to_fixed_saturation", "hadamard_saturation",
        "activation_scale_format_error", "linear_total_shift_format_error",
        "linear_group_guard_overflow_s37", "linear_software_group_guard_overflow",
        "linear_accumulator_overflow", "linear_software_accumulator_overflow",
        "linear_output_saturation", "rope_output_saturation", "kv12_clip",
        "qk_score_clip", "pv_output_saturation", "swiglu_output_overflow",
    }
    counters = _require_fields(audit["counters"], counter_names,
                               "current reference counters")
    if (any(type(value) is not int or value < 0 for value in counters.values()) or
            counters["activation_elements"] == 0):
        raise RuntimeContractError("current reference counters are invalid")
    fault_names = {
        "activation_scale_format_error", "linear_total_shift_format_error",
        "linear_group_guard_overflow_s37", "linear_software_group_guard_overflow",
        "linear_accumulator_overflow", "linear_software_accumulator_overflow",
        "swiglu_output_overflow",
    }
    if any(counters[name] for name in fault_names):
        raise RuntimeContractError("current reference has numerical fault counters")
    linear = audit["linear"]
    expected_linear = {
        f"model.layers.{layer}.{scope}.{op}.weight": op
        for layer in range(LAYERS)
        for scope, ops in (("self_attn", ("q_proj", "k_proj", "v_proj", "o_proj")),
                           ("mlp", ("gate_proj", "up_proj", "down_proj")))
        for op in ops
    }
    if not isinstance(linear, dict) or set(linear) != set(expected_linear):
        raise RuntimeContractError("current reference linear audit coverage is not 224")
    linear_fields = {
        "linear_group_guard_overflow_s37", "linear_software_group_guard_overflow",
        "linear_accumulator_overflow", "linear_software_accumulator_overflow",
        "linear_output_saturation", "linear_total_shift_min", "linear_total_shift_max",
    }
    for name, op in expected_linear.items():
        values = _require_fields(linear[name], linear_fields,
                                 f"current linear audit {name}")
        if any(type(value) is not int or value < 0 for value in values.values()):
            raise RuntimeContractError(f"current linear audit has noninteger {name}")
        minimum = 12 if op == "down_proj" else 20
        if (not minimum <= values["linear_total_shift_min"] <=
                values["linear_total_shift_max"] <= 44 or
                any(values[key] for key in linear_fields if
                    key not in {"linear_output_saturation", "linear_total_shift_min",
                                "linear_total_shift_max"})):
            raise RuntimeContractError(f"current linear audit fault or shift drift: {name}")
    _validate_reference_records(root, reference, samples)


def _validate_reference_evidence(
    reference: WorkloadReference, checkpoint_sha256: str,
    dataset: FrozenFile, samples: Sequence[WorkloadSample],
) -> None:
    if reference.profile == CURRENT_PROFILE:
        _validate_current_reference_evidence(reference, checkpoint_sha256,
                                             dataset, samples)
    elif reference.profile == LEGACY_PROFILE:
        _validate_legacy_reference_evidence(reference, checkpoint_sha256,
                                            dataset, samples)
    else:
        raise RuntimeContractError("unknown software reference profile")


@dataclass(frozen=True)
class FrozenWorkload:
    manifest_path: Path
    model_id: str
    checkpoint_sha256: str
    dataset: FrozenFile
    tokenizer_files: tuple[FrozenFile, ...]
    samples: tuple[WorkloadSample, ...]
    reference: WorkloadReference
    profile: str = LEGACY_PROFILE

    @classmethod
    def load(
        cls, manifest_path: str | Path, *, profile: str = CURRENT_PROFILE,
    ) -> "FrozenWorkload":
        if profile not in (CURRENT_PROFILE, LEGACY_PROFILE):
            raise RuntimeContractError("unsupported workload evidence profile")
        path = Path(manifest_path).resolve(strict=True)
        raw = _require_fields(_load_json(path), {
            "schema_version", "model_id", "checkpoint_sha256",
            "dataset", "tokenizer_files", "sample_count", "profile",
            "reference", "samples",
        }, "workload manifest")
        if (type(raw["schema_version"]) is not int or
                raw["schema_version"] != WORKLOAD_SCHEMA_VERSION):
            raise RuntimeContractError("unsupported workload schema")
        if raw["model_id"] != MODEL_ID:
            raise RuntimeContractError("workload model_id is not Llama-3.1-8B-Instruct")
        checkpoint_sha = _require_sha(
            raw["checkpoint_sha256"], "workload checkpoint_sha256"
        )
        base = path.parent
        dataset = FrozenFile.parse(raw["dataset"], base, "dataset")
        tokenizer_raw = raw["tokenizer_files"]
        if not isinstance(tokenizer_raw, list) or not tokenizer_raw:
            raise RuntimeContractError("tokenizer_files must be a nonempty list")
        tokenizer = tuple(
            FrozenFile.parse(item, base, f"tokenizer_files[{index}]")
            for index, item in enumerate(tokenizer_raw)
        )
        if len({item.path for item in tokenizer}) != len(tokenizer):
            raise RuntimeContractError("tokenizer file paths must be unique")

        workload_shape = _require_fields(raw["profile"], {
            "max_tokens", "cohort_rows", "attention_query_count",
            "padding", "truncation", "valid_tokens_per_sample",
        }, "workload profile")
        exact_workload_shape = {
            "max_tokens": 128,
            "cohort_rows": COHORT_ROWS,
            "attention_query_count": COHORT_ROWS,
            "padding": "none",
            "truncation": "contiguous-17-token-window-to-16-causal-pairs",
            "valid_tokens_per_sample": COHORT_ROWS,
        }
        if workload_shape != exact_workload_shape:
            raise RuntimeContractError(
                "unsupported workload profile: "
                f"expected={exact_workload_shape} actual={workload_shape}"
            )

        reference_fields = {
            "software_id", "quantization", "metric", "expected_mean_nll",
            "absolute_tolerance", "seed", "evidence",
        }
        if profile == CURRENT_PROFILE:
            reference_fields.add("profile")
        elif isinstance(raw["reference"], dict) and "profile" in raw["reference"]:
            reference_fields.add("profile")
        reference_raw = _require_fields(raw["reference"], reference_fields,
                                        "workload reference")
        if (profile == CURRENT_PROFILE and
                (reference_raw["profile"] != CURRENT_PROFILE or
                 reference_raw["software_id"] != CURRENT_REFERENCE_ID)):
            raise RuntimeContractError("current workload reference profile/ID mismatch")
        if (profile == LEGACY_PROFILE and
                (reference_raw.get("profile", LEGACY_PROFILE) != LEGACY_PROFILE or
                 reference_raw["software_id"] != SOFTWARE_REFERENCE_ID)):
            raise RuntimeContractError("historical workload reference profile/ID mismatch")
        if (not isinstance(reference_raw["software_id"], str) or
                not reference_raw["software_id"]):
            raise RuntimeContractError("reference software_id is empty")
        if reference_raw["quantization"] != QUANTIZATION_ID:
            raise RuntimeContractError("reference quantization contract mismatch")
        if reference_raw["metric"] != "causal_nll":
            raise RuntimeContractError("only causal_nll acceptance is supported")
        for name in ("expected_mean_nll", "absolute_tolerance"):
            value = reference_raw[name]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise RuntimeContractError(f"reference {name} must be finite/nonnegative")
        if type(reference_raw["seed"]) is not int:
            raise RuntimeContractError("reference seed must be an integer")
        evidence = FrozenFile.parse(
            reference_raw["evidence"], base, "reference evidence"
        )
        frozen_inputs = {dataset.path, *(item.path for item in tokenizer)}
        if evidence.path in frozen_inputs:
            raise RuntimeContractError(
                "reference evidence must be distinct from dataset/tokenizer files"
            )
        reference = WorkloadReference(
            software_id=reference_raw["software_id"],
            quantization=reference_raw["quantization"],
            metric=reference_raw["metric"],
            expected_mean_nll=float(reference_raw["expected_mean_nll"]),
            absolute_tolerance=float(reference_raw["absolute_tolerance"]),
            seed=reference_raw["seed"],
            evidence=evidence,
            profile=profile,
        )

        samples_raw = raw["samples"]
        if not isinstance(samples_raw, list) or len(samples_raw) < 2 or (
            len(samples_raw) % 2
        ):
            raise RuntimeContractError("workload needs an even number of samples >= 2")
        if type(raw["sample_count"]) is not int or (
            raw["sample_count"] != len(samples_raw)
        ):
            raise RuntimeContractError("workload sample_count mismatch")
        samples = []
        sample_ids = set()
        for index, item_raw in enumerate(samples_raw):
            item = _require_fields(item_raw, {
                "sample_id", "input_token_ids", "target_token_ids",
                "valid_tokens",
            }, f"sample[{index}]")
            sample_id = item["sample_id"]
            if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
                raise RuntimeContractError(f"sample[{index}] has invalid/duplicate ID")
            sample_ids.add(sample_id)
            token_lists = []
            for key in ("input_token_ids", "target_token_ids"):
                values = item[key]
                if not isinstance(values, list) or len(values) != COHORT_ROWS or any(
                    type(value) is not int or not 0 <= value < VOCAB_SIZE
                    for value in values
                ):
                    raise RuntimeContractError(
                        f"sample[{index}] {key} must contain 16 vocabulary IDs"
                    )
                token_lists.append(tuple(values))
            if item["valid_tokens"] != COHORT_ROWS:
                raise RuntimeContractError(
                    "this board profile forbids padded rows; valid_tokens must be 16"
                )
            samples.append(WorkloadSample(
                sample_id, token_lists[0], token_lists[1], COHORT_ROWS
            ))

        dataset.verify()
        for item in tokenizer:
            item.verify()
        reference.evidence.verify()
        _validate_reference_evidence(
            reference, checkpoint_sha, dataset, tuple(samples)
        )
        return cls(path, raw["model_id"], checkpoint_sha, dataset, tokenizer,
                   tuple(samples), reference, profile)

    @property
    def valid_tokens(self) -> int:
        return sum(sample.valid_tokens for sample in self.samples)

    def identity(self) -> dict:
        return {
            "manifest": str(self.manifest_path),
            "manifest_sha256": sha256_file(self.manifest_path),
            "model_id": self.model_id,
            "checkpoint_sha256": self.checkpoint_sha256,
            "dataset": self.dataset.as_dict(),
            "tokenizer_files": [item.as_dict() for item in self.tokenizer_files],
            "sample_count": len(self.samples),
            "valid_tokens": self.valid_tokens,
            "reference": self.reference.as_dict(),
            "profile": self.profile,
        }


class HostModel(Protocol):
    norm_weights: LlamaNormWeights

    def embed(self, token_ids: Sequence[int]) -> np.ndarray:
        """Return one 16x4096 input embedding tensor."""

    def evaluate(
        self, hidden: np.ndarray, target_token_ids: Sequence[int], top_k: int = 5,
    ) -> dict:
        """Run chunked Host LM head and return auditable metrics."""


def streaming_lm_head(
    hidden: np.ndarray,
    target_token_ids: Sequence[int],
    vocabulary_size: int,
    weight_loader: Callable[[int, int], np.ndarray],
    chunk_rows: int,
    top_k: int = 5,
) -> dict:
    """Compute exact float32 logits statistics without materializing full logits."""
    values = np.asarray(hidden, dtype=np.float32)
    targets = np.asarray(target_token_ids, dtype=np.int64)
    if values.ndim != 2 or values.shape[1] <= 0:
        raise ValueError("LM-head hidden input must be a nonempty matrix")
    if (type(vocabulary_size) is not int or vocabulary_size <= 0 or
            type(chunk_rows) is not int or chunk_rows <= 0):
        raise ValueError("LM-head vocabulary/chunk sizes must be positive integers")
    if targets.shape != (values.shape[0],) or np.any(targets < 0) or np.any(
        targets >= vocabulary_size
    ):
        raise ValueError("LM-head targets must match rows and vocabulary")
    if not 1 <= top_k <= min(chunk_rows, vocabulary_size):
        raise ValueError("invalid LM-head top_k")

    row_count = values.shape[0]
    running_max = np.full(row_count, -np.inf, dtype=np.float64)
    running_sum = np.zeros(row_count, dtype=np.float64)
    target_logits = np.full(row_count, np.nan, dtype=np.float32)
    top_values = np.full((row_count, top_k), -np.inf, dtype=np.float32)
    top_ids = np.full((row_count, top_k), -1, dtype=np.int64)
    rows = np.arange(row_count)

    for start in range(0, vocabulary_size, chunk_rows):
        stop = min(start + chunk_rows, vocabulary_size)
        weights = np.asarray(weight_loader(start, stop), dtype=np.float32)
        expected_shape = (stop - start, values.shape[1])
        if weights.shape != expected_shape or not np.all(np.isfinite(weights)):
            raise RuntimeContractError(
                f"LM-head weight chunk shape/value drifted: "
                f"expected={expected_shape} actual={weights.shape}"
            )
        logits = np.asarray(values @ weights.T, dtype=np.float32)
        block_max = np.max(logits, axis=1).astype(np.float64)
        next_max = np.maximum(running_max, block_max)
        running_sum = (
            running_sum * np.exp(running_max - next_max)
            + np.sum(
                np.exp(logits.astype(np.float64) - next_max[:, None]), axis=1
            )
        )
        running_max = next_max

        target_mask = (targets >= start) & (targets < stop)
        if np.any(target_mask):
            target_rows = rows[target_mask]
            target_logits[target_mask] = logits[
                target_rows, targets[target_mask] - start
            ]

        block_ids = np.arange(start, stop, dtype=np.int64)
        candidate_values = np.concatenate((top_values, logits), axis=1)
        candidate_ids = np.concatenate((
            top_ids,
            np.broadcast_to(block_ids, (row_count, stop - start)),
        ), axis=1)
        order = np.lexsort((candidate_ids, -candidate_values), axis=1)[:, :top_k]
        top_values = np.take_along_axis(candidate_values, order, axis=1)
        top_ids = np.take_along_axis(candidate_ids, order, axis=1)

    if np.any(~np.isfinite(target_logits)):
        raise RuntimeContractError("LM-head target logits were not populated")
    logsumexp = running_max + np.log(running_sum)
    nll = logsumexp - target_logits.astype(np.float64)
    return {
        "rows": row_count,
        "nll_sum": float(np.sum(nll, dtype=np.float64)),
        "mean_nll": float(np.mean(nll, dtype=np.float64)),
        "per_row_nll": nll.tolist(),
        "target_logits": target_logits.astype(np.float64).tolist(),
        "top_token_ids": top_ids.tolist(),
        "top_logits": top_values.astype(np.float64).tolist(),
    }


class Llama31HostModel:
    """Memory-mapped checkpoint access for embedding, norms and chunked LM head."""

    def __init__(
        self, model_dir: str | Path, expected_checkpoint_sha256: str,
        lm_head_chunk_rows: int = 2048,
    ) -> None:
        if lm_head_chunk_rows <= 0:
            raise ValueError("LM-head chunk rows must be positive")
        self.checkpoint = LlamaCheckpoint(Path(model_dir))
        actual_sha, self.checkpoint_identity = self.checkpoint.source_identity()
        if actual_sha != expected_checkpoint_sha256:
            raise RuntimeContractError(
                "checkpoint identity disagrees with ScaleCode/workload manifest: "
                f"expected={expected_checkpoint_sha256} actual={actual_sha}"
            )
        self.lm_head_chunk_rows = lm_head_chunk_rows
        input_norm = np.stack([
            self.checkpoint.float32(
                f"model.layers.{layer}.input_layernorm.weight"
            ) for layer in range(LAYERS)
        ])
        post_norm = np.stack([
            self.checkpoint.float32(
                f"model.layers.{layer}.post_attention_layernorm.weight"
            ) for layer in range(LAYERS)
        ])
        final_norm = self.checkpoint.float32("model.norm.weight")
        self.norm_weights = LlamaNormWeights(
            input_norm, post_norm, final_norm,
            epsilon=float(self.checkpoint.config["rms_norm_eps"]),
        )

    def embed(self, token_ids: Sequence[int]) -> np.ndarray:
        ids = np.asarray(token_ids, dtype=np.int64)
        if ids.shape != (COHORT_ROWS,) or np.any(ids < 0) or np.any(ids >= VOCAB_SIZE):
            raise ValueError("embedding input must contain 16 vocabulary IDs")
        result = self.checkpoint.float32("model.embed_tokens.weight", rows=ids)
        if result.shape != ACTIVATION_SHAPE:
            raise RuntimeContractError(f"embedding shape drifted: {result.shape}")
        return np.ascontiguousarray(result, dtype=np.float32)

    def evaluate(
        self, hidden: np.ndarray, target_token_ids: Sequence[int], top_k: int = 5,
    ) -> dict:
        values = np.asarray(hidden, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != HIDDEN:
            raise ValueError("LM-head hidden input must have shape (rows, 4096)")
        result = streaming_lm_head(
            values, target_token_ids, VOCAB_SIZE,
            lambda start, stop: self.checkpoint.float32(
                "lm_head.weight", rows=slice(start, stop)
            ),
            self.lm_head_chunk_rows, top_k,
        )
        normalized = np.ascontiguousarray(values, dtype="<f4")
        result["final_normalized_sha256"] = hashlib.sha256(
            normalized.tobytes(order="C")
        ).hexdigest()
        return result


class TelemetryBackend(Protocol):
    @property
    def telemetry(self) -> tuple[HardwareCommandTelemetry, ...]:
        """Return all completion telemetry captured before ACK."""


def _overlap_ns(report: PipelineReport) -> int:
    starts: dict[int, tuple[str, int]] = {}
    intervals: dict[str, list[tuple[int, int]]] = {
        "attention_running": [], "mlp_running": [],
    }
    for event in report.events:
        if event.command_id is None or event.stage not in intervals:
            continue
        if event.kind == "start":
            starts[event.command_id] = (event.stage, event.monotonic_ns)
        elif event.kind == "complete":
            try:
                stage, start = starts.pop(event.command_id)
            except KeyError as exc:
                raise RuntimeContractError("completion trace has no matching start") \
                    from exc
            intervals[stage].append((start, event.monotonic_ns))
    if starts:
        raise RuntimeContractError("pipeline trace contains unfinished commands")
    return sum(
        max(0, min(a1, m1) - max(a0, m0))
        for a0, a1 in intervals["attention_running"]
        for m0, m1 in intervals["mlp_running"]
    )


def _telemetry_dict(item: HardwareCommandTelemetry) -> dict:
    result = asdict(item)
    result["identity"] = asdict(item.identity)
    return result


class ScaleLLMBoardExecutor:
    """Runs a frozen workload three times without reopening XDMA or weights."""

    def __init__(
        self, backend: TelemetryBackend, transfers: PinnedActivationPool,
        host_model: HostModel, workload: FrozenWorkload,
    ) -> None:
        self.backend = backend
        self.transfers = transfers
        self.host_model = host_model
        self.workload = workload
        self._next_request_id = 1
        self._next_command_id = 1

    def run(self, repetitions: int = 3) -> dict:
        if repetitions < 3:
            raise ValueError("board acceptance requires at least three repetitions")
        repetition_reports = []
        signatures = []
        for repetition in range(repetitions):
            report = self._run_repetition(repetition)
            repetition_reports.append(report)
            signatures.append(report["result_signature"])
        if len(set(signatures)) != 1:
            raise RuntimeContractError(
                f"three-run result signatures disagree: {signatures}"
            )
        return {
            "schema": "scalellm_v5_board_execution_v1",
            "repetitions": repetitions,
            "sample_count": len(self.workload.samples),
            "valid_tokens_per_repetition": self.workload.valid_tokens,
            "stable_result_signature": signatures[0],
            "runs": repetition_reports,
        }

    def _run_repetition(self, repetition: int) -> dict:
        telemetry_start = len(self.backend.telemetry)
        transfer_start = len(self.transfers.transfers)
        wall_start = time.monotonic_ns()
        batch_reports = []
        pipeline_ns = 0
        overlap_ns = 0
        nll_sum = 0.0
        nll_rows = 0

        for batch_index in range(0, len(self.workload.samples), 2):
            pair = self.workload.samples[batch_index:batch_index + 2]
            host = ScaleLLMHostBoundaryOps(self.transfers,
                                           self.host_model.norm_weights)
            host.prepare_cohort(0, 0, self.host_model.embed(pair[0].input_token_ids))
            host.prepare_cohort(1, 3, self.host_model.embed(pair[1].input_token_ids))
            request_ids = (self._next_request_id, self._next_request_id + 1)
            self._next_request_id += 2
            runtime = DualCohortRuntime(
                self.backend, host, layers=LAYERS, cohort_ids=(0, 1),
                request_ids=request_ids,
                command_id_start=self._next_command_id,
            )
            pipeline = runtime.run()
            if (pipeline.layers != LAYERS or pipeline.completed_rows != 32 or
                    pipeline.commands_submitted != COMMANDS_PER_PAIR or
                    pipeline.commands_completed != COMMANDS_PER_PAIR):
                raise RuntimeContractError("32-layer runtime completion count drifted")
            self._next_command_id += COMMANDS_PER_PAIR
            pair_overlap = _overlap_ns(pipeline)
            if pair_overlap <= 0:
                raise RuntimeContractError(
                    "Attention and MLP did not overlap across cohorts"
                )
            normalized = np.concatenate((
                host.final_normalized(0), host.final_normalized(1)
            ), axis=0)
            targets = pair[0].target_token_ids + pair[1].target_token_ids
            metrics = self.host_model.evaluate(normalized, targets)
            if metrics["rows"] != 32:
                raise RuntimeContractError("Host LM-head row count drifted")
            nll_sum += float(metrics["nll_sum"])
            nll_rows += int(metrics["rows"])
            pipeline_ns += pipeline.end_to_end_ns
            overlap_ns += pair_overlap
            batch_reports.append({
                "batch_index": batch_index // 2,
                "sample_ids": [sample.sample_id for sample in pair],
                "request_ids": list(request_ids),
                "pipeline": pipeline.as_dict(),
                "attention_mlp_overlap_ns": pair_overlap,
                "host_metrics": metrics,
            })

        wall_end = time.monotonic_ns()
        telemetry = self.backend.telemetry[telemetry_start:]
        transfers = self.transfers.transfers[transfer_start:]
        expected_commands = (len(self.workload.samples) // 2) * COMMANDS_PER_PAIR
        if len(telemetry) != expected_commands:
            raise RuntimeContractError(
                f"hardware telemetry count mismatch: expected={expected_commands} "
                f"actual={len(telemetry)}"
            )
        for item in telemetry:
            if item.completion_status != "SUCCESS" or item.counters.get(
                "error_code", 0
            ) != 0:
                raise RuntimeContractError(
                    f"hardware telemetry reports failure: {_telemetry_dict(item)}"
                )
        if not transfers or any(not item.pinned for item in transfers):
            raise RuntimeContractError("acceptance used an unlocked activation buffer")

        mean_nll = nll_sum / nll_rows
        reference = self.workload.reference
        reference_error = abs(mean_nll - reference.expected_mean_nll)
        metric_pass = reference_error <= reference.absolute_tolerance
        if not metric_pass:
            raise RuntimeContractError(
                f"causal NLL failed: actual={mean_nll} "
                f"expected={reference.expected_mean_nll} "
                f"tolerance={reference.absolute_tolerance}"
            )
        signature_payload = [{
            "sample_ids": item["sample_ids"],
            "host_metrics": item["host_metrics"],
        } for item in batch_reports]
        signature = hashlib.sha256(json.dumps(
            signature_payload, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")).hexdigest()
        valid_tokens = self.workload.valid_tokens
        return {
            "repetition": repetition,
            "wall_start_monotonic_ns": wall_start,
            "wall_end_monotonic_ns": wall_end,
            "valid_tokens": valid_tokens,
            "commands": expected_commands,
            "pipeline_ns": pipeline_ns,
            "full_wall_ns": wall_end - wall_start,
            "attention_mlp_overlap_ns": overlap_ns,
            "pipeline_processed_tokens_per_second": (
                valid_tokens * 1e9 / pipeline_ns
            ),
            "full_application_tokens_per_second": (
                valid_tokens * 1e9 / (wall_end - wall_start)
            ),
            "mean_nll": mean_nll,
            "reference_mean_nll": reference.expected_mean_nll,
            "reference_absolute_error": reference_error,
            "reference_tolerance": reference.absolute_tolerance,
            "metric_pass": metric_pass,
            "result_signature": signature,
            "transfer_count": len(transfers),
            "transfers": [asdict(item) for item in transfers],
            "hardware_telemetry": [_telemetry_dict(item) for item in telemetry],
            "batches": batch_reports,
        }


def _write_json_atomic(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def run_board(args: argparse.Namespace) -> dict:
    board = BoardBuildEvidence.load(args.board_report_dir, profile=CURRENT_PROFILE)
    board_audit = BoardAuditEvidence.load(args.board_audit_dir, board)
    board_programming = BoardProgrammingEvidence.load(
        args.program_report_dir, board, board_audit
    )
    artifacts = ScaleCodeArtifactManifest.load(args.artifact_manifest)
    workload = FrozenWorkload.load(args.workload_manifest, profile=CURRENT_PROFILE)
    if any(item.profile != CURRENT_PROFILE for item in
           (board, board_audit, board_programming, workload)):
        raise RuntimeContractError("board run refuses mixed or legacy profiles")
    if artifacts.model_id != MODEL_ID or workload.model_id != MODEL_ID:
        raise RuntimeContractError("model identity is not frozen Llama-3.1-8B-Instruct")
    if artifacts.checkpoint_sha256 != workload.checkpoint_sha256:
        raise RuntimeContractError("artifact/workload checkpoint SHA mismatch")
    host_model = Llama31HostModel(
        args.model_dir, artifacts.checkpoint_sha256,
        lm_head_chunk_rows=args.lm_head_chunk_rows,
    )
    if tuple(item.path for item in workload.tokenizer_files) != tuple(
        path.resolve(strict=True) for path in host_model.checkpoint.tokenizer_paths
    ):
        raise RuntimeContractError("workload tokenizer files are not from the checkpoint")
    power_sampler = FilePowerSampler(
        args.power_input, args.power_source_label,
        scale_to_watts=args.power_scale_to_watts,
        sample_interval_s=args.power_sample_interval_s,
    )

    output = Path(args.output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeContractError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    identity = {
        "schema": "scalellm_v5_board_run_identity_v1",
        "profile": CURRENT_PROFILE,
        "board": board.as_dict(),
        "board_audit": board_audit.as_dict(),
        "board_programming": board_programming.as_dict(),
        "artifacts": {
            "manifest": str(artifacts.manifest_path),
            "manifest_sha256": sha256_file(artifacts.manifest_path),
            "model_id": artifacts.model_id,
            "checkpoint_sha256": artifacts.checkpoint_sha256,
        },
        "workload": workload.identity(),
        "checkpoint_identity": host_model.checkpoint_identity,
    }
    _write_json_atomic(output / "run_identity.json", identity)

    session = XdmaSession(
        h2c=args.h2c, c2h=args.c2h, user=args.user,
        event=None if args.event == "none" else args.event,
    )
    with session:
        stager = XdmaLayerStager(
            session, artifacts, chunk_bytes=args.metadata_chunk_bytes
        )
        backend = ScaleLLMHardwareBackend(
            session, stager, timeout_s=args.command_timeout_s,
            poll_interval_s=args.poll_interval_s,
        )
        backend.initialize_shared_mode()
        preload_start = time.monotonic_ns()
        preloaded_bytes = preload_all_matrices(
            session, artifacts, chunk_bytes=args.matrix_chunk_bytes
        )
        preload_end = time.monotonic_ns()
        if preloaded_bytes != EXPECTED_MATRIX_BYTES:
            raise RuntimeContractError(
                f"resident matrix byte count drifted: {preloaded_bytes}"
            )
        sample_audit = verify_resident_matrix_samples(
            session, artifacts, sample_bytes=args.readback_sample_bytes,
            chunk_bytes=args.activation_chunk_bytes,
        )
        with power_sampler:
            with PinnedActivationPool(
                session, chunk_bytes=args.activation_chunk_bytes,
                require_lock=True,
            ) as transfers:
                execution = ScaleLLMBoardExecutor(
                    backend, transfers, host_model, workload
                ).run(repetitions=args.repetitions)
        processed_tokens = sum(
            run["valid_tokens"] for run in execution["runs"]
        )
        power = power_sampler.report(processed_tokens)
        power["runs"] = []
        for run in execution["runs"]:
            run_power = power_sampler.report_window(
                run["wall_start_monotonic_ns"],
                run["wall_end_monotonic_ns"],
                run["valid_tokens"],
            )
            run_power["repetition"] = run["repetition"]
            power["runs"].append(run_power)

    result = {
        "schema": "scalellm_v5_full_board_acceptance_v1",
        "gate_pass": True,
        "run_identity_sha256": sha256_file(output / "run_identity.json"),
        "preload": {
            "bytes": preloaded_bytes,
            "elapsed_ns": preload_end - preload_start,
            "gigabytes_per_second": (
                preloaded_bytes / (preload_end - preload_start)
            ),
            "sample_readback": sample_audit,
        },
        "power": power,
        "execution": execution,
    }
    _write_json_atomic(output / "acceptance.json", result)
    (output / "OUTPUT_SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  {path}\n"
            for path in sorted(output.iterdir())
            if path.is_file() and path.name != "OUTPUT_SHA256SUMS"
        ), encoding="ascii",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run strict ScaleLLM V5 VCU118 board acceptance"
    )
    parser.add_argument("--board-report-dir", type=Path, required=True)
    parser.add_argument("--board-audit-dir", type=Path, required=True)
    parser.add_argument("--program-report-dir", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--workload-manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--power-input", type=Path, required=True)
    parser.add_argument("--power-source-label", required=True)
    parser.add_argument("--power-scale-to-watts", type=float, default=1e-6)
    parser.add_argument("--power-sample-interval-s", type=float, default=0.1)
    parser.add_argument("--h2c", default="/dev/xdma0_h2c_0")
    parser.add_argument("--c2h", default="/dev/xdma0_c2h_0")
    parser.add_argument("--user", default="/dev/xdma0_user")
    parser.add_argument("--event", default="/dev/xdma0_events_0")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--matrix-chunk-bytes", type=int, default=4 << 20)
    parser.add_argument("--metadata-chunk-bytes", type=int, default=4 << 20)
    parser.add_argument("--activation-chunk-bytes", type=int, default=1 << 20)
    parser.add_argument("--readback-sample-bytes", type=int, default=4096)
    parser.add_argument("--lm-head-chunk-rows", type=int, default=2048)
    parser.add_argument("--command-timeout-s", type=float, default=2.0)
    parser.add_argument("--poll-interval-s", type=float, default=0.0005)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = run_board(args)
    print(json.dumps({
        "gate_pass": result["gate_pass"],
        "preload_bytes": result["preload"]["bytes"],
        "stable_result_signature": result["execution"][
            "stable_result_signature"
        ],
        "pipeline_processed_tokens_per_second": [
            run["pipeline_processed_tokens_per_second"]
            for run in result["execution"]["runs"]
        ],
        "mean_power_watts": result["power"]["mean_watts"],
        "processed_tokens_per_joule": result["power"][
            "processed_tokens_per_joule"
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
