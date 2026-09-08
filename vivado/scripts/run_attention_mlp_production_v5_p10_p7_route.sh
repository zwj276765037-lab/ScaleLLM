#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
ROUTE_TCL="$ROOT/vivado/scripts/resume_attention_mlp_production_v5_p10_p7_route.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p7_route.sh"
HELPER_LIB="$ROOT/vivado/scripts/resume_attention_mlp_production_v5_route.tcl"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P6_LIB="$ROOT/vivado/scripts/v5_production_p6_postprocess_partition_floorplan.tcl"
IO_AUDIT="$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"

[[ $# -eq 1 ]] || { printf 'usage: %s P7_PLACE_ARTIFACT_DIR\n' "$0" >&2; exit 2; }
[[ -x "$VIVADO" ]] || { printf 'missing Vivado: %s\n' "$VIVADO" >&2; exit 2; }
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" == 32 ]] || {
    printf 'P7 production route requires HAP_JOBS=32\n' >&2
    exit 2
}
export HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE="${HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
export HAP_ROUTE_DIRECTIVE="${HAP_ROUTE_DIRECTIVE:-AggressiveExplore}"
export HAP_POST_ROUTE_PHYSOPT_DIRECTIVE="${HAP_POST_ROUTE_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
for value in "$HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE" "$HAP_ROUTE_DIRECTIVE" \
        "$HAP_POST_ROUTE_PHYSOPT_DIRECTIVE"; do
    [[ "$value" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]] || {
        printf 'invalid P7 route directive: %q\n' "$value" >&2
        exit 2
    }
done

require_free_batch_slot() {
    mapfile -t active_batch < <(pgrep -af \
        '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
    if [[ "${#active_batch[@]}" -ne 0 ]]; then
        printf 'another batch Vivado is active; P7 route not started:\n' >&2
        printf '  %s\n' "${active_batch[@]}" >&2
        exit 75
    fi
}

place_dir="$(readlink -e -- "$1")"
[[ -d "$place_dir" ]] || { printf 'missing P7 placement directory\n' >&2; exit 2; }
export HAP_POST_PLACE_DCP="$place_dir/post_place.dcp"
export HAP_PLACE_SUMMARY="$place_dir/summary.txt"
export HAP_PLACE_INPUT_SHA="$place_dir/INPUT_SHA256SUMS"
export HAP_PLACE_OUTPUT_SHA="$place_dir/OUTPUT_SHA256SUMS"
PLACE_INPUT_FILES="$place_dir/INPUT_FILES"
PLACE_LAUNCHER_STATUS="$place_dir/launcher_status.txt"
PLACE_SELECTORS="$place_dir/selectors_post_place.txt"
PLACE_GEOMETRY="$place_dir/attention_geometry_post_place.txt"
PLACE_GEOMETRY_PLACEMENT="$place_dir/attention_geometry_placement.txt"
PLACE_BASE_PBLOCKS="$place_dir/base_pblocks_post_place.txt"
PLACE_P5_PLAN="$place_dir/p5_input_plan_post_place.txt"
PLACE_P5_PBLOCKS="$place_dir/p5_input_pblocks_post_place.txt"
PLACE_P6_PLAN="$place_dir/p6_postprocess_plan_post_place.txt"
PLACE_P6_PBLOCKS="$place_dir/p6_postprocess_pblocks_post_place.txt"
PLACE_PRE_GATE="$place_dir/pre_place_gate.txt"
PLACE_FAST_GATE="$place_dir/post_place_fast_gate.txt"
place_files=("$HAP_POST_PLACE_DCP" "$HAP_PLACE_SUMMARY"
    "$HAP_PLACE_INPUT_SHA" "$HAP_PLACE_OUTPUT_SHA" "$PLACE_INPUT_FILES"
    "$PLACE_LAUNCHER_STATUS" "$PLACE_SELECTORS" "$PLACE_GEOMETRY"
    "$PLACE_GEOMETRY_PLACEMENT" "$PLACE_BASE_PBLOCKS" "$PLACE_P5_PLAN"
    "$PLACE_P5_PBLOCKS" "$PLACE_P6_PLAN" "$PLACE_P6_PBLOCKS" \
    "$PLACE_PRE_GATE" "$PLACE_FAST_GATE")
for file in "${place_files[@]}" "$ROUTE_TCL" "$LAUNCHER" "$HELPER_LIB" \
        "$SELECTOR_LIB" "$GEOMETRY_LIB" "$P5_LIB" "$P6_LIB" \
        "$IO_AUDIT" "$CLOCK_XDC"; do
    [[ -s "$file" ]] || { printf 'missing P7 route input: %s\n' "$file" >&2; exit 2; }
done
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") >/dev/null
(cd / && sha256sum -c --strict "$HAP_PLACE_OUTPUT_SHA") >/dev/null
export HAP_PLACE_INPUT_MANIFEST_SHA256
HAP_PLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')"
export HAP_PLACE_OUTPUT_MANIFEST_SHA256
HAP_PLACE_OUTPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PLACE_OUTPUT_SHA" | awk '{print $1}')"

for literal in status=PASS flow_mode=accept acceptance_evidence=1 \
        route_eligible=1 final_exit_code=0 vivado_exit_code=0 \
        input_sha_recheck_exit_code=0 input_manifest_sha_match=1 \
        place_gate_exit_code=0 checkpoint_written=1 \
        implementation_commands_requested=1 bitstream_generated=0; do
    grep -Fqx -- "$literal" "$PLACE_LAUNCHER_STATUS"
done
for literal in status=V5_P10_P7_PRODUCTION_PLACE_PASS \
        stage=V5_P10_P7_POST_PLACE_ACCEPT flow_mode=accept \
        acceptance_evidence=1 route_eligible=1 checkpoint_written=1 \
        input_manifest_entries=11 provenance_verified=1 pre_place_verified=1 \
        part=xcvu9p-flga2104-2L-e top=hap_attention_mlp_production_core \
        contract_variant=P2_COHORT16_COL2_12_2 \
        p5_contract=P5_INPUT_HALF_LOCAL_8_8 \
        p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4 \
        p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8 \
        region2_variant=rowsplit_y5_y6_y6_y8 jobs=32 \
        core_clock_mhz=100 ddr0_clock_mhz=300 ddr1_clock_mhz=300 \
        dsp48e2=5453 uram288=752 mlp_kernel_dsp48e2=3072 \
        history2_repack_instances=2 generic_repack_instances=0 \
        projection_weight_capture_ok=1 canonical_pblock_count=11 \
        geometry_pblock_count=12 p5_added_pblock_count=2 \
        p6_added_pblock_count=2 total_pblock_count=27 \
        slr0_dsp48e2=1862 slr1_dsp48e2=1781 slr2_dsp48e2=1810 \
        slr0_uram288=224 slr1_uram288=224 slr2_uram288=304 \
        unplaced_primitives=0 wrong_slr_primitives=0 \
        completed_u8_ff=4096 completed_meta_ff=352 \
        input_capture_ff=12288 input_capture_controls=48 \
        p6_slr0_row_primitives=10696 p6_center_row_primitives=21392 \
        p6_slr2_row_primitives=10696 \
        p7_region2_rows0_3_primitives=26800 \
        p7_region2_rows4_7_primitives=26800 \
        p7_region2_residual_primitives=15199 \
        p7_region2_rows0_3_dsp48e2=272 \
        p7_region2_rows4_7_dsp48e2=272 \
        p7_region2_residual_dsp48e2=0 \
        compute_clock_buffer_none_missing_after_reapply=0 \
        pre_place_drc_errors=0 post_place_drc_errors=0 \
        false_path_exception_rows=0 datapath_only_exception_rows=0 \
        timing_coverage_ok=1 cdc_critical=0 data_bufg=0 \
        congestion_level6_or_higher_windows=0 resource_ok=1 structure_ok=1 \
        placement_ok=1 optimizer_extras_ok=1 fast_gate_ok=1 policy_ok=1 \
        level5_screen_ok=1 level6_congestion_ok=1; do
    grep -Fqx -- "$literal" "$HAP_PLACE_SUMMARY"
done
require_free_batch_slot

STAMP="$(date +%Y%m%d_%H%M%S)"
requested="${HAP_ROUTE_DIR:-$ROOT/vivado/reports/production_v5_p10_p7_route_$STAMP}"
export HAP_ROUTE_DIR="$(readlink -m -- "$requested")"
[[ ! -e "$HAP_ROUTE_DIR" ]] || {
    printf 'P7 route evidence directory exists: %s\n' "$HAP_ROUTE_DIR" >&2
    exit 2
}
mkdir "$HAP_ROUTE_DIR"
export HAP_ROUTE_HELPER_LIB="$HELPER_LIB"
export HAP_ROUTE_SELECTOR_LIB="$SELECTOR_LIB"
export HAP_ROUTE_GEOMETRY_LIB="$GEOMETRY_LIB"
export HAP_ROUTE_P5_LIB="$P5_LIB"
export HAP_ROUTE_P6_LIB="$P6_LIB"
export HAP_ROUTE_IO_AUDIT="$IO_AUDIT"
export HAP_ROUTE_CLOCK_XDC="$CLOCK_XDC"
export HAP_ROUTE_LAUNCHER="$LAUNCHER"
inputs=("$HAP_POST_PLACE_DCP" "$HAP_PLACE_SUMMARY"
    "$HAP_PLACE_INPUT_SHA" "$HAP_PLACE_OUTPUT_SHA" "$PLACE_INPUT_FILES"
    "$PLACE_LAUNCHER_STATUS" "$PLACE_SELECTORS" "$PLACE_GEOMETRY"
    "$PLACE_GEOMETRY_PLACEMENT" "$PLACE_BASE_PBLOCKS" "$PLACE_P5_PLAN"
    "$PLACE_P5_PBLOCKS" "$PLACE_P6_PLAN" "$PLACE_P6_PBLOCKS" \
    "$PLACE_PRE_GATE" "$PLACE_FAST_GATE" "$SELECTOR_LIB" "$GEOMETRY_LIB" \
    "$P5_LIB" "$P6_LIB" "$IO_AUDIT" "$CLOCK_XDC" "$HELPER_LIB" \
    "$ROUTE_TCL" "$LAUNCHER")
printf '%s\n' "${inputs[@]}" > "$HAP_ROUTE_DIR/INPUT_FILES"
sha256sum -- "${inputs[@]}" > "$HAP_ROUTE_DIR/INPUT_SHA256SUMS"
export HAP_ROUTE_INPUT_MANIFEST_SHA256
HAP_ROUTE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_ROUTE_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_ROUTE_DIR/INPUT_SHA256SUMS") >/dev/null

vivado_exit_code=255
vivado_invoked=0
route_input_sha_postcheck=0
place_input_sha_postcheck=0
place_output_sha_postcheck=0
route_input_manifest_sha_match=0
place_input_manifest_sha_match=0
place_output_manifest_sha_match=0

write_status() {
    local rc="$1" status=FAIL
    [[ "$rc" -eq 0 ]] && status=PASS
    printf '%s\n' "status=$status" "final_exit_code=$rc" \
        "vivado_exit_code=$vivado_exit_code" "vivado_invoked=$vivado_invoked" \
        "route_input_sha_postcheck=$route_input_sha_postcheck" \
        "place_input_sha_postcheck=$place_input_sha_postcheck" \
        "place_output_sha_postcheck=$place_output_sha_postcheck" \
        "route_input_manifest_sha_match=$route_input_manifest_sha_match" \
        "place_input_manifest_sha_match=$place_input_manifest_sha_match" \
        "place_output_manifest_sha_match=$place_output_manifest_sha_match" \
        "route_input_manifest_sha256=$HAP_ROUTE_INPUT_MANIFEST_SHA256" \
        'bitstream_generated=0' > "$HAP_ROUTE_DIR/launcher_status.txt"
}

archive_outputs() {
    local -a outputs=() current=() manifested=()
    local index
    mapfile -d '' outputs < <(find "$HAP_ROUTE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || return 1
    sha256sum -- "${outputs[@]}" > "$HAP_ROUTE_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_ROUTE_DIR/OUTPUT_SHA256SUMS" >/dev/null)
    mapfile -d '' current < <(find "$HAP_ROUTE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    mapfile -t manifested < <(awk \
        '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
        "$HAP_ROUTE_DIR/OUTPUT_SHA256SUMS" | sort)
    [[ "${#current[@]}" -eq "${#manifested[@]}" ]] || return 1
    for index in "${!current[@]}"; do
        [[ "${current[$index]}" == "${manifested[$index]}" ]] || return 1
    done
}

exit_archive() {
    local rc="$?"
    trap - EXIT
    write_status "$rc" || rc=96
    if ! archive_outputs; then
        [[ "$rc" -ne 0 ]] || rc=97
        write_status "$rc" || true
        archive_outputs || true
    fi
    exit "$rc"
}
trap exit_archive EXIT

cd "$ROOT"
set +e
vivado_invoked=1
"$VIVADO" -mode batch -notrace \
    -source "$ROUTE_TCL" \
    -log "$HAP_ROUTE_DIR/vivado.log" -journal "$HAP_ROUTE_DIR/vivado.jou"
vivado_exit_code=$?
set -e
final_rc="$vivado_exit_code"
(cd / && sha256sum -c --strict "$HAP_ROUTE_DIR/INPUT_SHA256SUMS") >/dev/null && \
    route_input_sha_postcheck=1 || final_rc=90
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") >/dev/null && \
    place_input_sha_postcheck=1 || final_rc=91
(cd / && sha256sum -c --strict "$HAP_PLACE_OUTPUT_SHA") >/dev/null && \
    place_output_sha_postcheck=1 || final_rc=92
[[ "$(sha256sum -- "$HAP_ROUTE_DIR/INPUT_SHA256SUMS" | awk '{print $1}')" == \
    "$HAP_ROUTE_INPUT_MANIFEST_SHA256" ]] && \
    route_input_manifest_sha_match=1 || final_rc=93
[[ "$(sha256sum -- "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')" == \
    "$HAP_PLACE_INPUT_MANIFEST_SHA256" ]] && \
    place_input_manifest_sha_match=1 || final_rc=94
[[ "$(sha256sum -- "$HAP_PLACE_OUTPUT_SHA" | awk '{print $1}')" == \
    "$HAP_PLACE_OUTPUT_MANIFEST_SHA256" ]] && \
    place_output_manifest_sha_match=1 || final_rc=95
write_status "$final_rc"
[[ "$final_rc" -eq 0 ]] || exit "$final_rc"

required=(summary.txt post_route.dcp post_route_diagnostic.dcp post_phys_opt.dcp
    selectors_input.txt selectors_post_route.txt
    attention_geometry_input.txt attention_geometry_post_route.txt
    attention_geometry_placement_input.txt
    attention_geometry_placement_post_route.txt
    base_pblocks_input.txt base_pblocks_post_route.txt
    p5_input_plan_input.txt p5_input_plan_post_route.txt
    p5_input_pblocks_input.txt p5_input_pblocks_post_route.txt
    p6_postprocess_plan_input.txt p6_postprocess_plan_post_route.txt
    p6_postprocess_pblocks_input.txt p6_postprocess_pblocks_post_route.txt
    architecture_boundaries_input.txt architecture_boundaries_post_route.txt
    utilization_post_route.rpt utilization_hier_post_route.rpt
    utilization_slr_post_route.rpt timing_post_phys_opt.rpt
    timing_post_route.rpt timing_setup_worst100_post_route.rpt
    timing_hold_worst100_post_route.rpt route_status_post_route.rpt
    drc_post_route.rpt cdc_post_route.rpt clock_interaction_post_route.rpt
    clock_utilization_post_route.rpt congestion_post_route.rpt
    exceptions_coverage_post_route.rpt vivado.log vivado.jou
    launcher_status.txt INPUT_FILES INPUT_SHA256SUMS)
for name in "${required[@]}"; do
    [[ -s "$HAP_ROUTE_DIR/$name" ]] || {
        printf 'missing P7 route output: %s\n' "$name" >&2
        exit 1
    }
done
summary="$HAP_ROUTE_DIR/summary.txt"
expected=(
    'status=V5_P10_P7_PRODUCTION_OOC_POST_ROUTE_PASS'
    'evidence_class=P7_PRODUCTION_CORE_OOC_POST_ROUTE' 'jobs=32'
    'core_clock_mhz=100' 'ddr0_clock_mhz=300' 'ddr1_clock_mhz=300'
    'input_sha_manifests_verified=1' 'place_input_manifest_entries=11'
    'route_input_manifest_entries=25'
    'base_contract_variant=P2_COHORT16_COL2_12_2'
    'p5_contract=P5_INPUT_HALF_LOCAL_8_8'
    'p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'
    'p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8'
    'region2_variant=rowsplit_y5_y6_y6_y8'
    'dsp48e2=5453' 'uram288=752' 'mlp_kernel_dsp48e2=3072'
    'history2_repack_instances=2' 'generic_repack_instances=0'
    'projection_weight_capture_ok=1' 'pblock_count=27'
    'canonical_pblock_count=11' 'geometry_pblock_count=12'
    'p5_added_pblock_count=2' 'p6_added_pblock_count=2'
    'pblock_dsp_coverage=5453' 'pblock_uram_coverage=752'
    'pblock_wrong_slr=0' 'p5_center_wrong_slr=0' 'p5_outer_wrong_slr=0'
    'p6_center_wrong_slr=0' 'p6_outer_wrong_slr=0'
    'p6_slr0_row_primitives=10696' 'p6_center_row_primitives=21392'
    'p6_slr2_row_primitives=10696'
    'p7_region2_rows0_3_primitives=26800'
    'p7_region2_rows4_7_primitives=26800'
    'p7_region2_residual_primitives=15199'
    'p7_region2_rows0_3_dsp48e2=272'
    'p7_region2_rows4_7_dsp48e2=272'
    'p7_region2_residual_dsp48e2=0'
    'completed_u8_ff=4096' 'completed_meta_ff=352'
    'input_capture_ff=12288' 'input_capture_controls=48'
    'slr0_dsp48e2=1862' 'slr1_dsp48e2=1781'
    'slr2_dsp48e2=1810' 'slr0_uram288=224' 'slr1_uram288=224'
    'slr2_uram288=304' 'unplaced_primitives=0' 'wrong_slr_primitives=0'
    'metadata_local_write_protected_ff=970'
    'mlp_capture_leaf_instances=1632' 'mlp_capture_leaf_lut1=1632'
    'pre_route_compute_missing_after=0' 'final_compute_missing_after=0'
    'route_error_nets=0' 'explicit_gap_nets=0' 'unrouted_nets=0'
    'some_unrouted_pin_nets=0' 'resource_conflict_nets=0'
    'antenna_island_nets=0' 'route_status_partial=0'
    'route_status_conflicts=0' 'route_clean=1' 'drc_errors=0'
    'drc_report_error_rows=0' 'no_clock_endpoints=0'
    'unconstrained_paths=0' 'no_input_delay_ports=3'
    'no_output_delay_ports=0' 'partial_input_delay_ports=0'
    'partial_output_delay_ports=0' 'timing_coverage_ok=1'
    'cdc_critical=0' 'data_bufg=0' 'false_path_exception_rows=0'
    'datapath_only_exception_rows=0'
    'congestion_level6_or_higher_windows=0' 'operation_ok=1' 'report_ok=1'
    'resource_ok=1' 'physical_ok=1' 'architecture_boundary_ok=1'
    'timing_ok=1' 'policy_ok=1' 'route_eligible=1'
    'checkpoint_written=1' 'bitstream_generated=0')
for literal in "${expected[@]}"; do
    [[ "$(grep -Fxc -- "$literal" "$summary" || true)" -eq 1 ]] || {
        printf 'P7 route summary gate failed: %s\n' "$literal" >&2
        exit 1
    }
done
awk -F= '/^wns_ns=|^whs_ns=/{n++; if ($2 < 0) bad=1} \
    END{exit n==2 && !bad ? 0 : 1}' "$summary"
archive_outputs
cat "$summary"
printf '%s\n' "$HAP_ROUTE_DIR"
