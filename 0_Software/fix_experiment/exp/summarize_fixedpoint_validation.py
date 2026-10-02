#!/usr/bin/env python3
"""Build the auditable Llama-3.1-8B format-v3 validation summary.

The report deliberately separates three different claims:

* task quality (ACC/PPL relative to the matched BF16 run),
* numerical-contract validity (format errors, overflow and saturation), and
* diagnostic ablations which are not implemented by the current RTL.

Only explicitly selected full-run manifests are allowed into the paper-facing
metric tables.  Smoke runs and diagnostic manifests remain available as
provenance but cannot silently replace a missing full result.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from protocol import PRIMARY_METRIC, TASK_ORDER


CASE_ORDER = ("bf16", "v5_attention", "v5_mlp", "v5")
CASE_LABEL = {
    "bf16": "Matched BF16",
    "v5_attention": "Attention-only",
    "v5_mlp": "MLP-only",
    "v5": "Full V5",
    "v5_mlp_down_s32_ablation": "Down-S32 diagnostic",
}
ACC_DROP_LIMIT_PP = {
    "v5_attention": 1.0,
    "v5_mlp": 1.0,
    "v5": 1.5,
}
PPL_RISE_LIMIT_PERCENT = {
    "v5_attention": 10.0,
    "v5_mlp": 10.0,
    "v5": 15.0,
}
ATTENTION_TRACE_NODES = {
    "rope_q_local",
    "rope_k_local",
    "kv12_key",
    "kv12_value",
    "qk_score_cumulative",
    "softmax_local",
    "pv_local",
}
MLP_TRACE_NODES = {
    "mlp_gate_projection",
    "mlp_up_projection",
    "mlp_silu_lut_local",
    "mlp_swiglu_round_local",
    "mlp_swiglu_cumulative",
    "mlp_down_projection_local",
    "mlp_down_projection_cumulative",
}

OPEN_WIDTH_STATUSES = {
    "CONFIRMED_FAILURE",
    "CONFIRMED_CONTRACT_GAP",
    "OPEN_QUALITY_RISK",
    "OBSERVABILITY_GAP",
    "DEPLOYMENT_BLOCKER",
    "VALIDATION_GAP",
    "HISTORICAL_REPRODUCTION_PENDING",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_if_present(path: Path) -> dict[str, Any] | None:
    return load(path) if path.is_file() else None


def write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(
            [{key: row.get(key) for key in columns} for row in rows]
        )
    temporary.replace(path)


def result_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["task"]): row for row in manifest.get("results", [])}


def selected_sources(
    root: Path, baseline_path: Path
) -> list[dict[str, Any]]:
    """Return the only manifests eligible for the primary result tables."""
    acc_root = root / "full_acc_rtl_zero_guard_v3"
    definitions = [
        ("bf16", "matched_baseline", baseline_path, None),
        (
            "v5_attention",
            "full_acc",
            acc_root / "v5_attention" / "merged" / "manifest.json",
            "acc",
        ),
        (
            "v5_attention",
            "full_ppl",
            root / "full_ppl" / "v5_attention" / "manifest.json",
            "ppl",
        ),
        (
            "v5_mlp",
            "full_acc",
            acc_root / "v5_mlp" / "merged" / "manifest.json",
            "acc",
        ),
        (
            "v5_mlp",
            "full_ppl",
            root / "full_ppl" / "v5_mlp_retry_gpu0" / "manifest.json",
            "ppl",
        ),
        (
            "v5",
            "full_acc",
            acc_root / "v5" / "merged" / "manifest.json",
            "acc",
        ),
        (
            "v5",
            "full_ppl",
            root / "full_ppl" / "v5" / "manifest.json",
            "ppl",
        ),
        (
            "v5_mlp_down_s32_ablation",
            "diagnostic_8block_ppl",
            root
            / "diagnostic"
            / "v5_mlp_down_s32_8blocks_retry"
            / "manifest.json",
            "ppl",
        ),
    ]
    sources: list[dict[str, Any]] = []
    for case, role, path, kind in definitions:
        manifest = load_if_present(path)
        sources.append(
            {
                "case": case,
                "role": role,
                "path": path,
                "kind": kind,
                "manifest": manifest,
            }
        )
    return sources


def metric_rows_from_sources(
    sources: list[dict[str, Any]], root: Path
) -> list[dict[str, Any]]:
    baseline_source = next(item for item in sources if item["case"] == "bf16")
    baseline = baseline_source["manifest"]
    if baseline is None:
        raise FileNotFoundError(baseline_source["path"])
    baseline_rows = result_map(baseline)
    diagnostic_baseline = load_if_present(root / "smoke" / "bf16" / "manifest.json")
    diagnostic_baseline_rows = (
        result_map(diagnostic_baseline) if diagnostic_baseline else {}
    )
    rows: list[dict[str, Any]] = []
    for source in sources:
        manifest = source["manifest"]
        if manifest is None:
            continue
        kind_filter = source["kind"]
        for raw in manifest.get("results", []):
            kind = str(raw.get("kind"))
            if kind_filter is not None and kind != kind_filter:
                continue
            case = str(source["case"])
            task = str(raw["task"])
            value = float(raw["value"])
            if case == "bf16":
                baseline_value: float | None = value
            elif case == "v5_mlp_down_s32_ablation":
                candidate = diagnostic_baseline_rows.get(task)
                same_blocks = candidate is not None and int(
                    candidate.get("evaluated_blocks") or -1
                ) == int(raw.get("evaluated_blocks") or -2)
                baseline_value = float(candidate["value"]) if same_blocks else None
            else:
                candidate = baseline_rows.get(task)
                baseline_value = (
                    float(candidate["value"]) if candidate is not None else None
                )
            delta = None if baseline_value is None else value - baseline_value
            rows.append(
                {
                    "case": case,
                    "case_label": CASE_LABEL.get(case, case),
                    "source_role": source["role"],
                    "task": task,
                    "kind": kind,
                    "primary_metric": raw.get("primary_metric"),
                    "value": value,
                    "baseline_value": baseline_value,
                    "absolute_delta": delta,
                    "delta_pp": (
                        None if delta is None or kind != "acc" else 100.0 * delta
                    ),
                    "relative_delta_percent": (
                        None
                        if delta is None or not baseline_value
                        else 100.0 * delta / baseline_value
                    ),
                    "stderr": raw.get("stderr"),
                    "samples": raw.get("samples"),
                    "evaluated_blocks": raw.get("evaluated_blocks"),
                    "scoring_tokens": raw.get("scoring_tokens"),
                    "full_stream": raw.get("full_stream"),
                    "status": manifest.get("status"),
                    "hardware_contract_status": manifest.get(
                        "hardware_contract_status"
                    ),
                    "manifest": str(source["path"]),
                }
            )
    return rows


def manifest_audit(manifest: dict[str, Any] | None) -> dict[str, int]:
    if manifest is None:
        return {}
    values = manifest.get("hardware_audit_total") or manifest.get(
        "hardware_audit"
    ) or {}
    return {str(key): int(value) for key, value in values.items()}


def preferred_case_manifest(
    sources: list[dict[str, Any]], case: str
) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = [item for item in sources if item["case"] == case]
    for role in (
        "matched_baseline",
        "full_acc",
        "full_ppl",
        "diagnostic_8block_ppl",
    ):
        for item in candidates:
            if item["role"] == role and item["manifest"] is not None:
                return item["path"], item["manifest"]
    return None, None


def source_manifest(
    sources: list[dict[str, Any]], case: str, role: str
) -> tuple[Path | None, dict[str, Any] | None]:
    for item in sources:
        if item["case"] == case and item["role"] == role:
            return item["path"], item["manifest"]
    return None, None


def build_width_findings(
    root: Path,
    sources: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one explicit register of closed and still-open numeric contracts.

    Static RTL/software alignment and dynamic precision sufficiency are separate
    claims.  A format may be implemented consistently and still be too narrow;
    conversely, a non-zero deliberate clamp is not automatically a bit-width
    overflow.  Keep those cases distinguishable in the paper-facing outputs.
    """

    attn_ppl_path, attn_ppl = source_manifest(
        sources, "v5_attention", "full_ppl"
    )
    mlp_ppl_path, mlp_ppl = source_manifest(sources, "v5_mlp", "full_ppl")
    full_ppl_path, full_ppl = source_manifest(sources, "v5", "full_ppl")
    attn_acc_path, attn_acc = source_manifest(
        sources, "v5_attention", "full_acc"
    )
    s32_path, s32 = source_manifest(
        sources, "v5_mlp_down_s32_ablation", "diagnostic_8block_ppl"
    )

    attn_ppl_audit = manifest_audit(attn_ppl)
    mlp_ppl_audit = manifest_audit(mlp_ppl)
    full_ppl_audit = manifest_audit(full_ppl)
    attn_acc_audit = manifest_audit(attn_acc)

    current_attention_shards: list[tuple[Path, dict[str, Any]]] = []
    for shard_path in sorted(
        (
            root
            / "full_acc_rtl_zero_guard_v3"
            / "v5_attention"
        ).glob("shard_*/manifest.json")
    ):
        current_attention_shards.append((shard_path, load(shard_path)))
    current_attention_format_errors = sum(
        manifest_audit(manifest).get("linear_total_shift_format_error", 0)
        for _, manifest in current_attention_shards
    )
    current_attention_minima = [
        int(values["linear_total_shift_min"])
        for _, manifest in current_attention_shards
        for values in (manifest.get("hardware_audit_by_module") or {}).values()
        if values.get("linear_total_shift_min") is not None
    ]
    current_attention_minimum = (
        min(current_attention_minima) if current_attention_minima else None
    )

    failure_path = root / "full_acc" / "v5_attention" / "shard_gpu1" / "failure.json"
    legacy_failure = load_if_present(failure_path)
    failure_text = str((legacy_failure or {}).get("error") or "")
    observed_shift_25 = (
        attn_acc_audit.get("linear_total_shift_format_error", 0) > 0
        or current_attention_format_errors > 0
    )
    historical_shift_25 = "total=25 legal=[26,47]" in failure_text
    if observed_shift_25:
        attention_shift_status = "CONFIRMED_CONTRACT_GAP"
        attention_shift_evidence = (
            f"current format_error="
            f"{attn_acc_audit.get('linear_total_shift_format_error', current_attention_format_errors)}; "
            f"current min={current_attention_minimum}"
        )
    elif attn_acc is not None:
        attention_shift_status = "NOT_REPRODUCED_CURRENT_TWIN"
        attention_shift_evidence = (
            f"current full ACC format_error=0; current min={current_attention_minimum}; "
            f"historical_pre_update_failure={historical_shift_25}"
        )
    elif historical_shift_25:
        attention_shift_status = "HISTORICAL_REPRODUCTION_PENDING"
        attention_shift_evidence = (
            f"historical pre-update failure: {failure_text}; current completed "
            f"shards={len(current_attention_shards)}, format_error="
            f"{current_attention_format_errors}, current min={current_attention_minimum}"
        )
    else:
        attention_shift_status = "VALIDATION_GAP"
        attention_shift_evidence = (
            f"current completed shards={len(current_attention_shards)}; "
            f"format_error={current_attention_format_errors}; "
            f"current min={current_attention_minimum}"
        )
    if attention_shift_status == "NOT_REPRODUCED_CURRENT_TWIN":
        attention_shift_action = (
            "Keep the active [26,47] RTL contract for the measured scope; "
            "retain the historical shift-25 record and add 24/25/26 boundary "
            "regression vectors so future model exports fail closed."
        )
        attention_shift_severity = "closed"
    elif observed_shift_25:
        attention_shift_action = (
            "Extend the active RTL/software recovery contract to cover the "
            "reproduced shift and add 24/25/26 boundary regression vectors."
        )
        attention_shift_severity = "critical"
    else:
        attention_shift_action = (
            "Do not change RTL from the historical failure alone. Finish the "
            "current full ACC range scan; only if shift=25 reproduces, cover it "
            "and add 24/25/26 boundary regression."
        )
        attention_shift_severity = "high"

    down_saturation = mlp_ppl_audit.get("linear_output_saturation", 0)
    full_down_saturation = full_ppl_audit.get("linear_output_saturation", 0)
    qk_clip = attn_ppl_audit.get("qk_score_clip", 0)
    trace_layer31 = next(
        (
            row
            for row in trace_rows
            if row.get("trace_domain") == "attention"
            and int(row.get("layer", -1)) == 31
            and row.get("node") == "qk_score_cumulative"
        ),
        None,
    )
    layer31_boundary = None
    if trace_layer31 and trace_layer31.get("valid_scores"):
        layer31_boundary = (
            100.0
            * int(trace_layer31.get("reference_score_boundary_count") or 0)
            / int(trace_layer31["valid_scores"])
        )

    activation_elements = sum(
        manifest_audit(manifest).get("activation_elements", 0)
        for manifest in (attn_ppl, mlp_ppl)
        if manifest is not None
    )
    entry_saturation = sum(
        manifest_audit(manifest).get("fp_to_fixed_saturation", 0)
        for manifest in (attn_ppl, mlp_ppl)
        if manifest is not None
    )
    hadamard_saturation = sum(
        manifest_audit(manifest).get("hadamard_saturation", 0)
        for manifest in (attn_ppl, mlp_ppl)
        if manifest is not None
    )

    s32_result = (result_map(s32 or {}).get("wikitext2") if s32 else None)
    s32_blocks = int((s32_result or {}).get("evaluated_blocks") or 0)
    format_audit = load_if_present(root / "format_v3_contract_audit.json") or {}
    artifact_check = next(
        (
            row
            for row in format_audit.get("checks", [])
            if row.get("check_id") == "artifact_mlp_format_id"
        ),
        {},
    )

    rows = [
        {
            "finding_id": "post_rmsnorm_s24_f16",
            "component": "Post-RMSNorm activation / Hadamard input",
            "active_format": "S24, 16 fractional bits (range [-128, 127.9999847])",
            "status": (
                "SUPPORTED_CURRENT_SCOPE"
                if entry_saturation == 0 and hadamard_saturation == 0
                else "CONFIRMED_FAILURE"
            ),
            "severity": "closed" if entry_saturation == 0 else "critical",
            "evidence": (
                f"activation_elements={activation_elements}; "
                f"fp_to_fixed_saturation={entry_saturation}; "
                f"hadamard_saturation={hadamard_saturation}"
            ),
            "required_action": "Keep S24/F16 for the measured scope; do not relabel it Q16.16.",
            "source": "; ".join(
                str(path) for path in (attn_ppl_path, mlp_ppl_path) if path
            ),
        },
        {
            "finding_id": "attention_shift_25",
            "component": "Attention A8W8 Group32 ScaleCode recovery",
            "active_format": "S42 guard; legal total_shift [26,47]",
            "status": attention_shift_status,
            "severity": attention_shift_severity,
            "evidence": attention_shift_evidence,
            "required_action": attention_shift_action,
            "source": str(
                attn_acc_path
                if attn_acc is not None
                else (
                    current_attention_shards[-1][0]
                    if current_attention_shards
                    else failure_path
                )
            ),
        },
        {
            "finding_id": "attention_qk_pm16_clamp",
            "component": "QK score boundary",
            "active_format": "S20/F14 storage with an explicit ±16 clamp",
            "status": "OPEN_QUALITY_RISK" if qk_clip else "SUPPORTED_CURRENT_SCOPE",
            "severity": "medium" if qk_clip else "closed",
            "evidence": (
                f"WikiText-2 qk_score_clip={qk_clip}; "
                + (
                    f"layer31 boundary={layer31_boundary:.3f}%"
                    if layer31_boundary is not None
                    else "layer31 boundary unavailable"
                )
            ),
            "required_action": (
                "Use final ACC to decide; first ablate a wider clamp inside the "
                "existing S20/F14 native range before adding bits."
            ),
            "source": str(attn_ppl_path or ""),
        },
        {
            "finding_id": "softmax_probability_u16_counter",
            "component": "Softmax probability output",
            "active_format": "U16 probability; internal clamp counter not exported",
            "status": "OBSERVABILITY_GAP",
            "severity": "medium",
            "evidence": "hap_softmax_row_128 connects clamp_count to prob_clamp_count_unused",
            "required_action": "Expose the counter through the top/status register and mirror it in the software audit.",
            "source": str(
                Path("fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/rtl/attention")
                / "hap_softmax_row_128.sv"
            ),
        },
        {
            "finding_id": "mlp_internal_s37_s44_s46",
            "component": "MLP recovery and accumulation",
            "active_format": "Group S37/F24; Gate/Up S44/F24; Down S46/F24",
            "status": (
                "SUPPORTED_CURRENT_SCOPE"
                if not any(
                    mlp_ppl_audit.get(key, 0)
                    for key in (
                        "linear_group_guard_overflow_s37",
                        "linear_accumulator_overflow",
                        "linear_software_group_guard_overflow",
                        "linear_software_accumulator_overflow",
                    )
                )
                else "CONFIRMED_FAILURE"
            ),
            "severity": (
                "closed"
                if not any(
                    mlp_ppl_audit.get(key, 0)
                    for key in (
                        "linear_group_guard_overflow_s37",
                        "linear_accumulator_overflow",
                        "linear_software_group_guard_overflow",
                        "linear_software_accumulator_overflow",
                    )
                )
                else "critical"
            ),
            "evidence": (
                "guard_overflow={}; accumulator_overflow={}".format(
                    mlp_ppl_audit.get("linear_group_guard_overflow_s37", 0),
                    mlp_ppl_audit.get("linear_accumulator_overflow", 0),
                )
            ),
            "required_action": "Keep the active S37/S44/S46 production path.",
            "source": str(mlp_ppl_path or ""),
        },
        {
            "finding_id": "mlp_down_s24_f16",
            "component": "MLP Down projection output boundary",
            "active_format": "S24/F16 (range [-128, 127.9999847])",
            "status": "CONFIRMED_FAILURE" if down_saturation else "SUPPORTED_CURRENT_SCOPE",
            "severity": "critical" if down_saturation else "closed",
            "evidence": (
                f"MLP-only saturation={down_saturation}; "
                f"Full-V5 saturation={full_down_saturation}; "
                "layer31 trace reference_abs_max=587.87"
            ),
            "required_action": (
                "Change only the Down output boundary to signed 32-bit with 16 "
                "fractional bits, then rerun full PPL and six-task ACC."
            ),
            "source": str(mlp_ppl_path or full_ppl_path or ""),
        },
        {
            "finding_id": "mlp_down_output_abi_chain",
            "component": "MLP Down output RTL/DMA/Host ABI",
            "active_format": (
                "S24/F16 across accumulator finalize, scheduler/repack, "
                "6144-bit tile, 24 AXI256 beats and Host unpack"
            ),
            "status": "CONFIRMED_CONTRACT_GAP" if down_saturation else "VALIDATION_GAP",
            "severity": "critical" if down_saturation else "high",
            "evidence": (
                "active production sources retain out_projection_s24, "
                "16x16x24 payloads, OUTPUT_TILES*24 DMA beats and "
                "unpack_s24_q16; widening only the S46 accumulator does not "
                "remove the final S24 saturation"
            ),
            "required_action": (
                "Use S32/F16 for the correctness-first implementation and "
                "propagate it through the Down-only "
                "finalizer, shared slice/queue, scheduler/repack, serial/full "
                "command, resource/production top, tensor DMA and Host "
                "unpack/buffer sizing. Change each 16x16 output tile from "
                "6144 bits/24 AXI256 beats to 8192 bits/32 beats and the Host "
                "C2H payload from 192 KiB to 256 KiB; keep the MLP input and "
                "Gate/Up boundaries at S24/F16."
            ),
            "source": "; ".join(
                (
                    "fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/rtl/mlp/"
                    "hap_mlp_down_group_major_accum_s46.sv",
                    "fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/rtl/mlp/"
                    "hap_mlp_down_v5_scheduler16_s46.sv",
                    "fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/rtl/integration/"
                    "hap_mlp_tensor_dma_bridge.sv",
                    "fpga_llm_project/0_fix_newdataflow_Hadamard/HAP/host/"
                    "scalellm_hostops.py",
                )
            ),
        },
        {
            "finding_id": "mlp_down_s32_validation",
            "component": "Proposed MLP Down S32/F16 replacement",
            "active_format": "Software diagnostic only; not current RTL",
            "status": "VALIDATION_GAP",
            "severity": "high",
            "evidence": (
                f"diagnostic evaluated_blocks={s32_blocks}; full_stream=False; "
                "layer31 observed reference_abs_max=587.87, so S27/F16 is the "
                "minimum width for that trace while S32/F16 remains the safe ABI choice"
            ),
            "required_action": (
                "Require full WikiText-2 PPL, all six ACC tasks and a full-stream "
                "pre-saturation range sweep before freezing S27/S28/S32; use S32/F16 "
                "for the correctness-first implementation."
            ),
            "source": str(s32_path or ""),
        },
        {
            "finding_id": "artifact_mlp_format_id",
            "component": "Checked-in deployment artifact",
            "active_format": str(artifact_check.get("observed") or "unknown"),
            "status": (
                "SUPPORTED_CURRENT_SCOPE"
                if artifact_check.get("pass") is True
                else "DEPLOYMENT_BLOCKER"
            ),
            "severity": "critical" if artifact_check.get("pass") is not True else "closed",
            "evidence": (
                f"expected={artifact_check.get('expected')}; "
                f"observed={artifact_check.get('observed')}"
            ),
            "required_action": (
                "Regenerate/migrate artifacts after the final format contract "
                "is frozen. Because Down S32/F16 changes the output ABI, do "
                "not reuse 0x48384603; assign a new synchronized RTL/Host/"
                "artifact ID (recommended 0x48384604)."
            ),
            "source": str(artifact_check.get("source") or ""),
        },
    ]
    for row in rows:
        row["open"] = row["status"] in OPEN_WIDTH_STATUSES
    return rows


def build_case_summaries(
    rows: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_case_task = {(row["case"], row["task"]): row for row in rows}
    baseline_acc = [
        by_case_task[("bf16", task)]["value"]
        for task in TASK_ORDER
        if ("bf16", task) in by_case_task
    ]
    baseline_macro = (
        sum(baseline_acc) / len(baseline_acc)
        if len(baseline_acc) == len(TASK_ORDER)
        else None
    )
    summaries: list[dict[str, Any]] = []
    for case in CASE_ORDER:
        acc_rows = [
            by_case_task[(case, task)]
            for task in TASK_ORDER
            if (case, task) in by_case_task
        ]
        ppl_row = by_case_task.get((case, "wikitext2"))
        acc_complete = len(acc_rows) == len(TASK_ORDER)
        macro = (
            sum(float(row["value"]) for row in acc_rows) / len(acc_rows)
            if acc_complete
            else None
        )
        macro_delta_pp = (
            None
            if macro is None or baseline_macro is None
            else 100.0 * (macro - baseline_macro)
        )
        ppl_delta_percent = (
            None if ppl_row is None else ppl_row["relative_delta_percent"]
        )
        acc_pass = (
            None
            if case == "bf16" or macro_delta_pp is None
            else macro_delta_pp >= -ACC_DROP_LIMIT_PP[case]
        )
        ppl_pass = (
            None
            if case == "bf16" or ppl_delta_percent is None
            else ppl_delta_percent <= PPL_RISE_LIMIT_PERCENT[case]
        )
        selected_path, selected_manifest = preferred_case_manifest(sources, case)
        audit = manifest_audit(selected_manifest)
        contract_status = (
            selected_manifest.get("hardware_contract_status")
            if selected_manifest is not None
            else "missing"
        )
        contract_pass = contract_status in {"valid", None}
        if case == "bf16":
            overall = "BASELINE" if acc_complete and ppl_row else "INCOMPLETE"
        elif not acc_complete or ppl_row is None:
            overall = "INCOMPLETE"
        elif not contract_pass:
            overall = "FAIL_CONTRACT"
        elif not acc_pass and not ppl_pass:
            overall = "FAIL_ACC_PPL"
        elif not acc_pass:
            overall = "FAIL_ACC"
        elif not ppl_pass:
            overall = "FAIL_PPL"
        else:
            overall = "PASS"
        summaries.append(
            {
                "case": case,
                "case_label": CASE_LABEL[case],
                "acc_tasks_complete": len(acc_rows),
                "acc_tasks_expected": len(TASK_ORDER),
                "macro_accuracy": macro,
                "baseline_macro_accuracy": baseline_macro,
                "macro_delta_pp": macro_delta_pp,
                "acc_limit_pp": (
                    None if case == "bf16" else ACC_DROP_LIMIT_PP[case]
                ),
                "acc_quality_pass": acc_pass,
                "ppl": None if ppl_row is None else ppl_row["value"],
                "baseline_ppl": (
                    None if ppl_row is None else ppl_row["baseline_value"]
                ),
                "ppl_delta_percent": ppl_delta_percent,
                "ppl_limit_percent": (
                    None if case == "bf16" else PPL_RISE_LIMIT_PERCENT[case]
                ),
                "ppl_quality_pass": ppl_pass,
                "hardware_contract_status": contract_status,
                "format_errors": audit.get("linear_total_shift_format_error"),
                "guard_overflow": audit.get(
                    "linear_group_guard_overflow_s37"
                ),
                "accumulator_overflow": audit.get(
                    "linear_accumulator_overflow"
                ),
                "linear_output_saturation": audit.get(
                    "linear_output_saturation"
                ),
                "overall": overall,
                "manifest": str(selected_path) if selected_path else None,
            }
        )
    return summaries


def collect_trace_rows(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    definitions = [
        ("v5_attention", root / "node_trace" / "manifest.json"),
        ("v5_mlp", root / "node_trace_mlp" / "manifest.json"),
    ]
    rows: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for case, path in definitions:
        domain = "attention" if case == "v5_attention" else "mlp"
        manifest = load_if_present(path)
        if manifest is None:
            coverage.append(
                {
                    "case": case,
                    "trace_domain": domain,
                    "required_layers": "0,15,31",
                    "observed_layers": "",
                    "required_nodes_per_layer": 7,
                    "complete": False,
                    "manifest": str(path),
                }
            )
            continue
        trace_rows = (manifest.get("node_trace") or {}).get("rows", [])
        for raw in trace_rows:
            rows.append(
                {
                    **raw,
                    "case": case,
                    "trace_domain": raw.get("trace_domain", domain),
                    "manifest": str(path),
                }
            )
        expected_nodes = (
            ATTENTION_TRACE_NODES if domain == "attention" else MLP_TRACE_NODES
        )
        observed_layers = sorted({int(row["layer"]) for row in trace_rows})
        complete = set(observed_layers) == {0, 15, 31} and all(
            expected_nodes.issubset(
                {
                    str(row["node"])
                    for row in trace_rows
                    if int(row["layer"]) == layer
                }
            )
            for layer in (0, 15, 31)
        )
        coverage.append(
            {
                "case": case,
                "trace_domain": domain,
                "required_layers": "0,15,31",
                "observed_layers": ",".join(map(str, observed_layers)),
                "required_nodes_per_layer": len(expected_nodes),
                "complete": complete,
                "manifest": str(path),
            }
        )
    return rows, coverage


def collect_audits(
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    audit_rows: list[dict[str, Any]] = []
    linear_rows: list[dict[str, Any]] = []
    for case in ("v5_attention", "v5_mlp", "v5", "v5_mlp_down_s32_ablation"):
        path, manifest = preferred_case_manifest(sources, case)
        if manifest is None or path is None:
            continue
        for metric, value in manifest_audit(manifest).items():
            audit_rows.append(
                {
                    "case": case,
                    "metric": metric,
                    "value": value,
                    "manifest": str(path),
                }
            )
        modules = manifest.get("hardware_audit_by_module") or {}
        for module, values in modules.items():
            linear_rows.append(
                {"case": case, "module": module, **values, "manifest": str(path)}
            )
    return audit_rows, linear_rows


def fmt(value: Any, spec: str = ".6f", missing: str = "—") -> str:
    if value is None:
        return missing
    return format(float(value), spec)


def build_markdown(
    *,
    root: Path,
    baseline_path: Path,
    checkpoint_identity_path: Path,
    checkpoint_identity: dict[str, Any] | None,
    metric_rows: list[dict[str, Any]],
    case_summaries: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
    trace_coverage: list[dict[str, Any]],
    width_findings: list[dict[str, Any]],
    regression_evidence: dict[str, Any] | None,
    pause_evidence: dict[str, Any] | None,
    migration_evidence: dict[str, Any] | None,
) -> str:
    by_case_task = {(row["case"], row["task"]): row for row in metric_rows}
    lines = [
        "# Llama-3.1-8B-Instruct format-v3 整数孪生验证报告",
        "",
        f"Matched BF16 baseline：`{baseline_path}`",
        "",
        "Checkpoint fingerprint：`{}`（`{}`）".format(
            (checkpoint_identity or {}).get("fingerprint_sha256", "unavailable"),
            checkpoint_identity_path,
        ),
        "",
        "正式 worker 的历史 manifest 未内嵌 `model_identity`；本报告使用同一"
        "本地 checkpoint 路径已有的逐文件 SHA-256 身份文件补充 provenance，"
        "强制验证器会重新计算全部14个文件的 SHA-256；本流程不回写或伪造 "
        "worker manifest 字段。",
        "",
        "本报告只把指定的完整 ACC/PPL manifest 纳入主结果；smoke、8-block "
        "Down-S32 和 RTL-zero-guard 均明确标注，不得冒充当前硬件通过结果。",
        "",
    ]
    if pause_evidence is not None:
        lines.extend(
            [
                "## 执行状态",
                "",
                "本轮 MLP-only/Full V5 ACC 已按用户指令停止，状态为 "
                f"`{pause_evidence.get('status', 'paused_incomplete')}`；"
                "现有完整 PPL、Attention ACC 与节点 trace 保留有效，但缺失的 "
                "MLP/Full ACC 不得由部分请求进度替代。",
                "",
                "| Case | 任务 | 已处理 likelihood requests | 总请求 | 进度 | "
                "可报告 ACC |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for worker in pause_evidence.get("workers", []):
            lines.append(
                "| {case} | {task} | {done:,} | {total:,} | {progress:.1f}% | "
                "{available} |".format(
                    case=worker.get("case", "—"),
                    task=worker.get("task", "—"),
                    done=int(worker.get("likelihood_requests_processed") or 0),
                    total=int(worker.get("likelihood_requests_total") or 0),
                    progress=float(worker.get("progress_percent") or 0.0),
                    available=(
                        "是" if worker.get("valid_accuracy_available") else "否"
                    ),
                )
            )
        lines.extend(
            [
                "",
                str(pause_evidence.get("interpretation") or ""),
                "",
            ]
        )
    lines.extend(
        [
        "## 总体判定",
        "",
        "| 配置 | Macro ACC | ΔACC (pp) | ACC判定 | PPL | ΔPPL | PPL判定 | 合同 | 总判定 |",
        "|---|---:|---:|---|---:|---:|---|---|---|",
        ]
    )
    for row in case_summaries:
        lines.append(
            "| {label} | {macro} | {delta} | {acc} | {ppl} | {ppl_delta} | "
            "{ppl_pass} | {contract} | {overall} |".format(
                label=row["case_label"],
                macro=fmt(row["macro_accuracy"]),
                delta=fmt(row["macro_delta_pp"], "+.3f"),
                acc=(
                    "—"
                    if row["acc_quality_pass"] is None
                    else ("PASS" if row["acc_quality_pass"] else "FAIL")
                ),
                ppl=fmt(row["ppl"]),
                ppl_delta=(
                    "—"
                    if row["ppl_delta_percent"] is None
                    else fmt(row["ppl_delta_percent"], "+.3f") + "%"
                ),
                ppl_pass=(
                    "—"
                    if row["ppl_quality_pass"] is None
                    else ("PASS" if row["ppl_quality_pass"] else "FAIL")
                ),
                contract=row["hardware_contract_status"],
                overall=row["overall"],
            )
        )

    lines.extend(
        [
            "",
            "## 位宽与格式结论登记",
            "",
            "`SUPPORTED_CURRENT_SCOPE` 只表示当前指定模型、数据和 context=128 "
            "范围内未观察到失败；它不是缩窄位宽的授权。",
            "",
            "| ID | 模块/边界 | 当前格式 | 状态 | 严重度 | 动态/静态证据 | 必须动作 |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for finding in width_findings:
        def clean(value: Any) -> str:
            return str(value or "—").replace("|", "\\|").replace("\n", " ")

        lines.append(
            "| {finding_id} | {component} | {active_format} | {status} | "
            "{severity} | {evidence} | {required_action} |".format(
                **{key: clean(value) for key, value in finding.items()}
            )
        )

    if migration_evidence is not None:
        lines.extend(
            [
                "",
                "## MLP Down S32/F16 迁移闭环审计",
                "",
                "该审计检查当前 active production closure，不修改 RTL。当前设计"
                "仍是 S24/F16，因此迁移状态必须保持显式不完整，不能把内部 S46 "
                "误报为输出已经加宽。",
                "",
                "状态：`{}`（{}/{}）".format(
                    migration_evidence.get("status", "missing"),
                    migration_evidence.get("checks_passed", 0),
                    migration_evidence.get("checks_total", 0),
                ),
                "",
                "| 检查项 | 模块 | 结果 | 当前观察 |",
                "|---|---|---|---|",
            ]
        )
        for row in migration_evidence.get("checks", []):
            def migration_clean(value: Any) -> str:
                return str(value or "—").replace("|", "\\|").replace("\n", " ")

            lines.append(
                "| {check_id} | {component} | {result} | {observed} |".format(
                    check_id=migration_clean(row.get("check_id")),
                    component=migration_clean(row.get("component")),
                    result="PASS" if row.get("pass") else "FAIL",
                    observed=migration_clean(row.get("observed")),
                )
            )

    lines.extend(
        [
            "",
            "## 软件/Host 回归证据",
            "",
            "| suite | 状态 | tests | 说明 |",
            "|---|---|---:|---|",
        ]
    )
    for suite in (regression_evidence or {}).get("suites", []):
        observed = suite.get("observed_tests")
        expected = suite.get("expected_tests")
        lines.append(
            f"| {suite.get('suite')} | {suite.get('status')} | "
            f"{observed if observed is not None else '—'}/{expected} | "
            f"`{suite.get('command')}` |"
        )

    lines.extend(
        [
            "",
            "## 六任务零样本 ACC",
            "",
            "口径：`lm-evaluation-harness==0.4.11`、zero-shot continuation "
            "likelihood、context=128、六任务等权 macro。",
            "",
            "| 配置 | 任务 | 指标 | ACC | BF16 | Δ (pp) | stderr | 样本数 | 合同 |",
            "|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for case in CASE_ORDER:
        for task in TASK_ORDER:
            row = by_case_task.get((case, task))
            if row is None:
                continue
            lines.append(
                "| {case} | {task} | {metric} | {value:.6f} | {baseline:.6f} | "
                "{delta:+.3f} | {stderr} | {samples} | {contract} |".format(
                    case=CASE_LABEL[case],
                    task=task,
                    metric=PRIMARY_METRIC[task],
                    value=row["value"],
                    baseline=row["baseline_value"],
                    delta=row["delta_pp"],
                    stderr=fmt(row["stderr"]),
                    samples=row["samples"],
                    contract=row["hardware_contract_status"],
                )
            )

    lines.extend(
        [
            "",
            "## WikiText-2 全量 PPL",
            "",
            "口径：raw-v1 test 全流、128-token 非重叠 block、丢弃尾部、每个 "
            "block 首 token 不计 NLL。",
            "",
            "| 配置 | PPL | BF16 | Δ | Δ% | blocks | scoring tokens | full | 合同 |",
            "|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    ppl_cases = CASE_ORDER + ("v5_mlp_down_s32_ablation",)
    for case in ppl_cases:
        row = by_case_task.get((case, "wikitext2"))
        if row is None:
            continue
        lines.append(
            "| {case} | {value:.6f} | {baseline} | {delta} | {percent} | "
            "{blocks} | {tokens} | {full} | {contract} |".format(
                case=CASE_LABEL[case],
                value=row["value"],
                baseline=fmt(row["baseline_value"]),
                delta=fmt(row["absolute_delta"], "+.6f"),
                percent=(
                    "—"
                    if row["relative_delta_percent"] is None
                    else fmt(row["relative_delta_percent"], "+.3f") + "%"
                ),
                blocks=row["evaluated_blocks"],
                tokens=row["scoring_tokens"],
                full=row["full_stream"],
                contract=row["hardware_contract_status"],
            )
        )

    lines.extend(
        [
            "",
            "## 合同与根因审计",
            "",
            "| 配置 | format error | guard overflow | accumulator overflow | output saturation |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in case_summaries:
        if row["case"] == "bf16":
            continue
        lines.append(
            "| {label} | {format_errors} | {guard} | {accum} | {sat} |".format(
                label=row["case_label"],
                format_errors=row["format_errors"],
                guard=row["guard_overflow"],
                accum=row["accumulator_overflow"],
                sat=row["linear_output_saturation"],
            )
        )
    lines.extend(
        [
            "",
            "- 当前 MLP RTL 内部为 S37/S44/S46，但 Down 最终边界仍为 S24 "
            "Q8.16；Down-S32 仅是软件因果诊断。",
            "- `invalid_format_error` 表示结果精确模拟了 RTL 的非法 shift 置零行为，"
            "但硬件格式合同失败，不能写成硬件精度通过。",
            "- 非零 output saturation 必须结合 `linear_audit_by_module.csv` 定位，"
            "不得笼统归因给 RoPE 或 Softmax。",
            "",
            "## layer 0/15/31 节点 trace",
            "",
            "| domain | layers | 每层要求节点数 | 完整 | manifest |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in trace_coverage:
        lines.append(
            f"| {row['trace_domain']} | {row['observed_layers']} | "
            f"{row['required_nodes_per_layer']} | {row['complete']} | "
            f"`{row['manifest']}` |"
        )
    lines.extend(
        [
            "",
            "| case | domain | layer | node | cosine | NMSE | max abs error | score boundary/valid |",
            "|---|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in trace_rows:
        boundary = row.get("reference_score_boundary_count")
        valid = row.get("valid_scores")
        boundary_text = (
            f"{boundary}/{valid}" if boundary is not None and valid is not None else "—"
        )
        lines.append(
            "| {case} | {domain} | {layer} | {node} | {cosine:.10f} | "
            "{nmse:.3e} | {max_error:.6g} | {boundary} |".format(
                case=row["case"],
                domain=row.get("trace_domain", "attention"),
                layer=row["layer"],
                node=row["node"],
                cosine=row["cosine"],
                nmse=row["nmse"],
                max_error=row["max_abs_error"],
                boundary=boundary_text,
            )
        )
    lines.extend(
        [
            "",
            "## 预注册阈值",
            "",
            "- Attention-only：Macro ACC 下降不超过 1.0 pp；PPL 相对上升不超过 10%。",
            "- MLP-only：Macro ACC 下降不超过 1.0 pp；PPL 相对上升不超过 10%。",
            "- Full V5：Macro ACC 下降不超过 1.5 pp；PPL 相对上升不超过 15%。",
            "- format error、非预期 guard/accumulator overflow 必须为 0。",
            "- 质量阈值通过与硬件合同通过是两个独立条件，二者均通过才能声称"
            "当前硬件定点链路保持精度。",
            "",
            "## 可复核产物",
            "",
            f"- 主指标：`{root / 'case_metrics.csv'}`",
            f"- case 判定：`{root / 'case_summary.csv'}`",
            f"- 节点 trace：`{root / 'node_trace.csv'}`",
            f"- 硬件计数器：`{root / 'hardware_audit.csv'}`",
            f"- Linear 模块审计：`{root / 'linear_audit_by_module.csv'}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    baseline_path = args.baseline_manifest.resolve()
    checkpoint_identity_path = (
        root.parent
        / "six_model_algorithm_literature_2048"
        / "model_identities"
        / "Llama-3.1-8B-Instruct.json"
    )
    checkpoint_identity = load_if_present(checkpoint_identity_path)
    sources = selected_sources(root, baseline_path)
    metric_rows = metric_rows_from_sources(sources, root)
    case_summaries = build_case_summaries(metric_rows, sources)
    trace_rows, trace_coverage = collect_trace_rows(root)
    width_findings = build_width_findings(root, sources, trace_rows)
    regression_evidence = load_if_present(root / "regression_evidence.json")
    pause_evidence = load_if_present(root / "validation_pause.json")
    migration_evidence = load_if_present(
        root / "mlp_down_s32_migration_audit.json"
    )
    audit_rows, linear_rows = collect_audits(sources)

    write_csv(
        root / "case_metrics.csv",
        [
            "case",
            "case_label",
            "source_role",
            "task",
            "kind",
            "primary_metric",
            "value",
            "baseline_value",
            "absolute_delta",
            "delta_pp",
            "relative_delta_percent",
            "stderr",
            "samples",
            "evaluated_blocks",
            "scoring_tokens",
            "full_stream",
            "status",
            "hardware_contract_status",
            "manifest",
        ],
        metric_rows,
    )
    write_csv(
        root / "case_summary.csv",
        [
            "case",
            "case_label",
            "acc_tasks_complete",
            "acc_tasks_expected",
            "macro_accuracy",
            "baseline_macro_accuracy",
            "macro_delta_pp",
            "acc_limit_pp",
            "acc_quality_pass",
            "ppl",
            "baseline_ppl",
            "ppl_delta_percent",
            "ppl_limit_percent",
            "ppl_quality_pass",
            "hardware_contract_status",
            "format_errors",
            "guard_overflow",
            "accumulator_overflow",
            "linear_output_saturation",
            "overall",
            "manifest",
        ],
        case_summaries,
    )
    write_csv(
        root / "node_trace.csv",
        [
            "case",
            "trace_domain",
            "layer",
            "trace_call",
            "tokens",
            "node",
            "elements",
            "cosine",
            "nmse",
            "mae",
            "max_abs_error",
            "reference_abs_max",
            "valid_scores",
            "reference_score_boundary_count",
            "manifest",
        ],
        trace_rows,
    )
    write_csv(
        root / "trace_coverage.csv",
        [
            "case",
            "trace_domain",
            "required_layers",
            "observed_layers",
            "required_nodes_per_layer",
            "complete",
            "manifest",
        ],
        trace_coverage,
    )
    write_csv(
        root / "hardware_audit.csv",
        ["case", "metric", "value", "manifest"],
        audit_rows,
    )
    write_csv(
        root / "linear_audit_by_module.csv",
        [
            "case",
            "module",
            "linear_total_shift_min",
            "linear_total_shift_max",
            "linear_group_guard_overflow_s37",
            "linear_software_group_guard_overflow",
            "linear_accumulator_overflow",
            "linear_software_accumulator_overflow",
            "linear_output_saturation",
            "manifest",
        ],
        linear_rows,
    )
    write_csv(
        root / "width_findings.csv",
        [
            "finding_id",
            "component",
            "active_format",
            "status",
            "severity",
            "open",
            "evidence",
            "required_action",
            "source",
        ],
        width_findings,
    )
    report = build_markdown(
        root=root,
        baseline_path=baseline_path,
        checkpoint_identity_path=checkpoint_identity_path,
        checkpoint_identity=checkpoint_identity,
        metric_rows=metric_rows,
        case_summaries=case_summaries,
        trace_rows=trace_rows,
        trace_coverage=trace_coverage,
        width_findings=width_findings,
        regression_evidence=regression_evidence,
        pause_evidence=pause_evidence,
        migration_evidence=migration_evidence,
    )
    temporary = root / "precision_validation_report.md.tmp"
    temporary.write_text(report, encoding="utf-8")
    temporary.replace(root / "precision_validation_report.md")
    print(
        json.dumps(
            {
                "root": str(root),
                "cases": case_summaries,
                "trace_coverage": trace_coverage,
                "open_width_findings": [
                    row for row in width_findings if row["open"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
