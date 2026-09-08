set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set build_dir [file normalize $::env(HAP_BUILD_DIR)]
set part xcvu9p-flga2104-2L-e
set manifest [file join $root vivado manifests \
    attention_a8w8_col3_leaf_sources.list]
set constraint [file join $root vivado constraints \
    attention_a8w8_col3_leaf_ooc_150mhz.xdc]

file mkdir $report_dir
file mkdir $build_dir
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
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

proc run_variant {root report_dir build_dir part manifest constraint \
        label top} {
    set out [file join $report_dir $label]
    set build [file join $build_dir $label]
    file mkdir $out
    file mkdir $build
    create_project attention_${label}_leaf_synth $build -part $part -force
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
    update_compile_order -fileset sources_1

    synth_design -top $top -part $part -mode out_of_context \
        -flatten_hierarchy none -directive PerformanceOptimized
    write_checkpoint -force [file join $out post_synth.dcp]
    report_utilization -file [file join $out utilization_post_synth.rpt]
    report_utilization -hierarchical -hierarchical_depth 16 \
        -file [file join $out utilization_hier_post_synth.rpt]
    report_timing_summary -delay_type min_max -max_paths 100 \
        -report_unconstrained \
        -file [file join $out timing_post_synth.rpt]
    report_clock_utilization -file \
        [file join $out clock_utilization_post_synth.rpt]

    set lut_total [llength [get_cells -quiet -hierarchical -filter \
        {REF_NAME =~ LUT*}]]
    set ff_total [llength [get_cells -quiet -hierarchical -filter \
        {REF_NAME =~ FD*}]]
    set dsp_total [llength [get_cells -quiet -hierarchical -filter \
        {REF_NAME == DSP48E2}]]
    set bram36_total [llength [get_cells -quiet -hierarchical -filter \
        {REF_NAME == RAMB36E2}]]
    set bram18_total [llength [get_cells -quiet -hierarchical -filter \
        {REF_NAME == RAMB18E2}]]
    set uram_total [llength [get_cells -quiet -hierarchical -filter \
        {REF_NAME == URAM288}]]
    lassign [count_data_bufg] data_bufg clock_bufg
    set wns [get_slack max]
    set whs [get_slack min]

    # REF/ORIG_REF names are kept by flatten_hierarchy=none.  The instance
    # counts are independent of primitive inference and fail closed if a lane
    # or one of the three physical shard wrappers disappears.
    set lane_cells [get_cells -quiet -hierarchical -filter {
        REF_NAME == hap_a8w8_group32_lane_s42 ||
        ORIG_REF_NAME == hap_a8w8_group32_lane_s42}]
    set lane_total [llength $lane_cells]
    set left_lanes [llength [filter $lane_cells {NAME =~ u_left2/*}]]
    set center_lanes [llength [filter $lane_cells {NAME =~ u_center12/*}]]
    set right_lanes [llength [filter $lane_cells {NAME =~ u_right2/*}]]
    set left_dsp [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME == DSP48E2 && NAME =~ u_left2/*}]]
    set center_dsp [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME == DSP48E2 && NAME =~ u_center12/*}]]
    set right_dsp [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME == DSP48E2 && NAME =~ u_right2/*}]]
    set left_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* && NAME =~ u_left2/*}]]
    set center_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* && NAME =~ u_center12/*}]]
    set right_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* && NAME =~ u_right2/*}]]
    set left_act_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* &&
        NAME =~ u_left2/u_shard/stage_act_u8_r_reg*}]]
    set center_act_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* &&
        NAME =~ u_center12/*/stage_act_u8_r_reg*}]]
    set right_act_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* &&
        NAME =~ u_right2/u_shard/stage_act_u8_r_reg*}]]
    set ref_act_ff [llength [get_cells -quiet -hierarchical -filter {
        REF_NAME =~ FD* && NAME =~ input_stage_act_u8_r_reg*}]]
    set left_instances [llength [get_cells -quiet u_left2]]
    set center_instances [llength [get_cells -quiet u_center12]]
    set right_instances [llength [get_cells -quiet u_right2]]
    set structural_ok 0
    if {$label eq "col3"} {
        set structural_ok [expr {
            $lane_total == 128 &&
            $left_lanes == 16 && $center_lanes == 96 &&
            $right_lanes == 16 &&
            $dsp_total == 2176 &&
            $left_dsp == 272 && $center_dsp == 1632 &&
            $right_dsp == 272 &&
            $left_instances == 1 && $center_instances == 1 &&
            $right_instances == 1 &&
            $left_act_ff == 2048 && $center_act_ff == 8192 &&
            $right_act_ff == 2048}]
    } else {
        set structural_ok [expr {
            $lane_total == 128 && $dsp_total == 2176 &&
            $ref_act_ff == 8192}]
    }
    set resource_ok [expr {
        $dsp_total == 2176 && $bram36_total == 0 &&
        $bram18_total == 0 && $uram_total == 0}]
    set timing_ok [expr {$wns >= 0.0 && $whs >= 0.0}]
    set bufg_ok [expr {$data_bufg == 0}]
    set status [expr {$structural_ok && $resource_ok && $timing_ok &&
        $bufg_ok ? "PASS" : "FAIL"}]

    set summary [open [file join $out summary.txt] w]
    foreach {key value} [list \
        tool [version -short] part $part top $top stage post_synth \
        clock_mhz 150 clock_period_ns 6.667 clock_uncertainty_ns 0.150 \
        wns_ns $wns whs_ns $whs lut_primitives $lut_total \
        ff_primitives $ff_total dsp48e2 $dsp_total expected_dsp48e2 2176 \
        ramb36e2 $bram36_total ramb18e2 $bram18_total uram288 $uram_total \
        data_bufg $data_bufg clock_bufg $clock_bufg lane_instances $lane_total \
        left_lane_instances $left_lanes center_lane_instances $center_lanes \
        right_lane_instances $right_lanes left_dsp48e2 $left_dsp \
        center_dsp48e2 $center_dsp right_dsp48e2 $right_dsp \
        left_ff_primitives $left_ff center_ff_primitives $center_ff \
        right_ff_primitives $right_ff left_activation_stage_ff $left_act_ff \
        center_activation_stage_ff $center_act_ff \
        right_activation_stage_ff $right_act_ff \
        reference_activation_stage_ff $ref_act_ff \
        left_wrapper_instances $left_instances \
        center_wrapper_instances $center_instances \
        right_wrapper_instances $right_instances structural_ok $structural_ok \
        resource_ok $resource_ok timing_ok $timing_ok bufg_ok $bufg_ok \
        status $status] {
        puts $summary "$key=$value"
    }
    close $summary
    puts "ATTN_COL3_LEAF_VARIANT LABEL=$label WNS=$wns WHS=$whs LUT=$lut_total FF=$ff_total DSP=$dsp_total LANES=$lane_total SPLIT=$left_lanes/$center_lanes/$right_lanes SHARD_DSP=$left_dsp/$center_dsp/$right_dsp ACT_FF=$left_act_ff/$center_act_ff/$right_act_ff REF_ACT_FF=$ref_act_ff DATA_BUFG=$data_bufg STATUS=$status"

    set result [dict create label $label top $top wns $wns whs $whs \
        lut_total $lut_total ff_total $ff_total dsp_total $dsp_total \
        data_bufg $data_bufg lane_total $lane_total left_lanes $left_lanes \
        center_lanes $center_lanes right_lanes $right_lanes \
        left_dsp $left_dsp center_dsp $center_dsp right_dsp $right_dsp \
        left_ff $left_ff center_ff $center_ff right_ff $right_ff \
        left_act_ff $left_act_ff center_act_ff $center_act_ff \
        right_act_ff $right_act_ff ref_act_ff $ref_act_ff \
        structural_ok $structural_ok resource_ok $resource_ok \
        timing_ok $timing_ok bufg_ok $bufg_ok status $status]
    close_project
    return $result
}

set ref_result [run_variant $root $report_dir $build_dir $part $manifest \
    $constraint reference hap_a8w8_array_16x16_s42]
set col3_result [run_variant $root $report_dir $build_dir $part $manifest \
    $constraint col3 hap_a8w8_array_16x16_s42_col3]

set total_ff_delta [expr {[dict get $col3_result ff_total] -
    [dict get $ref_result ff_total]}]
set activation_ff_col3 [expr {[dict get $col3_result left_act_ff] +
    [dict get $col3_result center_act_ff] +
    [dict get $col3_result right_act_ff]}]
set activation_ff_delta [expr {$activation_ff_col3 -
    [dict get $ref_result ref_act_ff]}]
set total_lut_delta [expr {[dict get $col3_result lut_total] -
    [dict get $ref_result lut_total]}]
set comparison_ok [expr {
    [dict get $ref_result structural_ok] &&
    [dict get $ref_result resource_ok] &&
    [dict get $col3_result status] eq "PASS" &&
    $activation_ff_col3 == 12288 && $activation_ff_delta == 4096}]
set final_status [expr {$comparison_ok ? "PASS" : "FAIL"}]

set summary [open [file join $report_dir summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $part stage targeted_leaf_post_synth \
    reference_top [dict get $ref_result top] \
    col3_top [dict get $col3_result top] \
    reference_lut_primitives [dict get $ref_result lut_total] \
    col3_lut_primitives [dict get $col3_result lut_total] \
    total_lut_delta $total_lut_delta \
    reference_ff_primitives [dict get $ref_result ff_total] \
    col3_ff_primitives [dict get $col3_result ff_total] \
    total_ff_delta $total_ff_delta \
    reference_activation_stage_ff [dict get $ref_result ref_act_ff] \
    col3_activation_stage_ff $activation_ff_col3 \
    activation_stage_ff_delta $activation_ff_delta \
    reference_dsp48e2 [dict get $ref_result dsp_total] \
    col3_dsp48e2 [dict get $col3_result dsp_total] \
    col3_lane_split [join [list [dict get $col3_result left_lanes] \
        [dict get $col3_result center_lanes] \
        [dict get $col3_result right_lanes]] /] \
    col3_dsp_split [join [list [dict get $col3_result left_dsp] \
        [dict get $col3_result center_dsp] \
        [dict get $col3_result right_dsp]] /] \
    col3_ff_split [join [list [dict get $col3_result left_ff] \
        [dict get $col3_result center_ff] \
        [dict get $col3_result right_ff]] /] \
    col3_activation_ff_split [join [list [dict get $col3_result left_act_ff] \
        [dict get $col3_result center_act_ff] \
        [dict get $col3_result right_act_ff]] /] \
    reference_wns_ns [dict get $ref_result wns] \
    reference_whs_ns [dict get $ref_result whs] \
    col3_wns_ns [dict get $col3_result wns] \
    col3_whs_ns [dict get $col3_result whs] \
    reference_data_bufg [dict get $ref_result data_bufg] \
    col3_data_bufg [dict get $col3_result data_bufg] \
    comparison_ok $comparison_ok status $final_status] {
    puts $summary "$key=$value"
}
close $summary
puts "ATTN_COL3_LEAF_COMPARE FF=[dict get $ref_result ff_total]->[dict get $col3_result ff_total] DELTA=$total_ff_delta ACT_FF=[dict get $ref_result ref_act_ff]->$activation_ff_col3 DELTA=$activation_ff_delta DSP=[dict get $ref_result dsp_total]->[dict get $col3_result dsp_total] WNS=[dict get $ref_result wns]/[dict get $col3_result wns] DATA_BUFG=[dict get $ref_result data_bufg]/[dict get $col3_result data_bufg] STATUS=$final_status"
if {$final_status ne "PASS"} {
    error "P1_ATTN_COL2_12_2 targeted leaf synthesis gate failed"
}
