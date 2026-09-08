create_clock -name core_clk -period 6.667 [get_ports clk]
set_clock_uncertainty 0.150 [get_clocks core_clk]
set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]
