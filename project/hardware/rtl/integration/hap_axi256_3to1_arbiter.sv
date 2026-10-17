`timescale 1ns / 1ps

// Command-locking arbiter for the three sequential AXI256 DMA engines used by
// the combined core. A client keeps req asserted for its complete command,
// including the final R/B response, so responses never change destination.
module hap_axi256_3to1_arbiter (
 input wire clk,input wire rst_n,input wire clear,
 input wire c0_req,input wire c1_req,input wire c2_req,
 output reg conflict_error,output wire[1:0]active_client,
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
 output wire m_arvalid,input wire m_arready,output wire[31:0]m_araddr,
 output wire[7:0]m_arlen,output wire[2:0]m_arsize,output wire[1:0]m_arburst,
 input wire m_rvalid,output wire m_rready,input wire[255:0]m_rdata,
 input wire[1:0]m_rresp,input wire m_rlast,
 output wire m_awvalid,input wire m_awready,output wire[31:0]m_awaddr,
 output wire[7:0]m_awlen,output wire[2:0]m_awsize,output wire[1:0]m_awburst,
 output wire m_wvalid,input wire m_wready,output wire[255:0]m_wdata,
 output wire[31:0]m_wstrb,output wire m_wlast,input wire m_bvalid,
 output wire m_bready,input wire[1:0]m_bresp);
 reg[1:0]owner_r;localparam IDLE=0,C0=1,C1=2,C2=3;
 assign active_client=owner_r;
 assign m_arvalid=owner_r==C0?c0_arvalid:owner_r==C1?c1_arvalid:owner_r==C2?c2_arvalid:0;
 assign m_araddr=owner_r==C0?c0_araddr:owner_r==C1?c1_araddr:c2_araddr;
 assign m_arlen=owner_r==C0?c0_arlen:owner_r==C1?c1_arlen:c2_arlen;
 assign m_arsize=owner_r==C0?c0_arsize:owner_r==C1?c1_arsize:c2_arsize;
 assign m_arburst=owner_r==C0?c0_arburst:owner_r==C1?c1_arburst:c2_arburst;
 assign c0_arready=owner_r==C0&&m_arready;assign c1_arready=owner_r==C1&&m_arready;
 assign c2_arready=owner_r==C2&&m_arready;assign c0_rvalid=owner_r==C0&&m_rvalid;
 assign c1_rvalid=owner_r==C1&&m_rvalid;assign c2_rvalid=owner_r==C2&&m_rvalid;
 assign c0_rdata=m_rdata;assign c1_rdata=m_rdata;assign c2_rdata=m_rdata;
 assign c0_rresp=m_rresp;assign c1_rresp=m_rresp;assign c2_rresp=m_rresp;
 assign c0_rlast=m_rlast;assign c1_rlast=m_rlast;assign c2_rlast=m_rlast;
 assign m_rready=owner_r==C0?c0_rready:owner_r==C1?c1_rready:owner_r==C2?c2_rready:0;
 assign m_awvalid=owner_r==C0?c0_awvalid:owner_r==C1?c1_awvalid:owner_r==C2?c2_awvalid:0;
 assign m_awaddr=owner_r==C0?c0_awaddr:owner_r==C1?c1_awaddr:c2_awaddr;
 assign m_awlen=owner_r==C0?c0_awlen:owner_r==C1?c1_awlen:c2_awlen;
 assign m_awsize=owner_r==C0?c0_awsize:owner_r==C1?c1_awsize:c2_awsize;
 assign m_awburst=owner_r==C0?c0_awburst:owner_r==C1?c1_awburst:c2_awburst;
 assign c0_awready=owner_r==C0&&m_awready;assign c1_awready=owner_r==C1&&m_awready;
 assign c2_awready=owner_r==C2&&m_awready;assign m_wvalid=owner_r==C0?c0_wvalid:owner_r==C1?c1_wvalid:owner_r==C2?c2_wvalid:0;
 assign m_wdata=owner_r==C0?c0_wdata:owner_r==C1?c1_wdata:c2_wdata;
 assign m_wstrb=owner_r==C0?c0_wstrb:owner_r==C1?c1_wstrb:c2_wstrb;
 assign m_wlast=owner_r==C0?c0_wlast:owner_r==C1?c1_wlast:c2_wlast;
 assign c0_wready=owner_r==C0&&m_wready;assign c1_wready=owner_r==C1&&m_wready;
 assign c2_wready=owner_r==C2&&m_wready;assign c0_bvalid=owner_r==C0&&m_bvalid;
 assign c1_bvalid=owner_r==C1&&m_bvalid;assign c2_bvalid=owner_r==C2&&m_bvalid;
 assign c0_bresp=m_bresp;assign c1_bresp=m_bresp;assign c2_bresp=m_bresp;
 assign m_bready=owner_r==C0?c0_bready:owner_r==C1?c1_bready:owner_r==C2?c2_bready:0;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin owner_r<=IDLE;conflict_error<=0;end
  else if(clear)begin owner_r<=IDLE;conflict_error<=0;end
  else begin
   // Concurrent requests are legal and remain pending behind the locked
   // client. Fixed priority is sufficient because each production DMA command
   // is finite and software does not submit an unbounded stream of commands.
   case(owner_r)
    IDLE:if(c0_req)owner_r<=C0;else if(c1_req)owner_r<=C1;else if(c2_req)owner_r<=C2;
    C0:if(!c0_req)owner_r<=IDLE;C1:if(!c1_req)owner_r<=IDLE;
    C2:if(!c2_req)owner_r<=IDLE;default:begin owner_r<=IDLE;conflict_error<=1;end
   endcase
  end
 end
endmodule
