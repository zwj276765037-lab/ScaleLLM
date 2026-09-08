create_clock -name core_clk -period 6.666 [get_ports core_clk]
create_clock -name ddr0_clk -period 3.333 [get_ports ddr0_clk]
create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]

set_clock_uncertainty 0.150 [get_clocks core_clk]
set_clock_uncertainty 0.100 [get_clocks {ddr0_clk ddr1_clk}]

# The locations match the raw OOC clock anchors.  No broad asynchronous clock
# group or false path is added: XPM owns its narrow Gray-pointer CDC timing.
set_property HD.CLK_SRC BUFGCE_X0Y44 [get_ports core_clk]
set_property HD.CLK_SRC BUFGCE_X0Y45 [get_ports ddr0_clk]
set_property HD.CLK_SRC BUFGCE_X0Y46 [get_ports ddr1_clk]

# Only reset assertion enters from the abstract shell.  All functional inputs
# and outputs are registered inside the harness; therefore no 512-bit top-level
# partition pins remain to create artificial zero-clock-insertion hold paths.
# Reset release is implemented by the DUT XPM reset synchronizers and audited
# by report_cdc/report_methodology, as in the raw OOC run.
