#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
FINE_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_fine19_pre_place.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_fine19_pre_place_audit.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s V5_POST_OPT_DCP FINE19_PROBE_DIR\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -f -- "$1")"
probe_dir="$(readlink -f -- "$2")"
export HAP_FINE19_PROBE_OUTPUT_SHA="$probe_dir/OUTPUT_SHA256SUMS"
probe_summary="$probe_dir/summary.txt"
probe_launcher_status="$probe_dir/launcher_status.txt"
for input in "$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$AUDIT_TCL" \
        "$LAUNCHER" "$HAP_FINE19_PROBE_OUTPUT_SHA" "$probe_summary" \
        "$probe_launcher_status"; do
    [[ -s "$input" ]] || {
        printf 'missing fine19 pre-place input: %s\n' "$input" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$HAP_FINE19_PROBE_OUTPUT_SHA")
for literal in 'status=PASS' 'final_exit_code=0' 'vivado_exit_code=0' \
        'probe_gate_exit_code=0' 'floorplan_mutated=0' \
        'implementation_commands_run=0' 'checkpoint_written=0'; do
    [[ "$(grep -Fxc -- "$literal" "$probe_launcher_status" || true)" -eq 1 ]] || {
        printf 'fine19 upstream launcher gate failed: %s\n' "$literal" >&2
        exit 2
    }
done
for literal in 'status=PASS' \
        'stage=V5_PRODUCTION_FINE19_FLOORPLAN_PROBE' \
        'contract_variant=P3_COHORT16_OOC10_19' \
        "input_dcp=$HAP_DCP" 'pblock_spec_count=19' 'member_overlap=0' \
        'pblock_dsp_coverage=5453' 'pblock_uram_coverage=752' \
        'raw_capacity_ok=1' 'floorplan_mutated=0' \
        'implementation_commands_run=0' 'checkpoint_written=0'; do
    [[ "$(grep -Fxc -- "$literal" "$probe_summary" || true)" -eq 1 ]] || {
        printf 'fine19 upstream summary gate failed: %s\n' "$literal" >&2
        exit 2
    }
done

mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; fine19 pre-place audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

# Pblock creation in memory and report_drc are allowed.  Implementation,
# timing constraints and design writers remain forbidden in both new sources.
audit_code="$(sed -E '/^[[:space:]]*#/d' "$AUDIT_TCL" "$FINE_LIB")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|set_false_path|set_max_delay|set_min_delay|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
    <<<"$audit_code"; then
    printf 'fine19 pre-place source contains a forbidden command\n' >&2
    exit 2
fi

export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] &&
    (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be an integer in 1..32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_FINE19_PREPLACE_DIR:-$ROOT/vivado/reports/production_v5_fine19_pre_place_audit_$STAMP}"
export HAP_FINE19_PREPLACE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_FINE19_PREPLACE_DIR" ]] || {
    printf 'fine19 pre-place evidence directory exists: %s\n' \
        "$HAP_FINE19_PREPLACE_DIR" >&2
    exit 2
}
mkdir "$HAP_FINE19_PREPLACE_DIR"

export HAP_FINE19_PREPLACE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_FINE19_PREPLACE_FINE_LIB="$FINE_LIB"
export HAP_FINE19_PREPLACE_LAUNCHER="$LAUNCHER"
export HAP_FINE19_PREPLACE_INPUT_SHA="$HAP_FINE19_PREPLACE_DIR/INPUT_SHA256SUMS"
export HAP_FINE19_PROBE_OUTPUT_SHA256
HAP_FINE19_PROBE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_FINE19_PROBE_OUTPUT_SHA" | awk '{print $1}')"
inputs=("$HAP_DCP" "$SELECTOR_LIB" "$FINE_LIB" "$AUDIT_TCL" "$LAUNCHER" \
    "$HAP_FINE19_PROBE_OUTPUT_SHA")
printf '%s\n' "${inputs[@]}" > "$HAP_FINE19_PREPLACE_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_FINE19_PREPLACE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_FINE19_PREPLACE_INPUT_MANIFEST_SHA256
HAP_FINE19_PREPLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_FINE19_PREPLACE_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_FINE19_PREPLACE_INPUT_SHA") \
    > "$HAP_FINE19_PREPLACE_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_production_v5_fine19_pre_place.tcl \
    -log "$HAP_FINE19_PREPLACE_DIR/vivado.log" \
    -journal "$HAP_FINE19_PREPLACE_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_FINE19_PREPLACE_INPUT_SHA") \
    > "$HAP_FINE19_PREPLACE_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_FINE19_PREPLACE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
(cd / && sha256sum -c --strict "$HAP_FINE19_PROBE_OUTPUT_SHA") \
    > "$HAP_FINE19_PREPLACE_DIR/upstream_probe_postcheck.txt" 2>&1
upstream_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 &&
      "$actual_manifest_sha" == "$HAP_FINE19_PREPLACE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi

for file in vivado.log vivado.jou; do
    [[ -e "$HAP_FINE19_PREPLACE_DIR/$file" ]] ||
        printf 'launcher_note=Vivado did not create %s\n' "$file" \
            > "$HAP_FINE19_PREPLACE_DIR/$file"
done
summary="$HAP_FINE19_PREPLACE_DIR/summary.txt"
gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$manifest_match" -eq 1 &&
      "$upstream_rc" -eq 0 && -s "$summary" ]]; then
    set +e
    gate_rc=0
    for required in selectors.txt pblocks.txt drc_pre_place.rpt; do
        [[ -s "$HAP_FINE19_PREPLACE_DIR/$required" ]] || gate_rc=1
    done
    for literal in \
        'status=V5_FINE19_PRE_PLACE_CONTRACT_AUDIT_PASS' \
        'stage=V5_FINE19_PRE_PLACE_CONTRACT_AUDIT' \
        'evidence_class=V5_FINE19_IN_MEMORY_PBLOCK_DRC' \
        'contract_variant=P3_COHORT16_OOC10_19' \
        "input_dcp=$HAP_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_FINE19_PREPLACE_INPUT_MANIFEST_SHA256" \
        'input_manifest_entries=6' 'provenance_verified=1' \
        "upstream_probe_manifest=$HAP_FINE19_PROBE_OUTPUT_SHA" \
        "upstream_probe_manifest_sha256=$HAP_FINE19_PROBE_OUTPUT_SHA256" \
        'upstream_probe_verified=1' 'dsp48e2=5453' 'uram288=752' \
        'mlp_kernel_dsp48e2=3072' 'raw_weight_push_loads=37' \
        'projection_weight_capture_ok=1' 'projection_primitives=443480' \
        'projection_dsp48e2=2240' 'center_region1_logic_primitives=74509' \
        'center_region1_cols4_5_dsp48e2=272' \
        'center_region1_cols6_7_dsp48e2=272' \
        'region3_input_primitives=2112' \
        'owner_region2_weight_primitives=2048' \
        'nonprojection_center_dsp48e2=85' \
        'projection_exact_cover=1' 'region1_exact_cover=1' \
        'owner_exact_cover=1' 'weight_owner_residency_ok=1' \
        'planned_slr0_dsp48e2=1862' 'planned_slr1_dsp48e2=1781' \
        'planned_slr2_dsp48e2=1810' 'planned_slr0_uram288=224' \
        'planned_slr1_uram288=224' 'planned_slr2_uram288=304' \
        'pblock_count=19' 'pblock_overlap=0' 'pblock_optimizer_extras=0' \
        'pblock_dsp_coverage=5453' 'pblock_uram_coverage=752' \
        'pblock_wrong_slr=0' 'pre_place_drc_errors=0' \
        'checkpoint_written=0' 'implementation_commands_run=0'; do
        if [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -ne 1 ]]; then
            printf 'fine19 pre-place summary gate failed: %s\n' "$literal" >&2
            gate_rc=1
        fi
    done
    set -e
fi

final_rc=0
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
elif [[ "$sha_rc" -ne 0 || "$manifest_match" -ne 1 ||
        "$upstream_rc" -ne 0 || "$gate_rc" -ne 0 ]]; then
    final_rc=1
fi
printf '%s\n' \
    "status=$([[ "$final_rc" -eq 0 ]] && printf PASS || printf FAIL)" \
    "final_exit_code=$final_rc" "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "upstream_probe_recheck_exit_code=$upstream_rc" \
    "audit_gate_exit_code=$gate_rc" 'checkpoint_written=0' \
    'implementation_commands_run=0' \
    > "$HAP_FINE19_PREPLACE_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_FINE19_PREPLACE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_FINE19_PREPLACE_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict \
    "$HAP_FINE19_PREPLACE_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 fine19 pre-place audit failed; evidence: %s\n' \
        "$HAP_FINE19_PREPLACE_DIR" >&2
    printf '%s\n' "$HAP_FINE19_PREPLACE_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_FINE19_PREPLACE_DIR"
