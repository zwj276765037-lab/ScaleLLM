`timescale 1ns / 1ps

// Registered-boundary timing harness for the production tensor DMA bridge.
// Resetless source/sink FFs anchor every non-clock partition pin without
// creating functional timing exceptions.  The DUT RTL itself is unchanged.
module hap_mlp_tensor_dma_bridge_registered_ooc_harness (
    input wire clk
);
    localparam integer SRC_W = 6489;
    localparam integer SINK_W = 12822;

    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_LOAD_VALID = 2;
    localparam integer S_LOAD_BANK = 3;
    localparam integer S_INPUT_BASE = 4;
    localparam integer S_STORE_VALID = 36;
    localparam integer S_OUTPUT_BASE = 37;
    localparam integer S_MLP_INPUT_READY = 69;
    localparam integer S_MLP_OUT_VALID = 70;
    localparam integer S_MLP_OUT_TILE = 71;
    localparam integer S_MLP_OUT_DATA = 79;
    localparam integer S_AXI_ARREADY = 6223;
    localparam integer S_AXI_RVALID = 6224;
    localparam integer S_AXI_RDATA = 6225;
    localparam integer S_AXI_RRESP = 6481;
    localparam integer S_AXI_RLAST = 6483;
    localparam integer S_AXI_AWREADY = 6484;
    localparam integer S_AXI_WREADY = 6485;
    localparam integer S_AXI_BVALID = 6486;
    localparam integer S_AXI_BRESP = 6487;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire load_ready, store_ready;
    wire mlp_input_valid, mlp_input_bank;
    wire [6:0] mlp_input_group;
    wire [12287:0] mlp_input_data;
    wire mlp_out_ready, busy, done, load_done, store_done, store_armed;
    wire axi_active, error;
    wire [2:0] phase;
    wire [31:0] input_beat_count, input_group_count;
    wire [31:0] output_beat_count, output_tile_count;
    wire m_axi_arvalid;
    wire [31:0] m_axi_araddr;
    wire [7:0] m_axi_arlen;
    wire [2:0] m_axi_arsize;
    wire [1:0] m_axi_arburst;
    wire m_axi_rready, m_axi_awvalid;
    wire [31:0] m_axi_awaddr;
    wire [7:0] m_axi_awlen;
    wire [2:0] m_axi_awsize;
    wire [1:0] m_axi_awburst;
    wire m_axi_wvalid;
    wire [255:0] m_axi_wdata;
    wire [31:0] m_axi_wstrb;
    wire m_axi_wlast, m_axi_bready;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        m_axi_bready, m_axi_wlast, m_axi_wstrb, m_axi_wdata,
        m_axi_wvalid, m_axi_awburst, m_axi_awsize, m_axi_awlen,
        m_axi_awaddr, m_axi_awvalid, m_axi_rready, m_axi_arburst,
        m_axi_arsize, m_axi_arlen, m_axi_araddr, m_axi_arvalid,
        output_tile_count, output_beat_count, input_group_count,
        input_beat_count, phase, error, axi_active, store_armed,
        store_done, load_done, done, busy, mlp_out_ready, mlp_input_data,
        mlp_input_group, mlp_input_bank, mlp_input_valid, store_ready,
        load_ready
    };

    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_tensor_dma_bridge #(
        .INPUT_GROUPS(128), .OUTPUT_TILES(256), .PRODUCTION_SHAPE(1)
    ) u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .load_valid(src_r[S_LOAD_VALID]), .load_ready(load_ready),
        .load_bank(src_r[S_LOAD_BANK]),
        .input_base_addr(src_r[S_INPUT_BASE +: 32]),
        .store_valid(src_r[S_STORE_VALID]), .store_ready(store_ready),
        .output_base_addr(src_r[S_OUTPUT_BASE +: 32]),
        .mlp_input_valid(mlp_input_valid),
        .mlp_input_ready(src_r[S_MLP_INPUT_READY]),
        .mlp_input_bank(mlp_input_bank),
        .mlp_input_group(mlp_input_group),
        .mlp_input_s24x16x32(mlp_input_data),
        .mlp_out_valid(src_r[S_MLP_OUT_VALID]),
        .mlp_out_ready(mlp_out_ready),
        .mlp_out_tile(src_r[S_MLP_OUT_TILE +: 8]),
        .mlp_out_s24x16x16(src_r[S_MLP_OUT_DATA +: 6144]),
        .busy(busy), .done(done), .load_done(load_done),
        .store_done(store_done), .store_armed(store_armed),
        .axi_active(axi_active), .error(error), .phase(phase),
        .input_beat_count(input_beat_count),
        .input_group_count(input_group_count),
        .output_beat_count(output_beat_count),
        .output_tile_count(output_tile_count),
        .m_axi_arvalid(m_axi_arvalid),
        .m_axi_arready(src_r[S_AXI_ARREADY]),
        .m_axi_araddr(m_axi_araddr), .m_axi_arlen(m_axi_arlen),
        .m_axi_arsize(m_axi_arsize), .m_axi_arburst(m_axi_arburst),
        .m_axi_rvalid(src_r[S_AXI_RVALID]), .m_axi_rready(m_axi_rready),
        .m_axi_rdata(src_r[S_AXI_RDATA +: 256]),
        .m_axi_rresp(src_r[S_AXI_RRESP +: 2]),
        .m_axi_rlast(src_r[S_AXI_RLAST]),
        .m_axi_awvalid(m_axi_awvalid),
        .m_axi_awready(src_r[S_AXI_AWREADY]),
        .m_axi_awaddr(m_axi_awaddr), .m_axi_awlen(m_axi_awlen),
        .m_axi_awsize(m_axi_awsize), .m_axi_awburst(m_axi_awburst),
        .m_axi_wvalid(m_axi_wvalid),
        .m_axi_wready(src_r[S_AXI_WREADY]), .m_axi_wdata(m_axi_wdata),
        .m_axi_wstrb(m_axi_wstrb), .m_axi_wlast(m_axi_wlast),
        .m_axi_bvalid(src_r[S_AXI_BVALID]), .m_axi_bready(m_axi_bready),
        .m_axi_bresp(src_r[S_AXI_BRESP +: 2])
    );

    initial begin
        if ((S_AXI_BRESP + 2) != SRC_W || $bits(dut_outputs) != SINK_W)
            $error("tensor DMA registered OOC vector layout mismatch");
    end
endmodule
