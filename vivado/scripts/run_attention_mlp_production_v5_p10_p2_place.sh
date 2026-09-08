#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
PLACE_TCL="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
IO_AUDIT="$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p2_place.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s V5_POST_OPT_DCP V5_P2_PREPLACE_AUDIT_DIR\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P10 production placement requires HAP_JOBS=32\n' >&2
    exit 2
}
export HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-AltSpreadLogic_high}"
[[ "$HAP_PLACE_DIRECTIVE" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || {
    printf 'invalid P10 place directive: %q\n' "$HAP_PLACE_DIRECTIVE" >&2
    exit 2
}
export HAP_MAX_POST_PLACE_LEVEL5_WINDOWS="${HAP_MAX_POST_PLACE_LEVEL5_WINDOWS:-1}"
if ! [[ "$HAP_MAX_POST_PLACE_LEVEL5_WINDOWS" =~ ^[0-9]+$ ]] ||
        (( HAP_MAX_POST_PLACE_LEVEL5_WINDOWS > 100 )); then
    printf 'P10 max Level-5 window count must be in 0..100\n' >&2
    exit 2
fi

require_free_batch_slot() {
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -ne 0 ]]; then
        printf 'another batch Vivado is active; P10 placement not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        exit 75
    fi
}

export HAP_DCP="$(readlink -e -- "$1")"
preplace_dir="$(readlink -e -- "$2")"
[[ -f "$HAP_DCP" && -d "$preplace_dir" ]] || {
    printf 'missing P10 post-opt DCP or pre-place directory\n' >&2
    exit 2
}
export HAP_P10_PREPLACE_OUTPUT_SHA="$preplace_dir/OUTPUT_SHA256SUMS"
preplace_summary="$preplace_dir/summary.txt"
preplace_status="$preplace_dir/launcher_status.txt"
preplace_input_sha="$preplace_dir/INPUT_SHA256SUMS"
for input in "$HAP_P10_PREPLACE_OUTPUT_SHA" "$preplace_summary" \
        "$preplace_status" "$preplace_input_sha" "$PLACE_TCL" \
        "$SELECTOR_LIB" "$GEOMETRY_LIB" "$IO_AUDIT" "$CLOCK_XDC" \
        "$LAUNCHER"; do
    [[ -s "$input" ]] || {
        printf 'missing P10 input evidence: %s\n' "$input" >&2
        exit 2
    }
done
(cd / && sha256sum -c --strict "$HAP_P10_PREPLACE_OUTPUT_SHA") >/dev/null
for literal in \
    status=V5_PRE_PLACE_CONTRACT_AUDIT_PASS \
    contract_variant=P2_COHORT16_COL2_12_2 \
    dsp48e2=5453 uram288=752 mlp_kernel_dsp48e2=3072 \
    metadata_leaf_instances=4 metadata_local_wr_en_ff=4 \
    metadata_local_wr_addr_ff=70 metadata_local_wr_data_ff=896 \
    metadata_local_write_protected_ff=970 \
    mlp_capture_leaf_instances=1632 mlp_capture_leaf_lut1=1632 \
    branch0_capture_leaf_instances=816 branch1_capture_leaf_instances=816 \
    branch0_capture_leaf_lut1=816 branch1_capture_leaf_lut1=816 \
    compute_clock_buffer_none_ok=1 geometry_pblock_prefix=p3_ \
    canonical_pblock_count=11 geometry_pblock_count=10 \
    geometry_region0_input_primitives=3136 \
    geometry_region3_input_primitives=2112 \
    geometry_owner_region2_weight_primitives=2048 \
    geometry_region0_input_ok=1 geometry_region3_input_ok=1 \
    geometry_owner_region2_weight_ok=1 \
    pblock_count=21 pblock_dsp_coverage=5453 pblock_uram_coverage=752 \
    pre_place_drc_errors=0 checkpoint_written=0 \
    implementation_commands_run=0; do
    grep -Fqx -- "$literal" "$preplace_summary"
done
for literal in status=PASS final_exit_code=0 vivado_exit_code=0 \
        input_sha_recheck_exit_code=0 input_manifest_sha_match=1 \
        audit_gate_exit_code=0 checkpoint_written=0 \
        implementation_commands_run=0; do
    grep -Fqx -- "$literal" "$preplace_status"
done
grep -Fqx -- "$(sha256sum -- "$HAP_DCP")" "$preplace_input_sha"
require_free_batch_slot

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_PLACE_DIR:-$ROOT/vivado/reports/production_v5_p10_p2_place_$STAMP}"
export HAP_PLACE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_PLACE_DIR" ]] || {
    printf 'P10 place evidence directory exists: %s\n' "$HAP_PLACE_DIR" >&2
    exit 2
}
mkdir "$HAP_PLACE_DIR"
export HAP_PLACE_INPUT_SHA="$HAP_PLACE_DIR/INPUT_SHA256SUMS"
export HAP_PLACE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_PLACE_GEOMETRY_LIB="$GEOMETRY_LIB"
export HAP_PLACE_LAUNCHER="$LAUNCHER"
export HAP_PLACE_IO_AUDIT="$IO_AUDIT"
export HAP_PLACE_CLOCK_XDC="$CLOCK_XDC"
printf '%s\n' "$HAP_DCP" "$SELECTOR_LIB" "$PLACE_TCL" "$LAUNCHER" \
    "$GEOMETRY_LIB" "$CLOCK_XDC" "$IO_AUDIT" \
    "$HAP_P10_PREPLACE_OUTPUT_SHA" \
    > "$HAP_PLACE_DIR/INPUT_FILES"
sha256sum -- "$HAP_DCP" "$SELECTOR_LIB" "$PLACE_TCL" "$LAUNCHER" \
    "$GEOMETRY_LIB" "$CLOCK_XDC" "$IO_AUDIT" \
    "$HAP_P10_PREPLACE_OUTPUT_SHA" \
    > "$HAP_PLACE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_PLACE_INPUT_MANIFEST_SHA256
HAP_PLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')"
export HAP_P10_PREPLACE_OUTPUT_SHA256
HAP_P10_PREPLACE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P10_PREPLACE_OUTPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") \
    > "$HAP_PLACE_DIR/input_sha_precheck.txt" 2>&1

vivado_exit_code=255
vivado_invoked=0
input_sha_recheck_exit_code=125
input_manifest_sha_match=0
preplace_output_sha_recheck_exit_code=125
place_gate_exit_code=125

write_launcher_status() {
    local final_rc="$1" status=FAIL acceptance=0 route_eligible=0 checkpoint=0
    if [[ "$final_rc" -eq 0 ]]; then
        status=PASS
        acceptance=1
        route_eligible=1
        checkpoint=1
    fi
    printf '%s\n' \
        "status=$status" \
        'flow_mode=accept' \
        "acceptance_evidence=$acceptance" \
        "route_eligible=$route_eligible" \
        "final_exit_code=$final_rc" \
        "vivado_exit_code=$vivado_exit_code" \
        "input_sha_recheck_exit_code=$input_sha_recheck_exit_code" \
        "input_manifest_sha_match=$input_manifest_sha_match" \
        "preplace_output_sha_recheck_exit_code=$preplace_output_sha_recheck_exit_code" \
        "place_gate_exit_code=$place_gate_exit_code" \
        "checkpoint_written=$checkpoint" \
        "vivado_invoked=$vivado_invoked" \
        'implementation_commands_requested=1' \
        'bitstream_generated=0' \
        > "$HAP_PLACE_DIR/launcher_status.txt"
}

archive_outputs() {
    local -a outputs=() current=() manifested=()
    local index
    mapfile -d '' outputs < <(find "$HAP_PLACE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || return 1
    sha256sum -- "${outputs[@]}" > "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS" >/dev/null)
    mapfile -d '' current < <(find "$HAP_PLACE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    mapfile -t manifested < <(awk \
        '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
        "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS" | sort)
    [[ "${#current[@]}" -eq "${#manifested[@]}" ]] || return 1
    for index in "${!current[@]}"; do
        [[ "${current[$index]}" == "${manifested[$index]}" ]] || return 1
    done
}

exit_archive() {
    local rc="$?"
    trap - EXIT
    write_launcher_status "$rc" || rc=96
    if ! archive_outputs; then
        [[ "$rc" -ne 0 ]] || rc=97
        write_launcher_status "$rc" || true
        archive_outputs || true
    fi
    exit "$rc"
}
trap exit_archive EXIT

require_free_batch_slot
cd "$ROOT"
set +e
vivado_invoked=1
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl \
    -log "$HAP_PLACE_DIR/vivado.log" \
    -journal "$HAP_PLACE_DIR/vivado.jou"
vivado_exit_code=$?
set -e

set +e
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") \
    > "$HAP_PLACE_DIR/input_sha_postcheck.txt" 2>&1
input_sha_recheck_exit_code=$?
(cd / && sha256sum -c --strict "$HAP_P10_PREPLACE_OUTPUT_SHA") \
    > "$HAP_PLACE_DIR/preplace_output_sha_postcheck.txt" 2>&1
preplace_output_sha_recheck_exit_code=$?
actual_input_manifest_sha="$(sha256sum -- \
    "$HAP_PLACE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
if [[ "$manifest_rc" -eq 0 && \
      "$actual_input_manifest_sha" == "$HAP_PLACE_INPUT_MANIFEST_SHA256" ]]; then
    input_manifest_sha_match=1
fi

place_gate_exit_code=0
if [[ "$vivado_exit_code" -ne 0 || "$input_sha_recheck_exit_code" -ne 0 ||
      "$preplace_output_sha_recheck_exit_code" -ne 0 ||
      "$input_manifest_sha_match" -ne 1 ]]; then
    place_gate_exit_code=1
fi
summary="$HAP_PLACE_DIR/summary.txt"
for required in "$summary" "$HAP_PLACE_DIR/post_place.dcp" \
        "$HAP_PLACE_DIR/selectors_post_place.txt" \
        "$HAP_PLACE_DIR/pblocks_post_place.txt" \
        "$HAP_PLACE_DIR/post_place_fast_gate.txt" \
        "$HAP_PLACE_DIR/timing_post_place.rpt" \
        "$HAP_PLACE_DIR/drc_post_place.rpt" \
        "$HAP_PLACE_DIR/cdc_post_place.rpt" \
        "$HAP_PLACE_DIR/exceptions_coverage_post_place.rpt"; do
    [[ -s "$required" ]] || place_gate_exit_code=1
done
if [[ "$place_gate_exit_code" -eq 0 ]]; then
    for literal in \
        status=V5_PRODUCTION_PLACE_PASS stage=V5_P10_P2_POST_PLACE_ACCEPT \
        flow_mode=accept acceptance_evidence=1 route_eligible=1 \
        checkpoint_written=1 input_manifest_entries=8 provenance_verified=1 \
        pre_place_verified=1 pblock_contract_variant=P2_COHORT16_COL2_12_2 \
        place_directive="$HAP_PLACE_DIRECTIVE" jobs=32 core_clock_mhz=100 \
        ddr0_clock_mhz=300 ddr1_clock_mhz=300 \
        dsp48e2=5453 uram288=752 mlp_kernel_dsp48e2=3072 \
        history2_repack_instances=2 generic_repack_instances=0 \
        compute_clock_buffer_none_ok=1 geometry_pblock_prefix=p3_ \
        canonical_pblock_count=11 geometry_pblock_count=10 \
        geometry_region0_input_primitives=3136 \
        geometry_region3_input_primitives=2112 \
        geometry_owner_region2_weight_primitives=2048 \
        geometry_region0_input_ok=1 geometry_region3_input_ok=1 \
        geometry_owner_region2_weight_ok=1 geometry_placement_ok=1 \
        metadata_leaf_instances=4 metadata_local_wr_en_ff=4 \
        metadata_local_wr_addr_ff=70 metadata_local_wr_data_ff=896 \
        metadata_local_write_protected_ff=970 \
        metadata_local_write_leaf_counts='243 243 242 242' \
        metadata_local_write_leaf_slr_counts='{243 0 0} {0 0 243} {0 242 0} {0 242 0}' \
        metadata_local_write_wrong_slr=0 \
        mlp_capture_leaf_instances=1632 mlp_capture_leaf_lut1=1632 \
        mlp_capture_leaf_branch_instances='816 816' \
        mlp_capture_leaf_branch_lut1='816 816' \
        mlp_capture_leaf_branch_slr_counts='{816 0 0} {0 0 816}' \
        mlp_capture_leaf_wrong_slr=0 \
        moved_lanes_slr0=16 center_lanes_slr1=96 moved_lanes_slr2=16 \
        planned_slr0_dsp48e2=1862 planned_slr1_dsp48e2=1781 \
        planned_slr2_dsp48e2=1810 slr0_dsp48e2=1862 \
        slr1_dsp48e2=1781 slr2_dsp48e2=1810 \
        slr0_uram288=224 slr1_uram288=224 slr2_uram288=304 \
        unplaced_primitives=0 wrong_slr_primitives=0 \
        pre_place_drc_errors=0 post_place_drc_errors=0 \
        false_path_exception_rows=0 datapath_only_exception_rows=0 \
        timing_coverage_ok=1 cdc_critical=0 data_bufg=0 \
        congestion_level6_or_higher_windows=0 resource_ok=1 structure_ok=1 \
        placement_ok=1 uram_distribution_ok=1 \
        pre_place_pblock_contract_ok=1 post_place_live_rediscovery_ok=1 \
        post_place_pblock_contract_ok=1 post_place_pblock_count=21 \
        post_place_canonical_pblock_count=11 \
        post_place_geometry_pblock_count=10 \
        post_place_pblock_dsp_coverage=5453 \
        post_place_pblock_uram_coverage=752 \
        post_place_pblock_wrong_slr=0 optimizer_extras_ok=1 \
        fast_gate_ok=1 policy_ok=1 level5_screen_ok=1 \
        level6_congestion_ok=1; do
        grep -Fqx -- "$literal" "$summary" || place_gate_exit_code=1
    done
    for literal in resource_ok=1 structure_ok=1 placement_ok=1 \
            optimizer_extras_ok=1 pre_place_drc_errors=0 data_bufg=0 \
            level6_or_higher_windows=0 fast_gate_ok=1; do
        grep -Fqx -- "$literal" \
            "$HAP_PLACE_DIR/post_place_fast_gate.txt" || place_gate_exit_code=1
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_PLACE_DIR/vivado.log"; then
        place_gate_exit_code=1
    fi
fi
if [[ "$place_gate_exit_code" -ne 0 ]]; then
    printf 'P10 production placement failed; evidence retained in %s\n' \
        "$HAP_PLACE_DIR" >&2
    exit 1
fi
printf 'P10_PRODUCTION_PLACE_PASS\n%s\n' "$HAP_PLACE_DIR"
