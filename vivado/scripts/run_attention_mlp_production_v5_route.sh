#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
[[ -x "$VIVADO" ]] || {
    printf 'Vivado executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
if [[ $# -ne 1 ]]; then
    printf 'usage: %s V5_PLACE_ARTIFACT_DIR\n' "$0" >&2
    exit 2
fi

export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] &&
    (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be an integer in 1..32: %q\n' "$HAP_JOBS" >&2
    exit 2
}

PLACE_DIR="$(readlink -f "$1")"
LEGACY_PLACE_DIR="$ROOT/vivado/reports/production_v5_place_20260817_223533"
if [[ "$PLACE_DIR" == "$LEGACY_PLACE_DIR" ]]; then
    printf 'V5 P2_COHORT16_COL2_12_2 route rejects the frozen legacy10 Run0138 artifact: %s\n' \
        "$LEGACY_PLACE_DIR" >&2
    exit 2
fi
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; route not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi

export HAP_POST_PLACE_DCP="$PLACE_DIR/post_place.dcp"
export HAP_PLACE_SUMMARY="$PLACE_DIR/summary.txt"
export HAP_PLACE_INPUT_SHA="$PLACE_DIR/INPUT_SHA256SUMS"
export HAP_PLACE_OUTPUT_SHA="$PLACE_DIR/OUTPUT_SHA256SUMS"
PLACE_INPUT_FILES="$PLACE_DIR/INPUT_FILES"
PLACE_LAUNCHER_STATUS="$PLACE_DIR/launcher_status.txt"
PLACE_SELECTORS="$PLACE_DIR/selectors_post_place.txt"
PLACE_PBLOCKS="$PLACE_DIR/pblocks_post_place.txt"
for input in "$HAP_POST_PLACE_DCP" "$HAP_PLACE_SUMMARY" \
        "$HAP_PLACE_INPUT_SHA" "$HAP_PLACE_OUTPUT_SHA" \
        "$PLACE_INPUT_FILES" "$PLACE_LAUNCHER_STATUS" \
        "$PLACE_SELECTORS" "$PLACE_PBLOCKS"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty V5 place evidence: %s\n' "$input" >&2
        exit 2
    }
done
export HAP_PLACE_INPUT_MANIFEST_SHA256
HAP_PLACE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')"
export HAP_PLACE_OUTPUT_MANIFEST_SHA256
HAP_PLACE_OUTPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_PLACE_OUTPUT_SHA" | awk '{print $1}')"

require_exact_line() {
    local file="$1" literal="$2" key
    key="${literal%%=*}"
    [[ "$(grep -Fxc -- "$literal" "$file" || true)" -eq 1 ]] || {
        printf 'V5 fresh place artifact gate failed: %s: %s\n' \
            "${file#"$PLACE_DIR/"}" "$literal" >&2
        return 1
    }
    [[ "$(grep -Ec -- "^${key}=" "$file" || true)" -eq 1 ]] || {
        printf 'V5 fresh place artifact field is missing or duplicated: %s: %s\n' \
            "${file#"$PLACE_DIR/"}" "$key" >&2
        return 1
    }
}

for literal in \
    'status=PASS' 'flow_mode=accept' 'acceptance_evidence=1' \
    'route_eligible=1' 'final_exit_code=0' 'vivado_exit_code=0' \
    'input_sha_recheck_exit_code=0' 'input_manifest_sha_match=1' \
    'place_gate_exit_code=0' 'checkpoint_written=1' \
    'vivado_invoked=1' 'implementation_commands_requested=1' \
    'bitstream_generated=0'; do
    require_exact_line "$PLACE_LAUNCHER_STATUS" "$literal"
done

# Require the independently frozen live-selector and pblock reports to carry
# the same fresh row-local contract as the place summary.  These files are
# already covered by HAP_PLACE_OUTPUT_SHA, verified immediately above.
for literal in \
    'contract_variant=P2_COHORT16_COL2_12_2' \
    'total_dsp=5453' \
    'total_uram=752' \
    'row_leaf_count=2' \
    'unique_hadamard_count=1' \
    'fold2_count=0' \
    'quantizer_count=4' \
    'silu_count=2' \
    'leaf0_dsp=2' \
    'leaf1_dsp=2' \
    'leaf0_ramb36=6' \
    'leaf1_ramb36=6' \
    'outer0_dsp=1538' \
    'outer2_dsp=1538' \
    'outer0_ramb36=102' \
    'outer2_ramb36=102' \
    'move0=16' \
    'center_lanes=96' \
    'move2=16' \
    'planned_slr0_dsp=1862' \
    'planned_slr1_dsp=1781' \
    'planned_slr2_dsp=1810'; do
    require_exact_line "$PLACE_SELECTORS" "$literal"
done
for literal in \
    'contract_variant=P2_COHORT16_COL2_12_2' \
    'pblock_count=11' \
    'dsp_coverage=5453' \
    'uram_coverage=752' \
    'placed_wrong=0' \
    'pb_v5_mlp_branch_slr0_dsp=1538' \
    'pb_v5_mlp_branch_slr0_ramb36=102' \
    'pb_v5_mlp_branch_slr2_dsp=1538' \
    'pb_v5_mlp_branch_slr2_ramb36=102' \
    'pb_v5_attention_projection_left2_slr0_target=0' \
    'pb_v5_attention_projection_left2_slr0_dsp=272' \
    'pb_v5_attention_projection_left2_slr0_uram=0' \
    'pb_v5_attention_projection_left2_slr0_missing=0' \
    'pb_v5_attention_projection_left2_slr0_placed_wrong=0' \
    'pb_v5_attention_projection_center12_slr1_target=1' \
    'pb_v5_attention_projection_center12_slr1_dsp=1781' \
    'pb_v5_attention_projection_center12_slr1_uram=0' \
    'pb_v5_attention_projection_center12_slr1_missing=0' \
    'pb_v5_attention_projection_center12_slr1_placed_wrong=0' \
    'pb_v5_attention_projection_right2_slr2_target=2' \
    'pb_v5_attention_projection_right2_slr2_dsp=272' \
    'pb_v5_attention_projection_right2_slr2_uram=0' \
    'pb_v5_attention_projection_right2_slr2_missing=0' \
    'pb_v5_attention_projection_right2_slr2_placed_wrong=0'; do
    require_exact_line "$PLACE_PBLOCKS" "$literal"
done

# Placement has eight frozen inputs, including its independent pre-place output
# manifest, and a dynamically complete output manifest.
# Freeze the manifests themselves separately, require every current nonempty
# artifact except OUTPUT_SHA256SUMS to appear exactly once, and repeat all
# checks after Vivado returns.
[[ "$(wc -l < "$HAP_PLACE_INPUT_SHA")" -eq 8 ]] || {
    printf 'V5 place input SHA manifest must have exactly 8 rows\n' >&2
    exit 2
}
place_output_manifest_entries="$(wc -l < "$HAP_PLACE_OUTPUT_SHA")"
[[ "$place_output_manifest_entries" -ge 1 ]] || {
    printf 'V5 place output SHA manifest is empty\n' >&2
    exit 2
}
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA")
(cd / && sha256sum -c --strict "$HAP_PLACE_OUTPUT_SHA")
mapfile -d '' expected_place_outputs < <(find "$PLACE_DIR" -maxdepth 1 \
    -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
mapfile -t manifested_place_outputs < <(awk '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
    "$HAP_PLACE_OUTPUT_SHA" | sort)
if ! awk '/^[0-9a-f]{64}[[:space:]]+\*?\// {next} {exit 1}' \
        "$HAP_PLACE_OUTPUT_SHA"; then
    printf 'V5 place output manifest has malformed or duplicate paths\n' >&2
    exit 2
fi
if [[ "$(printf '%s\n' "${manifested_place_outputs[@]}" | sort -u | wc -l)" \
      -ne "$place_output_manifest_entries" ]]; then
    printf 'V5 place output manifest has malformed or duplicate paths\n' >&2
    exit 2
fi
[[ "${#expected_place_outputs[@]}" -eq "$place_output_manifest_entries" &&
    "${#manifested_place_outputs[@]}" -eq "$place_output_manifest_entries" ]] || {
    printf 'V5 place output manifest/file cardinality mismatch\n' >&2
    exit 2
}
for index in "${!expected_place_outputs[@]}"; do
    [[ "${expected_place_outputs[$index]}" == \
       "${manifested_place_outputs[$index]}" ]] || {
        printf 'V5 place output manifest is not the complete current nonempty file set\n' >&2
        exit 2
    }
done
for required_path in "$HAP_POST_PLACE_DCP" "$HAP_PLACE_SUMMARY" \
        "$HAP_PLACE_INPUT_SHA" "$PLACE_INPUT_FILES" \
        "$PLACE_LAUNCHER_STATUS" "$PLACE_SELECTORS" "$PLACE_PBLOCKS"; do
    [[ "$(grep -Fxc -- \
        "$(sha256sum -- "$required_path" | awk '{print $1}')  $required_path" \
        "$HAP_PLACE_OUTPUT_SHA" || true)" -eq 1 ]] || {
        printf 'V5 place required output is not uniquely frozen: %s\n' \
            "$required_path" >&2
        exit 2
    }
done

declare -A REQUIRED_PLACE=(
    [status]=V5_PRODUCTION_PLACE_PASS
    [flow_mode]=accept
    [acceptance_evidence]=1
    [route_eligible]=1
    [checkpoint_written]=1
    [input_manifest_entries]=8
    [compute_clock_buffer_none_ok]=1
    [geometry_pblock_prefix]=p3_
    [canonical_pblock_count]=11
    [geometry_pblock_count]=10
    [geometry_region0_input_primitives]=3136
    [geometry_region3_input_primitives]=2112
    [geometry_owner_region2_weight_primitives]=2048
    [geometry_region0_input_ok]=1
    [geometry_region3_input_ok]=1
    [geometry_owner_region2_weight_ok]=1
    [geometry_placement_ok]=1
    [pre_place_verified]=1
    [part]=xcvu9p-flga2104-2L-e
    [top]=hap_attention_mlp_production_core
    [core_clock_mhz]=100
    [ddr0_clock_mhz]=300
    [ddr1_clock_mhz]=300
    [mlp_kernel_dsp48e2]=3072
    [dsp48e2]=5453
    [uram288]=752
    [history2_repack_instances]=2
    [generic_repack_instances]=0
    [raw_weight_push_loads]=37
    [weight_data_capture_contract]=32x256
    [weight_data_capture_nets]=32
    [weight_data_capture_loads]=256/256
    [weight_meta_capture_contract]=2x256
    [weight_meta_capture_nets]=2
    [weight_meta_capture_loads]=256/256
    [weight_group_capture_contract]=2x7
    [weight_group_capture_nets]=2
    [weight_group_capture_loads]=7/7
    [projection_weight_capture_ok]=1
    [slr0_uram288]=224
    [slr1_uram288]=224
    [slr2_uram288]=304
    [unplaced_primitives]=0
    [wrong_slr_primitives]=0
    [pre_place_pblock_contract_ok]=1
    [post_place_live_rediscovery_ok]=1
    [post_place_pblock_contract_ok]=1
    [pblock_contract_variant]=P2_COHORT16_COL2_12_2
    [attention_row_instances]=1
    [kv_cache_instances]=1
    [kv_quantizer4_instances]=1
    [attention_island_target_slr]=0
    [attention_island_dsp48e2]=52
    [attention_island_ramb36e2]=88
    [attention_island_ramb18e2]=2
    [attention_island_uram288]=0
    [attention_island_quantizer_overlap]=0
    [attention_island_row_cache_overlap]=0
    [attention_island_pblock_dsp48e2]=52
    [attention_island_pblock_ramb36e2]=88
    [attention_island_pblock_ramb18e2]=2
    [attention_island_pblock_uram288]=0
    [moved_lanes_slr0]=16
    [center_lanes_slr1]=96
    [moved_lanes_slr2]=16
    [planned_slr0_dsp48e2]=1862
    [planned_slr1_dsp48e2]=1781
    [planned_slr2_dsp48e2]=1810
    [slr0_dsp48e2]=1862
    [slr1_dsp48e2]=1781
    [slr2_dsp48e2]=1810
    [post_place_pblock_count]=21
    [post_place_canonical_pblock_count]=11
    [post_place_geometry_pblock_count]=10
    [post_place_pblock_dsp_coverage]=5453
    [post_place_pblock_uram_coverage]=752
    [post_place_pblock_wrong_slr]=0
    [mlp_local_clear_ff]=2
    [mlp_local_clear_protected_ff]=2
    [branch0_local_clear_ff]=1
    [branch1_local_clear_ff]=1
    [branch0_local_clear_slr]='1 0 0'
    [branch1_local_clear_slr]='0 0 1'
    [mlp_local_clear_wrong_slr]=0
    [mlp_central_clear_ff]=1
    [mlp_central_clear_branch_endpoints]=2
    [mlp_central_clear_direct_branch_state]=0
    [metadata_leaf_instances]=4
    [metadata_local_wr_en_ff]=4
    [metadata_local_wr_addr_ff]=70
    [metadata_local_wr_data_ff]=896
    [metadata_local_write_protected_ff]=970
    [metadata_local_write_leaf_counts]='243 243 242 242'
    [metadata_local_write_leaf_slr_counts]='{243 0 0} {0 0 243} {0 242 0} {0 242 0}'
    [metadata_local_write_wrong_slr]=0
    [mlp_capture_leaf_instances]=1632
    [mlp_capture_leaf_lut1]=1632
    [mlp_capture_leaf_branch_instances]='816 816'
    [mlp_capture_leaf_branch_lut1]='816 816'
    [mlp_capture_leaf_branch_slr_counts]='{816 0 0} {0 0 816}'
    [mlp_capture_leaf_wrong_slr]=0
    [branch0_wrong_slr]=0
    [branch2_wrong_slr]=0
    [attention_lane0_wrong_slr]=0
    [attention_lane2_wrong_slr]=0
    [center_dsp_wrong_slr]=0
    [metadata_gate0_wrong_slr]=0
    [metadata_gate2_wrong_slr]=0
    [metadata_down0_wrong_slr]=0
    [metadata_down1_wrong_slr]=0
    [attention_metadata_wrong_slr]=0
    [attention_island_wrong_slr]=0
    [pre_place_drc_errors]=0
    [post_place_drc_errors]=0
    [false_path_exception_rows]=0
    [datapath_only_exception_rows]=0
    [no_clock_endpoints]=0
    [unconstrained_paths]=0
    [no_input_delay_ports]=3
    [no_output_delay_ports]=0
    [partial_input_delay_ports]=0
    [partial_output_delay_ports]=0
    [timing_coverage_ok]=1
    [cdc_critical]=0
    [data_bufg]=0
    [fast_gate_ok]=1
    [congestion_level6_or_higher_windows]=0
    [resource_ok]=1
    [placement_ok]=1
    [uram_distribution_ok]=1
    [policy_ok]=1
    [level6_congestion_ok]=1
)
for key in "${!REQUIRED_PLACE[@]}"; do
    [[ "$(grep -Fxc "$key=${REQUIRED_PLACE[$key]}" \
        "$HAP_PLACE_SUMMARY")" -eq 1 ]] || {
        printf 'V5 place summary gate failed: %s=%s\n' \
            "$key" "${REQUIRED_PLACE[$key]}" >&2
        exit 2
    }
done
ROUTE_TCL="$ROOT/vivado/scripts/resume_attention_mlp_production_v5_route.tcl"
LAUNCHER="$ROOT/vivado/scripts/run_attention_mlp_production_v5_route.sh"
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
IO_AUDIT="$ROOT/vivado/scripts/check_attention_mlp_production_io_selectors.tcl"
CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
for input in "$ROUTE_TCL" "$LAUNCHER" "$SELECTOR_LIB" \
        "$IO_AUDIT" "$CLOCK_XDC"; do
    [[ -s "$input" ]] || {
        printf 'missing or empty V5 route source: %s\n' "$input" >&2
        exit 2
    }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
requested_route_dir="${HAP_ROUTE_DIR:-$ROOT/vivado/reports/production_v5_route_$STAMP}"
export HAP_ROUTE_DIR="$(readlink -m -- "$requested_route_dir")"
export HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE="${HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
export HAP_ROUTE_DIRECTIVE="${HAP_ROUTE_DIRECTIVE:-AggressiveExplore}"
export HAP_POST_ROUTE_PHYSOPT_DIRECTIVE="${HAP_POST_ROUTE_PHYSOPT_DIRECTIVE:-AggressiveExplore}"
[[ ! -e "$HAP_ROUTE_DIR" ]] || {
    printf 'V5 route evidence directory already exists: %s\n' \
        "$HAP_ROUTE_DIR" >&2
    exit 2
}
mkdir "$HAP_ROUTE_DIR"

# Every exit after the fresh evidence directory is created (PASS or FAIL)
# must leave a hash-complete archive.  OUTPUT_SHA256SUMS is the sole
# self-exclusion; vivado.jou, the frozen input evidence and any Tcl error
# diagnostics are ordinary evidence and are therefore included.
archive_route_outputs() {
    local index
    local -a outputs=() current=() manifested=()
    mapfile -d '' outputs < <(find "$HAP_ROUTE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || {
        printf 'V5 route evidence directory has no nonempty outputs: %s\n' \
            "$HAP_ROUTE_DIR" >&2
        return 1
    }
    sha256sum -- "${outputs[@]}" > "$HAP_ROUTE_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_ROUTE_DIR/OUTPUT_SHA256SUMS" >/dev/null)
    mapfile -d '' current < <(find "$HAP_ROUTE_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    mapfile -t manifested < <(awk '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
        "$HAP_ROUTE_DIR/OUTPUT_SHA256SUMS" | sort)
    [[ "${#current[@]}" -eq "${#manifested[@]}" ]] || return 1
    for index in "${!current[@]}"; do
        [[ "${current[$index]}" == "${manifested[$index]}" ]] || return 1
    done
}

vivado_exit_code=255
vivado_invoked=0
route_input_sha_precheck=0
route_input_sha_postcheck=0
place_input_sha_postcheck=0
place_output_sha_postcheck=0
route_input_manifest_sha_match=0
place_input_manifest_sha_match=0
place_output_manifest_sha_match=0
HAP_ROUTE_INPUT_MANIFEST_SHA256=""

write_route_launcher_status() {
    local final_rc="$1" status=FAIL
    [[ "$final_rc" -eq 0 ]] && status=PASS
    printf '%s\n' \
        "status=$status" \
        "final_exit_code=$final_rc" \
        "vivado_exit_code=$vivado_exit_code" \
        "vivado_invoked=$vivado_invoked" \
        "route_input_sha_precheck=$route_input_sha_precheck" \
        "route_input_sha_postcheck=$route_input_sha_postcheck" \
        "place_input_sha_postcheck=$place_input_sha_postcheck" \
        "place_output_sha_postcheck=$place_output_sha_postcheck" \
        "place_input_manifest_sha_match=$place_input_manifest_sha_match" \
        "place_output_manifest_sha_match=$place_output_manifest_sha_match" \
        "route_input_manifest_sha_match=$route_input_manifest_sha_match" \
        "route_input_manifest_sha256=$HAP_ROUTE_INPUT_MANIFEST_SHA256" \
        'bitstream_generated=0' \
        > "$HAP_ROUTE_DIR/launcher_status.txt"
}

route_exit_archive() {
    local rc="$?"
    trap - EXIT
    write_route_launcher_status "$rc" || rc=96
    if ! archive_route_outputs; then
        [[ "$rc" -ne 0 ]] || rc=97
        write_route_launcher_status "$rc" || true
        archive_route_outputs || true
    fi
    exit "$rc"
}
trap route_exit_archive EXIT

INPUTS=(
    "$HAP_POST_PLACE_DCP" "$HAP_PLACE_SUMMARY"
    "$HAP_PLACE_INPUT_SHA" "$HAP_PLACE_OUTPUT_SHA" "$PLACE_INPUT_FILES"
    "$PLACE_LAUNCHER_STATUS" "$PLACE_SELECTORS" "$PLACE_PBLOCKS"
    "$SELECTOR_LIB" "$IO_AUDIT" "$CLOCK_XDC" "$ROUTE_TCL" "$LAUNCHER"
)
printf '%s\n' "${INPUTS[@]}" > "$HAP_ROUTE_DIR/INPUT_FILES"
sha256sum "${INPUTS[@]}" > "$HAP_ROUTE_DIR/INPUT_SHA256SUMS"
export HAP_ROUTE_INPUT_MANIFEST_SHA256
HAP_ROUTE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_ROUTE_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict "$HAP_ROUTE_DIR/INPUT_SHA256SUMS")
route_input_sha_precheck=1

cd "$ROOT"
set +e
vivado_invoked=1
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/resume_attention_mlp_production_v5_route.tcl \
    -log "$HAP_ROUTE_DIR/vivado.log" \
    -journal "$HAP_ROUTE_DIR/vivado.jou"
vivado_exit_code=$?
set -e
vivado_rc="$vivado_exit_code"

# Always preserve a launcher-level result and all diagnostics.  Failure must
# never fall through to bitgen; this script deliberately stops at routed DCP.
(cd / && sha256sum -c --strict "$HAP_ROUTE_DIR/INPUT_SHA256SUMS") && \
    route_input_sha_postcheck=1 || vivado_rc=90
(cd / && sha256sum -c --strict "$HAP_PLACE_INPUT_SHA") && \
    place_input_sha_postcheck=1 || vivado_rc=91
(cd / && sha256sum -c --strict "$HAP_PLACE_OUTPUT_SHA") && \
    place_output_sha_postcheck=1 || vivado_rc=92
if [[ "$(sha256sum -- "$HAP_ROUTE_DIR/INPUT_SHA256SUMS" | awk '{print $1}')" == \
      "$HAP_ROUTE_INPUT_MANIFEST_SHA256" ]]; then
    route_input_manifest_sha_match=1
else
    vivado_rc=93
fi
if [[ "$(sha256sum -- "$HAP_PLACE_INPUT_SHA" | awk '{print $1}')" == \
      "$HAP_PLACE_INPUT_MANIFEST_SHA256" ]]; then
    place_input_manifest_sha_match=1
else
    vivado_rc=94
fi
if [[ "$(sha256sum -- "$HAP_PLACE_OUTPUT_SHA" | awk '{print $1}')" == \
      "$HAP_PLACE_OUTPUT_MANIFEST_SHA256" ]]; then
    place_output_manifest_sha_match=1
else
    vivado_rc=95
fi
write_route_launcher_status "$vivado_rc"

if [[ "$vivado_rc" -ne 0 ]]; then
    printf 'V5 production OOC route failed (Vivado/status rc=%d); diagnostics retained in %s\n' \
        "$vivado_rc" "$HAP_ROUTE_DIR" >&2
    printf '%s\n' "$HAP_ROUTE_DIR"
    exit "$vivado_rc"
fi

REQUIRED_OUTPUTS=(
    summary.txt selectors_input.txt selectors_post_route.txt
    pblocks_input.txt pblocks_post_route.txt
    architecture_boundaries_input.txt architecture_boundaries_post_route.txt
    post_phys_opt.dcp post_route.dcp
    utilization_post_route.rpt utilization_hier_post_route.rpt
    utilization_slr_post_route.rpt timing_post_phys_opt.rpt
    timing_post_route.rpt timing_setup_worst100_post_route.rpt
    timing_hold_worst100_post_route.rpt route_status_post_route.rpt
    drc_post_route.rpt cdc_post_route.rpt
    clock_interaction_post_route.rpt clock_utilization_post_route.rpt
    congestion_post_route.rpt exceptions_coverage_post_route.rpt
    vivado.log vivado.jou launcher_status.txt INPUT_FILES INPUT_SHA256SUMS
)
for required in "${REQUIRED_OUTPUTS[@]}"; do
    [[ -s "$HAP_ROUTE_DIR/$required" ]] || {
        printf 'missing or empty V5 route output: %s\n' "$required" >&2
        exit 1
    }
done

SUMMARY="$HAP_ROUTE_DIR/summary.txt"
declare -A REQUIRED_ROUTE=(
    [status]=V5_PRODUCTION_OOC_POST_ROUTE_PASS
    [part]=xcvu9p-flga2104-2L-e
    [top]=hap_attention_mlp_production_core
    [evidence_class]=PRODUCTION_CORE_OOC_POST_ROUTE
    [jobs]="$HAP_JOBS"
    [core_clock_mhz]=100
    [ddr0_clock_mhz]=300
    [ddr1_clock_mhz]=300
    [core_io_budget_ns]=1.000
    [ddr_io_budget_ns]=0.800
    [input_sha_manifests_verified]=1
    [place_input_manifest_entries]=8
    [place_input_manifest_sha256]="$HAP_PLACE_INPUT_MANIFEST_SHA256"
    [place_output_manifest_entries]="$place_output_manifest_entries"
    [place_output_manifest_sha256]="$HAP_PLACE_OUTPUT_MANIFEST_SHA256"
    [route_input_manifest_entries]=13
    [route_input_manifest_sha256]="$HAP_ROUTE_INPUT_MANIFEST_SHA256"
    [post_phys_opt_checkpoint_written]=1
    [v5_serial_instances]=1
    [old_serial_instances]=0
    [v5_shared_instances]=1
    [v5_branch_instances]=2
    [v5_kernel12_instances]=2
    [v4_kernel16_instances]=0
    [history2_repack_instances]=2
    [generic_repack_instances]=0
    [raw_weight_push_loads]=37
    [weight_data_capture_contract]=32x256
    [weight_data_capture_nets]=32
    [weight_data_capture_loads]=256/256
    [weight_meta_capture_contract]=2x256
    [weight_meta_capture_nets]=2
    [weight_meta_capture_loads]=256/256
    [weight_group_capture_contract]=2x7
    [weight_group_capture_nets]=2
    [weight_group_capture_loads]=7/7
    [projection_weight_capture_ok]=1
    [mlp_kernel_dsp48e2]=3072
    [branch0_dsp48e2]=1536
    [branch2_dsp48e2]=1536
    [row_leaf0_dsp48e2]=2
    [row_leaf1_dsp48e2]=2
    [row_leaf0_ramb36e2]=6
    [row_leaf1_ramb36e2]=6
    [outer0_dsp48e2]=1538
    [outer2_dsp48e2]=1538
    [outer0_ramb36e2]=102
    [outer2_ramb36e2]=102
    [mlp_local_clear_ff]=2
    [mlp_local_clear_protected_ff]=2
    [branch0_local_clear_ff]=1
    [branch1_local_clear_ff]=1
    [branch0_local_clear_slr]='1 0 0'
    [branch1_local_clear_slr]='0 0 1'
    [mlp_local_clear_wrong_slr]=0
    [mlp_central_clear_ff]=1
    [mlp_central_clear_branch_endpoints]=2
    [mlp_central_clear_direct_branch_state]=0
    [metadata_leaf_instances]=4
    [metadata_local_wr_en_ff]=4
    [metadata_local_wr_addr_ff]=70
    [metadata_local_wr_data_ff]=896
    [metadata_local_write_protected_ff]=970
    [metadata_local_write_leaf_counts]='243 243 242 242'
    [metadata_local_write_leaf_slr_counts]='{243 0 0} {0 0 243} {0 242 0} {0 242 0}'
    [metadata_local_write_wrong_slr]=0
    [mlp_capture_leaf_instances]=1632
    [mlp_capture_leaf_lut1]=1632
    [mlp_capture_leaf_branch_instances]='816 816'
    [mlp_capture_leaf_branch_lut1]='816 816'
    [mlp_capture_leaf_branch_slr_counts]='{816 0 0} {0 0 816}'
    [mlp_capture_leaf_wrong_slr]=0
    [dsp48e2]=5453
    [uram288]=752
    [slr0_uram288]=224
    [slr1_uram288]=224
    [slr2_uram288]=304
    [unplaced_primitives]=0
    [wrong_slr_primitives]=0
    [live_post_route_rediscovery_ok]=1
    [pblock_contract_ok]=1
    [pblock_contract_variant]=P2_COHORT16_COL2_12_2
    [attention_row_instances]=1
    [kv_cache_instances]=1
    [kv_quantizer4_instances]=1
    [attention_island_target_slr]=0
    [attention_island_dsp48e2]=52
    [attention_island_ramb36e2]=88
    [attention_island_ramb18e2]=2
    [attention_island_uram288]=0
    [attention_island_quantizer_overlap]=0
    [attention_island_row_cache_overlap]=0
    [attention_island_pblock_dsp48e2]=52
    [attention_island_pblock_ramb36e2]=88
    [attention_island_pblock_ramb18e2]=2
    [attention_island_pblock_uram288]=0
    [moved_lanes_slr0]=16
    [center_lanes_slr1]=96
    [moved_lanes_slr2]=16
    [planned_slr0_dsp48e2]=1862
    [planned_slr1_dsp48e2]=1781
    [planned_slr2_dsp48e2]=1810
    [slr0_dsp48e2]=1862
    [slr1_dsp48e2]=1781
    [slr2_dsp48e2]=1810
    [attention_island_wrong_slr]=0
    [pblock_count]=21
    [canonical_pblock_count]=11
    [geometry_pblock_count]=10
    [geometry_region0_input_primitives]=3136
    [geometry_region3_input_primitives]=2112
    [geometry_owner_region2_weight_primitives]=2048
    [geometry_region0_input_ok]=1
    [geometry_region3_input_ok]=1
    [geometry_owner_region2_weight_ok]=1
    [geometry_placement_ok]=1
    [pblock_dsp_coverage]=5453
    [pblock_uram_coverage]=752
    [pblock_wrong_slr]=0
    [route_error_nets]=0
    [explicit_gap_nets]=0
    [unrouted_nets]=0
    [some_unrouted_pin_nets]=0
    [resource_conflict_nets]=0
    [antenna_island_nets]=0
    [route_status_partial]=0
    [route_status_conflicts]=0
    [route_clean]=1
    [drc_errors]=0
    [drc_report_error_rows]=0
    [no_clock_endpoints]=0
    [unconstrained_paths]=0
    [no_input_delay_ports]=3
    [no_output_delay_ports]=0
    [partial_input_delay_ports]=0
    [partial_output_delay_ports]=0
    [timing_coverage_ok]=1
    [cdc_critical]=0
    [data_bufg]=0
    [false_path_exception_rows]=0
    [datapath_only_exception_rows]=0
    [congestion_global_long_level6_or_higher_windows]=0
    [operation_ok]=1
    [report_ok]=1
    [resource_ok]=1
    [physical_ok]=1
    [architecture_boundary_ok]=1
    [timing_ok]=1
    [policy_ok]=1
    [bitstream_generated]=0
)
for key in "${!REQUIRED_ROUTE[@]}"; do
    [[ "$(grep -Fxc "$key=${REQUIRED_ROUTE[$key]}" "$SUMMARY")" -eq 1 ]] || {
        printf 'V5 route summary gate failed: %s=%s\n' \
            "$key" "${REQUIRED_ROUTE[$key]}" >&2
        exit 1
    }
done
awk -F= '/^wns_ns=|^whs_ns=/{n++; if ($2 < 0) bad=1} \
    END{exit n==2 && !bad?0:1}' "$SUMMARY"
(cd / && sha256sum -c --strict "$HAP_ROUTE_DIR/INPUT_SHA256SUMS")
archive_route_outputs
cat "$SUMMARY"
printf '%s\n' "$HAP_ROUTE_DIR"
