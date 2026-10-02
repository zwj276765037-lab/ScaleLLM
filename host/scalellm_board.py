#!/usr/bin/env python3
"""Strict VCU118 runner for the 32-layer ScaleLLM acceptance workload."""

from __future__ import annotations

import argparse
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
    HIDDEN,
    LAYERS,
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


MODEL_ID = "meta-llama/Llama-3.1-8B"
WORKLOAD_SCHEMA_VERSION = 1
COHORT_ROWS = 16
QUANTIZATION_ID = (
    "hadamard32-scalecode-group32-attention-a8w8-mlp-a8w4-swiglu"
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
EXPECTED_MATRIX_BYTES = 3_968 << 20
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

    @classmethod
    def load(cls, report_dir: str | Path) -> "BoardBuildEvidence":
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

    @classmethod
    def load(
        cls, report_dir: str | Path, board: BoardBuildEvidence
    ) -> "BoardAuditEvidence":
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

    @classmethod
    def load(
        cls, report_dir: str | Path, board: BoardBuildEvidence,
        audit: BoardAuditEvidence,
    ) -> "BoardProgrammingEvidence":
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

    def as_dict(self) -> dict:
        return {
            "software_id": self.software_id,
            "quantization": self.quantization,
            "metric": self.metric,
            "expected_mean_nll": self.expected_mean_nll,
            "absolute_tolerance": self.absolute_tolerance,
            "seed": self.seed,
            "evidence": self.evidence.as_dict(),
        }


def _finite_number(value: object, label: str, *, nonnegative: bool) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise RuntimeContractError(f"{label} must be finite")
    result = float(value)
    if nonnegative and result < 0:
        raise RuntimeContractError(f"{label} must be nonnegative")
    return result


def _validate_reference_evidence(
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


@dataclass(frozen=True)
class FrozenWorkload:
    manifest_path: Path
    model_id: str
    checkpoint_sha256: str
    dataset: FrozenFile
    tokenizer_files: tuple[FrozenFile, ...]
    samples: tuple[WorkloadSample, ...]
    reference: WorkloadReference

    @classmethod
    def load(cls, manifest_path: str | Path) -> "FrozenWorkload":
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
            raise RuntimeContractError("workload model_id is not Llama-3.1-8B")
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

        profile = _require_fields(raw["profile"], {
            "max_tokens", "cohort_rows", "attention_query_count",
            "padding", "truncation", "valid_tokens_per_sample",
        }, "workload profile")
        exact_profile = {
            "max_tokens": 128,
            "cohort_rows": COHORT_ROWS,
            "attention_query_count": COHORT_ROWS,
            "padding": "none",
            "truncation": "contiguous-17-token-window-to-16-causal-pairs",
            "valid_tokens_per_sample": COHORT_ROWS,
        }
        if profile != exact_profile:
            raise RuntimeContractError(
                f"unsupported workload profile: expected={exact_profile} actual={profile}"
            )

        reference_raw = _require_fields(raw["reference"], {
            "software_id", "quantization", "metric", "expected_mean_nll",
            "absolute_tolerance", "seed", "evidence",
        }, "workload reference")
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
                   tuple(samples), reference)

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
    board = BoardBuildEvidence.load(args.board_report_dir)
    board_audit = BoardAuditEvidence.load(args.board_audit_dir, board)
    board_programming = BoardProgrammingEvidence.load(
        args.program_report_dir, board, board_audit
    )
    artifacts = ScaleCodeArtifactManifest.load(args.artifact_manifest)
    workload = FrozenWorkload.load(args.workload_manifest)
    if artifacts.model_id != MODEL_ID or workload.model_id != MODEL_ID:
        raise RuntimeContractError("model identity is not frozen Llama-3.1-8B")
    if artifacts.checkpoint_sha256 != workload.checkpoint_sha256:
        raise RuntimeContractError("artifact/workload checkpoint SHA mismatch")
    host_model = Llama31HostModel(
        args.model_dir, artifacts.checkpoint_sha256,
        lm_head_chunk_rows=args.lm_head_chunk_rows,
    )
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
