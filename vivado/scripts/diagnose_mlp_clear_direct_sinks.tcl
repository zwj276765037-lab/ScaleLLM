set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set output_path [file normalize $::env(HAP_OUTPUT_PATH)]

proc cells_of_module {module_name} {
    return [get_cells -quiet -hierarchical -filter \
        "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]
}

proc cells_below_roots {roots candidates} {
    set result {}
    foreach cell $candidates {
        set cell_name [get_property NAME $cell]
        foreach root $roots {
            if {[string match "[get_property NAME $root]/*" $cell_name]} {
                lappend result $cell
                break
            }
        }
    }
    return [lsort -dictionary -unique $result]
}

open_checkpoint $input_dcp
set branches [lsort -dictionary \
    [cells_of_module hap_mlp_shared_local_slice8x12_s44_s46]]
set central [get_cells -quiet -hierarchical -filter {
    NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
set q [get_pins -quiet -of_objects $central -filter {REF_PIN_NAME == Q}]
set nets [lsort -dictionary -unique [get_nets -quiet -of_objects $q]]
set sink_pins [lsort -dictionary -unique [get_pins -quiet -leaf \
    -of_objects $nets -filter {DIRECTION == IN}]]
set sink_cells [lsort -dictionary -unique \
    [get_cells -quiet -of_objects $sink_pins]]
set branch_sink_cells [cells_below_roots $branches $sink_cells]
set clear_cells [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    NAME =~ */clear_local_r_reg* && REF_NAME =~ FD*}]]

set fp [open $output_path w]
puts $fp "input_dcp=$input_dcp"
puts $fp "branch_count=[llength $branches]"
puts $fp "central_count=[llength $central]"
puts $fp "central_q_count=[llength $q]"
puts $fp "central_net_count=[llength $nets]"
puts $fp "direct_sink_pin_count=[llength $sink_pins]"
puts $fp "direct_sink_cell_count=[llength $sink_cells]"
puts $fp "direct_branch_sink_cell_count=[llength $branch_sink_cells]"
puts $fp "clear_cell_count=[llength $clear_cells]"
puts $fp "direct_branch_sinks_equal_clear=[expr {$branch_sink_cells eq $clear_cells}]"
set index 0
foreach pin $sink_pins {
    set cell [get_cells -quiet -of_objects $pin]
    puts $fp "sink${index}_pin=[get_property NAME $pin]"
    puts $fp "sink${index}_ref_pin=[get_property REF_PIN_NAME $pin]"
    puts $fp "sink${index}_cell=[get_property NAME $cell]"
    puts $fp "sink${index}_ref=[get_property REF_NAME $cell]"
    incr index
}
puts $fp "implementation_commands_run=0"
puts $fp "checkpoint_written=0"
close $fp
close_design
