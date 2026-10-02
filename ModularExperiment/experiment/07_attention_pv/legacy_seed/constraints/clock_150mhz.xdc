create_clock -name clk -period 6.667 [get_ports clk]
set_clock_uncertainty -setup 0.150 [get_clocks clk]
set_clock_uncertainty -hold 0.000 [get_clocks clk]
set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]
