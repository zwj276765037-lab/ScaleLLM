set pcie_refclk_p_port [get_ports -quiet pcie_refclk_p]
set pcie_refclk_n_port [get_ports -quiet pcie_refclk_n]
set pcie_perstn_port [get_ports -quiet pcie_perstn]
set_property BOARD_PART_PIN {pcie_mgt_clkp} $pcie_refclk_p_port
set_property BOARD_PART_PIN {pcie_mgt_clkn} $pcie_refclk_n_port
set_property BOARD_PART_PIN {pcie_perstn_rst} $pcie_perstn_port
create_clock -period 10.000 -name pcie_refclk $pcie_refclk_p_port

# The Attention legacy frontend still has four explicit two-flop status
# synchronizers outside XPM.  The MLP and owner paths use XPM CDC primitives,
# whose generated constraints remain authoritative.
set manual_cdc_stage1 [get_pins -hier -quiet -regexp \
    {^.*/core/inst/u_core/u_compute/u_attention/u_weight_frontend/(reader[01]_(busy|error)_sync1_r_reg|u_half[01]/ddr_error_sync1_r_reg)/D$}]
set_false_path -to $manual_cdc_stage1

set core_ready_stage1 [get_pins -hier -quiet -regexp \
    {^.*/core_gate/inst/ready[01]_sync_reg\[0\]/D$}]
set_false_path -to $core_ready_stage1

# base_aresetn asynchronously asserts these small reset release chains.  Only
# the ASYNC_REG clear pins are exempted; deassertion and all downstream timing
# remain synchronous and analyzed.
set reset_sync_async_clear [get_pins -hier -quiet -regexp \
    {^.*/(core_gate|d0_gate|d1_gate)/inst/(ready[01]_sync|sync)_reg\[[0-3]\]/CLR$}]
set_false_path -to $reset_sync_async_clear
