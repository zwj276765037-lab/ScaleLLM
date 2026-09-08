set out [file normalize $::env(HAP_REPORT_DIR)]
set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set expected_dcp_sha $::env(HAP_EXPECTED_DCP_SHA256)
set input_manifest_sha $::env(HAP_INPUT_MANIFEST_SHA256)
set lower_tile_name $::env(HAP_WINDOW_LOWER_TILE)
set upper_tile_name $::env(HAP_WINDOW_UPPER_TILE)

file mkdir $out
if {![file exists $input_dcp]} {error "missing input DCP $input_dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}
set actual_dcp_sha [lindex [exec sha256sum -- $input_dcp] 0]
if {![regexp {^[0-9a-f]{64}$} $expected_dcp_sha] ||
    $actual_dcp_sha ne $expected_dcp_sha} {
    error "congestion diagnosis input DCP hash mismatch"
}
if {![regexp {^[0-9a-f]{64}$} $input_manifest_sha]} {
    error "congestion diagnosis input manifest hash is invalid"
}

proc require_count {label objects expected} {
    set actual [llength $objects]
    if {$actual != $expected} {
        error "$label count mismatch expected=$expected actual=$actual"
    }
    return $actual
}

proc object_names {objects} {
    if {[llength $objects] == 0} {return {}}
    return [lsort -dictionary -unique [get_property NAME $objects]]
}

proc name_intersection {left right} {
    set present [dict create]
    foreach value $left {dict set present $value 1}
    set result {}
    foreach value $right {
        if {[dict exists $present $value]} {lappend result $value}
    }
    return [lsort -dictionary -unique $result]
}

proc name_difference {left right} {
    set removed [dict create]
    foreach value $right {dict set removed $value 1}
    set result {}
    foreach value $left {
        if {![dict exists $removed $value]} {lappend result $value}
    }
    return [lsort -dictionary -unique $result]
}

proc output_net_names {cells} {
    if {[llength $cells] == 0} {return {}}
    set pins [get_pins -quiet -of_objects $cells -filter {DIRECTION == OUT}]
    return [object_names [get_nets -quiet -of_objects $pins -segments \
        -top_net_of_hierarchical_group]]
}

proc input_net_names {cells} {
    if {[llength $cells] == 0} {return {}}
    set pins [get_pins -quiet -of_objects $cells -filter {DIRECTION == IN}]
    return [object_names [get_nets -quiet -of_objects $pins -segments \
        -top_net_of_hierarchical_group]]
}

proc cell_category {name} {
    if {[string match "u_dut/group_stage_act_u8_region_r_reg*" $name]} {
        if {[info exists ::localized_stage_name($name)]} {
            return localized_activation
        }
        return owner_activation
    }
    if {[string match \
            "u_dut/group_stage_act_zero_point_region_r_reg*" $name]} {
        if {[info exists ::localized_stage_name($name)]} {
            return localized_zero_point
        }
        return owner_zero_point
    }
    if {[string match "u_dut/group_stage_weight_s8_r*" $name]} {
        if {[info exists ::localized_stage_name($name)]} {
            return localized_weight
        }
        return owner_weight
    }
    if {[string match \
            "u_dut/u_array/u_center12/u_region2_cols8_11/*" $name]} {
        return region2
    }
    if {[string match \
            "u_dut/u_array/u_center12/u_region3_cols12_13/*" $name]} {
        return region3
    }
    if {[string match \
            "u_dut/u_array/u_center12/u_region1_cols4_7/*" $name]} {
        return region1
    }
    if {[string match \
            "u_dut/u_array/u_center12/u_region0_cols2_3/*" $name]} {
        return region0
    }
    if {![string match "u_dut/*" $name]} {return harness}
    return owner_or_other_dut
}

open_checkpoint $input_dcp
set expected_part xcvu9p-flga2104-2L-e
set actual_part [get_property PART [current_project]]
if {$actual_part ne $expected_part} {
    error "part mismatch expected=$expected_part actual=$actual_part"
}

set lower_tile [get_tiles -quiet $lower_tile_name]
set upper_tile [get_tiles -quiet $upper_tile_name]
require_count lower_window_tile $lower_tile 1
require_count upper_window_tile $upper_tile 1
set lower_x [get_property GRID_POINT_X $lower_tile]
set lower_y [get_property GRID_POINT_Y $lower_tile]
set upper_x [get_property GRID_POINT_X $upper_tile]
set upper_y [get_property GRID_POINT_Y $upper_tile]
set min_x [expr {min($lower_x, $upper_x)}]
set max_x [expr {max($lower_x, $upper_x)}]
set min_y [expr {min($lower_y, $upper_y)}]
set max_y [expr {max($lower_y, $upper_y)}]
set tile_filter [format \
    {GRID_POINT_X >= %d && GRID_POINT_X <= %d && GRID_POINT_Y >= %d && GRID_POINT_Y <= %d} \
    $min_x $max_x $min_y $max_y]
set window_tiles [get_tiles -quiet -filter $tile_filter]
if {[llength $window_tiles] == 0} {error "window tile collection is empty"}
set window_sites [get_sites -quiet -of_objects $window_tiles]
if {[llength $window_sites] == 0} {error "window site collection is empty"}

# Reverse site-to-cell lookup is not uniform across primitive types.  Union the
# direct site relation with the BEL relation and retain only placed leaf cells.
set direct_site_cells [get_cells -quiet -of_objects $window_sites]
set window_bels [get_bels -quiet -of_objects $window_sites]
set bel_cells [get_cells -quiet -of_objects $window_bels]
set window_cell_names [lsort -dictionary -unique [concat \
    [object_names $direct_site_cells] [object_names $bel_cells]]]
set window_cells [get_cells -quiet $window_cell_names -filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
if {[llength $window_cells] == 0} {error "window primitive collection is empty"}

set pblocks [get_pblocks -quiet]
require_count canonical_pblocks $pblocks 10
set region2_pblock [get_pblocks -quiet \
    pb_projection_center_region2_shared_cr_x0y5_x1y9]
set region3_pblock [get_pblocks -quiet \
    pb_projection_center_region3_shared_cr_x0y5_x1y9]
set owner_pblock [get_pblocks -quiet pb_projection_owner_cr_x2y5_x4y9]
require_count region2_pblock $region2_pblock 1
require_count region3_pblock $region3_pblock 1
require_count owner_pblock $owner_pblock 1

set primitive_filter {
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}
set region2_cells [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/u_center12/u_region2_cols8_11/* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set region3_cells [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/u_center12/u_region3_cols12_13/* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set region0_cells [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/u_center12/u_region0_cols2_3/* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set region1_cells [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/u_center12/u_region1_cols4_7/* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]
set region2_pblock_cells [get_cells -quiet -of_objects $region2_pblock \
    -filter $primitive_filter]
set region3_pblock_cells [get_cells -quiet -of_objects $region3_pblock \
    -filter $primitive_filter]
set owner_pblock_cells [get_cells -quiet -of_objects $owner_pblock \
    -filter $primitive_filter]

set all_activation [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/group_stage_act_u8_region_r_reg* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME =~ FD*}]
set all_zero_point [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/group_stage_act_zero_point_region_r_reg* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME =~ FD*}]
set all_weight [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/group_stage_weight_s8_r* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL &&
    REF_NAME != GND && REF_NAME != VCC}]

set region3_pblock_names [object_names $region3_pblock_cells]
set localized_activation_names [name_intersection \
    [object_names $all_activation] $region3_pblock_names]
set localized_zero_names [name_intersection \
    [object_names $all_zero_point] $region3_pblock_names]
set localized_weight_names [name_intersection \
    [object_names $all_weight] $region3_pblock_names]
array set localized_stage_name {}
foreach name [concat $localized_activation_names $localized_zero_names \
        $localized_weight_names] {
    set localized_stage_name($name) 1
}

set localized_activation [get_cells -quiet $localized_activation_names]
set localized_zero [get_cells -quiet $localized_zero_names]
set localized_weight [get_cells -quiet $localized_weight_names]
set owner_activation_names [name_difference [object_names $all_activation] \
    $localized_activation_names]
set owner_zero_names [name_difference [object_names $all_zero_point] \
    $localized_zero_names]
set owner_weight_names [name_difference [object_names $all_weight] \
    $localized_weight_names]
set owner_stage_names [concat $owner_activation_names $owner_zero_names \
    $owner_weight_names]
set owner_residual_names [name_difference [object_names $owner_pblock_cells] \
    $owner_stage_names]
set owner_activation [get_cells -quiet $owner_activation_names]
set owner_zero [get_cells -quiet $owner_zero_names]
set owner_weight [get_cells -quiet $owner_weight_names]
set owner_residual [get_cells -quiet $owner_residual_names]

set stage_fh [open [file join $out stage_cell_locations.tsv] w]
puts $stage_fh "category\tref_name\tloc\tcell"
foreach {category cells} [list \
        owner_activation $owner_activation \
        owner_zero_point $owner_zero \
        owner_weight $owner_weight \
        localized_activation $localized_activation \
        localized_zero_point $localized_zero \
        localized_weight $localized_weight] {
    if {[llength $cells] == 0} {continue}
    set names [get_property NAME $cells]
    set refs [get_property REF_NAME $cells]
    set locs [get_property LOC $cells]
    foreach name $names ref $refs loc $locs {
        puts $stage_fh "$category\t$ref\t$loc\t$name"
    }
}
close $stage_fh

require_count region0_logic $region0_cells 36644
require_count region1_logic $region1_cells 70469
require_count region2_logic $region2_cells 70457
require_count region3_logic $region3_cells 36649
require_count region2_pblock_primitives $region2_pblock_cells 70457
require_count activation_source_universe $all_activation 8192
require_count zero_point_source_universe $all_zero_point 256
require_count weight_source_universe $all_weight 8192

set category_counts [dict create]
set reference_counts [dict create]
set window_names [get_property NAME $window_cells]
set window_refs [get_property REF_NAME $window_cells]
set window_locs [get_property LOC $window_cells]
set cells_fh [open [file join $out window_cells.tsv] w]
puts $cells_fh "category\tref_name\tloc\tcell"
foreach name $window_names ref $window_refs loc $window_locs {
    set category [cell_category $name]
    dict incr category_counts $category
    dict incr reference_counts "$category\t$ref"
    puts $cells_fh "$category\t$ref\t$loc\t$name"
}
close $cells_fh

set category_fh [open [file join $out window_category_counts.tsv] w]
puts $category_fh "category\tprimitive_count"
foreach category [lsort -dictionary [dict keys $category_counts]] {
    puts $category_fh "$category\t[dict get $category_counts $category]"
}
close $category_fh

set ref_fh [open [file join $out window_reference_counts.tsv] w]
puts $ref_fh "category\tref_name\tprimitive_count"
foreach key [lsort -dictionary [dict keys $reference_counts]] {
    puts $ref_fh "$key\t[dict get $reference_counts $key]"
}
close $ref_fh

set pblock_fh [open [file join $out window_pblock_counts.tsv] w]
puts $pblock_fh "pblock\tprimitive_count\twindow_primitive_count"
foreach pblock [lsort -dictionary $pblocks] {
    set pblock_cells [get_cells -quiet -of_objects $pblock \
        -filter $primitive_filter]
    set overlap [name_intersection [object_names $pblock_cells] $window_names]
    puts $pblock_fh "[get_property NAME $pblock]\t[llength $pblock_cells]\t[llength $overlap]"
}
close $pblock_fh

# Query routed resources in the exact report rectangle.  This makes the
# crossing matrix distinguish logical connectivity from nets whose routed
# nodes actually consume this congestion window.
set window_nodes [get_nodes -quiet -of_objects $window_tiles]
set window_routed_nets [get_nets -quiet -of_objects $window_nodes -segments \
    -top_net_of_hierarchical_group]
set window_routed_net_names [object_names $window_routed_nets]

set group_names {
    region0 region1 region2 region3 owner_residual owner_activation owner_zero_point
    owner_weight localized_activation localized_zero_point localized_weight
}
set group_cells(region0) $region0_cells
set group_cells(region1) $region1_cells
set group_cells(region2) $region2_cells
set group_cells(region3) $region3_cells
set group_cells(owner_residual) $owner_residual
set group_cells(owner_activation) $owner_activation
set group_cells(owner_zero_point) $owner_zero
set group_cells(owner_weight) $owner_weight
set group_cells(localized_activation) $localized_activation
set group_cells(localized_zero_point) $localized_zero
set group_cells(localized_weight) $localized_weight

set group_fh [open [file join $out source_group_counts.tsv] w]
puts $group_fh "group\tprimitive_count\toutput_net_count\tinput_net_count"
foreach group $group_names {
    set group_output_nets($group) [output_net_names $group_cells($group)]
    set group_input_nets($group) [input_net_names $group_cells($group)]
    puts $group_fh "$group\t[llength $group_cells($group)]\t[llength $group_output_nets($group)]\t[llength $group_input_nets($group)]"
}
close $group_fh

set crossing_fh [open [file join $out crossing_nets.tsv] w]
puts $crossing_fh \
    "source\tdestination\tlogical_crossing_nets\twindow_routed_crossing_nets"
set crossing_detail_fh \
    [open [file join $out crossing_net_details.tsv] w]
puts $crossing_detail_fh "source\tdestination\tnet"
set nonzero_logical_pairs 0
set nonzero_window_pairs 0
foreach source $group_names {
    foreach destination $group_names {
        if {$source eq $destination} {continue}
        set logical [name_intersection $group_output_nets($source) \
            $group_input_nets($destination)]
        set routed [name_intersection $logical $window_routed_net_names]
        if {[llength $logical] != 0} {incr nonzero_logical_pairs}
        if {[llength $routed] != 0} {incr nonzero_window_pairs}
        puts $crossing_fh "$source\t$destination\t[llength $logical]\t[llength $routed]"
        foreach net $routed {
            puts $crossing_detail_fh "$source\t$destination\t$net"
        }
    }
}
close $crossing_fh
close $crossing_detail_fh

set summary_fh [open [file join $out summary.txt] w]
foreach {key value} [list \
        tool [version -short] part $actual_part \
        stage PROJECTION_REUSE_OOC_ROUTED_CONGESTION_WINDOW_DIAGNOSIS \
        evidence_class READ_ONLY_ROUTED_DCP_DIAGNOSIS \
        input_dcp $input_dcp input_dcp_sha256 $actual_dcp_sha \
        input_manifest_sha256 $input_manifest_sha \
        lower_tile $lower_tile_name upper_tile $upper_tile_name \
        grid_min_x $min_x grid_max_x $max_x \
        grid_min_y $min_y grid_max_y $max_y \
        window_tiles [llength $window_tiles] \
        window_sites [llength $window_sites] \
        window_primitives [llength $window_cells] \
        window_routing_nodes [llength $window_nodes] \
        window_routed_nets [llength $window_routed_nets] \
        pblock_count [llength $pblocks] \
        region0_primitives [llength $region0_cells] \
        region1_primitives [llength $region1_cells] \
        region2_primitives [llength $region2_cells] \
        region3_primitives [llength $region3_cells] \
        activation_source_universe [llength $all_activation] \
        zero_point_source_universe [llength $all_zero_point] \
        weight_source_universe [llength $all_weight] \
        owner_physical_primitives [llength $owner_pblock_cells] \
        owner_residual_primitives [llength $owner_residual] \
        owner_activation_primitives [llength $owner_activation] \
        owner_zero_point_primitives [llength $owner_zero] \
        owner_weight_primitives [llength $owner_weight] \
        localized_activation_primitives [llength $localized_activation] \
        localized_zero_point_primitives [llength $localized_zero] \
        localized_weight_primitives [llength $localized_weight] \
        nonzero_logical_crossing_pairs $nonzero_logical_pairs \
        nonzero_window_routed_crossing_pairs $nonzero_window_pairs \
        implementation_commands_run 0 checkpoint_written 0 status PASS] {
    puts $summary_fh "$key=$value"
}
close $summary_fh

close_project
