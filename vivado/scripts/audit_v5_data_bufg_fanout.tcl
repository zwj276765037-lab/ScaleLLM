# Read-only endpoint audit for data nets that Vivado promoted onto BUFGCE.
# Usage: vivado -mode batch -source audit_v5_data_bufg_fanout.tcl \
#          -tclargs <post_place.dcp> <output_directory>

proc write_ranked_array {fp label array_name} {
    upvar 1 $array_name counts
    set ranked {}
    foreach key [array names counts] {
        lappend ranked [list $counts($key) $key]
    }
    set ranked [lsort -integer -decreasing -index 0 $ranked]
    puts $fp "$label top"
    foreach item [lrange $ranked 0 19] {
        puts $fp "  [lindex $item 0]\t[lindex $item 1]"
    }
}

if {$argc != 2} {
    error "usage: audit_v5_data_bufg_fanout.tcl <dcp> <output_directory>"
}

set dcp [file normalize [lindex $argv 0]]
set out_dir [file normalize [lindex $argv 1]]
if {![file exists $dcp]} {
    error "checkpoint does not exist: $dcp"
}
file mkdir $out_dir

open_checkpoint $dcp
set report_path [file join $out_dir data_bufg_endpoint_audit.txt]
set fp [open $report_path w]
puts $fp "checkpoint\t$dcp"
puts $fp "part\t[get_property PART [current_design]]"

set bufgs [lsort [get_cells -quiet -hier -filter {REF_NAME == BUFGCE}]]
puts $fp "bufgce_count\t[llength $bufgs]"

foreach bufg $bufgs {
    set out_pin [get_pins -quiet ${bufg}/O]
    set in_pin [get_pins -quiet ${bufg}/I]
    set out_net [get_nets -quiet -of_objects $out_pin]
    set in_net [get_nets -quiet -of_objects $in_pin]
    set loads [get_pins -quiet -leaf -of_objects $out_net \
        -filter {DIRECTION == IN}]

    puts $fp ""
    puts $fp "BUFGCE\t$bufg"
    puts $fp "input_net\t$in_net"
    puts $fp "output_net\t$out_net"
    puts $fp "direct_leaf_loads\t[llength $loads]"

    array unset by_ref
    array unset by_pin
    array unset by_parent
    set samples {}
    foreach pin $loads {
        set cell [lindex [get_cells -quiet -of_objects $pin] 0]
        if {$cell eq ""} {
            continue
        }
        set ref [get_property REF_NAME $cell]
        set ref_pin [get_property REF_PIN_NAME $pin]
        if {$ref eq ""} { set ref "<none>" }
        if {$ref_pin eq ""} { set ref_pin "<none>" }
        if {![info exists by_ref($ref)]} { set by_ref($ref) 0 }
        if {![info exists by_pin($ref_pin)]} { set by_pin($ref_pin) 0 }
        incr by_ref($ref)
        incr by_pin($ref_pin)

        set cname [get_property NAME $cell]
        set fields [split $cname /]
        set prefix [join [lrange $fields 0 6] /]
        if {![info exists by_parent($prefix)]} { set by_parent($prefix) 0 }
        incr by_parent($prefix)
        if {[llength $samples] < 12} {
            lappend samples [get_property NAME $pin]
        }
    }

    write_ranked_array $fp by_ref by_ref
    write_ranked_array $fp by_pin by_pin
    write_ranked_array $fp by_parent by_parent
    puts $fp "sample_load_pins"
    foreach sample $samples {
        puts $fp "  $sample"
    }
}

close $fp
close_design
puts "DATA_BUFG_AUDIT_PASS $report_path"
