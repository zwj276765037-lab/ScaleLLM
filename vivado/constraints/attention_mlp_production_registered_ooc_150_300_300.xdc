create_clock -name core_clk -period 6.666 [get_ports core_clk]
create_clock -name ddr0_clk -period 3.333 [get_ports ddr0_clk]
create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]

set_clock_uncertainty 0.150 [get_clocks core_clk]
set_clock_uncertainty 0.100 [get_clocks {ddr0_clk ddr1_clk}]

# These are the only asynchronous groups.  They describe the genuine XDMA /
# independent-MIG clock relationship; no functional path or endpoint is
# waived.  CDC structures inside u_dut remain subject to report_cdc and
# methodology gates.
set_clock_groups -asynchronous \
    -group [get_clocks core_clk] \
    -group [get_clocks ddr0_clk] \
    -group [get_clocks ddr1_clk]

# OOC clock insertion anchors only.  The board design owns the real clock
# buffers and generated-clock definitions.
set_property HD.CLK_SRC BUFGCE_X0Y44 [get_ports core_clk]
set_property HD.CLK_SRC BUFGCE_X0Y45 [get_ports ddr0_clk]
set_property HD.CLK_SRC BUFGCE_X0Y46 [get_ports ddr1_clk]

# The six top-level ports are clocks/resets.  All 1,888 functional bits are
# represented by same-domain resetless registers inside the harness.  The Tcl
# applies max/min delay contracts directly between those registers after
# synthesis: core 6.666-1.000=5.666 ns, DDR 3.333-0.800=2.533 ns, min=0.
# Consequently this XDC intentionally contains no set_input_delay,
# set_output_delay, set_false_path, or -datapath_only exception.
