#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS="$ROOT/vivado/scripts"
LIB="$SCRIPTS/v5_production_floorplan_selectors.tcl"
PLACE="$SCRIPTS/place_attention_mlp_production_v5_floorplan.tcl"
ROUTE="$SCRIPTS/resume_attention_mlp_production_v5_route.tcl"
REOPEN="$SCRIPTS/audit_attention_mlp_production_v5_post_place_live_reopen.tcl"
SYNTH="$SCRIPTS/synth_attention_mlp_production_v5.tcl"
SYNTH_RUN="$SCRIPTS/run_attention_mlp_production_v5_synth.sh"
POST_OPT="$SCRIPTS/audit_attention_mlp_production_v5_post_opt_dcp.tcl"
APPLY="$SCRIPTS/apply_attention_mlp_vcu118_v5_floorplan.tcl"
SELECTOR_CHECK="$SCRIPTS/check_attention_mlp_production_v5_floorplan_selectors.tcl"
SELECTOR_RUN="$SCRIPTS/run_attention_mlp_production_v5_floorplan_selector_check.sh"
PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_place.sh"
PLACE_SCREEN_RUN="$SCRIPTS/run_attention_mlp_production_v5_place_screen.sh"
PHYSICAL_LEDGER="$SCRIPTS/summarize_attention_mlp_v5_physical_runs.sh"
ROUTE_RUN="$SCRIPTS/run_attention_mlp_production_v5_route.sh"
REOPEN_RUN="$SCRIPTS/run_attention_mlp_production_v5_post_place_live_reopen_audit.sh"
POST_OPT_RUN="$SCRIPTS/run_attention_mlp_production_v5_post_opt_audit.sh"
PRE_PLACE="$SCRIPTS/audit_attention_mlp_production_v5_pre_place_contract.tcl"
PRE_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_pre_place_contract_audit.sh"
DEVICE_PROBE="$SCRIPTS/probe_attention_mlp_production_v5_device_slr_sites.tcl"
DEVICE_PROBE_RUN="$SCRIPTS/run_attention_mlp_production_v5_device_slr_site_probe.sh"
OOC_CAPACITY="$SCRIPTS/probe_projection_core16x16_w8_reuse_floorplan_capacity.tcl"
OOC_CAPACITY_RUN="$SCRIPTS/run_projection_core16x16_w8_reuse_floorplan_capacity_probe.sh"
OOC_FLOORPLAN="$SCRIPTS/projection_core16x16_w8_reuse_ooc_floorplan.tcl"
OOC_PRE_PLACE="$SCRIPTS/audit_projection_core16x16_w8_reuse_ooc_pre_place.tcl"
OOC_PRE_PLACE_RUN="$SCRIPTS/run_audit_projection_core16x16_w8_reuse_ooc_pre_place.sh"
OOC_ROUTE="$SCRIPTS/route_projection_core16x16_w8_reuse_registered_ooc.tcl"
OOC_ROUTE_RUN="$SCRIPTS/run_projection_core16x16_w8_reuse_registered_ooc_route.sh"
OOC_REOPEN="$SCRIPTS/audit_projection_core16x16_w8_reuse_registered_ooc_route.tcl"
OOC_REOPEN_RUN="$SCRIPTS/run_audit_projection_core16x16_w8_reuse_registered_ooc_route.sh"
OOC_REGION3_DIAG="$SCRIPTS/diagnose_projection_core16x16_w8_reuse_region3_input_staging.tcl"
FINE19_PROBE="$SCRIPTS/probe_attention_mlp_production_v5_fine19_floorplan.tcl"
FINE19_PROBE_RUN="$SCRIPTS/run_attention_mlp_production_v5_fine19_floorplan_probe.sh"
FINE19_LIB="$SCRIPTS/v5_production_fine19_floorplan.tcl"
COMPOSITE21_LIB="$SCRIPTS/v5_production_composite21_floorplan.tcl"
COMPOSITE21_PRE_PLACE="$SCRIPTS/audit_attention_mlp_production_v5_composite21_pre_place.tcl"
COMPOSITE21_PRE_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_composite21_pre_place_audit.sh"
COMPOSITE21_DIAG="$SCRIPTS/diagnose_attention_mlp_production_v5_composite21_partition.tcl"
COMPOSITE21_DIAG_RUN="$SCRIPTS/run_attention_mlp_production_v5_composite21_partition_diagnosis.sh"
P9_RECOVERY="$SCRIPTS/diagnose_attention_mlp_production_v5_p9_post_place_recovery.tcl"
P9_RECOVERY_RUN="$SCRIPTS/run_attention_mlp_production_v5_p9_post_place_recovery.sh"
P9_TIMING="$SCRIPTS/diagnose_attention_mlp_production_v5_p9_timing_roots.tcl"
P9_TIMING_RUN="$SCRIPTS/run_attention_mlp_production_v5_p9_timing_roots.sh"
ATTENTION_LOCAL_DIAG="$SCRIPTS/diagnose_projection_core16x16_w8_reuse_local_lockstep_post_synth.tcl"
ATTENTION_LOCAL_DIAG_RUN="$SCRIPTS/run_projection_core16x16_w8_reuse_local_lockstep_post_synth.sh"
MLP_OWNER_SYNTH="$SCRIPTS/synth_a8w4_slice8x12_owner_capture_registered_ooc.tcl"
MLP_OWNER_SYNTH_RUN="$SCRIPTS/run_a8w4_slice8x12_owner_capture_registered_ooc_synth.sh"
MLP_OWNER_ROUTE="$SCRIPTS/route_a8w4_slice8x12_owner_capture_registered_ooc.tcl"
MLP_OWNER_ROUTE_RUN="$SCRIPTS/run_a8w4_slice8x12_owner_capture_registered_ooc_route.sh"
MLP_OWNER_XDC="$ROOT/vivado/constraints/a8w4_slice8x12_group_registered_ooc_100mhz.xdc"
P10_PLACE="$SCRIPTS/place_attention_mlp_production_v5_p10_p2.tcl"
P10_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p2_place.sh"
P4_LIB="$SCRIPTS/v5_production_physical448_floorplan.tcl"
P4_PRE_PLACE="$SCRIPTS/audit_attention_mlp_production_v5_p10_p4_pre_place.tcl"
P4_PRE_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p4_pre_place.sh"
P4_PLACE="$SCRIPTS/place_attention_mlp_production_v5_p10_p4.tcl"
P4_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p4_place.sh"
P4_ROUTE="$SCRIPTS/resume_attention_mlp_production_v5_p10_p4_route.tcl"
P4_ROUTE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p4_route.sh"
P12_RELIEF_LIB="$SCRIPTS/v5_production_p12_region1_x5y5_relief_floorplan.tcl"
P12_PRE_PLACE="$SCRIPTS/audit_attention_mlp_production_v5_p10_p12_pre_place.tcl"
P12_PRE_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p12_pre_place.sh"
P12_PLACE="$SCRIPTS/place_attention_mlp_production_v5_p10_p12.tcl"
P12_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p12_place.sh"
P13_RELIEF_LIB="$SCRIPTS/v5_production_p13_region1_x5y5_relief_floorplan.tcl"
P13_LANE_LIB="$SCRIPTS/v5_production_p13_region1_lane_relief_floorplan.tcl"
P13_CANDIDATE="$SCRIPTS/diagnose_attention_mlp_production_v5_p13_region1_lane_candidate.tcl"
P13_CANDIDATE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p13_region1_lane_candidate.sh"
P13_PRE_PLACE="$SCRIPTS/audit_attention_mlp_production_v5_p10_p13_pre_place.tcl"
P13_PRE_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p13_pre_place.sh"
P13_PLACE="$SCRIPTS/place_attention_mlp_production_v5_p10_p13.tcl"
P13_PLACE_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p13_place.sh"
P13_LEVEL6_MAP="$SCRIPTS/diagnose_attention_mlp_production_v5_p10_p13_level6_map.tcl"
P13_LEVEL6_MAP_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p13_level6_map.sh"
P13_TIMING_ROOTS="$SCRIPTS/diagnose_attention_mlp_production_v5_p10_p13_timing_roots.tcl"
P13_TIMING_ROOTS_RUN="$SCRIPTS/run_attention_mlp_production_v5_p10_p13_timing_roots.sh"
MLP_AXIL="$SCRIPTS/route_mlp_axil_control_ooc.tcl"
MLP_AXIL_RUN="$SCRIPTS/run_mlp_axil_control_ooc.sh"
MLP_AXIL_XDC="$ROOT/vivado/constraints/mlp_axil_control_ooc_150mhz.xdc"
MLP_AXIL_HARNESS="$ROOT/rtl/integration/hap_mlp_axil_control_registered_ooc_harness.sv"
CLOCK_XDC="$ROOT/vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc"
META_RTL="$ROOT/rtl/mlp/hap_mlp_weight_meta_resident_ab.sv"
META_OOC="$SCRIPTS/synth_mlp_weight_meta_resident_ab_ooc.tcl"
META_OOC_RUN="$SCRIPTS/run_mlp_weight_meta_resident_ab_ooc.sh"

fail() {
    printf 'V5 physical-gate static check failed: %s\n' "$*" >&2
    exit 1
}

for file in "$LIB" "$PLACE" "$ROUTE" "$REOPEN" "$SYNTH" "$SYNTH_RUN" \
        "$POST_OPT" "$APPLY" \
        "$SELECTOR_CHECK" "$SELECTOR_RUN" \
        "$PLACE_RUN" "$PLACE_SCREEN_RUN" "$PHYSICAL_LEDGER" "$ROUTE_RUN" \
        "$REOPEN_RUN" "$POST_OPT_RUN" \
        "$PRE_PLACE" "$PRE_PLACE_RUN" \
        "$DEVICE_PROBE" "$DEVICE_PROBE_RUN" \
        "$OOC_CAPACITY" "$OOC_CAPACITY_RUN" "$OOC_FLOORPLAN" \
        "$OOC_PRE_PLACE" "$OOC_PRE_PLACE_RUN" \
        "$OOC_ROUTE" "$OOC_ROUTE_RUN" \
        "$OOC_REOPEN" "$OOC_REOPEN_RUN" "$OOC_REGION3_DIAG" \
        "$FINE19_PROBE" "$FINE19_PROBE_RUN" \
        "$FINE19_LIB" "$COMPOSITE21_LIB" \
        "$COMPOSITE21_PRE_PLACE" "$COMPOSITE21_PRE_PLACE_RUN" \
        "$COMPOSITE21_DIAG" "$COMPOSITE21_DIAG_RUN" \
        "$P9_RECOVERY" "$P9_RECOVERY_RUN" \
        "$P9_TIMING" "$P9_TIMING_RUN" \
        "$ATTENTION_LOCAL_DIAG" "$ATTENTION_LOCAL_DIAG_RUN" \
        "$MLP_OWNER_SYNTH" "$MLP_OWNER_SYNTH_RUN" \
		"$MLP_OWNER_ROUTE" "$MLP_OWNER_ROUTE_RUN" "$MLP_OWNER_XDC" \
		"$P10_PLACE" "$P10_PLACE_RUN" "$P4_LIB" "$P4_PRE_PLACE" \
		"$P4_PRE_PLACE_RUN" "$P4_PLACE" "$P4_PLACE_RUN" \
		"$P4_ROUTE" "$P4_ROUTE_RUN" "$P12_RELIEF_LIB" \
			"$P12_PRE_PLACE" "$P12_PRE_PLACE_RUN" "$P12_PLACE" \
			"$P12_PLACE_RUN" "$P13_RELIEF_LIB" "$P13_LANE_LIB" \
			"$P13_CANDIDATE" "$P13_CANDIDATE_RUN" \
				"$P13_PRE_PLACE" "$P13_PRE_PLACE_RUN" "$P13_PLACE" \
				"$P13_PLACE_RUN" "$P13_LEVEL6_MAP" "$P13_LEVEL6_MAP_RUN" \
				"$P13_TIMING_ROOTS" "$P13_TIMING_ROOTS_RUN" \
        "$MLP_AXIL" "$MLP_AXIL_RUN" "$MLP_AXIL_XDC" \
        "$MLP_AXIL_HARNESS" "$CLOCK_XDC" "$META_RTL" "$META_OOC" \
        "$META_OOC_RUN"; do
    [[ -s "$file" ]] || fail "missing ${file#"$ROOT/"}"
done
bash -n "$SYNTH_RUN" "$SELECTOR_RUN" "$PLACE_RUN" "$PLACE_SCREEN_RUN" "$PHYSICAL_LEDGER" \
    "$ROUTE_RUN" \
    "$REOPEN_RUN" "$POST_OPT_RUN" \
    "$DEVICE_PROBE_RUN" "$PRE_PLACE_RUN" "$OOC_CAPACITY_RUN" \
    "$OOC_PRE_PLACE_RUN" "$OOC_ROUTE_RUN" "$OOC_REOPEN_RUN" \
    "$FINE19_PROBE_RUN" "$COMPOSITE21_PRE_PLACE_RUN" \
    "$COMPOSITE21_DIAG_RUN" "$P9_RECOVERY_RUN" "$P9_TIMING_RUN" \
    "$ATTENTION_LOCAL_DIAG_RUN" "$MLP_OWNER_SYNTH_RUN" \
		"$MLP_OWNER_ROUTE_RUN" "$P10_PLACE_RUN" "$P4_PRE_PLACE_RUN" \
			"$P4_PLACE_RUN" "$P4_ROUTE_RUN" "$P12_PRE_PLACE_RUN" \
			"$P12_PLACE_RUN" "$P13_CANDIDATE_RUN" \
				"$P13_PRE_PLACE_RUN" "$P13_PLACE_RUN" "$P13_LEVEL6_MAP_RUN" \
				"$P13_TIMING_ROOTS_RUN" \
    "$MLP_AXIL_RUN" "$META_OOC_RUN"

for file in "$LIB" "$PLACE" "$ROUTE" "$REOPEN" "$SYNTH" "$POST_OPT" "$APPLY" \
        "$SELECTOR_CHECK" "$DEVICE_PROBE" "$PRE_PLACE" \
        "$OOC_CAPACITY" "$OOC_FLOORPLAN" "$OOC_PRE_PLACE" \
        "$OOC_ROUTE" "$OOC_REOPEN" "$OOC_REGION3_DIAG" \
        "$FINE19_PROBE" "$FINE19_LIB" "$COMPOSITE21_LIB" \
        "$COMPOSITE21_PRE_PLACE" "$COMPOSITE21_DIAG" "$P9_RECOVERY" \
        "$P9_TIMING" "$ATTENTION_LOCAL_DIAG" "$MLP_OWNER_SYNTH" \
		"$MLP_OWNER_ROUTE" "$P10_PLACE" "$P4_LIB" "$P4_PRE_PLACE" \
			"$P4_PLACE" "$P4_ROUTE" "$P12_RELIEF_LIB" "$P12_PRE_PLACE" \
			"$P12_PLACE" "$P13_RELIEF_LIB" "$P13_LANE_LIB" \
				"$P13_CANDIDATE" "$P13_PRE_PLACE" "$P13_PLACE" \
				"$P13_LEVEL6_MAP" "$P13_TIMING_ROOTS" \
        "$MLP_AXIL" "$MLP_AXIL_XDC" "$META_OOC"; do
    TCL_FILE="$file" tclsh <<'EOF'
set fh [open $::env(TCL_FILE) r]
set text [read $fh]
close $fh
if {![info complete $text]} {exit 1}
EOF
done

HAP_ROUTE_SOURCE_PROCS_ONLY=1 ROUTE_HELPER="$ROUTE" tclsh <<'EOF'
source $::env(ROUTE_HELPER)
foreach name {
    hap_parse_summary hap_verify_sha_manifest
    hap_require_complete_place_output_manifest hap_require_manifest_path
    hap_require_exact_manifest_paths hap_xdc_contract hap_clock_contract
    hap_first_slack hap_route_row hap_timing_count hap_cdc_critical
    hap_drc_error_rows hap_bufg_counts hap_safe_report
    hap_utilization_totals hap_route_swiglu_local_clear_audit
    hap_route_require_boundary_contract hap_route_write_boundary_audit
} {
    if {[llength [info commands $name]] != 1} {
        error "P4 route helper did not export $name"
    }
}
puts V5_ROUTE_HELPER_SOURCE_ONLY_PASS
EOF

OOC_FLOORPLAN="$OOC_FLOORPLAN" tclsh <<'EOF'
source $::env(OOC_FLOORPLAN)
set fixture {
Placer Final Level Congestion Reporting
| North | Long | 5 |
| South | Long | 6 |
Router Initial Congestion
| East | Global | 4 |
| West | Long | 6 |
}
set level5 [hap_projection_ooc_floorplan::congestion_counts_at_or_above \
    $fixture 5]
set level6 [hap_projection_ooc_floorplan::congestion_level6_counts $fixture]
if {[dict get $level5 placer] != 2 || [dict get $level5 router] != 1 ||
    [dict get $level5 total] != 3 || [dict get $level6 placer] != 1 ||
    [dict get $level6 router] != 1 || [dict get $level6 total] != 2} {
    error "projection congestion threshold parser mismatch"
}
if {![catch {
    hap_projection_ooc_floorplan::congestion_counts_at_or_above $fixture 0
}]} {
    error "projection congestion parser accepted invalid threshold"
}
EOF

require_literal() {
    local file="$1" literal="$2"
    grep -Fq -- "$literal" "$file" || \
        fail "missing ${file#"$ROOT/"}: $literal"
}
reject_literal() {
    local file="$1" literal="$2"
    ! grep -Fq -- "$literal" "$file" || \
        fail "forbidden ${file#"$ROOT/"}: $literal"
}
require_literal_count() {
    local file="$1" literal="$2" expected="$3" actual
    actual="$(grep -Fc -- "$literal" "$file" || true)"
    [[ "$actual" -eq "$expected" ]] || \
        fail "literal count drifted in ${file#"$ROOT/"}: expected=$expected actual=$actual literal=$literal"
}

# P12 adds X5Y5 to the existing region1 logic range. Vivado represents that
# L-shaped union as two canonical rectangles; keep the exact representation
# under a fast source-only contract.
OOC_FLOORPLAN="$OOC_FLOORPLAN" P12_RELIEF_LIB="$P12_RELIEF_LIB" tclsh <<'EOF'
source $::env(OOC_FLOORPLAN)
source $::env(P12_RELIEF_LIB)
set expected [list CLOCKREGION_X2Y5:CLOCKREGION_X5Y5 \
    CLOCKREGION_X2Y6:CLOCKREGION_X4Y9]
if {$::hap_v5_p12_region1_relief::canonical_ranges ne $expected} {
    error "P12 canonical range contract mismatch"
}
EOF
for literal in \
    'variable contract P12_ATTN_REGION1_LOGIC_PLUS_X5Y5' \
    'variable base_range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' \
    'variable relief_range CLOCKREGION_X5Y5:CLOCKREGION_X5Y5' \
    'CLOCKREGION_X2Y5:CLOCKREGION_X5Y5' \
    'CLOCKREGION_X2Y6:CLOCKREGION_X4Y9' \
    'resize_pblock $pblock -add [list [dict get $plan relief_range]]'; do
    require_literal "$P12_RELIEF_LIB" "$literal"
done
for file in "$P12_PRE_PLACE" "$P12_PLACE"; do
    require_literal "$file" 'input_manifest_entries 14'
done
require_literal "$P12_PLACE_RUN" 'input_manifest_entries=14'
require_literal "$P12_PRE_PLACE" \
    '"V5_P10_P12_PRE_PLACE_PASS"'
require_literal_count "$P12_PLACE" \
    'place_design -directive $place_directive' 1
require_literal "$P12_PLACE" \
    'congestion_level6_or_higher_windows $level6'
require_literal "$P12_PLACE" 'level6_congestion_ok [expr {$level6 == 0}]'
for command in synth_design opt_design place_design phys_opt_design route_design; do
    reject_literal "$P12_PRE_PLACE" "$command"
done

# P13 retains the canonical X5Y5 parent range and adds one exact hard child
# pblock for three capacity-proven region1 lane-logic groups.
OOC_FLOORPLAN="$OOC_FLOORPLAN" P13_RELIEF_LIB="$P13_RELIEF_LIB" \
        P13_LANE_LIB="$P13_LANE_LIB" tclsh <<'EOF'
source $::env(OOC_FLOORPLAN)
source $::env(P13_RELIEF_LIB)
source $::env(P13_LANE_LIB)
set expected [list CLOCKREGION_X2Y5:CLOCKREGION_X5Y5 \
    CLOCKREGION_X2Y6:CLOCKREGION_X4Y9]
if {$::hap_v5_p13_region1_relief::canonical_ranges ne $expected} {
    error "P13 canonical parent range contract mismatch"
}
if {$::hap_v5_p13_region1_lane_relief::selected_lane_ids ne \
        {r2c3 r6c3 r7c3}} {
    error "P13 selected lane contract mismatch"
}
EOF
for literal in \
    'variable contract P13_ATTN_REGION1_LANES_R2C3_R6C3_R7C3_X5Y5' \
    'variable grid_range CLOCKREGION_X5Y5:CLOCKREGION_X5Y5' \
    'variable selected_lane_ids {r2c3 r6c3 r7c3}' \
    '[llength $selected_primitives] != 4974' \
    '$ff != 2271 || $dsp != 0' \
    'add_cells_to_pblock [get_pblocks $name] [dict get $plan primitives]'; do
    require_literal "$P13_LANE_LIB" "$literal"
done
for file in "$P13_PRE_PLACE" "$P13_PLACE"; do
    require_literal "$file" 'input_manifest_entries 15'
done
require_literal "$P13_PRE_PLACE" \
    'p13_region1_lane_contract [dict get $lane_plan contract]'
require_literal "$P13_PLACE" 'p13_region1_lane_contract $lane_contract'
require_literal "$P13_PLACE_RUN" 'input_manifest_entries=15'
require_literal "$P13_PRE_PLACE" '"V5_P10_P13_PRE_PLACE_PASS"'
require_literal_count "$P13_PLACE" \
    'place_design -directive $place_directive' 1
require_literal "$P13_PLACE" \
    'congestion_level6_or_higher_windows $level6'
require_literal "$P13_PLACE" 'level6_congestion_ok [expr {$level6 == 0}]'
for command in synth_design opt_design place_design phys_opt_design route_design; do
    reject_literal "$P13_PRE_PLACE" "$command"
    reject_literal "$P13_CANDIDATE" "$command"
done
for command in create_pblock resize_pblock add_cells_to_pblock \
        write_checkpoint; do
    reject_literal "$P13_CANDIDATE" "$command"
done
for command in synth_design opt_design place_design phys_opt_design \
        route_design create_pblock resize_pblock add_cells_to_pblock \
        write_checkpoint; do
    reject_literal "$P13_LEVEL6_MAP" "$command"
done
require_literal "$P13_LEVEL6_MAP" \
    'status V5_P10_P13_LEVEL6_PHYSICAL_MAP_PASS'
require_literal "$P13_LEVEL6_MAP" \
    'error "level6_windows count mismatch: expected=9 actual=$window_count"'
require_literal "$P13_LEVEL6_MAP_RUN" 'level6_windows_profiled=9'
for command in synth_design opt_design place_design phys_opt_design \
        route_design create_pblock resize_pblock add_cells_to_pblock \
        write_checkpoint; do
    reject_literal "$P13_TIMING_ROOTS" "$command"
done
require_literal "$P13_TIMING_ROOTS" \
    'status V5_P10_P13_TIMING_ROOT_DIAGNOSIS_PASS'
require_literal "$P13_TIMING_ROOTS_RUN" 'setup_paths_profiled=200'

require_literal "$CLOCK_XDC" \
    'create_clock -name core_clk -period 10.000 [get_ports core_clk]'
require_literal "$CLOCK_XDC" \
    'create_clock -name ddr0_clk -period 3.333 [get_ports ddr0_clk]'
require_literal "$CLOCK_XDC" \
    'create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]'
require_literal "$PLACE_RUN" \
    'attention_mlp_production_v5_ooc_clocks_100mhz.xdc'
require_literal "$PLACE" \
    '{core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333}'
require_literal "$ROUTE_RUN" \
    'attention_mlp_production_v5_ooc_clocks_100mhz.xdc'
require_literal "$ROUTE" \
    'core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300'
require_literal "$ROUTE" \
    'core_period_ns 10.000 ddr0_period_ns 3.333 ddr1_period_ns 3.333'
require_literal "$PLACE" 'jobs $jobs core_clock_mhz 100'
require_literal "$ROUTE_RUN" '[core_clock_mhz]=100'
for file in "$PLACE" "$ROUTE" "$ROUTE_RUN"; do
    reject_literal "$file" 'core_clock_mhz 150'
    reject_literal "$file" 'core_clock_mhz=150'
    reject_literal "$file" '[core_clock_mhz]=150'
done

# The cohort16 capacity probe is read-only and may wait for exactly one heavy
# slot at a 30-60 minute cadence.  It binds all inputs before waiting and
# revalidates them immediately before launch.
for literal in \
	'set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)' \
	'set input_manifest_sha $::env(HAP_CAPACITY_INPUT_MANIFEST_SHA256)' \
	'active_region2_shared_x0_x1' \
	'active_region3_shared_x0_x1' \
	'active_region23_shared_x0_x1' \
	'active_region1_owner_x2_x4' \
	'active_region0_frontend_x4_x5' \
	'active_center_total_x2_x5' \
		'active_region1_cols4_5_dsp_x3_x4' \
		'active_region1_cols6_7_dsp_x2_x3' \
	'active_region1_logic_residual_x2_x4' \
	'active_owner_region2_weight_x2_x4_y5_y6' \
	'candidate_count 10' \
	'center_region1_bisect_exact_cover' \
	'center_region1_dsp_stripe_exact_cover' \
	'region0_input_localization_ok $region0_localization_ok' \
	'region3_input_localization_ok $region3_localization_ok' \
	'active_floorplan_raw_capacity_ok $active_capacity_ok' \
	'canonical_floorplan_mutated 0 implementation_commands_run 0' \
	'owner_region2_weight_anchor_ok $owner_region2_weight_anchor_ok' \
	'checkpoint_written 0 status $status'; do
    require_literal "$OOC_CAPACITY" "$literal"
done
reject_literal "$OOC_CAPACITY" 'hap_projection_ooc_floorplan::apply'
[[ "$(grep -Fc -- 'write_candidate $fp' "$OOC_CAPACITY")" -eq 10 ]] || \
		fail 'cohort16 capacity candidate count drifted from 10'
for literal in \
		'pb_projection_center_region2_shared_cr_x0y5_x1y9' \
		'pb_projection_center_region3_shared_cr_x0y5_x1y9' \
			'pb_projection_center_region1_cols4_5_dsp_cr_x3y5_x4y9' \
			'pb_projection_center_region1_cols6_7_dsp_cr_x2y5_x3y9' \
		'pb_projection_center_region1_logic_residual_cr_x2y5_x4y9' \
		'pb_projection_owner_cr_x2y5_x4y9' \
		'pb_projection_owner_region2_weight_cr_x2y5_x4y6' \
		'pb_projection_center_region0_frontend_cr_x4y5_x5y9'; do
	require_literal_count "$OOC_FLOORPLAN" "$literal" 1
done
for literal in \
		'key center_region3_floorplan_primitives' \
		'key owner_residual_floorplan_primitives' \
		'key owner_region2_weight_primitives' \
		'proc hap_projection_ooc_floorplan::discover {{dut_path u_dut} \' \
		'{allow_empty_center_wrapper 0}} {' \
		'if {!$allow_empty_center_wrapper &&' \
		'proc hap_projection_ooc_floorplan::partition_region3_input_staging {' \
		'proc hap_projection_ooc_floorplan::region0_input_localization_ok {plan}' \
		'proc hap_projection_ooc_floorplan::region3_input_localization_ok {plan}' \
		'proc hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok {plan}' \
		'activation_source $activation_source_count 8192' \
		'zero_point_source $zero_point_source_count 256' \
		'weight_ff_source $weight_ff_source_count 4096' \
		'weight_lut_source $weight_lut_source_count 4096' \
		'if {($index / 256) % 4 == 0}' \
		'if {($index / 8) % 4 == 0}' \
		'if {$index >= 512 && $index < 1024}' \
		'$region0_activation_primitives 2048' \
		'$region0_zero_point_primitives 64' \
		'$region0_weight_ff_primitives 512' \
		'$region0_weight_lut_primitives 512' \
		'[llength $region0_input_primitives] != 3136' \
		'[count_ref $region0_input_primitives FDRE] != 2624' \
		'[count_ref $region0_input_primitives LUT3] != 512' \
		'[count_ref $region0_input_primitives DSP48E2] != 0' \
		'$activation_primitives 2048' \
		'$zero_point_primitives 64' \
		'$owner_weight_ff_primitives 512' \
		'$owner_weight_lut_primitives 512' \
		'$owner_region2_weight_ff_primitives 1024' \
		'$owner_region2_weight_lut_primitives 1024' \
		'[llength $region3_input_primitives] != 2112' \
		'[count_ref $region3_input_primitives FDRE] != 2112' \
		'[count_ref $region3_input_primitives LUT3] != 0' \
		'[count_ref $region3_input_primitives DSP48E2] != 0' \
		'owner_region0_input_exact_cover' \
		'owner_region3_input_exact_cover' \
		'owner_region2_weight_exact_cover' \
		'region3_weight_owner_residency_ok'; do
	require_literal "$OOC_FLOORPLAN" "$literal"
done
require_literal_count "$OOC_FLOORPLAN" \
		'CLOCKREGION_X0Y5:CLOCKREGION_X1Y9' 3
require_literal "$OOC_PRE_PLACE" \
		'[dict get $pblock_audit pblock_count] == 10'
require_literal_count "$OOC_FLOORPLAN" \
		'CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' 2
	require_literal_count "$OOC_FLOORPLAN" \
			'CLOCKREGION_X3Y5:CLOCKREGION_X4Y9' 1
require_literal_count "$OOC_FLOORPLAN" \
			'CLOCKREGION_X2Y5:CLOCKREGION_X3Y9' 1
require_literal_count "$OOC_FLOORPLAN" \
		'CLOCKREGION_X2Y5:CLOCKREGION_X4Y6' 1
require_literal_count "$OOC_FLOORPLAN" \
		'CLOCKREGION_X4Y5:CLOCKREGION_X5Y9' 1
for literal in \
			'pb_projection_center_region1_cr_x2y5_x4y9' \
			'pb_projection_center_region1_cols4_5_cr_x3y5_x3y9' \
			'pb_projection_center_region1_cols4_5_dsp_cr_x3y5_x3y9' \
			'pb_projection_center_region1_cols6_7_cr_x2y5_x2y9' \
			'pb_projection_center_region1_residual_cr_x2y5_x4y9' \
			'pb_projection_center_region1_cols4_5_cr_x3y5_x4y9' \
			'pb_projection_center_region1_cols6_7_cr_x2y5_x3y9' \
			'pb_projection_owner_cr_x2y5_x3y9' \
			'pb_projection_center_region2_cr_x0y5_x0y9' \
			'pb_projection_center_region3_cr_x1y5_x1y9' \
			'CLOCKREGION_X0Y5:CLOCKREGION_X0Y9' \
			'CLOCKREGION_X1Y5:CLOCKREGION_X1Y9'; do
	reject_literal "$OOC_FLOORPLAN" "$literal"
done
for literal in \
    'HAP_WAIT_FOR_SLOT="${HAP_WAIT_FOR_SLOT:-0}"' \
    'HAP_POLL_SECONDS="${HAP_POLL_SECONDS:-3600}"' \
    '(( HAP_POLL_SECONDS >= 1800 && HAP_POLL_SECONDS <= 3600 ))' \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'sleep "$HAP_POLL_SECONDS"' \
    'INPUT_SHA256SUMS' \
    'sha256sum -c --strict' \
		'candidate_count=10' \
		'candidate_region2_label=active_region2_shared_x0_x1' \
		'candidate_region2_raw_capacity_ok=1' \
		'candidate_region3_label=active_region3_shared_x0_x1' \
	'candidate_region3_raw_capacity_ok=1' \
		'candidate_region23_label=active_region23_shared_x0_x1' \
		'candidate_region23_primitive_count=109526' \
		'candidate_region23_lut_demand=53703' \
		'candidate_region23_lut_capacity=128160' \
		'candidate_region23_lut_util_pct=41.903' \
		'candidate_region23_ff_demand=51489' \
		'candidate_region23_ff_capacity=256320' \
		'candidate_region23_ff_util_pct=20.088' \
		'candidate_region23_dsp_demand=816' \
		'candidate_region23_dsp_capacity=960' \
		'candidate_region23_dsp_util_pct=85.000' \
		'candidate_region23_raw_capacity_ok=1' \
	'candidate_region1_owner_raw_capacity_ok=1' \
	'candidate_region0_frontend_raw_capacity_ok=1' \
		'candidate_center_total_raw_capacity_ok=1' \
		'candidate_region1_cols4_5_dsp_demand=272' \
			'candidate_region1_cols4_5_dsp_raw_capacity_ok=1' \
			'candidate_region1_cols6_7_dsp_demand=272' \
			'candidate_region1_cols6_7_dsp_raw_capacity_ok=1' \
			'candidate_region1_logic_residual_dsp_demand=0' \
			'candidate_region1_logic_residual_raw_capacity_ok=1' \
		'candidate_owner_region2_weight_primitive_count=2048' \
		'candidate_owner_region2_weight_lut_demand=1024' \
		'candidate_owner_region2_weight_ff_demand=1024' \
		'candidate_owner_region2_weight_dsp_demand=0' \
		'candidate_owner_region2_weight_raw_capacity_ok=1' \
		'center_region1_lane_roots=32' \
		'center_region1_cols4_5_lane_roots=16' \
		'center_region1_cols6_7_lane_roots=16' \
			'center_region1_bisect_exact_cover=1' \
		'center_region1_dsp_stripe_exact_cover=1' \
		'owner_region2_weight_ff_primitives=1024' \
		'owner_region2_weight_lut_primitives=1024' \
		'owner_region2_weight_primitives=2048' \
		'owner_region2_weight_exact_cover=1' \
		'region0_input_activation_primitives=2048' \
		'region0_input_zero_point_primitives=64' \
		'region0_input_weight_ff_primitives=512' \
		'region0_input_weight_lut_primitives=512' \
		'region0_input_weight_primitives=1024' \
		'region0_input_primitives=3136' \
		'region0_input_fdre=2624' \
		'region0_input_lut3=512' \
		'region0_input_dsp48e2=0' \
		'owner_region0_input_exact_cover=1' \
		'region0_input_localization_ok=1' \
		'region3_input_activation_primitives=2048' \
		'region3_input_zero_point_primitives=64' \
		'region3_input_weight_ff_primitives=0' \
		'region3_input_weight_lut_primitives=0' \
		'region3_owner_weight_ff_primitives=512' \
		'region3_owner_weight_lut_primitives=512' \
		'region3_input_primitives=2112' \
		'region3_input_fdre=2112' \
		'region3_input_lut3=0' \
		'region3_input_dsp48e2=0' \
		'owner_region3_input_exact_cover=1' \
		'region3_weight_owner_residency_ok=1' \
		'region3_input_localization_ok=1' \
		'owner_region2_weight_anchor_ok=1' \
		'active_floorplan_raw_capacity_ok=1' \
	'canonical_floorplan_mutated=0'; do
    require_literal "$OOC_CAPACITY_RUN" "$literal"
done

# The selected cohort16 experiment must use one authenticated DCP and one
# batch Vivado slot at every stage.  Route has no historical fallback DCP,
# and the independent reopen may consume only the strict-PASS route artifact.
for file in "$OOC_PRE_PLACE_RUN" "$OOC_ROUTE_RUN" "$OOC_REOPEN_RUN"; do
    for literal in \
        "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
        'require_free_batch_slot' \
        'HAP_EXPECTED_DCP_SHA256' \
        'HAP_INPUT_MANIFEST_SHA256' \
        'sha256sum -c --strict' \
        'input_sha_postcheck.txt' \
        'input_manifest_post_match' \
        'OUTPUT_SHA256SUMS'; do
        require_literal "$file" "$literal"
    done
done
for file in "$OOC_PRE_PLACE" "$OOC_ROUTE" "$OOC_REOPEN"; do
    for literal in \
        'set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)' \
        'set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)' \
        'input_dcp_sha256 $actual_dcp_sha' \
        'input_manifest_sha256 $input_manifest_sha'; do
        require_literal "$file" "$literal"
    done
    for literal in \
        'center_region1_cols4_5_dsp_primitives' \
        'center_region1_cols6_7_dsp_primitives' \
        'center_region1_logic_residual_primitives' \
        'center_region1_dsp_stripe_exact_cover' \
        'owner_region2_weight_ff_primitives' \
        'owner_region2_weight_lut_primitives' \
        'owner_region2_weight_primitives' \
        'owner_region2_weight_exact_cover' \
        'region0_input_activation_primitives' \
        'region0_input_zero_point_primitives' \
        'region0_input_weight_ff_primitives' \
        'region0_input_weight_lut_primitives' \
        'region0_input_weight_primitives' \
        'region0_input_primitives' \
        'owner_region0_input_exact_cover' \
        'region0_input_localization_ok' \
        'region3_input_activation_primitives' \
        'region3_input_zero_point_primitives' \
        'region3_input_weight_ff_primitives' \
        'region3_input_weight_lut_primitives' \
        'region3_owner_weight_ff_primitives' \
        'region3_owner_weight_lut_primitives' \
        'region3_input_primitives' \
        'owner_region3_input_exact_cover' \
        'region3_weight_owner_residency_ok' \
        'region3_input_localization_ok' \
        'owner_region2_weight_anchor_ok'; do
        require_literal "$file" "$literal"
    done
done
for file in "$OOC_PRE_PLACE_RUN" "$OOC_ROUTE_RUN" "$OOC_REOPEN_RUN"; do
    for literal in \
        'floorplan_center_region1_cols4_5_dsp_primitives=272' \
        'floorplan_center_region1_cols6_7_dsp_primitives=272' \
        'floorplan_center_region1_logic_residual_dsp48e2=0' \
        'floorplan_center_region1_dsp_stripe_exact_cover=1' \
        'floorplan_owner_region2_weight_ff_primitives=1024' \
        'floorplan_owner_region2_weight_lut_primitives=1024' \
        'floorplan_owner_region2_weight_primitives=2048' \
        'floorplan_owner_region2_weight_exact_cover=1' \
        'floorplan_region0_input_activation_primitives=2048' \
        'floorplan_region0_input_zero_point_primitives=64' \
        'floorplan_region0_input_weight_ff_primitives=512' \
        'floorplan_region0_input_weight_lut_primitives=512' \
        'floorplan_region0_input_weight_primitives=1024' \
        'floorplan_region0_input_primitives=3136' \
        'floorplan_region0_input_fdre=2624' \
        'floorplan_region0_input_lut3=512' \
        'floorplan_region0_input_dsp48e2=0' \
        'floorplan_owner_region0_input_exact_cover=1' \
        'floorplan_region0_input_localization_ok=1' \
        'floorplan_region3_input_activation_primitives=2048' \
        'floorplan_region3_input_zero_point_primitives=64' \
		'floorplan_region3_input_weight_ff_primitives=0' \
		'floorplan_region3_input_weight_lut_primitives=0' \
		'floorplan_region3_owner_weight_ff_primitives=512' \
		'floorplan_region3_owner_weight_lut_primitives=512' \
		'floorplan_region3_input_primitives=2112' \
		'floorplan_region3_input_fdre=2112' \
		'floorplan_region3_input_lut3=0' \
		'floorplan_region3_input_dsp48e2=0' \
		'floorplan_owner_region3_input_exact_cover=1' \
		'floorplan_region3_weight_owner_residency_ok=1' \
		'floorplan_region3_input_localization_ok=1' \
		'floorplan_owner_region2_weight_anchor_ok=1'; do
        require_literal "$file" "$literal"
    done
done
for literal in \
    ': "${HAP_INPUT_DCP:?set HAP_INPUT_DCP to the selected fresh post-synth checkpoint}"' \
    'HAP_PLACE_DIRECTIVE="${HAP_PLACE_DIRECTIVE:-AltSpreadLogic_high}"' \
    'HAP_MAX_POST_PLACE_LEVEL5_WINDOWS="${HAP_MAX_POST_PLACE_LEVEL5_WINDOWS:-1}"' \
    'RUN_CONTRACT="$HAP_REPORT_DIR/RUN_CONTRACT"' \
    'level6_or_higher_congestion_windows=0'; do
    require_literal "$OOC_ROUTE_RUN" "$literal"
done
reject_literal "$OOC_ROUTE_RUN" \
    'projection_core16x16_w8_reuse_registered_ooc_synth_20260825_011454'
require_literal "$OOC_ROUTE" 'set place_directive AltSpreadLogic_high'
for literal in \
    'stage REGISTERED_OOC_POST_PLACE_FAST_GATE' \
    'set post_place_drc_errors [llength [get_drc_violations -quiet -filter \' \
    'set post_place_data_bufg 0' \
    'hap_projection_ooc_floorplan::congestion_level6_counts \' \
    'hap_projection_ooc_floorplan::congestion_counts_at_or_above \' \
    'set post_place_level5_screen_ok [expr {' \
    'set post_place_fast_gate_ok [expr {' \
    'post_place_region0_input_localization_ok' \
    'post_place_region3_input_localization_ok' \
    'write_checkpoint -force [file join $out post_place_diagnostic_only.dcp]' \
    'if {!$post_place_fast_gate_ok}' \
    'post_place_fast_gate_ok $post_place_fast_gate_ok'; do
    require_literal "$OOC_ROUTE" "$literal"
done
for literal in \
    'post_place_fast_gate.txt' \
    'post_place_diagnostic_only.dcp' \
    'post_place_drc_errors=0' \
    'post_place_data_bufg=0' \
    'post_place_level6_or_higher_congestion_windows=0' \
    'post_place_region0_input_localization_ok=1' \
    'post_place_region3_input_localization_ok=1' \
    'post_place_owner_region2_weight_anchor_ok=1' \
    'post_place_strict_gate_ok=1' \
    'post_place_level5_screen_ok=1' \
    'post_place_fast_gate_ok=1'; do
    require_literal "$OOC_ROUTE_RUN" "$literal"
done
OOC_ROUTE_TEXT="$(tr '\n' ' ' < "$OOC_ROUTE")"
for literal in \
    'place_design -directive $place_directive' \
    'write_checkpoint -force [file join $out post_place_diagnostic_only.dcp]' \
    'report_design_analysis -congestion -file $post_place_congestion_path' \
    'set post_place_fast_gate_ok' \
    'if {!$post_place_fast_gate_ok}' \
    'write_checkpoint -force [file join $out post_place.dcp]' \
    'phys_opt_design -directive $pre_route_physopt_directive' \
    'route_design -directive $route_directive'; do
    case "$OOC_ROUTE_TEXT" in
        *"$literal"*) OOC_ROUTE_TEXT="${OOC_ROUTE_TEXT#*"$literal"}" ;;
        *) fail 'Attention OOC post-place fast-gate order drifted' ;;
    esac
done
for literal in \
    'route_output_manifest="$route_dir/OUTPUT_SHA256SUMS"' \
    "grep -Fqx 'status=PASS' \"\$route_summary\"" \
    "grep -Fqx 'status=PASS' \"\$route_launcher_status\"" \
    'route_output_sha_precheck.txt' \
    'route_output_sha_postcheck.txt'; do
    require_literal "$OOC_REOPEN_RUN" "$literal"
done

# The MLP control-plane route uses an exception-free registered boundary,
# owns the heavy slot at launch, and fails closed on timing/route provenance.
require_literal_count "$MLP_AXIL_RUN" 'require_free_batch_slot' 3
for literal in \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'HAP_INPUT_MANIFEST_SHA256' \
    'input_sha_postcheck.txt' \
    'input_manifest_post_match' \
    'status=$launcher_status' \
    'OUTPUT_SHA256SUMS'; do
    require_literal "$MLP_AXIL_RUN" "$literal"
done
for literal in \
    'set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]'; do
    require_literal "$MLP_AXIL_XDC" "$literal"
done
for literal in set_input_delay set_output_delay set_false_path \
        set_max_delay set_min_delay; do
    reject_literal "$MLP_AXIL_XDC" "$literal"
done
for literal in \
    'module hap_mlp_axil_control_registered_ooc_harness' \
    'localparam integer SRC_W = S_META_ERROR + 1' \
    'localparam integer SINK_W = 409' \
    'hap_mlp_axil_control #(.PRODUCTION_INTEGRATION(1)) u_dut'; do
    require_literal "$MLP_AXIL_HARNESS" "$literal"
done
for literal in \
    'set top hap_mlp_axil_control_registered_ooc_harness' \
    'NAME =~ src_r_reg* && REF_NAME =~ FD*' \
    'NAME =~ sink_r_reg* && REF_NAME =~ FD*' \
    'set timing_coverage_ok [expr {' \
    'set route_clean [expr {' \
    'set data_bufg 0' \
    'timing_coverage_ok $timing_coverage_ok' \
    'route_clean $route_clean' \
    'drc_errors $drc status $status' \
    'write_checkpoint -force [file join $report_dir post_route.dcp]'; do
    require_literal "$MLP_AXIL" "$literal"
done

# Common V5-only physical audit: exact hard-pblock contract, exact global
# DSP/URAM coverage and fail-closed wrong/unplaced accounting.
for literal in \
    'proc hap_v5_floorplan::physical_slr_audit_for_cells {cells}' \
    'proc hap_v5_floorplan::physical_slr_counts_for_cells {cells}' \
    'proc hap_v5_floorplan::device_site_slr_map {}' \
    'proc hap_v5_floorplan::physical_metrics {live_plan {pblock_audit {}}}' \
    'proc hap_v5_floorplan::physical_ok {live_plan metrics}' \
    'proc hap_v5_floorplan::pblock_specs {live_plan {variant P0_11}}' \
    'proc hap_v5_floorplan::expanded_pblock_primitives {pblock}' \
    'proc hap_v5_floorplan::pblockable_primitives {cells}' \
    '$primitive_level ne "INTERNAL"' \
    'proc hap_v5_floorplan::audit_pblock_contract {live_plan require_placed \' \
    '{variant P0_11} {delegate_specs {}}} {' \
    'delegated_member_count $delegated_count_total' \
    'if {$variant ne "P2_COHORT16_COL2_12_2" &&' \
    '$variant ne "P1_ATTN_COL2_12_2" &&' \
    'set expected_count [expr {$variant eq "legacy10" ? 10 : 11}]' \
    'contract_variant $variant' \
    'if {[llength $missing] != 0}' \
    'if {$covered_dsp_names ne $all_dsp_names ||' \
    'if {$covered_uram_names ne $all_uram_names ||' \
    'if {$ref eq "GND" || $ref eq "VCC"}' \
    'set refs [get_property REF_NAME $cells]' \
    'set physical_direct [get_property SLR_INDEX $physical_cells]' \
    'set physical_locs [get_property LOC $physical_cells]' \
    'set physical_bels [get_property BEL $physical_cells]' \
    'foreach property {SLR_INDEX LOC BEL}' \
    'set virtual_sites [get_sites -quiet -of_objects $virtual_cells]' \
    'set virtual_bels [get_bels -quiet -of_objects $virtual_cells]' \
    'set is_placed_empty $physical_count' \
    'set unique_locs [lsort -dictionary -unique $physical_locs]' \
    'set sites [get_sites -quiet $unique_locs]' \
    'if {$unique_site_names ne $unique_locs}' \
    'set slr_sites [get_sites -quiet -of_objects $slr]' \
    '[get_slrs -quiet -of_objects $slr_sites]' \
    'if {$mapped_site_names ne $all_site_names}' \
    'set device_map [hap_v5_floorplan::device_site_slr_map]' \
    'set site_to_index [dict get $device_map site_to_slr]' \
    'if {$direct ne "" && $direct != $index}' \
    'virtual_gnd $virtual_gnd virtual_vcc $virtual_vcc' \
    'direct_slr_empty $direct_slr_empty' \
    'is_placed_empty $is_placed_empty' \
    'if {$placed_wrong != 0}' \
    'if {[llength $unique_member_names] != $member_count_sum}' \
    'hap_attention_row_head128' \
    'hap_kv12_cache' \
    'hap_kv12_quantizer4' \
    'hap_v5_floorplan::require_count attention_rows $attention_rows 1' \
    'hap_v5_floorplan::require_count kv_caches $kv_caches 1' \
    'hap_v5_floorplan::require_count kv_quantizers4 $kv_quantizers4 1' \
    'set p2_contract [expr {$variant eq "P2_COHORT16_COL2_12_2"}]' \
    'set col3_contract [expr {$p1_contract || $p2_contract}]' \
    'if {$p2_contract && $attention_board_variant ne "cohort16"}' \
    'set expected_attention_dsp [expr {$p2_contract ? 2296 : 2304}]' \
    '[llength $attention_dsp] != $expected_attention_dsp' \
    'hap_v5_floorplan::cell_is_below $root $attention_root' \
    'P0 Attention-row signature mismatch' \
    'P0 KV-cache signature mismatch' \
    '[llength $attention_row_dsp] != 52' \
    '[llength $attention_row_ramb36] != 0' \
    '[llength $attention_row_ramb18] != 0' \
    '[llength $attention_row_uram] != 0' \
    '[llength $kv_cache_dsp] != 0' \
    '[llength $kv_cache_ramb36] != 88' \
    '[llength $kv_cache_ramb18] != 2' \
    '[llength $kv_cache_uram] != 0' \
    '[llength $row_cache_overlap] != 0' \
    '[llength $island_quantizer_overlap] != 0' \
    'hap_v5_floorplan::require_count swiglu_frontends \' \
    '$swiglu_frontends 1' \
    'hap_v5_floorplan::require_count swiglu_row_leaves $row_leaves 2' \
    'hap_v5_floorplan::require_count swiglu_unique_hadamard \' \
    '$central_hadamards 1' \
    'hap_v5_floorplan::require_count swiglu_fold2_hadamard \' \
    '$fold2_hadamards 0' \
    'hap_v5_floorplan::require_count swiglu_quantizers \' \
    '$central_quantizers 4' \
    'hap_v5_floorplan::require_count swiglu_silu_units $silu_units 2' \
    'set outer0_primitives [hap_v5_floorplan::list_union \' \
    '$compute_branch0_primitives $row_leaf0_primitives]' \
    'set outer2_primitives [hap_v5_floorplan::list_union \' \
    '$compute_branch2_primitives $row_leaf1_primitives]' \
    '[llength $outer0_dsp] != 1538' \
    '[llength $outer2_dsp] != 1538' \
    '[llength $outer0_ramb36] != 102' \
    '[llength $outer2_ramb36] != 102' \
    'set center_nonprojection_dsp \' \
    '[hap_v5_floorplan::list_subtract $center_dsp \' \
    '$center_projection_dsp]' \
    '[expr {$p2_contract ? 149 : 161}]' \
    '$move0 != 16 || [llength $lanes_slr1] != 96 ||' \
    '$move2 != 16 || $planned0 != 1862 || $planned1 != 1781 ||' \
    '$move2 != 16 || $planned0 != 1862 || $planned1 != 1793 ||' \
    '$planned2 != 1810' \
    '$move0 != 12 || [llength $lanes_slr1] != 101 ||' \
    '$move2 != 15 || $planned0 != 1794 || $planned1 != 1878 ||' \
    '$planned2 != 1793' \
    'Fresh P0_11 split drifted:' \
    'set outer0_key outer0_primitives' \
    'set outer2_key outer2_primitives' \
    'key $outer0_key dsp $outer0_dsp uram 0 \' \
    'key $outer2_key dsp $outer2_dsp uram 0 \' \
    'ramb36 $outer0_ramb36 ramb18 0]' \
    'ramb36 $outer2_ramb36 ramb18 0]'; do
    require_literal "$LIB" "$literal"
done
reject_literal "$LIB" 'get_property IS_PLACED'

# Million-cell selector and pblock audits must use Vivado bulk property calls.
# Per-object get_property loops made a read-only pre-place audit exceed 9:53.
for literal in \
    'set names [get_property NAME $cells]' \
    'V5 bulk NAME cardinality mismatch' \
    'set refs [get_property REF_NAME $cells]' \
    'V5 bulk REF_NAME cardinality mismatch'; do
    require_literal "$LIB" "$literal"
done
for literal in \
    'set primitive_flags [get_property IS_PRIMITIVE $direct_members]' \
    'set member_refs [get_property REF_NAME $members]' \
    'proc hap_v5_fine19::spec_is_soft {spec}' \
    'set_property IS_SOFT [expr {$soft ? "true" : "false"}]' \
    'if {$soft} {incr soft_pblock_count}' \
    '(!$soft && [dict get $placement wrong] != 0)' \
    'soft_outside [dict get $audit soft_outside]' \
    '{allow_optimizer_extras 0}' \
    '(!$allow_optimizer_extras && $optimizer_extra_count != 0)' \
    '($allow_optimizer_extras && $optimizer_extra_count > 4096)' \
    '($allow_optimizer_extras && abs($primitive_delta) > 4096)' \
    'proc hap_v5_fine19::physical_metrics {audit {expected_contract_variant ""}}' \
    'proc hap_v5_fine19::physical_ok {metrics}'; do
    require_literal "$FINE19_LIB" "$literal"
done
reject_literal "$FINE19_LIB" \
    '[get_property IS_PRIMITIVE $member]'
reject_literal "$FINE19_LIB" \
    'switch -- [get_property REF_NAME $member]'
for literal in \
    'variable contract_variant P9_COHORT16_MLP_CENTRAL_X2X4_21' \
    'variable expected_fine_members 1432847' \
    'variable expected_mlp_residual_members 285796' \
    'variable expected_attention_direct_members 71350' \
    'variable expected_central_island_members 197091' \
    'variable expected_mlp_remaining_members 88785' \
    'variable expected_center_dsp_remaining 5' \
    'variable central_anchor_range CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' \
    'variable attention_direct_constrained 0' \
    'proc hap_v5_composite21::discover {base_plan fine_plan' \
    'proc hap_v5_composite21::full_specs {base_plan fine_plan composite_plan}' \
    'name pb_v5_mlp_central_frontends_cr_x2y5_x4y9' \
    'cells [dict get $composite_plan central_island_primitives]' \
    'name pb_v5_center_nonprojection_dsp_residual_slr1' \
    'cells [dict get $composite_plan center_dsp_remaining_primitives]' \
    'name pb_v5_mlp_residual_without_central_frontends_slr1' \
    'cells [dict get $composite_plan mlp_remaining_primitives]' \
    'central_partition_ok 1' \
    'hap_v5_fine19::apply_specs' \
    'hap_v5_fine19::audit_specs' \
    'proc hap_v5_composite21::physical_metrics {audit}' \
    'if {![dict exists $audit records $name placed_wrong]}' \
    'pb_v5_mlp_central_frontends_cr_x2y5_x4y9 placed_wrong' \
    'pb_v5_center_nonprojection_dsp_residual_slr1 placed_wrong' \
    'pb_v5_mlp_residual_without_central_frontends_slr1 placed_wrong' \
    'set compatibility_audit $audit' \
    'dict set compatibility_audit records' \
    'pb_v5_center_nonprojection_dsp_slr1 placed_wrong' \
    'set metrics [hap_v5_fine19::physical_metrics' \
    '$compatibility_audit $contract_variant]' \
    'dict set metrics central_island_wrong $central_island_wrong' \
    'dict set metrics center_dsp_remaining_wrong $center_dsp_remaining_wrong' \
    'dict set metrics mlp_remaining_wrong $mlp_remaining_wrong' \
    'return $metrics' \
    'proc hap_v5_composite21::physical_ok {metrics}'; do
    require_literal "$COMPOSITE21_LIB" "$literal"
done
reject_literal "$COMPOSITE21_LIB" \
    'return [hap_v5_fine19::physical_metrics $audit $contract_variant]'
reject_literal "$COMPOSITE21_LIB" 'pb_v5_attention_direct_slr2'
for literal in \
    'set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan]' \
    'proc hap_composite21_require_nonempty_file {path label}' \
    'hap_composite21_require_nonempty_file $normalized "$label input"' \
    'hap_v5_composite21::apply $base_plan $fine_plan $composite_plan' \
    'set audit [hap_v5_composite21::audit' \
    'V5_COMPOSITE21_PRE_PLACE_AUDIT_PASS' \
    'contract_variant [dict get $composite_plan contract_variant]' \
    'pblock_count [dict get $audit pblock_count]' \
    'soft_pblock_count [dict get $audit soft_pblock_count]' \
    'soft_outside [dict get $audit soft_outside]' \
    'pre_place_drc_errors $pre_place_drc_errors' \
    'floorplan_mutated_in_memory 1 implementation_commands_run 0' \
    'checkpoint_written 0 status $status'; do
    require_literal "$COMPOSITE21_PRE_PLACE" "$literal"
done
for literal in \
    '[[ $# -eq 2 ]]' \
    'HAP_COMPOSITE21_PROBE_OUTPUT_SHA' \
    '[[ "$HAP_JOBS" == 32 ]]' \
    '(cd / && sha256sum -c --strict "$HAP_COMPOSITE21_PROBE_OUTPUT_SHA")' \
    'contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
    'pblock_count=21' \
    'central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' \
    'central_island_count=197091' \
    'mlp_remaining_count=88785' \
    'center_dsp_remaining_dsp=5' \
    'central_partition_ok=1' \
    'soft_pblock_count=0' \
    'soft_outside=0' \
    'pre_place_drc_errors=0' \
    'implementation_commands_run=0' \
    'checkpoint_written=0'; do
    require_literal "$COMPOSITE21_PRE_PLACE_RUN" "$literal"
done
for forbidden in place_design phys_opt_design route_design write_checkpoint \
        write_bitstream; do
    reject_literal "$COMPOSITE21_PRE_PLACE" "$forbidden"
done
for literal in \
    'set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan]' \
    'set attention_direct [dict get $composite_plan attention_direct_primitives]' \
    'attention_direct_top_groups.txt' \
    'attention_direct_level2_groups.txt' \
    'puts $fp "interface_${field}=' \
    'failed_slr2_lut_percent 107.2' \
    'failed_slr12_sll_required 27211' \
    'floorplan_mutated 0' \
    'implementation_commands_run 0 checkpoint_written 0'; do
    require_literal "$COMPOSITE21_DIAG" "$literal"
done
for literal in \
    '[[ $# -eq 2 ]]' \
    'FAILED_P4_PLACE_OUTPUT_SHA256SUMS' \
    '107.2% LUT utilization in SLR2' \
    '27211 SLLs required between SLR1 and SLR2 of 17280 SLLs available' \
    'diagnosis_gate_exit_code=$gate_rc' \
    'floorplan_mutated=0' \
    'implementation_commands_run=0' \
    'checkpoint_written=0'; do
    require_literal "$COMPOSITE21_DIAG_RUN" "$literal"
done
for forbidden in place_design phys_opt_design route_design create_pblock \
        add_cells_to_pblock write_checkpoint write_bitstream; do
    reject_literal "$COMPOSITE21_DIAG" "$forbidden"
done

# P9 recovery may only inspect the diagnostic checkpoint produced after the
# completed placement.  Freeze its lineage, live rediscovery, physical audit,
# congestion parser and explicit non-route-eligible result.
for literal in \
    'set dcp [file normalize $::env(HAP_P9_RECOVERY_DCP)]' \
    'set failed_output_sha [file normalize' \
    'set frozen [hap_p9_recovery_manifest $input_sha 7 $expected_input_sha' \
    'set failed_entries [hap_p9_recovery_manifest $failed_output_sha -1' \
    'failure_stage=post_place_live_rediscovery' \
    'place_design_completed=1 diagnostic_checkpoint_written=1' \
    'acceptance_evidence=0 route_eligible=0 checkpoint_written=0' \
    'open_checkpoint $dcp' \
    'if {[llength [get_pblocks -quiet]] != 21}' \
    'set composite_plan [hap_v5_composite21::discover $base_plan $fine_plan 1]' \
    'set pblock_audit [hap_v5_composite21::audit' \
    'set metrics [hap_v5_composite21::physical_metrics $pblock_audit]' \
    'report_design_analysis -congestion -file $congestion_path' \
    'set congestion_level5_count 0' \
    'set congestion_level6_count 0' \
    'set congestion_schema_ok [expr {$congestion_schema_header_count == 1 &&' \
    'set worst_setup [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]' \
    'set worst_hold [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]' \
    'p9_central_island_wrong_slr [dict get $metrics central_island_wrong]' \
    'p9_center_dsp_remaining_wrong_slr' \
    '[dict get $metrics center_dsp_remaining_wrong]' \
    'p9_mlp_remaining_wrong_slr [dict get $metrics mlp_remaining_wrong]' \
    'congestion_level5_or_higher_windows $congestion_level5_count' \
    'congestion_level6_or_higher_windows $congestion_level6_count' \
    'acceptance_evidence 0 route_eligible 0 floorplan_mutated 0' \
    'implementation_commands_run 0 checkpoint_written 0' \
    'close_design'; do
    require_literal "$P9_RECOVERY" "$literal"
done
P9_RECOVERY_CODE="$(sed -E '/^[[:space:]]*#/d' "$P9_RECOVERY")"
if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
        <<<"$P9_RECOVERY_CODE"; then
    fail 'P9 recovery Tcl contains a mutation command'
fi
for literal in \
    '[[ $# -eq 2 ]]' \
    'export HAP_JOBS="${HAP_JOBS:-32}"' \
    '[[ "$HAP_JOBS" == 32 ]]' \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'another batch Vivado is active; P9 recovery not started' \
    'P9 recovery Tcl contains a forbidden mutation command' \
    'HAP_P9_RECOVERY_INPUT_MANIFEST_SHA256' \
    '(cd / && sha256sum -c --strict "$HAP_P9_RECOVERY_INPUT_SHA")' \
    'status=P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS' \
    'contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
    'pblock_count=21' \
    'pblock_dsp_coverage=5453 pblock_uram_coverage=752 pblock_wrong_slr=0' \
    'p9_central_island_wrong_slr=0 p9_center_dsp_remaining_wrong_slr=0' \
    'p9_mlp_remaining_wrong_slr=0 additional_wrong_slr=0' \
    'congestion_level5_or_higher_windows' \
    'congestion_level6_or_higher_windows' \
    'acceptance_evidence=0 route_eligible=0 floorplan_mutated=0' \
    "'checkpoint_written=0' 'route_eligible=0'" \
    '! -name OUTPUT_SHA256SUMS' \
    'sha256sum -- "${outputs[@]}" > "$HAP_P9_RECOVERY_DIR/OUTPUT_SHA256SUMS"'; do
    require_literal "$P9_RECOVERY_RUN" "$literal"
done

# The timing-root successor is also read-only. It consumes the terminal P9
# recovery manifest and produces endpoint/category evidence, never acceptance.
for literal in \
    'set dcp [file normalize $::env(HAP_P9_TIMING_DCP)]' \
    'set recovery_output_sha [file normalize' \
    'set frozen [hap_p9_timing_manifest $input_sha 4 $expected_input_sha' \
    'set recovery_entries [hap_p9_timing_manifest $recovery_output_sha -1' \
    'status=P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS' \
    'congestion_level5_or_higher_windows=24' \
    'congestion_level6_or_higher_windows=12 fast_gate_ok=0' \
    'acceptance_evidence=0 route_eligible=0' \
    'open_checkpoint $dcp' \
    'if {[llength [get_pblocks -quiet]] != 21}' \
    'set setup_paths [get_timing_paths -quiet -delay_type max -max_paths 500' \
    'set hold_paths [get_timing_paths -quiet -delay_type min -max_paths 500' \
    'hap_p9_timing_write_paths $setup_paths [file join $out setup_paths.tsv]' \
    'hap_p9_timing_write_paths $hold_paths [file join $out hold_paths.tsv]' \
    'report_timing_summary -delay_type min_max -max_paths 500 -nworst 20' \
    'report_timing -delay_type max -max_paths 500 -nworst 20' \
    'report_timing -delay_type min -max_paths 500 -nworst 20' \
    'report_high_fanout_nets -timing -load_types -max_nets 300' \
    'report_clock_utilization -file' \
    'evidence_class READ_ONLY_P9_TIMING_ROOT_DIAGNOSIS' \
    'recovery_terminal_fail_verified 1 pblock_count 21' \
    'source_congestion_level5_or_higher_windows 24' \
    'source_congestion_level6_or_higher_windows 12' \
    'acceptance_evidence 0 route_eligible 0 floorplan_mutated 0' \
    'implementation_commands_run 0 checkpoint_written 0' \
    'status P9_TIMING_ROOT_DIAGNOSIS_PASS' \
    'close_design'; do
    require_literal "$P9_TIMING" "$literal"
done
P9_TIMING_CODE="$(sed -E '/^[[:space:]]*#/d' "$P9_TIMING")"
if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|link_design|read_xdc|create_pblock|resize_pblock|delete_pblock|add_cells_to_pblock|remove_cells_from_pblock|set_property|reset_property|write_checkpoint|write_bitstream|write_cfgmem|launch_runs|wait_on_run)([^[:alnum:]_]|$)' \
        <<<"$P9_TIMING_CODE"; then
    fail 'P9 timing Tcl contains a mutation command'
fi
for literal in \
    '[[ $# -eq 2 ]]' \
    'export HAP_JOBS="${HAP_JOBS:-32}"' \
    '[[ "$HAP_JOBS" == 32 ]]' \
    'status=P9_POST_PLACE_RECOVERY_DIAGNOSIS_PASS' \
    'congestion_level5_or_higher_windows=24' \
    'congestion_level6_or_higher_windows=12 fast_gate_ok=0' \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'another batch Vivado is active; P9 timing diagnosis not started' \
    'P9 timing Tcl contains a forbidden mutation command' \
    'HAP_P9_TIMING_INPUT_MANIFEST_SHA256' \
    '(cd / && sha256sum -c --strict "$HAP_P9_TIMING_INPUT_SHA")' \
    'status=P9_TIMING_ROOT_DIAGNOSIS_PASS' \
    'evidence_class=READ_ONLY_P9_TIMING_ROOT_DIAGNOSIS jobs=32' \
    'recovery_terminal_fail_verified=1 pblock_count=21' \
    'setup_path_count=500 hold_path_count=500' \
    'source_congestion_level5_or_higher_windows=24' \
    'source_congestion_level6_or_higher_windows=12' \
    'acceptance_evidence=0 route_eligible=0 floorplan_mutated=0' \
    "'checkpoint_written=0' 'route_eligible=0'" \
    'required_reports_ok=$reports_ok' \
    '! -name OUTPUT_SHA256SUMS' \
    'sha256sum -- "${outputs[@]}" > "$HAP_P9_TIMING_DIR/OUTPUT_SHA256SUMS"'; do
    require_literal "$P9_TIMING_RUN" "$literal"
done
for literal in \
    'set uncovered_primitives [hap_v5_floorplan::list_subtract' \
    'set mlp_uncovered [hap_v5_floorplan::list_intersection' \
    'set attention_compute_uncovered [hap_v5_floorplan::list_intersection' \
    'set attention_shell_uncovered [hap_v5_floorplan::list_intersection' \
    'set support_uncovered [hap_v5_floorplan::list_subtract' \
    'composite_partition_ok $composite_partition_ok' \
    'subgroup_partition_ok $subgroup_partition_ok' \
    'uncovered_hard_resources_zero $uncovered_hard_resources_zero' \
    'attention0_mlp2_raw_capacity_ok $attention0_mlp2_capacity_ok' \
    'attention2_mlp0_raw_capacity_ok $attention2_mlp0_capacity_ok' \
    'set composite21_plan [hap_v5_composite21::discover $base_plan $fine_plan]' \
    'set composite21_specs [hap_v5_composite21::full_specs' \
    'V5 composite21 spec count mismatch:' \
    'composite21_member_overlap $composite21_member_overlap' \
    'composite21_aggregate_capacity_ok' \
    'composite21_resource_distribution_ok' \
    'canonical_pblock_count_before 0 canonical_pblock_count_after' \
    'implementation_commands_run 0 checkpoint_written 0'; do
    require_literal "$FINE19_PROBE" "$literal"
done
for literal in \
    'composite_capacity="$HAP_FINE19_PROBE_DIR/composite_capacity.txt"' \
    'composite_subgroups="$HAP_FINE19_PROBE_DIR/composite_subgroups.txt"' \
    'composite21_capacity="$HAP_FINE19_PROBE_DIR/composite21_pblock_capacity.txt"' \
    'export HAP_COMPOSITE21_LIB="$COMPOSITE21_LIB"' \
    'POST_OPT_AUDIT_OUTPUT_SHA256SUMS' \
    'HAP_POST_OPT_AUDIT_OUTPUT_SHA' \
    "'post_opt_audit_verified=1'" \
    'attention_postprocess_row_bank_instances=16' \
    'attention_postprocess_store_lut_primitives=19194' \
    'attention_postprocess_store_ff_primitives=24580' \
    "'input_manifest_entries=8'" \
    'P9_DIAG_OUTPUT_SHA256SUMS' \
    'HAP_P9_DIAG_OUTPUT_SHA' \
    "'p9_diag_verified=1'" \
    "'uncovered_dsp48e2=0' 'uncovered_uram288=0'" \
    "'composite_partition_ok=1' 'subgroup_partition_ok=1'" \
    "'composite21_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21'" \
    "'composite21_pblock_spec_count=21'" \
    "'composite21_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9'" \
    "'composite21_central_island_count=197091'" \
    "'composite21_central_island_dsp=80'" \
    "'composite21_mlp_remaining_count=88785'" \
    "'composite21_center_dsp_remaining=5'" \
    "'composite21_central_partition_ok=1'" \
    "'composite21_attention_direct_constrained=0'" \
    "'composite21_soft_pblock_count=0'" \
    "'composite21_residual_member_count=192495'" \
    "'composite21_residual_lut=80958'" \
    "'composite21_hard_slr0_lut=273205'" \
    "'composite21_hard_slr1_lut=312771'" \
    "'composite21_hard_slr2_lut=263359'" \
    "'composite21_flexible_lut=80958'" \
    "'composite21_outer_90pct_lut_headroom=172780'" \
    "'composite21_hard_capacity_ok=1'" \
    "'composite21_flexible_outer_90pct_fit=1'" \
    "grep -c '^aggregate_slr='" \
    "grep -c '^collection='" \
    "grep -c '^candidate='"; do
    require_literal "$FINE19_PROBE_RUN" "$literal"
done
for literal in \
    'proc hap_v5_floorplan::physical_metrics {live_plan}' \
    'set cell_sites [get_sites -quiet -of_objects $cell]' \
    'set cell_bels [get_bels -quiet -of_objects $cell]' \
    'set unique_locs [lsort -dictionary -unique $locs]' \
    'set site_indices [get_property SLR_INDEX $sites]' \
    'get_property SLR_INDEX $sites' \
    'foreach site $sites site_name $site_names index $site_indices {' \
    'if {$direct != $index}' \
    '[get_sites $site_name]'; do
    reject_literal "$LIB" "$literal"
done
for name in \
    pb_v5_mlp_branch_slr0 pb_v5_mlp_branch_slr2 \
    pb_v5_meta_gate_slr0 pb_v5_meta_gate_slr2 \
    pb_v5_meta_down0_slr1 pb_v5_meta_down1_slr1 \
    pb_v5_attention_meta_slr2; do
    [[ "$(grep -Fc -- "[dict create name $name " "$LIB")" -eq 1 ]] || \
        fail "canonical pblock spec is not unique: $name"
done
for spec in \
    'set lane0_pblock [expr {$col3_contract ?' \
    '"pb_v5_attention_projection_left2_slr0" :' \
    'set lane2_pblock [expr {$col3_contract ?' \
    '"pb_v5_attention_projection_right2_slr2" :' \
    'set center_pblock [expr {$col3_contract ?' \
    '"pb_v5_attention_projection_center12_slr1" :' \
    '[dict create name $lane0_pblock \' \
    '[dict create name $lane2_pblock \' \
    '[dict create name $center_pblock target 1 \'; do
    require_literal_count "$LIB" "$spec" 1
done
[[ "$(grep -Fc -- \
    'name pb_v5_attention_row_kv_cache_slr0 target 0' "$LIB")" -eq 1 ]] || \
    fail 'canonical pblock spec is not unique: pb_v5_attention_row_kv_cache_slr0'

# Every production discovery is variant-explicit.  Some implementation hooks
# bind the variant once and deliberately reuse it before and after placement;
# audit both that binding and the exact number of variable-qualified calls.
for spec in \
    "$SELECTOR_CHECK|P2_COHORT16_COL2_12_2|1" \
    "$ROUTE|P2_COHORT16_COL2_12_2|2" \
    "$REOPEN|legacy10|1"; do
    IFS='|' read -r file variant expected <<<"$spec"
    require_literal_count "$file" \
        "hap_v5_floorplan::discover $variant" "$expected"
    require_literal_count "$file" \
        'hap_v5_floorplan::discover' "$expected"
done
require_literal_count "$PLACE" \
    'set contract_variant P9_COHORT16_MLP_CENTRAL_X2X4_21' 1
require_literal_count "$PLACE" \
    'set base_contract_variant P2_COHORT16_COL2_12_2' 1
require_literal_count "$PLACE" \
    'hap_v5_floorplan::discover $base_contract_variant' 2
require_literal_count "$PLACE" 'hap_v5_fine19::discover' 2
require_literal_count "$PLACE" 'hap_v5_composite21::discover' 2
require_literal_count "$APPLY" \
    'set base_contract P2_COHORT16_COL2_12_2' 1
require_literal_count "$APPLY" \
    'hap_v5_floorplan::discover $base_contract' 1
require_literal_count "$APPLY" 'hap_v5_floorplan::discover' 1

# The board pre-place hook uses the same canonical, Attention-geometry, P5
# input-locality and P6 postprocess layers as the accepted P7 production
# placement and route contract.
for literal in \
    'set ::hap_v5_floorplan::expected_top attention_mlp_vcu118_v5_bd_wrapper' \
    'set base_contract P2_COHORT16_COL2_12_2' \
    'set p5_contract P5_INPUT_HALF_LOCAL_8_8' \
    'set p6_contract P6_POSTPROCESS_GROUP4_SPLIT_4_8_4' \
    'set p7_contract P7_ATTN_REGION2_ROWS_Y5_Y6_Y6_Y8' \
    'set region2_variant rowsplit_y5_y6_y6_y8' \
    'set plan [hap_v5_floorplan::discover $base_contract]' \
    'projection_core16x16_w8_reuse_ooc_floorplan.tcl' \
    'v5_production_p5_input_partition_floorplan.tcl' \
    'v5_production_p6_postprocess_partition_floorplan.tcl' \
    'set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]' \
    'set p5_plan [hap_v5_p5_input_partition::discover $plan]' \
    'set p6_plan [hap_v5_p6_postprocess_partition::discover $plan $p5_plan]' \
    'hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0' \
    'hap_v5_p5_input_partition::apply $p5_plan' \
    'hap_v5_p6_postprocess_partition::apply $p6_plan' \
    '[dict get $geometry_audit pblock_count] != 12' \
    'set base_audit [hap_v5_floorplan::audit_pblock_contract' \
    'set p5_audit [hap_v5_p5_input_partition::audit $p5_plan 0]' \
    'set p6_audit [hap_v5_p6_postprocess_partition::audit $p6_plan 0]' \
    '[dict get $base_audit pblock_count] != 11' \
    '[dict get $base_audit dsp_coverage] != 5453' \
    '[dict get $base_audit uram_coverage] != 752' \
    '[dict get $p5_audit pblock_count] != 2' \
    '[dict get $p6_audit pblock_count] != 2' \
    '[llength [get_pblocks -quiet]] != 27' \
    'V5_BOARD_FLOORPLAN_APPLIED' \
    'V5_BOARD_ATTENTION_GEOMETRY_PRE_PLACE_PASS' \
    'V5_BOARD_BASE_PBLOCK_PRE_PLACE_PASS' \
    'V5_BOARD_P5_INPUT_PLAN_PRE_PLACE_PASS' \
    'V5_BOARD_P5_INPUT_PBLOCK_PRE_PLACE_PASS' \
    'V5_BOARD_P6_POSTPROCESS_PLAN_PRE_PLACE_PASS' \
    'V5_BOARD_P6_POSTPROCESS_PBLOCK_PRE_PLACE_PASS'; do
    require_literal "$APPLY" "$literal"
done
reject_literal "$APPLY" 'pb_board_v5_'
for literal in \
    'pblock_contract_variant [dict get $plan contract_variant]' \
    'attention_board_variant [dict get $plan attention_board_variant]' \
    'attention_dsp48e2 [dict get $plan attention_dsp]' \
    'center_projection_dsp48e2 [dict get $plan center_projection_dsp]' \
    'center_nonprojection_dsp48e2 \' \
    'attention_island_dsp48e2 [dict get $plan attention_island_dsp]' \
    'attention_island_ramb36e2 [dict get $plan attention_island_ramb36]' \
    'attention_island_ramb18e2 [dict get $plan attention_island_ramb18]' \
    'attention_island_quantizer_overlap' \
    'attention_island_row_cache_overlap' \
    'planned_slr0_dsp48e2 $planned0' \
    'planned_slr1_dsp48e2 $planned1' \
    'planned_slr2_dsp48e2 $planned2' \
    'swiglu_frontend_count 1 row_leaf_count 2' \
    'unique_hadamard_count 1 fold2_count 0 quantizer_count 4 silu_count 2' \
    'outer0 outer0_primitives 1538 102' \
    'outer2 outer2_primitives 1538 102' \
    '[llength $covered_dsp] != 5453' \
    '$move0 + $center_lanes + $move2 != 128'; do
    require_literal "$SELECTOR_CHECK" "$literal"
done
for literal in \
    'contract_variant=P2_COHORT16_COL2_12_2' \
    'dsp48e2=5453' \
    'attention_board_variant=cohort16' \
    'attention_dsp48e2=2296' \
    'center_projection_dsp48e2=1632' \
    'center_nonprojection_dsp48e2=149' \
    'planned_slr0_dsp48e2=1862' \
    'planned_slr1_dsp48e2=1781' \
    'planned_slr2_dsp48e2=1810'; do
    require_literal "$SELECTOR_RUN" "$literal"
done

# place_design must be followed by live rediscovery before metrics; the old
# pre-place-plan wrong-SLR implementation is forbidden.
PLACE_TEXT="$(tr '\n' ' ' < "$PLACE")"
ORDERED_PLACE_TEXT="$PLACE_TEXT"
for literal in \
    'place_design -directive $place_directive' \
    'set post_plan [hap_v5_floorplan::discover $base_contract_variant]' \
    'set post_fine_plan [hap_v5_fine19::discover $post_plan 1]' \
    '[hap_v5_composite21::discover $post_plan $post_fine_plan 1]' \
    'set post_pblock_audit' \
    '[hap_v5_composite21::audit' \
    '[hap_v5_composite21::physical_metrics $post_pblock_audit]'; do
    case "$ORDERED_PLACE_TEXT" in
        *"$literal"*) ORDERED_PLACE_TEXT="${ORDERED_PLACE_TEXT#*"$literal"}" ;;
        *) fail 'post-place live rediscovery/audit order drifted' ;;
    esac
done
reject_literal "$PLACE" 'proc count_wrong_slr {cells target}'
reject_literal "$PLACE" '[dict get $plan branch0_primitives] 0]'
reject_literal "$PLACE" '[hap_v5_floorplan::physical_metrics $post_plan]'
require_literal "$PLACE" '[hap_v5_composite21::audit '

# Normalize Tcl line continuations solely for checking multi-line call sites.
ROUTE_TEXT="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' \
    "$ROUTE")"
REOPEN_TEXT="$(sed -zE 's/\\[[:space:]]+/ /g; s/[[:space:]]+/ /g' \
    "$REOPEN")"

# Route must audit both the opened checkpoint and a freshly rediscovered final
# netlist after all phys_opt/route commands.
for literal in \
	'$input_plan 1 P2_COHORT16_COL2_12_2 \' \
	'$input_geometry_plan p3_]]' \
	'set final_plan [hap_v5_floorplan::discover P2_COHORT16_COL2_12_2]' \
	'$final_plan 1 P2_COHORT16_COL2_12_2 \' \
	'$final_geometry_plan p3_]]' \
    'pblock_wrong_slr [dict get $final_pblock_audit placed_wrong]'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    '[hap_v5_floorplan::physical_metrics $input_plan $input_pblock_audit]' \
    '[hap_v5_floorplan::physical_metrics $final_plan $final_pblock_audit]'; do
    grep -Fq -- "$literal" <<<"$ROUTE_TEXT" || \
        fail "missing normalized ${ROUTE#"$ROOT/"}: $literal"
done
reject_literal "$ROUTE" 'proc hap_wrong_slr {cells target}'
reject_literal "$ROUTE" 'proc hap_require_pblock_contract {}'
reject_literal "$ROUTE" '[hap_v5_floorplan::physical_metrics $input_plan]'
reject_literal "$ROUTE" '[hap_v5_floorplan::physical_metrics $final_plan]'

# The place launcher freezes every nonempty output, including all reports and
# launcher evidence.  Route must consume the dynamic complete set, bind both
# manifest files by their own SHA, and require every route input path live.
for literal in \
    'set frozen_outputs [hap_verify_sha_manifest $place_output_sha -1' \
    'set frozen_route_inputs [hap_verify_sha_manifest $route_input_sha 13' \
    'hap_require_complete_place_output_manifest $frozen_outputs $place_output_sha' \
    'hap_require_exact_manifest_paths $frozen_route_inputs' \
    'place_output_manifest_entries [dict size $frozen_outputs]' \
    'route_input_manifest_entries 13' \
    'place_input_manifest_sha256 $expected_place_input_manifest_sha' \
    'place_output_manifest_sha256 $expected_place_output_manifest_sha' \
    'route_input_manifest_sha256 $expected_route_input_manifest_sha'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    'HAP_PLACE_INPUT_MANIFEST_SHA256' \
    'HAP_PLACE_OUTPUT_MANIFEST_SHA256' \
    "PLACE_LAUNCHER_STATUS=\"\$PLACE_DIR/launcher_status.txt\"" \
    "require_exact_line \"\$PLACE_LAUNCHER_STATUS\" \"\$literal\"" \
    'place_output_manifest_entries="$(wc -l < "$HAP_PLACE_OUTPUT_SHA")"' \
    '[place_output_manifest_entries]="$place_output_manifest_entries"' \
    'archive_route_outputs' \
    'route_input_sha_postcheck=1' \
    'vivado.log vivado.jou launcher_status.txt INPUT_FILES INPUT_SHA256SUMS'; do
    require_literal "$ROUTE_RUN" "$literal"
done
for literal in \
    'set place_launcher_status [file normalize [file join' \
    'hap_require_manifest_path $frozen_outputs $place_launcher_status' \
    'set place_launcher [hap_parse_summary $place_launcher_status' \
    'place_gate_exit_code 0' \
    'implementation_commands_requested 1'; do
    require_literal "$ROUTE" "$literal"
done
for old in 15 16; do
    reject_literal "$ROUTE" \
        "set frozen_outputs [hap_verify_sha_manifest \$place_output_sha $old]"
    reject_literal "$ROUTE" "place_output_manifest_entries $old"
    reject_literal "$ROUTE_RUN" \
        "V5 place output SHA manifest must have exactly $old rows"
done

# Pre-place and place both verify the expected DCP SHA and manifest-self SHA
# inside Vivado.  Place additionally rediscovers the two structural repairs,
# recognizes the canonical congestion table schema/data rows, and archives
# the complete nonempty output set instead of a manually maintained subset.
for literal in \
    'set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)' \
    'set expected_manifest_sha $::env(HAP_PREPLACE_INPUT_MANIFEST_SHA256)' \
    'set compact_input_frontend [hap_preplace_cells_of_module' \
    'set down_elastic2 [hap_preplace_cells_of_module' \
    'proc hap_preplace_mlp_local_clear_audit {branches}' \
    'proc hap_preplace_swiglu_local_clear_audit {}' \
    'proc hap_preplace_mlp_clear_boundary_audit {branches}' \
    'set mlp_local_branches [hap_preplace_cells_of_module' \
    'mlp_local_clear_protected_ff $mlp_local_clear_protected_ff' \
    'swiglu_local_clear_protected_ff [dict get $swiglu_clear protected]' \
    'swiglu_direct_clear_bypass_state [dict get $swiglu_clear bypass]' \
    'mlp_central_clear_direct_branch_state' \
    'report_drc -file [file join $out drc_pre_place.rpt]' \
    'set pre_place_drc_errors [llength [get_drc_violations -quiet -filter \' \
    '$pre_place_drc_errors == 0 ?' \
    'pre_place_drc_errors $pre_place_drc_errors' \
    'compact_input_frontend_instances [llength $compact_input_frontend]' \
    'down_elastic2_instances [llength $down_elastic2]'; do
    require_literal "$PRE_PLACE" "$literal"
done
for literal in \
    'set frozen [hap_verify_manifest $input_sha 5 $expected_manifest_sha]' \
    'set geometry_lib [file normalize $::env(HAP_PREPLACE_GEOMETRY_LIB)]' \
    'set_property CLOCK_BUFFER_TYPE NONE $compute_nets' \
    'hap_projection_ooc_floorplan::discover $projection_root 1' \
    'hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0' \
    'hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix' \
    'set total_pblock_count [llength [get_pblocks -quiet]]' \
    'canonical_pblock_count [dict get $audit pblock_count]' \
    'geometry_pblock_count [dict get $geometry_audit pblock_count]' \
    'pblock_count $total_pblock_count'; do
    require_literal "$PRE_PLACE" "$literal"
done
for literal in \
    'input_manifest_sha_match=$manifest_sha_match' \
    'audit_gate_exit_code=$audit_gate_rc' \
    'drc_pre_place.rpt' \
    'pre_place_drc_errors=0' \
    'mlp_local_clear_ff=2' \
    'mlp_local_clear_protected_ff=2' \
    'branch0_local_clear_ff=1' \
    'branch1_local_clear_ff=1' \
    'swiglu_local_clear_ff=8' \
    'swiglu_local_clear_protected_ff=8' \
    'swiglu_control_clear_ff=1' \
    'swiglu_hadamard_clear_ff=1' \
    'swiglu_quantizer_clear_ff=4' \
    'swiglu_row_clear_ff=2' \
    'swiglu_direct_clear_bypass_state=0' \
    'mlp_central_clear_ff=1' \
    'mlp_central_clear_branch_endpoints=2' \
    'mlp_central_clear_direct_branch_state=0' \
    'input_manifest_entries=5' \
    'compute_clock_buffer_none_ok=1' \
    'canonical_pblock_count=11' \
    'geometry_pblock_count=10' \
    'pblock_count=21' \
    'find "$HAP_PREPLACE_AUDIT_DIR" -maxdepth 1' \
    '-type f -size +0c ! -name OUTPUT_SHA256SUMS'; do
    require_literal "$PRE_PLACE_RUN" "$literal"
done
for literal in \
    'set input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]' \
    'proc hap_place_require_nonempty_file {path label}' \
    'hap_place_require_nonempty_file $normalized "frozen place input"' \
    'set flow_mode [expr {[info exists ::env(HAP_PLACE_MODE)] ?' \
    'if {$flow_mode ni {screen accept}}' \
    'if {$flow_mode eq "screen"}' \
    'V5_PRODUCTION_PLACE_SCREEN_PASS' \
    'acceptance_evidence 0 route_eligible 0 checkpoint_written 0' \
    'timing_run 0 cdc_run 0 exception_coverage_run 0' \
    'set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)' \
    'set expected_manifest_sha $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)' \
    'proc hap_place_mlp_local_clear_audit {require_placed}' \
    'set pre_mlp_local_clear [hap_place_mlp_local_clear_audit 0]' \
    'set post_mlp_local_clear [hap_place_mlp_local_clear_audit 1]' \
    '[dict get $post_mlp_local_clear branch0_slr] eq {1 0 0}' \
    '[dict get $post_mlp_local_clear branch1_slr] eq {0 0 1}' \
    'mlp_local_clear_wrong_slr [dict get $post_mlp_local_clear wrong]' \
    'mlp_central_clear_branch_endpoints' \
    'mlp_central_clear_direct_branch_state' \
    'set frozen_inputs [hap_place_verify_manifest $input_sha 9' \
    'set fine_lib [file normalize $::env(HAP_PLACE_FINE_LIB)]' \
    'set composite_lib [file normalize $::env(HAP_PLACE_COMPOSITE_LIB)]' \
    'set preplace_output_sha [file normalize ' \
    'set preplace_outputs [hap_place_verify_manifest $preplace_output_sha -1' \
    'composite21_pre_place_input_manifest_sha256 $expected_preplace_input_sha' \
    'Composite21 pre-place summary gate failed' \
    'Composite21 pre-place launcher gate failed' \
    'set compact_input_frontend [hap_place_cells_of_module' \
    'set down_elastic2 [hap_place_cells_of_module' \
    'set post_compact_input_frontend [hap_place_cells_of_module' \
    'set post_down_elastic2 [hap_place_cells_of_module' \
    'set post_fine_plan [hap_v5_fine19::discover $post_plan 1]' \
    'set post_composite_plan ' \
    '[hap_v5_composite21::discover $post_plan $post_fine_plan 1]' \
    'fine19_post_place_optimizer_extras_ok $fine19_optimizer_extras_ok' \
    'composite21_post_place_selector_deltas_ok' \
    'composite21_post_place_pblock_optimizer_extras_ok' \
    'set p9_central_island_wrong' \
    '[dict get $physical_metrics central_island_wrong]' \
    'set p9_center_dsp_remaining_wrong' \
    '[dict get $physical_metrics center_dsp_remaining_wrong]' \
    'set p9_mlp_remaining_wrong' \
    '[dict get $physical_metrics mlp_remaining_wrong]' \
    'p9_central_island_wrong_slr $p9_central_island_wrong' \
    'p9_center_dsp_remaining_wrong_slr $p9_center_dsp_remaining_wrong' \
    'p9_mlp_remaining_wrong_slr $p9_mlp_remaining_wrong' \
    'post_place_diagnostic_only.dcp' \
    'failure_stage post_place_live_rediscovery' \
    'acceptance_evidence 0 route_eligible 0 checkpoint_written 0' \
    'set congestion_schema_header_count 0' \
    'set congestion_data_row_count 0' \
    'set congestion_level5_count 0' \
    'set congestion_schema_ok [expr {$congestion_schema_header_count == 1 &&' \
    'error "V5 post-place congestion report schema/data rows are unrecognized"' \
    'set fast_gate_ok [expr {$resource_ok && $placement_ok && $fast_policy_ok &&' \
    'if {$flow_mode eq "accept"}' \
    'if {!$fast_gate_ok}' \
    'failure_stage post_place_fast_gate acceptance_evidence 0' \
    'acceptance_evidence $route_eligible route_eligible $route_eligible' \
    'fast_gate_ok $fast_gate_ok' \
    'level5_screen_ok $level5_screen_ok' \
    'congestion_schema_ok $congestion_schema_ok'; do
    require_literal "$PLACE" "$literal"
done
for literal in \
    'HAP_PLACE_MODE="${HAP_PLACE_MODE:-accept}"' \
    'expected_summary_status=V5_PRODUCTION_PLACE_SCREEN_PASS' \
    'flow_mode=screen' \
    'route_eligible=0' \
    '[[ ! -e "$HAP_PLACE_DIR/post_place.dcp" ]]' \
    'HAP_PLACE_INPUT_MANIFEST_SHA256' \
    'HAP_PLACE_COMPOSITE21_PREPLACE_OUTPUT_SHA256' \
    'HAP_PLACE_COMPOSITE21_PREPLACE_INPUT_SHA256' \
    'input_manifest_sha_match=$manifest_sha_match' \
    'composite21_pre_place_recheck_exit_code=$preplace_recheck_rc' \
    'place_gate_exit_code=$place_gate_rc' \
    'compact_input_frontend_instances=1' \
    'down_elastic2_instances=2' \
    'mlp_local_clear_ff=2' \
    'mlp_local_clear_protected_ff=2' \
    'branch0_local_clear_ff=1' \
    'branch1_local_clear_ff=1' \
    'branch0_local_clear_slr=1 0 0' \
    'branch1_local_clear_slr=0 0 1' \
    'mlp_local_clear_wrong_slr=0' \
    'mlp_central_clear_ff=1' \
    'mlp_central_clear_branch_endpoints=2' \
    'mlp_central_clear_direct_branch_state=0' \
    'congestion_schema_header_count=1' \
    'congestion_schema_ok=1' \
    'level5_screen_ok=1' \
    'fast_gate_ok=1' \
    'find "$HAP_PLACE_DIR" -maxdepth 1' \
    '-type f -size +0c ! -name OUTPUT_SHA256SUMS'; do
    require_literal "$PLACE_RUN" "$literal"
done
for literal in \
    'export HAP_PLACE_MODE=screen' \
    'exec "$SCRIPT_DIR/run_attention_mlp_production_v5_place.sh" "$@"'; do
    require_literal "$PLACE_SCREEN_RUN" "$literal"
done
for literal in \
    "'flow_mode=accept'" "'acceptance_evidence=1'" \
    "'route_eligible=1'"; do
    require_literal "$ROUTE_RUN" "$literal"
done
for literal in \
    'flow_mode accept' 'acceptance_evidence 1' 'route_eligible 1'; do
    require_literal "$ROUTE" "$literal"
done
require_literal "$ROUTE" 'fast_gate_ok 1'
require_literal "$ROUTE_RUN" '[fast_gate_ok]=1'
for literal in \
    'proc hap_route_mlp_local_clear_audit {require_placed}' \
    'proc hap_route_metadata_local_write_audit {require_placed}' \
    'proc hap_route_mlp_capture_leaf_audit {require_placed}' \
    'proc hap_route_require_boundary_contract {clear metadata capture label}' \
    'architecture_boundaries_input.txt' \
    'architecture_boundaries_post_route.txt' \
    'metadata_local_write_protected_ff [dict get $final_metadata protected]' \
    'mlp_capture_leaf_instances [dict get $final_capture instances]' \
    'mlp_capture_leaf_branch_slr_counts' \
    'architecture_boundary_ok $architecture_boundary_ok'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    'architecture_boundaries_input.txt architecture_boundaries_post_route.txt' \
    '[metadata_local_write_protected_ff]=970' \
    "[metadata_local_write_leaf_slr_counts]='{243 0 0} {0 0 243} {0 242 0} {0 242 0}'" \
    '[mlp_capture_leaf_instances]=1632' \
    '[mlp_capture_leaf_lut1]=1632' \
    "[mlp_capture_leaf_branch_slr_counts]='{816 0 0} {0 0 816}'" \
    '[architecture_boundary_ok]=1'; do
    require_literal "$ROUTE_RUN" "$literal"
done

# Acceptance must reject a losing placement before checkpoint/report work.  A
# passing candidate continues in the same in-memory placed design.
ORDERED_FAST_GATE_TEXT="$PLACE_TEXT"
for literal in \
    'report_design_analysis -congestion -file' \
    'set fast_gate_ok' \
    'if {!$fast_gate_ok}' \
    'write_checkpoint -force [file join $out post_place.dcp]'; do
    case "$ORDERED_FAST_GATE_TEXT" in
        *"$literal"*) ORDERED_FAST_GATE_TEXT="${ORDERED_FAST_GATE_TEXT#*"$literal"}" ;;
        *) fail 'post-place fast-gate/checkpoint order drifted' ;;
    esac
done

for literal in \
    'command_cpu()' 'effective_cores()' 'command_effective_cores()' \
    'peak_memory_mb()' 'synth_cores' 'route_cores' 'peak_mb'; do
    require_literal "$PHYSICAL_LEDGER" "$literal"
done

# The frozen Run 0138 audit is a read-only reopen.  It must rediscover all
# objects live and pass the matching pblock audit into physical_metrics.
for literal in \
	'set live_plan [hap_v5_floorplan::discover legacy10]' \
	'[hap_v5_floorplan::audit_pblock_contract $live_plan 1 legacy10]'; do
    require_literal "$REOPEN" "$literal"
done
literal='[hap_v5_floorplan::physical_metrics $live_plan $pblock_audit]'
grep -Fq -- "$literal" <<<"$REOPEN_TEXT" || \
    fail "missing normalized ${REOPEN#"$ROOT/"}: $literal"
reject_literal "$REOPEN" '[hap_v5_floorplan::physical_metrics $live_plan]'
REOPEN_CODE="$(sed -E '/^[[:space:]]*#/d' "$REOPEN")"
if grep -Eq \
        '(^|[^[:alnum:]_])(place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' \
        <<<"$REOPEN_CODE"; then
    fail 'read-only reopen audit contains an implementation/write command'
fi
for literal in \
    'production_v5_place_20260817_223533/post_place.dcp' \
    '63aa1417c862419edb102e85da15e28cfc1b52bec2136ad8ae72a1084a450b7a'; do
    require_literal "$REOPEN_RUN" "$literal"
done
for literal in \
    '[dict get $live_plan total_dsp] == 5469 &&' \
    '$slr_dsp eq {1791 1870 1808} &&' \
    '[dict get $pblock_audit dsp_coverage] == 5469 &&'; do
    require_literal "$REOPEN" "$literal"
done
for literal in \
    'set +e' 'vivado_rc=$?' \
    'checkpoint_written=0' 'implementation_commands_run=0' \
    'archive_outputs' 'OUTPUT_SHA256SUMS'; do
    require_literal "$REOPEN_RUN" "$literal"
done

# The repaired cohort16 projection weight-capture tree is a production identity,
# not merely an OOC diagnostic.  Discovery rejects it before placement and the
# synth/post-opt/route launchers require explicit summary evidence.
for literal in \
    'proc hap_v5_floorplan::audit_weight_capture_class {' \
    'proc hap_v5_floorplan::audit_projection_weight_capture {}' \
    'hap_projection_core16x16_w8_reuse' \
    'hap_v5_floorplan::require_count raw_weight_push_loads $raw_loads 37' \
    'weight_data weight_data_capture_enable 32 256' \
    'weight_meta weight_meta_capture_enable 2 256' \
    'weight_group weight_group_capture_enable 2 7' \
    'projection_weight_capture_ok [dict get $projection_weight_capture ok]'; do
    require_literal "$LIB" "$literal"
done
for file in "$SYNTH" "$POST_OPT"; do
    for literal in \
        'proc audit_weight_capture_class {' \
        'proc audit_projection_weight_capture {roots}' \
        'require_count raw_weight_push_loads $raw_loads 37' \
        'weight_data_capture_enable 32 256' \
        'weight_meta_capture_enable 2 256' \
        'weight_group_capture_enable 2 7' \
        'projection_weight_capture_ok [dict get $projection_weight_capture ok]'; do
        require_literal "$file" "$literal"
    done
done
for file in "$SYNTH_RUN" "$POST_OPT_RUN" "$PLACE_RUN" \
        "$SELECTOR_RUN" "$PRE_PLACE_RUN"; do
    for literal in \
        'raw_weight_push_loads=37' \
        'weight_data_capture_contract=32x256' \
        'weight_data_capture_nets=32' \
        'weight_data_capture_loads=256/256' \
        'weight_meta_capture_contract=2x256' \
        'weight_meta_capture_nets=2' \
        'weight_meta_capture_loads=256/256' \
        'weight_group_capture_contract=2x7' \
        'weight_group_capture_nets=2' \
        'weight_group_capture_loads=7/7' \
        'projection_weight_capture_ok=1'; do
        require_literal "$file" "$literal"
    done
done
for literal in \
    '[raw_weight_push_loads]=37' \
    '[weight_data_capture_contract]=32x256' \
    '[weight_data_capture_nets]=32' \
    '[weight_data_capture_loads]=256/256' \
    '[weight_meta_capture_contract]=2x256' \
    '[weight_meta_capture_nets]=2' \
    '[weight_meta_capture_loads]=256/256' \
    '[weight_group_capture_contract]=2x7' \
    '[weight_group_capture_nets]=2' \
    '[weight_group_capture_loads]=7/7' \
    '[projection_weight_capture_ok]=1'; do
    require_literal "$ROUTE_RUN" "$literal"
done
for file in "$PLACE" "$ROUTE" "$PRE_PLACE" "$SELECTOR_CHECK"; do
    require_literal "$file" 'projection_weight_capture_ok'
done

# A fresh post-opt DCP must prove the new Attention column-sharded identity as
# well as the compact MLP frontend and per-branch down elastic queues.  This
# prevents a resource-compatible checkpoint from the superseded array from
# entering placement through the independent read-only reopen path.
for literal in \
    '[cells_of_module hap_a8w8_array_16x16_s42_col3]' \
    '[cells_of_module hap_a8w8_array_16x16_s42]' \
    '[cells_of_module hap_a8w8_col_shard_left2_s42]' \
    '[cells_of_module hap_a8w8_col_shard_center12_s42]' \
    '[cells_of_module hap_a8w8_col_shard_right2_s42]' \
    '[cells_of_module hap_a8w8_col_shard_s42]' \
    '[cells_of_module hap_mlp_input_frontend16_compact_cache]' \
    '[cells_of_module hap_mlp_down_activation_cache16]' \
    '[cells_of_module hap_mlp_tile_accum_s36]' \
    '[cells_of_module hap_mlp_down_group_major_accum_s45]' \
    '[cells_of_module hap_mlp_down_branch_elastic2_s24]' \
    '&& [llength $attention_col3_array] == 1' \
    '&& [llength $attention_old_array] == 0' \
    '&& [llength $attention_left_shard] == 1' \
    '&& [llength $attention_center_shard] == 1' \
    '&& [llength $attention_right_shard] == 1' \
    '&& [llength $attention_center_subshards] == 4' \
    '&& [llength $attention_leaf_shards] == 6' \
    '&& [llength $compact_input_frontend] == 1' \
    '&& [llength $down_activation_cache] == 1' \
    '&& [llength $gate_accums] == 2' \
    '&& [llength $down_accums] == 2' \
    '&& [llength $down_elastic2] == 2' \
    'attention_col3_array_instances [llength $attention_col3_array]' \
    'attention_old_array_instances [llength $attention_old_array]' \
    'attention_left2_shard_instances [llength $attention_left_shard]' \
    'attention_center12_shard_instances [llength $attention_center_shard]' \
    'attention_right2_shard_instances [llength $attention_right_shard]' \
    'attention_center_subshard_instances [llength $attention_center_subshards]' \
    'attention_leaf_shard_instances [llength $attention_leaf_shards]' \
    'compact_input_frontend_instances [llength $compact_input_frontend]' \
    'compact_input_capture_contract 48x256' \
    'down_activation_capture_contract 16x280' \
    'gate_accum_write_controls $gate_write_controls' \
    'gate_accum_finalize_owners $gate_finalize_owners' \
    'down_guard_capture_contract 16x432' \
    'down_output_capture_contract 16x288' \
    'serial_reset_lut2_domains $serial_reset_domains' \
    'post_opt_data_bufg $data_bufg' \
    'protected_structure_ok $protected_structure_ok' \
    'post_opt_data_bufg_ok $post_opt_data_bufg_ok' \
    'down_elastic2_instances [llength $down_elastic2]'; do
    require_literal "$POST_OPT" "$literal"
done
for literal in \
    'attention_col3_array_instances=1' \
    'attention_old_array_instances=0' \
    'attention_left2_shard_instances=1' \
    'attention_center12_shard_instances=1' \
    'attention_right2_shard_instances=1' \
    'attention_center_subshard_instances=4' \
    'attention_leaf_shard_instances=6' \
    'compact_input_frontend_instances=1' \
    'compact_input_capture_contract=48x256' \
    'compact_input_capture_loads=256/256' \
    'down_activation_capture_contract=16x280' \
    'down_activation_capture_loads=280/280' \
    'gate_accum_write_controls=16' \
    'gate_accum_finalize_owners=16' \
    'down_guard_capture_contract=16x432' \
    'down_guard_capture_loads=432/432' \
    'down_output_capture_contract=16x288' \
    'down_output_capture_loads=288/288' \
    'serial_reset_lut2_domains=3' \
    'serial_reset_protected_domains=3' \
    'post_opt_data_bufg=0' \
    'protected_structure_ok=1' \
    'post_opt_data_bufg_ok=1' \
    'down_elastic2_instances=2'; do
    require_literal "$POST_OPT_RUN" "$literal"
done
for literal in \
    'recovered_post_opt_after_in_memory_structural_audit' \
    'mlp_local_clear_protected_ff count mismatch: expected=2 actual=1' \
    'mlp_central_clear_branch_endpoints count mismatch: expected=2 actual=9530' \
    "'synth_design completed successfully'" \
    "'opt_design completed successfully'" \
    "'^[A-Za-z0-9_]+ count mismatch: expected=[0-9]+ actual=[0-9]+$'" \
    "'^[[:space:]]*(ERROR|FATAL):'" \
    'recovery_failure_signature=$UPSTREAM_RECOVERY_FAILURE_SIGNATURE' \
    'upstream_recovery_failure_signature=$UPSTREAM_RECOVERY_FAILURE_SIGNATURE'; do
    require_literal "$POST_OPT_RUN" "$literal"
done
POST_OPT_CODE="$(sed -E '/^[[:space:]]*#/d' "$POST_OPT")"
if grep -Eq \
        '(^|[^[:alnum:]_])(synth_design|opt_design|power_opt_design|place_design|phys_opt_design|route_design|write_checkpoint)([^[:alnum:]_]|$)' \
        <<<"$POST_OPT_CODE"; then
    fail 'read-only post-opt reopen audit contains an implementation/write command'
fi

# The lightweight API proof may synthesize only its disposable top.  It must
# never open a checkpoint or run any implementation/checkpoint-write command.
for literal in \
    'synth_design -top hap_v5_device_probe_top' \
    'set slr_sites [get_sites -quiet -of_objects $slr]' \
    '[get_slrs -quiet -of_objects $slr_sites]' \
    'site_has_slr_index_property $site_has_slr_index_property' \
    'checkpoint_opened 0 implementation_commands_run 0' \
    'checkpoint_written 0 status $status'; do
    require_literal "$DEVICE_PROBE" "$literal"
done
DEVICE_PROBE_CODE="$(sed -E '/^[[:space:]]*#/d' "$DEVICE_PROBE")"
if grep -Eq \
        '(^|[^[:alnum:]_])(open_checkpoint|read_checkpoint|place_design|route_design|phys_opt_design|write_checkpoint)([^[:alnum:]_]|$)' \
        <<<"$DEVICE_PROBE_CODE"; then
    fail 'device-only SLR/site probe contains a forbidden command'
fi
for literal in \
    'V5_DEVICE_SLR_SITE_API_PROBE_PASS' \
    'site_has_slr_index_property=0' \
    'checkpoint_opened=0' 'implementation_commands_run=0' \
    'checkpoint_written=0'; do
    require_literal "$DEVICE_PROBE_RUN" "$literal"
done

# The correction must not weaken the independent policy gates that rejected
# the previous place: 33 data BUFG, CDC Critical and Level-6 remain failures.
for literal in \
    '$false_path_rows == 0 && $datapath_only_rows == 0 && $data_bufg == 0 &&' \
    '$timing_coverage_ok && $cdc_critical == 0' \
    '$no_level6 && $level5_screen_ok ? "V5_PRODUCTION_PLACE_PASS" : "FAIL"'; do
    require_literal "$PLACE" "$literal"
done
for literal in \
    '$cdc_critical == 0 &&' \
    '$data_bufg == 0 && $false_path_rows == 0 &&' \
    '$congestion_level6 == 0' \
    '$wns >= 0.0 && $whs >= 0.0'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    'set canonical_header_count 0' \
    'Direction[[:space:]]*\|[[:space:]]*Type[[:space:]]*\|[[:space:]]*Level' \
    'Congestion report canonical Direction/Type/Level/Window schema is missing' \
    'set congestion_rows 0' \
    'Congestion report has neither Global/Long rows nor a clean marker'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    '[pblock_contract_variant]=P2_COHORT16_COL2_12_2' \
    '[post_place_pblock_count]=21' \
    '[post_place_canonical_pblock_count]=11' \
    '[post_place_geometry_pblock_count]=10' \
    '[dsp48e2]=5453' \
    '[post_place_pblock_dsp_coverage]=5453' \
    '[post_place_pblock_uram_coverage]=752' \
    '[post_place_pblock_wrong_slr]=0' \
    '[attention_island_dsp48e2]=52' \
    '[attention_island_ramb36e2]=88' \
    '[attention_island_ramb18e2]=2' \
    '[attention_island_uram288]=0' \
    '[attention_island_quantizer_overlap]=0' \
    '[attention_island_row_cache_overlap]=0' \
    '[attention_island_pblock_dsp48e2]=52' \
    '[attention_island_pblock_ramb36e2]=88' \
    '[attention_island_pblock_ramb18e2]=2' \
    '[attention_island_pblock_uram288]=0' \
    '[attention_island_wrong_slr]=0' \
    '[row_leaf0_dsp48e2]=2' \
    '[row_leaf1_dsp48e2]=2' \
    '[row_leaf0_ramb36e2]=6' \
    '[row_leaf1_ramb36e2]=6' \
    '[outer0_dsp48e2]=1538' \
    '[outer2_dsp48e2]=1538' \
    '[outer0_ramb36e2]=102' \
    '[outer2_ramb36e2]=102' \
    '[moved_lanes_slr0]=16' \
    '[center_lanes_slr1]=96' \
    '[moved_lanes_slr2]=16' \
    '[planned_slr0_dsp48e2]=1862' \
    '[planned_slr1_dsp48e2]=1781' \
    '[planned_slr2_dsp48e2]=1810' \
    '[slr0_dsp48e2]=1862' \
    '[slr1_dsp48e2]=1781' \
    '[slr2_dsp48e2]=1810' \
    '[pblock_dsp_coverage]=5453'; do
    require_literal "$ROUTE_RUN" "$literal"
done
for literal in \
    'pblock_contract_variant=P9_COHORT16_MLP_CENTRAL_X2X4_21' \
    'post_place_pblock_count=21' \
    'post_place_pblock_overlap=0' \
    'projection_exact_cover=1' \
    'region1_exact_cover=1' \
    'owner_exact_cover=1' \
    'weight_owner_residency_ok=1' \
    'composite21_pre_place_verified=1' \
    'composite21_pre_place_central_partition_ok=1' \
    'composite21_post_place_central_anchor_range=CLOCKREGION_X2Y5:CLOCKREGION_X4Y9' \
    'composite21_post_place_central_island_dsp=80' \
    'composite21_post_place_center_dsp_remaining=5' \
    'composite21_post_place_central_partition_ok=1' \
    'composite21_post_place_selector_deltas_ok=1' \
    'composite21_post_place_pblock_optimizer_extras_ok=1' \
    'composite21_additional_wrong_slr=0' \
    'p9_central_island_wrong_slr=0' \
    'p9_center_dsp_remaining_wrong_slr=0' \
    'p9_mlp_remaining_wrong_slr=0' \
    'attention_direct_unconstrained=1' \
    'attention_direct_unresolved_primitives=0' \
    'attention_direct_placement_ok=1' \
    'dsp48e2=5453' \
    'post_place_pblock_dsp_coverage=5453' \
    'attention_island_dsp48e2=52' \
    'attention_island_ramb36e2=88' \
    'attention_island_ramb18e2=2' \
    'attention_island_uram288=0' \
    'attention_island_quantizer_overlap=0' \
    'attention_island_row_cache_overlap=0' \
    'attention_island_wrong_slr=0' \
    'outer0_dsp48e2=1538' \
    'outer2_dsp48e2=1538' \
    'outer0_ramb36e2=102' \
    'outer2_ramb36e2=102' \
    'moved_lanes_slr0=16' \
    'center_lanes_slr1=96' \
    'moved_lanes_slr2=16' \
    'planned_slr0_dsp48e2=1862' \
    'planned_slr1_dsp48e2=1781' \
    'planned_slr2_dsp48e2=1810'; do
    require_literal "$PLACE_RUN" "$literal"
done
for literal in \
    'pblock_contract_variant=legacy10' \
    'pblock_count=10' \
    'pblock_dsp_coverage=5469' \
    'dsp48e2=5469' \
    'slr0_dsp48e2=1791' \
    'slr1_dsp48e2=1870' \
    'slr2_dsp48e2=1808'; do
    require_literal "$REOPEN_RUN" "$literal"
done

# Fresh production must never regress to the superseded Run0138/early-P0
# resource equations.  Those literals remain legal only in the two frozen,
# read-only legacy audit files checked immediately above.
for file in "$LIB" "$SELECTOR_CHECK" "$PLACE" "$ROUTE" "$APPLY" \
        "$PLACE_RUN" "$ROUTE_RUN"; do
    for old in 5469 1843 1818 1808 1791 1870; do
        reject_literal "$file" "$old"
    done
done
# P0 remains a selector-library compatibility API, but no fresh production
# consumer may authorize or report the superseded 12/101/15 distribution.
for file in "$SELECTOR_CHECK" "$PLACE" "$ROUTE" "$APPLY" \
        "$PLACE_RUN" "$ROUTE_RUN"; do
    for old in \
        'P0_11' 'move0=12' 'center_lanes=101' 'move2=15' \
        'moved_lanes_slr0=12' 'center_lanes_slr1=101' \
        'moved_lanes_slr2=15' 'planned_slr0_dsp=1794' \
        'planned_slr1_dsp=1878' 'planned_slr0_dsp48e2=1794' \
        'planned_slr1_dsp48e2=1878'; do
        reject_literal "$file" "$old"
    done
done
for file in "$PLACE" "$ROUTE"; do
    reject_literal "$file" \
        '[hap_v5_floorplan::audit_pblock_contract $post_plan 1]'
    reject_literal "$file" \
        '[hap_v5_floorplan::audit_pblock_contract $input_plan 1]'
    reject_literal "$file" \
        '[hap_v5_floorplan::audit_pblock_contract $final_plan 1]'
done
reject_literal "$REOPEN" \
    '[hap_v5_floorplan::audit_pblock_contract $live_plan 1]'
reject_literal "$ROUTE_RUN" \
    'accepts only the frozen place artifact'
require_literal "$ROUTE_RUN" \
    'rejects the frozen legacy10 Run0138 artifact'

for literal in \
    'remote_array_control_startpoints' \
    'center_wrapper_control_registers' \
    'local_shard_control_registers' \
    'implementation_commands 0' \
    'checkpoints_written 0'; do
    require_literal "$ATTENTION_LOCAL_DIAG" "$literal"
done
for literal in \
    'sha256sum -c "$SOURCE_MANIFEST"' \
    "grep -qx 'remote_array_control_startpoints=0'" \
    "grep -qx 'implementation_commands=0'" \
    "grep -qx 'checkpoints_written=0'"; do
    require_literal "$ATTENTION_LOCAL_DIAG_RUN" "$literal"
done
for literal in \
    'ingress_capture_leaf_instances' \
    'ingress_capture_leaf_lut1' \
    'all_fanout -quiet -flat -endpoints_only' \
    'ingress_capture_leaf_total_ce_loads' \
    'ingress_capture_leaf_load32_count' \
    'ingress_capture_leaf_load36_count' \
    'ingress_capture_leaf_load42_count' \
    'ingress_capture_leaf_non_ce_endpoints' \
    'ingress_capture_leaf_load_ok' \
    'dut_dsp48e2 $dut_dsp' \
    'forbidden_timing_exception_count'; do
    require_literal "$MLP_OWNER_SYNTH" "$literal"
done
for literal in \
    "grep -qx 'ingress_capture_leaf_instances=816'" \
    "grep -qx 'ingress_capture_leaf_lut1=816'" \
    "grep -qx 'ingress_capture_leaf_min_ce_load=32'" \
    "grep -qx 'ingress_capture_leaf_max_ce_load=42'" \
    "grep -qx 'ingress_capture_leaf_total_ce_loads=28128'" \
    "grep -qx 'ingress_capture_leaf_load32_count=384'" \
    "grep -qx 'ingress_capture_leaf_load36_count=384'" \
    "grep -qx 'ingress_capture_leaf_load42_count=48'" \
    "grep -qx 'ingress_capture_leaf_non_ce_endpoints=0'" \
    "grep -qx 'ingress_capture_leaf_load_ok=1'" \
    "grep -qx 'dut_dsp48e2=1536'"; do
    require_literal "$MLP_OWNER_SYNTH_RUN" "$literal"
done
require_literal "$MLP_OWNER_XDC" \
    'create_clock -name clk -period 10.000 [get_ports clk]'
require_literal "$MLP_OWNER_SYNTH" \
    'stage OWNER_CAPTURE_REGISTERED_OOC_POST_SYNTH clock_mhz 100 jobs $jobs'
require_literal "$MLP_OWNER_SYNTH_RUN" \
    'a8w4_slice8x12_group_registered_ooc_100mhz.xdc'

# The 1536-DSP MLP half-array must independently place and route in one hard
# VCU118 SLR at 100 MHz before the two halves are admitted to production.
for literal in \
    'set top hap_a8w4_slice8x12_group_registered_ooc_harness' \
    'proc placed_slr_audit {cells label expected_slr}' \
    'regexp {([0-2])$} $slr -> slr_index' \
    'require_count existing_pblocks [get_pblocks -quiet] 0' \
    'create_pblock pb_mlp_owner_capture_slr0' \
    'resize_pblock [get_pblocks pb_mlp_owner_capture_slr0] -add [list SLR0]' \
    'set_property IS_SOFT false [get_pblocks pb_mlp_owner_capture_slr0]' \
    'set post_place_drc [llength [get_drc_violations -quiet -filter {' \
    'set post_place_primitive_audit [placed_slr_audit \' \
    'set wrong_slr [dict get $post_place_primitive_audit placed_other]' \
    'write_checkpoint -force [file join $out post_place_diagnostic_only.dcp]' \
    'write_checkpoint -force [file join $out post_place.dcp]' \
    'phys_opt_design -directive $pre_route_physopt_directive' \
    'route_design -directive $route_directive' \
    'phys_opt_design -directive $post_route_physopt_directive' \
    'set route_errors [route_row $route_text "# of nets with routing errors" 1]' \
    'set accepted_clock_explicit_gaps [expr {' \
    'set unaccepted_explicit_gaps \' \
    'unaccepted_explicit_route_gaps $unaccepted_explicit_gaps' \
    'set timing_coverage_ok [expr {' \
    'set no_timing_exceptions [expr {' \
    'set final_primitive_audit [placed_slr_audit \' \
    'set final_wrong_slr [dict get $final_primitive_audit placed_other]' \
    'final_dsp_slr0 $final_dsp0 final_dsp_other_slr $final_dsp_other' \
    'if {$status ne "PASS"} {error "MLP owner-capture OOC route gate failed"}'; do
    require_literal "$MLP_OWNER_ROUTE" "$literal"
done
reject_literal "$MLP_OWNER_ROUTE" \
    'filter $pblock_cells {SLR_INDEX != 0}'
reject_literal "$MLP_OWNER_ROUTE" \
    'filter $final_primitives {SLR_INDEX != 0}'
reject_literal "$MLP_OWNER_ROUTE" 'get_property IS_PLACED'
MLP_OWNER_ROUTE_TEXT="$(tr '\n' ' ' < "$MLP_OWNER_ROUTE")"
for literal in \
    'place_design -directive $place_directive' \
    'write_checkpoint -force [file join $out post_place_diagnostic_only.dcp]' \
    'report_drc -file [file join $out drc_post_place.rpt]' \
    'set post_place_drc' \
    'if {!$fast_gate}' \
    'write_checkpoint -force [file join $out post_place.dcp]' \
    'route_design -directive $route_directive' \
    'phys_opt_design -directive $post_route_physopt_directive' \
    'report_drc -file [file join $out drc_post_route.rpt]' \
    'set drc_errors'; do
    case "$MLP_OWNER_ROUTE_TEXT" in
        *"$literal"*) MLP_OWNER_ROUTE_TEXT="${MLP_OWNER_ROUTE_TEXT#*"$literal"}" ;;
        *) fail 'MLP owner-capture OOC physical-gate order drifted' ;;
    esac
done
for literal in \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'require_free_batch_slot' \
    'HAP_INPUT_MANIFEST_SHA256' \
    'HAP_PRE_ROUTE_PHYSOPT_DIRECTIVE' \
    'HAP_POST_ROUTE_PHYSOPT_DIRECTIVE' \
    'RUN_CONTRACT="$HAP_REPORT_DIR/RUN_CONTRACT"' \
    'input_sha_postcheck.txt' \
    'input_manifest_post_match' \
    'post_place_diagnostic_only.dcp' \
    'post_route_before_physopt.dcp' \
    'final_wrong_slr_primitives=0' \
    'final_dsp_slr0=1536' \
    'unaccepted_explicit_route_gaps=0' \
    'timing_coverage_ok=1' \
    'OUTPUT_SHA256SUMS'; do
    require_literal "$MLP_OWNER_ROUTE_RUN" "$literal"
done

# P10 retires the rejected P9 Composite21 launch path. It consumes one fresh
# P2 pre-place proof and performs one 100 MHz acceptance place with 11
# canonical ownership pblocks plus the proven 10-pblock Attention geometry.
for literal in \
    'set contract_variant P2_COHORT16_COL2_12_2' \
    'set frozen_inputs [hap_p10_verify_manifest $input_sha 8 $expected_manifest_sha]' \
    'set geometry_lib [file normalize $::env(HAP_PLACE_GEOMETRY_LIB)]' \
    'set_property CLOCK_BUFFER_TYPE NONE $compute_nets' \
    'set post_compute_clock_buffer_none_count 0' \
    'hap_projection_ooc_floorplan::discover $projection_root 1' \
    'hap_projection_ooc_floorplan::apply $geometry_plan $geometry_prefix 0' \
    'hap_projection_ooc_floorplan::specs $geometry_plan $geometry_prefix' \
    'set pre_total_pblock_count [llength [get_pblocks -quiet]]' \
    'set post_total_pblock_count [llength [get_pblocks -quiet]]' \
    'set post_geometry_audit [hap_projection_ooc_floorplan::audit_pblocks \' \
    'set post_geometry_placement \' \
    'post_place_pblock_count $post_total_pblock_count' \
    'metadata_local_write_protected_ff 970' \
    'mlp_capture_leaf_instances 1632' \
    'mlp_capture_leaf_lut1 1632' \
    'branch0_capture_leaf_instances 816' \
    'branch1_capture_leaf_instances 816' \
    'set post_capture [hap_p10_mlp_capture_leaf_audit \' \
    '{{816 0 0} {0 0 816}}' \
    'foreach spec [hap_v5_floorplan::pblock_specs $plan $contract_variant]' \
    'place_design -directive $place_directive' \
    'set post_audit [hap_v5_floorplan::audit_pblock_contract \' \
    'set post_metadata [hap_p10_metadata_local_write_audit 1]' \
    '{{243 0 0} {0 0 243} {0 242 0} {0 242 0}}' \
    'set fast_gate_ok [expr {' \
    'post_place_diagnostic_only.dcp' \
    'report_drc -file [file join $out drc_post_place.rpt]' \
    'set policy_ok [expr {' \
    'write_checkpoint -force [file join $out post_place.dcp]' \
    'core_clock_mhz 100 ddr0_clock_mhz 300 ddr1_clock_mhz 300' \
    'status $status'; do
    require_literal "$P10_PLACE" "$literal"
done
for forbidden in P9_ COMPOSITE21 core_clock_mhz\ 150; do
    reject_literal "$P10_PLACE" "$forbidden"
done
P10_PLACE_TEXT="$(tr '\n' ' ' < "$P10_PLACE")"
for literal in \
    'place_design -directive $place_directive' \
    'report_design_analysis -congestion -file $congestion_path' \
    'set fast_gate_ok' \
    'if {!$fast_gate_ok}' \
    'report_drc -file [file join $out drc_post_place.rpt]' \
    'set post_drc_errors' \
    'set status' \
    'write_checkpoint -force [file join $out post_place.dcp]'; do
    case "$P10_PLACE_TEXT" in
        *"$literal"*) P10_PLACE_TEXT="${P10_PLACE_TEXT#*"$literal"}" ;;
        *) fail 'P10 production place fast-gate/report/checkpoint order drifted' ;;
    esac
done
for literal in \
    '[[ $# -eq 2 ]]' \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'require_free_batch_slot' \
    'HAP_P10_PREPLACE_OUTPUT_SHA' \
    'metadata_local_write_protected_ff=970' \
    'mlp_capture_leaf_instances=1632' \
    'mlp_capture_leaf_lut1=1632' \
    "mlp_capture_leaf_branch_slr_counts='{816 0 0} {0 0 816}'" \
    'INPUT_SHA256SUMS' \
    'input_sha_postcheck.txt' \
    'preplace_output_sha_postcheck.txt' \
    'input_manifest_entries=8' \
    'compute_clock_buffer_none_ok=1' \
    'geometry_pblock_prefix=p3_' \
    'canonical_pblock_count=11' \
    'geometry_pblock_count=10' \
    'post_place_pblock_count=21' \
    'post_place_fast_gate.txt' \
    'final_exit_code=$final_rc' \
    'OUTPUT_SHA256SUMS' \
    'P10_PRODUCTION_PLACE_PASS'; do
    require_literal "$P10_PLACE_RUN" "$literal"
done
for literal in \
    'hap_verify_sha_manifest $place_input_sha 8' \
    'place_input_manifest_entries 8' \
    'proc hap_require_p3_attention_geometry {' \
    'proc hap_route_compute_clock_buffer_none {}' \
    'hap_projection_ooc_floorplan::audit_pblocks \' \
    'pblock_count [llength [get_pblocks -quiet]]'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    'set clear_endpoints {}' \
    'lsearch -exact $endpoint_cells $cell' \
    'set central_nets [lsort -dictionary -unique ' \
    'get_pins -quiet -leaf -of_objects $central_nets' \
    'set direct_branch_state {}' \
    'central_branch_endpoints [llength $clear_endpoints]' \
    'central_direct_branch_state [llength $direct_branch_state]'; do
    require_literal "$ROUTE" "$literal"
done
reject_literal "$ROUTE" 'central_branch_endpoints 2 \'
reject_literal "$ROUTE" 'central_direct_branch_state 0]'
for literal in \
    'must have exactly 8 rows' \
    '[input_manifest_entries]=8' \
    '[place_input_manifest_entries]=8' \
    '[post_place_pblock_count]=21' \
    '[pblock_count]=21'; do
    require_literal "$ROUTE_RUN" "$literal"
done
reject_literal "$ROUTE" 'hap_verify_sha_manifest $place_input_sha 6'
reject_literal "$ROUTE_RUN" 'must have exactly 6 rows'

# P4 is a physical-only 4/8/4 redistribution. Its one-process placement must
# finish exact pre-place DRC before place_design, reapply the compute-net BUFG
# policy after placement, and retain the frozen arithmetic/resource identity.
for literal in \
    'contract_variant P4_COHORT16_PHYSICAL4_8_4_19' \
    'expected_dsp_distribution {2198 1173 2082}' \
    'expected_uram_distribution {224 224 304}' \
    'set center_extra {}' \
    'if {[get_property REF_NAME $cell] eq "DSP48E2"}' \
    'require_count full_specs $specs 19'; do
    require_literal "$P4_LIB" "$literal"
done
for literal in \
    'proc hap_projection_ooc_floorplan::placed_ref_counts {cells ref_name}' \
    'set dsp [placed_ref_counts [dict get $plan dut_primitives] DSP48E2]'; do
    require_literal "$OOC_FLOORPLAN" "$literal"
done
reject_literal "$P4_PRE_PLACE" \
    'report_utilization -pblocks [get_pblocks -quiet]'
P4_PRE_PLACE_TEXT="$(tr '\n' ' ' < "$P4_PRE_PLACE")"
for literal in \
    'report_drc -file [file join $out drc_pre_place.rpt]' \
    'set drc_errors' \
    'report_utilization -file [file join $out utilization_pre_place.rpt]'; do
    case "$P4_PRE_PLACE_TEXT" in
        *"$literal"*) P4_PRE_PLACE_TEXT="${P4_PRE_PLACE_TEXT#*"$literal"}" ;;
        *) fail 'P4 standalone pre-place DRC/report order drifted' ;;
    esac
done
P4_PLACE_TEXT="$(tr '\n' ' ' < "$P4_PLACE")"
for literal in \
    'report_drc -file [file join $out drc_pre_place.rpt]' \
    'set pre_drc_errors' \
    'report_utilization -file [file join $out utilization_pre_place.rpt]' \
    'if {!$pre_place_ok}' \
    'place_design -directive $place_directive' \
    'set compute_clock_buffer_none_missing_before_reapply 0' \
    'set_property CLOCK_BUFFER_TYPE NONE $post_compute_nets' \
    'set compute_clock_buffer_none_missing_after_reapply 0' \
    'report_design_analysis -congestion -file $congestion_path' \
    'report_drc -file [file join $out drc_post_place.rpt]' \
    'set fast_gate_ok' \
    'if {!$fast_gate_ok}' \
    'write_checkpoint -force [file join $out post_place.dcp]'; do
    case "$P4_PLACE_TEXT" in
        *"$literal"*) P4_PLACE_TEXT="${P4_PLACE_TEXT#*"$literal"}" ;;
        *) fail 'P4 integrated placement gate order drifted' ;;
    esac
done
for literal in \
    'physical_contract P4_COHORT16_PHYSICAL4_8_4_19' \
    'set frozen [hap_p10_verify_manifest $input_sha 10' \
    'core_clock_mhz 100' \
    '[dict get $post_base_plan kernel_dsp] == 3072' \
    '$slr_dsp eq {2198 1173 2082}' \
    '$slr_uram eq {224 224 304}' \
    '$pre_drc_errors == 0 && $post_drc_errors == 0' \
    '$data_bufg == 0 && $level6 == 0 && $level5 <= $max_level5' \
    'V5_P10_P4_PRODUCTION_PLACE_PASS'; do
    require_literal "$P4_PLACE" "$literal"
done
for literal in \
    '[[ $# -eq 1 ]]' \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'require_free_batch_slot' \
    'HAP_JOBS="${HAP_JOBS:-32}"' \
    'AltSpreadLogic_high' \
    'INPUT_SHA256SUMS' \
    'input_sha_postcheck.txt' \
    'input_manifest_entries=10' \
    'physical_contract_variant=P4_COHORT16_PHYSICAL4_8_4_19' \
    'slr0_dsp48e2=2198' 'slr1_dsp48e2=1173' 'slr2_dsp48e2=2082' \
    'compute_clock_buffer_none_missing_after_reapply=0' \
    'congestion_level6_or_higher_windows=0' \
    'P4_PRODUCTION_PLACE_PASS' 'OUTPUT_SHA256SUMS'; do
    require_literal "$P4_PLACE_RUN" "$literal"
done

# P4 routing must consume only a fully accepted manifested P4 placement,
# preserve the 4/8/4 physical identity, and write an accepted checkpoint only
# after route, timing, DRC, congestion and architecture gates all pass.
for literal in \
    '[info exists ::env(HAP_ROUTE_SOURCE_PROCS_ONLY)]' \
    'if {$hap_route_source_procs_only} {return}'; do
    require_literal "$ROUTE" "$literal"
done
for literal in \
    'set ::env(HAP_ROUTE_SOURCE_PROCS_ONLY) 1' \
    'source $helper_lib' \
    'unset ::env(HAP_ROUTE_SOURCE_PROCS_ONLY)' \
    'physical_contract P4_COHORT16_PHYSICAL4_8_4_19' \
    'set frozen_place_inputs [hap_verify_sha_manifest $place_input_sha 10' \
    'set frozen_route_inputs [hap_verify_sha_manifest $route_input_sha 20' \
    'hap_require_complete_place_output_manifest' \
    'status V5_P10_P4_PRODUCTION_PLACE_PASS' \
    'route_eligible 1 checkpoint_written 1' \
    'phys_opt_design -directive $pre_physopt_directive' \
    'route_design -directive $route_directive' \
    'phys_opt_design -hold_fix' \
    'post_route_diagnostic.dcp' \
    'set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]' \
    'congestion_level6 == 0' \
    'V5_P10_P4_PRODUCTION_OOC_POST_ROUTE_PASS' \
    'if {$route_eligible}' \
    'post_route.dcp' \
    'bitstream_generated 0'; do
    require_literal "$P4_ROUTE" "$literal"
done
for literal in \
    '[[ $# -eq 1 ]]' \
    "'[u]nwrapped/lnx64.o/vivado .*[-]mode batch'" \
    'require_free_batch_slot' \
    'HAP_JOBS="${HAP_JOBS:-32}"' \
    'sha256sum -c --strict "$HAP_PLACE_INPUT_SHA"' \
    'sha256sum -c --strict "$HAP_PLACE_OUTPUT_SHA"' \
    'route_eligible=1' \
    'physical_contract_variant=P4_COHORT16_PHYSICAL4_8_4_19' \
    'route_input_manifest_entries=20' \
    'dsp48e2=5453' 'uram288=752' 'mlp_kernel_dsp48e2=3072' \
    'wns_ns=|^whs_ns=' \
    'timing_ok=1' 'route_clean=1' 'drc_errors=0' \
    'congestion_level6_or_higher_windows=0' \
    'checkpoint_written=1' 'bitstream_generated=0' \
    'OUTPUT_SHA256SUMS'; do
    require_literal "$P4_ROUTE_RUN" "$literal"
done

# Mission 0056 is a physical contract, not merely an RTL attribute.  The
# production synth, independent post-opt reopen and pre-place gate must each
# reject anything other than one protected local-clear FF per MLP branch.
for file in "$SYNTH" "$POST_OPT"; do
    for literal in \
        'proc audit_mlp_local_clear {branches}' \
        'proc audit_swiglu_local_clear {frontends row_leaves}' \
        'proc audit_mlp_central_clear_boundary {branches}' \
        'all_fanout -flat -endpoints_only' \
        'clear_local_r_reg*' \
        'MLP local clear FF lost DONT_TOUCH' \
        'if {$protected_count != 2}' \
        'mlp_local_clear_protected_ff count mismatch: expected=2 actual=$protected_count' \
        'mlp_local_clear_ff $mlp_local_clear_ff' \
        'mlp_local_clear_protected_ff $mlp_local_clear_protected_ff' \
        'branch0_local_clear_ff $branch0_local_clear_ff' \
        'branch1_local_clear_ff $branch1_local_clear_ff' \
        'swiglu_local_clear_ff $swiglu_local_clear_ff' \
        'swiglu_local_clear_protected_ff $swiglu_local_clear_protected_ff' \
        'swiglu_direct_clear_bypass_state $swiglu_direct_clear_bypass_state' \
        'mlp_central_clear_branch_endpoints' \
        'mlp_central_clear_direct_branch_state'; do
        require_literal "$file" "$literal"
    done
done
for file in "$SYNTH_RUN" "$POST_OPT_RUN" "$PRE_PLACE_RUN"; do
    for literal in \
        'mlp_local_clear_ff=2' \
        'mlp_local_clear_protected_ff=2' \
        'branch0_local_clear_ff=1' \
        'branch1_local_clear_ff=1' \
        'swiglu_local_clear_ff=8' \
        'swiglu_local_clear_protected_ff=8' \
        'swiglu_control_clear_ff=1' \
        'swiglu_hadamard_clear_ff=1' \
        'swiglu_quantizer_clear_ff=4' \
        'swiglu_row_clear_ff=2' \
        'swiglu_direct_clear_bypass_state=0' \
        'mlp_central_clear_ff=1' \
        'mlp_central_clear_branch_endpoints=2' \
        'mlp_central_clear_direct_branch_state=0'; do
        require_literal "$file" "$literal"
    done
done

# Mission 0057 moves metadata write selection and payload capture below each
# physical URAM leaf. Require all four local boundaries and their OOC proof.
for literal in \
    'parameter integer BANK_ID = 0' \
    'reg wr_en_local_r;' \
    'reg [ADDR_W-1:0] wr_addr_local_r;' \
    'reg [223:0] wr_data_local_r;' \
    'wr_en_local_r <= wr_valid && (wr_bank == BANK_ID[0]);' \
    'mem[wr_addr_local_r] <= wr_data_local_r;'; do
    require_literal "$META_RTL" "$literal"
done
for literal in \
    'local_wr_en_ff' \
    'local_wr_addr_ff' \
    'local_wr_data_ff' \
    'protected_local_write_ff' \
    'local_write_boundary_ok'; do
    require_literal "$META_OOC" "$literal"
done
for literal in \
    "grep -qx 'uram288=672'" \
    "grep -qx 'local_wr_en_ff=4'" \
    "grep -qx 'local_wr_addr_ff=70'" \
    "grep -qx 'local_wr_data_ff=896'" \
    "grep -qx 'protected_local_write_ff=970'" \
    "grep -qx 'local_write_boundary_ok=1'"; do
    require_literal "$META_OOC_RUN" "$literal"
done
for literal in \
    'proc hap_preplace_metadata_local_write_audit {}' \
    'metadata_leaf_instances metadata_local_wr_en_ff' \
    'metadata_local_wr_addr_ff metadata_local_wr_data_ff' \
    'metadata_local_write_protected_ff'; do
    require_literal "$PRE_PLACE" "$literal"
done
for literal in \
    'metadata_leaf_instances=4' \
    'metadata_local_wr_en_ff=4' \
    'metadata_local_wr_addr_ff=70' \
    'metadata_local_wr_data_ff=896' \
    'metadata_local_write_protected_ff=970'; do
    require_literal "$PRE_PLACE_RUN" "$literal"
done

# Capture leaves are a retained physical contract across synthesis, post-opt,
# pre-place, placement and route.  Each MLP branch owns 816 protected LUT1
# leaves in its target SLR; no stage may infer this from DSP counts alone.
for file in "$SYNTH" "$POST_OPT" "$PRE_PLACE"; do
    for literal in \
        'hap_a8w4_ingress_capture_leaf' \
        'mlp_capture_leaf_instances' \
        'mlp_capture_leaf_lut1' \
        'branch0_capture_leaf_instances' \
        'branch1_capture_leaf_instances' \
        'branch0_capture_leaf_lut1' \
        'branch1_capture_leaf_lut1'; do
        require_literal "$file" "$literal"
    done
done
for file in "$SYNTH_RUN" "$POST_OPT_RUN" "$PRE_PLACE_RUN"; do
    for literal in \
        'mlp_capture_leaf_instances=1632' \
        'mlp_capture_leaf_lut1=1632' \
        'branch0_capture_leaf_instances=816' \
        'branch1_capture_leaf_instances=816' \
        'branch0_capture_leaf_lut1=816' \
        'branch1_capture_leaf_lut1=816'; do
        require_literal "$file" "$literal"
    done
done

"$ROOT/vivado/scripts/check_mlp_swiglu_product_frontend16_q4_registered_ooc_static.sh"

printf 'V5_PHYSICAL_GATE_STATIC_PASS\n'
