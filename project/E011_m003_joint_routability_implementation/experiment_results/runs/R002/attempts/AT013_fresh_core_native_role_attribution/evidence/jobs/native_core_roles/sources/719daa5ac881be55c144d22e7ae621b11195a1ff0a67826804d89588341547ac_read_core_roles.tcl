# Read only original same-version completed core checkpoint; no constraints apply.
set report $::env(HAP_REPORT_DIR)
set checkpoint [lindex $argv 0]
set_param general.maxThreads 8
open_checkpoint $checkpoint
proc prop {object key} {
 if {$key ni [list_property $object]} {return NOT_SUPPORTED}
 return [get_property -quiet $key $object]
}
proc dump_rows {path objects} {
 set keys {NAME REF_NAME PARENT ORIG_CELL_NAME ORIG_REF_NAME IS_PRIMITIVE DONT_TOUCH}
 set h [open $path {WRONLY CREAT EXCL}];puts $h [join $keys "\t"]
 foreach object $objects {
  set values {}
  foreach key $keys {lappend values [string map [list "\t" { } "\n" { } "\r" { }] [prop $object $key]]}
  puts $h [join $values "\t"]
 }
 close $h
}
set parents [get_cells -quiet -hier -filter {NAME =~ "*u_mlp/u_serial_command/u_shared_compute"}]
dump_rows [file join $report parent_scope_candidates.tsv] $parents
set payload [get_cells -quiet -hier -filter {IS_PRIMITIVE == 1 && NAME =~ "*parent_*_r_reg*"}]
dump_rows [file join $report parent_payload_and_count_native.tsv] $payload
set buffers [get_cells -quiet -hier -filter {IS_PRIMITIVE == 1 && NAME =~ "*u_shared_compute/*u_ce_buffer"}]
dump_rows [file join $report parent_buffer_native.tsv] $buffers
set meta [get_cells -quiet -hier -filter {IS_PRIMITIVE == 1 && NAME =~ "*u_attention/u_meta/*"}]
dump_rows [file join $report metadata_native_names.tsv] $meta
set h [open [file join $report query_counts.txt] {WRONLY CREAT EXCL}]
puts $h "parent_scope_candidates=[llength $parents]\npayload_and_count_candidates=[llength $payload]\nbuffer_candidates=[llength $buffers]\nmetadata_candidates=[llength $meta]\nconstraint_apply_requested=0\nnew_synthesis_launched=0"
close $h
close_design
puts "M003_FRESH_CORE_NATIVE_ROLE_ATTRIBUTION_COMPLETED"
