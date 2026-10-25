# Read-only, bounded inspection after the owning implementation has ended.
# No set_* timing constraints, synthesis, optimization, placement, or routing.
# Targets derive from R008/AT001_impl/route_bus_skew_warning_observation.json.
set guq_targets {
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_weight_frontend/u_command1_cdc/dest_hsdata_ff_reg[14]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_weight_frontend/u_command1_cdc/dest_hsdata_ff_reg[16]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_weight_frontend/u_command0_cdc/dest_hsdata_ff_reg[14]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_weight_frontend/u_command0_cdc/dest_hsdata_ff_reg[16]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command1_cdc/dest_hsdata_ff_reg[17]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command1_cdc/dest_hsdata_ff_reg[15]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command1_cdc/dest_hsdata_ff_reg[16]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command0_cdc/dest_hsdata_ff_reg[17]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command0_cdc/dest_hsdata_ff_reg[15]/D}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command0_cdc/dest_hsdata_ff_reg[16]/D}
}
set guq_scopes {
 scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_weight_frontend/u_command0_cdc
 scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_weight_frontend/u_command1_cdc
 scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command0_cdc
 scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_w4_frontend/u_command1_cdc
}
set guq_reset_scopes {
 scalellm_vcu118_f05_bd_i/d0_gate/inst/u_base_reset_cdc
 scalellm_vcu118_f05_bd_i/d1_gate/inst/u_base_reset_cdc
}
set guq_dsp_targets {
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_shared_compute/u_branch0/u_kernel/gen_row[0].gen_pair[0].u_lane/u_dot/gen_leaf[0].u_leaf/s1_dsp_product_s25_r0}
 {scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_shared_compute/u_branch1/u_kernel/gen_row[0].gen_pair[0].u_lane/u_dot/gen_leaf[0].u_leaf/s1_dsp_product_s25_r0}
}
proc guq_literal_regex {name} {
 regsub -all {[][\\.^$*+?(){}|]} $name {\\&} escaped
 return [format {^%s$} $escaped]
}
proc guq_names {objects} {set v {};foreach x $objects {lappend v [get_property NAME $x]};return $v}
proc guq_clock {out label cell} {
 set cp [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == C}]
 set clocks {};if {[llength $cp]} {set clocks [get_clocks -quiet -of_objects $cp]}
 puts $out [list clock $label cell [get_property NAME $cell] C [guq_names $cp] clocks [guq_names $clocks]]
}
proc guq_report {out label command path} {
 puts $out [list report $label command $command]
 if {[catch {uplevel 1 $command} detail]} {
  puts $out [list report $label status NATIVE_ERROR detail $detail];return
 }
 if {![file isfile $path] || [file size $path]==0} {
  puts $out [list report $label status MISSING_OR_EMPTY];return
 }
 puts $out [list report $label status COLLECTED bytes [file size $path]]
}
proc guq_drivers {pin} {
 set ns [get_nets -quiet -segments -of_objects $pin]
 if {![llength $ns]} {return {}}
 # Preserve a native pin collection, including all leaf drivers on all segments.
 return [get_pins -quiet -leaf -of_objects $ns -filter {DIRECTION == OUT}]
}
proc guq_fanout {out label driver} {
 set nets [get_nets -quiet -segments -of_objects $driver]
 if {![llength $nets]} {puts $out [list fanout $label status NO_NET];return}
 set loads [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == IN}]
 puts $out [list fanout $label driver [get_property NAME $driver] count [llength $loads] emitted_bound 128]
 set emitted 0
 foreach load $loads {
  if {$emitted>=128} {puts $out [list fanout_bound $label];break}
  incr emitted
  set cell [get_cells -quiet -of_objects $load]
  puts $out [list fanout_load $label pin [get_property NAME $load] owner [guq_names $cell] ref [get_property REF_NAME $cell]]
  if {[llength $cell]==1 && [string match FD* [get_property REF_NAME $cell]]} {guq_clock $out fanout:$label $cell}
 }
}
proc guq_trace {out target sink {emit_launch_fanout 0}} {
 # Only the ten specified data cones, at most 64 unique pins / depth eight.
 # Stop at real FD* Q, VCC/GND, unknown primitive, or an external input.
 set queue [list [list $sink 0]];set seen {};set count 0
 while {[llength $queue]} {
  lassign [lindex $queue 0] pin depth;set queue [lrange $queue 1 end]
  set name [get_property NAME $pin]
  if {[dict exists $seen $name]} {continue};dict set seen $name 1
  incr count
  if {$count>64 || $depth>8} {puts $out [list trace_bound $target count $count depth $depth];return}
  set drivers [guq_drivers $pin]
  puts $out [list trace $target sink $name depth $depth drivers [guq_names $drivers]]
  if {![llength $drivers]} {puts $out [list unresolved $target no_leaf_driver_at $name];continue}
  foreach driver $drivers {
   set owner [get_cells -quiet -of_objects $driver]
   if {[llength $owner]!=1} {puts $out [list unresolved $target driver $driver owner_count [llength $owner]];continue}
   set ref [get_property REF_NAME $owner];set oname [get_property NAME $owner]
   puts $out [list driver $target pin [get_property NAME $driver] owner $oname ref $ref]
   if {[string match FD* $ref] && [get_property REF_PIN_NAME $driver] eq "Q"} {
    puts $out [list launch_FF $target Q [get_property NAME $driver] cell $oname ref $ref]
    guq_clock $out launch:$target $owner
    if {$emit_launch_fanout} {guq_fanout $out $target $driver}
    continue
   }
   if {$ref in {VCC GND}} {puts $out [list constant_primitive $target owner $oname ref $ref];continue}
   if {![string match LUT* $ref] && ![string match MUXF* $ref] && $ref ni {BUF IBUF}} {
    puts $out [list unresolved $target nontraversed_primitive $oname ref $ref];continue
   }
   set ins [get_pins -quiet -of_objects $owner -filter {DIRECTION == IN}]
   foreach ip $ins {lappend queue [list $ip [expr {$depth+1}]]}
  }
 }
 puts $out [list trace_complete $target visited $count]
}
proc guq_reset_identity {outdir} {
 global guq_reset_scopes
 set out [open [file join $outdir native_xdma_reset_objects.txt] w]
 puts $out {scope=two_exact_XDMA_to_DDR_gate_base_reset_chains; separate_from_prior_six_chains_24_stages; diagnostic_no_waiver}
 puts $out {source_RTL=DEST_SYNC_FF4_INIT_SYNC_FF1_RST_ACTIVE_HIGH0; actual_primitive_polarity_connectivity_recorded_below}
 foreach scope $guq_reset_scopes {
  set cells [get_cells -quiet -hierarchical -filter [format {NAME =~ "%s/*" && IS_PRIMITIVE == 1} $scope]]
  if {[llength $cells]>128} {error "Reset scope exceeded 128 primitive bound: $scope"}
  set by_name {}
  foreach cell $cells {dict set by_name [get_property NAME $cell] $cell}
  puts $out [list reset_scope $scope primitives [llength $cells]]
  set previous_name {}
  for {set i 0} {$i<4} {incr i} {
   set name [format {%s/arststages_ff_reg[%d]} $scope $i]
   if {![dict exists $by_name $name]} {puts $out [list reset_stage $name status MISSING];continue}
   set cell [dict get $by_name $name]
   puts $out [list reset_stage $name ref [get_property REF_NAME $cell] async_reg [get_property ASYNC_REG $cell] init [get_property INIT $cell] expected_previous $previous_name]
   guq_clock $out reset_stage:$name $cell
   foreach kind {D CLR PRE} {
    set pins [get_pins -quiet -of_objects $cell -filter [format {REF_PIN_NAME == %s} $kind]]
    foreach pin $pins {
     set drivers [guq_drivers $pin]
     puts $out [list reset_connectivity stage $name kind $kind sink [get_property NAME $pin] drivers [guq_names $drivers]]
     if {$i==0} {guq_trace $out reset:$kind:$name $pin [expr {$kind ne "D"}]}
    }
   }
   set previous_name $name
   if {$i==3} {
    set q [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == Q}]
    foreach pin $q {guq_fanout $out reset_output:$scope $pin}
   }
  }
 }
 puts $out {interpretation=PENDING_REVIEW; source_fanout_and_release_reconvergence_are_recorded_not_waived}
 close $out
}
proc guq_dsp_identity {outdir} {
 global guq_dsp_targets
 set out [open [file join $outdir native_representative_dsp_objects.txt] w]
 puts $out {scope=two_representative_physical_DSPs_not_all3072; compare_with_separate_bound_funcsim_all3072_mode_proof; no_waiver}
 foreach name $guq_dsp_targets {
  set cells [get_cells -quiet -hierarchical -regexp [guq_literal_regex $name]]
  puts $out [list representative $name count [llength $cells]]
  if {[llength $cells]!=1} {continue}
  set cell $cells
  puts $out [list representative $name ref [get_property REF_NAME $cell] PREG [get_property PREG $cell] OPMODEREG [get_property OPMODEREG $cell]]
  set pins [get_pins -quiet -of_objects $cell -filter {DIRECTION == IN}]
  foreach pin $pins {
   set refpin [get_property REF_PIN_NAME $pin]
   if {![string match OPMODE* $refpin] && ![string match ALUMODE* $refpin]} {continue}
   puts $out [list mode_pin representative $name pin [get_property NAME $pin] ref_pin $refpin direct_drivers [guq_names [guq_drivers $pin]]]
   guq_trace $out dsp:$name:$refpin $pin
  }
 }
 puts $out {interpretation=PENDING_REVIEW; compare_actual_driver_aliases_with_Z000_or011_no_P_feedback_not_pin_index_assumption}
 close $out
}
proc guq_smc_exception_identity {outdir} {
 set out [open [file join $outdir native_smc_scoped_exceptions.txt] w]
 puts $out {scope=two_exact_SMC_request_FIFO_doutb_registers; original_four_invalid_option_catches_remain_preserved; no_global_valid_or_ignored_objects_dump}
 set prefix scalellm_vcu118_f05_bd_i
 set suffix {inst/s00_nodes/s00_w_node/inst/inst_mi_handler/gen_normal_area.gen_fifo_req.inst_fifo_req/gen_xpm_memory_fifo.inst_fifo}
 foreach smc {d0_smc d1_smc} {
  set scope "$prefix/$smc/$suffix/gen_mem_rep\[0\].inst_xpm_memory/xpm_memory_base_inst"
  set cells [get_cells -quiet -hierarchical -filter [format {NAME =~ "%s/%s/%s/*doutb*reg*"} $prefix $smc $suffix]]
  if {[llength $cells]>512} {error "SMC exception scope exceeded bound: $smc"}
  foreach cell $cells {
   if {[string first "$scope/" [get_property NAME $cell]]!=0} {error {SMC exception object escaped literal memory scope}}
   puts $out [list smc_object $smc name [get_property NAME $cell] ref [get_property REF_NAME $cell]]
  }
  set regs {};if {[llength $cells]} {set regs [filter $cells {IS_PRIMITIVE == 1 && REF_NAME =~ FD*}]}
  puts $out [list smc_registers $smc count [llength $regs]]
  if {![llength $regs]} {continue}
  foreach reg $regs {guq_clock $out smc:$smc $reg}
  # These forms retain explicit cell endpoint scope. The unsupported global
  # write_valid_exceptions / ignored_objects forms are never reissued.
  foreach {label flags} {scoped {} coverage {-coverage} ignored_scoped {-ignored}} {
   set path [file join $outdir ${smc}_${label}_exceptions.rpt]
   guq_report $out smc:$smc:$label [concat [list report_exceptions -to $regs] $flags [list -file $path]] $path
  }
  set d [get_pins -quiet -of_objects $regs -filter {REF_PIN_NAME == D}]
  set path [file join $outdir ${smc}_doutb_one_timing_path.rpt]
  guq_report $out smc:$smc:timing [list report_timing -to $d -delay_type max -max_paths 1 -path_type short -file $path] $path
 }
 puts $out {interpretation=PENDING_REVIEW; scoped_ignored_command_errors_or_empty_reports_are_recorded_not_zero_ignored_or_global_validity}
 close $out
}
proc guq_main {} {
 global guq_targets guq_scopes argv
 if {[llength $argv]!=2} {error {usage: inspect_gu_bus_skew.tcl DCP NEW_OUTPUT_DIRECTORY}}
 lassign $argv dcp outdir
 if {![file isfile $dcp] || [file exists $outdir]} {error {DCP must exist; output directory must be new}}
 file mkdir $outdir
 set_param general.maxThreads 8
 open_checkpoint $dcp
 set out [open [file join $outdir native_bus_skew_objects.txt] w]
 puts $out {scope=ten_exact_warning_D_pins_four_XPM_handshake_instances; diagnostic_only_no_waiver}
 puts $out {group_count_bits_are_reset_zero_then_accepted_command_one; not_all_time_constant_one}
 set owner_map {};set scope_map {};set number 0
 foreach scope $guq_scopes {
  incr number
  set cells [get_cells -quiet -hierarchical -filter [format {NAME =~ "%s/*" && IS_PRIMITIVE == 1} $scope]]
  if {[llength $cells]>512} {error "XPM scope exceeded 512 primitive bound: $scope"}
  puts $out [list scope $scope primitives [llength $cells]]
  foreach cell $cells {
   set name [get_property NAME $cell]
   if {[string first "$scope/" $name]!=0} {error {native scope escaped literal prefix}}
   dict set owner_map $name $cell
  }
  # Native collections stay native; no lappend/concat conversion before -of_objects.
  set src {};set dst {}
  if {[llength $cells]} {
   set src [filter $cells [format {NAME =~ "%s/src_hsdata_ff_reg*"} $scope]]
   set dst [filter $cells [format {NAME =~ "%s/dest_hsdata_ff_reg*"} $scope]]
  }
  puts $out [list scope_sources $scope [guq_names $src]]
  puts $out [list scope_destinations $scope [guq_names $dst]]
  foreach cell $src {guq_clock $out source $cell}
  foreach cell $dst {guq_clock $out destination $cell}
  set h [get_cells -quiet -hierarchical -filter [format {NAME == "%s"} $scope]]
  puts $out [list hierarchy $scope count [llength $h]]
  if {[llength $h]==1} {
   set path [file join $outdir scope${number}_bus_skew.rpt]
   guq_report $out bus_skew:$scope [list report_bus_skew -cells $h -max_paths 32 -nworst 1 -path_type short -delay_type min_max -file $path] $path
  }
  if {[llength $src] && [llength $dst]} {
   # Effective XDC uses cells for both -from and -to, rather than Q/D pins.
   set path [file join $outdir scope${number}_exception_coverage.rpt]
   guq_report $out exception:$scope [list report_exceptions -from $src -to $dst -coverage -file $path] $path
  } else {puts $out [list report exception:$scope status MISSING_NATIVE_SOURCE_OR_DESTINATION]}
 }
 foreach target $guq_targets {
  set owner [file dirname $target]
  if {![dict exists $owner_map $owner]} {puts $out [list target $target status MISSING_OWNER];continue}
  set cell [dict get $owner_map $owner]
  set pin [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
  puts $out [list target $target owner_ref [get_property REF_NAME $cell] D_count [llength $pin]]
  if {[llength $pin]!=1 || [get_property NAME $pin] ne $target} {puts $out [list target $target status MISSING_OR_AMBIGUOUS_D];continue}
  guq_clock $out destination:$target $cell
  guq_trace $out $target $pin
  # Do not assume source and destination bit indexes survived optimization.
  set path [file join $outdir target_[format %02d [lsearch -exact $guq_targets $target]]_timing.rpt]
  guq_report $out timing:$target [list report_timing -to $pin -delay_type max -max_paths 1 -path_type short -file $path] $path
 }
 puts $out {interpretation=PENDING_REVIEW; missing_path_does_not_imply_constant_or_waived; source_aliases_need_actual_native_driver_evidence}
 close $out
 guq_reset_identity $outdir
 guq_dsp_identity $outdir
 guq_smc_exception_identity $outdir
 close_design
 puts {NATIVE_GU_BUS_SKEW_DIAGNOSTIC_COMPLETED}
}
if {![info exists ::HAP_BUS_QUERY_DEFINITIONS_ONLY] || !$::HAP_BUS_QUERY_DEFINITIONS_ONLY} {guq_main}
