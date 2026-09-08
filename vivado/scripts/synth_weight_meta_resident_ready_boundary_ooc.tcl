set script_dir [file dirname [file normalize [info script]]]
set root [file normalize [file join $script_dir ../..]]
set out [file normalize $::env(HAP_REPORT_DIR)]
set part xcvu9p-flga2104-2L-e
file mkdir $out

if {![string match "2025.2*" [version -short]]} {
    error "Vivado 2025.2 required"
}

create_project -in_memory -part $part
read_verilog -sv [file join $root rtl attention \
    hap_weight_meta_resident.sv]
read_xdc [file join $root vivado constraints \
    weight_meta_resident_ooc_150mhz.xdc]
synth_design -top hap_weight_meta_resident -part $part \
    -mode out_of_context
opt_design

set uram [get_cells -quiet -hierarchical -filter {REF_NAME == URAM288}]
set dsp [get_cells -quiet -hierarchical -filter {REF_NAME == DSP48E2}]
set local_open [get_cells -quiet -hierarchical -filter \
    {NAME =~ *rd_port_open_r_reg*}]
set ready_to_uram [get_timing_paths -quiet -from \
    [get_ports rsp_ready] -to $uram -max_paths 1]
set exceptions [report_exceptions -coverage -return_string]
set forbidden_exception 0
if {[regexp -nocase {false path|datapath-only} $exceptions]} {
    set forbidden_exception 1
}
set status [expr {[llength $uram] == 80 && [llength $dsp] == 0 &&
    [llength $local_open] >= 1 && [llength $ready_to_uram] == 0 &&
    !$forbidden_exception ? "PASS" : "FAIL"}]

report_utilization -file [file join $out utilization_post_opt.rpt]
report_timing_summary -delay_type min_max -max_paths 20 \
    -report_unconstrained -file [file join $out timing_post_opt.rpt]
report_exceptions -coverage -file \
    [file join $out exceptions_coverage.rpt]
report_drc -file [file join $out drc_post_opt.rpt]
write_checkpoint -force [file join $out post_opt.dcp]

set fp [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] part $part \
        top hap_weight_meta_resident uram288 [llength $uram] \
        dsp48e2 [llength $dsp] local_ready_registers [llength $local_open] \
        rsp_ready_to_uram_paths [llength $ready_to_uram] \
        forbidden_exception $forbidden_exception status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "PASS"} {
    error "Attention metadata ready-boundary OOC contract failed"
}
