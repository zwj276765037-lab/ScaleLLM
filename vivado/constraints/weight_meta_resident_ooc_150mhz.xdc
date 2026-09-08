create_clock -name clk -period 6.666 [get_ports clk]

# Registered OOC boundary modelling only.  These are real external delays,
# not false paths or datapath-only waivers.
set nonclock_inputs [get_ports -filter {DIRECTION == IN && NAME != clk}]
set all_outputs [get_ports -filter {DIRECTION == OUT}]
set_input_delay -clock clk -max 1.000 $nonclock_inputs
set_input_delay -clock clk -min 0.000 $nonclock_inputs
set_output_delay -clock clk -max 1.000 $all_outputs
set_output_delay -clock clk -min 0.000 $all_outputs

set_property HD.CLK_SRC BUFGCTRL_X0Y24 [get_ports clk]
