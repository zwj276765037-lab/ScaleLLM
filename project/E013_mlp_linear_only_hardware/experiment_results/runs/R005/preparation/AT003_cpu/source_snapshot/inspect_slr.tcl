# Read-only M006 physical evidence. No implementation or constraint mutations.
set_param general.maxThreads 8
set out $::env(M006_SLR_REPORT)
file mkdir $out
set status [open [file join $out sections.tsv] w]
puts $status "section\tstatus\tdetail"
proc collect {name command} {
 global status out
 if {[catch {uplevel 1 $command} detail options]} {
  set f [open [file join $out ${name}.error.txt] w]
  puts $f $detail;puts $f [dict get $options -errorinfo];close $f
  puts $status "$name\tERROR\t${name}.error.txt"
  flush $status
  return 0
 }
 puts $status "$name\tCOLLECTED\t"
 flush $status
 return 1
}
open_checkpoint $::env(M006_SLR_DCP)
set id [open [file join $out design_identity.txt] w]
puts $id "design=[current_design]"
puts $id "tool_version=[version -short]"
puts $id "part=[get_property PART [current_design]]"
puts $id "source_stage=$::env(M006_SLR_STAGE)"
puts $id "source_dcp=$::env(M006_SLR_DCP)"
puts $id "source_sha256=$::env(M006_SLR_DCP_SHA)"
puts $id "scope=read_only_diagnostic_not_physical_qualification"
set fully_placed [report_route_status -boolean_check PLACED_FULLY]
puts $id "placed_fully=$fully_placed"
puts $id "routed_fully=[report_route_status -boolean_check ROUTED_FULLY]"
puts $id "errors_in_routes=[report_route_status -boolean_check ERRORS_IN_ROUTES]"
foreach slr [get_slrs] {puts $id "slr=$slr"}
close $id
if {![string is boolean -strict $fully_placed] || !$fully_placed} {
 error "SLR geometry requires a fully placed saved DCP; this is not one"
}
collect route_status [list report_route_status -file [file join $out route_status.rpt]]
collect utilization_slr [list report_utilization -slr -packthru -file [file join $out utilization_slr.rpt]]
collect crossing_global [list report_slr_crossing -max_nets 40 -file [file join $out crossing_global.rpt]]

set core scalellm_vcu118_f05_bd_i/core/inst/u_core
set compute $core/u_compute
# Parent/child counts overlap: these tables must never be summed.
set scopes [list \
 [list metadata $core/u_meta_bank] \
 [list branch0 $compute/u_mlp/u_shared_compute/u_branch0] \
 [list branch1 $compute/u_mlp/u_shared_compute/u_branch1] \
 [list mlp $compute/u_mlp] \
 [list down_scheduler $compute/u_mlp/u_down_scheduler] \
 [list gu_repack $compute/u_mlp/u_gate_scheduler/u_projection_repack] \
 [list a8_cache $compute/u_cache] \
 [list attention $compute/u_attention]]
set sf [open [file join $out scopes.tsv] w]
puts $sf "label\tpath\tmatching_hierarchies"
set selected_names {}
foreach pair $scopes {
 lassign $pair label path
 set cells [get_cells -quiet $path]
 puts $sf "$label\t$path\t[llength $cells]"
 if {[llength $cells]==1} {
  lappend selected_names $path
  collect utilization_$label [list report_utilization -slr -packthru -cells $cells -file [file join $out utilization_${label}_slr.rpt]]
 } else {
  puts $status "scope_$label\tUNAVAILABLE\texact hierarchy count [llength $cells]"
 }
}
close $sf
if {[llength $selected_names]} {
 # Re-resolve names to a native collection; no string list passed to -of_objects.
 collect crossing_scopes [list report_slr_crossing -cells [get_cells $selected_names] -max_nets 40 -file [file join $out crossing_scopes.rpt]]
}

proc occupied_slice_sites {scopes out} {
 set f [open [file join $out slice_sites.tsv] w]
 puts $f "slr\tscope\tcapacity_slice_sites\tprimitive_occupied_slice_sites"
 foreach slr [get_slrs] {
  set sites [get_sites -of_objects $slr -filter {SITE_TYPE =~ SLICE*}]
  set cells [get_cells -of_objects $sites]
  set occupied_count 0
  if {[llength $cells]} {set occupied_count [llength [get_sites -of_objects $cells -filter {SITE_TYPE =~ SLICE*}]]}
  puts $f "$slr\tboard\t[llength $sites]\t$occupied_count"
  foreach pair $scopes {
   lassign $pair label path
   if {[llength [get_cells -quiet $path]]!=1} {continue}
   set scoped [get_cells -of_objects $sites -filter [format {NAME =~ "%s/*"} $path]]
   set occupied_count 0
   if {[llength $scoped]} {set occupied_count [llength [get_sites -of_objects $scoped -filter {SITE_TYPE =~ SLICE*}]]}
   puts $f "$slr\t$label\t[llength $sites]\t$occupied_count"
  }
 }
 close $f
}
collect slice_sites [list occupied_slice_sites $scopes $out]
# Primitive-occupied sites are not LUT/8 estimates. Native utilization also
# records pack-thru usage; pure routing occupancy is not silently equated here.
collect congestion [list report_design_analysis -congestion -min_congestion_level 3 -file [file join $out congestion.rpt]]

proc old_windows {out} {
 set wf [open [file join $out old_windows.tsv] w]
 puts $wf "clock_region\tslr\tplaced_primitive_count"
 foreach region {X3Y11 X1Y10 X1Y3 X3Y9 X3Y6 X3Y7 X3Y10} {
  set cr [get_clock_regions -quiet $region]
  if {[llength $cr]!=1} {puts $wf "$region\tUNAVAILABLE\t";continue}
  set cells [get_cells -of_objects $cr]
  puts $wf "$region\t[get_slrs -of_objects $cr]\t[llength $cells]"
  if {[llength $cells]} {
   collect window_$region [list report_utilization -cells $cells -file [file join $out window_${region}_utilization.rpt]]
  } else {
   global status
   puts $status "window_$region\tNO_MATCH\tzero placed primitives in this clock region"
  }
 }
 close $wf
}
collect old_windows [list old_windows $out]

set pf [open [file join $out path_samples.tsv] w]
puts $pf "bucket\treturned\tcap\tfull_population"
foreach delay {max min} {
 foreach mode {worst negative} {
  set name cross_${delay}_${mode}
  set args [list get_timing_paths -inter_slr data_crossing -delay_type $delay -sort_by slack -max_paths 100 -nworst 1]
  if {$mode eq "negative"} {lappend args -slack_lesser_than 0}
  if {[catch {uplevel #0 $args} paths options]} {
   set f [open [file join $out ${name}.error.txt] w];puts $f $paths;close $f
   puts $status "$name\tERROR\t${name}.error.txt";continue
  }
  if {[llength $paths]>100} {error "Native query exceeded the declared per-bucket 100-path cap"}
  puts $pf "$name\t[llength $paths]\t100\tNO"
  if {[llength $paths]} {
   collect $name [list report_timing -of_objects $paths -sort_by slack -max_paths 100 -file [file join $out ${name}.rpt]]
   collect ${name}_characteristics [list report_design_analysis -of_timing_paths $paths -show_all -full_logical_pin -file [file join $out ${name}_characteristics.rpt]]
  } else {
   puts $status "$name\tNO_MATCH\tzero returned paths within declared query"
  }
 }
}
close $pf
close $status
puts "M006_SLR_DIAGNOSTIC_COLLECTION_DONE"
