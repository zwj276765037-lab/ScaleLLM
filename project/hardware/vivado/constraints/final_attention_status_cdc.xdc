# Four source-contract-qualified single-bit status CDC paths, physical DDR0 UI
# (5 ns) to core (12.5 ns). No second-stage or consumer exception is introduced.
# This top-hierarchy file is implementation-only in the project. Synthesis
# evidence explicitly reads it after open_run has stitched the real OOC design.
set_max_delay 5.000 -datapath_only -from [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/u_reader0/active_r_reg/C}] -to [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/reader0_busy_sync1_r_reg/D}]
set_max_delay 5.000 -datapath_only -from [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/u_reader0/error_reg/C}] -to [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/reader0_error_sync1_r_reg/D}]
set_max_delay 5.000 -datapath_only -from [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/u_reader1/active_r_reg/C}] -to [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/reader1_busy_sync1_r_reg/D}]
set_max_delay 5.000 -datapath_only -from [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/u_reader1/error_reg/C}] -to [get_pins {scalellm_final_decode16_bd_i/core/inst/u_core/u_a/u_weight_frontend/reader1_error_sync1_r_reg/D}]
