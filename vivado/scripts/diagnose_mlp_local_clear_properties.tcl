set input_dcp [file normalize $::env(HAP_INPUT_DCP)]
set output_path [file normalize $::env(HAP_OUTPUT_PATH)]

proc property_or_empty {object property_name} {
    if {[catch {get_property $property_name $object} value]} {
        return <UNAVAILABLE>
    }
    if {$value eq ""} {return <EMPTY>}
    return $value
}

proc property_is_true {object property_name} {
    set value [string tolower [property_or_empty $object $property_name]]
    return [expr {$value eq "1" || $value eq "true" || $value eq "yes"}]
}

open_checkpoint $input_dcp
set branches [lsort -dictionary [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_mlp_shared_local_slice8x12_s43_s45 ||
    REF_NAME == hap_mlp_shared_local_slice8x12_s43_s45
}]]
set clear_cells {}
set records {}
set protected_count 0
foreach branch $branches {
    set branch_name [get_property NAME $branch]
    set cells [lsort -dictionary [get_cells -quiet -hierarchical -filter \
        "NAME =~ ${branch_name}/clear_local_r_reg* && REF_NAME =~ FD*"]]
    foreach cell $cells {
        if {[property_is_true $cell DONT_TOUCH]} {incr protected_count}
        lappend clear_cells $cell
        lappend records [list \
            branch $branch_name \
            cell [get_property NAME $cell] \
            ref_name [get_property REF_NAME $cell] \
            orig_ref_name [property_or_empty $cell ORIG_REF_NAME] \
            dont_touch [property_or_empty $cell DONT_TOUCH] \
            keep [property_or_empty $cell KEEP] \
            shreg_extract [property_or_empty $cell SHREG_EXTRACT]]
    }
}
set clear_cells [lsort -dictionary -unique $clear_cells]

set central [get_cells -quiet -hierarchical -filter {
    NAME =~ */maintenance_soft_clear_pulse_r_reg && REF_NAME =~ FD*}]
set central_clear_endpoints 0
if {[llength $central] == 1} {
    set q [get_pins -quiet -of_objects $central -filter {REF_PIN_NAME == Q}]
    if {[llength $q] == 1} {
        set endpoints [get_cells -quiet -of_objects \
            [all_fanout -quiet -flat -endpoints_only -from $q]]
        foreach clear_cell $clear_cells {
            if {[lsearch -exact $endpoints $clear_cell] >= 0} {
                incr central_clear_endpoints
            }
        }
    }
}

set status [expr {[llength $branches] == 2 &&
    [llength $clear_cells] == 2 && [llength $central] == 1 &&
    $central_clear_endpoints == 2 ? "PASS" : "FAIL"}]
set fp [open $output_path w]
puts $fp "input_dcp=$input_dcp"
puts $fp "checkpoint_design=[current_design]"
puts $fp "branch_count=[llength $branches]"
puts $fp "clear_ff_count=[llength $clear_cells]"
puts $fp "dont_touch_true_count=$protected_count"
puts $fp "central_clear_ff_count=[llength $central]"
puts $fp "central_clear_endpoints=$central_clear_endpoints"
set index 0
foreach record $records {
    foreach {key value} $record {
        puts $fp "branch${index}_${key}=$value"
    }
    incr index
}
puts $fp "implementation_commands_run=0"
puts $fp "checkpoint_written=0"
puts $fp "status=$status"
close $fp
close_design
