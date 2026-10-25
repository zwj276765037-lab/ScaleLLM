# User-prioritized engineering-validation file generation only.
# Max-DPO clock-group coverage and external reset signoff remain open.
# No severity downgrade, DRC bypass, physical rerun or device programming.
if {[llength $argv]!=2} {error {usage: write_preliminary_bitstream.tcl ROUTED_DCP NEW_OUTPUT_DIRECTORY}}
lassign $argv dcp outdir
if {![file isfile $dcp] || [file exists $outdir]} {error {DCP must exist and output directory must be new}}
file mkdir $outdir
set_param general.maxThreads 8
open_checkpoint $dcp
# write_bitstream runs its normal native checks. A true DRC blocker is fatal.
write_bitstream [file join $outdir ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit]
close_design
puts NATIVE_GU_PRELIMINARY_BITSTREAM_COMPLETED
