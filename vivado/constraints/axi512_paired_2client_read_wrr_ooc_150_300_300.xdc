create_clock -name core_clk -period 6.666 [get_ports core_clk]
create_clock -name ddr0_clk -period 3.333 [get_ports ddr0_clk]
create_clock -name ddr1_clk -period 3.333 [get_ports ddr1_clk]

set_clock_uncertainty 0.150 [get_clocks core_clk]
set_clock_uncertainty 0.100 [get_clocks {ddr0_clk ddr1_clk}]

# OOC anchors only.  The full board integration replaces these with generated
# clocks from the real core/MIG infrastructure.
set_property HD.CLK_SRC BUFGCE_X0Y44 [get_ports core_clk]
set_property HD.CLK_SRC BUFGCE_X0Y45 [get_ports ddr0_clk]
set_property HD.CLK_SRC BUFGCE_X0Y46 [get_ports ddr1_clk]

# Preserve the XPM FIFO/CDC timing exceptions applied by the instantiated XPM
# primitives.  Do not use broad set_clock_groups here: doing so would mask the
# Gray-pointer datapath/bus-skew checks this OOC run is intended to audit.

# Explicit shell budgets keep top-level input->register and register->output
# paths visible.  Resets/clocks are excluded; reset release is implemented by
# xpm_cdc_sync_rst and is separately covered by report_cdc/methodology.
set core_inputs [get_ports -quiet {
  core_clear core_enable attn_source_quiescent mlp_source_quiescent
  ddr0_enable ddr1_enable
}]
set core_outputs [get_ports -quiet {
  core_quiescent error accepted_attn_bursts[*] accepted_mlp_bursts[*]
  both_eligible_cycles[*] maintenance_pause_sources maintenance_drain_active
  maintenance_soft_clear_pulse
}]
set ddr0_inputs [get_ports -quiet {
  a0_arvalid a0_araddr[*] a0_arlen[*] a0_arsize[*] a0_arburst[*]
  a0_rready m0_arvalid m0_araddr[*] m0_arlen[*] m0_arsize[*] m0_arburst[*]
  m0_rready p0_arready p0_rvalid p0_rdata[*] p0_rresp[*] p0_rlast
}]
set ddr0_outputs [get_ports -quiet {
  a0_arready a0_rvalid a0_rdata[*] a0_rresp[*] a0_rlast
  m0_arready m0_rvalid m0_rdata[*] m0_rresp[*] m0_rlast
  p0_arvalid p0_araddr[*] p0_arlen[*] p0_arsize[*] p0_arburst[*] p0_rready
  p0_hol_cycles[*] p0_tag_high_watermark[*]
}]
set ddr1_inputs [get_ports -quiet {
  a1_arvalid a1_araddr[*] a1_arlen[*] a1_arsize[*] a1_arburst[*]
  a1_rready m1_arvalid m1_araddr[*] m1_arlen[*] m1_arsize[*] m1_arburst[*]
  m1_rready p1_arready p1_rvalid p1_rdata[*] p1_rresp[*] p1_rlast
}]
set ddr1_outputs [get_ports -quiet {
  a1_arready a1_rvalid a1_rdata[*] a1_rresp[*] a1_rlast
  m1_arready m1_rvalid m1_rdata[*] m1_rresp[*] m1_rlast
  p1_arvalid p1_araddr[*] p1_arlen[*] p1_arsize[*] p1_arburst[*] p1_rready
  p1_hol_cycles[*] p1_tag_high_watermark[*]
}]

set_input_delay -clock core_clk -max 1.000 $core_inputs
set_input_delay -clock core_clk -min 0.000 $core_inputs
set_output_delay -clock core_clk -max 1.000 $core_outputs
set_output_delay -clock core_clk -min 0.000 $core_outputs
set_input_delay -clock ddr0_clk -max 0.800 $ddr0_inputs
set_input_delay -clock ddr0_clk -min 0.000 $ddr0_inputs
set_output_delay -clock ddr0_clk -max 0.800 $ddr0_outputs
set_output_delay -clock ddr0_clk -min 0.000 $ddr0_outputs
set_input_delay -clock ddr1_clk -max 0.800 $ddr1_inputs
set_input_delay -clock ddr1_clk -min 0.000 $ddr1_inputs
set_output_delay -clock ddr1_clk -max 0.800 $ddr1_outputs
set_output_delay -clock ddr1_clk -min 0.000 $ddr1_outputs
