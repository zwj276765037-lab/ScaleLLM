create_clock -name clk -period 6.667 [get_ports clk]
set_clock_uncertainty 0.150 [get_clocks clk]

