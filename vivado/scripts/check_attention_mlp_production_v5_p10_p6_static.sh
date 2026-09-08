#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
P5_LIB="$ROOT/vivado/scripts/v5_production_p5_input_partition_floorplan.tcl"
P6_LIB="$ROOT/vivado/scripts/v5_production_p6_postprocess_partition_floorplan.tcl"
AUDIT="$ROOT/vivado/scripts/audit_attention_mlp_production_v5_p10_p6_pre_place.tcl"
PRE_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p6_pre_place.sh"
PLACE="$ROOT/vivado/scripts/place_attention_mlp_production_v5_p10_p6.tcl"
PLACE_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p6_place.sh"
ROUTE="$ROOT/vivado/scripts/resume_attention_mlp_production_v5_p10_p6_route.tcl"
ROUTE_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p6_route.sh"
DIAG="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p10_p5_redistribution.tcl"
DIAG_LAUNCH="$ROOT/vivado/scripts/run_attention_mlp_production_v5_p10_p5_redistribution_diagnosis.sh"
SELECTOR_MOCK="$ROOT/vivado/scripts/test_v5_production_p6_postprocess_selector_mock.tcl"
XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"

for file in "$P5_LIB" "$P6_LIB" "$AUDIT" "$PRE_LAUNCH" "$PLACE" \
        "$PLACE_LAUNCH" "$ROUTE" "$ROUTE_LAUNCH" "$DIAG" \
        "$DIAG_LAUNCH" "$SELECTOR_MOCK" "$XDC"; do
    [[ -s "$file" ]] || {
        printf 'missing P6 static input: %s\n' "$file" >&2
        exit 1
    }
done
bash -n "$PRE_LAUNCH" "$PLACE_LAUNCH" "$ROUTE_LAUNCH" "$DIAG_LAUNCH"

tclsh <<EOF
foreach path [list "$P6_LIB" "$AUDIT" "$PLACE" "$ROUTE" "$DIAG"] {
    set fp [open \$path r]
    set data [read \$fp]
    close \$fp
    if {![info complete \$data]} {error "incomplete Tcl: \$path"}
}
EOF
HAP_P6_SELECTOR_LIB="$P6_LIB" tclsh "$SELECTOR_MOCK" | \
    grep -Fqx P6_SELECTOR_MOCK_DISCOVERY_PASS

require_exact() {
    local file="$1" literal="$2"
    [[ "$(grep -Fxc -- "$literal" "$file" || true)" -eq 1 ]] || {
        printf 'P6 static literal missing/duplicated: %s :: %s\n' \
            "$file" "$literal" >&2
        exit 1
    }
}

require_exact "$P6_LIB" '    variable contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'
require_exact "$P6_LIB" '    variable slr0_pblock pb_v5_p6_postprocess_rows0_3_slr0'
require_exact "$P6_LIB" '    variable slr2_pblock pb_v5_p6_postprocess_rows12_15_slr2'
require_exact "$P6_LIB" '    set slr0_rows [concat {*}[lrange $row_primitives 0 3]]'
require_exact "$P6_LIB" '    set center_rows [concat {*}[lrange $row_primitives 4 11]]'
require_exact "$P6_LIB" '    set slr2_rows [concat {*}[lrange $row_primitives 12 15]]'
require_exact "$P6_LIB" '        per_row_primitives 2674 per_row_lut 994 per_row_ff 1536]'

require_exact "$AUDIT" 'set contract_variant P2_COHORT16_COL2_12_2'
require_exact "$AUDIT" '    input_manifest_entries 10 provenance_verified 1 \'
require_exact "$AUDIT" '    p6_contract [dict get $p6_plan contract] \'
require_exact "$AUDIT" '    p6_added_pblock_count [dict get $p6_audit pblock_count] \'
require_exact "$AUDIT" '    total_pblock_count $pblock_count \'
require_exact "$AUDIT" 'set status [expr {$status_ok ? "V5_P10_P6_PRE_PLACE_PASS" : "FAIL"}]'

require_exact "$PLACE" 'set p5_contract P5_INPUT_HALF_LOCAL_8_8'
require_exact "$PLACE" 'set p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'
require_exact "$PLACE" 'set preplace_output_sha [file normalize $::env(HAP_P6_PREPLACE_OUTPUT_SHA)]'
require_exact "$PLACE" '    input_manifest_entries 11 provenance_verified 1 \'
require_exact "$PLACE" '    p6_added_pblock_count [dict get $post_p6_audit pblock_count] \'
require_exact "$PLACE" '    "V5_P10_P6_PRODUCTION_PLACE_PASS" : "FAIL"}]'
require_exact "$PLACE_LAUNCH" "        'status=V5_P10_P6_PRODUCTION_PLACE_PASS'"
require_exact "$PLACE_LAUNCH" "        'input_manifest_entries=11' 'provenance_verified=1'"
require_exact "$PLACE_LAUNCH" "        'p6_added_pblock_count=2' 'total_pblock_count=25'"

require_exact "$ROUTE" 'set p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4'
require_exact "$ROUTE" 'set frozen_place_inputs [hap_verify_sha_manifest $place_input_sha 11 \'
require_exact "$ROUTE" 'set frozen_route_inputs [hap_verify_sha_manifest $route_input_sha 25 \'
require_exact "$ROUTE" '    set p6_plan [hap_v5_p6_postprocess_partition::discover \'
require_exact "$ROUTE" '        [llength [get_pblocks -quiet]] != 25 ||'
require_exact "$ROUTE" '    "V5_P10_P6_PRODUCTION_OOC_POST_ROUTE_PASS" :'
require_exact "$ROUTE" '    route_input_manifest_entries 25 \'
require_exact "$ROUTE_LAUNCH" "    'status=V5_P10_P6_PRODUCTION_OOC_POST_ROUTE_PASS'"
require_exact "$ROUTE_LAUNCH" "    'route_input_manifest_entries=25'"
require_exact "$ROUTE_LAUNCH" "    'p5_added_pblock_count=2' 'p6_added_pblock_count=2'"

[[ "$(grep -Ec '^[[:space:]]*place_design([[:space:]]|$)' "$AUDIT" || true)" -eq 0 ]]
[[ "$(grep -Ec '^[[:space:]]*(route_design|phys_opt_design|write_checkpoint|write_bitstream)([[:space:]]|$)' \
    "$AUDIT" || true)" -eq 0 ]]
[[ "$(grep -Ec '^[[:space:]]*place_design([[:space:]]|$)' "$PLACE" || true)" -eq 1 ]]
[[ "$(grep -Ec '^[[:space:]]*(route_design|phys_opt_design|write_bitstream)([[:space:]]|$)' \
    "$PLACE" || true)" -eq 0 ]]
[[ "$(grep -Ec 'write_checkpoint' "$PLACE" || true)" -eq 3 ]]
[[ "$(grep -Ec 'route_design[[:space:]]+(-directive|-preserve)' \
    "$ROUTE" || true)" -eq 3 ]]
[[ "$(grep -Ec '^[[:space:]]*write_bitstream([[:space:]]|$)' \
    "$ROUTE" || true)" -eq 0 ]]

diag_code="$(sed -E '/^[[:space:]]*#/d' "$DIAG")"
if grep -Eq '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint|write_bitstream)([^[:alnum:]_]|$)' \
        <<<"$diag_code"; then
    printf 'P6 redistribution diagnosis is not read-only\n' >&2
    exit 1
fi
require_exact "$DIAG" '        open_checkpoint_elapsed_ms $open_elapsed floorplan_mutated 0 \'

[[ "$(grep -Ec 'set_false_path|set_max_delay.*-datapath_only|set_min_delay.*-datapath_only' \
    "$XDC" || true)" -eq 0 ]]
[[ "$(grep -Ec '^[[:space:]]*create_clock[[:space:]]' "$XDC")" -eq 3 ]]
[[ "$(grep -Ec '^[[:space:]]*set_input_delay[[:space:]]' "$XDC")" -eq 6 ]]
[[ "$(grep -Ec '^[[:space:]]*set_output_delay[[:space:]]' "$XDC")" -eq 6 ]]

printf 'V5_P10_P6_STATIC_PASS\n'
