#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIVADO="${VIVADO:-/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado}"
export HAP_JOBS="${HAP_JOBS:-32}"
[[ "$HAP_JOBS" =~ ^[0-9]+$ ]] &&
    (( HAP_JOBS >= 1 && HAP_JOBS <= 32 )) || {
    printf 'HAP_JOBS must be an integer in 1..32: %q\n' "$HAP_JOBS" >&2
    exit 2
}
PROVENANCE_LIB="$ROOT/vivado/scripts/v5_board_build_provenance.sh"
[[ -s "$PROVENANCE_LIB" ]] || {
    printf 'missing V5 board provenance library: %s\n' "$PROVENANCE_LIB" >&2
    exit 2
}
source "$PROVENANCE_LIB"
if [[ $# -ne 1 ]]; then
    printf 'usage: %s V5_PRODUCTION_OOC_ROUTE_PASS_ARTIFACT_DIR\n' "$0" >&2
    exit 2
fi
requested_ooc_route="$1"
STAMP="$(date +%Y%m%d_%H%M%S)"
export HAP_PROJECT_FILE="${HAP_PROJECT_FILE:-$ROOT/vivado/project/attention_mlp_vcu118_v5_dual_ddr/attention_mlp_vcu118_v5_dual_ddr.xpr}"
export HAP_REPORT_DIR="${HAP_REPORT_DIR:-$ROOT/vivado/reports/attention_mlp_vcu118_v5_bitstream_$STAMP}"
HAP_REPORT_DIR="$(readlink -m -- "$HAP_REPORT_DIR")"
export HAP_REPORT_DIR
[[ ! -e "$HAP_REPORT_DIR" ]] || {
    printf 'V5 board bitstream evidence directory already exists: %s\n' \
        "$HAP_REPORT_DIR" >&2
    exit 2
}
mapfile -t active_batch < <(pgrep -u "$(id -u)" -af \
    '[u]nwrapped/lnx64.o/vivado .*[-]mode batch' || true)
if [[ "${#active_batch[@]}" -ne 0 ]]; then
    printf 'another batch Vivado is active; V5 board bitstream not started:\n' >&2
    printf '  %s\n' "${active_batch[@]}" >&2
    exit 75
fi
HAP_OOC_ROUTE_DIR="$(readlink -e -- "$requested_ooc_route")" || {
    printf 'missing OOC route authorization artifact: %s\n' "$1" >&2
    exit 2
}
export HAP_OOC_ROUTE_DIR
hap_v5_verify_ooc_route_artifact "$HAP_OOC_ROUTE_DIR"
OOC_ROUTE_SUMMARY="$HAP_OOC_ROUTE_DIR/summary.txt"
mapfile -t route_variant_rows < <(sed -n 's/^rtl_variant=//p' \
    "$OOC_ROUTE_SUMMARY")
if [[ "${#route_variant_rows[@]}" -eq 0 ]]; then
    export HAP_BOARD_RTL_VARIANT=P14_LEGACY
elif [[ "${#route_variant_rows[@]}" -eq 1 &&
        -n "${route_variant_rows[0]}" ]]; then
    export HAP_BOARD_RTL_VARIANT="${route_variant_rows[0]}"
else
    printf 'OOC route rtl_variant is empty or duplicated\n' >&2
    exit 2
fi
hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" p9_quantizer3_primitives \
    "OOC route summary" HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES
hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" p14_region2_relief_primitives \
    "OOC route summary" HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES
export HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES
export HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES
[[ "$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" =~ ^[1-9][0-9]*$ &&
   "$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" =~ ^[1-9][0-9]*$ ]] || exit 2

SELECTOR_LIB="$ROOT/vivado/scripts/v5_production_floorplan_selectors.tcl"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P9_POST_LIB="$ROOT/vivado/scripts/v5_production_p9_postprocess_partition_floorplan.tcl"
P8_BOUNDARY_LIB="$ROOT/vivado/scripts/audit_mlp_p8_parent_ingress_boundary_replica_aware.tcl"
BOARD_PHYSICAL_EXTRA_INPUTS=()
case "$HAP_BOARD_RTL_VARIANT" in
    P14_LEGACY)
        GEOMETRY_LIB="$ROOT/vivado/scripts/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
        P9_QUANTIZER3_LIB="$ROOT/vivado/scripts/v5_production_p9_quantizer3_locality_floorplan.tcl"
        P14_RELIEF_LIB="$ROOT/vivado/scripts/v5_production_p14_region2_x2_relief_floorplan.tcl"
        HAP_BOARD_EXPECTED_INPUT_COUNT=134
        HAP_BOARD_EXPECTED_IMMUTABLE_INPUT_COUNT=133
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
        hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" p16_post_opt_summary \
            "P16 no-clip OOC route summary" HAP_P16_POST_OPT_SUMMARY
        hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" \
            p16_post_opt_summary_sha256 \
            "P16 no-clip OOC route summary" HAP_P16_POST_OPT_SUMMARY_SHA256
        HAP_P16_POST_OPT_SUMMARY="$(readlink -e -- \
            "$HAP_P16_POST_OPT_SUMMARY")"
        [[ -s "$HAP_P16_POST_OPT_SUMMARY" &&
           "$HAP_P16_POST_OPT_SUMMARY_SHA256" =~ ^[0-9a-f]{64}$ &&
           "$(sha256sum -- "$HAP_P16_POST_OPT_SUMMARY" | awk '{print $1}')" == \
                "$HAP_P16_POST_OPT_SUMMARY_SHA256" ]] || exit 2
        hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" \
            p16_production_region2_summary \
            "P16 no-clip OOC route summary" \
            HAP_P16_PRODUCTION_REGION2_SUMMARY
        hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" \
            p16_production_region2_summary_sha256 \
            "P16 no-clip OOC route summary" \
            HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256
        hap_v5_get_unique_value "$OOC_ROUTE_SUMMARY" \
            p16_production_dcp_sha256 \
            "P16 no-clip OOC route summary" HAP_P16_PRODUCTION_DCP_SHA256
        HAP_P16_PRODUCTION_REGION2_SUMMARY="$(readlink -e -- \
            "$HAP_P16_PRODUCTION_REGION2_SUMMARY")"
        [[ -s "$HAP_P16_PRODUCTION_REGION2_SUMMARY" &&
           "$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" =~ ^[0-9a-f]{64}$ &&
           "$HAP_P16_PRODUCTION_DCP_SHA256" =~ ^[0-9a-f]{64}$ &&
           "$(sha256sum -- "$HAP_P16_PRODUCTION_REGION2_SUMMARY" | \
                awk '{print $1}')" == \
                "$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" ]] || exit 2
        export HAP_P16_POST_OPT_SUMMARY HAP_P16_POST_OPT_SUMMARY_SHA256
        export HAP_P16_PRODUCTION_REGION2_SUMMARY
        export HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256
        export HAP_P16_PRODUCTION_DCP_SHA256
        BOARD_PHYSICAL_EXTRA_INPUTS=("$P16_ADAPTER" "$BASE_GEOMETRY"
            "$P9_QUANTIZER3_BASE" "$P14_RELIEF_BASE"
            "$HAP_P16_POST_OPT_SUMMARY"
            "$HAP_P16_PRODUCTION_REGION2_SUMMARY")
        HAP_BOARD_EXPECTED_INPUT_COUNT=140
        HAP_BOARD_EXPECTED_IMMUTABLE_INPUT_COUNT=139
        HAP_BOARD_EXPECTED_TOTAL_DSP=5449
        HAP_BOARD_EXPECTED_SLR1_DSP=1777
        HAP_BOARD_EXPECTED_PROJECTED_SLR_DSP='1862 1777 1810'
        hap_v5_get_unique_value "$HAP_P16_PRODUCTION_REGION2_SUMMARY" \
            region2_rows0_3_primitives "P16 production region2 summary" \
            HAP_BOARD_EXPECTED_REGION2_ROWS0_3_PRIMITIVES
        hap_v5_get_unique_value "$HAP_P16_PRODUCTION_REGION2_SUMMARY" \
            region2_rows4_7_primitives "P16 production region2 summary" \
            HAP_BOARD_EXPECTED_REGION2_ROWS4_7_PRIMITIVES
        hap_v5_get_unique_value "$HAP_P16_PRODUCTION_REGION2_SUMMARY" \
            region2_residual_primitives "P16 production region2 summary" \
            HAP_BOARD_EXPECTED_REGION2_RESIDUAL_PRIMITIVES
        ;;
    *)
        printf 'unsupported board RTL variant: %s\n' \
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
export HAP_BOARD_EXPECTED_INPUT_COUNT
export HAP_BOARD_EXPECTED_IMMUTABLE_INPUT_COUNT
export HAP_SOURCE_XDC_INVENTORY="$HAP_REPORT_DIR/XDC_SOURCE_INVENTORY"
export HAP_XDC_INVENTORY="$HAP_REPORT_DIR/XDC_ACTIVE_INVENTORY"
"$ROOT/vivado/scripts/check_attention_mlp_vcu118_v5_board_contract.sh"
[[ -x "$VIVADO" ]] || {
    printf 'Vivado 2025.2 executable is missing: %s\n' "$VIVADO" >&2
    exit 2
}
mkdir "$HAP_REPORT_DIR"

# From this point every exit preserves a dynamically complete evidence set.
# The Vivado project file is the only mutable input; all other inputs are
# frozen in a separate immutable manifest and checked after the long build.
vivado_exit_code=255
vivado_invoked=0
input_manifest_sha_match=0
immutable_input_postcheck=0
immutable_input_manifest_sha_match=0
recursive_source_post_build_sha_verified=0
ooc_route_authorization_post_build_verified=0
HAP_INPUT_MANIFEST_SHA256=""
HAP_IMMUTABLE_INPUT_MANIFEST_SHA256=""
HAP_BOARD_IMMUTABLE_INPUT_COUNT=0

archive_board_outputs() {
    local index
    local -a outputs=() current=() manifested=()
    mapfile -d '' outputs < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    [[ "${#outputs[@]}" -gt 0 ]] || return 1
    sha256sum -- "${outputs[@]}" > "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS"
    (cd / && sha256sum -c --strict \
        "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS" >/dev/null)
    mapfile -d '' current < <(find "$HAP_REPORT_DIR" -maxdepth 1 \
        -type f -size +0c ! -name OUTPUT_SHA256SUMS -print0 | sort -z)
    mapfile -t manifested < <(awk '{sub(/^[0-9a-f]{64}[[:space:]]+\*?/, ""); print}' \
        "$HAP_REPORT_DIR/OUTPUT_SHA256SUMS" | sort)
    [[ "${#current[@]}" -eq "${#manifested[@]}" ]] || return 1
    for index in "${!current[@]}"; do
        [[ "${current[$index]}" == "${manifested[$index]}" ]] || return 1
    done
}

write_board_launcher_status() {
    local final_rc="$1" status=FAIL generated=0
    [[ "$final_rc" -eq 0 ]] && status=PASS
    [[ -s "$HAP_REPORT_DIR/attention_mlp_vcu118_v5.bit" ]] && generated=1
    printf '%s\n' \
        "status=$status" \
        "final_exit_code=$final_rc" \
        "vivado_exit_code=$vivado_exit_code" \
        "vivado_invoked=$vivado_invoked" \
        "complete_input_manifest_sha256=$HAP_INPUT_MANIFEST_SHA256" \
        "complete_input_manifest_sha_match=$input_manifest_sha_match" \
        "immutable_input_count=$HAP_BOARD_IMMUTABLE_INPUT_COUNT" \
        "immutable_input_manifest_sha256=$HAP_IMMUTABLE_INPUT_MANIFEST_SHA256" \
        "immutable_input_manifest_sha_match=$immutable_input_manifest_sha_match" \
        "immutable_input_postcheck=$immutable_input_postcheck" \
        'project_file_postcheck_exempt=1' \
        "rtl_variant=$HAP_BOARD_RTL_VARIANT" \
        "recursive_source_post_build_sha_verified=$recursive_source_post_build_sha_verified" \
        "ooc_route_authorization_post_build_verified=$ooc_route_authorization_post_build_verified" \
        "bitstream_generated=$generated" \
        > "$HAP_REPORT_DIR/launcher_status.txt"
}

board_exit_archive() {
    local rc="$?"
    trap - EXIT
    write_board_launcher_status "$rc" || rc=96
    if ! archive_board_outputs; then
        [[ "$rc" -ne 0 ]] || rc=97
        write_board_launcher_status "$rc" || true
        archive_board_outputs || true
    fi
    exit "$rc"
}
trap board_exit_archive EXIT

[[ -s "$HAP_PROJECT_FILE" ]] || {
    printf 'missing V5 board project; run the V5 BD launcher first: %s\n' \
        "$HAP_PROJECT_FILE" >&2
    exit 2
}

"$ROOT/vivado/scripts/inventory_attention_mlp_vcu118_v5_xdc.sh" \
    "$ROOT" "$HAP_REPORT_DIR" "$HAP_SOURCE_XDC_INVENTORY"

BOARD_SOURCE_MANIFEST="$ROOT/vivado/manifests/attention_mlp_board_core_v5_sources.list"
hap_v5_expand_source_manifest "$ROOT" "$BOARD_SOURCE_MANIFEST" \
    SOURCE_MANIFESTS RTL_SOURCES SOURCE_CLOSURE
[[ "${#SOURCE_MANIFESTS[@]}" -eq 3 && "${#RTL_SOURCES[@]}" -eq 87 &&
    "${#SOURCE_CLOSURE[@]}" -eq 90 ]] || {
    printf 'V5 board recursive source closure drifted: manifests=%d sources=%d closure=%d\n' \
        "${#SOURCE_MANIFESTS[@]}" "${#RTL_SOURCES[@]}" \
        "${#SOURCE_CLOSURE[@]}" >&2
    exit 2
}
printf '%s\n' "${SOURCE_MANIFESTS[@]}" > \
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_MANIFEST_FILES"
printf '%s\n' "${RTL_SOURCES[@]}" > \
    "$HAP_REPORT_DIR/RECURSIVE_RTL_SOURCE_FILES"
printf '%s\n' "${SOURCE_CLOSURE[@]}" > \
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_CLOSURE_FILES"
sha256sum "${SOURCE_CLOSURE[@]}" > \
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS"
export HAP_BOARD_SOURCE_MANIFEST_COUNT="${#SOURCE_MANIFESTS[@]}"
export HAP_BOARD_RTL_SOURCE_COUNT="${#RTL_SOURCES[@]}"
export HAP_BOARD_SOURCE_CLOSURE_COUNT="${#SOURCE_CLOSURE[@]}"
export HAP_RECURSIVE_SOURCE_SHA_MANIFEST=\
"$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS"
export HAP_RECURSIVE_SOURCE_MANIFEST_SHA256
HAP_RECURSIVE_SOURCE_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_RECURSIVE_SOURCE_SHA_MANIFEST" | awk '{print $1}')"

mapfile -t OOC_ROUTE_AUTHORIZATION_FILES < <(
    printf '%s\n' \
        "$HAP_OOC_ROUTE_DIR/summary.txt" \
        "$HAP_OOC_ROUTE_DIR/selectors_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/attention_geometry_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/attention_geometry_placement_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/base_pblocks_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p5_input_plan_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p5_input_pblocks_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p9_postprocess_plan_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p9_postprocess_pblocks_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p9_quantizer3_plan_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p9_quantizer3_pblock_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p14_region2_relief_plan_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p14_region2_relief_pblock_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/p8_parent_ingress_boundary_input.txt" \
        "$HAP_OOC_ROUTE_DIR/p8_parent_ingress_boundary_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/architecture_boundaries_input.txt" \
        "$HAP_OOC_ROUTE_DIR/architecture_boundaries_post_route.txt" \
        "$HAP_OOC_ROUTE_DIR/launcher_status.txt" \
        "$HAP_OOC_ROUTE_DIR/INPUT_FILES" \
        "$HAP_OOC_ROUTE_DIR/INPUT_SHA256SUMS" \
        "$HAP_OOC_ROUTE_DIR/OUTPUT_SHA256SUMS" \
        "$HAP_OOC_ROUTE_DIR/post_route.dcp"
)
printf '%s\n' "${OOC_ROUTE_AUTHORIZATION_FILES[@]}" > \
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_FILES"
sha256sum "${OOC_ROUTE_AUTHORIZATION_FILES[@]}" > \
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS"
export HAP_OOC_ROUTE_AUTHORIZATION_SHA_MANIFEST=\
"$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS"
export HAP_OOC_ROUTE_AUTHORIZATION_MANIFEST_SHA256
HAP_OOC_ROUTE_AUTHORIZATION_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_OOC_ROUTE_AUTHORIZATION_SHA_MANIFEST" | awk '{print $1}')"

INPUTS=(
    "$HAP_PROJECT_FILE"
    "$HAP_SOURCE_XDC_INVENTORY"
    "$ROOT/vivado/constraints/attention_mlp_vcu118_board_v5.xdc"
    "$ROOT/vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl"
    "$ROOT/vivado/scripts/run_attention_mlp_vcu118_v5_bitstream.sh"
    "$ROOT/vivado/scripts/attention_mlp_vcu118_v5_post_route_gate.tcl"
    "$ROOT/vivado/scripts/write_attention_mlp_vcu118_v5_xdc_inventory.tcl"
    "$ROOT/vivado/scripts/apply_attention_mlp_vcu118_v5_floorplan.tcl"
    "$SELECTOR_LIB"
    "$GEOMETRY_LIB"
    "$P5_LIB"
    "$P9_POST_LIB"
    "$P9_QUANTIZER3_LIB"
    "$P14_RELIEF_LIB"
    "$P8_BOUNDARY_LIB"
    "${BOARD_PHYSICAL_EXTRA_INPUTS[@]}"
    "$PROVENANCE_LIB"
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_MANIFEST_FILES"
    "$HAP_REPORT_DIR/RECURSIVE_RTL_SOURCE_FILES"
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_CLOSURE_FILES"
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS"
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_FILES"
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS"
    "${SOURCE_CLOSURE[@]}"
    "${OOC_ROUTE_AUTHORIZATION_FILES[@]}"
)
printf '%s\n' "${INPUTS[@]}" > "$HAP_REPORT_DIR/INPUT_FILES"
sha256sum "${INPUTS[@]}" > "$HAP_REPORT_DIR/INPUT_SHA256SUMS"
[[ "${#INPUTS[@]}" -eq "$HAP_BOARD_EXPECTED_INPUT_COUNT" ]] || {
    printf 'V5 board complete input closure drifted: expected=%s actual=%d\n' \
        "$HAP_BOARD_EXPECTED_INPUT_COUNT" "${#INPUTS[@]}" >&2
    exit 2
}
export HAP_BOARD_INPUT_COUNT="${#INPUTS[@]}"
export HAP_INPUT_SHA_MANIFEST="$HAP_REPORT_DIR/INPUT_SHA256SUMS"
export HAP_INPUT_FILES="$HAP_REPORT_DIR/INPUT_FILES"
export HAP_INPUT_MANIFEST_SHA256
HAP_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_INPUT_SHA_MANIFEST" | awk '{print $1}')"

# INPUTS[0] is the .xpr that Vivado run management intentionally updates.
# Every remaining design/provenance input must stay byte-identical.
IMMUTABLE_INPUTS=("${INPUTS[@]:1}")
printf '%s\n' "${IMMUTABLE_INPUTS[@]}" > \
    "$HAP_REPORT_DIR/IMMUTABLE_INPUT_FILES"
sha256sum -- "${IMMUTABLE_INPUTS[@]}" > \
    "$HAP_REPORT_DIR/IMMUTABLE_INPUT_SHA256SUMS"
export HAP_IMMUTABLE_INPUT_FILES="$HAP_REPORT_DIR/IMMUTABLE_INPUT_FILES"
export HAP_IMMUTABLE_INPUT_SHA_MANIFEST=\
"$HAP_REPORT_DIR/IMMUTABLE_INPUT_SHA256SUMS"
export HAP_BOARD_IMMUTABLE_INPUT_COUNT="${#IMMUTABLE_INPUTS[@]}"
export HAP_IMMUTABLE_INPUT_MANIFEST_SHA256
HAP_IMMUTABLE_INPUT_MANIFEST_SHA256="$(sha256sum -- \
    "$HAP_IMMUTABLE_INPUT_SHA_MANIFEST" | awk '{print $1}')"
[[ "$HAP_BOARD_IMMUTABLE_INPUT_COUNT" -eq \
    "$HAP_BOARD_EXPECTED_IMMUTABLE_INPUT_COUNT" ]]
(cd / && sha256sum -c --strict "$HAP_REPORT_DIR/INPUT_SHA256SUMS")
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/IMMUTABLE_INPUT_SHA256SUMS")
input_manifest_sha_match=1
immutable_input_manifest_sha_match=1
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS")
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS")
hap_v5_verify_ooc_route_artifact "$HAP_OOC_ROUTE_DIR"

cd "$ROOT"
set +e
vivado_invoked=1
"$VIVADO" -mode batch -notrace \
    -source vivado/scripts/build_attention_mlp_vcu118_v5_bitstream.tcl \
    -log "$HAP_REPORT_DIR/vivado.log" \
    -journal "$HAP_REPORT_DIR/vivado.jou"
vivado_exit_code=$?
set -e
vivado_rc="$vivado_exit_code"

# The project metadata is intentionally updated by Vivado run management, so
# the complete input manifest is verified before launch and again inside the
# build Tcl before implementation begins.  The immutable recursive RTL/source
# closure and OOC authorization evidence are additionally rechecked after the
# long run and must remain byte-identical.
if [[ "$(sha256sum -- "$HAP_INPUT_SHA_MANIFEST" | awk '{print $1}')" \
      == "$HAP_INPUT_MANIFEST_SHA256" ]]; then
    input_manifest_sha_match=1
else
    vivado_rc=93
    input_manifest_sha_match=0
fi
if [[ "$(sha256sum -- "$HAP_IMMUTABLE_INPUT_SHA_MANIFEST" | \
        awk '{print $1}')" == \
      "$HAP_IMMUTABLE_INPUT_MANIFEST_SHA256" ]]; then
    immutable_input_manifest_sha_match=1
else
    vivado_rc=94
    immutable_input_manifest_sha_match=0
fi
(cd / && sha256sum -c --strict \
    "$HAP_IMMUTABLE_INPUT_SHA_MANIFEST") && \
    immutable_input_postcheck=1 || {
        vivado_rc=95
        immutable_input_postcheck=0
    }
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS") && \
    recursive_source_post_build_sha_verified=1 || {
    vivado_rc=90
    recursive_source_post_build_sha_verified=0
}
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS") && \
    ooc_route_authorization_post_build_verified=1 || {
    vivado_rc=91
    ooc_route_authorization_post_build_verified=0
}
hap_v5_verify_ooc_route_artifact "$HAP_OOC_ROUTE_DIR" || {
    vivado_rc=92
    ooc_route_authorization_post_build_verified=0
}
write_board_launcher_status "$vivado_rc"
if [[ "$vivado_rc" -ne 0 ]]; then
    printf 'V5 board bitstream build/provenance failed (rc=%d): %s\n' \
        "$vivado_rc" "$HAP_REPORT_DIR" >&2
    printf '%s\n' "$HAP_REPORT_DIR"
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

for required in summary.txt post_route_gate_summary.txt \
    XDC_SOURCE_INVENTORY XDC_ACTIVE_INVENTORY \
    INPUT_FILES INPUT_SHA256SUMS IMMUTABLE_INPUT_FILES \
    IMMUTABLE_INPUT_SHA256SUMS launcher_status.txt \
    RECURSIVE_SOURCE_MANIFEST_FILES RECURSIVE_RTL_SOURCE_FILES \
    RECURSIVE_SOURCE_CLOSURE_FILES RECURSIVE_SOURCE_SHA256SUMS \
    OOC_ROUTE_AUTHORIZATION_FILES OOC_ROUTE_AUTHORIZATION_SHA256SUMS \
    attention_mlp_vcu118_v5.bit attention_mlp_vcu118_v5_post_route.dcp \
    timing_post_route.rpt route_status_post_route.rpt drc_post_route.rpt \
    bufg_topology_post_route.txt \
    cdc_post_route.rpt selectors_post_route.txt \
    attention_geometry_post_route.txt \
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
    congestion_post_route.rpt exceptions_coverage_post_route.rpt \
    exceptions_valid_post_route.xdc exceptions_merged_post_route.xdc \
    utilization_post_route.rpt utilization_hier_post_route.rpt \
    utilization_slr_post_route.rpt clock_interaction_post_route.rpt \
    clock_utilization_post_route.rpt vivado.log vivado.jou; do
    [[ -s "$HAP_REPORT_DIR/$required" ]] || {
        printf 'missing or empty V5 board output: %s\n' "$required" >&2
        exit 1
    }
done
check_bufg_summary_schema "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'final_exit_code=0' "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'status=PASS' "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'vivado_exit_code=0' "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'vivado_invoked=1' "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'complete_input_manifest_sha_match=1' \
    "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx "immutable_input_count=$HAP_BOARD_EXPECTED_IMMUTABLE_INPUT_COUNT" \
    "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'immutable_input_manifest_sha_match=1' \
    "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'immutable_input_postcheck=1' \
    "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'recursive_source_post_build_sha_verified=1' \
    "$HAP_REPORT_DIR/launcher_status.txt"
grep -Fqx 'ooc_route_authorization_post_build_verified=1' \
    "$HAP_REPORT_DIR/launcher_status.txt"
[[ "$(wc -l < "$HAP_REPORT_DIR/RECURSIVE_SOURCE_MANIFEST_FILES")" -eq 3 ]]
[[ "$(wc -l < "$HAP_REPORT_DIR/RECURSIVE_RTL_SOURCE_FILES")" -eq 87 ]]
[[ "$(wc -l < "$HAP_REPORT_DIR/RECURSIVE_SOURCE_CLOSURE_FILES")" -eq 90 ]]
[[ "$(wc -l < "$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS")" -eq 90 ]]
[[ "$(wc -l < "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_FILES")" -eq 22 ]]
[[ "$(wc -l < "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS")" -eq 22 ]]
grep -Fqx 'status=V5_BOARD_BITSTREAM_PASS' "$HAP_REPORT_DIR/summary.txt"
[[ "$(grep -c '^status=' "$HAP_REPORT_DIR/summary.txt")" -eq 1 ]]
grep -Fqx 'post_route_gate_status=V5_BOARD_POST_ROUTE_PASS' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'status=V5_BOARD_POST_ROUTE_PASS' \
    "$HAP_REPORT_DIR/post_route_gate_summary.txt"
[[ "$(grep -c '^status=' \
    "$HAP_REPORT_DIR/post_route_gate_summary.txt")" -eq 1 ]]
grep -Fqx "dsp48e2=$HAP_BOARD_EXPECTED_TOTAL_DSP" \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'mlp_kernel_dsp48e2=3072' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'uram288=752' "$HAP_REPORT_DIR/summary.txt"
for exact in raw_weight_push_loads=37 \
    weight_data_capture_contract=32x256 weight_data_capture_nets=32 \
    weight_data_capture_loads=256/256 \
    weight_meta_capture_contract=2x256 weight_meta_capture_nets=2 \
    weight_meta_capture_loads=256/256 \
    weight_group_capture_contract=2x7 weight_group_capture_nets=2 \
    weight_group_capture_loads=7/7 projection_weight_capture_ok=1; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "$exact" "$HAP_REPORT_DIR/post_route_gate_summary.txt"
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
    grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "$exact" "$HAP_REPORT_DIR/post_route_gate_summary.txt"
    grep -Fqx "$exact" \
        "$HAP_REPORT_DIR/architecture_boundaries_post_route.txt"
done
grep -Fqx 'status=V5_BOARD_ARCHITECTURE_BOUNDARIES_PASS' \
    "$HAP_REPORT_DIR/architecture_boundaries_post_route.txt"
grep -Fqx 'cdc_critical=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'data_bufg=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'real_bufg_bad_connections=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'bufg_gt_data=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'bufg_gt_sync_clk_without_clock=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'bufg_gt_sync_bad_connections=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'production_core_bufg_gt_sync=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'bufg_partition_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'bufg_gt_sync_topology_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'bufg_topology_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'drc_errors=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'route_clean=1' "$HAP_REPORT_DIR/summary.txt"
for exact in no_clock_endpoints=0 unconstrained_paths=0 \
    timing_coverage_ok=1; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
    grep -Fqx "$exact" "$HAP_REPORT_DIR/post_route_gate_summary.txt"
done
grep -Fqx 'congestion_level6_or_higher_windows=0' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'exception_scope_policy_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'live_post_route_rediscovery_ok=1' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'base_contract_variant=P2_COHORT16_COL2_12_2' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p5_contract=P5_INPUT_HALF_LOCAL_8_8' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_contract=P9_POSTPROCESS_SPLIT_6_4_6' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p9_quantizer3_contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p14_region2_relief_contract=P14_ATTN_REGION2_SHARED_X0_X2' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'pblock_contract_variant=P2_COHORT16_COL2_12_2' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'pblock_contract_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'pblock_require_placed=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'pblock_count=26' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'canonical_pblock_count=11' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'geometry_pblock_count=10' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p5_added_pblock_count=2' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_added_pblock_count=2' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p9_quantizer3_added_pblock_count=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p14_region2_relief_added_pblock_count=0' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'total_pblock_count=26' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'completed_u8_ff=4096' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'completed_meta_ff=352' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'input_capture_ff=12288' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'input_capture_controls=48' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p5_center_wrong_slr=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p5_outer_wrong_slr=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_center_wrong_slr=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'p9_postprocess_outer_wrong_slr=0' "$HAP_REPORT_DIR/summary.txt"
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
    grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
done
grep -Fqx "rtl_variant=$HAP_BOARD_RTL_VARIANT" \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx "rtl_resource_variant=$HAP_BOARD_RTL_VARIANT" \
    "$HAP_REPORT_DIR/summary.txt"
if [[ "$HAP_BOARD_RTL_VARIANT" == P16_NOCLIP ]]; then
    for exact in \
        "region2_signature_source=P16_PRODUCTION_POST_OPT_SHA256:$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" \
        "p16_post_opt_summary=$HAP_P16_POST_OPT_SUMMARY" \
        "p16_post_opt_summary_sha256=$HAP_P16_POST_OPT_SUMMARY_SHA256" \
        "p16_production_region2_summary=$HAP_P16_PRODUCTION_REGION2_SUMMARY" \
        "p16_production_region2_summary_sha256=$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" \
        "p16_production_dcp_sha256=$HAP_P16_PRODUCTION_DCP_SHA256"; do
        grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
    done
    grep -Fqx \
        "region2_signature_source=P16_PRODUCTION_POST_OPT_SHA256:$HAP_P16_PRODUCTION_REGION2_SUMMARY_SHA256" \
        "$HAP_REPORT_DIR/post_route_gate_summary.txt"
fi
grep -Fqx 'physical_placement_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx "pblock_dsp_coverage=$HAP_BOARD_EXPECTED_TOTAL_DSP" \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'pblock_uram_coverage=752' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'pblock_wrong_slr=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'wrong_slr_primitives=0' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'physical_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'floorplan_contract_ok=1' "$HAP_REPORT_DIR/summary.txt"
grep -Fqx 'ooc_route_authorization_verified=1' \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx "ooc_route_artifact=$HAP_OOC_ROUTE_DIR" \
    "$HAP_REPORT_DIR/summary.txt"
for exact in complete_input_sha_verified=1 \
    "complete_input_count=$HAP_BOARD_EXPECTED_INPUT_COUNT" \
    recursive_source_sha_verified=1 recursive_source_manifest_count=3 \
    recursive_rtl_source_count=87 recursive_source_closure_count=90; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
done
OOC_ROUTE_SUMMARY_SHA="$(sha256sum "$HAP_OOC_ROUTE_DIR/summary.txt" | \
    awk '{print $1}')"
OOC_ROUTE_DCP_SHA="$(sha256sum "$HAP_OOC_ROUTE_DIR/post_route.dcp" | \
    awk '{print $1}')"
grep -Fqx "ooc_route_summary_sha256=$OOC_ROUTE_SUMMARY_SHA" \
    "$HAP_REPORT_DIR/summary.txt"
grep -Fqx "ooc_route_post_route_dcp_sha256=$OOC_ROUTE_DCP_SHA" \
    "$HAP_REPORT_DIR/summary.txt"
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
    grep -Fqx "$exact" "$HAP_REPORT_DIR/summary.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_SELECTORS_PASS \
    "contract_variant=P2_COHORT16_COL2_12_2 total_dsp=$HAP_BOARD_EXPECTED_TOTAL_DSP total_uram=752" \
    outer0_dsp=1538 outer2_dsp=1538 \
    outer0_ramb36=102 outer2_ramb36=102 move0=16 center_lanes=96 \
    move2=16 planned_slr0_dsp=1862 \
    "planned_slr1_dsp=$HAP_BOARD_EXPECTED_SLR1_DSP" \
    planned_slr2_dsp=1810; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/selectors_post_route.txt"
done
[[ "$(grep -c '^status=' \
    "$HAP_REPORT_DIR/selectors_post_route.txt")" -eq 1 ]]
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
    grep -Fqx "$exact" "$HAP_REPORT_DIR/attention_geometry_post_route.txt"
done
[[ "$(grep -c '^status=' \
    "$HAP_REPORT_DIR/attention_geometry_post_route.txt")" -eq 1 ]]
for exact in status=V5_BOARD_POST_ROUTE_GEOMETRY_PLACEMENT_PASS ok=1 \
    wrong_total=0 unplaced_total=0 'slr_dsp=272 1696 272'; do
    grep -Fqx "$exact" \
        "$HAP_REPORT_DIR/attention_geometry_placement_post_route.txt"
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
    grep -Fqx "$exact" "$HAP_REPORT_DIR/base_pblocks_post_route.txt"
done
[[ "$(grep -c '^status=' \
    "$HAP_REPORT_DIR/base_pblocks_post_route.txt")" -eq 1 ]]
for exact in status=V5_BOARD_POST_ROUTE_P5_INPUT_PLAN_PASS \
    contract=P5_INPUT_HALF_LOCAL_8_8 quantizer_count=4 cache_count=2 \
    hadamard_count=1 completed_u8_ff=4096 completed_meta_ff=352 \
    input_capture_ff=12288 capture_leaf_count=48 center_canonical_overlap=8; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p5_input_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P5_INPUT_PBLOCKS_PASS ok=1 \
    require_placed=1 pblock_count=2 center_missing=0 \
    center_outer_overlap=0 center_wrong=0 outer_wrong=0; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p5_input_pblocks_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PLAN_PASS \
    contract=P9_POSTPROCESS_SPLIT_6_4_6 row_bank_count=16 \
    all_row_primitives=42784 slr0_row_primitives=16044 \
    center_row_primitives=10696 slr2_row_primitives=16044 \
    per_row_primitives=2674 per_row_lut=994 per_row_ff=1536; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p9_postprocess_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_POSTPROCESS_PBLOCKS_PASS ok=1 \
    require_placed=1 pblock_count=2 center_missing=0 \
    center_outer_overlap=0 center_wrong=0 outer_wrong=0 \
    slr0_target=0 slr0_missing=0 slr0_wrong=0 \
    slr2_target=2 slr2_missing=0 slr2_wrong=0; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p9_postprocess_pblocks_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PLAN_PASS \
    contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
    "primitive_count=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    grid_range=CLOCKREGION_X2Y5:CLOCKREGION_X3Y6; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p9_quantizer3_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P9_QUANTIZER3_PBLOCK_PASS ok=1 \
    require_placed=1 contract=P9_SWIGLU_QUANTIZER3_CR_X2Y5_X3Y6 \
    "expected=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    "members=$HAP_BOARD_EXPECTED_QUANTIZER3_PRIMITIVES" \
    missing=0 extras=0 wrong=0 unplaced=0; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p9_quantizer3_pblock_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PLAN_PASS \
    contract=P14_ATTN_REGION2_SHARED_X0_X2 \
    "primitive_count=$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" \
    base_range=CLOCKREGION_X0Y5:CLOCKREGION_X1Y9 \
    relief_range=CLOCKREGION_X2Y5:CLOCKREGION_X2Y9 \
    expected_range=CLOCKREGION_X0Y5:CLOCKREGION_X2Y9; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p14_region2_relief_plan_post_route.txt"
done
for exact in status=V5_BOARD_POST_ROUTE_P14_REGION2_RELIEF_PBLOCK_PASS \
    ok=1 contract=P14_ATTN_REGION2_SHARED_X0_X2 require_placed=1 \
    "primitive_count=$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" \
    missing=0 wrong=0 unplaced=0; do
    grep -Fqx "$exact" "$HAP_REPORT_DIR/p14_region2_relief_pblock_post_route.txt"
done
awk -F= -v maximum="$HAP_BOARD_EXPECTED_RELIEF_PRIMITIVES" '
    $1 == "relief_placed" {
        count++
        if ($2 !~ /^[0-9]+$/ || $2 + 0 > maximum) bad=1
    }
    END {exit count == 1 && !bad ? 0 : 1}
' "$HAP_REPORT_DIR/p14_region2_relief_pblock_post_route.txt"
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
        "$HAP_REPORT_DIR/p8_parent_ingress_boundary_post_route.txt"
done
awk -F= '/^wns_ns=|^whs_ns=/{if ($2 < 0) exit 1; n++} END{exit n==2?0:1}' \
    "$HAP_REPORT_DIR/summary.txt"
awk -F= '/^slr[012]_dsp48e2=/{if ($2 > 2280) exit 1; n++} END{exit n==3?0:1}' \
    "$HAP_REPORT_DIR/summary.txt"
archive_board_outputs
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/RECURSIVE_SOURCE_SHA256SUMS")
(cd / && sha256sum -c --strict \
    "$HAP_REPORT_DIR/OOC_ROUTE_AUTHORIZATION_SHA256SUMS")
cat "$HAP_REPORT_DIR/summary.txt"
printf '%s\n' "$HAP_REPORT_DIR"
