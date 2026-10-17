# Generated from frozen production controller by agent-owned prepare.py.
# Continue only an identified genuine project-init, post-OPT, or physopt checkpoint.
set script_dir [file normalize $::env(SLR2_REUSED_SCRIPT_DIR)]
set project_dir [file normalize $::env(HAP_PROJECT_DIR)]
set report_dir [file normalize $::env(HAP_REPORT_DIR)]
set stage $::env(HAP_STAGE)
if {$stage ni {place route} || $::env(HAP_EXECUTION_MODE) ne "checkpoint_restored_commands"} {error "Invalid recovery execution mode"}
if {![string match "2025.2*" [version -short]]} {error "Expected Vivado 2025.2"}
source [file join $script_dir m002_diagnostic_common.tcl]
source $::env(SLR2_HOOKS)
set_param general.maxThreads 8
open_project [file join $project_dir scalellm_vcu118_f05.xpr]
require_disabled_ip_cache
write_identity [file join $report_dir effective_build_identity.txt]
if {[hash_file [file join $report_dir effective_build_identity.txt]] ne [hash_file [file join $::env(HAP_SYNTH_REPORT_DIR) build_identity.txt]]} {error "Recovery original project synthesis identity changed"}
m002_dump_xdc project
exec python3 $::env(SLR2_ADAPTER) constraints project $report_dir
set run [get_runs impl_1]
set h [open [file join $report_dir implementation_settings.txt] w]
foreach property [lsort [list_property $run]] {puts $h "$property=[m002_prop $run $property]"}
close $h
m002_put [file join $report_dir implementation_settings_scope.txt] "scope=candidate_project_settings\neffective_execution=archived_m002_resume_physical.tcl_and_actual_command_receipts\noriginal_impl_1_status=FAIL"
# Original impl_1 remains failed. This flow never writes success receipts there.
close_project
open_checkpoint $::env(HAP_RECOVERY_CHECKPOINT)
set design [current_design]
set actual_project [current_project]
set actual_fileset [current_fileset]
set h [open [file join $report_dir restored_design_properties.tsv] w]
foreach object [concat [list $design $actual_project] [get_filesets -quiet *]] {
    puts $h "OBJECT\t$object"
    if {[catch {set properties [lsort [list_property $object]]} issue]} {puts $h "PROPERTY_ERROR\t$object\t$issue";continue}
    foreach property $properties {
        if {[catch {set value [m002_prop $object $property]} issue]} {puts $h "PROPERTY_ERROR\t$object\t$property\t$issue"} else {puts $h "$object\t$property\t$value"}
    }
}
close $h
# open_checkpoint creates a temporary project with its own defaults. Restore
# the execution policy there; candidate XPR settings do not configure it.
set restored_cache_before [get_property IP_CACHE_PERMISSIONS $actual_project]
set restored_repo [get_property IP_OUTPUT_REPO $actual_project]
set_property IP_CACHE_PERMISSIONS disable $actual_project
set restored_cache_after [require_disabled_ip_cache]
m002_put [file join $report_dir restored_runtime_settings.txt] "scope=actual_checkpoint_project\nproject=$actual_project\nip_cache_before=$restored_cache_before\nip_cache_after=$restored_cache_after\nip_output_repo=$restored_repo\nthreads=[get_param general.maxThreads]"
m002_put [file join $report_dir restored_checkpoint_mode.txt] "execution_mode=checkpoint_restored_commands\nconstraint_mode=embedded_checkpoint_inherited\ncheckpoint=$::env(HAP_RECOVERY_CHECKPOINT)\noriginal_impl_1_status=FAIL_not_reinterpreted"
# NAME identifies an in-memory design and need not equal the logical RTL top.
# Package top/part/board/tool+hash were checked before starting Vivado.
set preflight_issues [list]
set actual_part [get_property PART $actual_project]
if {$actual_part ne "xcvu9p-flga2104-2L-e"} {lappend preflight_issues "actual_project_part=$actual_part"}
set actual_top [get_property -quiet TOP $actual_fileset]
if {$actual_top ne "" && $actual_top ne "scalellm_vcu118_f05_bd_wrapper"} {lappend preflight_issues "actual_fileset_top=$actual_top"}
set design_part [m002_prop $design PART]
set design_top [m002_prop $design TOP]
if {$design_part ne "" && $design_part ne "xcvu9p-flga2104-2L-e"} {lappend preflight_issues "actual_design_part=$design_part"}
if {$design_top ne "" && $design_top ne "scalellm_vcu118_f05_bd_wrapper"} {lappend preflight_issues "actual_design_top=$design_top"}
set root [m002_exact get_cells scalellm_vcu118_f05_bd_i]
if {[llength $root] != 1 || [get_property REF_NAME $root] ne "scalellm_vcu118_f05_bd"} {lappend preflight_issues "actual_bd_root=$root"}
set h [open [file join $report_dir restored_preflight.tsv] w]
puts $h "DESIGN_OBJECT\t$design\nACTUAL_PROJECT_PART\t$actual_part\nACTUAL_FILESET_TOP\t$actual_top\nBD_ROOT\t$root"
puts $h "ACTUAL_DESIGN_PART\t$design_part\nACTUAL_DESIGN_TOP\t$design_top"
if {[llength $root] == 1} {puts $h "BD_ROOT_REF\t[get_property REF_NAME $root]"}
source [file join $report_dir probe_targets.tcl]
foreach target $::m002_cdc_targets {
    set exact [list]
    if {[catch {set exact [m002_exact get_pins $target]} issue]} {lappend preflight_issues "target_query_error=$target $issue"}
    puts $h "TARGET\t$target\tEXACT_NAME_MATCHES=[llength $exact]\t$exact"
    if {[llength $exact] == 1} {
        set cell [get_cells -quiet -of_objects $exact]
        puts $h "TARGET_OBJECT\tNAME=[get_property NAME $exact]\tREF_PIN_NAME=[get_property REF_PIN_NAME $exact]\tCELL=$cell\tREF_NAME=[get_property REF_NAME $cell]"
    }
    if {[llength $exact] != 1 || [get_property NAME $exact] ne $target} {
        lappend preflight_issues "target=$target matches=[llength $exact]"
        set prefix [file dirname [file dirname $target]]
        set cells [get_cells -quiet -hier -filter [format {NAME =~ %s/*} $prefix]]
        puts $h "TARGET_SCOPE\t$prefix\tCELLS=[llength $cells]"
        foreach cell $cells {puts $h "SCOPE_CELL\t$cell\t[get_property REF_NAME $cell]"}
    }
}
foreach {name direction} {pcie_perstn IN ddr4_sdram_c1_reset_n OUT ddr4_sdram_c2_reset_n OUT} {
    if {[catch {
        set port [get_ports -quiet $name]
        puts $h "RESET_PORT\t$name\tMATCHES=[llength $port]\tDIRECTION=[m002_prop $port DIRECTION]"
        if {[llength $port] != 1 || [get_property DIRECTION $port] ne $direction} {lappend preflight_issues "reset_port=$name"}
    } issue]} {puts $h "RESET_PORT_ERROR\t$name\t$issue";lappend preflight_issues "reset_port_query=$name"}
}
foreach {port primary generated} {pcie_refclk_p 10.000 10.000 default_250mhz_clk1_clk_p 4.000 5.000 default_250mhz_clk2_clk_p 4.000 5.000} {
    if {[catch {
        set family [require_clock_family $port $primary $generated]
        puts $h "CLOCK_FAMILY\t$port\t$family"
        foreach clock $family {puts $h "CLOCK_PERIOD\t$port\t$clock\t[get_property PERIOD $clock]"}
    } issue]} {puts $h "CLOCK_FAMILY_ERROR\t$port\t$issue";lappend preflight_issues "clock_family=$port"}
}
if {[catch {
    set bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]
    puts $h "BLACKBOX_COUNT\t[llength $bb]\t$bb"
    m002_debug_probe restore $bb
} issue]} {puts $h "DEBUG_ERROR\t$issue";lappend preflight_issues debug_query}
foreach {gate module} {core_gate u_base_reset_cdc core_gate u_ready0_cdc core_gate u_ready1_cdc d0_gate u_base_reset_cdc d0_gate u_ready_cdc d1_gate u_base_reset_cdc d1_gate u_ready_cdc} {
    set prefix scalellm_vcu118_f05_bd_i/$gate/inst/$module
    set cells [get_cells -quiet -hier -filter [format {NAME =~ %s/arststages_ff_reg*} $prefix]]
    puts $h "ASYNC_CHAIN_COUNT\t$prefix\t[llength $cells]"
    set sequential [filter $cells {IS_SEQUENTIAL == 1}]
    puts $h "ASYNC_SEQUENTIAL_COUNT\t$prefix\t[llength $sequential]"
    if {[llength $sequential] != 4} {lappend preflight_issues "async_chain_count=$prefix"}
    foreach cell $cells {puts $h "CHAIN_CELL\t$cell\t[get_property REF_NAME $cell]\tPINS=[llength [get_pins -quiet -of_objects $cell]]"}
}
foreach ddr {0 1} {
    foreach psr {psr0 psr_aclk1} {
        set prefix scalellm_vcu118_f05_bd_i/d${ddr}_smc/inst/clk_map/$psr/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX
        set cells [get_cells -quiet -hier -filter [format {NAME =~ %s/syncstages_ff_reg*} $prefix]]
        puts $h "AUX_CHAIN_COUNT\t$prefix\t[llength $cells]"
        set sequential [filter $cells {IS_SEQUENTIAL == 1}]
        puts $h "AUX_SEQUENTIAL_COUNT\t$prefix\t[llength $sequential]"
        if {[llength $sequential] != 4} {lappend preflight_issues "aux_chain_count=$prefix"}
    }
    set pattern "*/d${ddr}_smc/inst/s00_nodes/s00_w_node/inst/inst_mi_handler/gen_normal_area.gen_fifo_req.inst_fifo_req/gen_xpm_memory_fifo.inst_fifo/gen_mem_rep*.inst_xpm_memory/xpm_memory_base_inst/*doutb*reg*"
    set cells [get_cells -quiet -hier -filter [format {NAME =~ %s} $pattern]]
    puts $h "XPM_COUNT\td${ddr}\t[llength $cells]"
    if {![llength $cells]} {lappend preflight_issues "xpm_target_scope=d${ddr}"}
    foreach cell $cells {puts $h "XPM_CELL\t$cell\t[get_property REF_NAME $cell]\tIS_SEQUENTIAL=[m002_prop $cell IS_SEQUENTIAL]"}
}
set local scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11/g_dual_accumulator.u_accumulator
foreach pattern {*head_wave* *tail_wave* *lockstep_error_r_reg*} {
    set cells [get_cells -quiet -hier -filter [format {NAME =~ %s/%s} $local $pattern]]
    puts $h "HEAD_LOCAL_COUNT\t$pattern\t[llength $cells]"
}
puts $h "PREFLIGHT_ISSUES\t$preflight_issues"
close $h
if {[llength $preflight_issues]} {error "Restored identity/object preflight failed: $preflight_issues"}
proc m002_command {point command} {
    set start [clock seconds]
    if {$point eq "route" && [info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation"} {
        source [file join $::script_dir m002_route_failure_capture.tcl]
        set rc [catch {m002_route_with_failure_capture $command} result options]
    } else {
        set rc [catch {uplevel #0 $command} result options]
    }
    m002_put [file join $::m002_report_dir ${point}_command_result.txt] "phase=$point\ncommand=$command\nstarted_epoch=$start\nended_epoch=[clock seconds]\nnative_tcl_code=$rc"
    if {$rc} {return -options $options $result}
}
# Direct commands do not load/read an incremental checkpoint.
set runtime_runs [get_runs -quiet impl_1]
if {[llength $runtime_runs]} {
    set_property AUTO_INCREMENTAL_CHECKPOINT 0 $runtime_runs
    set_property INCREMENTAL_CHECKPOINT {} $runtime_runs
}
set h [open [file join $report_dir candidate_runtime_policy.tsv] {WRONLY CREAT EXCL}]
puts $h "actual_project\t[current_project]\nthreads\t[get_param general.maxThreads]\nip_cache\t[require_disabled_ip_cache]\nexecution\tdirect_commands_no_incremental_checkpoint_read\nplace_directive\tSSI_SpreadSLLs\nphysopt_directive\tDefault\nroute_directive\tDefault"
foreach run $runtime_runs {puts $h "runtime_run\t$run\tauto_incremental=[m002_prop $run AUTO_INCREMENTAL_CHECKPOINT]\tincremental_checkpoint=[m002_prop $run INCREMENTAL_CHECKPOINT]"}
close $h
slr2::topology
slr2::resolve pre_place
slr2::constrain
slr2::cut pre_place
slr2::scoped_timing pre_place
if {$stage eq "place"} {
    set restore_placed [expr {$::env(HAP_RECOVERY_PHASE) eq "post_place_pre_physopt"}]
    if {$restore_placed} {
        m002_command pre_place_restore m002_live_pre_place_restore
        exec python3 $::env(SLR2_ADAPTER) physical-resume live $report_dir
    } elseif {$::env(HAP_RECOVERY_PHASE) eq "post_debug_pre_place"} {
        m002_command pre_place_restore m002_live_pre_place_restore
        exec python3 $::env(SLR2_ADAPTER) pre-place restored_pre_place $report_dir
    } else {
    if {$::env(HAP_RECOVERY_PHASE) eq "project_init_after_link_before_opt"} {
        m002_post init
        m002_command opt opt_design
    } elseif {$::env(HAP_RECOVERY_PHASE) ne "post_opt_pre_debug"} {error "Unsupported physical recovery phase"}
    m002_post opt
    set h [open [file join $report_dir opt_result.txt] r];set opt_admission [read $h];close $h
    # An OPT PENDING disposition can authorize only the native debug step.
    if {[dict get [string map [list = " "] $opt_admission] completed] != 1 || [dict get [string map [list = " "] $opt_admission] debug_materialization_eligible] != 1} {error "OPT did not admit debug materialization"}
    set cores [get_debug_cores -quiet]
    m002_put [file join $report_dir debug_materialization_condition.txt] "debug_core_count=[llength $cores]\ndebug_cores=$cores\ncondition=actual_get_debug_cores_nonempty"
    if {[llength $cores] > 0} {
        m002_command debug_materialization implement_debug_core
    } else {
        m002_command debug_materialization {set ::m002_debug_skipped no_debug_cores}
    }
    m002_post debug_materialized
    exec python3 $::env(SLR2_ADAPTER) pre-place debug_materialized $report_dir
    }
    set optimized [expr {[info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation"}]
    if {!$restore_placed} {
        if {$optimized} {m002_command place {place_design -directive SSI_SpreadSLLs}} else {m002_command place place_design}
    }
    slr2::post_phase place
    if {$optimized} {m002_command physopt {phys_opt_design -directive Default}} else {m002_command physopt phys_opt_design}
    slr2::post_phase physopt
    set route_code [catch {m002_command route {route_design -directive Default}} route_result route_options]
    if {$route_code} {
        # Original failure is already captured by the unchanged route wrapper.
        set capture_code [catch {slr2::phase route_failed} capture_result capture_options]
        m002_put [file join $report_dir candidate_failed_route_capture.txt] [list code $capture_code result $capture_result options $capture_options]
        return -options $route_options $route_result
    }
    slr2::post_phase route
    set checkpoint [file join $report_dir route.dcp]
} else {
    # Explicitly restore the qualified physopt DCP of this execution mode.
    if {[info exists ::env(HAP_EXECUTION_PROFILE)] && $::env(HAP_EXECUTION_PROFILE) eq "m002_optimized_implementation"} {m002_command route {route_design -directive Default}} else {m002_command route route_design}
    m002_post route
    set checkpoint [file join $report_dir route.dcp]
}
m002_put [file join $report_dir implementation_checkpoint.sha256] "[hash_file $checkpoint]  $checkpoint"
close_design
puts "M002_SLR2_FULL_IMPLEMENTATION_CONTROLLER_COMPLETED physical_signoff=false"
