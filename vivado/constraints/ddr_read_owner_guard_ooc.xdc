create_clock -name core_clk -period 6.666 [get_ports core_clk]
create_clock -name ddr0_clk -period 3.333 [get_ports ddr0_clk]
create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]

set_clock_groups -asynchronous \
    -group [get_clocks core_clk] \
    -group [get_clocks ddr0_clk] \
    -group [get_clocks ddr1_clk]
