set root [file normalize [file join [file dirname [info script]] ../../..]]
set out_dir [file normalize [file join $root ModularExperiment result _environment]]
file mkdir $out_dir

set fp [open [file join $out_dir vivado_environment.txt] w]
puts $fp "tool=[version -short]"
puts $fp "part=xcvu9p-flga2104-2L-e"

create_project -in_memory -part xcvu9p-flga2104-2L-e
set defs [get_ipdefs -all -quiet *floating_point*]
puts $fp "floating_point_ipdefs=$defs"
if {[llength $defs] == 0} {
    close $fp
    error "No floating_point IP definition is installed"
}

set selected [lindex $defs end]
set parts [split $selected :]
set vendor [lindex $parts 0]
set library [lindex $parts 1]
set name [lindex $parts 2]
set version [lindex $parts 3]
create_ip -name $name -vendor $vendor -library $library -version $version \
    -module_name modular_experiment_fp_probe -dir $out_dir
set ip [get_ips modular_experiment_fp_probe]
puts $fp "selected_ipdef=$selected"
foreach prop [lsort [list_property $ip]] {
    if {[string match "CONFIG.*" $prop]} {
        puts $fp "$prop=[get_property $prop $ip]"
    }
}
foreach prop {
    CONFIG.Operation_Type
    CONFIG.A_Precision_Type
    CONFIG.Result_Precision_Type
    CONFIG.Add_Sub_Value
    CONFIG.C_Optimization
    CONFIG.C_Mult_Usage
    CONFIG.Flow_Control
} {
    if {![catch {set allowed [list_property_value $prop $ip]}]} {
        puts $fp "ALLOWED.$prop=$allowed"
    }
}
close $fp
puts "WROTE [file join $out_dir vivado_environment.txt]"
