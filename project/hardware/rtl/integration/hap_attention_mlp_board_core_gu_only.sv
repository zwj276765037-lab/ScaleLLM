`timescale 1ns / 1ps

// VCU118 module-reference boundary for the complete production core.  The
// Vivado block design owns XDMA, SmartConnect, clocks/resets and both MIGs.
module hap_attention_mlp_board_core_gu_only (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 core_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 100000000, ASSOCIATED_BUSIF S_AXIL:M_AXI_DATA:M_AXI_MLP_DATA, ASSOCIATED_RESET core_rst_n" *)
    input  wire          core_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 core_rst_n RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire          core_rst_n,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL AWADDR" *) input wire [11:0] s_axil_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL AWVALID" *) input wire s_axil_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL AWREADY" *) output wire s_axil_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WDATA" *) input wire [31:0] s_axil_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WSTRB" *) input wire [3:0] s_axil_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WVALID" *) input wire s_axil_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL WREADY" *) output wire s_axil_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL BRESP" *) output wire [1:0] s_axil_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL BVALID" *) output wire s_axil_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL BREADY" *) input wire s_axil_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL ARADDR" *) input wire [11:0] s_axil_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL ARVALID" *) input wire s_axil_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL ARREADY" *) output wire s_axil_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RDATA" *) output wire [31:0] s_axil_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RRESP" *) output wire [1:0] s_axil_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RVALID" *) output wire s_axil_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 S_AXIL RREADY" *) input wire s_axil_rready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARVALID" *) output wire m_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARREADY" *) input wire m_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4, DATA_WIDTH 256, ADDR_WIDTH 32, READ_WRITE_MODE READ_WRITE, MAX_BURST_LENGTH 256, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] m_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARLEN" *) output wire [7:0] m_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARSIZE" *) output wire [2:0] m_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA ARBURST" *) output wire [1:0] m_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RVALID" *) input wire m_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RREADY" *) output wire m_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RDATA" *) input wire [255:0] m_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RRESP" *) input wire [1:0] m_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA RLAST" *) input wire m_axi_rlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWVALID" *) output wire m_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWREADY" *) input wire m_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWADDR" *) output wire [31:0] m_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWLEN" *) output wire [7:0] m_axi_awlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWSIZE" *) output wire [2:0] m_axi_awsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA AWBURST" *) output wire [1:0] m_axi_awburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WVALID" *) output wire m_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WREADY" *) input wire m_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WDATA" *) output wire [255:0] m_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WSTRB" *) output wire [31:0] m_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA WLAST" *) output wire m_axi_wlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA BVALID" *) input wire m_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA BREADY" *) output wire m_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_DATA BRESP" *) input wire [1:0] m_axi_bresp,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA ARVALID" *) output wire m_mlp_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA ARREADY" *) input wire m_mlp_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA ARADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4, DATA_WIDTH 256, ADDR_WIDTH 32, READ_WRITE_MODE READ_WRITE, MAX_BURST_LENGTH 256, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] m_mlp_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA ARLEN" *) output wire [7:0] m_mlp_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA ARSIZE" *) output wire [2:0] m_mlp_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA ARBURST" *) output wire [1:0] m_mlp_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA RVALID" *) input wire m_mlp_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA RREADY" *) output wire m_mlp_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA RDATA" *) input wire [255:0] m_mlp_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA RRESP" *) input wire [1:0] m_mlp_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA RLAST" *) input wire m_mlp_axi_rlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA AWVALID" *) output wire m_mlp_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA AWREADY" *) input wire m_mlp_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA AWADDR" *) output wire [31:0] m_mlp_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA AWLEN" *) output wire [7:0] m_mlp_axi_awlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA AWSIZE" *) output wire [2:0] m_mlp_axi_awsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA AWBURST" *) output wire [1:0] m_mlp_axi_awburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA WVALID" *) output wire m_mlp_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA WREADY" *) input wire m_mlp_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA WDATA" *) output wire [255:0] m_mlp_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA WSTRB" *) output wire [31:0] m_mlp_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA WLAST" *) output wire m_mlp_axi_wlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA BVALID" *) input wire m_mlp_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA BREADY" *) output wire m_mlp_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_MLP_DATA BRESP" *) input wire [1:0] m_mlp_axi_bresp,

    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ddr0_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C0, ASSOCIATED_RESET ddr0_rst_n" *) input wire ddr0_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ddr0_rst_n RST" *) input wire ddr0_rst_n,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARVALID" *) output wire ddr0_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARREADY" *) input wire ddr0_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4, DATA_WIDTH 512, ADDR_WIDTH 32, READ_WRITE_MODE READ_ONLY, MAX_BURST_LENGTH 16, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] ddr0_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARLEN" *) output wire [7:0] ddr0_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARSIZE" *) output wire [2:0] ddr0_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 ARBURST" *) output wire [1:0] ddr0_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RVALID" *) input wire ddr0_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RREADY" *) output wire ddr0_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RDATA" *) input wire [511:0] ddr0_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RRESP" *) input wire [1:0] ddr0_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C0 RLAST" *) input wire ddr0_axi_rlast,

    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ddr1_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 200000000, ASSOCIATED_BUSIF M_AXI_WEIGHT_C1, ASSOCIATED_RESET ddr1_rst_n" *) input wire ddr1_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ddr1_rst_n RST" *) input wire ddr1_rst_n,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARVALID" *) output wire ddr1_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARREADY" *) input wire ddr1_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4, DATA_WIDTH 512, ADDR_WIDTH 32, READ_WRITE_MODE READ_ONLY, MAX_BURST_LENGTH 16, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] ddr1_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARLEN" *) output wire [7:0] ddr1_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARSIZE" *) output wire [2:0] ddr1_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 ARBURST" *) output wire [1:0] ddr1_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RVALID" *) input wire ddr1_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RREADY" *) output wire ddr1_axi_rready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RDATA" *) input wire [511:0] ddr1_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RRESP" *) input wire [1:0] ddr1_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI_WEIGHT_C1 RLAST" *) input wire ddr1_axi_rlast,

    (* X_INTERFACE_INFO = "xilinx.com:signal:interrupt:1.0 irq INTERRUPT" *)
    (* X_INTERFACE_PARAMETER = "SENSITIVITY LEVEL_HIGH" *)
    output wire irq
);
    wire attention_irq;
    wire mlp_irq;
    wire integration_error;
    reg irq_r = 1'b0;

    hap_attention_mlp_production_core_gu_only #(.INTERMEDIATE_COLUMNS(14336),
        .HIDDEN_COLUMNS(4096),.ENFORCE_PRODUCTION_SHAPE(1)) u_core (
        .core_clk(core_clk), .core_rst_n(core_rst_n), .core_clear(1'b0),
        .ddr0_clk(ddr0_clk), .ddr0_rst_n(ddr0_rst_n),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ctrl_awaddr(s_axil_awaddr), .ctrl_awvalid(s_axil_awvalid),
        .ctrl_awready(s_axil_awready), .ctrl_wdata(s_axil_wdata),
        .ctrl_wstrb(s_axil_wstrb), .ctrl_wvalid(s_axil_wvalid),
        .ctrl_wready(s_axil_wready), .ctrl_bresp(s_axil_bresp),
        .ctrl_bvalid(s_axil_bvalid), .ctrl_bready(s_axil_bready),
        .ctrl_araddr(s_axil_araddr), .ctrl_arvalid(s_axil_arvalid),
        .ctrl_arready(s_axil_arready), .ctrl_rdata(s_axil_rdata),
        .ctrl_rresp(s_axil_rresp), .ctrl_rvalid(s_axil_rvalid),
        .ctrl_rready(s_axil_rready),
        .data_axi_arvalid(m_axi_arvalid), .data_axi_arready(m_axi_arready),
        .data_axi_araddr(m_axi_araddr), .data_axi_arlen(m_axi_arlen),
        .data_axi_arsize(m_axi_arsize), .data_axi_arburst(m_axi_arburst),
        .data_axi_rvalid(m_axi_rvalid), .data_axi_rready(m_axi_rready),
        .data_axi_rdata(m_axi_rdata), .data_axi_rresp(m_axi_rresp),
        .data_axi_rlast(m_axi_rlast), .data_axi_awvalid(m_axi_awvalid),
        .data_axi_awready(m_axi_awready), .data_axi_awaddr(m_axi_awaddr),
        .data_axi_awlen(m_axi_awlen), .data_axi_awsize(m_axi_awsize),
        .data_axi_awburst(m_axi_awburst), .data_axi_wvalid(m_axi_wvalid),
        .data_axi_wready(m_axi_wready), .data_axi_wdata(m_axi_wdata),
        .data_axi_wstrb(m_axi_wstrb), .data_axi_wlast(m_axi_wlast),
        .data_axi_bvalid(m_axi_bvalid), .data_axi_bready(m_axi_bready),
        .data_axi_bresp(m_axi_bresp),
        .mlp_data_axi_arvalid(m_mlp_axi_arvalid), .mlp_data_axi_arready(m_mlp_axi_arready),
        .mlp_data_axi_araddr(m_mlp_axi_araddr), .mlp_data_axi_arlen(m_mlp_axi_arlen),
        .mlp_data_axi_arsize(m_mlp_axi_arsize), .mlp_data_axi_arburst(m_mlp_axi_arburst),
        .mlp_data_axi_rvalid(m_mlp_axi_rvalid), .mlp_data_axi_rready(m_mlp_axi_rready),
        .mlp_data_axi_rdata(m_mlp_axi_rdata), .mlp_data_axi_rresp(m_mlp_axi_rresp),
        .mlp_data_axi_rlast(m_mlp_axi_rlast), .mlp_data_axi_awvalid(m_mlp_axi_awvalid),
        .mlp_data_axi_awready(m_mlp_axi_awready), .mlp_data_axi_awaddr(m_mlp_axi_awaddr),
        .mlp_data_axi_awlen(m_mlp_axi_awlen), .mlp_data_axi_awsize(m_mlp_axi_awsize),
        .mlp_data_axi_awburst(m_mlp_axi_awburst), .mlp_data_axi_wvalid(m_mlp_axi_wvalid),
        .mlp_data_axi_wready(m_mlp_axi_wready), .mlp_data_axi_wdata(m_mlp_axi_wdata),
        .mlp_data_axi_wstrb(m_mlp_axi_wstrb), .mlp_data_axi_wlast(m_mlp_axi_wlast),
        .mlp_data_axi_bvalid(m_mlp_axi_bvalid), .mlp_data_axi_bready(m_mlp_axi_bready),
        .mlp_data_axi_bresp(m_mlp_axi_bresp),
        .ddr0_axi_arvalid(ddr0_axi_arvalid), .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize), .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid), .ddr0_axi_rready(ddr0_axi_rready),
        .ddr0_axi_rdata(ddr0_axi_rdata), .ddr0_axi_rresp(ddr0_axi_rresp),
        .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_axi_arvalid(ddr1_axi_arvalid), .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize), .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid), .ddr1_axi_rready(ddr1_axi_rready),
        .ddr1_axi_rdata(ddr1_axi_rdata), .ddr1_axi_rresp(ddr1_axi_rresp),
        .ddr1_axi_rlast(ddr1_axi_rlast), .attention_irq(attention_irq),
        .mlp_irq(mlp_irq), .integration_error(integration_error)
    );

    // XDMA keeps its destination synchronizer.  Present it a core-clocked
    // level so a handoff between interrupt contributors cannot glitch its
    // first stage.  Each producer retains its existing clear behavior.
    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) irq_r <= 1'b0;
        else irq_r <= attention_irq || mlp_irq || integration_error;
    end
    assign irq = irq_r;
endmodule
