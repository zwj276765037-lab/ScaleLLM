#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
AUDIT_TCL="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_pre_place_contract.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_pre_place_contract_audit.sh"

[[ $# -eq 1 ]] || { printf 'usage: %s V5_POST_OPT_DCP\n' "$0" >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_DCP="$(readlink -f -- "$1")"
for input in "$HAP_DCP" "$AUDIT_TCL" "$SELECTOR_LIB" "$GEOMETRY_LIB" \
        "$LAUNCHER"; do
    [[ -s "$input" ]] || { printf 'missing pre-place input: %s\n' "$input" >&2; exit 2; }
    [[ "$input" != *$'\n'* ]] || {
        printf 'newline is forbidden in pre-place input path: %q\n' "$input" >&2
        exit 2
    }
done
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; pre-place audit not started\n' >&2
    exit 75
fi

# The in-memory pblock mutation is the only permitted design mutation.  No
# implementation command, timing exception, checkpoint, or bitstream writer
# is legal in this read-only evidence flow.
audit_code="$(sed -E '/^[[:space:]]*#/d' "$AUDIT_TCL")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|set_false_path|set_max_delay|set_min_delay|write_checkpoint|write_bitstream|write_cfgmem|eval|uplevel)([^[:alnum:]_]|$)' \
    <<<"$audit_code"; then
    printf 'pre-place audit Tcl contains a forbidden command\n' >&2
    exit 2
fi
geometry_code="$(sed -E '/^[[:space:]]*#/d' "$GEOMETRY_LIB")"
if grep -Eq \
    '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|set_false_path|set_max_delay|set_min_delay|write_checkpoint|write_bitstream|write_cfgmem)([^[:alnum:]_]|$)' \
    <<<"$geometry_code"; then
    printf 'pre-place geometry library contains a forbidden command\n' >&2
    exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_PREPLACE_AUDIT_DIR:-$(dirname "$HAP_DCP")/v5_pre_place_contract_audit_$STAMP}"
export HAP_PREPLACE_AUDIT_DIR="$(readlink -m -- "$requested")"
[[ "$HAP_PREPLACE_AUDIT_DIR" != *$'\n'* ]] || {
    printf 'newline is forbidden in pre-place output path: %q\n' \
        "$HAP_PREPLACE_AUDIT_DIR" >&2
    exit 2
}
[[ ! -e "$HAP_PREPLACE_AUDIT_DIR" ]] || {
    printf 'pre-place audit directory exists: %s\n' "$HAP_PREPLACE_AUDIT_DIR" >&2
    exit 2
}
mkdir "$HAP_PREPLACE_AUDIT_DIR"
export HAP_PREPLACE_INPUT_SHA="$HAP_PREPLACE_AUDIT_DIR/INPUT_SHA256SUMS"
export HAP_PREPLACE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_PREPLACE_GEOMETRY_LIB="$GEOMETRY_LIB"
export HAP_PREPLACE_LAUNCHER="$LAUNCHER"
printf '%s\n' "$HAP_DCP" "$SELECTOR_LIB" "$GEOMETRY_LIB" "$AUDIT_TCL" \
    "$LAUNCHER" \
    > "$HAP_PREPLACE_AUDIT_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$SELECTOR_LIB" "$GEOMETRY_LIB" "$AUDIT_TCL" \
    "$LAUNCHER" \
    > "$HAP_PREPLACE_INPUT_SHA"
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
    -source vivado/scripts/audit_attention_mlp_production_v5_pre_place_contract.tcl \
    -log "$HAP_PREPLACE_AUDIT_DIR/vivado.log" \
    -journal "$HAP_PREPLACE_AUDIT_DIR/vivado.jou"
vivado_rc=$?
(cd / && sha256sum -c --strict "$HAP_PREPLACE_INPUT_SHA") \
    > "$HAP_PREPLACE_AUDIT_DIR/input_sha_postcheck.txt" 2>&1
sha_rc=$?
actual_manifest_sha="$(sha256sum -- "$HAP_PREPLACE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_sha_rc=$?
set -e
manifest_sha_match=0
if [[ "$manifest_sha_rc" -eq 0 && \
      "$actual_manifest_sha" == "$HAP_PREPLACE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_sha_match=1
fi

for vivado_artifact in vivado.log vivado.jou; do
    if [[ ! -e "$HAP_PREPLACE_AUDIT_DIR/$vivado_artifact" ]]; then
        printf 'launcher_note=Vivado did not create %s\n' "$vivado_artifact" \
            > "$HAP_PREPLACE_AUDIT_DIR/$vivado_artifact"
    fi
done
summary="$HAP_PREPLACE_AUDIT_DIR/summary.txt"
audit_gate_rc=125
if [[ "$vivado_rc" -eq 0 && "$sha_rc" -eq 0 && \
      "$manifest_sha_match" -eq 1 && -s "$summary" ]]; then
    set +e
    audit_gate_rc=0
    for required in summary.txt selectors.txt pblocks.txt attention_geometry.txt \
            drc_pre_place.rpt INPUT_FILES \
            INPUT_SHA256SUMS input_sha_precheck.txt input_sha_postcheck.txt \
            vivado.log vivado.jou; do
        if [[ ! -s "$HAP_PREPLACE_AUDIT_DIR/$required" ]]; then
            printf 'missing or empty pre-place audit output: %s\n' \
                "$required" >&2
            audit_gate_rc=1
        fi
    done
    awk -F= 'NF < 2 || seen[$1]++ {exit 1} END {exit 0}' "$summary" || \
        audit_gate_rc=1
    for literal in \
        'status=V5_PRE_PLACE_CONTRACT_AUDIT_PASS' \
        'evidence_class=V5_PRE_PLACE_READ_ONLY_CONTRACT' \
        "input_dcp=$HAP_DCP" \
        "input_dcp_sha256=$HAP_EXPECTED_DCP_SHA256" \
        "input_manifest_sha256=$HAP_PREPLACE_INPUT_MANIFEST_SHA256" \
        'input_manifest_entries=5' 'provenance_verified=1' \
        'contract_variant=P2_COHORT16_COL2_12_2' 'dsp48e2=5453' 'uram288=752' \
        'mlp_kernel_dsp48e2=3072' 'swiglu_structure=1/2/1/0/4/2' \
        'raw_weight_push_loads=37' \
        'weight_data_capture_contract=32x256' \
        'weight_data_capture_nets=32' \
        'weight_data_capture_loads=256/256' \
        'weight_meta_capture_contract=2x256' \
        'weight_meta_capture_nets=2' \
        'weight_meta_capture_loads=256/256' \
        'weight_group_capture_contract=2x7' \
        'weight_group_capture_nets=2' \
        'weight_group_capture_loads=7/7' \
        'projection_weight_capture_ok=1' \
        'compact_input_frontend_instances=1' 'down_elastic2_instances=2' \
        'mlp_local_clear_ff=2' 'mlp_local_clear_protected_ff=2' \
        'branch0_local_clear_ff=1' 'branch1_local_clear_ff=1' \
        'swiglu_local_clear_ff=8' \
        'swiglu_local_clear_protected_ff=8' \
        'swiglu_control_clear_ff=1' 'swiglu_hadamard_clear_ff=1' \
        'swiglu_quantizer_clear_ff=4' 'swiglu_row_clear_ff=2' \
        'swiglu_direct_clear_bypass_state=0' \
        'mlp_central_clear_ff=1' \
        'mlp_central_clear_branch_endpoints=2' \
        'mlp_central_clear_direct_branch_state=0' \
        'metadata_leaf_instances=4' \
        'metadata_local_wr_en_ff=4' \
        'metadata_local_wr_addr_ff=70' \
        'metadata_local_wr_data_ff=896' \
        'metadata_local_write_protected_ff=970' \
        'mlp_capture_leaf_instances=1632' \
        'mlp_capture_leaf_lut1=1632' \
        'branch0_capture_leaf_instances=816' \
        'branch1_capture_leaf_instances=816' \
        'branch0_capture_leaf_lut1=816' \
        'branch1_capture_leaf_lut1=816' \
        'compute_clock_buffer_none_ok=1' \
        'geometry_pblock_prefix=p3_' \
        'canonical_pblock_count=11' 'geometry_pblock_count=10' \
        'geometry_region0_input_primitives=3136' \
        'geometry_region3_input_primitives=2112' \
        'geometry_owner_region2_weight_primitives=2048' \
        'geometry_region0_input_ok=1' 'geometry_region3_input_ok=1' \
        'geometry_owner_region2_weight_ok=1' \
        'outer0_dsp48e2=1538' 'outer2_dsp48e2=1538' \
        'outer0_ramb36e2=102' 'outer2_ramb36e2=102' \
        'moved_lanes_slr0=16' 'center_lanes_slr1=96' \
        'moved_lanes_slr2=16' 'planned_slr0_dsp48e2=1862' \
        'planned_slr1_dsp48e2=1781' 'planned_slr2_dsp48e2=1810' \
        'pblock_count=21' 'pblock_dsp_coverage=5453' \
        'pblock_uram_coverage=752' 'pblock_overlap=0' \
        'pre_place_drc_errors=0' \
        'checkpoint_written=0' 'implementation_commands_run=0'; do
        if [[ "$(grep -Fxc -- "$literal" "$summary" 2>/dev/null || true)" -ne 1 ]]; then
            printf 'pre-place summary gate failed: %s\n' "$literal" >&2
            audit_gate_rc=1
        fi
    done
    set -e
fi

final_rc=0
final_status=PASS
if [[ "$vivado_rc" -ne 0 ]]; then
    final_rc="$vivado_rc"
    final_status=FAIL
elif [[ "$sha_rc" -ne 0 || "$manifest_sha_match" -ne 1 || \
        "$audit_gate_rc" -ne 0 ]]; then
    final_rc=1
    final_status=FAIL
fi
printf '%s\n' \
    "status=$final_status" \
    "final_exit_code=$final_rc" \
    "vivado_exit_code=$vivado_rc" \
    "input_sha_recheck_exit_code=$sha_rc" \
    "input_manifest_sha_match=$manifest_sha_match" \
    "audit_gate_exit_code=$audit_gate_rc" \
    'checkpoint_written=0' \
    'implementation_commands_run=0' \
    > "$HAP_PREPLACE_AUDIT_DIR/launcher_status.txt"

mapfile -d '' outputs < <(find "$HAP_PREPLACE_AUDIT_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
[[ "${#outputs[@]}" -ne 0 ]] || {
    printf 'pre-place audit produced no hashable evidence\n' >&2
    exit 1
}
sha256sum -- "${outputs[@]}" > "$HAP_PREPLACE_AUDIT_DIR/OUTPUT_SHA256SUMS"
(cd / && sha256sum -c --strict \
    "$HAP_PREPLACE_AUDIT_DIR/OUTPUT_SHA256SUMS")
if [[ "$final_rc" -ne 0 ]]; then
    printf 'V5 pre-place audit failed; evidence: %s\n' \
        "$HAP_PREPLACE_AUDIT_DIR" >&2
    printf '%s\n' "$HAP_PREPLACE_AUDIT_DIR"
    exit "$final_rc"
fi
cat "$summary"
printf '%s\n' "$HAP_PREPLACE_AUDIT_DIR"
