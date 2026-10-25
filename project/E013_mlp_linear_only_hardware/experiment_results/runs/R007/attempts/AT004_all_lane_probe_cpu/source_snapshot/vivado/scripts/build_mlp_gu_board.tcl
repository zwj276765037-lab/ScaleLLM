set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
source [file join $script_dir m006_system_python.tcl]
puts [m006_python [file join $script_dir m006_gu_entry.py] check]

# Quality evidence is distinct from a successful native Tcl process. Commands
# and flags below were checked against the installed Vivado2025.2 Tcl manuals.
proc m006_quality_json {path data} {
 set encoded [m006_python -c {import json,sys
root={};it=iter(sys.argv[1:])
for key,value in zip(it,it):
 try: value=json.loads(value)
 except (ValueError,TypeError): pass
 node=root;parts=key.split('.')
 for part in parts[:-1]: node=node.setdefault(part,{})
 node[parts[-1]]=value
print(json.dumps(root,indent=2))} {*}$data]
 set f [open $path w];puts $f $encoded;close $f
}
proc m006_q {key value} {global quality;dict set quality $key $value}
proc m006_expected_cell {out label path expected_ref} {
 set cells [get_cells -quiet $path]
 puts $out "$label.expected_path=$path expected_type=$expected_ref count=[llength $cells]"
 if {[llength $cells]!=1} {return {}}
 set ref [get_property REF_NAME $cells]
 puts $out "$label.actual_ref=$ref"
 # OOC module references receive a project/IP prefix. Match the complete
 # expected type suffix at the exact frozen instance, not an arbitrary glob.
 if {$ref ne $expected_ref && ![string match "*_$expected_ref" $ref]} {return {}}
 return $cells
}
proc m006_report {label command path} {
 if {[catch {uplevel 1 $command} detail]} {
  m006_q $label.native_status FAIL;m006_q $label.native_error $detail
  return 0
 }
 if {![file isfile $path] || [file size $path]==0} {
  m006_q $label.native_status FAIL;m006_q $label.native_error missing_or_empty_report
  return 0
 }
 m006_q $label.native_status COMPLETE;m006_q $label.report $path
 m006_q $label.sha256 [lindex [exec sha256sum -- $path] 0]
 return 1
}
proc m006_netlist_identity {report_dir} {
 global stage
 set out [open [file join $report_dir netlist_identity.txt] w]
 set base scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute
 set attention [m006_expected_cell $out attention $base/u_attention hap_attention_board_cohort16_core]
 set kernel [m006_expected_cell $out shared_kernel $base/u_mlp/u_shared_compute hap_mlp_gu_dual_slice16x12_s44]
 set banned [get_cells -quiet -hierarchical -filter {REF_NAME =~ *hap_mlp_hadamard* || REF_NAME =~ *hap_mlp_swiglu* || REF_NAME =~ *hap_mlp_silu_mul* || REF_NAME =~ *hap_mlp_robust_a8_quantizer* || REF_NAME =~ *hap_mlp_input_frontend* || REF_NAME =~ *hap_mlp_product_frontend* || REF_NAME =~ *hap_mlp_full_command* || REF_NAME =~ *hap_mlp_serial_ddr_command*}]
 set sample [lindex [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE == 1}] 0]
 set blackbox_query_available [expr {$sample ne "" && [lsearch -exact [list_property $sample] IS_BLACKBOX]>=0}]
 if {$blackbox_query_available} {set blackboxes [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1}]} else {set blackboxes unavailable}
 foreach {label objects} [list attention $attention shared_kernel $kernel forbidden_mlp $banned blackboxes $blackboxes] {
  puts $out "$label.count=[llength $objects]"
  foreach cell $objects {
   if {$cell eq "unavailable"} {puts $out "blackbox_query=unavailable";continue}
   puts $out "$label.cell=$cell ref=[get_property REF_NAME $cell]"
  }
 }
 set debug_placeholder {};set unresolved {}
 if {$blackbox_query_available} {
  foreach cell $blackboxes {
   if {$stage eq "synth" && $cell eq "dbg_hub" && [get_property REF_NAME $cell] eq "dbg_hub_CV"} {lappend debug_placeholder $cell} else {lappend unresolved $cell}
  }
 }
 puts $out "pre_opt_debug_placeholder=$debug_placeholder unresolved_user_blackboxes=$unresolved"
 puts $out {debug_policy=Only exact dbg_hub/dbg_hub_CV is a pre-opt placeholder; every post-opt blackbox is rejected.}
 close $out
 m006_q netlist.attention_cells [llength $attention]
 m006_q netlist.shared_kernel_cells [llength $kernel]
 m006_q netlist.forbidden_mlp_cells [llength $banned]
 m006_q netlist.blackbox_query_available $blackbox_query_available
 m006_q netlist.blackbox_cells [expr {$blackbox_query_available?[llength $blackboxes]:-1}]
 m006_q netlist.unresolved_user_blackboxes [llength $unresolved]
 m006_q netlist.pre_opt_debug_placeholder_cells [llength $debug_placeholder]
 m006_q netlist.debug_placeholder_scope [expr {[llength $debug_placeholder] ? "PENDING_NATIVE_OPT_IMPLEMENTATION" : "NONE"}]
 m006_q netlist.report [file join $report_dir netlist_identity.txt]
 set ok [expr {[llength $attention]==1 && [llength $kernel]==1 && [llength $banned]==0 && $blackbox_query_available && [llength $unresolved]==0 && [llength $debug_placeholder]<=1}]
 m006_q netlist.status [expr {$ok?"PASS":"FAIL"}]
 return $ok
}
proc m006_clock_identity {report_dir} {
 set out [open [file join $report_dir clock_identity.txt] w]
 set wrappers [m006_expected_cell $out wrapper scalellm_vcu118_f05_bd_i/core/inst hap_attention_mlp_board_core_gu_only]
 set ok [expr {[llength $wrappers]>0}]
 foreach {label pin_name expected_ns} {core core_clk 10.0 ddr0 ddr0_clk 5.0 ddr1 ddr1_clk 5.0} {
  set pins {}
  # Keep Vivado's native object collection; lappend/concat converts it into
  # strings that -of_objects correctly refuses in Vivado2025.2.
  if {[llength $wrappers]==1} {set pins [get_pins -quiet [lindex $wrappers 0]/$pin_name]}
  set clocks {}
  if {[llength $pins]} {set clocks [get_clocks -quiet -of_objects $pins]}
  set domain_ok [expr {[llength $pins]>0 && [llength $clocks]==1}]
  puts $out "$label.pins=$pins"
  puts $out "$label.clocks=$clocks"
  m006_q clocks.$label.pins $pins;m006_q clocks.$label.clocks $clocks
  m006_q clocks.$label.expected_period_ns $expected_ns
  foreach clock $clocks {
   set period [get_property PERIOD $clock]
   puts $out "$label.clock=$clock period_ns=$period generated=[get_property IS_GENERATED $clock]"
   m006_q clocks.$label.period_ns $period
   if {![string is double -strict $period] || abs(double($period)-$expected_ns)>0.001} {set domain_ok 0}
  }
  m006_q clocks.$label.status [expr {$domain_ok?"PASS":"FAIL"}]
  if {!$domain_ok} {set ok 0}
 }
 close $out
 m006_q clocks.status [expr {$ok?"PASS":"FAIL"}]
 m006_q clocks.report [file join $report_dir clock_identity.txt]
 return $ok
}
proc m006_constraint_identity {report_dir} {
 set out [open [file join $report_dir constraint_identity.txt] w]
 foreach clock [lsort [get_clocks -quiet]] {puts $out "clock=$clock period=[get_property PERIOD $clock] generated=[get_property IS_GENERATED $clock]"}
 foreach port [lsort [get_ports -quiet]] {puts $out "port=$port package_pin=[get_property PACKAGE_PIN $port] iostandard=[get_property IOSTANDARD $port]"}
 close $out
 write_xdc -force [file join $report_dir effective_constraints.xdc]
 report_io -file [file join $report_dir io_identity.rpt]
 m006_q constraints.native_objects_report [file join $report_dir constraint_identity.txt]
 m006_q constraints.effective_xdc [file join $report_dir effective_constraints.xdc]
 m006_q constraints.status RECORDED_NATIVE_OBJECTS
}
proc m006_reset_cdc_identity {report_dir tag} {
 set out [open [file join $report_dir ${tag}_reset_cdc_identity.txt] w]
 set root scalellm_vcu118_f05_bd_i
 set paths [list $root/core_gate/inst/u_ready0_cdc/arststages_ff_reg $root/core_gate/inst/u_ready1_cdc/arststages_ff_reg]
 foreach domain {d0 d1} {
  foreach reset {psr0 psr_aclk1} {lappend paths $root/${domain}_smc/inst/clk_map/$reset/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg}
 }
 set ok 1;set total 0
 foreach path $paths {
  set previous {}
  for {set i 0} {$i<4} {incr i} {
   set name [format {%s[%d]} $path $i]
   set cell [get_cells -quiet $name]
   if {[llength $cell]!=1} {set ok 0;puts $out "missing_stage=$name";continue}
   incr total
   set ref [get_property REF_NAME $cell];set async [get_property ASYNC_REG $cell]
   set clocks [get_clocks -quiet -of_objects [get_pins -quiet $cell/C]]
   set stage_ok [expr {$ref in {FDRE FDSE FDCE FDPE} && [string is boolean -strict $async] && $async && [llength $clocks]==1}]
   foreach clock $clocks {if {abs(double([get_property PERIOD $clock])-10.0)>0.001} {set stage_ok 0}}
   set drivers {}
   if {$i>0} {
    set net [get_nets -quiet -of_objects [get_pins -quiet $cell/D]]
    set drivers [get_cells -quiet -of_objects [get_pins -quiet -leaf -of_objects $net -filter {DIRECTION == OUT}]]
    if {[lsearch -exact $drivers $previous]<0} {set stage_ok 0}
   }
   puts $out "stage=$cell ref=$ref async_reg=$async clocks=$clocks previous=$previous actual_D_drivers=$drivers pass=$stage_ok"
   if {!$stage_ok} {set ok 0};set previous $cell
  }
 }
 close $out
 m006_q ${tag}_reset_cdc.synchronizer_chains [llength $paths]
 m006_q ${tag}_reset_cdc.observed_stages $total
 m006_q ${tag}_reset_cdc.status [expr {$ok?"PASS":"FAIL"}]
 m006_q ${tag}_reset_cdc.scope six_reviewed_reset_level_paths_only_CDC10_native_findings_not_waived
 m006_q ${tag}_reset_cdc.report [file join $report_dir ${tag}_reset_cdc_identity.txt]
 if {!$ok} {error "Reviewed six reset CDC synchronizer structures did not match native identity"}
}
proc m006_post_opt_debug {report_dir} {
 if {![info exists ::env(HAP_DEBUG_TARGETS)]} {error "Post-opt debug target provenance missing"}
 set out [open [file join $report_dir post_opt_debug_identity.txt] w]
 set blackboxes [get_cells -quiet -hierarchical -filter {IS_BLACKBOX == 1}]
 puts $out "post_opt_blackboxes=$blackboxes"
 set ok [expr {[llength $blackboxes]==0}]
 foreach key {pre_opt_no_clock_pins pre_opt_unconstrained_endpoints} {
  set targets [split [m006_python -c {import json,sys;print("\n".join(json.load(open(sys.argv[1]))[sys.argv[2]]))} $::env(HAP_DEBUG_TARGETS) $key] "\n"]
  set found 0;set removed 0;set clocked 0;set missing 0
  foreach name $targets {
   set pin [get_pins -quiet $name]
   if {![llength $pin]} {incr removed;puts $out "$key.removed=$name";continue}
   incr found
   set cell [get_cells -quiet -of_objects $pin]
   set clock_pins [get_pins -quiet $cell/C]
   if {![llength $clock_pins]} {set clock_pins [get_pins -quiet $cell/CLK]}
   set clocks {}
   if {[llength $clock_pins]} {set clocks [get_clocks -quiet -of_objects $clock_pins]}
   if {[llength $clocks]} {incr clocked} else {incr missing;set ok 0}
   puts $out "$key.pin=$name cell=$cell clocks=$clocks"
  }
  puts $out "$key.total=[llength $targets] surviving=$found removed=$removed clocked=$clocked missing_clock=$missing"
  m006_q post_opt_debug.$key.total [llength $targets]
  m006_q post_opt_debug.$key.surviving $found;m006_q post_opt_debug.$key.removed $removed
  m006_q post_opt_debug.$key.clocked $clocked;m006_q post_opt_debug.$key.missing_clock $missing
 }
 close $out
 m006_q post_opt_debug.blackbox_count [llength $blackboxes]
 m006_q post_opt_debug.status [expr {$ok?"PASS":"FAIL"}]
 m006_q post_opt_debug.report [file join $report_dir post_opt_debug_identity.txt]
 if {!$ok} {error "Native post-opt debug blackbox/clock coverage failed before place"}
 m006_reset_cdc_identity $report_dir post_opt
}
proc m006_timing_metrics {report_dir} {
 foreach {kind delay} {setup max hold min} {
  if {[catch {get_timing_paths -delay_type $delay -max_paths 1} paths] || ![llength $paths]} {
   m006_q timing.$kind.status PENDING_REVIEW;m006_q timing.$kind.reason no_readable_native_timing_path
  } else {
   set slack [get_property SLACK [lindex $paths 0]]
   m006_q timing.$kind.worst_slack_ns $slack
   if {[string is double -strict $slack]} {m006_q timing.$kind.status [expr {$slack>=0?"PASS":"FAIL"}]} else {m006_q timing.$kind.status PENDING_REVIEW}
  }
 }
 set summary [file join $report_dir timing_summary.rpt]
 m006_q timing.aggregate_metrics_status PENDING_REVIEW
 if {[file isfile $summary]} {
  set f [open $summary r];set text [read $f];close $f
  set in_table 0
  foreach line [split $text "\n"] {
   if {[string match *WNS\(ns\)* $line] && [string match *TNS\(ns\)* $line]} {set in_table 1;continue}
   if {!$in_table} {continue}
   set words [regexp -all -inline {\S+} $line]
   if {[llength $words]<12} {continue}
   set numeric 1
   foreach index {0 1 2 3 4 5 6 7} {if {![string is double -strict [lindex $words $index]]} {set numeric 0}}
   if {!$numeric} {continue}
   foreach {index key} {0 wns_ns 1 tns_ns 2 setup_failing_endpoints 3 setup_total_endpoints 4 whs_ns 5 ths_ns 6 hold_failing_endpoints 7 hold_total_endpoints} {m006_q timing.$key [lindex $words $index]}
   m006_q timing.aggregate_metrics_status RECORDED_NATIVE_TABLE
   break
  }
 }
 set path [file join $report_dir check_timing.rpt]
 set ok [m006_report unconstrained [list check_timing -override_defaults {no_clock unconstrained_internal_endpoints no_input_delay no_output_delay} -file $path] $path]
 m006_q unconstrained.status PENDING_REVIEW
 if {$ok} {
  set f [open $path r];set text [read $f];close $f
  set found 0;set total 0
  foreach label {no_clock unconstrained_internal_endpoints no_input_delay no_output_delay} {
   set expression [format {checking\s+%s\s+\(([0-9]+)\)} $label]
   if {[regexp -nocase $expression $text whole count]} {incr found;incr total $count;m006_q unconstrained.$label $count}
  }
  if {$found==4} {m006_q unconstrained.status [expr {$total==0?"PASS":"FAIL"}]} else {m006_q unconstrained.reason native_check_report_requires_manual_count_review}
 }
}
proc m006_drc_metrics {report_dir} {
 set errors 0;set warnings 0;set unknown 0
 set out [open [file join $report_dir drc_native_objects.txt] w]
 foreach object [get_drc_violations -quiet] {
  set severity unavailable
  if {[lsearch -exact [list_property $object] SEVERITY]>=0} {set severity [get_property SEVERITY $object]}
  puts $out "$object severity=$severity"
  if {$severity in {Error {Critical Warning}}} {incr errors} elseif {$severity eq "Warning"} {incr warnings} elseif {$severity ne "Info"} {incr unknown}
 }
 close $out
 m006_q drc.error_or_critical_count $errors;m006_q drc.warning_count $warnings;m006_q drc.unknown_severity_count $unknown
 m006_q drc.status [expr {$errors>0?"FAIL":($warnings>0||$unknown>0?"PENDING_REVIEW":"PASS")}]
 m006_q drc.objects_report [file join $report_dir drc_native_objects.txt]
}

# New GU source graph is checked against actual synthesized hierarchy.
proc m006_gu_structure {report_dir} {
 set base scalellm_vcu118_f05_bd_i/core/inst/u_core
 set compute $base/u_compute/u_mlp
 set out [open [file join $report_dir gu_structure_identity.txt] w]
 set cache [m006_expected_cell $out cache128 $base/u_compute/u_cache hap_mlp_gu_cache16]
 set gu [m006_expected_cell $out gu_compute $compute hap_mlp_gu_compute16_s44]
 set meta [m006_expected_cell $out gu_metadata $base/u_meta_bank hap_mlp_gu_weight_meta_resident_ab]
 set banned [get_cells -quiet -hierarchical -filter {REF_NAME =~ *hap_mlp_down* || REF_NAME =~ *hap_mlp_linear_down* || REF_NAME =~ *hap_mlp_tile_accum_s45_s54* || REF_NAME =~ *hap_mlp_projection_repack12_to16_s32* || REF_NAME =~ *hap_a8w4_group32_lane2_s45* || REF_NAME =~ *hap_a8w4_slice8x12_group_s45* || REF_NAME =~ *hap_mlp_shared_dual_slice16x12_s44_s54* || NAME =~ */u_down_accum* || NAME =~ */u_down_repack* || NAME =~ */u_down_scheduler* || NAME =~ */u_down_bank*}]
 set dsps [get_cells -quiet -hierarchical -filter "NAME =~ $compute/u_shared_compute/* && REF_NAME =~ DSP48*"]
 set urams [get_cells -quiet -hierarchical -filter "NAME =~ $base/u_meta_bank/* && REF_NAME =~ URAM288*"]
 set lanes [get_cells -quiet -hierarchical -filter "NAME =~ $compute/u_shared_compute/* && REF_NAME =~ *hap_a8w4_gu_group32_lane2_s37*"]
 set lane_width_mismatches 0;set guard0_total 0;set guard1_total 0
 foreach lane $lanes {
  set pins0 [get_pins -quiet -of_objects [get_cells -quiet $lane] -filter {DIRECTION == OUT && REF_PIN_NAME =~ guard0_s37*}]
  set pins1 [get_pins -quiet -of_objects [get_cells -quiet $lane] -filter {DIRECTION == OUT && REF_PIN_NAME =~ guard1_s37*}]
  incr guard0_total [llength $pins0];incr guard1_total [llength $pins1]
  if {[llength $pins0]!=37 || [llength $pins1]!=37} {incr lane_width_mismatches}
  puts $out "lane=$lane guard0_bits=[llength $pins0] guard1_bits=[llength $pins1]"
 }
 puts $out "scope=actual_synthesized_hierarchy_not_text_search"
 puts $out "forbidden_down_cells=[llength $banned] mlp_dsp=[llength $dsps] gu_metadata_uram=[llength $urams] lane_instances=[llength $lanes]"
 puts $out "all_lane_width_mismatches=$lane_width_mismatches guard0_total_bits=$guard0_total guard1_total_bits=$guard1_total"
 puts $out {cache_depth_source=bound_new_RTL_memory_0_to_127; primitive_BRAM_depth_rounding_does_not_prove_logical_depth_or_savings}
 foreach cell $banned {puts $out "forbidden=$cell ref=[get_property REF_NAME $cell]"}
 close $out
 set ok [expr {[llength $cache]==1 && [llength $gu]==1 && [llength $meta]==1 && [llength $banned]==0 && [llength $dsps]==3072 && [llength $urams]==448 && [llength $lanes]==96 &&  $lane_width_mismatches==0 && $guard0_total==3552 && $guard1_total==3552}]
 foreach {label count} [list forbidden_down [llength $banned] mlp_dsp [llength $dsps] gu_metadata_uram [llength $urams] lanes [llength $lanes] lane_width_mismatches $lane_width_mismatches guard0_total_bits $guard0_total guard1_total_bits $guard1_total] {m006_q gu_structure.$label $count}
 m006_q gu_structure.status [expr {$ok?"PASS":"FAIL"}]
 m006_q gu_structure.report [file join $report_dir gu_structure_identity.txt]
 return $ok
}
proc m006_pre_opt_debug_targets {report_dir} {
 global root
 set reference [file join $root source mlp_gu_only debug_endpoint_reference.json]
 set out [open [file join $report_dir pre_opt_debug_identity.txt] w]
 foreach key {pre_opt_no_clock_pins pre_opt_unconstrained_endpoints} {
  set targets [split [m006_python -c {import json,sys;print("\n".join(json.load(open(sys.argv[1]))[sys.argv[2]]))} $reference $key] "\n"]
  foreach name $targets {
   if {![string match {scalellm_vcu118_f05_bd_i/ddr4_*} $name] || [string first /u_ddr_cal_top/u_ddr_cal/ $name]<0} {error "Debug endpoint reference outside DDR calibration"}
   set pin [get_pins -quiet $name]
   if {[llength $pin]!=1} {error "New DCP debug reference target missing: $name"}
   puts $out "$key.pin=$pin owner=[get_cells -quiet -of_objects $pin]"
  }
  puts $out "$key.validated_count=[llength $targets]"
 }
 close $out
 file copy -force $reference [file join $report_dir pre_opt_debug_targets.json]
}
proc m006_slr_pressure {report_dir tag} {
 # Same native implementation session, before route. No crossing-path scan.
 set path [file join $report_dir ${tag}_utilization_slr.rpt]
 m006_report ${tag}_slr [list report_utilization -slr -file $path] $path
 set base scalellm_vcu118_f05_bd_i/core/inst/u_core
 foreach {label name} [list attention $base/u_compute/u_attention metadata $base/u_meta_bank branch0 $base/u_compute/u_mlp/u_shared_compute/u_branch0 branch1 $base/u_compute/u_mlp/u_shared_compute/u_branch1] {
  set cells [get_cells -quiet $name]
  if {[llength $cells]!=1} {m006_q ${tag}_slr.$label.status MISSING_SCOPE;continue}
  set path [file join $report_dir ${tag}_${label}_utilization_slr.rpt]
  m006_report ${tag}_slr.$label [list report_utilization -slr -cells $cells -file $path] $path
 }
 set path [file join $report_dir ${tag}_congestion.rpt]
 m006_report ${tag}_congestion [list report_design_analysis -congestion -file $path] $path
}

foreach name {HAP_PROJECT_DIR HAP_REPORT_DIR HAP_STAGE} {
 if {![info exists ::env($name)]} {error "Missing $name"}
}
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
if {![string match [file join $root vivado project *] $project_dir] || ![file isdirectory $project_dir]} {error "Invalid M006 project"}
set_param general.maxThreads 8
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
config_ip_cache -disable_cache
set stage $::env(HAP_STAGE)
if {$stage ni {synth impl}} {error "Unknown M006 stage $stage"}
set quality [dict create stage $stage process.status RUNNING overall.status PENDING_REVIEW quality_is_native_exit_code false]
set stage_failed [catch {
if {$stage eq "synth"} {
 set bd_files [get_files -quiet "*/scalellm_vcu118_f05_bd.bd"]
 if {[llength $bd_files]!=1} {error "M006 board BD is not unique"}
 generate_target all $bd_files
 create_ip_run $bd_files
 set runs [lsort -unique [concat [get_runs synth_1] [get_runs -quiet -filter {NAME =~ *_synth_1}]]]
 set rom [file join $root data softmax_exp_u17.mem]
 set rom_sha [lindex [exec sha256sum -- $rom] 0]
 if {$rom_sha ne "3af91ffa7ead647b42b8440c9a098d84b0abb81ffdc09c96550c724bf7248967"} {error "Attention softmax ROM hash mismatch"}
 set rom_inputs [open [file join $report_dir attention_rom_inputs.sha256] w]
 foreach run $runs {
  set directory [file normalize [get_property DIRECTORY $run]]
  file mkdir [file join $directory data]
  set staged [file join $directory data softmax_exp_u17.mem]
  file copy -force -- $rom $staged
  if {[lindex [exec sha256sum -- $staged] 0] ne $rom_sha} {error "Attention ROM staging mismatch"}
  puts $rom_inputs "$rom_sha  $staged"
 }
 close $rom_inputs
 launch_runs synth_1 -jobs 4
 wait_on_run synth_1
 set status [get_property STATUS [get_runs synth_1]]
 if {![string match "synth_design Complete*" $status]} {error "Synthesis failed: $status"}
 foreach run $runs {
  set runlog [file join [get_property DIRECTORY $run] runme.log]
  if {[file isfile $runlog]} {
   set f [open $runlog r];set data [read $f];close $f
   if {[regexp -nocase {Synth[[:space:]]+8-4445} $data]} {error "Unresolved ROM warning in $runlog"}
  }
 }
 exec sha256sum --check --status [file join $report_dir attention_rom_inputs.sha256]
 open_run synth_1
 write_checkpoint -force [file join $report_dir synthesized.dcp]
 m006_pre_opt_debug_targets $report_dir
} elseif {$stage eq "impl"} {
 if {![info exists ::env(HAP_SYNTH_DCP)]} {error "HAP_SYNTH_DCP required"}
 open_checkpoint $::env(HAP_SYNTH_DCP)
 opt_design
 m006_post_opt_debug $report_dir
 write_checkpoint -force [file join $report_dir optimized.dcp]
 place_design
 write_checkpoint -force [file join $report_dir placed.dcp]
 m006_slr_pressure $report_dir placed
 phys_opt_design
 write_checkpoint -force [file join $report_dir physopt.dcp]
 m006_slr_pressure $report_dir physopt
 route_design
 write_checkpoint -force [file join $report_dir routed.dcp]
 report_route_status -file [file join $report_dir route_status.rpt]
} else {error "Unknown M006 stage $stage"}
} stage_detail stage_options]
m006_q process.status [expr {$stage_failed?"FAIL":"NATIVE_STAGE_COMPLETED"}]
if {$stage_failed} {m006_q process.error $stage_detail}

# Preserve report provenance and continue collecting independent diagnostics if
# one quality report fails. The native failure is re-raised after JSON is saved.
foreach {label command filename} {
 utilization {report_utilization -hierarchical} utilization_hierarchical.rpt
 timing {report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose} timing_summary.rpt
 clock_interaction {report_clock_interaction} clock_interaction.rpt
 cdc {report_cdc -details -no_waiver} cdc.rpt
 drc {report_drc} drc.rpt
} {
 set path [file join $report_dir $filename]
 m006_report $label [concat $command [list -file $path]] $path
}
m006_q cdc.status PENDING_REVIEW
m006_q cdc.reason native_topology_and_waiver_review_required_no_automatic_pass
set probes {netlist m006_netlist_identity clocks m006_clock_identity}
lappend probes timing_metrics m006_timing_metrics drc_metrics m006_drc_metrics gu_structure m006_gu_structure
foreach {label command} $probes {
 if {[catch {$command $report_dir} detail]} {
  m006_q $label.status PENDING_REVIEW;m006_q $label.collection_error $detail
 }
}
if {$stage eq "impl"} {
 set route_path [file join $report_dir route_status.rpt]
 m006_report route [list report_route_status -file $route_path] $route_path
 if {[catch {
  set placed [report_route_status -boolean_check PLACED_FULLY]
  set routed [report_route_status -boolean_check ROUTED_FULLY]
  set errors [report_route_status -boolean_check ERRORS_IN_ROUTES]
  foreach value [list $placed $routed $errors] {if {![string is boolean -strict $value]} {error "nonboolean route result: $value"}}
  m006_q route.placed_fully $placed;m006_q route.routed_fully $routed;m006_q route.errors_in_routes $errors
  m006_q route.status [expr {$placed&&$routed&&!$errors?"PASS":"FAIL"}]
 } detail]} {m006_q route.status PENDING_REVIEW;m006_q route.collection_error $detail}
} else {m006_q route.status NOT_RUN;m006_q route.reason synthesis_stage_only}
set overall PENDING_REVIEW
foreach {key value} $quality {
 if {[string match *.status $key] && $value eq "FAIL"} {set overall FAIL}
 if {[string match *.native_status $key] && $value eq "FAIL"} {set overall FAIL}
}
m006_q overall.status $overall
m006_q overall.reason native_completion_is_not_route_timing_DRC_CDC_acceptance
m006_quality_json [file join $report_dir stage_quality.json] $quality
if {$stage_failed} {return -options $stage_options $stage_detail}
if {[dict get $quality netlist.status] ne "PASS" || [dict get $quality clocks.status] ne "PASS" || [dict get $quality gu_structure.status] ne "PASS"} {
 error "M006 required native netlist/clock identity failed; inspect stage_quality.json"
}
puts "M006_NATIVE_STAGE_COMPLETE $stage"
puts "M006_QUALITY_STATUS $overall (see stage_quality.json)"
