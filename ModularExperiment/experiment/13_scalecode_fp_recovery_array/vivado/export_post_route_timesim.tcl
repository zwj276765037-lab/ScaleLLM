set checkpoint [file normalize $::env(HAP_POWER_DCP)]
set netlist [file normalize $::env(HAP_TIMESIM_NETLIST)]
set sdf [file normalize $::env(HAP_TIMESIM_SDF)]

file mkdir [file dirname $netlist]
open_checkpoint $checkpoint
write_sdf -force $sdf
write_verilog -force -mode timesim -sdf_anno true -sdf_file $sdf $netlist
close_design
