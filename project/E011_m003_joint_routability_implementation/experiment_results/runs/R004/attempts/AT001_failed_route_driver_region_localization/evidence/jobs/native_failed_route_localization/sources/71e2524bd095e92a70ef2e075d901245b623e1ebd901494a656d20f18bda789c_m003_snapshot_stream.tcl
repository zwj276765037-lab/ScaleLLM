# Row emission happens while collecting, before later design queries.
namespace eval m003 {variable stream_state {};variable connection_token {}}
proc m003::clock_group {cell terminal} {
 variable connection_token
 set pin [m003_conn::one [get_pins -of_objects $cell -filter [format {REF_PIN_NAME == "%s"} $terminal]] "$cell/$terminal"]
 return [dict get [m003_conn::bind $connection_token $pin] group]
}
proc m003::stream_begin {phase out} {
 variable stream_state
 if {$stream_state ne {}} {error {M003 snapshot stream already active}}
 if {![regexp {^[a-zA-Z0-9_]+$} $phase] || ![file isdirectory $out]} {error {M003 invalid snapshot stream context}}
 set stream_state [dict create phase $phase out $out channels {} paths {} counts {}]
 foreach section {cells ce_edges master_inputs memory_pins meta_ref_cells pblocks boundaries helper_pins uram_configs reset_provenance} {
  set path [file join $out m003_stream_${phase}_${section}.jsonl.partial]
  dict set stream_state paths $section $path
  dict set stream_state channels $section [open $path {WRONLY CREAT EXCL}]
  dict set stream_state counts $section 0
 }
}
proc m003::stream_row {section row} {
 variable stream_state
 if {$stream_state eq {} || ![dict exists $stream_state channels $section]} {error {M003 inactive/unknown snapshot row stream}}
 set handle [dict get $stream_state channels $section]
 puts $handle [jobject $row]
 set count [expr {[dict get $stream_state counts $section]+1}];dict set stream_state counts $section $count
 # Bounded stage progress; no per-pin synchronous writes.
 if {$count%2048==0} {flush $handle;m003_conn::event snapshot_rows [dict create section $section rows $count]}
}
proc m003::stream_array {handle path} {
 set input [open $path r];set separator {}
 puts -nonewline $handle \[
 set code [catch {
  while {[gets $input row]>=0} {
   if {$row eq {}} {error {M003 empty row in snapshot spool}}
   puts -nonewline $handle "$separator$row";set separator ,
  }
 } message options]
 close $input
 if {$code} {return -options $options $message}
 puts -nonewline $handle \]
}
proc m003::stream_finish {path meta target_sites control_sources connectivity} {
 variable stream_state
 if {$stream_state eq {}} {error {M003 snapshot stream is inactive}}
 dict for {section handle} [dict get $stream_state channels] {close $handle}
 dict set stream_state channels {}
 set phase [dict get $stream_state phase];set out [dict get $stream_state out]
 set group_path [file join $out m003_connection_${phase}_groups.jsonl.partial]
 set endpoint_path [file join $out m003_connection_${phase}_endpoints.jsonl.partial]
 set partial $path.partial
 if {[file exists $path]} {error {M003 snapshot final output exists}}
 set h [open $partial {WRONLY CREAT EXCL}]
 set code [catch {
  puts -nonewline $h "\{\"schema\":\"M003_native_grouped_stream_v1\",\"meta\":[jobject $meta]"
  dict for {section row_path} [dict get $stream_state paths] {puts -nonewline $h ",[jq $section]:";stream_array $h $row_path}
  puts -nonewline $h ",\"target_sites\":[jobject $target_sites],\"control_sources\":[jobject $control_sources]"
  puts -nonewline $h ",\"connection_groups\":";stream_array $h $group_path
  puts -nonewline $h ",\"connection_endpoints\":";stream_array $h $endpoint_path
  puts -nonewline $h ",\"connection_counts\":\{\"endpoints\":[dict get $connectivity endpoints],\"groups\":[dict get $connectivity groups]\},\"connection_api_counts\":\{"
  set sep {}
  dict for {kind values} [dict get $connectivity counters] {
   puts -nonewline $h "$sep[jq $kind]:\{";set value_sep {}
   dict for {k v} $values {puts -nonewline $h "$value_sep[jq $k]:$v";set value_sep ,}
   puts -nonewline $h \};set sep ,
  }
  puts $h "\}\}";close $h;set h {}
  dict for {section row_path} [dict get $stream_state paths] {file rename $row_path [string range $row_path 0 end-8]}
  foreach row_path [list $group_path $endpoint_path] {file rename $row_path [string range $row_path 0 end-8]}
  file rename $partial $path
 } message options]
 if {$h ne {}} {catch {close $h}}
 if {$code} {return -options $options $message}
 set stream_state {}
}
proc m003::stream_abort {} {
 variable stream_state
 if {$stream_state ne {}} {dict for {section handle} [dict get $stream_state channels] {catch {close $handle}}}
 set stream_state {}
}
