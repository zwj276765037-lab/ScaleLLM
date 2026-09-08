set input_dcp [file normalize $::env(HAP_INPUT_DCP)]

if {![file exists $input_dcp]} {error "missing input DCP $input_dcp"}
if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 is required, got [version -short]"
}

open_checkpoint $input_dcp

set all_stage [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/*group_stage* && IS_PRIMITIVE &&
    PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND && REF_NAME != VCC}]]
puts "ALL_STAGE_PRIMITIVES=[llength $all_stage]"

foreach pattern {
        u_dut/group_stage_act_u8_region_r_reg*
        u_dut/group_stage_act_zero_point_region_r_reg*
        u_dut/group_stage_weight_s8_r_reg*
        u_dut/group_stage_weight_s8_r*} {
    set cells [lsort -dictionary [get_cells -quiet -hierarchical -filter \
        "NAME =~ $pattern && IS_PRIMITIVE && \
         PRIMITIVE_LEVEL != INTERNAL && REF_NAME != GND && REF_NAME != VCC"]]
    puts "PATTERN=$pattern COUNT=[llength $cells]"
    foreach cell [concat [lrange $cells 0 7] [lrange $cells end-7 end]] {
        puts "CELL=[get_property NAME $cell] REF=[get_property REF_NAME $cell]"
    }
}

array set refs {}
foreach cell $all_stage {
    set ref [get_property REF_NAME $cell]
    if {![info exists refs($ref)]} {set refs($ref) 0}
    incr refs($ref)
}
foreach ref [lsort -dictionary [array names refs]] {
    puts "ALL_STAGE_REF=$ref COUNT=$refs($ref)"
}
set placed_sample [lindex [get_cells -quiet -hierarchical -filter {
    NAME =~ u_dut/u_array/u_center12/u_region3_cols12_13/* &&
    IS_PRIMITIVE && PRIMITIVE_LEVEL != INTERNAL && REF_NAME == FDRE}] 0]
if {[llength $placed_sample] == 1} {
    puts "PLACED_SAMPLE=[get_property NAME $placed_sample]"
    puts "PLACED_SAMPLE_PROPERTIES=[lsort -dictionary \
        [list_property $placed_sample]]"
    foreach property {LOC BEL SITE TILE SLR_INDEX CLOCK_REGION} {
        if {![catch {get_property $property $placed_sample} value]} {
            puts "PLACED_SAMPLE_${property}=$value"
        }
    }
    set sample_sites [get_sites -quiet -of_objects $placed_sample]
    set sample_bels [get_bels -quiet -of_objects $placed_sample]
    set sample_tiles [get_tiles -quiet -of_objects $sample_sites]
    puts "PLACED_SAMPLE_SITES=[get_property NAME $sample_sites]"
    puts "PLACED_SAMPLE_BELS=[get_property NAME $sample_bels]"
    puts "PLACED_SAMPLE_TILES=[get_property NAME $sample_tiles]"
}

close_project
