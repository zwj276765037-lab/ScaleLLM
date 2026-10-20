
source [lindex $argv 0]
set actual {};for {set i 0} {$i<12062} {incr i} {lappend actual handle_$i}
set declared 12062;set iterations 0
rename llength native_llength
proc llength {value} {if {$value eq "OPAQUE_NATIVE_COLLECTION"} {return $::declared};return [native_llength $value]}
rename foreach native_foreach
proc foreach {args} {
 if {[native_llength $args]==3 && [lindex $args 1] eq "OPAQUE_NATIVE_COLLECTION"} {incr ::iterations;set args [lreplace $args 1 1 $::actual]}
 set code [catch {uplevel 1 [list native_foreach {*}$args]} value options]
 return -options $options $value
}
set code [catch {
set actual [lrange $actual 0 499];m003_conn::bounded_objects OPAQUE_NATIVE_COLLECTION segments
} message options]
if {$code} {puts stderr [dict get $options -errorinfo];exit 1}
puts INDEPENDENT_BOUND_PASS
