set out [file normalize $::env(HAP_REPORT_DIR)]
open_checkpoint [file join $out post_opt.dcp]

set timing_text [report_timing_summary -delay_type min_max -max_paths 10 \
    -report_unconstrained -warn_on_violation -return_string]
proc check_timing_count {text label} {
    if {![regexp -line -- "checking ${label} \\(([0-9]+)\\)" \
            $text -> count]} {
        error "Missing check_timing category $label"
    }
    return $count
}
set no_clock [check_timing_count $timing_text no_clock]
set unconstrained [check_timing_count $timing_text \
    unconstrained_internal_endpoints]
set lut [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ FD*}]]
set ramb36 [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB36E2}]]
set ramb18 [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == RAMB18E2}]]
set dsp [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == DSP48E2}]]
set uram [llength [get_cells -quiet -hierarchical -filter \
    {REF_NAME == URAM288}]]
set status [expr {$ramb36 == 96 && $ramb18 == 0 && $dsp == 0 &&
    $uram == 0 && $no_clock == 0 && $unconstrained == 0 ? "PASS" : "FAIL"}]
set fp [open [file join $out summary.txt] w]
foreach {key value} [list \
    tool [version -short] part xcvu9p-flga2104-2L-e \
    top hap_mlp_gate_up_gather_pingpong12 \
    groups 128 block_width 10 bank_depth 1024 \
    expected_ramb36 96 lut_primitives $lut ff_primitives $ff \
    ramb36e2 $ramb36 ramb18e2 $ramb18 dsp48e2 $dsp uram288 $uram \
    no_clock_endpoints $no_clock unconstrained_paths $unconstrained \
    status $status] {
    puts $fp "$key=$value"
}
close $fp
if {$status ne "PASS"} {
    error "V5 gate/up ping-pong gather post-opt structure audit failed"
}
