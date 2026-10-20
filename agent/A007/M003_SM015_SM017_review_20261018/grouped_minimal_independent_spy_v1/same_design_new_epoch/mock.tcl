
set scenario [lindex $argv 0];set report [lindex $argv 1];set library [lindex $argv 2]
set design D0
set cells {};set pinmap {};set props {};set ngroups {};set allnets {}
for {set i 0} {$i<12062} {incr i} {
 set n n$i;lappend allnets $n
 dict set props $n NAME [expr {$i==0?"core_clk":"alias$i"}];dict set props $n CLASS net
}
for {set i 0} {$i<80} {incr i} {
 set c c$i;set s [expr {$i/40}];set o [expr {$i%40}]
 set name [format {inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice[%d].meta_mem_reg_uram_%d} $s $o]
 dict set props $c NAME $name;dict set props $c REF_NAME URAM288
 set p p$i;dict set props $p NAME $name/CLK;dict set pinmap $p n$i
 lappend cells $c
}
dict set props D0 NAME fresh_core;dict set props D0 PART xcu250
set groups [list $allnets]
if {$scenario eq "two"} {
 set groups [list [lrange $allnets 0 39] [lrange $allnets 40 end]]
 # second independent clock group contains the selected boundary alias only in
 # logical tests; standalone exact-clock qualification deliberately rejects it.
}
foreach g $groups {foreach n $g {dict set ngroups $n $g}}
dict set props port NAME core_clk;dict set props port DIRECTION IN
dict set props driver NAME clkbuf/O;dict set props owner NAME clkbuf;dict set props owner REF_NAME BUFG
if {$scenario eq "wrong_clock"} {dict set props n0 NAME wrong_clk;dict set props port NAME wrong_clk}
proc current_design {} {return $::design}
proc get_property {key objects} {
 set result {};foreach object $objects {
  if {$::scenario eq "name_collision" && $object eq "n1" && $key eq "NAME"} {lappend result core_clk} else {lappend result [dict get $::props $object $key]}
 };if {[llength $objects]==1} {return [lindex $result 0]};return $result
}
proc get_cells {args} {
 if {[lsearch -exact $args -hier]>=0} {
  if {$::scenario eq "missing"} {return [lrange $::cells 0 end-1]}
  if {$::scenario eq "duplicate"} {return [lreplace $::cells 79 79 c0]}
  if {$::scenario eq "extra"} {return [concat $::cells c0]}
  if {$::scenario eq "badname"} {dict set ::props c0 NAME {inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slicesXg_slice[0].meta_mem_reg_uram_0}}
  if {$::scenario eq "leading_zero"} {dict set ::props c0 NAME {inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice[0].meta_mem_reg_uram_00}}
  return $::cells
 };return owner
}
proc get_pins {args} {
 if {[lsearch -exact $args -leaf]>=0} {
  if {$::scenario in {dual leaf}} {return driver};return {}
 }
 set i [string range [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]] 1 end];return p$i
}
proc get_nets {args} {
 if {[lsearch -exact $args -quiet]>=0} {error {spy forbids quiet proof query}}
 set pin [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]]
 if {![dict exists $::pinmap $pin]} {error {get_nets must consume an actual pin}}
 if {$::scenario eq "api_error"} {return -code error -errorcode {NATIVE SPY} {native API failed}}
 set n [dict get $::pinmap $pin]
 if {[lsearch -exact $args -top_net_of_hierarchical_group]>=0} {
  if {$::scenario eq "top_missing"} {return {}}
  if {$::scenario eq "top_multiple"} {return {n0 n1}}
  if {$::scenario eq "top_outside"} {return foreign}
  return [lindex [dict get $::ngroups $n] 0]
 }
 if {[lsearch -exact $args -segments]>=0} {
  set g [dict get $::ngroups $n]
  if {$::scenario eq "omit_direct"} {return [lrange $g 1 end]}
  if {$::scenario eq "overlap" && $pin eq "p1"} {return {n0 n1}}
  if {$::scenario eq "overlap"} {return {n0}}
  return $g
 }
 if {$::scenario eq "disconnected" && $pin eq "p79"} {return {}}
 return $n
}
proc get_ports {args} {
 if {[llength [lindex $args end]]!=1} {error {ports query must use actual singleton top}}
 if {$::scenario eq "port_error"} {error {native port failure}}
 if {$::scenario eq "leaf"} {return {}}
 if {$::scenario eq "bad_direction"} {dict set ::props port DIRECTION OUT}
 if {$::scenario eq "wrong_clock"} {dict set ::props n0 NAME wrong_clk;dict set ::props port NAME wrong_clk}
 return port
}
set ::env(M003_GROUPED_CLOCK_LIBRARY_ONLY) 1
source [file join $library read_grouped_clock.tcl]

set old [m003_conn::begin phaseA]
set b [m003_conn::bind $old p0]
m003_conn::source $old [dict get $b group]
m003_conn::finish $old
# Same native design handle/name/part but fresh call after the phase changed.
dict set props n1 NAME phaseB_alias
set newer [m003_conn::begin phaseB]
set b [m003_conn::bind $newer p1]
set g [m003_conn::source $newer [dict get $b group]]
if {"phaseB_alias" ni [dict get $g nets] || "alias1" in [dict get $g nets]} {error {old alias cache survived phase change}}
if {[dict get [m003_conn::stats] segments calls]!=1} {error {fresh phase did not query actual group}}
if {![catch {m003_conn::binding $old p0}]} {error {prior token remained valid}}
m003_conn::finish $newer
puts independent_epoch_cache_reset_PASS
