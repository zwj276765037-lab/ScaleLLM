#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
PLACE_TCL="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p6.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P6_LIB="$ROOT/vivado/scripts/v5_production_p6_postprocess_partition_floorplan.tcl"
P10_PROC_LIB="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p2.tcl"
IO_AUDIT="$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p6_place.sh"

[[ $# -eq 2 ]] || {
    printf 'usage: %s V5_POST_OPT_DCP P6_PREPLACE_OUTPUT_SHA256SUMS\n' "$0" >&2
    exit 2
}
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P6 production placement requires HAP_JOBS=32\n' >&2
    exit 2
}
export HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-AltSpreadLogic_high}"
[[ "$HAP_PLACE_DIRECTIVE" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || {
    printf 'invalid P6 place directive: %q\n' "$HAP_PLACE_DIRECTIVE" >&2
    exit 2
}
export HAP_MAX_POST_PLACE_LEVEL5_WINDOWS="${HAP_MAX_POST_PLACE_LEVEL5_WINDOWS:-1}"
if ! [[ "$HAP_MAX_POST_PLACE_LEVEL5_WINDOWS" =~ ^[0-9]+$ ]] ||
        (( HAP_MAX_POST_PLACE_LEVEL5_WINDOWS > 100 )); then
    printf 'P6 max Level-5 window count must be in 0..100\n' >&2
    exit 2
fi

require_free_batch_slot() {
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -ne 0 ]]; then
        printf 'another batch Vivado is active; P6 placement not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        exit 75
    fi
}

export HAP_DCP="$(readlink -e -- "$1")"
export HAP_P6_PREPLACE_OUTPUT_SHA="$(readlink -e -- "$2")"
inputs=("$HAP_DCP" "$SELECTOR_LIB" "$GEOMETRY_LIB" "$P5_LIB"
    "$P6_LIB" "$P10_PROC_LIB" "$PLACE_TCL" "$LAUNCHER" "$CLOCK_XDC"
    "$IO_AUDIT" "$HAP_P6_PREPLACE_OUTPUT_SHA")
for input in "${inputs[@]}"; do
    [[ -s "$input" ]] || { printf 'missing P6 input: %s\n' "$input" >&2; exit 2; }
done
require_free_batch_slot

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_PLACE_DIR:-$ROOT/vivado/reports/production_v5_p10_p6_place_$STAMP}"
export HAP_PLACE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_PLACE_DIR" ]] || {
    printf 'P6 place evidence directory exists: %s\n' "$HAP_PLACE_DIR" >&2
    exit 2
}
mkdir "$HAP_PLACE_DIR"
export HAP_PLACE_INPUT_SHA="$HAP_PLACE_DIR/INPUT_SHA256SUMS"
export HAP_PLACE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_PLACE_GEOMETRY_LIB="$GEOMETRY_LIB"
export HAP_PLACE_P5_LIB="$P5_LIB"
export HAP_PLACE_P6_LIB="$P6_LIB"
export HAP_PLACE_P10_PROC_LIB="$P10_PROC_LIB"
export HAP_PLACE_LAUNCHER="$LAUNCHER"
export HAP_PLACE_IO_AUDIT="$IO_AUDIT"
export HAP_PLACE_CLOCK_XDC="$CLOCK_XDC"
printf '%s\n' "${inputs[@]}" > "$HAP_PLACE_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_PLACE_INPUT_SHA"
export HAP_EXPECTED_DCP_SHA256
HAP_EXPECTED_DCP_SHA256="$(sha256sum -- "$HAP_DCP" | awk '{print $1}')"
export HAP_PLACE_INPUT_MANIFEST_SHA256
HAP_PLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')"
export HAP_P6_PREPLACE_OUTPUT_SHA256
HAP_P6_PREPLACE_OUTPUT_SHA256="$(sha256sum -- \
    "$HAP_P6_PREPLACE_OUTPUT_SHA" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") \
    > "$HAP_PLACE_DIR/input_sha_precheck.txt" 2>&1

vivado_exit_code=255
input_sha_recheck_exit_code=125
manifest_sha_match=0
place_gate_exit_code=125
final_rc=1

write_launcher_status() {
    local status=FAIL acceptance=0 route_eligible=0 checkpoint=0
    if [[ "$final_rc" -eq 0 ]]; then
        status=PASS; acceptance=1; route_eligible=1; checkpoint=1
    fi
    printf '%s\n' "status=$status" 'flow_mode=accept' \
        "acceptance_evidence=$acceptance" "route_eligible=$route_eligible" \
        "final_exit_code=$final_rc" "vivado_exit_code=$vivado_exit_code" \
        "input_sha_recheck_exit_code=$input_sha_recheck_exit_code" \
        "input_manifest_sha_match=$manifest_sha_match" \
        "place_gate_exit_code=$place_gate_exit_code" \
        "checkpoint_written=$checkpoint" 'implementation_commands_requested=1' \
        'bitstream_generated=0' > "$HAP_PLACE_DIR/launcher_status.txt"
}

archive_outputs() {
    mapfile -d '' outputs < <(find "$HAP_PLACE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || return 1
    sha256sum -- "${outputs[@]}" > "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_PLACE_DIR/OUTPUT_SHA256SUMS" >/dev/null)
}

finish() {
    local trap_rc="$?"
    trap - EXIT
    [[ "$trap_rc" -eq 0 ]] || final_rc="$trap_rc"
    write_launcher_status || final_rc=96
    if ! archive_outputs; then
        final_rc=97
        write_launcher_status || true
        archive_outputs || true
    fi
    exit "$final_rc"
}
trap finish EXIT

require_free_batch_slot
cd "$ROOT"
set +e
"$VIVADO" -mode batch -notrace \
    -source "$PLACE_TCL" \
    -log "$HAP_PLACE_DIR/vivado.log" \
    -journal "$HAP_PLACE_DIR/vivado.jou"
vivado_exit_code=$?
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") \
    > "$HAP_PLACE_DIR/input_sha_postcheck.txt" 2>&1
input_sha_recheck_exit_code=$?
actual_manifest_sha="$(sha256sum -- "$HAP_PLACE_INPUT_SHA" 2>/dev/null | awk '{print $1}')"
manifest_rc=$?
set -e
if [[ "$manifest_rc" -eq 0 &&
      "$actual_manifest_sha" == "$HAP_PLACE_INPUT_MANIFEST_SHA256" ]]; then
    manifest_sha_match=1
fi

place_gate_exit_code=0
if [[ "$vivado_exit_code" -ne 0 || "$input_sha_recheck_exit_code" -ne 0 ||
      "$manifest_sha_match" -ne 1 ]]; then
    place_gate_exit_code=1
fi
required=(summary.txt post_place.dcp pre_place_gate.txt
    post_place_fast_gate.txt selectors_post_place.txt
    attention_geometry_post_place.txt attention_geometry_placement.txt
    base_pblocks_post_place.txt p5_input_plan_post_place.txt
    p5_input_pblocks_post_place.txt p6_postprocess_plan_post_place.txt
    p6_postprocess_pblocks_post_place.txt timing_post_place.rpt
    drc_pre_place.rpt drc_post_place.rpt cdc_post_place.rpt
    exceptions_coverage_post_place.rpt)
for file in "${required[@]}"; do
    [[ -s "$HAP_PLACE_DIR/$file" ]] || place_gate_exit_code=1
done
summary="$HAP_PLACE_DIR/summary.txt"
if [[ "$place_gate_exit_code" -eq 0 ]]; then
    expected=(
        'status=V5_P10_P6_PRODUCTION_PLACE_PASS'
        'stage=V5_P10_P6_POST_PLACE_ACCEPT' 'flow_mode=accept'
        'acceptance_evidence=1' 'route_eligible=1' 'checkpoint_written=1'
        'input_manifest_entries=11' 'provenance_verified=1'
        'pre_place_verified=1' 'contract_variant=P2_COHORT16_COL2_12_2'
        'p5_contract=P5_INPUT_HALF_LOCAL_8_8'
        'p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'
        "place_directive=$HAP_PLACE_DIRECTIVE" 'jobs=32'
        'core_clock_mhz=100' 'ddr0_clock_mhz=300' 'ddr1_clock_mhz=300'
        'dsp48e2=5453' 'uram288=752' 'mlp_kernel_dsp48e2=3072'
        'history2_repack_instances=2' 'generic_repack_instances=0'
        'projection_weight_capture_ok=1' 'canonical_pblock_count=11'
        'geometry_pblock_count=10' 'p5_added_pblock_count=2'
        'p6_added_pblock_count=2' 'total_pblock_count=25'
        'slr0_dsp48e2=1862'
        'slr1_dsp48e2=1781' 'slr2_dsp48e2=1810'
        'slr0_uram288=224' 'slr1_uram288=224' 'slr2_uram288=304'
        'unplaced_primitives=0' 'wrong_slr_primitives=0'
        'p5_center_wrong_slr=0' 'p5_outer_wrong_slr=0'
        'p6_center_wrong_slr=0' 'p6_outer_wrong_slr=0'
        'p6_slr0_row_primitives=10696' 'p6_center_row_primitives=21392'
        'p6_slr2_row_primitives=10696'
        'compute_clock_buffer_none_missing_after_reapply=0'
        'pre_place_drc_errors=0' 'post_place_drc_errors=0'
        'false_path_exception_rows=0' 'datapath_only_exception_rows=0'
        'timing_coverage_ok=1' 'cdc_critical=0' 'data_bufg=0'
        'congestion_level6_or_higher_windows=0' 'resource_ok=1'
        'structure_ok=1' 'placement_ok=1' 'optimizer_extras_ok=1'
        'fast_gate_ok=1' 'policy_ok=1' 'level5_screen_ok=1'
        'level6_congestion_ok=1')
    for literal in "${expected[@]}"; do
        [[ "$(grep -Fxc -- "$literal" "$summary" || true)" -eq 1 ]] || {
            printf 'P6 summary gate failed: %s\n' "$literal" >&2
            place_gate_exit_code=1
        }
    done
    if grep -Eq '^(ERROR|FATAL):' "$HAP_PLACE_DIR/vivado.log"; then
        place_gate_exit_code=1
    fi
fi
if [[ "$place_gate_exit_code" -ne 0 ]]; then
    printf 'P6 production placement failed; evidence: %s\n' \
        "$HAP_PLACE_DIR" >&2
    exit 1
fi
final_rc=0
printf 'P6_PRODUCTION_PLACE_PASS\n%s\n' "$HAP_PLACE_DIR"
