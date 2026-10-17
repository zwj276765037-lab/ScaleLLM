set_property LOC MMCM_X0Y2 [get_cells -hier -filter {NAME =~ */u_ddr4_infrastructure/gen_mmcme*.u_mmcme_adv_inst}]
set_property INTERNAL_VREF {0.84} [get_iobanks 42] 
set_property INTERNAL_VREF {0.84} [get_iobanks 40] 
