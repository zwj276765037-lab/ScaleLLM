set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set top hap_a8w8_array_16x16_s42_registered_ooc_harness
set manifest [file join $root vivado manifests \
    attention_a8w8_col3_leaf_sources.list]
set constraint [file join $root vivado constraints \
    attention_a8w8_col3_registered_leaf_ooc_150mhz.xdc]
file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

set fp [open $constraint r]
set xdc_text [read $fp]
close $fp
set forbidden_constraint_count [regexp -all -nocase \
    {set_false_path|set_clock_groups|set_max_delay|set_min_delay|-datapath_only} \
    $xdc_text]
if {$forbidden_constraint_count != 0} {
    error "registered Attention leaf XDC contains a timing exception"
}

proc count_data_bufg {} {
    set data_count 0
    set clock_count 0
    foreach cell [get_cells -quiet -hierarchical -filter {REF_NAME =~ BUFG*}] {
        set outputs [get_pins -quiet -of_objects $cell -filter \
            {DIRECTION == OUT}]
        if {[llength [get_clocks -quiet -of_objects $outputs]] != 0} {
            incr clock_count
        } else {
            incr data_count
        }
    }
    return [list $data_count $clock_count]
}

proc get_slack {delay_type} {
    set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
    if {[llength $paths] == 0} { return -999.0 }
    return [get_property SLACK [lindex $paths 0]]
}

proc check_timing_count {text check_name} {
    set pattern [format \
        {checking[[:space:]]+%s[[:space:]]+\(([0-9]+)\)} $check_name]
    if {![regexp -nocase -- $pattern $text -> count]} {
        error "check_timing category '$check_name' is missing"
    }
    return $count
}

proc run_variant {root report_dir build_dir part manifest constraint top \
        label use_col3 forbidden_constraint_count} {
    set out [file join $report_dir $label]
    set build [file join $build_dir $label]
    file mkdir $out
    file mkdir $build
    create_project attention_${label}_registered_leaf $build -part $part -force
    set_property target_language Verilog [current_project]
    set handle [open $manifest r]
    foreach raw_line [split [read $handle] "\n"] {
        set line [string trim $raw_line]
        if {$line eq "" || [string index $line 0] eq "#"} { continue }
        set path [file normalize [file join $root $line]]
        if {![file exists $path]} { error "Missing source: $path" }
        add_files -fileset sources_1 $path
        set_property file_type SystemVerilog [get_files $path]
    }
    close $handle
    add_files -fileset constrs_1 -norecurse $constraint
    set_property top $top [current_fileset]
    set_property generic USE_COL3=$use_col3 [current_fileset]
    update_compile_order -fileset sources_1
    synth_design -top $top -part $part -mode out_of_context \
        -flatten_hierarchy none -directive PerformanceOptimized \
        -generic USE_COL3=$use_col3

    set src [get_cells -quiet -hierarchical -filter {
        NAME =~ src_r_reg* && REF_NAME =~ FD*}]
    set sink [get_cells -quiet -hierarchical -filter {
        NAME =~ sink_r_reg* && REF_NAME =~ FD*}]
    if {[llength $src] != 13766 || [llength $sink] != 6275} {
        error "registered proxy FF mismatch src=[llength $src] sink=[llength $sink]"
    }
    set dut_prefix [expr {$use_col3 ? "g_col3.u_dut" :
        "g_reference.u_dut"}]
    if {[llength [get_cells -quiet $dut_prefix]] != 1} {
        error "$label DUT instance missing"
    }
    write_checkpoint -force [file join $out post_synth.dcp]
    report_utilization -file [file join $out utilization_post_synth.rpt]
    report_utilization -hierarchical -hierarchical_depth 18 \
        -file [file join $out utilization_hier_post_synth.rpt]
    set timing_text [report_timing_summary -delay_type min_max \
        -max_paths 100 -report_unconstrained -warn_on_violation \
        -return_string]
    set timing_fp [open [file join $out timing_post_synth.rpt] w]
    puts $timing_fp $timing_text
    close $timing_fp
    report_clock_utilization -file \
        [file join $out clock_utilization_post_synth.rpt]
    report_exceptions -coverage -file \
        [file join $out exceptions_coverage_post_synth.rpt]
    set efp [open [file join $out exceptions_coverage_post_synth.rpt] r]
    set exceptions_text [read $efp]
    close $efp
    set no_timing_exceptions [expr {
        [string first "No timing exceptions found." $exceptions_text] >= 0}]
    set no_clock [check_timing_count $timing_text no_clock]
    set unconstrained [check_timing_count $timing_text \
        unconstrained_internal_endpoints]
    set no_input_delay [check_timing_count $timing_text no_input_delay]
    set no_output_delay [check_timing_count $timing_text no_output_delay]
    set partial_input_delay [check_timing_count $timing_text \
        partial_input_delay]
    set partial_output_delay [check_timing_count $timing_text \
        partial_output_delay]
    set timing_coverage_ok [expr {$no_clock == 0 && $unconstrained == 0 &&
        $no_input_delay == 0 && $no_output_delay == 0 &&
        $partial_input_delay == 0 && $partial_output_delay == 0}]

    set dut_lut [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && REF_NAME =~ LUT*"]]
    set dut_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && REF_NAME =~ FD*"]]
    set dut_dsp [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && REF_NAME == DSP48E2"]]
    set dut_bram36 [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && REF_NAME == RAMB36E2"]]
    set dut_bram18 [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && REF_NAME == RAMB18E2"]]
    set dut_uram [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && REF_NAME == URAM288"]]
    set lane_cells [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/* && (REF_NAME == hap_a8w8_group32_lane_s42 || ORIG_REF_NAME == hap_a8w8_group32_lane_s42)"]
    set lane_total [llength $lane_cells]
    set left_lanes [llength [filter $lane_cells \
        "NAME =~ $dut_prefix/u_left2/*"]]
    set center_lanes [llength [filter $lane_cells \
        "NAME =~ $dut_prefix/u_center12/*"]]
    set right_lanes [llength [filter $lane_cells \
        "NAME =~ $dut_prefix/u_right2/*"]]
    set left_dsp [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_left2/* && REF_NAME == DSP48E2"]]
    set center_dsp [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_center12/* && REF_NAME == DSP48E2"]]
    set right_dsp [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_right2/* && REF_NAME == DSP48E2"]]
    set left_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_left2/* && REF_NAME =~ FD*"]]
    set center_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_center12/* && REF_NAME =~ FD*"]]
    set right_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_right2/* && REF_NAME =~ FD*"]]
    set left_act_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_left2/u_shard/stage_act_u8_r_reg* && REF_NAME =~ FD*"]]
    set center_act_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_center12/*/stage_act_u8_r_reg* && REF_NAME =~ FD*"]]
    set right_act_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/u_right2/u_shard/stage_act_u8_r_reg* && REF_NAME =~ FD*"]]
    set ref_act_ff [llength [get_cells -quiet -hierarchical -filter \
        "NAME =~ $dut_prefix/input_stage_act_u8_r_reg* && REF_NAME =~ FD*"]]
    lassign [count_data_bufg] data_bufg clock_bufg
    set wns [get_slack max]
    set whs [get_slack min]
    if {$use_col3} {
        set structural_ok [expr {$lane_total == 128 &&
            $left_lanes == 16 && $center_lanes == 96 &&
            $right_lanes == 16 && $dut_dsp == 2176 &&
            $left_dsp == 272 && $center_dsp == 1632 &&
            $right_dsp == 272 && $left_act_ff == 2048 &&
            $center_act_ff == 8192 && $right_act_ff == 2048}]
    } else {
        set structural_ok [expr {$lane_total == 128 && $dut_dsp == 2176 &&
            $ref_act_ff == 8192}]
    }
    set resource_ok [expr {$dut_dsp == 2176 && $dut_bram36 == 0 &&
        $dut_bram18 == 0 && $dut_uram == 0}]
    # Hold slack is not a signoff metric before placement: the unplaced
    # RAMD32 address paths have no router-inserted hold delay yet.  Preserve
    # WHS as a diagnostic and enforce it later in the routed/full-design gate.
    set setup_timing_ok [expr {$wns >= 0.0}]
    set status [expr {$structural_ok && $resource_ok && $setup_timing_ok &&
        $data_bufg == 0 && $forbidden_constraint_count == 0 &&
        $no_timing_exceptions && $timing_coverage_ok ? "PASS" : "FAIL"}]
    set summary [open [file join $out summary.txt] w]
    foreach {key value} [list tool [version -short] part $part top $top \
        use_col3 $use_col3 stage registered_targeted_leaf_post_synth \
        timing_gate_scope setup_only_unplaced hold_diagnostic_only 1 \
        clock_mhz 150 source_proxy_ff [llength $src] \
        sink_proxy_ff [llength $sink] dut_lut_primitives $dut_lut \
        dut_ff_primitives $dut_ff dut_dsp48e2 $dut_dsp \
        dut_ramb36e2 $dut_bram36 dut_ramb18e2 $dut_bram18 \
        dut_uram288 $dut_uram lane_instances $lane_total \
        left_lane_instances $left_lanes center_lane_instances $center_lanes \
        right_lane_instances $right_lanes left_dsp48e2 $left_dsp \
        center_dsp48e2 $center_dsp right_dsp48e2 $right_dsp \
        left_ff_primitives $left_ff center_ff_primitives $center_ff \
        right_ff_primitives $right_ff left_activation_stage_ff $left_act_ff \
        center_activation_stage_ff $center_act_ff \
        right_activation_stage_ff $right_act_ff \
        reference_activation_stage_ff $ref_act_ff wns_ns $wns whs_ns $whs \
        data_bufg $data_bufg clock_bufg $clock_bufg \
        forbidden_timing_exception_count $forbidden_constraint_count \
        no_timing_exceptions $no_timing_exceptions no_clock_endpoints $no_clock \
        unconstrained_internal_endpoints $unconstrained \
        no_input_delay_endpoints $no_input_delay \
        no_output_delay_endpoints $no_output_delay \
        partial_input_delay_endpoints $partial_input_delay \
        partial_output_delay_endpoints $partial_output_delay \
        timing_coverage_ok $timing_coverage_ok structural_ok $structural_ok \
        resource_ok $resource_ok setup_timing_ok $setup_timing_ok \
        status $status] {
        puts $summary "$key=$value"
    }
    close $summary
    puts "ATTN_COL3_REGISTERED_LEAF LABEL=$label WNS=$wns WHS_DIAGNOSTIC=$whs LUT=$dut_lut FF=$dut_ff DSP=$dut_dsp LANES=$lane_total SPLIT=$left_lanes/$center_lanes/$right_lanes DSP_SPLIT=$left_dsp/$center_dsp/$right_dsp ACT_FF=$left_act_ff/$center_act_ff/$right_act_ff REF_ACT_FF=$ref_act_ff DATA_BUFG=$data_bufg EXCEPTIONS=$forbidden_constraint_count/$no_timing_exceptions COVERAGE=$timing_coverage_ok STATUS=$status"
    set result [dict create label $label wns $wns whs $whs lut $dut_lut \
        ff $dut_ff dsp $dut_dsp lanes $lane_total left_lanes $left_lanes \
        center_lanes $center_lanes right_lanes $right_lanes \
        left_dsp $left_dsp center_dsp $center_dsp right_dsp $right_dsp \
        left_ff $left_ff center_ff $center_ff right_ff $right_ff \
        left_act_ff $left_act_ff center_act_ff $center_act_ff \
        right_act_ff $right_act_ff ref_act_ff $ref_act_ff \
        data_bufg $data_bufg setup_timing_ok $setup_timing_ok status $status]
    close_project
    return $result
}

set ref [run_variant $root $report_dir $build_dir $part $manifest \
    $constraint $top reference 0 $forbidden_constraint_count]
set col3 [run_variant $root $report_dir $build_dir $part $manifest \
    $constraint $top col3 1 $forbidden_constraint_count]
set ff_delta [expr {[dict get $col3 ff] - [dict get $ref ff]}]
set lut_delta [expr {[dict get $col3 lut] - [dict get $ref lut]}]
set col3_act_ff [expr {[dict get $col3 left_act_ff] +
    [dict get $col3 center_act_ff] + [dict get $col3 right_act_ff]}]
set act_ff_delta [expr {$col3_act_ff - [dict get $ref ref_act_ff]}]
set comparison_ok [expr {[dict get $ref status] eq "PASS" &&
    [dict get $col3 status] eq "PASS" && $col3_act_ff == 12288 &&
    $act_ff_delta == 4096}]
set final_status [expr {$comparison_ok ? "PASS" : "FAIL"}]
set summary [open [file join $report_dir summary.txt] w]
foreach {key value} [list tool [version -short] part $part \
    stage registered_targeted_leaf_post_synth clock_mhz 150 \
    timing_gate_scope setup_only_unplaced hold_diagnostic_only 1 \
    reference_lut_primitives [dict get $ref lut] \
    col3_lut_primitives [dict get $col3 lut] total_lut_delta $lut_delta \
    reference_ff_primitives [dict get $ref ff] \
    col3_ff_primitives [dict get $col3 ff] total_ff_delta $ff_delta \
    reference_activation_stage_ff [dict get $ref ref_act_ff] \
    col3_activation_stage_ff $col3_act_ff activation_stage_ff_delta $act_ff_delta \
    reference_dsp48e2 [dict get $ref dsp] col3_dsp48e2 [dict get $col3 dsp] \
    col3_lane_split [join [list [dict get $col3 left_lanes] \
        [dict get $col3 center_lanes] [dict get $col3 right_lanes]] /] \
    col3_dsp_split [join [list [dict get $col3 left_dsp] \
        [dict get $col3 center_dsp] [dict get $col3 right_dsp]] /] \
    col3_ff_split [join [list [dict get $col3 left_ff] \
        [dict get $col3 center_ff] [dict get $col3 right_ff]] /] \
    col3_activation_ff_split [join [list [dict get $col3 left_act_ff] \
        [dict get $col3 center_act_ff] [dict get $col3 right_act_ff]] /] \
    reference_wns_ns [dict get $ref wns] reference_whs_ns [dict get $ref whs] \
    col3_wns_ns [dict get $col3 wns] col3_whs_ns [dict get $col3 whs] \
    reference_setup_timing_ok [dict get $ref setup_timing_ok] \
    col3_setup_timing_ok [dict get $col3 setup_timing_ok] \
    reference_data_bufg [dict get $ref data_bufg] \
    col3_data_bufg [dict get $col3 data_bufg] \
    forbidden_timing_exception_count $forbidden_constraint_count \
    comparison_ok $comparison_ok status $final_status] {
    puts $summary "$key=$value"
}
close $summary
puts "ATTN_COL3_REGISTERED_COMPARE FF=[dict get $ref ff]->[dict get $col3 ff] DELTA=$ff_delta ACT_FF=[dict get $ref ref_act_ff]->$col3_act_ff DELTA=$act_ff_delta DSP=[dict get $ref dsp]->[dict get $col3 dsp] WNS=[dict get $ref wns]/[dict get $col3 wns] WHS_DIAGNOSTIC=[dict get $ref whs]/[dict get $col3 whs] DATA_BUFG=[dict get $ref data_bufg]/[dict get $col3 data_bufg] STATUS=$final_status"
if {$final_status ne "PASS"} {
    error "P1_ATTN_COL2_12_2 registered targeted leaf gate failed"
}
