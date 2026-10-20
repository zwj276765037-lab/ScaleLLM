set fh [open [lindex $argv 0] rb]
set ::scalar [read $fh]
close $fh
proc get_property {args} {return $::scalar}
proc row {args} {error "unexpected scalar fallback"}
proc vals {objects prop {optional 0}} {
    if {![llength $objects]} {return [list]}
    set v [get_property -quiet $prop $objects]
    if {[llength $v] != [llength $objects]} {
        set v [list]
        foreach o $objects {lappend v [get_property -quiet $prop $o]}
        row $::align [list $prop [llength $objects] SCALAR_ALIGNMENT_FALLBACK]
    }
    if {[llength $v] != [llength $objects]} {error "native property alignment: $prop"}
    if {!$optional} {foreach x $v {if {$x eq ""} {error "required property empty: $prop"}}}
    return $v
}

set values [vals [list $::scalar] NAME]
set observed [lindex $values 0]
puts [list object_count 1 scalar_length [string length $::scalar] list_length [llength $::scalar] parsed_length [string length $observed] literal_equal [expr {$::scalar eq $observed}]]
if {$::scalar eq $observed} {error "expected saved scalar corruption not reproduced"}
set wrapped [list $::scalar]
if {[lindex $wrapped 0] ne $::scalar || [llength $wrapped]!=1} {error "byte-preserving list wrapping failed"}
puts [list byte_preserving_wrap 1]
