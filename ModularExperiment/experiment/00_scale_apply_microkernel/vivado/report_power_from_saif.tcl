set checkpoint [file normalize $::env(HAP_POWER_DCP)]
set saif [file normalize $::env(HAP_SAIF_PATH)]
set strip_path $::env(HAP_SAIF_STRIP_PATH)
set report_dir [file normalize $::env(HAP_REPORT_DIR)]

file mkdir $report_dir
open_checkpoint $checkpoint

set unmatched_file [file join $report_dir saif_unmatched.rpt]
read_saif -verbose -strip_path $strip_path -out_file $unmatched_file $saif

report_power -hier all -hierarchical_depth 0 -l 100 -advisory \
    -file [file join $report_dir power_post_route.rpt]
report_power -format xml -file [file join $report_dir power_post_route.xml]
report_power -rpx [file join $report_dir power_post_route.rpx]

report_clock_utilization -file [file join $report_dir clock_utilization.rpt]
close_design
