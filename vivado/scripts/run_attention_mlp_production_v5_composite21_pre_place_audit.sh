#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_composite21_pre_place.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
FINE_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
COMPOSITE_LIB="$ROOT/vivado/scripts/v5_production_composite21_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_composite21_pre_place_audit.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s V5_POST_OPT_DCP COMPOSITE21_PROBE_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -f -- "$1")"
export HAP_COMPOSITE21_PROBE_OUTPUT_SHA="$(readlink -f -- "$2")"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'Composite21 production qualification requires HAP_JOBS=32: %q\n' \
        "$HAP_JOBS" >&2
    exit 2
}
inputs=("$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$COMPOSITE_LIB" \
    "$AUDIT_TCL" "$LAUNCHER" "$HAP_COMPOSITE21_PROBE_OUTPUT_SHA")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || {
        printf 'missing Composite21 pre-place input: %s\n' "$input" >&2
        exit 2
    }
    [[ "$input" != *$'\n'* && "$input" != *$'\r'* ]] || {
        printf 'newline is forbidden in Composite21 input path: %q\n' "$input" >&2
        exit 2
    }
done

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; Composite21 pre-place audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

audit_code="$(sed -E '/^[[:space:]]*#/d' "$AUDIT_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|set_false_path|set_max_delay|set_min_delay|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run|eval|uplevel)([^[:alnum:]_]|$)' \
    <<<"$audit_code"; then
    printf 'Composite21 pre-place Tcl contains a forbidden command\n' >&2
    exit 2
fi

probe_dir="$(dirname "$HAP_COMPOSITE21_PROBE_OUTPUT_SHA")"
probe_summary="$probe_dir/summary.txt"
probe_launcher_status="$probe_dir/launcher_status.txt"
for evidence in "$probe_summary" "$probe_launcher_status"; do
    [[ -s "$evidence" ]] || {
        printf 'missing Composite21 probe evidence: %s\n' "$evidence" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_PROBE_OUTPUT_SHA") >/dev/null
for literal in status=PASS \
        composite21_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21 \
        composite21_pblock_spec_count=21 composite21_member_overlap=0 \
        composite21_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9 \
        composite21_central_island_count=197091 \
        composite21_central_island_dsp=80 \
        composite21_mlp_remaining_count=88785 \
        composite21_center_dsp_remaining=5 \
        composite21_central_partition_ok=1 \
        composite21_aggregate_capacity_ok=1 \
        composite21_attention_direct_constrained=0 \
        composite21_soft_pblock_count=0 \
        composite21_hard_capacity_ok=1 \
        composite21_flexible_outer_90pct_fit=1 \
        composite21_dsp_coverage=5453 composite21_uram_coverage=752 \
        composite21_resource_distribution_ok=1 \
        "input_dcp=$HAP_DCP"; do
    [[ "$(grep -Fxc -- "$literal" "$probe_summary" || true)" -eq 1 ]] || {
        printf 'Composite21 probe summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
for literal in status=PASS final_exit_code=0 vivado_exit_code=0 \
        input_sha_recheck_exit_code=0 input_manifest_sha_match=1 \
        probe_gate_exit_code=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0; do
    [[ "$(grep -Fxc -- "$literal" "$probe_launcher_status" || true)" -eq 1 ]] || {
        printf 'Composite21 probe launcher gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_COMPOSITE21_PREPLACE_DIR:-$ROOT/vivado/reports/production_v5_composite21_pre_place_$STAMP}"
export HAP_COMPOSITE21_PREPLACE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_COMPOSITE21_PREPLACE_DIR" ]] || {
    printf 'Composite21 pre-place evidence directory exists: %s\n' \
        "$HAP_COMPOSITE21_PREPLACE_DIR" >&2
    exit 2
}
mkdir "$HAP_COMPOSITE21_PREPLACE_DIR"
export HAP_COMPOSITE21_PREPLACE_INPUT_SHA="$HAP_COMPOSITE21_PREPLACE_DIR/INPUT_SHA256SUMS"
export HAP_COMPOSITE21_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_COMPOSITE21_FINE_LIB="$FINE_LIB"
export HAP_COMPOSITE21_LIB="$COMPOSITE_LIB"
export HAP_COMPOSITE21_PREPLACE_LAUNCHER="$LAUNCHER"
printf '%s\n' "${inputs[@]}" > "$HAP_COMPOSITE21_PREPLACE_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_COMPOSITE21_PREPLACE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_COMPOSITE21_PROBE_OUTPUT_SHA256
HAP_COMPOSITE21_PROBE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_COMPOSITE21_PROBE_OUTPUT_SHA" | awk '{print $1}')"
export HAP_COMPOSITE21_PREPLACE_INPUT_MANIFEST_SHA256
HAP_COMPOSITE21_PREPLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_COMPOSITE21_PREPLACE_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_PREPLACE_INPUT_SHA") \
    > "$HAP_COMPOSITE21_PREPLACE_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_production_v5_composite21_pre_place.tcl \
    -log "$HAP_COMPOSITE21_PREPLACE_DIR/vivado.log" \
    -journal "$HAP_COMPOSITE21_PREPLACE_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_PREPLACE_INPUT_SHA") \
    > "$HAP_COMPOSITE21_PREPLACE_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_COMPOSITE21_PREPLACE_INPUT_SHA" \
    2>/dev/null | awk '{print $1}')"
manifest_rc=$?
(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_PROBE_OUTPUT_SHA") \
    > "$HAP_COMPOSITE21_PREPLACE_DIR/probe_output_postcheck.txt" 2>&1
probe_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_COMPOSITE21_PREPLACE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi
for file in vivado.log vivado.jou; do
    [[ -e "$HAP_COMPOSITE21_PREPLACE_DIR/$file" ]] ||
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_COMPOSITE21_PREPLACE_DIR/$file"
done

summary="$HAP_COMPOSITE21_PREPLACE_DIR/summary.txt"
gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$probe_rc" -eq 0 && \
      "$manifest_match" -eq 1 && -s "$summary" ]]; then
    set +e
    gate_rc=0
    for required in summary.txt selectors_base.txt selectors_fine19.txt \
            selectors_composite21.txt pblocks.txt drc_pre_place.rpt INPUT_FILES \
            INPUT_SHA256SUMS input_sha_precheck.txt input_sha_postcheck.txt \
            probe_output_postcheck.txt vivado.log vivado.jou; do
        [[ -s "$HAP_COMPOSITE21_PREPLACE_DIR/$required" ]] || {
            printf 'missing Composite21 pre-place output: %s\n' "$required" >&2
            gate_rc=1
        }
    done
    awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' "$summary" || gate_rc=1
    for literal in \
        'status=V5_COMPOSITE21_PRE_PLACE_AUDIT_PASS' \
        'stage=V5_PRODUCTION_COMPOSITE21_PRE_PLACE_AUDIT' \
        'evidence_class=IN_MEMORY_PRE_PLACE_PBLOCK_DRC' 'jobs=32' \
        "input_dcp=$HAP_DCP" "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_COMPOSITE21_PREPLACE_INPUT_MANIFEST_SHA256" \
        'input_manifest_entries=7' \
        "probe_output_manifest=$HAP_COMPOSITE21_PROBE_OUTPUT_SHA" \
        "probe_output_manifest_sha256=$HAP_COMPOSITE21_PROBE_OUTPUT_SHA256" \
        'probe_verified=1' \
        'contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
        'fine_contract_variant=P3_COHORT16_OOC10_19' 'pblock_count=21' \
        'member_count=1718643' 'member_overlap=0' 'optimizer_extra_count=0' \
        'soft_pblock_count=0' 'soft_outside=0' \
        'fine_member_count=1432847' 'mlp_residual_count=285796' \
        'central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' \
        'central_island_count=197091' 'central_island_delta=0' \
        'central_island_dsp=80' 'mlp_remaining_count=88785' \
        'mlp_remaining_delta=0' 'center_dsp_remaining_count=5' \
        'center_dsp_remaining_dsp=5' 'central_partition_ok=1' \
        'attention_direct_count=71350' 'attention_direct_constrained=0' \
        'owner_overlap=0' \
        'hard_resource_intrusion=0' 'exact_partition=1' \
        'pblock_dsp_coverage=5453' 'pblock_uram_coverage=752' \
        'pblock_wrong_slr=0' 'pre_place_drc_errors=0' \
        'floorplan_mutated_in_memory=1' 'implementation_commands_run=0' \
        'checkpoint_written=0'; do
        if [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -ne 1 ]]; then
            printf 'Composite21 pre-place summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        fi
    done
    [[ "$(grep -c '_target=' "$HAP_COMPOSITE21_PREPLACE_DIR/pblocks.txt" || true)" \
        -eq 21 ]] || gate_rc=1
    set -e
fi

final_rc=0
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
elif [[ "$sha_rc" -ne 0 || "$probe_rc" -ne 0 || "$manifest_match" -ne 1 || \
        "$gate_rc" -ne 0 ]]; then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "probe_output_recheck_exit_code=$probe_rc" \
    "audit_gate_exit_code=$gate_rc" \
    'floorplan_mutated_in_memory=1' 'implementation_commands_run=0' \
    'checkpoint_written=0' > "$HAP_COMPOSITE21_PREPLACE_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_COMPOSITE21_PREPLACE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
[[ "${#outputs[@]}" -ne 0 ]] || {
    printf 'Composite21 pre-place audit produced no evidence\n' >&2
    exit 1
}
sha256sum -- "${outputs[@]}" > "$HAP_COMPOSITE21_PREPLACE_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict \
    "$HAP_COMPOSITE21_PREPLACE_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 Composite21 pre-place audit failed; evidence: %s\n' \
        "$HAP_COMPOSITE21_PREPLACE_DIR" >&2
    printf '%s\n' "$HAP_COMPOSITE21_PREPLACE_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_COMPOSITE21_PREPLACE_DIR"
