namespace eval constraint_probe {}
proc constraint_probe::apply {} {
 create_pblock type_probe_pblock
 resize_pblock [get_pblocks type_probe_pblock] -add CLOCKREGION_X4Y5
 add_cells_to_pblock [get_pblocks type_probe_pblock] [get_cells -hier -filter {REF_NAME == FDRE}]
 puts "NATIVE_TCL_CONSTRAINT_PROBE_APPLIED"
}
