#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN="$ROOT/vivado/scripts/run_mission0194_format_v3_post_place_audit.sh"
TCL="$ROOT/vivado/scripts/diagnose_attention_mlp_production_v5_p16_noclip_post_place_delta.tcl"

bash -n "$RUN"
tclsh <<EOF
set fp [open {$TCL} r]
set text [read \$fp]
close \$fp
if {![info complete \$text]} {exit 1}
EOF

for literal in \
        'HAP_P16_DELTA_EXPECTED_REMOVED_LUT=2' \
        'HAP_P16_DELTA_EXPECTED_RAMB36=829' \
        'EXPECTED_POST_PLACE_SHA=01f134c30570072c5fe650b2e0d03241d9e9b32699756f28dc005920d17d6de3' \
        'READ_ONLY_AUTHENTICATED_DCP_COMPARISON' \
        'V5_M0194_FORMAT3_POST_PLACE_AUDIT_PASS' \
        'residual_removed_non_lut=0' 'lane_identity_ok=1' \
        'region2_partition_exact_cover=1' 'region2_wrong_slr=0' \
        'global_unplaced_primitives=0' 'post_place_drc_errors=0' \
        '[r]un_module_power[.]sh' 'HAP_JOBS=32'; do
    grep -Fq -- "$literal" "$RUN"
done
for literal in \
        'expected removal count in 0..2' \
        'lane_identity_ok' 'exact_partition_cover 1' \
        'residual_removed_non_lut' 'post_place_tns_ns' 'post_place_ths_ns' \
        'physical_slr_audit_for_cells' \
        'hap_mlp_p8_parent_boundary::audit' \
        'implementation_commands_run 0 checkpoint_written 0 route_eligible 0'; do
    grep -Fq -- "$literal" "$TCL"
done

audit_code="$(sed -E '/^[[:space:]]*#/d' "$TCL")"
if grep -Eq \
        '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint|write_bitstream)([^[:alnum:]_]|$)' \
        <<<"$audit_code"; then
    exit 1
fi
printf 'M0194_FORMAT3_POST_PLACE_AUDIT_STATIC_PASS\n'
