create_clock -name clk -period 6.666 [get_ports clk]
set_property HD.CLK_SRC BUFGCE_X0Y0 [get_ports clk]

# The registered timing harness exposes no functional top-level ports. Every
# DUT boundary path is a real same-clock register-to-register path, so no I/O
# delay or timing exception is legal in this OOC gate.
