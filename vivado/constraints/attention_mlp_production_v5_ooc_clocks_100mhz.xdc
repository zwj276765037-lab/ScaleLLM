create_clock -name core_clk -period 10.000 [get_ports core_clk]
create_clock -name ddr0_clk -period 3.333 [get_ports ddr0_clk]
create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]

# The three shell clocks are genuinely asynchronous: core_clk is owned by the
# XDMA/control shell while ddr0_clk/ddr1_clk are independent MIG UI clocks.
# This is a CDC relationship, not a timing-closure waiver. Functional paths
# cross the domains only through the RTL CDC structures and remain subject to
# report_cdc in the post-route acceptance gate.
set_clock_groups -asynchronous -group [get_clocks core_clk] \
    -group [get_clocks ddr0_clk] -group [get_clocks ddr1_clk]

# Board shell owns clock input buffers. These locations are OOC delay anchors,
# not board pin constraints and must be replaced by generated-clock constraints
# after connecting the real MIG/XDMA block design.
set_property HD.CLK_SRC BUFGCE_X0Y44 [get_ports core_clk]
set_property HD.CLK_SRC BUFGCE_X0Y45 [get_ports ddr0_clk]
set_property HD.CLK_SRC BUFGCE_X0Y46 [get_ports ddr1_clk]

# V5 production OOC shell contract. Keep this file to XDC-supported constraint
# commands only. Fail-closed selector/control-flow checks live in the ordinary
# Tcl audit sourced by the placement flow; Vivado's XDC parser intentionally
# rejects commands such as if/foreach/add_to_collection.
#
# The 100 MHz core shell consumes at most 1.000 ns and either 300 MHz MIG shell
# consumes at most 0.800 ns. min=0.000 deliberately keeps external hold paths
# visible. Clock and reset ports are the only ports excluded from these lists.
set_input_delay -clock core_clk -max 1.000 [get_ports -quiet {
    core_clear ctrl_awaddr ctrl_awvalid ctrl_wdata ctrl_wstrb ctrl_wvalid
    ctrl_bready ctrl_araddr ctrl_arvalid ctrl_rready data_axi_arready
    data_axi_rvalid data_axi_rdata data_axi_rresp data_axi_rlast
    data_axi_awready data_axi_wready data_axi_bvalid data_axi_bresp
}]
set_input_delay -clock core_clk -min 0.000 [get_ports -quiet {
    core_clear ctrl_awaddr ctrl_awvalid ctrl_wdata ctrl_wstrb ctrl_wvalid
    ctrl_bready ctrl_araddr ctrl_arvalid ctrl_rready data_axi_arready
    data_axi_rvalid data_axi_rdata data_axi_rresp data_axi_rlast
    data_axi_awready data_axi_wready data_axi_bvalid data_axi_bresp
}]
set_output_delay -clock core_clk -max 1.000 [get_ports -quiet {
    ctrl_awready ctrl_wready ctrl_bresp ctrl_bvalid ctrl_arready ctrl_rdata
    ctrl_rresp ctrl_rvalid data_axi_arvalid data_axi_araddr data_axi_arlen
    data_axi_arsize data_axi_arburst data_axi_rready data_axi_awvalid
    data_axi_awaddr data_axi_awlen data_axi_awsize data_axi_awburst
    data_axi_wvalid data_axi_wdata data_axi_wstrb data_axi_wlast
    data_axi_bready attention_irq mlp_irq integration_error
}]
set_output_delay -clock core_clk -min 0.000 [get_ports -quiet {
    ctrl_awready ctrl_wready ctrl_bresp ctrl_bvalid ctrl_arready ctrl_rdata
    ctrl_rresp ctrl_rvalid data_axi_arvalid data_axi_araddr data_axi_arlen
    data_axi_arsize data_axi_arburst data_axi_rready data_axi_awvalid
    data_axi_awaddr data_axi_awlen data_axi_awsize data_axi_awburst
    data_axi_wvalid data_axi_wdata data_axi_wstrb data_axi_wlast
    data_axi_bready attention_irq mlp_irq integration_error
}]
set_input_delay -clock ddr0_clk -max 0.800 [get_ports -quiet {
    ddr0_axi_arready ddr0_axi_rvalid ddr0_axi_rdata ddr0_axi_rresp
    ddr0_axi_rlast
}]
set_input_delay -clock ddr0_clk -min 0.000 [get_ports -quiet {
    ddr0_axi_arready ddr0_axi_rvalid ddr0_axi_rdata ddr0_axi_rresp
    ddr0_axi_rlast
}]
set_output_delay -clock ddr0_clk -max 0.800 [get_ports -quiet {
    ddr0_axi_arvalid ddr0_axi_araddr ddr0_axi_arlen ddr0_axi_arsize
    ddr0_axi_arburst ddr0_axi_rready
}]
set_output_delay -clock ddr0_clk -min 0.000 [get_ports -quiet {
    ddr0_axi_arvalid ddr0_axi_araddr ddr0_axi_arlen ddr0_axi_arsize
    ddr0_axi_arburst ddr0_axi_rready
}]
set_input_delay -clock ddr1_clk -max 0.800 [get_ports -quiet {
    ddr1_axi_arready ddr1_axi_rvalid ddr1_axi_rdata ddr1_axi_rresp
    ddr1_axi_rlast
}]
set_input_delay -clock ddr1_clk -min 0.000 [get_ports -quiet {
    ddr1_axi_arready ddr1_axi_rvalid ddr1_axi_rdata ddr1_axi_rresp
    ddr1_axi_rlast
}]
set_output_delay -clock ddr1_clk -max 0.800 [get_ports -quiet {
    ddr1_axi_arvalid ddr1_axi_araddr ddr1_axi_arlen ddr1_axi_arsize
    ddr1_axi_arburst ddr1_axi_rready
}]
set_output_delay -clock ddr1_clk -min 0.000 [get_ports -quiet {
    ddr1_axi_arvalid ddr1_axi_araddr ddr1_axi_arlen ddr1_axi_arsize
    ddr1_axi_arburst ddr1_axi_rready
}]
