#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RTL="$ROOT/rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv"
LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
AUDIT="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_p10_p5_pre_place.tcl"
PRE_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p5_pre_place.sh"
PLACE="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p5.tcl"
PLACE_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p5_place.sh"
ROUTE="$ROOT/vivado/scripts/resume_attention_mlp_production_v5_p10_p5_route.tcl"
ROUTE_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p5_route.sh"
FULL_SIM="$ROOT/vivado/scripts/run_mlp_full_command16_s45_xsim.sh"
XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"

for file in "$RTL" "$LIB" "$AUDIT" "$PRE_LAUNCH" "$PLACE" \
        "$PLACE_LAUNCH" "$ROUTE" "$ROUTE_LAUNCH" "$FULL_SIM" "$XDC"; do
    [[ -s "$file" ]] || { printf 'missing P5 static input: %s\n' "$file" >&2; exit 1; }
done
bash -n "$PRE_LAUNCH" "$PLACE_LAUNCH" "$ROUTE_LAUNCH" "$FULL_SIM"

tclsh <<EOF
foreach path [list "$LIB" "$AUDIT" "$PLACE" "$ROUTE"] {
    set fp [open \$path r]
    set data [read \$fp]
    close \$fp
    if {![info complete \$data]} {error "incomplete Tcl: \$path"}
}
EOF

require_exact() {
    local file="$1" literal="$2"
    [[ "$(grep -Fxc -- "$literal" "$file" || true)" -eq 1 ]] || {
        printf 'P5 static literal missing/duplicated: %s :: %s\n' \
            "$file" "$literal" >&2
        exit 1
    }
}

require_exact "$RTL" '        {dispatch_row_r[3], dispatch_row_r[0]};'
require_exact "$RTL" '            ((row_bank / 8) * 2) + (row_bank % 2);'
require_exact "$RTL" '        localparam integer ROW_WAVE = (row_bank % 8) / 2;'
for literal in \
        '        .wr_valid(bundle_valid_r),.wr_ready(half0_wr_ready),' \
        '        .wr_valid(bundle_valid_r),.wr_ready(half1_wr_ready),' \
        '        .rd_rsp_ready(rd_rsp_ready),.rd_rsp_bank(half0_rsp_bank),' \
        '        .rd_rsp_ready(rd_rsp_ready),.rd_rsp_bank(half1_rsp_bank),' \
        '        .release_valid(release_valid),.release_ready(half0_release_ready),' \
        '        .release_valid(release_valid),.release_ready(half1_release_ready),' \
        '               (bundle_valid_r&&(half0_wr_ready!=half1_wr_ready))||' \
        '               (rd_req_valid&&(half0_rd_req_ready!=half1_rd_req_ready))||' \
        '               (half0_rsp_valid!=half1_rsp_valid)||'; do
    require_exact "$RTL" "$literal"
done
[[ "$(grep -Fxc -- '        .rd_req_valid(rd_req_valid),' "$RTL" || true)" -eq 2 ]]
if grep -Eq '\.wr_valid\(cache_write_fire\)|\.rd_req_valid\(rd_req_valid&&half[01]_rd_req_ready\)|assign half[01]_rsp_ready =|\.release_valid\(release_fire\)' \
        "$RTL"; then
    printf 'P5 compact frontend retains a cross-half handshake dependency\n' >&2
    exit 1
fi
require_exact "$LIB" '    variable contract P5_INPUT_HALF_LOCAL_8_8'
require_exact "$LIB" '    variable half0_pblock pb_v5_p5_input_half0_slr0'
require_exact "$LIB" '    variable half1_pblock pb_v5_p5_input_half1_slr2'
require_exact "$LIB" '    variable center_pblock pb_v5_attention_projection_center12_slr1'
require_exact "$LIB" '            [dict get $half1 extras]}]]'
require_exact "$AUDIT" 'set contract_variant P2_COHORT16_COL2_12_2'
require_exact "$AUDIT" 'set geometry_prefix p3_'
require_exact "$PLACE" 'set contract_variant P2_COHORT16_COL2_12_2'
require_exact "$PLACE" 'set p5_contract P5_INPUT_HALF_LOCAL_8_8'
require_exact "$PLACE" 'set geometry_prefix p3_'
require_exact "$ROUTE" 'set p5_contract P5_INPUT_HALF_LOCAL_8_8'
require_exact "$ROUTE" 'set frozen_route_inputs [hap_verify_sha_manifest $route_input_sha 22 \'
require_exact "$ROUTE" '    route_input_manifest_entries 22 \'
require_exact "$ROUTE_LAUNCH" '    '\''route_input_manifest_entries=22'\'''
[[ "$(grep -Fxc -- '    rtl/mlp/hap_mlp_input_frontend16_compact_cache.sv \' \
    "$FULL_SIM" || true)" -eq 2 ]] || {
    printf 'P5 full-command compact-frontend hash/compile coverage mismatch\n' >&2
    exit 1
}

[[ "$(grep -Ec '^[[:space:]]*place_design([[:space:]]|$)' "$AUDIT" || true)" -eq 0 ]]
[[ "$(grep -Ec '^[[:space:]]*(route_design|write_checkpoint|write_bitstream)([[:space:]]|$)' \
    "$AUDIT" || true)" -eq 0 ]]
[[ "$(grep -Ec '^[[:space:]]*place_design([[:space:]]|$)' "$PLACE" || true)" -eq 1 ]]
[[ "$(grep -Ec '^[[:space:]]*(route_design|write_bitstream)([[:space:]]|$)' \
    "$PLACE" || true)" -eq 0 ]]
[[ "$(grep -Ec 'write_checkpoint' "$PLACE" || true)" -eq 3 ]]
[[ "$(grep -Ec 'route_design[[:space:]]+(-directive|-preserve)' \
    "$ROUTE" || true)" -eq 3 ]]
[[ "$(grep -Ec '^[[:space:]]*write_bitstream([[:space:]]|$)' "$ROUTE" || true)" -eq 0 ]]
[[ "$( (grep -Eh '(^|[^[:alnum:]_])(P4|p4)([^[:alnum:]_]|$)|PHYSICAL4_8_4_19|physical448|fine19' \
    "$ROUTE" "$ROUTE_LAUNCH" || true) | wc -l)" -eq 0 ]]
[[ "$(grep -Ec 'set_false_path|set_max_delay.*-datapath_only|set_min_delay.*-datapath_only' \
    "$XDC" || true)" -eq 0 ]]
[[ "$(grep -Ec '^[[:space:]]*create_clock[[:space:]]' "$XDC")" -eq 3 ]]
[[ "$(grep -Ec '^[[:space:]]*set_input_delay[[:space:]]' "$XDC")" -eq 6 ]]
[[ "$(grep -Ec '^[[:space:]]*set_output_delay[[:space:]]' "$XDC")" -eq 6 ]]

printf 'V5_P10_P5_STATIC_PASS\n'
