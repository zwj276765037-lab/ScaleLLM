namespace eval constraint_probe {if {![info exists attempts]} {variable attempts 0}}
proc constraint_probe::apply {} {
 variable attempts;incr attempts
 if {[info exists ::env(HAP_M003_RESTORE_VERIFY_ONLY)]} {error "probe restore must never reapply"}
 create_pblock type_probe_pblock
 resize_pblock [get_pblocks type_probe_pblock] -add CLOCKREGION_X4Y5
 add_cells_to_pblock [get_pblocks type_probe_pblock] [get_cells -hier -filter {REF_NAME == FDRE}]
 puts "NATIVE_TCL_CONSTRAINT_PROBE_APPLIED attempts=$attempts"
}
