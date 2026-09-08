`timescale 1ns / 1ps

// Fail-closed registered OOC timing proxy for the complete production core.
//
// The real board shell launches/captures every functional interface in its
// owning clock domain.  A raw OOC top instead exposes abstract partition pins,
// whose missing launch/capture clock insertion can create meaningless hold
// failures.  This timing-only harness replaces those functional pins with
// local resetless source/sink registers.  The production core and its source
// manifest remain unchanged.
//
// Boundary contract (clock/reset excluded):
//   domain   source FF (DUT inputs)   sink FF (DUT outputs)
//   core              332                    428
//   ddr0              517                     47
//   ddr1              517                     47
//   total            1366                    522 = 1888 FF
//
// DONT_TOUCH/KEEP/SHREG_EXTRACT make trimming, merging, or SRL conversion a
// hard count failure in the implementation Tcl.  No boundary data register is
// reset: adding reset to 1,888 proxy-only bits would inject non-production
// reset fanout and congestion.  The three clocks and three resets connect
// directly to u_dut and are the only top-level ports.
module hap_attention_mlp_production_registered_ooc_harness (
    input wire core_clk,
    input wire core_rst_n,
    input wire ddr0_clk,
    input wire ddr0_rst_n,
    input wire ddr1_clk,
    input wire ddr1_rst_n
);
    localparam integer CORE_SRC_W = 332;
    localparam integer CORE_SINK_W = 428;
    localparam integer DDR_SRC_W = 517;
    localparam integer DDR_SINK_W = 47;

    // Core source-vector layout (all functional core-domain DUT inputs).
    localparam integer C_CORE_CLEAR       = 0;
    localparam integer C_CTRL_AWADDR      = 1;
    localparam integer C_CTRL_AWVALID     = 13;
    localparam integer C_CTRL_WDATA       = 14;
    localparam integer C_CTRL_WSTRB       = 46;
    localparam integer C_CTRL_WVALID      = 50;
    localparam integer C_CTRL_BREADY      = 51;
    localparam integer C_CTRL_ARADDR      = 52;
    localparam integer C_CTRL_ARVALID     = 64;
    localparam integer C_CTRL_RREADY      = 65;
    localparam integer C_DATA_ARREADY     = 66;
    localparam integer C_DATA_RVALID      = 67;
    localparam integer C_DATA_RDATA       = 68;
    localparam integer C_DATA_RRESP       = 324;
    localparam integer C_DATA_RLAST       = 326;
    localparam integer C_DATA_AWREADY     = 327;
    localparam integer C_DATA_WREADY      = 328;
    localparam integer C_DATA_BVALID      = 329;
    localparam integer C_DATA_BRESP       = 330;

    // DDR source-vector layout (identical for ddr0 and ddr1 DUT inputs).
    localparam integer D_ARREADY = 0;
    localparam integer D_RVALID  = 1;
    localparam integer D_RDATA   = 2;
    localparam integer D_RRESP   = 514;
    localparam integer D_RLAST   = 516;

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

    // One-to-one recirculation keeps every source anchor live without a wide
    // checksum/XOR cone.  These are deliberately resetless proxy registers.
    always @(posedge core_clk)
        core_src_r <= {core_src_r[CORE_SRC_W-2:0], ~core_src_r[CORE_SRC_W-1]};
    always @(posedge ddr0_clk)
        ddr0_src_r <= {ddr0_src_r[DDR_SRC_W-2:0], ~ddr0_src_r[DDR_SRC_W-1]};
    always @(posedge ddr1_clk)
        ddr1_src_r <= {ddr1_src_r[DDR_SRC_W-2:0], ~ddr1_src_r[DDR_SRC_W-1]};

    wire ctrl_awready;
    wire ctrl_wready;
    wire [1:0] ctrl_bresp;
    wire ctrl_bvalid;
    wire ctrl_arready;
    wire [31:0] ctrl_rdata;
    wire [1:0] ctrl_rresp;
    wire ctrl_rvalid;

    wire data_axi_arvalid;
    wire [31:0] data_axi_araddr;
    wire [7:0] data_axi_arlen;
    wire [2:0] data_axi_arsize;
    wire [1:0] data_axi_arburst;
    wire data_axi_rready;
    wire data_axi_awvalid;
    wire [31:0] data_axi_awaddr;
    wire [7:0] data_axi_awlen;
    wire [2:0] data_axi_awsize;
    wire [1:0] data_axi_awburst;
    wire data_axi_wvalid;
    wire [255:0] data_axi_wdata;
    wire [31:0] data_axi_wstrb;
    wire data_axi_wlast;
    wire data_axi_bready;

    wire ddr0_axi_arvalid;
    wire [31:0] ddr0_axi_araddr;
    wire [7:0] ddr0_axi_arlen;
    wire [2:0] ddr0_axi_arsize;
    wire [1:0] ddr0_axi_arburst;
    wire ddr0_axi_rready;

    wire ddr1_axi_arvalid;
    wire [31:0] ddr1_axi_araddr;
    wire [7:0] ddr1_axi_arlen;
    wire [2:0] ddr1_axi_arsize;
    wire [1:0] ddr1_axi_arburst;
    wire ddr1_axi_rready;

    wire attention_irq;
    wire mlp_irq;
    wire integration_error;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [CORE_SINK_W-1:0] core_dut_outputs = {
        integration_error, mlp_irq, attention_irq,
        data_axi_bready,
        data_axi_wlast, data_axi_wstrb, data_axi_wdata, data_axi_wvalid,
        data_axi_awburst, data_axi_awsize, data_axi_awlen,
        data_axi_awaddr, data_axi_awvalid,
        data_axi_rready,
        data_axi_arburst, data_axi_arsize, data_axi_arlen,
        data_axi_araddr, data_axi_arvalid,
        ctrl_rvalid, ctrl_rresp, ctrl_rdata, ctrl_arready,
        ctrl_bvalid, ctrl_bresp, ctrl_wready, ctrl_awready
    };
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [DDR_SINK_W-1:0] ddr0_dut_outputs = {
        ddr0_axi_rready, ddr0_axi_arburst, ddr0_axi_arsize,
        ddr0_axi_arlen, ddr0_axi_araddr, ddr0_axi_arvalid
    };
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [DDR_SINK_W-1:0] ddr1_dut_outputs = {
        ddr1_axi_rready, ddr1_axi_arburst, ddr1_axi_arsize,
        ddr1_axi_arlen, ddr1_axi_araddr, ddr1_axi_arvalid
    };

    always @(posedge core_clk) core_sink_r <= core_dut_outputs;
    always @(posedge ddr0_clk) ddr0_sink_r <= ddr0_dut_outputs;
    always @(posedge ddr1_clk) ddr1_sink_r <= ddr1_dut_outputs;

    hap_attention_mlp_production_core u_dut (
        .core_clk(core_clk),
        .core_rst_n(core_rst_n),
        .core_clear(core_src_r[C_CORE_CLEAR]),
        .ddr0_clk(ddr0_clk),
        .ddr0_rst_n(ddr0_rst_n),
        .ddr1_clk(ddr1_clk),
        .ddr1_rst_n(ddr1_rst_n),

        .ctrl_awaddr(core_src_r[C_CTRL_AWADDR +: 12]),
        .ctrl_awvalid(core_src_r[C_CTRL_AWVALID]),
        .ctrl_awready(ctrl_awready),
        .ctrl_wdata(core_src_r[C_CTRL_WDATA +: 32]),
        .ctrl_wstrb(core_src_r[C_CTRL_WSTRB +: 4]),
        .ctrl_wvalid(core_src_r[C_CTRL_WVALID]),
        .ctrl_wready(ctrl_wready),
        .ctrl_bresp(ctrl_bresp),
        .ctrl_bvalid(ctrl_bvalid),
        .ctrl_bready(core_src_r[C_CTRL_BREADY]),
        .ctrl_araddr(core_src_r[C_CTRL_ARADDR +: 12]),
        .ctrl_arvalid(core_src_r[C_CTRL_ARVALID]),
        .ctrl_arready(ctrl_arready),
        .ctrl_rdata(ctrl_rdata),
        .ctrl_rresp(ctrl_rresp),
        .ctrl_rvalid(ctrl_rvalid),
        .ctrl_rready(core_src_r[C_CTRL_RREADY]),

        .data_axi_arvalid(data_axi_arvalid),
        .data_axi_arready(core_src_r[C_DATA_ARREADY]),
        .data_axi_araddr(data_axi_araddr),
        .data_axi_arlen(data_axi_arlen),
        .data_axi_arsize(data_axi_arsize),
        .data_axi_arburst(data_axi_arburst),
        .data_axi_rvalid(core_src_r[C_DATA_RVALID]),
        .data_axi_rready(data_axi_rready),
        .data_axi_rdata(core_src_r[C_DATA_RDATA +: 256]),
        .data_axi_rresp(core_src_r[C_DATA_RRESP +: 2]),
        .data_axi_rlast(core_src_r[C_DATA_RLAST]),
        .data_axi_awvalid(data_axi_awvalid),
        .data_axi_awready(core_src_r[C_DATA_AWREADY]),
        .data_axi_awaddr(data_axi_awaddr),
        .data_axi_awlen(data_axi_awlen),
        .data_axi_awsize(data_axi_awsize),
        .data_axi_awburst(data_axi_awburst),
        .data_axi_wvalid(data_axi_wvalid),
        .data_axi_wready(core_src_r[C_DATA_WREADY]),
        .data_axi_wdata(data_axi_wdata),
        .data_axi_wstrb(data_axi_wstrb),
        .data_axi_wlast(data_axi_wlast),
        .data_axi_bvalid(core_src_r[C_DATA_BVALID]),
        .data_axi_bready(data_axi_bready),
        .data_axi_bresp(core_src_r[C_DATA_BRESP +: 2]),

        .ddr0_axi_arvalid(ddr0_axi_arvalid),
        .ddr0_axi_arready(ddr0_src_r[D_ARREADY]),
        .ddr0_axi_araddr(ddr0_axi_araddr),
        .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize),
        .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_src_r[D_RVALID]),
        .ddr0_axi_rready(ddr0_axi_rready),
        .ddr0_axi_rdata(ddr0_src_r[D_RDATA +: 512]),
        .ddr0_axi_rresp(ddr0_src_r[D_RRESP +: 2]),
        .ddr0_axi_rlast(ddr0_src_r[D_RLAST]),

        .ddr1_axi_arvalid(ddr1_axi_arvalid),
        .ddr1_axi_arready(ddr1_src_r[D_ARREADY]),
        .ddr1_axi_araddr(ddr1_axi_araddr),
        .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize),
        .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_src_r[D_RVALID]),
        .ddr1_axi_rready(ddr1_axi_rready),
        .ddr1_axi_rdata(ddr1_src_r[D_RDATA +: 512]),
        .ddr1_axi_rresp(ddr1_src_r[D_RRESP +: 2]),
        .ddr1_axi_rlast(ddr1_src_r[D_RLAST]),

        .attention_irq(attention_irq),
        .mlp_irq(mlp_irq),
        .integration_error(integration_error)
    );

    initial begin
        if (C_DATA_BRESP + 2 != CORE_SRC_W)
            $error("production registered OOC core source layout mismatch");
        if (D_RLAST != DDR_SRC_W-1)
            $error("production registered OOC DDR source layout mismatch");
        if ($bits(core_dut_outputs) != CORE_SINK_W ||
            $bits(ddr0_dut_outputs) != DDR_SINK_W ||
            $bits(ddr1_dut_outputs) != DDR_SINK_W)
            $error("production registered OOC sink layout mismatch");
    end
endmodule
