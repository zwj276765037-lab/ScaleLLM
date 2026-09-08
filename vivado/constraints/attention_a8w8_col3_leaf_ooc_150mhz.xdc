create_clock -name core_clk -period 6.667 [get_ports clk]
set_clock_uncertainty 0.150 [get_clocks core_clk]
set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]

# Registered OOC boundary model: retain the production 1 ns shell allowance
# without any functional false path or datapath-only waiver.  rst_n is the
# sole asynchronous reset input; synchronous clear remains fully timed.
set nonclock_inputs [get_ports -filter {
    DIRECTION == IN && NAME != clk && NAME != rst_n}]
set all_outputs [get_ports -filter {DIRECTION == OUT}]
set_input_delay -clock core_clk -max 1.000 $nonclock_inputs
set_input_delay -clock core_clk -min 0.000 $nonclock_inputs
set_output_delay -clock core_clk -max 1.000 $all_outputs
set_output_delay -clock core_clk -min 0.000 $all_outputs
set_false_path -from [get_ports rst_n]
