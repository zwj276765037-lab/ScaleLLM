# Read-only diagnosis for parent FIFO occupancy FFs after placement.  This
# script does not run implementation commands or write a checkpoint.

if {$argc != 2} {
    error "usage: diagnose_mlp_p8_parent_count_replicas.tcl DCP OUT_DIR"
}

set dcp [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
file mkdir $out

proc p8_count_cells_of_module {module_name} {
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "ORIG_REF_NAME == $module_name || REF_NAME == $module_name"]]
}

proc p8_count_named_ff {root pattern} {
    set root_name [get_property NAME $root]
    return [lsort -dictionary -unique [get_cells -quiet -hierarchical \
        -filter "NAME =~ ${root_name}/${pattern} && REF_NAME =~ FD*"]]
}

proc p8_count_object_names {objects} {
    set names {}
    foreach object $objects {
        lappend names [get_property NAME $object]
    }
    return [lsort -dictionary -unique $names]
}

proc p8_count_property_or_na {object property} {
    if {[lsearch -exact [list_property $object] $property] < 0} {
        return NA
    }
    set value [get_property $property $object]
    if {$value eq ""} {
        return EMPTY
    }
    return $value
}

proc p8_count_pin_connectivity {handle cell ref_pin_name} {
    set pins [get_pins -quiet -of_objects $cell \
        -filter "REF_PIN_NAME == $ref_pin_name"]
    puts $handle "pin_${ref_pin_name}_count=[llength $pins]"
    foreach pin $pins {
        set nets [get_nets -quiet -of_objects $pin]
        puts $handle "pin_${ref_pin_name}_name=[get_property NAME $pin]"
        puts $handle "pin_${ref_pin_name}_nets=[join [p8_count_object_names $nets] ,]"
        foreach net $nets {
            set drivers [get_pins -quiet -of_objects $net \
                -filter {DIRECTION == OUT}]
            set loads [get_pins -quiet -of_objects $net \
                -filter {DIRECTION == IN}]
            puts $handle "pin_${ref_pin_name}_net=[get_property NAME $net] driver_count=[llength $drivers] load_count=[llength $loads] drivers=[join [p8_count_object_names $drivers] ,]"
        }
    }
}

open_checkpoint $dcp

set shared [p8_count_cells_of_module hap_mlp_shared_dual_slice16x12_s44_s46]
if {[llength $shared] != 1} {
    error "unexpected P8 shared hierarchy count: [llength $shared]"
}
set shared_root [lindex $shared 0]
set parent_count [p8_count_named_ff $shared_root parent_count_r_reg*]

set report_path [file join $out p8_parent_count_replicas.txt]
set report [open $report_path w]
puts $report "status=P8_PARENT_COUNT_REPLICA_DIAGNOSIS"
puts $report "tool=[version -short]"
puts $report "input_dcp=$dcp"
puts $report "shared_root=[get_property NAME $shared_root]"
puts $report "parent_count_ff=[llength $parent_count]"

set selected_properties {}
foreach cell $parent_count {
    foreach property [list_property $cell] {
        if {[regexp -nocase {(^|_)(orig|replic|equiv|ref|loc|bel|primitive|clock|init|dont_touch|hier)} $property]} {
            lappend selected_properties $property
        }
    }
}
set selected_properties [lsort -dictionary -unique $selected_properties]
puts $report "selected_properties=[join $selected_properties ,]"

set index 0
foreach cell $parent_count {
    puts $report "BEGIN_CELL=$index"
    puts $report "name=[get_property NAME $cell]"
    foreach property $selected_properties {
        puts $report "property.${property}=[p8_count_property_or_na $cell $property]"
    }
    foreach ref_pin_name {D Q C CE R S CLR PRE} {
        p8_count_pin_connectivity $report $cell $ref_pin_name
    }
    set d_pins [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
    set d_starts [all_fanin -quiet -flat -startpoints_only -to $d_pins]
    puts $report "d_startpoint_count=[llength $d_starts]"
    puts $report "d_startpoints=[join [p8_count_object_names $d_starts] ,]"
    puts $report "END_CELL=$index"
    incr index
}

close $report
close_design
puts "P8_PARENT_COUNT_DIAG_REPORT=$report_path"
