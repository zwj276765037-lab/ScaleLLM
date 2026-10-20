set probe_dir [file dirname [file normalize [info script]]]
source [file join $probe_dir helper.tcl]
constraint_probe::apply
