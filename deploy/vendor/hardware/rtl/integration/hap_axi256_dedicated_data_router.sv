`timescale 1ns / 1ps
// Physical DDR affinity for data DMA. c0 (Attention) bypasses directly to
// DDR0; c1 (MLP tensor) and c2 (MLP metadata) retain command-level locking
// and return routing on DDR1. Clock conversion is owned by the board BD.
module hap_axi256_dedicated_data_router (
 input wire clk,input wire rst_n,input wire clear,
 input wire c0_req,input wire c1_req,input wire c2_req,
 output wire conflict_error,output wire[1:0]active_client,
 input wire c0_arvalid,output wire c0_arready,input wire[31:0]c0_araddr,
 input wire[7:0]c0_arlen,input wire[2:0]c0_arsize,input wire[1:0]c0_arburst,
 output wire c0_rvalid,input wire c0_rready,output wire[255:0]c0_rdata,
 output wire[1:0]c0_rresp,output wire c0_rlast,
 input wire c0_awvalid,output wire c0_awready,input wire[31:0]c0_awaddr,
 input wire[7:0]c0_awlen,input wire[2:0]c0_awsize,input wire[1:0]c0_awburst,
 input wire c0_wvalid,output wire c0_wready,input wire[255:0]c0_wdata,
 input wire[31:0]c0_wstrb,input wire c0_wlast,output wire c0_bvalid,
 input wire c0_bready,output wire[1:0]c0_bresp,
 input wire c1_arvalid,output wire c1_arready,input wire[31:0]c1_araddr,
 input wire[7:0]c1_arlen,input wire[2:0]c1_arsize,input wire[1:0]c1_arburst,
 output wire c1_rvalid,input wire c1_rready,output wire[255:0]c1_rdata,
 output wire[1:0]c1_rresp,output wire c1_rlast,
 input wire c1_awvalid,output wire c1_awready,input wire[31:0]c1_awaddr,
 input wire[7:0]c1_awlen,input wire[2:0]c1_awsize,input wire[1:0]c1_awburst,
 input wire c1_wvalid,output wire c1_wready,input wire[255:0]c1_wdata,
 input wire[31:0]c1_wstrb,input wire c1_wlast,output wire c1_bvalid,
 input wire c1_bready,output wire[1:0]c1_bresp,
 input wire c2_arvalid,output wire c2_arready,input wire[31:0]c2_araddr,
 input wire[7:0]c2_arlen,input wire[2:0]c2_arsize,input wire[1:0]c2_arburst,
 output wire c2_rvalid,input wire c2_rready,output wire[255:0]c2_rdata,
 output wire[1:0]c2_rresp,output wire c2_rlast,
 input wire c2_awvalid,output wire c2_awready,input wire[31:0]c2_awaddr,
 input wire[7:0]c2_awlen,input wire[2:0]c2_awsize,input wire[1:0]c2_awburst,
 input wire c2_wvalid,output wire c2_wready,input wire[255:0]c2_wdata,
 input wire[31:0]c2_wstrb,input wire c2_wlast,output wire c2_bvalid,
 input wire c2_bready,output wire[1:0]c2_bresp,
 output wire data_axi_arvalid,input wire data_axi_arready,
 output wire[31:0]data_axi_araddr,output wire[7:0]data_axi_arlen,
 output wire[2:0]data_axi_arsize,output wire[1:0]data_axi_arburst,
 input wire data_axi_rvalid,output wire data_axi_rready,input wire[255:0]data_axi_rdata,
 input wire[1:0]data_axi_rresp,input wire data_axi_rlast,
 output wire data_axi_awvalid,input wire data_axi_awready,
 output wire[31:0]data_axi_awaddr,output wire[7:0]data_axi_awlen,
 output wire[2:0]data_axi_awsize,output wire[1:0]data_axi_awburst,
 output wire data_axi_wvalid,input wire data_axi_wready,output wire[255:0]data_axi_wdata,
 output wire[31:0]data_axi_wstrb,output wire data_axi_wlast,
 input wire data_axi_bvalid,output wire data_axi_bready,input wire[1:0]data_axi_bresp,
 output wire mlp_data_axi_arvalid,input wire mlp_data_axi_arready,
 output wire[31:0]mlp_data_axi_araddr,output wire[7:0]mlp_data_axi_arlen,
 output wire[2:0]mlp_data_axi_arsize,output wire[1:0]mlp_data_axi_arburst,
 input wire mlp_data_axi_rvalid,output wire mlp_data_axi_rready,input wire[255:0]mlp_data_axi_rdata,
 input wire[1:0]mlp_data_axi_rresp,input wire mlp_data_axi_rlast,
 output wire mlp_data_axi_awvalid,input wire mlp_data_axi_awready,
 output wire[31:0]mlp_data_axi_awaddr,output wire[7:0]mlp_data_axi_awlen,
 output wire[2:0]mlp_data_axi_awsize,output wire[1:0]mlp_data_axi_awburst,
 output wire mlp_data_axi_wvalid,input wire mlp_data_axi_wready,output wire[255:0]mlp_data_axi_wdata,
 output wire[31:0]mlp_data_axi_wstrb,output wire mlp_data_axi_wlast,
 input wire mlp_data_axi_bvalid,output wire mlp_data_axi_bready,input wire[1:0]mlp_data_axi_bresp);
 wire m_arvalid,m_arready,m_rvalid,m_rready,m_rlast,m_awvalid,m_awready,m_wvalid,m_wready,m_wlast,m_bvalid,m_bready;
 wire[31:0]m_araddr,m_awaddr,m_wstrb;wire[7:0]m_arlen,m_awlen;wire[2:0]m_arsize,m_awsize;
 wire[1:0]m_arburst,m_rresp,m_awburst,m_bresp;wire[255:0]m_rdata,m_wdata;
 // Attention DMA is physically DDR0-only; MLP tensor/meta arbitrate DDR1.
 assign data_axi_arvalid=c0_arvalid;
 assign c0_arready=data_axi_arready;
 assign data_axi_araddr=c0_araddr;
 assign data_axi_arlen=c0_arlen;
 assign data_axi_arsize=c0_arsize;
 assign data_axi_arburst=c0_arburst;
 assign c0_rvalid=data_axi_rvalid;
 assign data_axi_rready=c0_rready;
 assign c0_rdata=data_axi_rdata;
 assign c0_rresp=data_axi_rresp;
 assign c0_rlast=data_axi_rlast;
 assign data_axi_awvalid=c0_awvalid;
 assign c0_awready=data_axi_awready;
 assign data_axi_awaddr=c0_awaddr;
 assign data_axi_awlen=c0_awlen;
 assign data_axi_awsize=c0_awsize;
 assign data_axi_awburst=c0_awburst;
 assign data_axi_wvalid=c0_wvalid;
 assign c0_wready=data_axi_wready;
 assign data_axi_wdata=c0_wdata;
 assign data_axi_wstrb=c0_wstrb;
 assign data_axi_wlast=c0_wlast;
 assign c0_bvalid=data_axi_bvalid;
 assign data_axi_bready=c0_bready;
 assign c0_bresp=data_axi_bresp;
 hap_axi256_3to1_arbiter u_data_arb(.clk(clk),.rst_n(rst_n),
  .clear(clear),.conflict_error(conflict_error),.c0_req(1'b0),
  .c0_arvalid('0),.c0_arready(),.c0_araddr('0),.c0_arlen('0),
  .c0_arsize('0),.c0_arburst('0),.c0_rvalid(),.c0_rready('0),
  .c0_rdata(),.c0_rresp(),.c0_rlast(),.c0_awvalid('0),
  .c0_awready(),.c0_awaddr('0),.c0_awlen('0),.c0_awsize('0),
  .c0_awburst('0),.c0_wvalid('0),.c0_wready(),.c0_wdata('0),
  .c0_wstrb('0),.c0_wlast('0),.c0_bvalid(),.c0_bready('0),
  .c0_bresp(),
  .*);
 assign mlp_data_axi_arvalid=m_arvalid;assign m_arready=mlp_data_axi_arready;assign mlp_data_axi_araddr=m_araddr;
 assign mlp_data_axi_arlen=m_arlen;assign mlp_data_axi_arsize=m_arsize;assign mlp_data_axi_arburst=m_arburst;
 assign m_rvalid=mlp_data_axi_rvalid;assign mlp_data_axi_rready=m_rready;assign m_rdata=mlp_data_axi_rdata;
 assign m_rresp=mlp_data_axi_rresp;assign m_rlast=mlp_data_axi_rlast;assign mlp_data_axi_awvalid=m_awvalid;
 assign m_awready=mlp_data_axi_awready;assign mlp_data_axi_awaddr=m_awaddr;assign mlp_data_axi_awlen=m_awlen;
 assign mlp_data_axi_awsize=m_awsize;assign mlp_data_axi_awburst=m_awburst;assign mlp_data_axi_wvalid=m_wvalid;
 assign m_wready=mlp_data_axi_wready;assign mlp_data_axi_wdata=m_wdata;assign mlp_data_axi_wstrb=m_wstrb;
 assign mlp_data_axi_wlast=m_wlast;assign m_bvalid=mlp_data_axi_bvalid;assign mlp_data_axi_bready=m_bready;
 assign m_bresp=mlp_data_axi_bresp;
endmodule
