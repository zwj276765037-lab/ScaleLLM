#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p9_post_place_recovery.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
FINE_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
COMPOSITE_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p9_post_place_recovery.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s P9_DIAGNOSTIC_DCP FAILED_PLACE_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_P9_RECOVERY_DCP="$(readlink -f -- "$1")"
export HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA="$(readlink -f -- "$2")"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P9 recovery requires HAP_JOBS=32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
inputs=("$HAP_P9_RECOVERY_DCP" "$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA"
    "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE_LIB" "$TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || { printf 'missing P9 recovery input: %s\n' "$input" >&2; exit 2; }
    [[ "$input" != *$'\n'* && "$input" != *$'\r'* ]] || {
        printf 'newline is forbidden in P9 recovery input path: %q\n' "$input" >&2
        exit 2
    }
done

failed_dir="$(dirname "$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA")"
failed_summary="$failed_dir/summary.txt"
failed_launcher="$failed_dir/launcher_status.txt"
for evidence in "$failed_summary" "$failed_launcher"; do
    [[ -s "$evidence" ]] || { printf 'missing failed P9 evidence: %s\n' "$evidence" >&2; exit 2; }
done
(cd / && sha256sum -c --strict "$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA") >/dev/null
for literal in failure_stage=post_place_live_rediscovery place_design_completed=1 \
        diagnostic_checkpoint_written=1 acceptance_evidence=0 route_eligible=0 \
        checkpoint_written=0 status=FAIL; do
    [[ "$(grep -Fxc -- "$literal" "$failed_summary" || true)" -eq 1 ]] || {
        printf 'failed P9 summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P9 recovery not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

readonly_code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
    <<<"$readonly_code"; then
    printf 'P9 recovery Tcl contains a forbidden mutation command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_P9_RECOVERY_DIR:-$ROOT/vivado/reports/production_v5_p9_post_place_recovery_$STAMP}"
export HAP_P9_RECOVERY_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_P9_RECOVERY_DIR" ]] || {
    printf 'P9 recovery evidence directory exists: %s\n' "$HAP_P9_RECOVERY_DIR" >&2
    exit 2
}
mkdir "$HAP_P9_RECOVERY_DIR"
export HAP_P9_RECOVERY_INPUT_SHA="$HAP_P9_RECOVERY_DIR/INPUT_SHA256SUMS"
export HAP_P9_RECOVERY_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_P9_RECOVERY_FINE_LIB="$FINE_LIB"
export HAP_P9_RECOVERY_COMPOSITE_LIB="$COMPOSITE_LIB"
export HAP_P9_RECOVERY_LAUNCHER="$LAUNCHER"
printf '%s\n' "${inputs[@]}" > "$HAP_P9_RECOVERY_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P9_RECOVERY_INPUT_SHA"
export HAP_P9_RECOVERY_DCP_SHA256
HAP_P9_RECOVERY_DCP_SHA256="$(sha256sum -- "$HAP_P9_RECOVERY_DCP" | awk '{print $1}')"
export HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA256
HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA" | awk '{print $1}')"
export HAP_P9_RECOVERY_INPUT_MANIFEST_SHA256
HAP_P9_RECOVERY_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_P9_RECOVERY_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P9_RECOVERY_INPUT_SHA") \
    > "$HAP_P9_RECOVERY_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/diagnose_attention_mlp_production_v5_p9_post_place_recovery.tcl \
    -log "$HAP_P9_RECOVERY_DIR/vivado.log" \
    -journal "$HAP_P9_RECOVERY_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_P9_RECOVERY_INPUT_SHA") \
    > "$HAP_P9_RECOVERY_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
(cd / && sha256sum -c --strict "$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA") \
    > "$HAP_P9_RECOVERY_DIR/failed_place_postcheck.txt" 2>&1
failed_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_P9_RECOVERY_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_P9_RECOVERY_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi
for file in vivado.log vivado.jou; do
    [[ -e "$HAP_P9_RECOVERY_DIR/$file" ]] || \
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_P9_RECOVERY_DIR/$file"
done

summary="$HAP_P9_RECOVERY_DIR/summary.txt"
gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$failed_rc" -eq 0 && \
      "$manifest_match" -eq 1 && -s "$summary" && \
      -s "$HAP_P9_RECOVERY_DIR/congestion_post_place.rpt" ]]; then
    set +e
    gate_rc=0
    awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' "$summary" || gate_rc=1
    for literal in \
        status=P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS \
        evidence_class=READ_ONLY_P9_POST_PLACE_RECOVERY jobs=32 \
        "input_dcp=$HAP_P9_RECOVERY_DCP" \
        "input_dcp_sha256=$HAP_P9_RECOVERY_DCP_SHA256" \
        "input_manifest_sha256=$HAP_P9_RECOVERY_INPUT_MANIFEST_SHA256" \
        input_manifest_entries=7 \
        "failed_place_output_manifest=$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA" \
        "failed_place_output_manifest_sha256=$HAP_P9_RECOVERY_FAILED_PLACE_OUTPUT_SHA256" \
        failed_place_verified=1 place_design_completed_upstream=1 \
        contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21 \
        fine_contract_variant=P3_COHORT16_OOC10_19 pblock_count=21 \
        pblock_member_overlap=0 pblock_optimizer_extras=0 \
        pblock_dsp_coverage=5453 pblock_uram_coverage=752 pblock_wrong_slr=0 \
        central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        central_island_dsp=80 center_dsp_remaining=5 central_partition_ok=1 \
        dsp48e2=5453 uram288=752 mlp_kernel_dsp48e2=3072 \
        slr0_dsp48e2=1862 slr1_dsp48e2=1781 slr2_dsp48e2=1810 \
        slr0_uram288=224 slr1_uram288=224 slr2_uram288=304 \
        unplaced_primitives=0 wrong_slr_primitives=0 \
        p9_central_island_wrong_slr=0 p9_center_dsp_remaining_wrong_slr=0 \
        p9_mlp_remaining_wrong_slr=0 additional_wrong_slr=0 \
        attention_direct_unresolved=0 attention_direct_placement_ok=1 \
        data_bufg=0 congestion_schema_header_count=1 congestion_schema_ok=1 \
        resource_ok=1 selector_deltas_ok=1 placement_ok=1 \
        acceptance_evidence=0 route_eligible=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0; do
        if [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -ne 1 ]]; then
            printf 'P9 recovery summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        fi
    done
    for key in fine_member_delta mlp_residual_delta central_island_delta \
            mlp_remaining_delta attention_direct_delta \
            central_island_count mlp_remaining_count attention_direct_count \
            attention_direct_slr0 attention_direct_slr1 attention_direct_slr2 \
            congestion_level5_or_higher_windows \
            congestion_level6_or_higher_windows congestion_data_rows_recognized \
            post_place_wns_ns post_place_whs_ns fast_gate_ok \
            level5_screen_ok level6_congestion_ok; do
        awk -F= -v key="$key" '$1==key {n++} END{exit n==1?0:1}' "$summary" || {
            printf 'P9 recovery numeric field gate failed: %s\n' "$key" >&2
            gate_rc=1
        }
    done
    set -e
fi

final_rc=0
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
elif [[ "$sha_rc" -ne 0 || "$failed_rc" -ne 0 || \
        "$manifest_match" -ne 1 || "$gate_rc" -ne 0 ]]; then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "failed_place_recheck_exit_code=$failed_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "diagnosis_gate_exit_code=$gate_rc" \
    'floorplan_mutated=0' 'implementation_commands_run=0' \
    'checkpoint_written=0' 'route_eligible=0' \
    > "$HAP_P9_RECOVERY_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_P9_RECOVERY_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_P9_RECOVERY_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_P9_RECOVERY_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'P9 post-place recovery diagnosis failed; evidence: %s\n' \
        "$HAP_P9_RECOVERY_DIR" >&2
    printf '%s\n' "$HAP_P9_RECOVERY_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_P9_RECOVERY_DIR"
