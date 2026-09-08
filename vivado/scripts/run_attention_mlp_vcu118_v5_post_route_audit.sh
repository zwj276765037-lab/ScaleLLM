#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
if [[ $# -ne 3 ]]; then
    printf 'usage: %s V5_POST_ROUTE_DCP V5_BITSTREAM XDC_SOURCE_INVENTORY\n' \
        "$0" >&2
    exit 2
fi
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_AUDIT_DIR="${HAP_AUDIT_DIR:-$ROOT/vivado/reports/attention_mlp_vcu118_v5_post_route_audit_$STAMP}"
HAP_AUDIT_DIR="$(readlink -m -- "$HAP_AUDIT_DIR")"
export HAP_AUDIT_DIR
[[ ! -e "$HAP_AUDIT_DIR" ]] || {
    printf 'independent V5 audit evidence directory already exists: %s\n' \
        "$HAP_AUDIT_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; independent V5 audit not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
export HAP_DCP="$(readlink -f "$1")"
export HAP_BITSTREAM="$(readlink -f "$2")"
export HAP_XDC_INVENTORY="$(readlink -f "$3")"
for input in "$HAP_DCP" "$HAP_BITSTREAM" "$HAP_XDC_INVENTORY"; do
    [[ -s "$input" ]] || { printf 'missing audit input: %s\n' "$input" >&2; exit 2; }
done
mkdir "$HAP_AUDIT_DIR"

# Preserve every nonempty artifact on every exit.  The output manifest is the
# sole self-exclusion, so journals and failure diagnostics cannot disappear
# from a failed or successful independent audit record.
archive_audit_outputs() {
    local index
    local -a outputs=() current=() manifested=()
    mapfile -d '' outputs < <(find "$HAP_AUDIT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || return 1
    sha256sum -- "${outputs[@]}" > "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS" >/dev/null)
    mapfile -d '' current < <(find "$HAP_AUDIT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    mapfile -t manifested < <(awk '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
        "$HAP_AUDIT_DIR/OUTPUT_SHA256SUMS" | sort)
    [[ "${#current[@]}" -eq "${#manifested[@]}" ]] || return 1
    for index in "${!current[@]}"; do
        [[ "${current[$index]}" == "${manifested[$index]}" ]] || return 1
    done
}

vivado_exit_code=255
vivado_invoked=0
input_sha_precheck=0
input_sha_postcheck=0
input_manifest_sha_match=0
HAP_AUDIT_INPUT_MANIFEST_SHA256=""

write_audit_launcher_status() {
    local final_rc="$1" status=FAIL
    [[ "$final_rc" -eq 0 ]] && status=PASS
    printf '%s\n' \
        "status=$status" \
        "final_exit_code=$final_rc" \
        "vivado_exit_code=$vivado_exit_code" \
        "vivado_invoked=$vivado_invoked" \
        "input_sha_precheck=$input_sha_precheck" \
        "input_sha_postcheck=$input_sha_postcheck" \
        "input_manifest_sha_match=$input_manifest_sha_match" \
        "input_manifest_sha256=$HAP_AUDIT_INPUT_MANIFEST_SHA256" \
        > "$HAP_AUDIT_DIR/launcher_status.txt"
}

audit_exit_archive() {
    local rc="$?"
    trap - EXIT
    write_audit_launcher_status "$rc" || rc=96
    if ! archive_audit_outputs; then
        [[ "$rc" -ne 0 ]] || rc=97
        write_audit_launcher_status "$rc" || true
        archive_audit_outputs || true
    fi
    exit "$rc"
}
trap audit_exit_archive EXIT

INPUTS=(
    "$HAP_DCP" "$HAP_BITSTREAM" "$HAP_XDC_INVENTORY"
    "$ROOT/vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl"
    "$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
    "$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
    "$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
    "$ROOT/vivado/scripts/v5_production_p6_postprocess_partition_floorplan.tcl"
    "$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_post_route_audit.sh"
)
printf '%s\n' "${INPUTS[@]}" > "$HAP_AUDIT_DIR/INPUT_FILES"
sha256sum "${INPUTS[@]}" > "$HAP_AUDIT_DIR/INPUT_SHA256SUMS"
export HAP_AUDIT_INPUT_MANIFEST_SHA256
HAP_AUDIT_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_AUDIT_DIR/INPUT_SHA256SUMS" | awk '{print $1}')"
(cd / && sha256sum -c --strict \
    "$HAP_AUDIT_DIR/INPUT_SHA256SUMS")
input_sha_precheck=1

cd "$ROOT"
set +e
vivado_invoked=1
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl \
    -log "$HAP_AUDIT_DIR/vivado.log" \
    -journal "$HAP_AUDIT_DIR/vivado.jou"
vivado_exit_code=$?
set -e
vivado_rc="$vivado_exit_code"
(cd / && sha256sum -c --strict \
    "$HAP_AUDIT_DIR/INPUT_SHA256SUMS") && {
    input_sha_postcheck=1
} || {
    vivado_rc=90
    input_sha_postcheck=0
}
if [[ "$(sha256sum -- "$HAP_AUDIT_DIR/INPUT_SHA256SUMS" | \
        awk '{print $1}')" == "$HAP_AUDIT_INPUT_MANIFEST_SHA256" ]]; then
    input_manifest_sha_match=1
else
    vivado_rc=91
fi
write_audit_launcher_status "$vivado_rc"
if [[ "$vivado_rc" -ne 0 ]]; then
    printf 'independent V5 audit failed (rc=%d): %s\n' \
        "$vivado_rc" "$HAP_AUDIT_DIR" >&2
    exit "$vivado_rc"
fi

check_bufg_summary_schema() {
    awk -F= '
        BEGIN {
            split("bufg_family_total real_bufg_total clock_bufg data_bufg real_bufg_bad_connections bufg_gt_total bufg_gt_clock bufg_gt_data bufg_gt_sync_total bufg_gt_sync_clk_without_clock bufg_gt_sync_cesync_leaf_loads bufg_gt_sync_clrsync_leaf_loads bufg_gt_sync_bad_connections production_core_bufg_gt_sync bufg_partition_ok bufg_gt_sync_topology_ok bufg_topology_ok", fields, " ")
            for (i in fields) required[fields[i]] = 1
        }
        $1 in required {
            count[$1]++
            if ($2 !~ /^[0-9]+$/) bad = 1
            value[$1] = $2 + 0
        }
        END {
            for (key in required) if (count[key] != 1) bad = 1
            if (value["bufg_family_total"] != \
                    value["real_bufg_total"] + value["bufg_gt_sync_total"])
                bad = 1
            if (value["real_bufg_total"] != \
                    value["clock_bufg"] + value["data_bufg"])
                bad = 1
            if (value["bufg_gt_total"] != \
                    value["bufg_gt_clock"] + value["bufg_gt_data"])
                bad = 1
            if (value["bufg_gt_total"] < 1 || \
                    value["bufg_gt_sync_total"] < 1 || \
                    value["bufg_gt_sync_cesync_leaf_loads"] < \
                        value["bufg_gt_sync_total"] || \
                    value["bufg_gt_sync_clrsync_leaf_loads"] < \
                        value["bufg_gt_sync_total"])
                bad = 1
            exit bad ? 1 : 0
        }' "$1"
}

for required in summary.txt post_route_gate_summary.txt timing_post_route.rpt \
    route_status_post_route.rpt drc_post_route.rpt congestion_post_route.rpt \
    bufg_topology_post_route.txt \
    selectors_post_route.txt attention_geometry_post_route.txt \
    attention_geometry_placement_post_route.txt \
    base_pblocks_post_route.txt p5_input_plan_post_route.txt \
    p5_input_pblocks_post_route.txt \
    p6_postprocess_plan_post_route.txt \
    p6_postprocess_pblocks_post_route.txt \
    architecture_boundaries_post_route.txt \
    exceptions_coverage_post_route.rpt exceptions_valid_post_route.xdc \
    exceptions_merged_post_route.xdc utilization_post_route.rpt \
    utilization_hier_post_route.rpt utilization_slr_post_route.rpt \
    clock_interaction_post_route.rpt clock_utilization_post_route.rpt \
    cdc_post_route.rpt launcher_status.txt vivado.log vivado.jou \
    INPUT_FILES INPUT_SHA256SUMS; do
    [[ -s "$HAP_AUDIT_DIR/$required" ]] || {
        printf 'missing or empty independent V5 audit output: %s\n' "$required" >&2
        exit 1
    }
done
grep -Fqx 'status=PASS' "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx 'final_exit_code=0' "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx 'vivado_exit_code=0' "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx 'vivado_invoked=1' "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx 'input_sha_precheck=1' "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx 'input_sha_postcheck=1' "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx 'input_manifest_sha_match=1' \
    "$HAP_AUDIT_DIR/launcher_status.txt"
grep -Fqx "input_manifest_sha256=$HAP_AUDIT_INPUT_MANIFEST_SHA256" \
    "$HAP_AUDIT_DIR/launcher_status.txt"
check_bufg_summary_schema "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'status=V5_BOARD_INDEPENDENT_AUDIT_PASS' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'audit_input_manifest_entries=10' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx "audit_input_manifest_sha256=$HAP_AUDIT_INPUT_MANIFEST_SHA256" \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'audit_input_manifests_verified=1' \
    "$HAP_AUDIT_DIR/summary.txt"
[[ "$(grep -c '^status=' "$HAP_AUDIT_DIR/summary.txt")" -eq 1 ]]
grep -Fqx 'post_route_gate_status=V5_BOARD_POST_ROUTE_PASS' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'status=V5_BOARD_POST_ROUTE_PASS' \
    "$HAP_AUDIT_DIR/post_route_gate_summary.txt"
[[ "$(grep -c '^status=' \
    "$HAP_AUDIT_DIR/post_route_gate_summary.txt")" -eq 1 ]]
grep -Fqx 'dsp48e2=5453' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'mlp_kernel_dsp48e2=3072' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'uram288=752' "$HAP_AUDIT_DIR/summary.txt"
for exact in raw_weight_push_loads=37 \
    weight_data_capture_contract=32x256 weight_data_capture_nets=32 \
    weight_data_capture_loads=256/256 \
    weight_meta_capture_contract=2x256 weight_meta_capture_nets=2 \
    weight_meta_capture_loads=256/256 \
    weight_group_capture_contract=2x7 weight_group_capture_nets=2 \
    weight_group_capture_loads=7/7 projection_weight_capture_ok=1; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/post_route_gate_summary.txt"
done
for exact in mlp_local_clear_ff=2 mlp_local_clear_protected_ff=2 \
    branch0_local_clear_ff=1 branch1_local_clear_ff=1 \
    'branch0_local_clear_slr=1 0 0' \
    'branch1_local_clear_slr=0 0 1' mlp_local_clear_wrong_slr=0 \
    mlp_central_clear_ff=1 mlp_central_clear_branch_endpoints=2 \
    mlp_central_clear_direct_branch_state=0 \
    swiglu_local_clear_ff=8 swiglu_local_clear_protected_ff=8 \
    swiglu_control_clear_ff=1 swiglu_hadamard_clear_ff=1 \
    swiglu_quantizer_clear_ff=4 swiglu_row_clear_ff=2 \
    swiglu_direct_clear_bypass_state=0 \
    metadata_leaf_instances=4 metadata_local_wr_en_ff=4 \
    metadata_local_wr_addr_ff=70 metadata_local_wr_data_ff=896 \
    metadata_local_write_protected_ff=970 \
    'metadata_local_write_leaf_counts=243 243 242 242' \
    'metadata_local_write_leaf_slr_counts={243 0 0} {0 0 243} {0 242 0} {0 242 0}' \
    metadata_local_write_wrong_slr=0 \
    mlp_capture_leaf_instances=1632 mlp_capture_leaf_lut1=1632 \
    'mlp_capture_leaf_branch_instances=816 816' \
    'mlp_capture_leaf_branch_lut1=816 816' \
    'mlp_capture_leaf_branch_slr_counts={816 0 0} {0 0 816}' \
    mlp_capture_leaf_wrong_slr=0 architecture_boundary_ok=1; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/post_route_gate_summary.txt"
    grep -Fqx "$exact" \
        "$HAP_AUDIT_DIR/architecture_boundaries_post_route.txt"
done
grep -Fqx 'status=V5_BOARD_ARCHITECTURE_BOUNDARIES_PASS' \
    "$HAP_AUDIT_DIR/architecture_boundaries_post_route.txt"
grep -Fqx 'cdc_critical=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'route_clean=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'drc_errors=0' "$HAP_AUDIT_DIR/summary.txt"
for exact in no_clock_endpoints=0 unconstrained_paths=0 \
    timing_coverage_ok=1; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/post_route_gate_summary.txt"
done
grep -Fqx 'data_bufg=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'real_bufg_bad_connections=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'bufg_gt_data=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'bufg_gt_sync_clk_without_clock=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'bufg_gt_sync_bad_connections=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'production_core_bufg_gt_sync=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'bufg_partition_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'bufg_gt_sync_topology_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'bufg_topology_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'congestion_level6_or_higher_windows=0' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'exception_scope_policy_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'live_post_route_rediscovery_ok=1' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'base_contract_variant=P2_COHORT16_COL2_12_2' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_contract=P5_INPUT_HALF_LOCAL_8_8' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'region2_variant=rowsplit_y5_y6_y6_y8' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_contract_variant=P2_COHORT16_COL2_12_2' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_contract_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_require_placed=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_count=27' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'canonical_pblock_count=11' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'geometry_pblock_count=12' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_added_pblock_count=2' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_added_pblock_count=2' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'total_pblock_count=27' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'completed_u8_ff=4096' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'completed_meta_ff=352' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'input_capture_ff=12288' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'input_capture_controls=48' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_center_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_outer_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_center_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_outer_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_slr0_row_primitives=10696' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_center_row_primitives=21392' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p6_slr2_row_primitives=10696' "$HAP_AUDIT_DIR/summary.txt"
for exact in p7_region2_rows0_3_primitives=26800 \
    p7_region2_rows4_7_primitives=26800 \
    p7_region2_residual_primitives=15199 \
    p7_region2_rows0_3_dsp48e2=272 \
    p7_region2_rows4_7_dsp48e2=272 \
    p7_region2_residual_dsp48e2=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
done
grep -Fqx 'physical_placement_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_dsp_coverage=5453' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_uram_coverage=752' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'wrong_slr_primitives=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'physical_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'floorplan_contract_ok=1' "$HAP_AUDIT_DIR/summary.txt"
for exact in \
    outer0_dsp48e2=1538 outer2_dsp48e2=1538 \
    outer0_ramb36e2=102 outer2_ramb36e2=102 \
    base_contract_variant=P2_COHORT16_COL2_12_2 \
    p5_contract=P5_INPUT_HALF_LOCAL_8_8 \
    p6_contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4 \
    p7_contract=P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8 \
    region2_variant=rowsplit_y5_y6_y6_y8 \
    'projected_slr_dsp48e2=1862 1781 1810' \
    'projected_slr_uram288=224 224 304' \
    slr0_dsp48e2=1862 slr1_dsp48e2=1781 slr2_dsp48e2=1810 \
    slr0_uram288=224 slr1_uram288=224 slr2_uram288=304; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_SELECTORS_PASS \
    contract_variant=P2_COHORT16_COL2_12_2 total_dsp=5453 total_uram=752 \
    outer0_dsp=1538 outer2_dsp=1538 \
    outer0_ramb36=102 outer2_ramb36=102 move0=16 center_lanes=96 \
    move2=16 planned_slr0_dsp=1862 planned_slr1_dsp=1781 \
    planned_slr2_dsp=1810; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/selectors_post_route.txt"
done
[[ "$(grep -c '^status=' \
    "$HAP_AUDIT_DIR/selectors_post_route.txt")" -eq 1 ]]
for exact in status=V5_BOARD_POST_ROUTE_GEOMETRY_PASS \
    region0_input_primitives=3136 region3_input_primitives=2112 \
    owner_region2_weight_primitives=2048 \
    center_region1_bisect_exact_cover=1 \
    center_region1_dsp_stripe_exact_cover=1 \
    center_region2_rows0_3_primitives=26800 \
    center_region2_rows0_3_primitives_dsp48e2=272 \
    center_region2_rows4_7_primitives=26800 \
    center_region2_rows4_7_primitives_dsp48e2=272 \
    center_region2_residual_primitives=15199 \
    center_region2_residual_primitives_dsp48e2=0 \
    center_region2_row_exact_cover=1 \
    owner_region0_input_exact_cover=1 owner_region3_input_exact_cover=1 \
    owner_region2_weight_exact_cover=1 region3_weight_owner_residency_ok=1; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/attention_geometry_post_route.txt"
done
[[ "$(grep -c '^status=' \
    "$HAP_AUDIT_DIR/attention_geometry_post_route.txt")" -eq 1 ]]
for exact in status=V5_BOARD_POST_ROUTE_GEOMETRY_PLACEMENT_PASS ok=1 \
    wrong_total=0 unplaced_total=0 'slr_dsp=272 1696 272'; do
    grep -Fqx "$exact" \
        "$HAP_AUDIT_DIR/attention_geometry_placement_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_BASE_PBLOCKS_PASS ok=1 \
    require_placed=1 contract_variant=P2_COHORT16_COL2_12_2 \
    pblock_count=11 \
    dsp_coverage=5453 uram_coverage=752 placed_wrong=0 \
    pb_v5_mlp_branch_slr0_dsp=1538 \
    pb_v5_mlp_branch_slr0_ramb36=102 \
    pb_v5_mlp_branch_slr0_missing=0 \
    pb_v5_mlp_branch_slr0_placed_wrong=0 \
    pb_v5_mlp_branch_slr2_dsp=1538 \
    pb_v5_mlp_branch_slr2_ramb36=102 \
    pb_v5_mlp_branch_slr2_missing=0 \
    pb_v5_mlp_branch_slr2_placed_wrong=0 \
    pb_v5_attention_row_kv_cache_slr0_dsp=52 \
    pb_v5_attention_row_kv_cache_slr0_uram=0 \
    pb_v5_attention_row_kv_cache_slr0_ramb36=88 \
    pb_v5_attention_row_kv_cache_slr0_ramb18=2 \
    pb_v5_attention_row_kv_cache_slr0_missing=0 \
    pb_v5_attention_row_kv_cache_slr0_placed_wrong=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/base_pblocks_post_route.txt"
done
[[ "$(grep -c '^status=' \
    "$HAP_AUDIT_DIR/base_pblocks_post_route.txt")" -eq 1 ]]
for exact in status=V5_BOARD_POST_ROUTE_P5_INPUT_PLAN_PASS \
    contract=P5_INPUT_HALF_LOCAL_8_8 quantizer_count=4 cache_count=2 \
    hadamard_count=1 completed_u8_ff=4096 completed_meta_ff=352 \
    input_capture_ff=12288 capture_leaf_count=48 center_canonical_overlap=8; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p5_input_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P5_INPUT_PBLOCKS_PASS ok=1 \
    require_placed=1 pblock_count=2 center_missing=0 \
    center_outer_overlap=0 center_wrong=0 outer_wrong=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p5_input_pblocks_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P6_POSTPROCESS_PLAN_PASS \
    contract=P6_POSTPROCESS_GROUP4_SPLIT_4_8_4 row_bank_count=16 \
    all_row_primitives=42784 slr0_row_primitives=10696 \
    center_row_primitives=21392 slr2_row_primitives=10696 \
    per_row_primitives=2674 per_row_lut=994 per_row_ff=1536; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p6_postprocess_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P6_POSTPROCESS_PBLOCKS_PASS ok=1 \
    require_placed=1 pblock_count=2 center_missing=0 \
    center_outer_overlap=0 center_wrong=0 outer_wrong=0 \
    slr0_target=0 slr0_missing=0 slr0_wrong=0 \
    slr2_target=2 slr2_missing=0 slr2_wrong=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p6_postprocess_pblocks_post_route.txt"
done
awk -F= '/^wns_ns=|^whs_ns=/{if ($2 < 0) exit 1; n++} END{exit n==2?0:1}' \
    "$HAP_AUDIT_DIR/summary.txt"
awk -F= '/^slr[012]_dsp48e2=/{if ($2 > 2280) exit 1; n++} END{exit n==3?0:1}' \
    "$HAP_AUDIT_DIR/summary.txt"
(cd / && sha256sum -c --strict "$HAP_AUDIT_DIR/INPUT_SHA256SUMS")
[[ "$(sha256sum -- "$HAP_AUDIT_DIR/INPUT_SHA256SUMS" | awk '{print $1}')" \
    == "$HAP_AUDIT_INPUT_MANIFEST_SHA256" ]]
archive_audit_outputs
cat "$HAP_AUDIT_DIR/summary.txt"
printf '%s\n' "$HAP_AUDIT_DIR"
