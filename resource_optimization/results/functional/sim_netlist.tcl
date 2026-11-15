set_param general.maxThreads 4
set run_dir [file normalize [lindex $argv 0]]
set netlist [file normalize [lindex $argv 1]]
set tb [file normalize [lindex $argv 2]]
foreach source [list $netlist $tb] {
    if {![file isfile $source]} {error "Missing simulation source: $source"}
}
puts "LEAF_NETLIST_SIM_IDENTITY netlist=$netlist tb=$tb tool=[version -short]"
create_project mlp_sc_post_synth_sim [file join $run_dir project] -part xcvu9p-flga2104-2L-e
add_files -fileset sim_1 [list $netlist $tb]
set_property top mlp_sc_recover2_tb [get_filesets sim_1]
set_property xsim.simulate.runtime 0ns [get_filesets sim_1]
update_compile_order -fileset sim_1
launch_simulation -simset sim_1 -mode behavioral
run all
close_sim
close_project
