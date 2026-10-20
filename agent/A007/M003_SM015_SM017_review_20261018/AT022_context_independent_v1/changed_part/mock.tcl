
set raw_name {fresh core[0]};set design_objects {H_other H_actual}
set props [dict create H_other [dict create NAME other PART part0] H_actual [dict create NAME {fresh core[0]} PART part0] H_new [dict create NAME {fresh core[0]} PART part0]]
set fault {}
proc current_design {} {if {$::fault eq "current_api"} {error {original current API error}};return $::raw_name}
proc get_designs {} {if {$::fault eq "get_api"} {error {original get API error}};return $::design_objects}
proc get_property {k obj} {
 if {$obj eq $::raw_name} {error {get_property forbids raw current_design NAME}}
 if {$::fault eq "part_api" && $k eq "PART"} {error {original PART API error}}
 return [dict get $::props $obj $k]
}
source [lindex $argv 0]
set code [catch {
set t [m003_conn::begin phase0];dict set props H_actual PART part1;m003_conn::check $t
} msg opts]
if {$code} {puts stderr [dict get $opts -errorinfo];exit 1}
puts {INDEPENDENT_CONTEXT_PASS}
