create_clock -name core_clk -period 6.666 [get_ports clk]
set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]

# Standalone core-domain leaf.  Keep the production 1.0 ns registered-I/O
# allowance so timing cannot pass by an unconstrained top boundary.
set_input_delay -max 1.000 -clock core_clk \
    [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_input_delay -min 0.000 -clock core_clk \
    [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -max 1.000 -clock core_clk \
    [get_ports -filter {DIRECTION == OUT}]
set_output_delay -min 0.000 -clock core_clk \
    [get_ports -filter {DIRECTION == OUT}]
set_clock_uncertainty 0.100 [get_clocks core_clk]
