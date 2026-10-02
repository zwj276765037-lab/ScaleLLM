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
BOARD_SUMMARY="$(dirname "$HAP_DCP")/summary.txt"
[[ -s "$BOARD_SUMMARY" ]] || {
    printf 'missing board summary for independent audit: %s\n' \
        "$BOARD_SUMMARY" >&2
    exit 2
}
unique_board_value() {
    local key="$1" values
    mapfile -t values < <(sed -n "s/^${key}=//p" "$BOARD_SUMMARY")
    [[ "${#values[@]}" -eq 1 && -n "${values[0]}" ]] || return 1
    printf '%s\n' "${values[0]}"
}
export HAP_BOARD_RTL_VARIANT="$(unique_board_value rtl_variant)"
export HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES="$(
    unique_board_value p9_quantizer3_primitives)"
export HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES="$(
    unique_board_value p14_region2_relief_primitives)"
[[ "$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" =~ ^[1-9][0-9]*$ &&
   "$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" =~ ^[1-9][0-9]*$ ]] || exit 2
SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P9_POST_LIB="$ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
P8_BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
AUDIT_PHYSICAL_EXTRA_INPUTS=()
case "$HAP_BOARD_RTL_VARIANT" in
    P14_LEGACY)
        GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
        P9_QUANTIZER3_LIB="$ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
        P14_RELIEF_LIB="$ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
        HAP_AUDIT_EXPECTED_INPUT_COUNT=14
        HAP_BOARD_EXPECTED_TOTAL_DSP=5453
        HAP_BOARD_EXPECTED_SLR1_DSP=1781
        HAP_BOARD_EXPECTED_PROJECTED_SLR_DSP='1862 1781 1810'
        HAP_BOARD_EXPECTED_REGION2_ROWS0_3_PRIMITIVES=26800
        HAP_BOARD_EXPECTED_REGION2_ROWS4_7_PRIMITIVES=26800
        HAP_BOARD_EXPECTED_REGION2_RESIDUAL_PRIMITIVES=15199
        ;;
    P16_NOCLIP)
        GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_p16_bound_floorplan.tcl"
        P9_QUANTIZER3_LIB="$ROOT/vivado/scripts/v5_production_p16_noclip_quantizer3_locality_floorplan.tcl"
        P14_RELIEF_LIB="$ROOT/vivado/scripts/v5_production_p16_noclip_region2_x2_relief_floorplan.tcl"
        P16_ADAPTER="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_p16_floorplan.tcl"
        BASE_GEOMETRY="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
        P9_QUANTIZER3_BASE="$ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
        P14_RELIEF_BASE="$ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
        export HAP_P16_POST_OPT_SUMMARY="$(readlink -e -- "$(
            unique_board_value p16_post_opt_summary)")"
        export HAP_P16_POST_OPT_SUMMARY_SHA256="$(
            unique_board_value p16_post_opt_summary_sha256)"
        [[ -s "$HAP_P16_POST_OPT_SUMMARY" &&
           "$HAP_P16_POST_OPT_SUMMARY_SHA256" =~ ^[0-9a-f]{64}$ &&
           "$(sha256sum -- "$HAP_P16_POST_OPT_SUMMARY" | awk '{print $1}')" == \
                "$HAP_P16_POST_OPT_SUMMARY_SHA256" ]] || exit 2
        export HAP_P16_PRODUCTION_REGION2_SUMMARY="$(readlink -e -- "$(
            unique_board_value p16_production_region2_summary)")"
        export HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256="$(
            unique_board_value p16_production_region2_summary_sha256)"
        export HAP_P16_PRODUCTION_DCP_SHA256="$(
            unique_board_value p16_production_dcp_sha256)"
        [[ -s "$HAP_P16_PRODUCTION_REGION2_SUMMARY" &&
           "$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" =~ ^[0-9a-f]{64}$ &&
           "$HAP_P16_PRODUCTION_DCP_SHA256" =~ ^[0-9a-f]{64}$ &&
           "$(sha256sum -- "$HAP_P16_PRODUCTION_REGION2_SUMMARY" | \
                awk '{print $1}')" == \
                "$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" ]] || exit 2
        AUDIT_PHYSICAL_EXTRA_INPUTS=("$P16_ADAPTER" "$BASE_GEOMETRY"
            "$P9_QUANTIZER3_BASE" "$P14_RELIEF_BASE"
            "$HAP_P16_POST_OPT_SUMMARY"
            "$HAP_P16_PRODUCTION_REGION2_SUMMARY")
        HAP_AUDIT_EXPECTED_INPUT_COUNT=20
        HAP_BOARD_EXPECTED_TOTAL_DSP=5449
        HAP_BOARD_EXPECTED_SLR1_DSP=1777
        HAP_BOARD_EXPECTED_PROJECTED_SLR_DSP='1862 1777 1810'
        unique_board_summary="$HAP_P16_PRODUCTION_REGION2_SUMMARY"
        unique_post_opt_value() {
            local key="$1" values
            mapfile -t values < <(sed -n "s/^${key}=//p" \
                "$unique_board_summary")
            [[ "${#values[@]}" -eq 1 && -n "${values[0]}" ]] || return 1
            printf '%s\n' "${values[0]}"
        }
        HAP_BOARD_EXPECTED_REGION2_ROWS0_3_PRIMITIVES="$(
            unique_post_opt_value region2_rows0_3_primitives)"
        HAP_BOARD_EXPECTED_REGION2_ROWS4_7_PRIMITIVES="$(
            unique_post_opt_value region2_rows4_7_primitives)"
        HAP_BOARD_EXPECTED_REGION2_RESIDUAL_PRIMITIVES="$(
            unique_post_opt_value region2_residual_primitives)"
        ;;
    *)
        printf 'unsupported independent-audit RTL variant: %s\n' \
            "$HAP_BOARD_RTL_VARIANT" >&2
        exit 2
        ;;
esac
for value in "$HAP_BOARD_EXPECTED_TOTAL_DSP" \
        "$HAP_BOARD_EXPECTED_SLR1_DSP" \
        "$HAP_BOARD_EXPECTED_REGION2_ROWS0_3_PRIMITIVES" \
        "$HAP_BOARD_EXPECTED_REGION2_ROWS4_7_PRIMITIVES" \
        "$HAP_BOARD_EXPECTED_REGION2_RESIDUAL_PRIMITIVES"; do
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || exit 2
done
export HAP_BOARD_EXPECTED_TOTAL_DSP HAP_BOARD_EXPECTED_SLR1_DSP
export HAP_BOARD_EXPECTED_PROJECTED_SLR_DSP
export HAP_BOARD_EXPECTED_REGION2_ROWS0_3_PRIMITIVES
export HAP_BOARD_EXPECTED_REGION2_ROWS4_7_PRIMITIVES
export HAP_BOARD_EXPECTED_REGION2_RESIDUAL_PRIMITIVES
export HAP_AUDIT_EXPECTED_INPUT_COUNT
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
        "rtl_variant=$HAP_BOARD_RTL_VARIANT" \
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
    "$HAP_DCP" "$HAP_BITSTREAM" "$HAP_XDC_INVENTORY" "$BOARD_SUMMARY"
    "$ROOT/vivado/scripts/audit_attention_mlp_vcu118_v5_post_route.tcl"
    "$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
    "$SELECTOR_LIB"
    "$GEOMETRY_LIB"
    "$P5_LIB"
    "$P9_POST_LIB"
    "$P9_QUANTIZER3_LIB"
    "$P14_RELIEF_LIB"
    "$P8_BOUNDARY_LIB"
    "${AUDIT_PHYSICAL_EXTRA_INPUTS[@]}"
    "$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_post_route_audit.sh"
)
[[ "${#INPUTS[@]}" -eq "$HAP_AUDIT_EXPECTED_INPUT_COUNT" ]]
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
    p9_postprocess_plan_post_route.txt \
    p9_postprocess_pblocks_post_route.txt \
    p9_quantizer3_plan_post_route.txt p9_quantizer3_pblock_post_route.txt \
    p14_region2_relief_plan_post_route.txt \
    p14_region2_relief_pblock_post_route.txt \
    p8_parent_ingress_boundary_post_route.txt \
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
grep -Fqx "rtl_variant=$HAP_BOARD_RTL_VARIANT" \
    "$HAP_AUDIT_DIR/launcher_status.txt"
check_bufg_summary_schema "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'status=V5_BOARD_INDEPENDENT_AUDIT_PASS' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx "audit_input_manifest_entries=$HAP_AUDIT_EXPECTED_INPUT_COUNT" \
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
grep -Fqx "dsp48e2=$HAP_BOARD_EXPECTED_TOTAL_DSP" \
    "$HAP_AUDIT_DIR/summary.txt"
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
grep -Fqx 'p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p14_region2_relief_contract=P14_ATTN_REGION2_SHARED_X0_X2' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_contract_variant=P2_COHORT16_COL2_12_2' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_contract_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_require_placed=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'pblock_count=26' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'canonical_pblock_count=11' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'geometry_pblock_count=10' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_added_pblock_count=2' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_added_pblock_count=2' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p9_quantizer3_added_pblock_count=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p14_region2_relief_added_pblock_count=0' \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'total_pblock_count=26' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'completed_u8_ff=4096' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'completed_meta_ff=352' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'input_capture_ff=12288' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'input_capture_controls=48' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_center_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p5_outer_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_center_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_outer_wrong_slr=0' "$HAP_AUDIT_DIR/summary.txt"
for exact in p9_slr0_row_primitives=16044 \
    p9_center_row_primitives=10696 p9_slr2_row_primitives=16044 \
    "p9_quantizer3_primitives=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    p9_quantizer3_grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6 \
    p9_quantizer3_wrong_region=0 p9_quantizer3_unplaced=0 \
    "p14_region2_relief_primitives=$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" \
    p14_region2_relief_base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
    p14_region2_relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9 \
    p14_region2_expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9 \
    p14_region2_relief_wrong=0 p14_region2_relief_unplaced=0 \
    parent_head_ff=6560 parent_tail_ff=6560 parent_count_ff=2 \
    parent_count_replica_equivalence_ok=1 parent_pointer_ff=0 \
    local_clear_shared_upstream_ready_paths=0 \
    branch_credit_shared_upstream_ready_paths=0 \
    local_clear_gate_compute_ready_paths=0 \
    branch_credit_gate_compute_ready_paths=0 \
    local_clear_down_compute_ready_paths=0 \
    branch_credit_down_compute_ready_paths=0 \
    local_clear_input_cache_ready_paths=0 \
    branch_credit_input_cache_ready_paths=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
done
grep -Fqx "rtl_variant=$HAP_BOARD_RTL_VARIANT" \
    "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx "rtl_resource_variant=$HAP_BOARD_RTL_VARIANT" \
    "$HAP_AUDIT_DIR/summary.txt"
if [[ "$HAP_BOARD_RTL_VARIANT" == P16_NOCLIP ]]; then
    for exact in \
        "region2_signature_source=P16_PRODUCTION_POST_OPT_SHA256:$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" \
        "p16_post_opt_summary=$HAP_P16_POST_OPT_SUMMARY" \
        "p16_post_opt_summary_sha256=$HAP_P16_POST_OPT_SUMMARY_SHA256" \
        "p16_production_region2_summary=$HAP_P16_PRODUCTION_REGION2_SUMMARY" \
        "p16_production_region2_summary_sha256=$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" \
        "p16_production_dcp_sha256=$HAP_P16_PRODUCTION_DCP_SHA256"; do
        grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
    done
fi
grep -Fqx 'physical_placement_ok=1' "$HAP_AUDIT_DIR/summary.txt"
grep -Fqx "pblock_dsp_coverage=$HAP_BOARD_EXPECTED_TOTAL_DSP" \
    "$HAP_AUDIT_DIR/summary.txt"
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
    p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6 \
    p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
    p14_region2_relief_contract=P14_ATTN_REGION2_SHARED_X0_X2 \
    "projected_slr_dsp48e2=$HAP_BOARD_EXPECTED_PROJECTED_SLR_DSP" \
    'projected_slr_uram288=224 224 304' \
    slr0_dsp48e2=1862 \
    "slr1_dsp48e2=$HAP_BOARD_EXPECTED_SLR1_DSP" slr2_dsp48e2=1810 \
    slr0_uram288=224 slr1_uram288=224 slr2_uram288=304; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/summary.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_SELECTORS_PASS \
    "contract_variant=P2_COHORT16_COL2_12_2 total_dsp=$HAP_BOARD_EXPECTED_TOTAL_DSP total_uram=752" \
    outer0_dsp=1538 outer2_dsp=1538 \
    outer0_ramb36=102 outer2_ramb36=102 move0=16 center_lanes=96 \
    move2=16 planned_slr0_dsp=1862 \
    "planned_slr1_dsp=$HAP_BOARD_EXPECTED_SLR1_DSP" \
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
    "center_region2_rows0_3_primitives=$HAP_BOARD_EXPECTED_REGION2_ROWS0_3_PRIMITIVES" \
    center_region2_rows0_3_primitives_dsp48e2=272 \
    "center_region2_rows4_7_primitives=$HAP_BOARD_EXPECTED_REGION2_ROWS4_7_PRIMITIVES" \
    center_region2_rows4_7_primitives_dsp48e2=272 \
    "center_region2_residual_primitives=$HAP_BOARD_EXPECTED_REGION2_RESIDUAL_PRIMITIVES" \
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
    "dsp_coverage=$HAP_BOARD_EXPECTED_TOTAL_DSP" \
    uram_coverage=752 placed_wrong=0 \
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
for exact in status=V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PLAN_PASS \
    contract=P9_POSTPROCESS_SPLIT_6_4_6 row_bank_count=16 \
    all_row_primitives=42784 slr0_row_primitives=16044 \
    center_row_primitives=10696 slr2_row_primitives=16044 \
    per_row_primitives=2674 per_row_lut=994 per_row_ff=1536; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p9_postprocess_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PBLOCKS_PASS ok=1 \
    require_placed=1 pblock_count=2 center_missing=0 \
    center_outer_overlap=0 center_wrong=0 outer_wrong=0 \
    slr0_target=0 slr0_missing=0 slr0_wrong=0 \
    slr2_target=2 slr2_missing=0 slr2_wrong=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p9_postprocess_pblocks_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PLAN_PASS \
    contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
    "primitive_count=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p9_quantizer3_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PBLOCK_PASS ok=1 \
    require_placed=1 contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
    "expected=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    "members=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    missing=0 extras=0 wrong=0 unplaced=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p9_quantizer3_pblock_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PLAN_PASS \
    contract=P14_ATTN_REGION2_SHARED_X0_X2 \
    "primitive_count=$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" \
    base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
    relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9 \
    expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p14_region2_relief_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PBLOCK_PASS \
    ok=1 contract=P14_ATTN_REGION2_SHARED_X0_X2 require_placed=1 \
    "primitive_count=$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" \
    missing=0 wrong=0 unplaced=0; do
    grep -Fqx "$exact" "$HAP_AUDIT_DIR/p14_region2_relief_pblock_post_route.txt"
done
awk -F= -v maximum="$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" '
    $1 == "relief_placed" {
        count++
        if ($2 !~ /^[0-9]+$/ || $2 + 0 > maximum) bad=1
    }
    END {exit count == 1 && !bad ? 0 : 1}
' "$HAP_AUDIT_DIR/p14_region2_relief_pblock_post_route.txt"
for exact in status=V5_BOARD_POST_ROUTE_P8_PARENT_INGRESS_BOUNDARY_PASS \
    ok=1 parent_head_ff=6560 parent_tail_ff=6560 parent_count_ff=2 \
    parent_count_replica_equivalence_ok=1 parent_pointer_ff=0 \
    local_clear_shared_upstream_ready_paths=0 \
    branch_credit_shared_upstream_ready_paths=0 \
    local_clear_gate_compute_ready_paths=0 \
    branch_credit_gate_compute_ready_paths=0 \
    local_clear_down_compute_ready_paths=0 \
    branch_credit_down_compute_ready_paths=0 \
    local_clear_input_cache_ready_paths=0 \
    branch_credit_input_cache_ready_paths=0; do
    grep -Fqx "$exact" \
        "$HAP_AUDIT_DIR/p8_parent_ingress_boundary_post_route.txt"
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
