# Static, pre-frozen discovery and role classification. Generated data is never sourced.
proc cq_base_predicate {} {return {((DIRECTION == IN && (IS_CLOCK == 0 || REF_PIN_NAME =~ CE*)) || DIRECTION == INOUT)}}
proc cq_full_predicate {extras} {
 set base [cq_base_predicate]
 if {![llength $extras]} {return $base}
 set terms {};foreach pin $extras {lappend terms [format {NAME == "%s"} $pin]}
 return "($base || (IS_CLOCK == 1 && ([join $terms { || }])))"
}
proc cq_property_or_unknown {object property} {
 if {[lsearch -exact [list_property $object] $property]<0} {return __UNAVAILABLE__}
 if {[catch {get_property $property $object} value]} {return __UNAVAILABLE__}
 return $value
}
proc cq_category_members {clocks category} {
 set cells [all_registers -clock $clocks]
 switch $category {
  data {return [all_registers -clock $clocks -data_pins]}
  asynchronous {return [all_registers -clock $clocks -async_pins]}
  clock_enable {return [get_pins -quiet -of_objects $cells -filter {(DIRECTION == IN || DIRECTION == INOUT) && (REF_PIN_NAME =~ CE* || REF_PIN_NAME =~ CLKEN*)}]}
  clock_gating_CE {
   set gates [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE == 1 && (REF_NAME =~ BUFG* || REF_NAME =~ BUFH* || REF_NAME =~ BUFR* || REF_NAME =~ BUFCE*)}]
   if {![llength $gates]} {return {}}
   return [get_pins -quiet -of_objects $gates -filter {(DIRECTION == IN || DIRECTION == INOUT) && (REF_PIN_NAME =~ CE* || REF_PIN_NAME =~ CLKEN*)}]
  }
 }
 error "unsupported pre-frozen capture category $category"
}
proc cq_capture_role_probe {outdir groups python helper} {
 set raw [open [file join $outdir capture_role_properties.txt] w]
 set json [open [file join $outdir capture_role_facts.jsonl] w]
 set total 0
 foreach domain {ddr0 ddr1} {
  set clocks [cq_clock_objects [dict get $groups $domain]]
  set clock_names [cq_names [all_registers -clock $clocks -clock_pins]]
  set output_names [cq_names [all_registers -clock $clocks -output_pins]]
  set missing {};set objects {};set category_names {}
  foreach category {data asynchronous clock_enable clock_gating_CE} {
   set members [cq_category_members $clocks $category]
   dict set category_names $category [cq_names $members]
   set omitted {};if {[llength $members]} {set omitted [filter $members "!([cq_base_predicate])"]}
   puts $raw [list domain $domain category $category members [llength $members] original_predicate_omitted [llength $omitted]]
   foreach pin $omitted {
    set name [get_property NAME $pin]
    dict lappend missing $name $category;dict set objects $name $pin
   }
  }
  dict for {name categories} $missing {
   incr total
   if {$total>512} {error {capture role probe exceeds512 bounded records}}
   set pin [dict get $objects $name];set cell [get_cells -quiet -of_objects $pin]
   set libraries [get_lib_pins -quiet -of_objects $pin]
   set libdir __UNAVAILABLE__;set libclock __UNAVAILABLE__;set libdata __UNAVAILABLE__
   puts $raw [list missing_pin $name domain $domain categories $categories owner [cq_names $cell] ref [get_property REF_NAME $cell] ref_pin [get_property REF_PIN_NAME $pin] direction [get_property DIRECTION $pin] is_clock [get_property IS_CLOCK $pin]]
   foreach library $libraries {
    set props {};foreach key [lsort [list_property $library]] {lappend props $key [cq_property_or_unknown $library $key]}
    puts $raw [list library_pin [get_property NAME $library] all_properties $props]
   }
   if {[llength $libraries]==1} {
    set libdir [cq_property_or_unknown $libraries DIRECTION]
    set libclock [cq_property_or_unknown $libraries IS_CLOCK]
    set libdata [cq_property_or_unknown $libraries IS_DATA]
   }
   set clock_member [expr {[lsearch -exact $clock_names $name]>=0}]
   set output_member [expr {[lsearch -exact $output_names $name]>=0}]
   set fields {}
   foreach {key value} [list domain $domain name $name owner_ref [get_property REF_NAME $cell] ref_pin [get_property REF_PIN_NAME $pin] direction [get_property DIRECTION $pin] is_clock [get_property IS_CLOCK $pin] library_direction $libdir library_is_clock $libclock library_is_data $libdata] {lappend fields "[cq_quote $key]:[cq_quote $value]"}
   lappend fields "\"categories\":[cq_json_array $categories]" "\"pin_clocks\":[cq_json_array [cq_names [get_clocks -quiet -of_objects $pin]]]" "\"library_pin_count\":[llength $libraries]" "\"native_clock_member\":[expr {$clock_member ? "true" : "false"}]" "\"native_output_member\":[expr {$output_member ? "true" : "false"}]"
   puts $json "\{[join $fields ,]\}"
  }
 }
 # The complete native/library discovery is closed before any branch decision.
 close $json;close $raw
 set classification [file join $outdir capture_role_classification.json]
 if {[catch {exec $python [file join [file dirname $helper] capture_role_classifier.py] [file join $outdir capture_role_facts.jsonl] [file join [file dirname $helper] role_model_sources.json] $classification} message]} {
  puts $message
  error {UNKNOWN capture role: bounded native/library facts retained; no timing mutation permitted}
 }
 puts $message
 set decision_file [file rootname $classification].tsv
 set f [open $decision_file r];set decisions {};set extras [dict create ddr0 {} ddr1 {}]
 while {[gets $f row]>=0} {
  lassign [split $row \t] domain action name
  if {$domain ni {ddr0 ddr1} || $action ni {ADD_EXACT_CAPTURE EXCLUDE_PROVEN_NONCAPTURE}} {error {invalid frozen role decision data}}
  dict set decisions $domain $name $action
  if {$action eq "ADD_EXACT_CAPTURE"} {dict lappend extras $domain $name}
 }
 close $f
 puts {CQ_STAGE CAPTURE_ROLE_DISCOVERY_AND_FROZEN_CLASSIFICATION_PASS}
 return [list $extras $decisions $classification]
}
proc cq_load_reused_sync {path} {
 set f [open $path r];set signatures {};set rows 0
 while {[gets $f row]>=0} {
  if {$row eq {}} {continue}
  set fields [dict create {*}[lrange $row 2 end]]
  set signature [list [lindex $row 0] [lindex $row 1] count [dict get $fields count]]
  if {[dict get $fields count]} {lappend signature SLACK [dict get $fields SLACK]}
  lappend signatures $signature;incr rows
 }
 close $f
 if {$rows!=100} {error {expected exactly100 frozen AT004 original same-clock extrema rows}}
 return [lsort $signatures]
}
