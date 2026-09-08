`timescale 1ns / 1ps

// Registered timing harness for the paired AXI512 scheduler OOC proxy.
//
// Raw OOC implementation leaves more than two thousand 512-bit payload pins
// as abstract partition pins.  With no HD.PARTPIN_LOCS, those pins have no
// launch/capture clock insertion delay and produce physically meaningless
// hold paths.  This wrapper replaces only that abstract shell with local
// source/sink registers.  The DUT is unchanged and all of its internal paths
// are still timed at 150/300/300 MHz.  The implementation Tcl additionally
// subtracts the original 1.0/0.8/0.8 ns I/O budgets from each registered
// boundary path.
//
// The boundary registers intentionally have no reset.  Resetting 3,619 proxy
// payload bits would create a timing/congestion network that is absent at the
// production MIG boundary.  DONT_TOUCH/KEEP/SHREG_EXTRACT prevent synthesis
// from trimming or converting the timing anchors.  This module is an OOC
// timing proxy only; it is never part of the production manifest.
module hap_axi512_paired_2client_read_wrr_ooc_harness (
    input wire core_clk,
    input wire core_rst_n,
    input wire ddr0_clk,
    input wire ddr0_rst_n,
    input wire ddr1_clk,
    input wire ddr1_rst_n
);
    localparam integer AXI_ADDR_W = 32;
    localparam integer CORE_SRC_W = 6;
    localparam integer CORE_SINK_W = 101;
    localparam integer DDR_SRC_W = 611;
    localparam integer DDR_SINK_W = 1145;

    // DDR source-vector layout.  Both DDR domains use the same bit map.
    localparam integer S_A_ARVALID    = 0;
    localparam integer S_A_ARADDR     = 1;
    localparam integer S_A_ARLEN      = 33;
    localparam integer S_A_ARSIZE     = 41;
    localparam integer S_A_ARBURST    = 44;
    localparam integer S_A_RREADY     = 46;
    localparam integer S_M_ARVALID    = 47;
    localparam integer S_M_ARADDR     = 48;
    localparam integer S_M_ARLEN      = 80;
    localparam integer S_M_ARSIZE     = 88;
    localparam integer S_M_ARBURST    = 91;
    localparam integer S_M_RREADY     = 93;
    localparam integer S_P_ARREADY    = 94;
    localparam integer S_P_RVALID     = 95;
    localparam integer S_P_RDATA      = 96;
    localparam integer S_P_RRESP      = 608;
    localparam integer S_P_RLAST      = 610;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [CORE_SRC_W-1:0] core_src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [DDR_SRC_W-1:0] ddr0_src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [DDR_SRC_W-1:0] ddr1_src_r;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [CORE_SINK_W-1:0] core_sink_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [DDR_SINK_W-1:0] ddr0_sink_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [DDR_SINK_W-1:0] ddr1_sink_r;

    // One-to-one recirculating sources keep every input timing anchor alive
    // without a wide XOR/checksum cone or a high-fanout payload reset.
    always @(posedge core_clk)
        core_src_r <= {core_src_r[CORE_SRC_W-2:0], ~core_src_r[CORE_SRC_W-1]};
    always @(posedge ddr0_clk)
        ddr0_src_r <= {ddr0_src_r[DDR_SRC_W-2:0], ~ddr0_src_r[DDR_SRC_W-1]};
    always @(posedge ddr1_clk)
        ddr1_src_r <= {ddr1_src_r[DDR_SRC_W-2:0], ~ddr1_src_r[DDR_SRC_W-1]};

    wire maintenance_pause_sources;
    wire maintenance_drain_active;
    wire maintenance_soft_clear_pulse;
    wire core_quiescent;
    wire error;
    wire [31:0] accepted_attn_bursts;
    wire [31:0] accepted_mlp_bursts;
    wire [31:0] both_eligible_cycles;

    wire a0_arready, a0_rvalid, a0_rlast;
    wire [511:0] a0_rdata;
    wire [1:0] a0_rresp;
    wire m0_arready, m0_rvalid, m0_rlast;
    wire [511:0] m0_rdata;
    wire [1:0] m0_rresp;
    wire p0_arvalid, p0_rready;
    wire [AXI_ADDR_W-1:0] p0_araddr;
    wire [7:0] p0_arlen;
    wire [2:0] p0_arsize;
    wire [1:0] p0_arburst;
    wire [31:0] p0_hol_cycles, p0_tag_high_watermark;

    wire a1_arready, a1_rvalid, a1_rlast;
    wire [511:0] a1_rdata;
    wire [1:0] a1_rresp;
    wire m1_arready, m1_rvalid, m1_rlast;
    wire [511:0] m1_rdata;
    wire [1:0] m1_rresp;
    wire p1_arvalid, p1_rready;
    wire [AXI_ADDR_W-1:0] p1_araddr;
    wire [7:0] p1_arlen;
    wire [2:0] p1_arsize;
    wire [1:0] p1_arburst;
    wire [31:0] p1_hol_cycles, p1_tag_high_watermark;

    wire [CORE_SINK_W-1:0] core_dut_outputs = {
        both_eligible_cycles, accepted_mlp_bursts, accepted_attn_bursts,
        error, core_quiescent, maintenance_soft_clear_pulse,
        maintenance_drain_active, maintenance_pause_sources
    };
    wire [DDR_SINK_W-1:0] ddr0_dut_outputs = {
        p0_tag_high_watermark, p0_hol_cycles,
        p0_rready, p0_arburst, p0_arsize, p0_arlen, p0_araddr, p0_arvalid,
        m0_rlast, m0_rresp, m0_rdata, m0_rvalid, m0_arready,
        a0_rlast, a0_rresp, a0_rdata, a0_rvalid, a0_arready
    };
    wire [DDR_SINK_W-1:0] ddr1_dut_outputs = {
        p1_tag_high_watermark, p1_hol_cycles,
        p1_rready, p1_arburst, p1_arsize, p1_arlen, p1_araddr, p1_arvalid,
        m1_rlast, m1_rresp, m1_rdata, m1_rvalid, m1_arready,
        a1_rlast, a1_rresp, a1_rdata, a1_rvalid, a1_arready
    };

    always @(posedge core_clk) core_sink_r <= core_dut_outputs;
    always @(posedge ddr0_clk) ddr0_sink_r <= ddr0_dut_outputs;
    always @(posedge ddr1_clk) ddr1_sink_r <= ddr1_dut_outputs;

    hap_axi512_paired_2client_read_wrr #(
        .AXI_ADDR_W(AXI_ADDR_W), .FIFO_DEPTH(16), .TAG_DEPTH(32), .SEQ_W(16)
    ) u_dut (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(core_src_r[0]), .core_enable(core_src_r[1]),
        .attn_source_quiescent(core_src_r[2]),
        .mlp_source_quiescent(core_src_r[3]),
        .maintenance_pause_sources(maintenance_pause_sources),
        .maintenance_drain_active(maintenance_drain_active),
        .maintenance_soft_clear_pulse(maintenance_soft_clear_pulse),

        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr0_enable(core_src_r[4]),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_enable(core_src_r[5]),

        .a0_arvalid(ddr0_src_r[S_A_ARVALID]), .a0_arready(a0_arready),
        .a0_araddr(ddr0_src_r[S_A_ARADDR +: AXI_ADDR_W]),
        .a0_arlen(ddr0_src_r[S_A_ARLEN +: 8]),
        .a0_arsize(ddr0_src_r[S_A_ARSIZE +: 3]),
        .a0_arburst(ddr0_src_r[S_A_ARBURST +: 2]),
        .a0_rvalid(a0_rvalid), .a0_rready(ddr0_src_r[S_A_RREADY]),
        .a0_rdata(a0_rdata), .a0_rresp(a0_rresp), .a0_rlast(a0_rlast),
        .m0_arvalid(ddr0_src_r[S_M_ARVALID]), .m0_arready(m0_arready),
        .m0_araddr(ddr0_src_r[S_M_ARADDR +: AXI_ADDR_W]),
        .m0_arlen(ddr0_src_r[S_M_ARLEN +: 8]),
        .m0_arsize(ddr0_src_r[S_M_ARSIZE +: 3]),
        .m0_arburst(ddr0_src_r[S_M_ARBURST +: 2]),
        .m0_rvalid(m0_rvalid), .m0_rready(ddr0_src_r[S_M_RREADY]),
        .m0_rdata(m0_rdata), .m0_rresp(m0_rresp), .m0_rlast(m0_rlast),
        .p0_arvalid(p0_arvalid), .p0_arready(ddr0_src_r[S_P_ARREADY]),
        .p0_araddr(p0_araddr), .p0_arlen(p0_arlen), .p0_arsize(p0_arsize),
        .p0_arburst(p0_arburst), .p0_rvalid(ddr0_src_r[S_P_RVALID]),
        .p0_rready(p0_rready),
        .p0_rdata(ddr0_src_r[S_P_RDATA +: 512]),
        .p0_rresp(ddr0_src_r[S_P_RRESP +: 2]),
        .p0_rlast(ddr0_src_r[S_P_RLAST]),

        .a1_arvalid(ddr1_src_r[S_A_ARVALID]), .a1_arready(a1_arready),
        .a1_araddr(ddr1_src_r[S_A_ARADDR +: AXI_ADDR_W]),
        .a1_arlen(ddr1_src_r[S_A_ARLEN +: 8]),
        .a1_arsize(ddr1_src_r[S_A_ARSIZE +: 3]),
        .a1_arburst(ddr1_src_r[S_A_ARBURST +: 2]),
        .a1_rvalid(a1_rvalid), .a1_rready(ddr1_src_r[S_A_RREADY]),
        .a1_rdata(a1_rdata), .a1_rresp(a1_rresp), .a1_rlast(a1_rlast),
        .m1_arvalid(ddr1_src_r[S_M_ARVALID]), .m1_arready(m1_arready),
        .m1_araddr(ddr1_src_r[S_M_ARADDR +: AXI_ADDR_W]),
        .m1_arlen(ddr1_src_r[S_M_ARLEN +: 8]),
        .m1_arsize(ddr1_src_r[S_M_ARSIZE +: 3]),
        .m1_arburst(ddr1_src_r[S_M_ARBURST +: 2]),
        .m1_rvalid(m1_rvalid), .m1_rready(ddr1_src_r[S_M_RREADY]),
        .m1_rdata(m1_rdata), .m1_rresp(m1_rresp), .m1_rlast(m1_rlast),
        .p1_arvalid(p1_arvalid), .p1_arready(ddr1_src_r[S_P_ARREADY]),
        .p1_araddr(p1_araddr), .p1_arlen(p1_arlen), .p1_arsize(p1_arsize),
        .p1_arburst(p1_arburst), .p1_rvalid(ddr1_src_r[S_P_RVALID]),
        .p1_rready(p1_rready),
        .p1_rdata(ddr1_src_r[S_P_RDATA +: 512]),
        .p1_rresp(ddr1_src_r[S_P_RRESP +: 2]),
        .p1_rlast(ddr1_src_r[S_P_RLAST]),

        .core_quiescent(core_quiescent), .error(error),
        .accepted_attn_bursts(accepted_attn_bursts),
        .accepted_mlp_bursts(accepted_mlp_bursts),
        .both_eligible_cycles(both_eligible_cycles),
        .p0_hol_cycles(p0_hol_cycles), .p1_hol_cycles(p1_hol_cycles),
        .p0_tag_high_watermark(p0_tag_high_watermark),
        .p1_tag_high_watermark(p1_tag_high_watermark)
    );

    initial begin
        if (S_P_RLAST != DDR_SRC_W-1)
            $error("registered OOC DDR source layout mismatch");
        if ($bits(core_dut_outputs) != CORE_SINK_W ||
            $bits(ddr0_dut_outputs) != DDR_SINK_W ||
            $bits(ddr1_dut_outputs) != DDR_SINK_W)
            $error("registered OOC sink layout mismatch");
    end
endmodule
