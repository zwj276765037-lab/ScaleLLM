# Bounded read-only fresh-core CLR provenance; no synthesis/apply/write_checkpoint.
source [file join [file dirname [file normalize [info script]]] frozen_shared_connectivity.tcl]
namespace eval m003_reset {variable h {};variable object_groups {};variable groups {};variable group_serial 0;variable seen_nodes {};variable visiting {};variable pins 0;variable root {};variable core {inst/u_core/u_compute/u_attention}}
proc m003_reset::emit {d} {variable h;set fields {};dict for {k v} $d {lappend fields "[m003_conn::quote $k]:[m003_conn::quote $v]"};puts $h "\{[join $fields ,]\}";flush $h}
proc m003_reset::prop {obj name} {if {$name ni [list_property $obj]} {return NOT_SUPPORTED};return [get_property $name $obj]}
proc m003_reset::group {pin} {
 variable object_groups;variable groups;variable group_serial
 set direct [m003_conn::bounded_objects [get_nets -of_objects $pin] direct_net]
 set n [m003_conn::one $direct required_direct_net]
 if {[dict exists $object_groups $n]} {return [dict get $object_groups $n]}
 set ns [m003_conn::bounded_objects [get_nets -segments -of_objects $pin] reset_segments]
 set names [m003_conn::names_of $ns]
 if {$n ni $ns || ![llength $ns] || [llength $ns]!=[llength [lsort -unique $ns]] || [llength $names]!=[llength $ns] || {} in $names || [llength $names]!=[llength [lsort -unique $names]]} {error {M003 invalid reset group actual membership or NAME vector}}
 foreach obj $ns {if {[string tolower [get_property CLASS $obj]] ne "net" || [dict exists $object_groups $obj]} {error {M003 invalid or overlapping reset group}}}
 set gid R[incr group_serial];foreach obj $ns {dict set object_groups $obj $gid}
 set drivers [m003_conn::bounded_objects [get_pins -leaf -of_objects $ns -filter {DIRECTION == OUT}] reset_drivers]
 if {[llength $drivers]>1} {error {M003 multiple reset drivers}}
 set ports {};set top [m003_conn::one [get_nets -top_net_of_hierarchical_group -segments -of_objects $pin] canonical_top]
 if {$top ni $ns} {error {M003 reset canonical top outside actual group}}
 if {![llength $drivers]} {set ports [m003_conn::bounded_objects [get_ports -of_objects $top] reset_primary_ports]}
 if {[llength $drivers]+[llength $ports]!=1} {error {M003 reset source missing or multiple}}
 set dirs {};foreach source [concat $drivers $ports] {lappend dirs [get_property DIRECTION $source]}
 if {([llength $drivers] && $dirs ne {OUT}) || ([llength $ports] && $dirs ne {IN})} {error {M003 reset source direction mismatch}}
 set row [dict create gid $gid objects $ns names $names drivers $drivers ports $ports]
 dict set groups $gid $row
 emit [dict create kind group id $gid actual_segment_count [llength $ns] nets $names direct_net [get_property NAME $n] leaf_drivers [m003_conn::names_of $drivers] primary_ports [m003_conn::names_of $ports] source_directions $dirs]
 return $gid
}
proc m003_reset::walk {gid depth} {
 variable groups;variable seen_nodes;variable visiting;variable pins;variable root
 if {$depth>4} {error {M003 reset provenance depth exceeds4}}
 if {[dict exists $visiting $gid]} {error {M003 reset combinational cycle}}
 if {$gid eq $root} {return}
 set g [dict get $groups $gid];set drivers [dict get $g drivers]
 if {![llength $drivers]} {error {M003 nonselected primary source in reset cone}}
 set driver [lindex $drivers 0];set cell [m003_conn::one [get_cells -of_objects $driver] reset_driver_owner];set name [get_property NAME $cell]
 if {[dict exists $seen_nodes $name]} {return}
 if {[dict size $seen_nodes]>=16} {error {M003 reset provenance nodes exceeds16}}
 dict set visiting $gid 1;dict set seen_nodes $name 1
 set ref [get_property REF_NAME $cell];set init [prop $cell INIT]
 emit [dict create kind node cell $name REF_NAME $ref INIT $init output_pin [get_property NAME $driver] output_direction [get_property DIRECTION $driver] output_group $gid]
 if {$ref ni {GND VCC}} {
  if {![regexp {^LUT[1-6]$} $ref]} {error "M003 unsupported reset source primitive: $ref"}
  set inputs [m003_conn::bounded_objects [get_pins -of_objects $cell -filter {DIRECTION == IN}] reset_inputs]
  if {[llength $inputs]!=[string index $ref end]} {error {M003 reset LUT input count mismatch}}
  foreach pin $inputs {
   if {[get_property DIRECTION $pin] ne "IN"} {error {M003 reset LUT input direction mismatch}}
   incr pins;if {$pins>64} {error {M003 reset provenance input pins exceeds64}}
   set ng [group $pin]
   emit [dict create kind input cell $name pin [get_property REF_PIN_NAME $pin] actual_pin [get_property NAME $pin] direction [get_property DIRECTION $pin] group $ng]
   walk $ng [expr {$depth+1}]
  }
 }
 dict unset visiting $gid
}
proc m003_reset::run {report} {
 variable h;variable core;variable root
 set h [open [file join $report reset_provenance.jsonl] {WRONLY CREAT EXCL}]
 set port [m003_conn::one [get_ports core_rst_n] independent_reset_port]
 if {[get_property NAME $port] ne "core_rst_n" || [get_property DIRECTION $port] ne "IN"} {error {M003 independent reset port mismatch}}
 set root [group $port];emit [dict create kind root group $root port core_rst_n direction IN]
 set selected {};set seen {}
 foreach family {core helper} {
  if {$family eq "core"} {set pattern ${core}/meta_read_addr_r_reg*} else {set pattern ${core}/u_meta/g_m003_width_slices.g_slice*}
  set cells [m003_conn::bounded_objects [get_cells -hier -filter [format {IS_PRIMITIVE == 1 && REF_NAME =~ FD* && NAME =~ "%s"} $pattern]] selected_address_FF]
  if {[llength $cells]>128} {error {M003 address selector exceeds128}}
  foreach cell $cells {
   set name [get_property NAME $cell];set slice -1
   if {$family eq "core"} {
    if {![regexp {^inst/u_core/u_compute/u_attention/meta_read_addr_r_reg\[([0-9]+)\]$} $name -> bit]} {continue}
   } else {
    if {![regexp {^inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices\.g_slice\[([01])\]\.u_addr/address_r_reg\[([0-9]+)\]$} $name -> slice bit]} {continue}
   }
   if {$bit>16 || [dict exists $seen $family,$slice,$bit]} {error {M003 unexpected or duplicate address identity}}
   dict set seen $family,$slice,$bit 1;lappend selected [list $family $slice $bit $cell]
  }
 }
 if {[llength $selected]!=51} {error {M003 expected exact17core+34helper reset endpoints}}
 for {set b 0} {$b<17} {incr b} {foreach pair {core,-1 helper,0 helper,1} {if {![dict exists $seen $pair,$b]} {error {M003 missing reset address endpoint}}}}
 foreach item $selected {
  lassign $item family slice bit cell
  set pin [m003_conn::one [get_pins -of_objects $cell -filter {REF_PIN_NAME == CLR}] actual_CLR_pin]
  if {[get_property DIRECTION $pin] ne "IN"} {error {M003 CLR endpoint is not IN}}
  set gid [group $pin]
  emit [dict create kind endpoint family $family slice $slice bit $bit cell [get_property NAME $cell] REF_NAME [get_property REF_NAME $cell] INIT [prop $cell INIT] IS_CLR_INVERTED [prop $cell IS_CLR_INVERTED] pin_IS_INVERTED [prop $pin IS_INVERTED] CLR_pin [get_property NAME $pin] group $gid]
  walk $gid 0
 }
 variable seen_nodes;variable pins;variable group_serial
 emit [dict create kind complete endpoints 51 nodes [dict size $seen_nodes] input_pins $pins groups $group_serial]
 close $h;set h {}
}
if {![info exists ::env(M003_RESET_LIBRARY_ONLY)]} {
 set_param general.maxThreads 8
 open_checkpoint [lindex $argv 0]
 if {[catch {m003_reset::run $::env(HAP_REPORT_DIR)} message options]} {
  if {$m003_reset::h ne {}} {close $m003_reset::h}
  set f [open [file join $::env(HAP_REPORT_DIR) diagnostic_error_info.txt] {WRONLY CREAT EXCL}];puts $f [dict get $options -errorinfo];close $f
  return -options $options $message
 }
 close_design
 puts M003_BOUNDED_RESET_PROVENANCE_COMPLETED
}
