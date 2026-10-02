set dcp [file normalize $::env(M7_DCP)]
set rd [file normalize $::env(M7_REPORT_DIR)]
set n $::env(M7_CASE_NAME)
file mkdir $rd
open_checkpoint $dcp
report_utilization -file [file join $rd utilization_post_route.rpt]
report_utilization -hierarchical -hierarchical_depth 12 \
    -file [file join $rd utilization_hier_post_route.rpt]
set qk [get_cells -quiet -hierarchical -filter {
    NAME =~ *u_qk && (REF_NAME =~ *qk* || ORIG_REF_NAME =~ *qk*)}]
if {[llength $qk] != 1} {
    error "expected exactly one physical QK slot, got [llength $qk]: $qk"
}
report_utilization -cells $qk \
    -file [file join $rd qk_slot_utilization_post_route.rpt]
report_timing_summary -delay_type min_max -max_paths 30 \
    -file [file join $rd timing_post_route.rpt]
report_route_status -file [file join $rd route_status.rpt]
set sp [lindex [get_timing_paths -quiet -delay_type max -max_paths 1] 0]
set hp [lindex [get_timing_paths -quiet -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $sp]
set whs [get_property SLACK $hp]
set unr [llength [get_nets -hierarchical -filter \
    {ROUTE_STATUS == UNROUTED || ROUTE_STATUS == PARTIALLY_ROUTED}]]
set drc_errors [llength [get_drc_violations -quiet -filter {SEVERITY == Error}]]
set error_messages [get_msg_config -count -severity ERROR]
set critical_warning_messages \
    [get_msg_config -count -severity {CRITICAL WARNING}]
set util [report_utilization -return_string]
set qk_util [report_utilization -cells $qk -return_string]
set row_lut NA
set row_ff NA
set row_dsp NA
set row_bram NA
set qk_lut NA
set qk_ff NA
set qk_dsp NA
set qk_bram NA
regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $util _ row_lut
regexp {\| CLB Registers\s+\|\s*([0-9]+)} $util _ row_ff
regexp {\| DSPs\s+\|\s*([0-9]+)} $util _ row_dsp
regexp {\| Block RAM Tile\s+\|\s*([0-9]+)} $util _ row_bram
regexp {\| CLB LUTs\*?\s+\|\s*([0-9]+)} $qk_util _ qk_lut
regexp {\| CLB Registers\s+\|\s*([0-9]+)} $qk_util _ qk_ff
regexp {\| DSPs\s+\|\s*([0-9]+)} $qk_util _ qk_dsp
regexp {\| Block RAM Tile\s+\|\s*([0-9]+)} $qk_util _ qk_bram
set f [open [file join $rd summary.txt] w]
foreach {k v} [list tool [version -short] part [get_property PART [current_design]] \
    case $n resource_contract hierarchical_Total_LUTs clock_mhz 150 \
    setup_uncertainty_ns 0.150 io_delay_constraints none \
    row_total_luts $row_lut row_flip_flops $row_ff row_dsps $row_dsp \
    row_bram_tiles $row_bram qk_cell [get_property NAME $qk] \
    qk_total_luts $qk_lut qk_flip_flops $qk_ff qk_dsps $qk_dsp \
    qk_bram_tiles $qk_bram \
    qk_detail_report qk_slot_utilization_post_route.rpt \
    hierarchy_report utilization_hier_post_route.rpt \
    wns_ns $wns whs_ns $whs unrouted_nets $unr drc_errors $drc_errors \
    error_messages $error_messages \
    critical_warning_messages $critical_warning_messages] {
    puts $f "$k=$v"
}
close $f
puts "M7_ARCH_DCP_RESULT CASE=$n ROW_TOTAL_LUT=$row_lut ROW_FF=$row_ff ROW_DSP=$row_dsp QK_CELL=[get_property NAME $qk] QK_TOTAL_LUT=$qk_lut QK_FF=$qk_ff QK_DSP=$qk_dsp WNS=$wns WHS=$whs UNROUTED=$unr DRC_ERRORS=$drc_errors ERROR_MESSAGES=$error_messages CRITICAL_WARNING_MESSAGES=$critical_warning_messages"
if {$wns < 0 || $whs < 0 || $unr != 0 || $drc_errors != 0 ||
        $error_messages != 0 || $critical_warning_messages != 0} {
    error "M7 DCP report gate"
}
close_design
exit
