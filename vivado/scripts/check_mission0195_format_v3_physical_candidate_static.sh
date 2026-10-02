#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLICY="$ROOT/vivado/scripts/v5_production_p17_optimizer_delta_policy.tcl"
POLICY_TEST="$ROOT/vivado/scripts/test_v5_production_p17_optimizer_delta_policy.tcl"
Q3="$ROOT/vivado/scripts/v5_production_p17_quantizer3_x3_isolation_floorplan.tcl"
FROZEN="$ROOT/vivado/scripts"

tclsh "$POLICY_TEST"
tclsh <<EOF
source {$Q3}
set audit [hap_v5_p17_quantizer3_isolation::audit_contract]
if {![dict get \$audit ok] || [dict get \$audit overlap_count] != 0} {exit 1}
puts P17_QUANTIZER3_X3_ISOLATION_STATIC_PASS
EOF

for file in "$POLICY" "$POLICY_TEST" "$Q3"; do
    tclsh <<EOF
set fp [open {$file} r]
set text [read \$fp]
close \$fp
if {![info complete \$text]} {exit 1}
EOF
done

grep -Fq 'P17_EXACT_TWO_ATTN_S42_LUT5_REMOVALS' "$POLICY"
grep -Fq 'lower_head_guard_s42_r[364]_i_3' "$POLICY"
grep -Fq 'lower_head_guard_s42_r[608]_i_3' "$POLICY"
grep -Fq "expected_init {32'h00A20000}" "$POLICY"
grep -Fq 'reported_removed_lut != 2' "$POLICY"
grep -Fq 'CLOCKREGION_X3Y5:CLOCKREGION_X3Y9' "$Q3"
grep -Fq 'overlap_count 0' "$Q3"

printf '%s  %s\n' \
    ea6c8865eb1c2f4fc1b557266dbc547c7629979d1f8bfcd79e622da65cf4b121 \
    "$FROZEN/diagnose_attention_mlp_production_v5_p16_noclip_post_place_delta.tcl" \
    d3f68452b42c1eac03ba66795f401bb659480674adff492ff8d2fa50be0626f6 \
    "$FROZEN/run_mission0194_format_v3_post_place_audit.sh" \
    00da9d36a12ff715673d0681dd916b79478332160e7faf83830b8322f9135490 \
    "$FROZEN/check_mission0194_format_v3_post_place_audit_static.sh" \
    386f4de2fe2bb8304c21915bc1f34966ee15352435cbae429c4ef88c8b0a039d \
    "$FROZEN/seal_mission0194_format_v3_post_place_audit.sh" | sha256sum -c --strict -

for file in "$POLICY" "$POLICY_TEST" "$Q3"; do
    code="$(sed -E '/^[[:space:]]*#/d' "$file")"
    if grep -Eq \
        '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint|write_bitstream)([^[:alnum:]_]|$)' \
        <<<"$code"; then
        exit 1
    fi
done

printf 'MISSION0195_FORMAT3_PHYSICAL_CANDIDATE_STATIC_PASS\n'
