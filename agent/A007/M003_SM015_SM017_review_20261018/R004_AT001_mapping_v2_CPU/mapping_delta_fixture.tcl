
set out [lindex $argv 0]; set mode [lindex $argv 1]; set count [lindex $argv 2]
proc chan {name header} {set f [open [file join $::out $name] w]; puts $f [join $header "\t"];return $f}
proc row {f data} {puts $f [join $data "\t"]}
proc mark args {}
proc vals {objects property args} {return $objects}
proc get_property {property object} {return $object}
proc get_slrs args {return {}}
proc get_clock_regions args {return {}}
proc get_sites args {return {}}
proc list_property args {return {}}
proc get_nodes args {set out {};for {set i 0} {$i<$::count} {incr i} {lappend out [format N%05d $i]};return $out}
proc get_tiles args {if {[llength $args]==1 || $::mode eq "missing_tile" || $::mode eq "empty_seed"} {return {}};return T}
source {/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E011_m003_joint_routability_implementation/experiment_source/failed_route_localization_v2/device_and_routes.tcl}
set ::segments [dict create can SEG]
set ::tileSLR [dict create];set ::tileCR [dict create]
if {$mode eq "mapped"} {dict set ::tileSLR T SLR1;dict set ::tileCR T X1Y1}
capture_routes {can}
set ::hotspot_nodes [list [list T N]]
if {$mode eq "empty_seed" || $mode eq "missing_tile"} {device_inventory}
