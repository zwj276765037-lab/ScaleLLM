# Read LATE, after the XDMA and both MIG clock constraints. The matching
# primary/generated clock identities are checked in build_vcu118_board.tcl.
# No reset paths or synchronizer stages are waived here.
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks -of_objects [get_ports pcie_refclk_p]] \
    -group [get_clocks -include_generated_clocks -of_objects [get_ports default_250mhz_clk1_clk_p]] \
    -group [get_clocks -include_generated_clocks -of_objects [get_ports default_250mhz_clk2_clk_p]]
