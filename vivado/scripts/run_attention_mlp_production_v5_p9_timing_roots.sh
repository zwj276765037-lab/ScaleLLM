#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p9_timing_roots.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p9_timing_roots.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s P9_DIAGNOSTIC_DCP P9_RECOVERY_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_P9_TIMING_DCP="$(readlink -f -- "$1")"
export HAP_P9_TIMING_RECOVERY_OUTPUT_SHA="$(readlink -f -- "$2")"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P9 timing diagnosis requires HAP_JOBS=32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
inputs=("$HAP_P9_TIMING_DCP" "$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA" \
    "$TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || { printf 'missing P9 timing input: %s\n' "$input" >&2; exit 2; }
    [[ "$input" != *$'\n'* && "$input" != *$'\r'* ]] || {
        printf 'newline is forbidden in P9 timing input path: %q\n' "$input" >&2
        exit 2
    }
done

recovery_dir="$(dirname "$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA")"
recovery_summary="$recovery_dir/summary.txt"
recovery_launcher="$recovery_dir/launcher_status.txt"
for evidence in "$recovery_summary" "$recovery_launcher"; do
    [[ -s "$evidence" ]] || { printf 'missing P9 recovery evidence: %s\n' "$evidence" >&2; exit 2; }
done
(cd / && sha256sum -c --strict "$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA") >/dev/null
for literal in status=P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS \
        congestion_level5_or_higher_windows=24 \
        congestion_level6_or_higher_windows=12 fast_gate_ok=0 \
        acceptance_evidence=0 route_eligible=0 \
        implementation_commands_run=0 checkpoint_written=0; do
    [[ "$(grep -Fxc -- "$literal" "$recovery_summary" || true)" -eq 1 ]] || {
        printf 'P9 recovery summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
for literal in status=PASS final_exit_code=0 vivado_exit_code=0 \
        diagnosis_gate_exit_code=0 route_eligible=0; do
    [[ "$(grep -Fxc -- "$literal" "$recovery_launcher" || true)" -eq 1 ]] || {
        printf 'P9 recovery launcher gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P9 timing diagnosis not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

readonly_code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
    <<<"$readonly_code"; then
    printf 'P9 timing Tcl contains a forbidden mutation command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_P9_TIMING_DIR:-$ROOT/vivado/reports/production_v5_p9_timing_roots_$STAMP}"
export HAP_P9_TIMING_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_P9_TIMING_DIR" ]] || {
    printf 'P9 timing evidence directory exists: %s\n' "$HAP_P9_TIMING_DIR" >&2
    exit 2
}
mkdir "$HAP_P9_TIMING_DIR"
export HAP_P9_TIMING_INPUT_SHA="$HAP_P9_TIMING_DIR/INPUT_SHA256SUMS"
export HAP_P9_TIMING_LAUNCHER="$LAUNCHER"
printf '%s\n' "${inputs[@]}" > "$HAP_P9_TIMING_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_P9_TIMING_INPUT_SHA"
export HAP_P9_TIMING_DCP_SHA256
HAP_P9_TIMING_DCP_SHA256="$(sha256sum -- "$HAP_P9_TIMING_DCP" | awk '{print $1}')"
export HAP_P9_TIMING_RECOVERY_OUTPUT_SHA256
HAP_P9_TIMING_RECOVERY_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA" | awk '{print $1}')"
export HAP_P9_TIMING_INPUT_MANIFEST_SHA256
HAP_P9_TIMING_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_P9_TIMING_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_P9_TIMING_INPUT_SHA") \
    > "$HAP_P9_TIMING_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/diagnose_attention_mlp_production_v5_p9_timing_roots.tcl \
    -log "$HAP_P9_TIMING_DIR/vivado.log" \
    -journal "$HAP_P9_TIMING_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_P9_TIMING_INPUT_SHA") \
    > "$HAP_P9_TIMING_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
(cd / && sha256sum -c --strict "$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA") \
    > "$HAP_P9_TIMING_DIR/recovery_output_postcheck.txt" 2>&1
recovery_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_P9_TIMING_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_P9_TIMING_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi
for file in vivado.log vivado.jou; do
    [[ -e "$HAP_P9_TIMING_DIR/$file" ]] || \
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_P9_TIMING_DIR/$file"
done

summary="$HAP_P9_TIMING_DIR/summary.txt"
gate_rc=125
required_reports=(setup_paths.tsv hold_paths.tsv setup_category_pairs.txt \
    hold_category_pairs.txt timing_summary_post_place.rpt \
    timing_setup_post_place.rpt timing_hold_post_place.rpt \
    high_fanout_post_place.rpt clock_utilization_post_place.rpt)
reports_ok=1
for report in "${required_reports[@]}"; do
    [[ -s "$HAP_P9_TIMING_DIR/$report" ]] || reports_ok=0
done
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$recovery_rc" -eq 0 && \
      "$manifest_match" -eq 1 && "$reports_ok" -eq 1 && -s "$summary" ]]; then
    set +e
    gate_rc=0
    awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' "$summary" || gate_rc=1
    for literal in status=P9_TIMING_ROOT_DIAGNOSIS_PASS \
        evidence_class=READ_ONLY_P9_TIMING_ROOT_DIAGNOSIS jobs=32 \
        "input_dcp=$HAP_P9_TIMING_DCP" \
        "input_dcp_sha256=$HAP_P9_TIMING_DCP_SHA256" \
        "input_manifest_sha256=$HAP_P9_TIMING_INPUT_MANIFEST_SHA256" \
        input_manifest_entries=4 \
        "recovery_output_manifest=$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA" \
        "recovery_output_manifest_sha256=$HAP_P9_TIMING_RECOVERY_OUTPUT_SHA256" \
        recovery_terminal_fail_verified=1 pblock_count=21 \
        setup_path_count=500 hold_path_count=500 \
        source_congestion_level5_or_higher_windows=24 \
        source_congestion_level6_or_higher_windows=12 \
        acceptance_evidence=0 route_eligible=0 floorplan_mutated=0 \
        implementation_commands_run=0 checkpoint_written=0; do
        if [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -ne 1 ]]; then
            printf 'P9 timing summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        fi
    done
    for key in recovery_output_entries setup_cross_slr_count \
            hold_cross_slr_count setup_unresolved_endpoint_count \
            hold_unresolved_endpoint_count setup_category_pair_count \
            hold_category_pair_count post_place_wns_ns post_place_whs_ns \
            open_checkpoint_elapsed_ms path_query_elapsed_ms report_elapsed_ms \
            total_elapsed_ms; do
        awk -F= -v key="$key" '$1==key {n++} END{exit n==1?0:1}' "$summary" || {
            printf 'P9 timing numeric field gate failed: %s\n' "$key" >&2
            gate_rc=1
        }
    done
    set -e
fi

final_rc=0
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
elif [[ "$sha_rc" -ne 0 || "$recovery_rc" -ne 0 || \
        "$manifest_match" -ne 1 || "$reports_ok" -ne 1 || "$gate_rc" -ne 0 ]]; then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "recovery_output_recheck_exit_code=$recovery_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "diagnosis_gate_exit_code=$gate_rc" "required_reports_ok=$reports_ok" \
    'floorplan_mutated=0' 'implementation_commands_run=0' \
    'checkpoint_written=0' 'route_eligible=0' \
    > "$HAP_P9_TIMING_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_P9_TIMING_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_P9_TIMING_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict "$HAP_P9_TIMING_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'P9 timing-root diagnosis failed; evidence: %s\n' \
        "$HAP_P9_TIMING_DIR" >&2
    printf '%s\n' "$HAP_P9_TIMING_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_P9_TIMING_DIR"
