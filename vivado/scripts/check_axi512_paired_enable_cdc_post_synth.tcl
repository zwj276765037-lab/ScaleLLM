if {![info exists ::env(HAP_CDC_DCP)] || ![info exists ::env(HAP_CDC_OUT)]} {
    error "HAP_CDC_DCP and HAP_CDC_OUT are required"
}
set dcp [file normalize $::env(HAP_CDC_DCP)]
set out [file normalize $::env(HAP_CDC_OUT)]
file mkdir $out
open_checkpoint $dcp
set report_path [file join $out cdc_post_synth.rpt]
report_cdc -details -file $report_path
set fh [open $report_path r]
set text [read $fh]
close $fh

set critical 0
foreach {whole count} [regexp -all -inline \
        {Critical[[:space:]]+([1-9][0-9]*)} $text] {
    incr critical $count
}
set enable0 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_enable0_cdc/syncstages_ff_reg* && ASYNC_REG == TRUE}]]
set enable1 [llength [get_cells -quiet -hierarchical -filter \
    {NAME =~ u_dut/u_enable1_cdc/syncstages_ff_reg* && ASYNC_REG == TRUE}]]
set raw0_fanout 0
foreach endpoint [all_fanout -flat -endpoints_only \
        -from [get_cells -quiet u_dut/u_enable0_cdc/src_ff_reg]] {
    if {![string match "u_dut/u_enable0_cdc/syncstages_ff_reg*" \
            [get_property NAME $endpoint]]} {incr raw0_fanout}
}
set raw1_fanout 0
foreach endpoint [all_fanout -flat -endpoints_only \
        -from [get_cells -quiet u_dut/u_enable1_cdc/src_ff_reg]] {
    if {![string match "u_dut/u_enable1_cdc/syncstages_ff_reg*" \
            [get_property NAME $endpoint]]} {incr raw1_fanout}
}
set status [expr {$critical == 0 && $enable0 == 2 && $enable1 == 2 &&
    $raw0_fanout == 0 && $raw1_fanout == 0 ? "PAIRED_ENABLE_CDC_PASS" :
    "PAIRED_ENABLE_CDC_FAIL"}]
set sf [open [file join $out summary.txt] w]
foreach {key value} [list tool [version -short] dcp $dcp \
    cdc_critical $critical enable0_async_ff $enable0 enable1_async_ff $enable1 \
    raw_enable0_non_sync_endpoints $raw0_fanout \
    raw_enable1_non_sync_endpoints $raw1_fanout status $status] {
    puts $sf "$key=$value"
}
close $sf
puts "PAIRED_ENABLE_CDC CRITICAL=$critical SYNC_FF=$enable0/$enable1 RAW_FANOUT=$raw0_fanout/$raw1_fanout STATUS=$status"
if {$status ne "PAIRED_ENABLE_CDC_PASS"} {
    error "Paired mode-enable CDC audit failed"
}
