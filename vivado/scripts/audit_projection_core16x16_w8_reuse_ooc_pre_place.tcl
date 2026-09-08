set out [file normalize $::env(HAP_REPORT_DIR)]
set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir \
    projection_core16x16_w8_reuse_ooc_floorplan.tcl]
file mkdir $out

if {![file exists $input_dcp]} {error "missing input DCP $input_dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set actual_dcp_sha [lindex [exec sha256sum -- $input_dcp] 0]
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    $actual_dcp_sha ne $expected_dcp_sha} {
    error "projection pre-place input DCP hash mismatch"
}
if {![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "projection pre-place input manifest hash is invalid"
}
set jobs 32
if {[info exists ::env(HAP_JOBS)]} {set jobs $::env(HAP_JOBS)}
if {![string is integer -strict $jobs] || $jobs < 1 || $jobs > 32} {
    error "HAP_JOBS must be an integer in 1..32, got '$jobs'"
}
set_param general.maxThreads $jobs

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch expected=$expected actual=$actual"
    }
    return $actual
}

proc audit_weight_capture_class {label name_glob expected_nets expected_loads} {
    set nets [lsort -dictionary [get_nets -quiet -hierarchical -filter \
        "NAME =~ $name_glob"]]
    require_count ${label}_nets $nets $expected_nets
    set min_load 1000000000
    set max_load 0
    foreach net $nets {
        set driver_pins [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == OUT}]
        require_count ${label}_driver_pin $driver_pins 1
        set driver [get_cells -quiet -of_objects $driver_pins]
        require_count ${label}_driver $driver 1
        if {[get_property REF_NAME $driver] ne "LUT2"} {
            error "$label capture driver is not a LUT2: $driver"
        }
        set loads [get_pins -quiet -leaf -of_objects $net -filter \
            {DIRECTION == IN}]
        require_count ${label}_loads $loads $expected_loads
        require_count ${label}_ce_loads \
            [get_pins -quiet -leaf -of_objects $net -filter \
                {DIRECTION == IN && REF_PIN_NAME == CE}] $expected_loads
        set load_count [llength $loads]
        if {$load_count < $min_load} {set min_load $load_count}
        if {$load_count > $max_load} {set max_load $load_count}
    }
    return [list [llength $nets] $min_load $max_load]
}

proc audit_weight_capture_tree {} {
    set raw_weight_push [get_nets -quiet -hierarchical -filter \
        {NAME == u_dut/weight_push}]
    require_count raw_weight_push_net $raw_weight_push 1
    set raw_loads [get_pins -quiet -leaf -of_objects $raw_weight_push \
        -filter {DIRECTION == IN}]
    require_count raw_weight_push_loads $raw_loads 37
    set data [audit_weight_capture_class weight_data \
        {u_dut/weight_data_capture_enable*} 32 256]
    set meta [audit_weight_capture_class weight_meta \
        {u_dut/weight_meta_capture_enable*} 2 256]
    set group [audit_weight_capture_class weight_group \
        {u_dut/weight_group_capture_enable*} 2 7]
    return [dict create raw_loads [llength $raw_loads] \
        data_nets [lindex $data 0] data_min [lindex $data 1] \
        data_max [lindex $data 2] meta_nets [lindex $meta 0] \
        meta_min [lindex $meta 1] meta_max [lindex $meta 2] \
        group_nets [lindex $group 0] group_min [lindex $group 1] \
        group_max [lindex $group 2]]
}

proc weight_fifo_mapping {} {
    set ff 0
    set ram 0
    set other 0
    foreach cell [get_cells -quiet -hierarchical -filter \
            {NAME =~ u_dut/*weight_*}] {
        set name [get_property NAME $cell]
        if {![string match "u_dut/*weight_group_mem_reg*" $name] &&
            ![string match "u_dut/*weight_s8_mem_reg*" $name] &&
            ![string match "u_dut/*weight_meta16_mem_reg*" $name]} {
            continue
        }
        set ref [get_property REF_NAME $cell]
        if {[string match "FD*" $ref]} {
            incr ff
        } elseif {[string match "RAM*" $ref]} {
            incr ram
        } else {
            incr other
        }
    }
    return [dict create ff $ff ram $ram other $other]
}

open_checkpoint $input_dcp
if {[get_property PART [current_project]] ne "xcvu9p-flga2104-2L-e"} {
    error "projection OOC pre-place part mismatch"
}
if {[llength [get_cells -quiet u_dut]] != 1 ||
    [llength [get_ports -quiet]] != 1} {
    error "projection OOC pre-place harness identity mismatch"
}

set pre_mapping [weight_fifo_mapping]
set pre_capture [audit_weight_capture_tree]
if {[dict get $pre_mapping ff] != 8718 ||
    [dict get $pre_mapping ram] != 0 ||
    [dict get $pre_mapping other] != 0} {
    error "projection W8 FIFO register mapping mismatch before opt: $pre_mapping"
}

opt_design -directive ExploreWithRemap
set dut_nets [get_nets -quiet -hierarchical -filter {NAME =~ u_dut/*}]
if {[llength $dut_nets] != 0} {
    set_property CLOCK_BUFFER_TYPE NONE $dut_nets
}
set post_mapping [weight_fifo_mapping]
set post_capture [audit_weight_capture_tree]
if {[dict get $post_mapping ff] != 8718 ||
    [dict get $post_mapping ram] != 0 ||
    [dict get $post_mapping other] != 0} {
    error "projection W8 FIFO register mapping mismatch after opt: $post_mapping"
}

set plan [hap_projection_ooc_floorplan::discover]
hap_projection_ooc_floorplan::apply $plan
set pblock_audit [hap_projection_ooc_floorplan::audit_pblocks $plan 1]
hap_projection_ooc_floorplan::write_plan $plan \
    [file join $out floorplan_pre_place_audit.txt] \
    PROJECTION_REUSE_OOC_PRE_PLACE_FLOORPLAN_PASS
report_drc -file [file join $out drc_pre_place_audit.rpt]
set drc_errors [llength [get_drc_violations -quiet -filter \
    {SEVERITY == Error}]]

set region0_input_primitives [dict get $plan region0_input_primitives]
set region0_localization_ok \
    [hap_projection_ooc_floorplan::region0_input_localization_ok $plan]
set region3_input_primitives [dict get $plan region3_input_primitives]
set region3_localization_ok \
    [hap_projection_ooc_floorplan::region3_input_localization_ok $plan]
set owner_region2_weight_anchor_ok \
    [hap_projection_ooc_floorplan::owner_region2_weight_anchor_ok $plan]

set status [expr {$drc_errors == 0 &&
    [dict get $pblock_audit pblock_count] == 10 &&
    [dict get $plan center_region1_bisect_exact_cover] == 1 &&
    [dict get $plan center_region1_dsp_stripe_exact_cover] == 1 &&
    $region0_localization_ok && $region3_localization_ok &&
    $owner_region2_weight_anchor_ok ? \
    "PASS" : "FAIL"}]
set fp [open [file join $out pre_place_summary.txt] w]
foreach {key value} [list tool [version -short] \
    part [get_property PART [current_project]] \
    stage REGISTERED_OOC_PRE_PLACE_AUDIT input_dcp $input_dcp jobs $jobs \
    input_dcp_sha256 $actual_dcp_sha \
    input_manifest_sha256 $input_manifest_sha \
    weight_fifo_ff_pre_opt [dict get $pre_mapping ff] \
    weight_fifo_ram_pre_opt [dict get $pre_mapping ram] \
    weight_fifo_ff_post_opt [dict get $post_mapping ff] \
    weight_fifo_ram_post_opt [dict get $post_mapping ram] \
    raw_weight_push_loads_pre_opt [dict get $pre_capture raw_loads] \
    raw_weight_push_loads_post_opt [dict get $post_capture raw_loads] \
    weight_data_capture_contract 32x256 \
    weight_data_capture_loads_pre_opt \
        [dict get $pre_capture data_min]/[dict get $pre_capture data_max] \
    weight_data_capture_loads_post_opt \
        [dict get $post_capture data_min]/[dict get $post_capture data_max] \
    weight_meta_capture_contract 2x256 \
    weight_meta_capture_loads_pre_opt \
        [dict get $pre_capture meta_min]/[dict get $pre_capture meta_max] \
    weight_meta_capture_loads_post_opt \
        [dict get $post_capture meta_min]/[dict get $post_capture meta_max] \
    weight_group_capture_contract 2x7 \
    weight_group_capture_loads_pre_opt \
        [dict get $pre_capture group_min]/[dict get $pre_capture group_max] \
    weight_group_capture_loads_post_opt \
        [dict get $post_capture group_min]/[dict get $post_capture group_max] \
    pblock_count [dict get $pblock_audit pblock_count] \
    floorplan_dut_primitives [llength [dict get $plan dut_primitives]] \
    floorplan_left_primitives [llength [dict get $plan left_primitives]] \
    floorplan_frontend_primitives \
        [llength [dict get $plan frontend_primitives]] \
    floorplan_center_primitives [llength [dict get $plan center_primitives]] \
    floorplan_center_region0_frontend_primitives \
        [llength [dict get $plan center_region0_frontend_primitives]] \
    floorplan_center_region1_cols4_5_lane_roots \
        [llength [dict get $plan center_region1_cols4_5_lane_roots]] \
    floorplan_center_region1_cols6_7_lane_roots \
        [llength [dict get $plan center_region1_cols6_7_lane_roots]] \
    floorplan_center_region1_cols4_5_primitives \
        [llength [dict get $plan center_region1_cols4_5_primitives]] \
    floorplan_center_region1_cols6_7_primitives \
        [llength [dict get $plan center_region1_cols6_7_primitives]] \
    floorplan_center_region1_residual_primitives \
        [llength [dict get $plan center_region1_residual_primitives]] \
    floorplan_center_region1_cols4_5_dsp_primitives \
        [llength [dict get $plan center_region1_cols4_5_dsp_primitives]] \
    floorplan_center_region1_cols6_7_dsp_primitives \
        [llength [dict get $plan center_region1_cols6_7_dsp_primitives]] \
    floorplan_center_region1_logic_residual_primitives \
        [llength [dict get $plan center_region1_logic_residual_primitives]] \
    floorplan_center_region1_logic_residual_dsp48e2 \
        [hap_projection_ooc_floorplan::count_ref \
            [dict get $plan center_region1_logic_residual_primitives] DSP48E2] \
    floorplan_center_region1_bisect_exact_cover \
        [dict get $plan center_region1_bisect_exact_cover] \
    floorplan_center_region1_dsp_stripe_exact_cover \
        [dict get $plan center_region1_dsp_stripe_exact_cover] \
    floorplan_right_primitives [llength [dict get $plan right_primitives]] \
    floorplan_owner_primitives [llength [dict get $plan owner_primitives]] \
    floorplan_owner_floorplan_primitives \
        [llength [dict get $plan owner_floorplan_primitives]] \
    floorplan_owner_residual_floorplan_primitives \
        [llength [dict get $plan owner_residual_floorplan_primitives]] \
    floorplan_owner_region2_weight_ff_primitives \
        [llength [dict get $plan owner_region2_weight_ff_primitives]] \
    floorplan_owner_region2_weight_lut_primitives \
        [llength [dict get $plan owner_region2_weight_lut_primitives]] \
    floorplan_owner_region2_weight_primitives \
        [llength [dict get $plan owner_region2_weight_primitives]] \
    floorplan_owner_region2_weight_exact_cover \
        [dict get $plan owner_region2_weight_exact_cover] \
    floorplan_region0_input_activation_primitives \
        [llength [dict get $plan region0_input_activation_primitives]] \
    floorplan_region0_input_zero_point_primitives \
        [llength [dict get $plan region0_input_zero_point_primitives]] \
    floorplan_region0_input_weight_ff_primitives \
        [llength [dict get $plan region0_input_weight_ff_primitives]] \
    floorplan_region0_input_weight_lut_primitives \
        [llength [dict get $plan region0_input_weight_lut_primitives]] \
    floorplan_region0_input_weight_primitives \
        [llength [dict get $plan region0_input_weight_primitives]] \
    floorplan_region0_input_primitives \
        [llength $region0_input_primitives] \
    floorplan_region0_input_fdre \
        [hap_projection_ooc_floorplan::count_ref \
            $region0_input_primitives FDRE] \
    floorplan_region0_input_lut3 \
        [hap_projection_ooc_floorplan::count_ref \
            $region0_input_primitives LUT3] \
    floorplan_region0_input_dsp48e2 \
        [hap_projection_ooc_floorplan::count_ref \
            $region0_input_primitives DSP48E2] \
    floorplan_owner_region0_input_exact_cover \
        [dict get $plan owner_region0_input_exact_cover] \
    floorplan_region0_input_localization_ok $region0_localization_ok \
    floorplan_center_region3_primitives \
        [llength [dict get $plan center_region3_primitives]] \
    floorplan_center_region3_floorplan_primitives \
        [llength [dict get $plan center_region3_floorplan_primitives]] \
    floorplan_region3_input_activation_primitives \
        [llength [dict get $plan region3_input_activation_primitives]] \
    floorplan_region3_input_zero_point_primitives \
        [llength [dict get $plan region3_input_zero_point_primitives]] \
    floorplan_region3_input_weight_ff_primitives \
        [llength [dict get $plan region3_input_weight_ff_primitives]] \
    floorplan_region3_input_weight_lut_primitives \
        [llength [dict get $plan region3_input_weight_lut_primitives]] \
    floorplan_region3_owner_weight_ff_primitives \
        [llength [dict get $plan region3_owner_weight_ff_primitives]] \
    floorplan_region3_owner_weight_lut_primitives \
        [llength [dict get $plan region3_owner_weight_lut_primitives]] \
    floorplan_region3_input_primitives \
        [llength $region3_input_primitives] \
    floorplan_region3_input_fdre \
        [hap_projection_ooc_floorplan::count_ref \
            $region3_input_primitives FDRE] \
    floorplan_region3_input_lut3 \
        [hap_projection_ooc_floorplan::count_ref \
            $region3_input_primitives LUT3] \
    floorplan_region3_input_dsp48e2 \
        [hap_projection_ooc_floorplan::count_ref \
            $region3_input_primitives DSP48E2] \
    floorplan_owner_region3_input_exact_cover \
        [dict get $plan owner_region3_input_exact_cover] \
    floorplan_region3_weight_owner_residency_ok \
        [dict get $plan region3_weight_owner_residency_ok] \
    floorplan_region3_input_localization_ok $region3_localization_ok \
    floorplan_owner_region2_weight_anchor_ok \
        $owner_region2_weight_anchor_ok \
    drc_errors $drc_errors status $status] {
    puts $fp "$key=$value"
}
close $fp
puts "PROJECTION_REUSE_OOC_PRE_PLACE FIFO_FF=[dict get $post_mapping ff] FIFO_RAM=[dict get $post_mapping ram] PBLOCKS=[dict get $pblock_audit pblock_count] DRC_ERRORS=$drc_errors STATUS=$status"
if {$status ne "PASS"} {
    error "projection reuse OOC pre-place audit failed"
}
close_project
