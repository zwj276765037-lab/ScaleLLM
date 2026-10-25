# Independent same-routed-graph constraint analysis. No physical implementation.
proc cq_names {objects} {return [get_property NAME $objects]}
proc cq_quote {s} {return \"[string map [list \\ \\\\ \" \\\" \n \\n \r \\r \t \\t] $s]\"}
proc cq_json_array {items} {set out {};foreach x $items {lappend out [cq_quote $x]};return \[[join $out ,]\]}
proc cq_clock_objects {names} {
 set conditions {};foreach name $names {lappend conditions [format {NAME == "%s"} $name]}
 return [get_clocks -quiet -filter [join $conditions { || }]]
}
proc cq_exact_cells {name} {
 regsub -all {[][\\.^$*+?(){}|]} $name {\\&} escaped
 return [get_cells -quiet -hierarchical -regexp [format {^%s$} $escaped]]
}
proc cq_direct_drivers {pin} {
 return [get_pins -quiet -leaf -of_objects [get_nets -quiet -segments -of_objects $pin] -filter {DIRECTION == OUT}]
}
proc cq_clocks {outdir label} {
 set out [open [file join $outdir ${label}_clock_identity.txt] w]
 set identities {}
 foreach clock [get_clocks -quiet *] {
  set row [list NAME [get_property NAME $clock]]
  foreach property {PERIOD WAVEFORM IS_GENERATED MASTER_CLOCK SOURCE_PINS} {
   if {[catch {get_property $property $clock} value]} {set value UNAVAILABLE}
   lappend row $property $value
  }
  lappend identities $row
 }
 set identities [lsort $identities]
 foreach row $identities {puts $out $row}
 close $out
 return $identities
}
proc cq_sync_paths {outdir label clocks} {
 set out [open [file join $outdir ${label}_same_clock_paths.txt] w]
 set rows {};set signatures {}
 foreach clock $clocks {
  foreach kind {max min} {
   set paths [get_timing_paths -from $clock -to $clock -delay_type $kind -max_paths 1]
   set row [list [get_property NAME $clock] $kind count [llength $paths]]
   if {[llength $paths]} {
    foreach key {SLACK REQUIREMENT DATAPATH_DELAY STARTPOINT_PIN ENDPOINT_PIN} {
     lappend row $key [get_property $key $paths]
    }
   }
   lappend rows $row
   # Equal-slack worst-path ties may select different endpoints after timing
   # reset. Preserve the full endpoints above, gate the same-clock extrema.
   set signature [list [get_property NAME $clock] $kind count [llength $paths]]
   if {[llength $paths]} {lappend signature SLACK [get_property SLACK $paths]}
   lappend signatures $signature
  }
 }
 set rows [lsort $rows];foreach row $rows {puts $out $row};close $out
 return [lsort $signatures]
}
proc cq_target_identity {outdir groups} {
 set prefix scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute
 set scopes [list $prefix/u_attention/u_weight_frontend/u_command0_cdc $prefix/u_attention/u_weight_frontend/u_command1_cdc $prefix/u_mlp/u_w4_frontend/u_command0_cdc $prefix/u_mlp/u_w4_frontend/u_command1_cdc]
 set target_dict [dict create ddr0 {} ddr1 {}];set path_dict {};set scope_number 0
 set out [open [file join $outdir native_dynamic_target_connectivity.txt] w]
 foreach scope $scopes {
  set domain [expr {$scope_number<2 ? "ddr0" : "ddr1"}];set expected [expr {$scope_number<2 ? 34 : 35}];incr scope_number
  set cells [get_cells -quiet -hierarchical -filter [format {NAME =~ "%s/dest_hsdata_ff_reg*" && IS_PRIMITIVE == 1} $scope]]
  if {[llength $cells]>128} {error "capture scope exceeds bounded128 cells: $scope"}
  set count 0
  foreach cell $cells {
   if {[get_property REF_NAME $cell] ne "FDRE"} {error "unexpected capture primitive in $scope"}
   set d [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == D}]
   if {[llength $d]!=1} {error {capture register must have exactly one D}}
   set drivers [cq_direct_drivers $d]
   if {[llength $drivers]!=1} {error {dynamic capture must have one direct driver}}
   set driver_cell [get_cells -quiet -of_objects $drivers]
   set ref [get_property REF_NAME $driver_cell]
   if {$ref in {VCC GND}} {puts $out [list constant_capture [get_property NAME $d] driver [get_property NAME $drivers] ref $ref];continue}
   if {![string match FD* $ref] || [get_property REF_PIN_NAME $drivers] ne "Q" || [string first "$scope/src_hsdata_ff_reg" [get_property NAME $driver_cell]]!=0} {error "target is not direct same-scope launch FF Q: $d"}
   if {[get_property DIRECTION $drivers] ne "OUT" || [get_property DIRECTION $d] ne "IN"} {error {target Q/D direction contradicts complement predicate}}
   set launch_c [get_pins -quiet -of_objects $driver_cell -filter {REF_PIN_NAME == C}]
   set capture_c [get_pins -quiet -of_objects $cell -filter {REF_PIN_NAME == C}]
   set launch_clocks [get_clocks -quiet -of_objects $launch_c];set capture_clocks [get_clocks -quiet -of_objects $capture_c]
   if {[llength $launch_c]!=1 || [llength $launch_clocks]!=1 || [llength $capture_clocks]!=1} {error {ambiguous target launch/capture clock}}
   if {![get_property IS_CLOCK $launch_c] || ![get_property IS_CLOCK $capture_c]} {error {target clock-pin taxonomy does not exclude launch/capture clock traversal}}
   if {[lsearch -exact [dict get $groups pcie] [get_property NAME $launch_clocks]]<0 || [lsearch -exact [dict get $groups $domain] [get_property NAME $capture_clocks]]<0} {error {target escaped original directed clock groups}}
   set name [get_property NAME $d]
   dict lappend target_dict $domain $name
   dict set path_dict $name [list $launch_c $d $drivers $scope_number]
   puts $out [list dynamic_capture $name launch_Q [get_property NAME $drivers] launch_C [get_property NAME $launch_c] launch_clock [cq_names $launch_clocks] capture_clock [cq_names $capture_clocks]]
   incr count
  }
  puts $out [list scope $scope dynamic_D $count expected $expected]
  if {$count!=$expected} {error "dynamic D count mismatch in $scope: $count != $expected"}
 }
 close $out
 set json [open [file join $outdir target_identity.json] w]
 set cg {};foreach key {pcie ddr0 ddr1} {lappend cg "[cq_quote $key]:[cq_json_array [dict get $groups $key]]"}
 set td {};foreach key {ddr0 ddr1} {dict set target_dict $key [lsort [dict get $target_dict $key]];lappend td "[cq_quote $key]:[cq_json_array [dict get $target_dict $key]]"}
 puts $json "\{\"clock_groups\":\{[join $cg ,]\},\"target_D\":\{[join $td ,]\}\}";close $json
 return [list $target_dict $path_dict $scopes]
}
proc cq_capture_complements {outdir groups targets path_dict} {
 set out [open [file join $outdir native_capture_complement_proof.txt] w]
 set predicate {((DIRECTION == IN && (IS_CLOCK == 0 || REF_PIN_NAME =~ CE*)) || DIRECTION == INOUT)}
 set outputs [get_pins -quiet -leaf -of_objects [get_nets -quiet -segments -of_objects [get_ports -quiet -filter {DIRECTION == OUT || DIRECTION == INOUT}]] -filter {DIRECTION == OUT || DIRECTION == INOUT}]
 set output_names [cq_names $outputs]
 puts $out [list output_capture_driver_pins [llength $outputs] names $output_names]
 dict for {name row} $path_dict {
  if {[lsearch -exact $output_names [get_property NAME [lindex $row 2]]]>=0} {error {target launch Q also drives an external output; complement needs refinement}}
  puts $out [list target_path_intersection $name primitive_input_through {} output_driver_through {} proof {direct FFQ to FDRE D; Q directionOUT; D excluded_by_exact_NAME; source/capture C are IS_CLOCK1; launch Q absent_from_all_external_output_drivers}]
 }
 foreach domain {ddr0 ddr1} {
  set clocks [cq_clock_objects [dict get $groups $domain]]
  set cells [all_registers -clock $clocks]
  # Native bulk query, never a Tcl per-primitive walk. The superset also
  # includes clock-gating CE and unregistered macro inputs. Original directed
  # clock clamps prevent it from cutting any previously timed clock pair.
  set primitives [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE == 1}]
  set inputs [get_pins -quiet -of_objects $primitives -filter $predicate]
  set expression $predicate
  foreach pin [dict get $targets $domain] {append expression [format { && NAME != "%s"} $pin]}
  set complement [get_pins -quiet -of_objects $primitives -filter $expression]
  set difference [expr {[llength $inputs]-[llength $complement]}]
  if {$difference!=[llength [dict get $targets $domain]]} {error {native complement difference differs from exact dynamic D set}}
  puts $out [list domain $domain capture_cells [llength $cells] through_superset_primitive_cells [llength $primitives] all_nonclock_input_pins [llength $inputs] through_complement [llength $complement] removed_exact_dynamic_D $difference]
  foreach pattern {FD* LD* RAMB* URAM* DSP*} {
   puts $out [list capture_class $domain $pattern cells [llength [filter $cells [format {REF_NAME =~ %s} $pattern]]]]
  }
  foreach category {data asynchronous clock_enable inout clock_gating_CE} {
   switch $category {
    data {set members [all_registers -clock $clocks -data_pins]}
    asynchronous {set members [all_registers -clock $clocks -async_pins]}
    clock_enable {set members [get_pins -quiet -of_objects $cells -filter {DIRECTION == IN && REF_PIN_NAME =~ CE*}]}
    inout {set members [get_pins -quiet -of_objects $primitives -filter {DIRECTION == INOUT}]}
    clock_gating_CE {
     set gates [filter $primitives {REF_NAME =~ BUFG* || REF_NAME =~ BUFH* || REF_NAME =~ BUFR*}]
     set members [get_pins -quiet -of_objects $gates -filter {(DIRECTION == IN || DIRECTION == INOUT) && REF_PIN_NAME =~ CE*}]
     puts $out [list gating_CE_native_objects $domain [cq_names $members]]
    }
   }
   set contained [filter $members $predicate]
   puts $out [list capture_category_subset $domain $category members [llength $members] in_through_superset [llength $contained]]
   if {[llength $members]!=[llength $contained]} {error "capture category omitted by complement predicate: $domain $category"}
  }
  puts $out [list proof $domain {from/to clock clamp preserves multi-clock-cell associations; the nonclock primitive-input through superset includes all captures/CE/reset/gating/RAM/DSP and external-output drivers; verified direct-Q-to-D target paths contain no other primitive input, so exactly their138 D are exposed}]
 }
 close $out
}
proc cq_target_timing {outdir path_dict scopes} {
 set out [open [file join $outdir corrected_dynamic_D_timing.txt] w]
 set number 0
 dict for {name row} $path_dict {
  lassign $row launch_c d q scope_number;incr number
  set paths [get_timing_paths -from $launch_c -to $d -delay_type max -max_paths 1]
  if {[llength $paths]!=1} {error "expected one active max path for $name"}
  set slack [get_property SLACK $paths];set requirement [get_property REQUIREMENT $paths]
  puts $out [list target $name slack $slack requirement $requirement datapath [get_property DATAPATH_DELAY $paths] startpoint [get_property STARTPOINT_PIN $paths] endpoint [get_property ENDPOINT_PIN $paths]]
  set text [report_timing -of_objects $paths -path_type short]
  set f [open [file join $outdir [format {dynamic_D_%03d.rpt} $number]] w];puts $f $text;close $f
  if {![string is double -strict $slack] || [string match -nocase *inf* $slack] || abs($requirement-10.0)>0.0001 || $slack<0} {error "Max-DPO10 not finite/met for $name"}
  if {![regexp -nocase {max.?delay.*datapath|datapath.*only} $text] || [regexp -nocase {Asynchronous Clock Groups|False Path} $text]} {error "target not governed by actual Max-DPO: $name"}
 }
 close $out
 if {$number!=138} {error {not all138 dynamic D timing paths were checked}}
 set i 0
 foreach scope $scopes {
  incr i
  set h [get_cells -quiet -hierarchical -filter [format {NAME == "%s"} $scope]]
  report_bus_skew -cells $h -max_paths 32 -nworst 1 -path_type short -delay_type min_max -file [file join $outdir corrected_scope${i}_bus_skew.rpt]
 }
}
proc cq_main {} {
 global argv
 if {[llength $argv]!=5} {error {usage: DCP NEW_OUTPUT_DIR PYTHON HELPER PARENT_TIMING_REPORT}}
 lassign $argv dcp outdir python helper parent_timing
 if {![file isfile $dcp] || [file exists $outdir]} {error {original DCP required and output must be new}}
 file mkdir $outdir;set_param general.maxThreads 8
 open_checkpoint $dcp
 puts {CQ_STAGE ORIGINAL_ROUTED_OPENED}
 write_xdc -constraints ALL -no_tool_comments [file join $outdir original_complete_all.xdc]
 write_xdc -type timing -constraints ALL -no_tool_comments [file join $outdir original_timing_all.xdc]
 set original_clocks [cq_clocks $outdir original]
 set clocks [get_clocks -quiet *]
 set original_sync [cq_sync_paths $outdir original $clocks]
 set groups {}
 foreach {key port} {pcie pcie_refclk_p ddr0 default_250mhz_clk1_clk_p ddr1 default_250mhz_clk2_clk_p} {
  dict set groups $key [lsort [cq_names [get_clocks -include_generated_clocks -of_objects [get_ports $port]]]]
 }
 lassign [cq_target_identity $outdir $groups] targets path_dict scopes
 cq_capture_complements $outdir $groups $targets $path_dict
 exec $python $helper replacement [file join $outdir target_identity.json] [file join $outdir user_group_replacement.xdc]
 set patch [exec $python $helper patch [file join $outdir original_timing_all.xdc] [file join $outdir user_group_replacement.xdc] [file join $outdir corrected_timing_all.xdc]]
 set f [open [file join $outdir exact_patch_identity.json] w];puts $f $patch;close $f
 puts {CQ_STAGE ZERO_DIFFERENCE_REPLAY_STARTED}
 reset_timing -invalid
 read_xdc [file join $outdir original_timing_all.xdc]
 set replay_clocks [cq_clocks $outdir zero_replay]
 if {$original_clocks ne $replay_clocks} {error {zero replay changed native clock identity}}
 write_xdc -type timing -constraints ALL -no_tool_comments [file join $outdir zero_replay_timing_all.xdc]
 set a [open [file join $outdir original_timing_all.xdc] r];set b [open [file join $outdir zero_replay_timing_all.xdc] r]
 set same [expr {[read $a] eq [read $b]}];close $a;close $b
 if {!$same} {error {zero replay changed exported complete timing constraints}}
 report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -max_paths 10 -file [file join $outdir zero_replay_timing_summary.rpt]
 exec $python $helper compare-timing $parent_timing [file join $outdir zero_replay_timing_summary.rpt]
 set replay_sync [cq_sync_paths $outdir zero_replay [get_clocks -quiet *]]
 if {$original_sync ne $replay_sync} {error {zero replay changed same-clock max/min paths}}
 puts {CQ_STAGE ZERO_DIFFERENCE_REPLAY_PASS}
 reset_timing -invalid
 read_xdc [file join $outdir corrected_timing_all.xdc]
 set corrected_clocks [cq_clocks $outdir corrected]
 if {$original_clocks ne $corrected_clocks} {error {correction changed clock identity}}
 cq_target_timing $outdir $path_dict $scopes
 puts {CQ_STAGE ALL138_FINITE_MAX_DPO_PASS}
 set corrected_sync [cq_sync_paths $outdir corrected [get_clocks -quiet *]]
 if {$original_sync ne $corrected_sync} {error {correction changed same-clock max/min paths}}
 report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -max_paths 10 -file [file join $outdir corrected_timing_summary.rpt]
 set acceptance [exec $python $helper assert-timing [file join $outdir corrected_timing_summary.rpt]]
 set f [open [file join $outdir corrected_active_timing_acceptance.json] w];puts $f $acceptance;close $f
 report_clock_interaction -delay_type min_max -file [file join $outdir corrected_clock_interaction.rpt]
 report_cdc -details -file [file join $outdir corrected_cdc.rpt]
 check_timing -verbose -file [file join $outdir corrected_check_timing.rpt]
 write_xdc -constraints ALL -no_tool_comments [file join $outdir corrected_complete_all.xdc]
 write_checkpoint [file join $outdir corrected_routed.dcp]
 puts {CQ_STAGE CORRECTED_ROUTED_CHECKPOINT_WRITTEN}
 close_design
 puts NATIVE_GU_ROUTED_CONSTRAINT_QUALIFICATION_COMPLETED
}
cq_main
