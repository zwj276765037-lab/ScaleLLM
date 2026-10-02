# Strict 100 MHz P4 production placement. The exact P4 pre-place audit and
# place_design run in one Vivado process so the authenticated DCP is opened
# only once.

set p4_place_script [file normalize [info script]]
set in_dcp [file normalize $::env(HAP_DCP)]
set out [file normalize $::env(HAP_PLACE_DIR)]
set input_sha [file normalize $::env(HAP_PLACE_INPUT_SHA)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set expected_manifest_sha $::env(HAP_PLACE_INPUT_MANIFEST_SHA256)
set selector_lib [file normalize $::env(HAP_PLACE_SELECTOR_LIB)]
set geometry_lib [file normalize $::env(HAP_PLACE_GEOMETRY_LIB)]
set pblock_lib [file normalize $::env(HAP_PLACE_PBLOCK_LIB)]
set physical_lib [file normalize $::env(HAP_PLACE_PHYSICAL_LIB)]
set p10_proc_lib [file normalize $::env(HAP_PLACE_P10_PROC_LIB)]
set expected_launcher [file normalize $::env(HAP_PLACE_LAUNCHER)]
set io_audit [file normalize $::env(HAP_PLACE_IO_AUDIT)]
set clock_xdc [file normalize $::env(HAP_PLACE_CLOCK_XDC)]
set place_directive [expr {[info exists ::env(HAP_PLACE_DIRECTIVE)] ?
    $::env(HAP_PLACE_DIRECTIVE) : "AltSpreadLogic_high"}]
set jobs [expr {[info exists ::env(HAP_JOBS)] ? $::env(HAP_JOBS) : 32}]
set max_level5 [expr {
    [info exists ::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS)] ?
    $::env(HAP_MAX_POST_PLACE_LEVEL5_WINDOWS) : 1}]
set base_contract P2_COHORT16_COL2_12_2
set physical_contract P4_COHORT16_PHYSICAL4_8_4_19
file mkdir $out

# Reuse only the generic fail-closed audit/report helpers. Historical P2 main
# flow and pblocks are never executed by this P4 script.
set ::env(HAP_P10_SOURCE_PROCS_ONLY) 1
source $p10_proc_lib
unset ::env(HAP_P10_SOURCE_PROCS_ONLY)

proc hap_p4_write_kv {path values} {
    set fp [open $path w]
    foreach {key value} $values {puts $fp "$key=$value"}
    close $fp
}

if {![string match "2025.2*" [version -short]]} {
    error "P4 placement requires Vivado 2025.2"
}
if {[llength [get_designs -quiet]] != 0} {
    error "P4 placement requires a fresh Vivado process"
}
if {![string is integer -strict $jobs] || $jobs != 32} {
    error "P4 production placement requires HAP_JOBS=32"
}
if {![string is integer -strict $max_level5] || $max_level5 < 0 ||
    $max_level5 > 100} {
    error "P4 max Level-5 window count must be in 0..100"
}
foreach digest [list $expected_dcp_sha $expected_manifest_sha] {
    if {![regexp {^[0-9a-f]{64}$} $digest]} {
        error "P4 received malformed SHA256"
    }
}
set_param general.maxThreads $jobs

set frozen [hap_p10_verify_manifest $input_sha 10 $expected_manifest_sha]
foreach required [list $in_dcp $selector_lib $geometry_lib $pblock_lib \
        $physical_lib $p10_proc_lib $p4_place_script $expected_launcher \
        $clock_xdc $io_audit] {
    if {![dict exists $frozen $required]} {
        error "P4 required input absent from manifest: $required"
    }
}
set actual_dcp_sha [hap_p10_sha256 $in_dcp]
if {$actual_dcp_sha ne $expected_dcp_sha} {
    error "P4 DCP identity mismatch"
}

set xdc_text [hap_p10_read_nonempty $clock_xdc "P4 clock XDC"]
set xdc_code ""
foreach line [split $xdc_text "\n"] {
    if {![regexp {^[[:space:]]*#} $line]} {append xdc_code $line "\n"}
}
set forbidden_false_path [join {set false path} _]
set forbidden_datapath "-[join {datapath only} _]"
if {[regexp -nocase -- [format {%s|%s} $forbidden_false_path \
        $forbidden_datapath] $xdc_code]} {
    error "P4 XDC contains a forbidden timing waiver"
}
if {[llength [regexp -all -inline {create_clock[[:space:]]} $xdc_code]] != 3 ||
    [llength [regexp -all -inline {set_input_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_output_delay[[:space:]]} $xdc_code]] != 6 ||
    [llength [regexp -all -inline {set_clock_groups[[:space:]]+-asynchronous} \
        $xdc_code]] != 1} {
    error "P4 XDC command cardinality mismatch"
}

source $selector_lib
source $geometry_lib
source $pblock_lib
source $physical_lib
open_checkpoint $in_dcp
read_xdc $clock_xdc
source $io_audit
foreach {name period} {core_clk 10.000 ddr0_clk 3.333 ddr1_clk 3.333} {
    set clocks [get_clocks -quiet $name]
    if {[llength $clocks] != 1 ||
        abs([get_property PERIOD $clocks] - $period) > 0.001} {
        error "P4 clock contract mismatch: $name"
    }
}

set compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $compute_nets] == 0} {error "P4 compute-net selector is empty"}
set_property CLOCK_BUFFER_TYPE NONE $compute_nets
foreach net $compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        error "P4 pre-place compute net lost CLOCK_BUFFER_TYPE NONE: $net"
    }
}

set base_plan [hap_v5_floorplan::discover $base_contract]
set projection_root [file dirname \
    [get_property NAME [dict get $base_plan projection_array]]]
set geometry_plan [hap_projection_ooc_floorplan::discover $projection_root 1]
set physical_plan [hap_v5_physical448::discover $base_plan $geometry_plan]
set compact_input [hap_p10_cells_of_module hap_mlp_input_frontend16_compact_cache]
set down_elastic [hap_p10_cells_of_module hap_mlp_down_branch_elastic2_s24_v6]
set pre_clear [hap_p10_mlp_local_clear_audit 0]
set pre_metadata [hap_p10_metadata_local_write_audit 0]
set pre_capture [hap_p10_mlp_capture_leaf_audit \
    [hap_p10_cells_of_module hap_mlp_shared_local_slice8x12_s44_s46] 0]

hap_v5_physical448::apply $physical_plan
set pre_audit [hap_v5_physical448::audit $physical_plan 0]
set pre_pblock_count [llength [get_pblocks -quiet]]
hap_v5_floorplan::write_discovery $base_plan \
    [file join $out selectors_pre_place.txt] V5_P10_P4_BASE_SELECTORS_PASS
hap_projection_ooc_floorplan::write_plan $geometry_plan \
    [file join $out attention_geometry_pre_place.txt] V5_P10_P4_GEOMETRY_PASS
hap_v5_physical448::write_plan $physical_plan \
    [file join $out physical448_pre_place.txt] V5_P10_P4_PHYSICAL_PLAN_PASS
hap_v5_fine19::write_audit $pre_audit \
    [file join $out pblocks_pre_place.txt] V5_P10_P4_PBLOCK_PRE_PLACE_PASS

# DRC is mandatory. The utilization report is diagnostic and follows it.
report_drc -file [file join $out drc_pre_place.rpt]
set pre_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]
report_utilization -file [file join $out utilization_pre_place.rpt]
set pre_place_ok [expr {
    [dict get $base_plan total_dsp] == 5453 &&
    [dict get $base_plan total_uram] == 752 &&
    [dict get $base_plan kernel_dsp] == 3072 &&
    [dict get $base_plan history2_count] == 2 &&
    [dict get $base_plan generic_repack_count] == 0 &&
    [dict get $base_plan projection_weight_capture_ok] == 1 &&
    [dict get $physical_plan contract_variant] eq $physical_contract &&
    [dict get $physical_plan projected_slr_dsp] eq {2198 1173 2082} &&
    [dict get $physical_plan projected_slr_uram] eq {224 224 304} &&
    [dict get $pre_audit ok] &&
    [dict get $pre_audit pblock_count] == 19 &&
    [dict get $pre_audit optimizer_extra_count] == 0 &&
    [dict get $pre_audit dsp_coverage] == 5453 &&
    [dict get $pre_audit uram_coverage] == 752 &&
    $pre_pblock_count == 19 && $pre_drc_errors == 0 &&
    [llength $compact_input] == 1 && [llength $down_elastic] == 2 &&
    [dict get $pre_clear total] == 2 &&
    [dict get $pre_clear protected] == 2 &&
    [dict get $pre_metadata protected] == 970 &&
    [dict get $pre_capture instances] == 1632 &&
    [dict get $pre_capture lut1] == 1632}]
hap_p4_write_kv [file join $out pre_place_gate.txt] [list \
    status [expr {$pre_place_ok ? "V5_P10_P4_PRE_PLACE_PASS" : "FAIL"}] \
    input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_p10_sha256 $input_sha] \
    input_manifest_entries 10 base_contract_variant $base_contract \
    physical_contract_variant $physical_contract pblock_count $pre_pblock_count \
    pblock_member_count [dict get $pre_audit member_count] \
    pblock_overlap [dict get $pre_audit member_overlap] \
    pblock_optimizer_extras [dict get $pre_audit optimizer_extra_count] \
    pblock_dsp_coverage [dict get $pre_audit dsp_coverage] \
    pblock_uram_coverage [dict get $pre_audit uram_coverage] \
    projected_slr_dsp48e2 [dict get $physical_plan projected_slr_dsp] \
    projected_slr_uram288 [dict get $physical_plan projected_slr_uram] \
    pre_place_drc_errors $pre_drc_errors implementation_commands_run 0 \
    checkpoint_written 0 route_eligible 0]
if {!$pre_place_ok} {error "P4 strict in-process pre-place gate failed"}

place_design -directive $place_directive

# Placement can create live alias nets which do not inherit the original net
# property. Reapply it to the complete live compute namespace before BUFG and
# route-eligibility audits.
set post_compute_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_compute/*}]
if {[llength $post_compute_nets] == 0} {
    error "P4 post-place compute-net selector is empty"
}
set compute_clock_buffer_none_missing_before_reapply 0
foreach net $post_compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        incr compute_clock_buffer_none_missing_before_reapply
    }
}
set_property CLOCK_BUFFER_TYPE NONE $post_compute_nets
set compute_clock_buffer_none_missing_after_reapply 0
foreach net $post_compute_nets {
    if {[get_property CLOCK_BUFFER_TYPE $net] ne "NONE"} {
        incr compute_clock_buffer_none_missing_after_reapply
    }
}
if {$compute_clock_buffer_none_missing_after_reapply != 0} {
    error "P4 post-place CLOCK_BUFFER_TYPE NONE reapply failed"
}

set rediscovery_rc [catch {
    set post_base_plan [hap_v5_floorplan::discover $base_contract]
    set post_projection_root [file dirname \
        [get_property NAME [dict get $post_base_plan projection_array]]]
    set post_geometry_plan \
        [hap_projection_ooc_floorplan::discover $post_projection_root 1]
    set post_physical_plan \
        [hap_v5_physical448::discover $post_base_plan $post_geometry_plan]
    set post_audit [hap_v5_physical448::audit $post_physical_plan 1]
    set physical [hap_v5_physical448::physical_metrics \
        $post_physical_plan $post_audit]
    set post_pblock_count [llength [get_pblocks -quiet]]
    set post_compact_input \
        [hap_p10_cells_of_module hap_mlp_input_frontend16_compact_cache]
    set post_down_elastic \
        [hap_p10_cells_of_module hap_mlp_down_branch_elastic2_s24_v6]
    set post_clear [hap_p10_mlp_local_clear_audit 1]
    set post_metadata [hap_p10_metadata_local_write_audit 1]
    set post_capture [hap_p10_mlp_capture_leaf_audit \
        [hap_p10_cells_of_module hap_mlp_shared_local_slice8x12_s44_s46] 1]
    hap_v5_floorplan::write_discovery $post_base_plan \
        [file join $out selectors_post_place.txt] \
        V5_P10_P4_POST_PLACE_SELECTORS_PASS
    hap_projection_ooc_floorplan::write_plan $post_geometry_plan \
        [file join $out attention_geometry_post_place.txt] \
        V5_P10_P4_GEOMETRY_POST_PLACE_PASS
    hap_v5_physical448::write_plan $post_physical_plan \
        [file join $out physical448_post_place.txt] \
        V5_P10_P4_PHYSICAL_POST_PLACE_PASS
    hap_v5_fine19::write_audit $post_audit \
        [file join $out pblocks_post_place.txt] \
        V5_P10_P4_PBLOCK_POST_PLACE_PASS
} rediscovery_error]
if {$rediscovery_rc != 0} {
    set diagnostic_written [expr {![catch {
        write_checkpoint -force \
            [file join $out post_place_diagnostic_only.dcp]}]}]
    set clean_error [string map [list "\r" " " "\n" " "] $rediscovery_error]
    hap_p4_write_kv [file join $out summary.txt] [list \
        tool [version -short] stage V5_P10_P4_POST_PLACE_REDISCOVERY \
        flow_mode accept failure_stage post_place_live_rediscovery \
        acceptance_evidence 0 route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_written \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p10_sha256 $input_sha] \
        input_manifest_entries 10 provenance_verified 1 \
        pre_place_verified 1 post_rediscovery_error $clean_error status FAIL]
    close_design
    error "P4 post-place rediscovery failed: $rediscovery_error"
}

set congestion_path [file join $out congestion_post_place.rpt]
report_design_analysis -congestion -file $congestion_path
set congestion [hap_p10_congestion_counts \
    [hap_p10_read_nonempty $congestion_path "P4 congestion report"]]
set level5 [dict get $congestion level5]
set level6 [dict get $congestion level6]
report_drc -file [file join $out drc_post_place.rpt]
set post_drc_errors [llength [get_drc_violations -quiet -filter {
    SEVERITY == Error}]]

set clock_bufg 0
set data_bufg 0
foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
    set outputs [get_pins -quiet -of_objects $cell -filter {DIRECTION == OUT}]
    if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
        incr clock_bufg
    } else {
        incr data_bufg
    }
}
set slr_dsp [dict get $physical slr_dsp]
set slr_uram [dict get $physical slr_uram]
set resource_ok [expr {
    [dict get $post_base_plan total_dsp] == 5453 &&
    [dict get $post_base_plan total_uram] == 752 &&
    [dict get $post_base_plan kernel_dsp] == 3072 &&
    [dict get $post_base_plan history2_count] == 2 &&
    [dict get $post_base_plan generic_repack_count] == 0 &&
    [dict get $post_base_plan projection_weight_capture_ok] == 1}]
set structure_ok [expr {
    [llength $post_compact_input] == 1 &&
    [llength $post_down_elastic] == 2 &&
    [dict get $post_clear total] == 2 &&
    [dict get $post_clear protected] == 2 &&
    [dict get $post_clear branch0_slr] eq {1 0 0} &&
    [dict get $post_clear branch1_slr] eq {0 0 1} &&
    [dict get $post_clear wrong] == 0 &&
    [dict get $post_metadata leaves] == 4 &&
    [dict get $post_metadata wr_en] == 4 &&
    [dict get $post_metadata wr_addr] == 70 &&
    [dict get $post_metadata wr_data] == 896 &&
    [dict get $post_metadata protected] == 970 &&
    [dict get $post_metadata leaf_counts] eq {243 243 242 242} &&
    [dict get $post_metadata leaf_slr_counts] eq \
        {{243 0 0} {0 0 243} {0 242 0} {0 242 0}} &&
    [dict get $post_metadata wrong] == 0 &&
    [dict get $post_capture instances] == 1632 &&
    [dict get $post_capture lut1] == 1632 &&
    [dict get $post_capture branch_instances] eq {816 816} &&
    [dict get $post_capture branch_lut1] eq {816 816} &&
    [dict get $post_capture branch_slr_counts] eq \
        {{816 0 0} {0 0 816}} &&
    [dict get $post_capture wrong] == 0 &&
    $compute_clock_buffer_none_missing_after_reapply == 0}]
set placement_ok [expr {
    [hap_v5_physical448::physical_ok $physical] &&
    [dict get $pre_audit ok] && [dict get $post_audit ok] &&
    [dict get $post_audit pblock_count] == 19 &&
    $pre_pblock_count == 19 && $post_pblock_count == 19 &&
    [dict get $post_audit placed_wrong] == 0 &&
    [dict get $physical wrong_total] == 0 &&
    [dict get $physical unplaced] == 0 &&
    $slr_dsp eq {2198 1173 2082} &&
    $slr_uram eq {224 224 304} &&
    [hap_projection_ooc_floorplan::region0_input_localization_ok \
        $post_geometry_plan] &&
    [hap_projection_ooc_floorplan::region3_input_localization_ok \
        $post_geometry_plan] &&
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok \
        $post_geometry_plan]}]
set optimizer_extras_ok [expr {
    [dict get $post_audit optimizer_extra_count] >= 0 &&
    [dict get $post_audit optimizer_extra_count] <= 4096}]
set fast_gate_ok [expr {$resource_ok && $structure_ok && $placement_ok &&
    $optimizer_extras_ok && $pre_drc_errors == 0 && $post_drc_errors == 0 &&
    $data_bufg == 0 && $level6 == 0 && $level5 <= $max_level5}]
hap_p4_write_kv [file join $out post_place_fast_gate.txt] [list \
    resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
    pre_place_drc_errors $pre_drc_errors post_place_drc_errors $post_drc_errors \
    compute_clock_buffer_none_missing_before_reapply \
        $compute_clock_buffer_none_missing_before_reapply \
    compute_clock_buffer_none_missing_after_reapply \
        $compute_clock_buffer_none_missing_after_reapply \
    data_bufg $data_bufg level5_or_higher_windows $level5 \
    level6_or_higher_windows $level6 max_level5_windows $max_level5 \
    fast_gate_ok $fast_gate_ok]
if {!$fast_gate_ok} {
    set diagnostic_written [expr {![catch {
        write_checkpoint -force \
            [file join $out post_place_diagnostic_only.dcp]}]}]
    hap_p4_write_kv [file join $out summary.txt] [list \
        tool [version -short] part [dict get $post_base_plan part] \
        top [dict get $post_base_plan top] \
        stage V5_P10_P4_POST_PLACE_FAST_GATE flow_mode accept \
        failure_stage post_place_fast_gate acceptance_evidence 0 \
        route_eligible 0 checkpoint_written 0 \
        diagnostic_checkpoint_written $diagnostic_written \
        input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 [hap_p10_sha256 $input_sha] \
        input_manifest_entries 10 provenance_verified 1 \
        pre_place_verified 1 physical_contract_variant $physical_contract \
        place_directive $place_directive jobs $jobs core_clock_mhz 100 \
        ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
        dsp48e2 [dict get $post_base_plan total_dsp] \
        uram288 [dict get $post_base_plan total_uram] \
        slr_dsp48e2 $slr_dsp slr_uram288 $slr_uram \
        unplaced_primitives [dict get $physical unplaced] \
        wrong_slr_primitives [dict get $physical wrong_total] \
        pre_place_drc_errors $pre_drc_errors \
        post_place_drc_errors $post_drc_errors data_bufg $data_bufg \
        congestion_level5_or_higher_windows $level5 \
        congestion_level6_or_higher_windows $level6 \
        resource_ok $resource_ok structure_ok $structure_ok \
        placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
        fast_gate_ok 0 status FAIL]
    close_design
    error "P4 placement rejected by post-place fast gate"
}

report_utilization -file [file join $out utilization_post_place.rpt]
report_utilization -hierarchical -hierarchical_depth 12 -file \
    [file join $out utilization_hier_post_place.rpt]
report_utilization -slr -file [file join $out utilization_slr_post_place.rpt]
set timing_text [report_timing_summary -delay_type min_max -max_paths 100 \
    -report_unconstrained -warn_on_violation -return_string]
set fp [open [file join $out timing_post_place.rpt] w]
puts $fp $timing_text
close $fp
report_cdc -details -file [file join $out cdc_post_place.rpt]
report_clock_interaction -delay_type min_max -file \
    [file join $out clock_interaction_post_place.rpt]
report_clock_utilization -file [file join $out clock_utilization_post_place.rpt]
set exceptions_path [file join $out exceptions_coverage_post_place.rpt]
report_exceptions -coverage -file $exceptions_path

set no_clock [hap_p10_check_timing_count $timing_text no_clock]
set unconstrained [hap_p10_check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set no_input_delay [hap_p10_check_timing_count $timing_text no_input_delay]
set no_output_delay [hap_p10_check_timing_count $timing_text no_output_delay]
set partial_input_delay [hap_p10_check_timing_count $timing_text partial_input_delay]
set partial_output_delay [hap_p10_check_timing_count $timing_text partial_output_delay]
set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
    $no_input_delay == 3 && $no_output_delay == 0 &&
    $partial_input_delay == 0 && $partial_output_delay == 0}]
set cdc_text [hap_p10_read_nonempty [file join $out cdc_post_place.rpt] \
    "P4 CDC report"]
if {![regexp -line \
        {^[[:space:]]*ID[[:space:]]+Severity[[:space:]]+Count[[:space:]]+Description[[:space:]]*$} \
        $cdc_text]} {
    error "P4 CDC report summary header is missing"
}
set cdc_critical 0
foreach {whole count} [regexp -all -inline -line -nocase \
        {^[^\n]*[[:space:]]Critical[[:space:]]+([1-9][0-9]*)[[:space:]]+[^\n]*$} \
        $cdc_text] {
    incr cdc_critical $count
}
set exception_text [hap_p10_read_nonempty $exceptions_path \
    "P4 exception report"]
set false_path_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+False Path[[:space:]]} $exception_text]
set datapath_only_rows [regexp -all -line \
    {^[[:space:]]*[0-9]+[[:space:]]+(Max|Min) Delay.*Datapath} $exception_text]
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {
    error "P4 timing query returned no path"
}
set wns [get_property SLACK [lindex $setup_path 0]]
set whs [get_property SLACK [lindex $hold_path 0]]
set policy_ok [expr {$post_drc_errors == 0 && $false_path_rows == 0 &&
    $datapath_only_rows == 0 && $data_bufg == 0 && $timing_coverage_ok &&
    $cdc_critical == 0}]
set status [expr {$fast_gate_ok && $policy_ok ?
    "V5_P10_P4_PRODUCTION_PLACE_PASS" : "FAIL"}]
set route_eligible [expr {$status eq "V5_P10_P4_PRODUCTION_PLACE_PASS"}]
if {$route_eligible} {
    write_checkpoint -force [file join $out post_place.dcp]
}

hap_p4_write_kv [file join $out summary.txt] [list \
    tool [version -short] part [dict get $post_base_plan part] \
    top [dict get $post_base_plan top] stage V5_P10_P4_POST_PLACE_ACCEPT \
    flow_mode accept acceptance_evidence $route_eligible \
    route_eligible $route_eligible checkpoint_written $route_eligible \
    input_dcp $in_dcp input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 [hap_p10_sha256 $input_sha] \
    input_manifest_entries 10 provenance_verified 1 pre_place_verified 1 \
    base_contract_variant $base_contract \
    physical_contract_variant $physical_contract \
    place_directive $place_directive jobs $jobs core_clock_mhz 100 \
    ddr0_clock_mhz 300 ddr1_clock_mhz 300 \
    dsp48e2 [dict get $post_base_plan total_dsp] \
    uram288 [dict get $post_base_plan total_uram] \
    mlp_kernel_dsp48e2 [dict get $post_base_plan kernel_dsp] \
    history2_repack_instances [dict get $post_base_plan history2_count] \
    generic_repack_instances [dict get $post_base_plan generic_repack_count] \
    projection_weight_capture_ok \
        [dict get $post_base_plan projection_weight_capture_ok] \
    pblock_count $post_pblock_count \
    pblock_dsp_coverage [dict get $post_audit dsp_coverage] \
    pblock_uram_coverage [dict get $post_audit uram_coverage] \
    pblock_overlap [dict get $post_audit member_overlap] \
    pblock_optimizer_extras [dict get $post_audit optimizer_extra_count] \
    slr0_dsp48e2 [lindex $slr_dsp 0] slr1_dsp48e2 [lindex $slr_dsp 1] \
    slr2_dsp48e2 [lindex $slr_dsp 2] \
    slr0_uram288 [lindex $slr_uram 0] slr1_uram288 [lindex $slr_uram 1] \
    slr2_uram288 [lindex $slr_uram 2] \
    unplaced_primitives [dict get $physical unplaced] \
    wrong_slr_primitives [dict get $physical wrong_total] \
    metadata_local_write_protected_ff [dict get $post_metadata protected] \
    mlp_capture_leaf_instances [dict get $post_capture instances] \
    mlp_capture_leaf_lut1 [dict get $post_capture lut1] \
    compute_clock_buffer_none_nets [llength $post_compute_nets] \
    compute_clock_buffer_none_missing_before_reapply \
        $compute_clock_buffer_none_missing_before_reapply \
    compute_clock_buffer_none_missing_after_reapply \
        $compute_clock_buffer_none_missing_after_reapply \
    pre_place_drc_errors $pre_drc_errors post_place_drc_errors $post_drc_errors \
    false_path_exception_rows $false_path_rows \
    datapath_only_exception_rows $datapath_only_rows \
    timing_coverage_ok $timing_coverage_ok cdc_critical $cdc_critical \
    clock_bufg $clock_bufg data_bufg $data_bufg \
    congestion_level5_or_higher_windows $level5 \
    congestion_level6_or_higher_windows $level6 \
    post_place_wns_ns $wns post_place_whs_ns $whs \
    resource_ok $resource_ok structure_ok $structure_ok \
    placement_ok $placement_ok optimizer_extras_ok $optimizer_extras_ok \
    fast_gate_ok $fast_gate_ok policy_ok $policy_ok \
    level5_screen_ok [expr {$level5 <= $max_level5}] \
    level6_congestion_ok [expr {$level6 == 0}] status $status]
close_design
if {!$route_eligible} {error "P4 production post-place policy gate failed"}
