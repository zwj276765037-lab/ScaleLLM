#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_p10_p4_pre_place.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
PBLOCK_LIB="$ROOT/vivado/scripts/v5_production_fine19_floorplan.tcl"
PHYSICAL_LIB="$ROOT/vivado/scripts/v5_production_physical448_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p4_pre_place.sh"

[[ $# -eq 1 ]] || { printf 'usage: %s V5_POST_OPT_DCP\n' "$0" >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -f -- "$1")"
inputs=("$HAP_DCP" "$SELECTOR_LIB" "$GEOMETRY_LIB" "$PBLOCK_LIB"
    "$PHYSICAL_LIB" "$AUDIT_TCL" "$LAUNCHER")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || { printf 'missing P4 input: %s\n' "$input" >&2; exit 2; }
done
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; P4 audit not started\n' >&2
    exit 75
fi

for source in "$AUDIT_TCL" "$GEOMETRY_LIB" "$PBLOCK_LIB" "$PHYSICAL_LIB"; do
    code="$(sed -E '/^[[:space:]]*#/d' "$source")"
    if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|set_false_path|set_max_delay|set_min_delay|write_checkpoint|write_bitstream|write_cfgmem)([^[:alnum:]_]|$)' \
        <<<"$code"; then
        printf 'P4 read-only source contains a forbidden command: %s\n' "$source" >&2
        exit 2
    fi
done

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_PREPLACE_AUDIT_DIR:-$ROOT/vivado/reports/production_v5_p10_p4_pre_place_${STAMP}}"
export HAP_PREPLACE_AUDIT_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_PREPLACE_AUDIT_DIR" ]] || {
    printf 'P4 audit directory exists: %s\n' "$HAP_PREPLACE_AUDIT_DIR" >&2
    exit 2
}
mkdir "$HAP_PREPLACE_AUDIT_DIR"
export HAP_PREPLACE_INPUT_SHA="$HAP_PREPLACE_AUDIT_DIR/INPUT_SHA256SUMS"
export HAP_PREPLACE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_PREPLACE_GEOMETRY_LIB="$GEOMETRY_LIB"
export HAP_PREPLACE_PBLOCK_LIB="$PBLOCK_LIB"
export HAP_PREPLACE_PHYSICAL_LIB="$PHYSICAL_LIB"
export HAP_PREPLACE_LAUNCHER="$LAUNCHER"
printf '%s\n' "${inputs[@]}" > "$HAP_PREPLACE_AUDIT_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_PREPLACE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_PREPLACE_INPUT_MANIFEST_SHA256
HAP_PREPLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PREPLACE_INPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_PREPLACE_INPUT_SHA") \
    > "$HAP_PREPLACE_AUDIT_DIR/input_sha_precheck.txt" 2>&1

cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_production_v5_p10_p4_pre_place.tcl \
    -log "$HAP_PREPLACE_AUDIT_DIR/vivado.log" \
    -journal "$HAP_PREPLACE_AUDIT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_PREPLACE_INPUT_SHA") \
    > "$HAP_PREPLACE_AUDIT_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_PREPLACE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
manifest_match=0
if [[ "$manifest_rc" -eq 0 &&
      "$actual_manifest_sha" == "$HAP_PREPLACE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_match=1
fi

summary="$HAP_PREPLACE_AUDIT_DIR/summary.txt"
audit_gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && "$manifest_match" -eq 1 &&
      -s "$summary" ]]; then
    audit_gate_rc=0
    required=(summary.txt selectors.txt attention_geometry.txt
        physical448_plan.txt pblocks.txt utilization_pre_place.rpt
        drc_pre_place.rpt INPUT_FILES INPUT_SHA256SUMS
        input_sha_precheck.txt input_sha_postcheck.txt vivado.log vivado.jou)
    for name in "${required[@]}"; do
        [[ -s "$HAP_PREPLACE_AUDIT_DIR/$name" ]] || audit_gate_rc=1
    done
    expected=(
        'status=V5_P10_P4_PRE_PLACE_PASS'
        'evidence_class=V5_P10_P4_READ_ONLY_PRE_PLACE'
        "input_dcp=$HAP_DCP"
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256"
        "input_manifest_sha256=$HAP_PREPLACE_INPUT_MANIFEST_SHA256"
        'input_manifest_entries=7'
        'provenance_verified=1'
        'base_contract_variant=P2_COHORT16_COL2_12_2'
        'physical_contract_variant=P4_COHORT16_PHYSICAL4_8_4_19'
        'dsp48e2=5453' 'uram288=752' 'mlp_kernel_dsp48e2=3072'
        'history2_repack_instances=2' 'generic_repack_instances=0'
        'projection_weight_capture_ok=1'
        'pblock_count=19' 'pblock_overlap=0'
        'pblock_dsp_coverage=5453' 'pblock_uram_coverage=752'
        'center_extra_dsp48e2=149'
        'moved_projection_frontend_dsp48e2=64'
        'center_residual_dsp48e2=85'
        'projected_slr_dsp48e2=2198 1173 2082'
        'projected_slr_uram288=224 224 304'
        'region0_target_slr=0' 'region3_target_slr=2'
        'pre_place_drc_errors=0' 'implementation_commands_run=0'
        'checkpoint_written=0' 'route_eligible=0')
    for literal in "${expected[@]}"; do
        [[ "$(grep -Fxc -- "$literal" "$summary" || true)" -eq 1 ]] || {
            printf 'P4 summary gate failed: %s\n' "$literal" >&2
            audit_gate_rc=1
        }
    done
fi

final_rc=0
status=PASS
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"; status=FAIL
elif [[ "$sha_rc" -ne 0 || "$manifest_match" -ne 1 ||
        "$audit_gate_rc" -ne 0 ]]; then
    final_rc=1; status=FAIL
fi
printf '%s\n' "status=$status" "final_exit_code=$final_rc" \
    "vivado_exit_code=$vivado_rc" "input_sha_recheck_exit_code=$sha_rc" \
    "input_manifest_sha_match=$manifest_match" \
    "audit_gate_exit_code=$audit_gate_rc" \
    'checkpoint_written=0' 'implementation_commands_run=0' \
    > "$HAP_PREPLACE_AUDIT_DIR/launcher_status.txt"
mapfile -d '' outputs < <(find "$HAP_PREPLACE_AUDIT_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
sha256sum -- "${outputs[@]}" > "$HAP_PREPLACE_AUDIT_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict \
    "$HAP_PREPLACE_AUDIT_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'P4 pre-place audit failed: %s\n' "$HAP_PREPLACE_AUDIT_DIR" >&2
    printf '%s\n' "$HAP_PREPLACE_AUDIT_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_PREPLACE_AUDIT_DIR"
