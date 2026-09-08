foreach variable {HAP_ROOT HAP_REPORT_DIR HAP_BUILD_DIR HAP_JOBS} {
    if {![info exists ::env($variable)] || $::env($variable) eq ""} {
        error "Missing required environment variable $variable"
    }
}

set root [file normalize $::env(HAP_ROOT)]
set out [file normalize $::env(HAP_REPORT_DIR)]
set build [file normalize $::env(HAP_BUILD_DIR)]
set jobs $::env(HAP_JOBS)
set part xcvu9p-flga2104-2L-e
set top hap_attention_cohort16_context_store_ooc_wrapper
set rtl [file join $root rtl attention hap_attention_cohort16_local_stores.sv]
set wrapper [file join $root rtl attention \
    hap_attention_cohort16_context_store_ooc_wrapper.sv]

set_param general.maxThreads $jobs
create_project context_store_ooc $build -part $part -force
set_property target_language Verilog [current_project]
read_verilog -sv [list $rtl $wrapper]
set_property top $top [current_fileset]
update_compile_order -fileset sources_1

set_msg_config -id {Synth 8-4445} -new_severity ERROR
set_msg_config -id {Synth 8-3848} -new_severity ERROR
set_msg_config -id {Synth 8-6901} -new_severity ERROR
synth_design -top $top -part $part -mode out_of_context \
    -flatten_hierarchy none -directive AreaOptimized_high
write_checkpoint -force [file join $out post_synth.dcp]
report_utilization -hierarchical -hierarchical_depth 4 \
    -file [file join $out utilization_post_synth.rpt]

opt_design -directive ExploreWithRemap
write_checkpoint -force [file join $out post_opt.dcp]
report_utilization -hierarchical -hierarchical_depth 4 \
    -file [file join $out utilization_post_opt.rpt]
write_verilog -force -mode funcsim \
    [file join $out context_store_post_opt_funcsim.v]

set context_instances [get_cells -quiet -hierarchical -filter {
    ORIG_REF_NAME == hap_attention_cohort16_context_store ||
    REF_NAME == hap_attention_cohort16_context_store
}]
set ramb36 [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB36E2}]
set ramb18 [get_cells -quiet -hierarchical -filter {REF_NAME == RAMB18E2}]
set lutram [get_cells -quiet -hierarchical -filter {
    REF_NAME =~ RAMD* || REF_NAME =~ RAMS*
}]
set dsp [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]
set uram [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]
set clb_lut [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]
set ff [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]
set status [expr {
    [llength $context_instances] == 1 &&
    [llength $ramb36] == 44 &&
    [llength $ramb18] == 0 &&
    [llength $lutram] == 0 &&
    [llength $dsp] == 0 &&
    [llength $uram] == 0 ?
    "ATTENTION_COHORT16_CONTEXT_STORE_OOC_PASS" : "FAIL"
}]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part $part top $top jobs $jobs \
    context_store_instances [llength $context_instances] \
    ramb36e2 [llength $ramb36] ramb18e2 [llength $ramb18] \
    lutram_primitives [llength $lutram] dsp48e2 [llength $dsp] \
    uram288 [llength $uram] lut_primitives [llength $clb_lut] \
    ff_primitives [llength $ff] status $status] {
    puts $fp "$key=$value"
}
close $fp

puts "CONTEXT_STORE_OOC INSTANCE=[llength $context_instances] RAMB36=[llength $ramb36] RAMB18=[llength $ramb18] LUTRAM=[llength $lutram] DSP=[llength $dsp] URAM=[llength $uram] STATUS=$status"
if {$status ne "ATTENTION_COHORT16_CONTEXT_STORE_OOC_PASS"} {
    error "Attention cohort16 context-store OOC resource gate failed"
}
close_project
