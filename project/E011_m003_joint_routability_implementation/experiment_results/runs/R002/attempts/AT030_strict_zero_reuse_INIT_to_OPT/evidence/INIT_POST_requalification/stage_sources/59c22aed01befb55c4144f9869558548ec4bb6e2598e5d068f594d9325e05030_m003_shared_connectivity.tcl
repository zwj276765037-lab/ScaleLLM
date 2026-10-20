# One immutable design/phase/call only. All net membership starts at native
# direct-net objects, never a guessed name or a historical alias hash.
namespace eval m003_conn {variable serial 0;variable active {};variable groups {};variable objects {};variable names {};variable bindings {};variable counters {};variable trace {};variable group_channel {};variable member_channel {}}
proc m003_conn::quote {s} {return \"[string map [list \\ \\\\ \" \\\" \n \\n \r \\r \t \\t] $s]\"}
proc m003_conn::array {values} {set out {};foreach v $values {lappend out [quote $v]};return \[[join $out ,]\]}
proc m003_conn::one {values label} {if {[llength $values]!=1} {error "M003 connection singleton required: $label"};return [lindex $values 0]}
# Native get_* collections stringify with a default display limit of500.
# Bound first and iterate natively, retaining each actual object in a plain list.
proc m003_conn::bounded_objects {collection label} {
 set count [llength $collection]
 if {$count>131072} {error "M003 $label collection exceeds131072: $count"}
 set ordinary [list]
 foreach object $collection {lappend ordinary $object}
 if {[llength $ordinary]!=$count} {error "M003 $label native iteration count differs"}
 return $ordinary
}
proc m003_conn::names_of {objects} {if {![llength $objects]} {return {}};return [get_property NAME $objects]}
proc m003_conn::event {name fields} {
 variable trace
 if {$trace eq {}} {return}
 set values [list "\"event\":[quote $name]" "\"clock_ms\":[clock milliseconds]"]
 dict for {k v} $fields {lappend values "[quote $k]:[quote $v]"}
 puts $trace "\{[join $values ,]\}";flush $trace
}
proc m003_conn::api {kind count command} {
 variable counters
 set start [clock milliseconds]
 if {![dict exists $counters $kind]} {dict set counters $kind [dict create calls 0 input_objects 0 total_ms 0 first_start_ms $start last_end_ms $start]}
 set row [dict get $counters $kind];dict incr row calls;dict incr row input_objects $count;dict set counters $kind $row
 set verbose [expr {$kind in {segments canonical drivers ports identity}}]
 if {$verbose} {event api_begin [dict create api $kind input_objects $count]}
 set code [catch {uplevel #0 $command} value options]
 set end [clock milliseconds]
 set row [dict get $counters $kind];dict incr row total_ms [expr {$end-$start}];dict set row last_end_ms $end;dict set counters $kind $row
 if {$verbose} {event api_end [dict create api $kind input_objects $count elapsed_ms [expr {$end-$start}] return_code $code]}
 return -options $options $value
}
# current_design returns a NAME, get_designs returns property-capable objects.
proc m003_conn::context {} {
 set name [current_design]
 if {$name eq {}} {error {M003 current design name is empty}}
 set selected {}
 foreach object [get_designs] {
  if {[get_property NAME $object] eq $name} {lappend selected $object}
 }
 set design [one $selected actual_current_design_object]
 return [dict create design $design design_name $name part [get_property PART $design]]
}
proc m003_conn::begin {phase {trace_path {}} {group_path {}} {member_path {}}} {
 variable serial;variable active;variable groups;variable objects;variable names;variable bindings;variable counters;variable trace;variable group_channel;variable member_channel
 if {$active ne {}} {error {M003 connection call already active; invalidate before another design/phase}}
 incr serial;set context [context]
 set active [dict merge [dict create token $serial phase $phase] $context]
 set groups {};set objects {};set names {};set bindings {};set counters {};set trace {};set group_channel {};set member_channel {}
 foreach {path var} [list $trace_path trace $group_path group_channel $member_path member_channel] {
  if {$path ne {}} {set $var [open $path {WRONLY CREAT EXCL}]}
 }
 event call_begin [dict create phase $phase design [dict get $context design] token $serial]
 return $serial
}
proc m003_conn::check {token} {
 variable active
 if {$active eq {} || $token ne [dict get $active token]} {error {M003 expired connectivity call token}}
 set current [context]
 foreach key {design design_name part} {if {[dict get $current $key] ne [dict get $active $key]} {error {M003 connectivity design context changed}}}
}
proc m003_conn::bind {token pin {connected 1}} {
 check $token
 variable groups;variable objects;variable names;variable bindings;variable member_channel
 set pname [get_property NAME $pin]
 if {[dict exists $bindings $pname]} {error "M003 duplicate endpoint: $pname"}
 set direct [api direct_net 1 [list get_nets -of_objects $pin]]
 if {![llength $direct]} {
  if {$connected} {error "M003 disconnected required endpoint: $pname"}
  set b [dict create pin $pname group {} direct_objects {} direct_nets {}]
 } else {
  one $direct "direct net of $pname"
  set object [lindex $direct 0];set name [get_property NAME $object]
  if {[string tolower [get_property CLASS $object]] ne "net"} {error {M003 direct object is not a net}}
  if {[dict exists $names $name] && [dict get $names $name] ne $object} {error {M003 distinct native net objects have same NAME}}
  if {[dict exists $objects $object]} {
   set gid [dict get $objects $object]
  } else {
   set native_segments [api segments [llength $direct] [list get_nets -segments -of_objects $pin]]
   set segments [bounded_objects $native_segments net_segments]
   if {![llength $segments]} {
    event membership_failure [dict create pin $pname direct_object $object direct_name $name direct_class [get_property CLASS $object] segment_count 0 reason empty_segments]
    error {M003 expanded segment collection is empty}
   }
   set segment_names [api identity [llength $segments] [list get_property NAME $segments]]
   set classes [api identity [llength $segments] [list get_property CLASS $segments]]
   if {[llength $segment_names]!=[llength $segments] || [llength $classes]!=[llength $segments]} {error {M003 vector net identity size mismatch}}
   set object_set {};foreach seg $segments {dict set object_set $seg 1}
   set object_unique_count [dict size $object_set];set member [dict exists $object_set $object]
   event segment_membership [dict create pin $pname direct_object $object direct_name $name direct_class [get_property CLASS $object] segment_count [llength $segments] object_unique_count $object_unique_count actual_direct_member $member direct_name_match_count [llength [lsearch -all -exact $segment_names $name]] sample_names [lrange $segment_names 0 2]]
   if {$object_unique_count!=[llength $segments]} {error {M003 duplicate actual objects in expanded segments}}
   if {!$member} {error {M003 actual direct net object is absent from expanded segments}}
   set overlap {}
   foreach seg $segments sn $segment_names class $classes {
    if {[string tolower $class] ne "net"} {error {M003 segment object is not a net}}
    if {[dict exists $names $sn] && [dict get $names $sn] ne $seg} {error {M003 segment NAME collision}}
    if {[dict exists $objects $seg]} {lappend overlap [dict get $objects $seg]}
   }
   if {[llength $segment_names]!=[llength [lsort -unique $segment_names]]} {error {M003 segment NAME duplicate}}
   if {[llength $overlap]} {
    set overlap [lsort -unique $overlap]
    if {[llength $overlap]!=1 || [lsort $segments] ne [lsort [dict get $groups [lindex $overlap 0] objects]]} {error {M003 overlapping nonidentical connectivity groups}}
    set gid [lindex $overlap 0]
   } else {
    set gid [format G%06d [dict size $groups]]
    dict set groups $gid [dict create id $gid objects $segments nets $segment_names source_done 0 members {} seed_pin $pin]
   }
   foreach seg $segments sn $segment_names {dict set objects $seg $gid;dict set names $sn $seg}
  }
  set g [dict get $groups $gid]
  if {$object ni [dict get $g objects]} {error {M003 endpoint direct object is not a member}}
  dict lappend g members $pname;dict set groups $gid $g
  set b [dict create pin $pname group $gid direct_objects $direct direct_nets [names_of $direct]]
 }
 dict set bindings $pname $b
 if {$member_channel ne {}} {puts $member_channel [binding_json $b]}
 return $b
}
proc m003_conn::binding_json {b} {return "\{\"pin\":[quote [dict get $b pin]],\"group\":[quote [dict get $b group]],\"direct_nets\":[array [dict get $b direct_nets]]\}"}
proc m003_conn::source {token gid {need_ports 1}} {
 check $token
 variable groups;variable group_channel
 if {![dict exists $groups $gid]} {error {M003 unknown connection group}}
 set g [dict get $groups $gid]
 if {[dict get $g source_done]} {
  if {$need_ports && ![dict get $g ports_queried]} {error {M003 source mode cannot be widened after publication}}
  return $g
 }
 set ns [dict get $g objects]
 set drivers [bounded_objects [api drivers [llength $ns] [list get_pins -leaf -of_objects $ns -filter {DIRECTION == OUT}]] leaf_drivers]
 if {[llength $drivers]>131072 || [llength $drivers]!=[llength [lsort -unique $drivers]]} {error {M003 leaf driver collection exceeds bound or duplicates}}
 set owner_names {};set refs {}
 foreach driver $drivers {
  set owner [one [api driver_owner 1 [list get_cells -of_objects $driver]] actual_driver_owner]
  lappend owner_names [get_property NAME $owner];lappend refs [get_property REF_NAME $owner]
 }
 set ports {};set dirs {};dict set g canonical_top_net {}
 if {$need_ports} {
  set top [api canonical 1 [list get_nets -top_net_of_hierarchical_group -segments -of_objects [dict get $g seed_pin]]]
  one $top canonical_top_net
  if {[lindex $top 0] ni $ns} {error {M003 canonical top object is outside actual group}}
  dict set g canonical_top_net [get_property NAME $top]
  set ports [bounded_objects [api ports 1 [list get_ports -of_objects $top]] primary_ports]
  if {[llength $ports]>131072 || [llength $ports]!=[llength [lsort -unique $ports]]} {error {M003 primary port collection exceeds bound or duplicates}}
  foreach port $ports {lappend dirs [get_property DIRECTION $port]}
 }
 # Keep actual native source objects internally for the independent clock
 # boundary witness; only NAME fields are serialized.
 dict set g leaf_driver_objects $drivers;dict set g primary_port_objects $ports
 dict set g leaf_drivers [names_of $drivers];dict set g driver_cells $owner_names;dict set g driver_refs $refs
 dict set g primary_ports [names_of $ports];dict set g primary_port_directions $dirs;dict set g ports_queried $need_ports;dict set g source_done 1
 dict set groups $gid $g
 if {$group_channel ne {}} {puts $group_channel [group_json $g];flush $group_channel}
 event group_source_complete [dict create group $gid net_count [llength $ns] driver_count [llength $drivers] port_count [llength $ports]]
 return $g
}
# A selected upstream clock net must already be an actual member of the
# current call's clock inventory. Query each group's source only once, then bind
# its actual exclusive leaf output or primary IN port as a distinct witness.
proc m003_conn::bind_source_net {token net} {
 check $token
 variable objects;variable names
 one $net independent_clock_net
 set name [get_property NAME $net]
 if {[string tolower [get_property CLASS $net]] ne "net" || ![dict exists $objects $net] || ![dict exists $names $name] || [dict get $names $name] ne $net} {error {M003 independent clock anchor is outside actual same-call groups}}
 set gid [dict get $objects $net];set g [source $token $gid 1]
 set drivers [dict get $g leaf_driver_objects];set ports [dict get $g primary_port_objects]
 if {[llength $drivers]==1 && ![llength $ports]} {
  set endpoint [lindex $drivers 0]
  if {[get_property DIRECTION $endpoint] ne "OUT"} {error {M003 independent leaf clock source is not OUT}}
 } elseif {![llength $drivers] && [llength $ports]==1 && [dict get $g primary_port_directions] eq {IN}} {
  set endpoint [lindex $ports 0]
 } else {error {M003 independent clock source is not exclusive leaf output or primary IN}}
 set b [bind $token $endpoint]
 if {[dict get $b group] ne $gid} {error {M003 independent clock source changed group}}
 event boundary_clock_source [dict create anchor $name endpoint [dict get $b pin] group $gid]
 return $b
}
proc m003_conn::group_json {g} {
 set fields [list "\"id\":[quote [dict get $g id]]"]
 lappend fields "\"canonical_top_net\":[quote [dict get $g canonical_top_net]]"
 foreach k {nets leaf_drivers driver_cells driver_refs primary_ports primary_port_directions} {lappend fields "[quote $k]:[array [dict get $g $k]]"}
 return "\{[join $fields ,]\}"
}
proc m003_conn::stats {} {variable counters;return $counters}
proc m003_conn::group_ids {token} {check $token;variable groups;return [dict keys $groups]}
proc m003_conn::binding {token pin} {check $token;variable bindings;return [dict get $bindings [get_property NAME $pin]]}
proc m003_conn::finish {token} {
 check $token
 variable groups;variable objects;variable names;variable bindings;variable counters;variable active;variable trace;variable group_channel;variable member_channel
 dict for {gid g} $groups {if {![dict get $g source_done]} {error {M003 group source inventory incomplete}}}
 set result [dict create context $active groups [dict size $groups] endpoints [dict size $bindings] counters $counters]
 event call_complete [dict create endpoints [dict size $bindings] groups [dict size $groups]]
 foreach var {group_channel member_channel trace} {if {[set $var] ne {}} {close [set $var];set $var {}}}
 set active {};set groups {};set objects {};set names {};set bindings {}
 return $result
}
proc m003_conn::abort {} {
 variable active;variable groups;variable objects;variable names;variable bindings;variable trace;variable group_channel;variable member_channel
 foreach var {group_channel member_channel trace} {if {[set $var] ne {}} {catch {close [set $var]};set $var {}}}
 set active {};set groups {};set objects {};set names {};set bindings {}
}
