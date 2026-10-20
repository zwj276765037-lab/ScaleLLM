source [file join [file dirname [file normalize [info script]]] shared_native_connectivity.tcl]
namespace eval m003_clock_fast {variable scope {inst/u_core/u_compute/u_attention/u_meta/}}
proc m003_clock_fast::run {report} {
 variable scope
 set token [m003_conn::begin clock_diagnostic [file join $report api_trace.jsonl] [file join $report clock_groups.jsonl.partial]]
 set h [open [file join $report clock_endpoints.jsonl.partial] {WRONLY CREAT EXCL}]
 set cells [get_cells -hier -filter [format {IS_PRIMITIVE == 1 && REF_NAME == URAM288 && NAME =~ "%s*"} $scope]]
 if {[llength $cells]!=80} {error {M003 expected exact80 URAM clock endpoints}}
 set seen {};set count 0
 foreach cell $cells {
  set name [get_property NAME $cell]
  if {![regexp {^inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices\.g_slice\[([01])\]\.meta_mem_reg_uram_(0|[1-9][0-9]*)$} $name -> slice ordinal] || $ordinal>=40 || [dict exists $seen $slice,$ordinal]} {error "M003 bad/duplicate URAM clock identity: $name"}
  dict set seen $slice,$ordinal 1
  set pin [m003_conn::one [get_pins -of_objects $cell -filter {REF_PIN_NAME == CLK}] "$name/CLK"]
  if {[get_property NAME $pin] ne "$name/CLK"} {error {M003 native clock pin identity mismatch}}
  set b [m003_conn::bind $token $pin]
  puts $h "\{\"cell\":[m003_conn::quote $name],\"slice\":$slice,\"ordinal\":$ordinal,\"CLK_pin\":[m003_conn::quote [dict get $b pin]],\"group\":[m003_conn::quote [dict get $b group]],\"direct_nets\":[m003_conn::array [dict get $b direct_nets]]\}";incr count
 }
 for {set slice 0} {$slice<2} {incr slice} {for {set ordinal 0} {$ordinal<40} {incr ordinal} {if {![dict exists $seen $slice,$ordinal]} {error {M003 missing clock endpoint}}}}
 close $h
 m003_conn::event endpoint_inventory_complete [dict create endpoints $count]
 foreach gid [m003_conn::group_ids $token] {
  set g [m003_conn::source $token $gid 1]
  if {"core_clk" ni [dict get $g nets]} {error {M003 clock differs from selected core_clk boundary}}
  set drivers [dict get $g leaf_drivers];set ports [dict get $g primary_ports];set dirs [dict get $g primary_port_directions]
  if {!(([llength $drivers]==1 && ![llength $ports] && ![llength $dirs]) || (![llength $drivers] && [llength $ports]==1 && $dirs eq {IN}))} {error "M003 unresolved/multiple clock source in $gid"}
 }
 set stats [m003_conn::finish $token]
 set h [open [file join $report api_counts.json] {WRONLY CREAT EXCL}]
 set fields {}
 dict for {kind values} [dict get $stats counters] {
  set items {};dict for {k v} $values {lappend items "[m003_conn::quote $k]:$v"}
  lappend fields "[m003_conn::quote $kind]:\{[join $items ,]\}"
 }
 puts $h "\{[join $fields ,]\}";close $h
 foreach stem {clock_groups clock_endpoints} {file rename [file join $report $stem.jsonl.partial] [file join $report $stem.jsonl]}
 set h [open [file join $report diagnostic_complete.json] {WRONLY CREAT EXCL}]
 puts $h "\{\"schema\":\"M003_grouped_clock_v1\",\"execution\":\"completed\",\"endpoints\":80,\"groups\":[dict get $stats groups],\"new_synthesis\":false,\"constraint_apply\":false,\"G4\":false\}";close $h
}
if {![info exists ::env(M003_GROUPED_CLOCK_LIBRARY_ONLY)]} {
 set_param general.maxThreads 8
 open_checkpoint [lindex $argv 0]
 if {[catch {m003_clock_fast::run $::env(HAP_REPORT_DIR)} message options]} {
  m003_conn::abort
  set h [open [file join $::env(HAP_REPORT_DIR) diagnostic_error_info.txt] {WRONLY CREAT EXCL}];puts $h [dict get $options -errorinfo];close $h
  return -options $options $message
 }
 close_design
 puts M003_GROUPED_CLOCK_DIAGNOSTIC_COMPLETED;flush stdout
}
