`timescale 1ns / 1ps

// VCU118 module-reference boundary for the complete production core.  The
// Vivado block design owns XDMA, SmartConnect, clocks/resets and both MIGs.
module hap_scalellm_final_core (
    input  wire          core_clk,
    input  wire          core_rst_n,

    input wire [11:0] s_axil_awaddr,
    input wire s_axil_awvalid,
    output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,
    output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,
    output wire s_axil_bvalid,
    input wire s_axil_bready,
    input wire [11:0] s_axil_araddr,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,
    input wire s_axil_rready,

    output wire m_axi_arvalid,
    input wire m_axi_arready,
    output wire [31:0] m_axi_araddr,
    output wire [7:0] m_axi_arlen,
    output wire [2:0] m_axi_arsize,
    output wire [1:0] m_axi_arburst,
    input wire m_axi_rvalid,
    output wire m_axi_rready,
    input wire [255:0] m_axi_rdata,
    input wire [1:0] m_axi_rresp,
    input wire m_axi_rlast,
    output wire m_axi_awvalid,
    input wire m_axi_awready,
    output wire [31:0] m_axi_awaddr,
    output wire [7:0] m_axi_awlen,
    output wire [2:0] m_axi_awsize,
    output wire [1:0] m_axi_awburst,
    output wire m_axi_wvalid,
    input wire m_axi_wready,
    output wire [255:0] m_axi_wdata,
    output wire [31:0] m_axi_wstrb,
    output wire m_axi_wlast,
    input wire m_axi_bvalid,
    output wire m_axi_bready,
    input wire [1:0] m_axi_bresp,

    output wire m_mlp_axi_arvalid,
    input wire m_mlp_axi_arready,
    output wire [31:0] m_mlp_axi_araddr,
    output wire [7:0] m_mlp_axi_arlen,
    output wire [2:0] m_mlp_axi_arsize,
    output wire [1:0] m_mlp_axi_arburst,
    input wire m_mlp_axi_rvalid,
    output wire m_mlp_axi_rready,
    input wire [255:0] m_mlp_axi_rdata,
    input wire [1:0] m_mlp_axi_rresp,
    input wire m_mlp_axi_rlast,
    output wire m_mlp_axi_awvalid,
    input wire m_mlp_axi_awready,
    output wire [31:0] m_mlp_axi_awaddr,
    output wire [7:0] m_mlp_axi_awlen,
    output wire [2:0] m_mlp_axi_awsize,
    output wire [1:0] m_mlp_axi_awburst,
    output wire m_mlp_axi_wvalid,
    input wire m_mlp_axi_wready,
    output wire [255:0] m_mlp_axi_wdata,
    output wire [31:0] m_mlp_axi_wstrb,
    output wire m_mlp_axi_wlast,
    input wire m_mlp_axi_bvalid,
    output wire m_mlp_axi_bready,
    input wire [1:0] m_mlp_axi_bresp,

    input wire ddr0_clk,
    input wire ddr0_rst_n,
    output wire ddr0_axi_arvalid,
    input wire ddr0_axi_arready,
    output wire [31:0] ddr0_axi_araddr,
    output wire [7:0] ddr0_axi_arlen,
    output wire [2:0] ddr0_axi_arsize,
    output wire [1:0] ddr0_axi_arburst,
    input wire ddr0_axi_rvalid,
    output wire ddr0_axi_rready,
    input wire [511:0] ddr0_axi_rdata,
    input wire [1:0] ddr0_axi_rresp,
    input wire ddr0_axi_rlast,

    input wire ddr1_clk,
    input wire ddr1_rst_n,
    output wire ddr1_axi_arvalid,
    input wire ddr1_axi_arready,
    output wire [31:0] ddr1_axi_araddr,
    output wire [7:0] ddr1_axi_arlen,
    output wire [2:0] ddr1_axi_arsize,
    output wire [1:0] ddr1_axi_arburst,
    input wire ddr1_axi_rvalid,
    output wire ddr1_axi_rready,
    input wire [511:0] ddr1_axi_rdata,
    input wire [1:0] ddr1_axi_rresp,
    input wire ddr1_axi_rlast,

    output wire irq
);
 `include "hap_scalellm_final_abi.svh"
 localparam[3:0]IDLE=0,CHECK=1,START_A=2,RUN_A=3,START_M=4,RUN_M=5,FINISH=6,FAULT=7;
 reg[3:0]state;reg[2047:0]d_r;
 wire submit_valid,submit_ready;wire[2047:0]submit_descriptor;wire abort_valid,control_busy,completion_valid,reset_required;
 reg result_valid;reg[31:0]result_error,result_input_bytes,result_output_bytes,result_cycles;reg result_reset_required;
 wire[31:0]check_error;
 reg abort_pending;reg[31:0]cycles;
 wire a_ready,a_done,a_error,a_w_quiet,a_ddr_quiet,a_data_busy,m_ready,m_done,m_error,m_w_quiet;
 wire[31:0]a_input_bytes,a_output_bytes,m_input_bytes,m_output_bytes;
 wire paired_core_quiescent,paired_error,maintenance_pause_sources,maintenance_drain_active,maintenance_soft_clear_pulse;
 assign submit_ready=state==IDLE&&paired_core_quiescent&&a_ready&&m_ready&&!paired_error;
 hap_scalellm_final_descriptor_check u_check(.descriptor(d_r),.error_code(check_error));
 hap_scalellm_final_axil_control u_ctrl(.clk(core_clk),.rst_n(core_rst_n),
 .s_axil_awaddr(s_axil_awaddr),
 .s_axil_awvalid(s_axil_awvalid),
 .s_axil_awready(s_axil_awready),
 .s_axil_wdata(s_axil_wdata),
 .s_axil_wstrb(s_axil_wstrb),
 .s_axil_wvalid(s_axil_wvalid),
 .s_axil_wready(s_axil_wready),
 .s_axil_bresp(s_axil_bresp),
 .s_axil_bvalid(s_axil_bvalid),
 .s_axil_bready(s_axil_bready),
 .s_axil_araddr(s_axil_araddr),
 .s_axil_arvalid(s_axil_arvalid),
 .s_axil_arready(s_axil_arready),
 .s_axil_rdata(s_axil_rdata),
 .s_axil_rresp(s_axil_rresp),
 .s_axil_rvalid(s_axil_rvalid),
 .s_axil_rready(s_axil_rready),
 .submit_valid(submit_valid),.submit_ready(submit_ready),.submit_descriptor(submit_descriptor),
 .result_valid(result_valid),.result_error(result_error),.result_reset_required(result_reset_required),
 .result_input_bytes(result_input_bytes),.result_output_bytes(result_output_bytes),.result_cycles(result_cycles),
 .abort_valid(abort_valid),.busy(control_busy),.completion_valid(completion_valid),.reset_required(reset_required),.irq(irq));
 wire att_d0_arvalid;
 wire att_d0_arready;
 wire [31:0] att_d0_araddr;
 wire [7:0] att_d0_arlen;
 wire [2:0] att_d0_arsize;
 wire [1:0] att_d0_arburst;
 wire att_d0_rvalid;
 wire att_d0_rready;
 wire [511:0] att_d0_rdata;
 wire [1:0] att_d0_rresp;
 wire att_d0_rlast;
 wire att_d1_arvalid;
 wire att_d1_arready;
 wire [31:0] att_d1_araddr;
 wire [7:0] att_d1_arlen;
 wire [2:0] att_d1_arsize;
 wire [1:0] att_d1_arburst;
 wire att_d1_rvalid;
 wire att_d1_rready;
 wire [511:0] att_d1_rdata;
 wire [1:0] att_d1_rresp;
 wire att_d1_rlast;
 wire mlp_d0_arvalid;
 wire mlp_d0_arready;
 wire [31:0] mlp_d0_araddr;
 wire [7:0] mlp_d0_arlen;
 wire [2:0] mlp_d0_arsize;
 wire [1:0] mlp_d0_arburst;
 wire mlp_d0_rvalid;
 wire mlp_d0_rready;
 wire [511:0] mlp_d0_rdata;
 wire [1:0] mlp_d0_rresp;
 wire mlp_d0_rlast;
 wire mlp_d1_arvalid;
 wire mlp_d1_arready;
 wire [31:0] mlp_d1_araddr;
 wire [7:0] mlp_d1_arlen;
 wire [2:0] mlp_d1_arsize;
 wire [1:0] mlp_d1_arburst;
 wire mlp_d1_rvalid;
 wire mlp_d1_rready;
 wire [511:0] mlp_d1_rdata;
 wire [1:0] mlp_d1_rresp;
 wire mlp_d1_rlast;
 hap_scalellm_final_attention_engine u_a(
 .core_clk(core_clk),.core_rst_n(core_rst_n),.start(state==START_A),.descriptor(d_r),
 .ready(a_ready),.done(a_done),.error(a_error),.weight_source_quiescent(a_w_quiet),
 .ddr_quiescent(a_ddr_quiet),.data_axi_busy(a_data_busy),
 .m_axi_arvalid(m_axi_arvalid),
 .m_axi_arready(m_axi_arready),
 .m_axi_araddr(m_axi_araddr),
 .m_axi_arlen(m_axi_arlen),
 .m_axi_arsize(m_axi_arsize),
 .m_axi_arburst(m_axi_arburst),
 .m_axi_rvalid(m_axi_rvalid),
 .m_axi_rready(m_axi_rready),
 .m_axi_rdata(m_axi_rdata),
 .m_axi_rresp(m_axi_rresp),
 .m_axi_rlast(m_axi_rlast),
 .m_axi_awvalid(m_axi_awvalid),
 .m_axi_awready(m_axi_awready),
 .m_axi_awaddr(m_axi_awaddr),
 .m_axi_awlen(m_axi_awlen),
 .m_axi_awsize(m_axi_awsize),
 .m_axi_awburst(m_axi_awburst),
 .m_axi_wvalid(m_axi_wvalid),
 .m_axi_wready(m_axi_wready),
 .m_axi_wdata(m_axi_wdata),
 .m_axi_wstrb(m_axi_wstrb),
 .m_axi_wlast(m_axi_wlast),
 .m_axi_bvalid(m_axi_bvalid),
 .m_axi_bready(m_axi_bready),
 .m_axi_bresp(m_axi_bresp),
 .ddr0_clk(ddr0_clk),
 .ddr0_rst_n(ddr0_rst_n),
 .ddr0_axi_arvalid(att_d0_arvalid),
 .ddr0_axi_arready(att_d0_arready),
 .ddr0_axi_araddr(att_d0_araddr),
 .ddr0_axi_arlen(att_d0_arlen),
 .ddr0_axi_arsize(att_d0_arsize),
 .ddr0_axi_arburst(att_d0_arburst),
 .ddr0_axi_rvalid(att_d0_rvalid),
 .ddr0_axi_rready(att_d0_rready),
 .ddr0_axi_rdata(att_d0_rdata),
 .ddr0_axi_rresp(att_d0_rresp),
 .ddr0_axi_rlast(att_d0_rlast),
 .ddr1_clk(ddr0_clk),
 .ddr1_rst_n(ddr0_rst_n),
 .ddr1_axi_arvalid(att_d1_arvalid),
 .ddr1_axi_arready(att_d1_arready),
 .ddr1_axi_araddr(att_d1_araddr),
 .ddr1_axi_arlen(att_d1_arlen),
 .ddr1_axi_arsize(att_d1_arsize),
 .ddr1_axi_arburst(att_d1_arburst),
 .ddr1_axi_rvalid(att_d1_rvalid),
 .ddr1_axi_rready(att_d1_rready),
 .ddr1_axi_rdata(att_d1_rdata),
 .ddr1_axi_rresp(att_d1_rresp),
 .ddr1_axi_rlast(att_d1_rlast),
 .input_bytes(a_input_bytes),
 .output_bytes(a_output_bytes)
 );
 hap_scalellm_final_mlp_engine u_m(
 .core_clk(core_clk),.core_rst_n(core_rst_n),.start(state==START_M),.descriptor(d_r),
 .ready(m_ready),.done(m_done),.error(m_error),.weight_source_quiescent(m_w_quiet),
 .m_axi_arvalid(m_mlp_axi_arvalid),
 .m_axi_arready(m_mlp_axi_arready),
 .m_axi_araddr(m_mlp_axi_araddr),
 .m_axi_arlen(m_mlp_axi_arlen),
 .m_axi_arsize(m_mlp_axi_arsize),
 .m_axi_arburst(m_mlp_axi_arburst),
 .m_axi_rvalid(m_mlp_axi_rvalid),
 .m_axi_rready(m_mlp_axi_rready),
 .m_axi_rdata(m_mlp_axi_rdata),
 .m_axi_rresp(m_mlp_axi_rresp),
 .m_axi_rlast(m_mlp_axi_rlast),
 .m_axi_awvalid(m_mlp_axi_awvalid),
 .m_axi_awready(m_mlp_axi_awready),
 .m_axi_awaddr(m_mlp_axi_awaddr),
 .m_axi_awlen(m_mlp_axi_awlen),
 .m_axi_awsize(m_mlp_axi_awsize),
 .m_axi_awburst(m_mlp_axi_awburst),
 .m_axi_wvalid(m_mlp_axi_wvalid),
 .m_axi_wready(m_mlp_axi_wready),
 .m_axi_wdata(m_mlp_axi_wdata),
 .m_axi_wstrb(m_mlp_axi_wstrb),
 .m_axi_wlast(m_mlp_axi_wlast),
 .m_axi_bvalid(m_mlp_axi_bvalid),
 .m_axi_bready(m_mlp_axi_bready),
 .m_axi_bresp(m_mlp_axi_bresp),
 .ddr0_clk(ddr1_clk),
 .ddr0_rst_n(ddr1_rst_n),
 .ddr0_axi_arvalid(mlp_d0_arvalid),
 .ddr0_axi_arready(mlp_d0_arready),
 .ddr0_axi_araddr(mlp_d0_araddr),
 .ddr0_axi_arlen(mlp_d0_arlen),
 .ddr0_axi_arsize(mlp_d0_arsize),
 .ddr0_axi_arburst(mlp_d0_arburst),
 .ddr0_axi_rvalid(mlp_d0_rvalid),
 .ddr0_axi_rready(mlp_d0_rready),
 .ddr0_axi_rdata(mlp_d0_rdata),
 .ddr0_axi_rresp(mlp_d0_rresp),
 .ddr0_axi_rlast(mlp_d0_rlast),
 .ddr1_clk(ddr1_clk),
 .ddr1_rst_n(ddr1_rst_n),
 .ddr1_axi_arvalid(mlp_d1_arvalid),
 .ddr1_axi_arready(mlp_d1_arready),
 .ddr1_axi_araddr(mlp_d1_araddr),
 .ddr1_axi_arlen(mlp_d1_arlen),
 .ddr1_axi_arsize(mlp_d1_arsize),
 .ddr1_axi_arburst(mlp_d1_arburst),
 .ddr1_axi_rvalid(mlp_d1_rvalid),
 .ddr1_axi_rready(mlp_d1_rready),
 .ddr1_axi_rdata(mlp_d1_rdata),
 .ddr1_axi_rresp(mlp_d1_rresp),
 .ddr1_axi_rlast(mlp_d1_rlast),
 .input_bytes(m_input_bytes),
 .output_bytes(m_output_bytes)
 );
 hap_axi512_dual_engine_dedicated_read u_paired_weight(
  .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(1'b0),
  .core_enable(1'b1),.attn_source_quiescent(a_w_quiet),
  .mlp_source_quiescent(m_w_quiet),.maintenance_pause_sources(maintenance_pause_sources),
  .maintenance_drain_active(maintenance_drain_active),
  .maintenance_soft_clear_pulse(maintenance_soft_clear_pulse),
  .ddr0_clk(ddr0_clk),.ddr0_rst_n(ddr0_rst_n),.ddr0_enable(1'b1),
  .ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),.ddr1_enable(1'b1),
  // Both logical halves terminate on their dedicated physical DDR.
  .a0_arvalid(att_d0_arvalid),.a0_arready(att_d0_arready),
  .a0_araddr(att_d0_araddr),.a0_arlen(att_d0_arlen),
  .a0_arsize(att_d0_arsize),.a0_arburst(att_d0_arburst),
  .a0_rvalid(att_d0_rvalid),.a0_rready(att_d0_rready),
  .a0_rdata(att_d0_rdata),.a0_rresp(att_d0_rresp),.a0_rlast(att_d0_rlast),
  .a1_arvalid(att_d1_arvalid),.a1_arready(att_d1_arready),
  .a1_araddr(att_d1_araddr),.a1_arlen(att_d1_arlen),
  .a1_arsize(att_d1_arsize),.a1_arburst(att_d1_arburst),
  .a1_rvalid(att_d1_rvalid),.a1_rready(att_d1_rready),
  .a1_rdata(att_d1_rdata),.a1_rresp(att_d1_rresp),.a1_rlast(att_d1_rlast),
  .m0_arvalid(mlp_d0_arvalid),.m0_arready(mlp_d0_arready),
  .m0_araddr(mlp_d0_araddr),.m0_arlen(mlp_d0_arlen),
  .m0_arsize(mlp_d0_arsize),.m0_arburst(mlp_d0_arburst),
  .m0_rvalid(mlp_d0_rvalid),.m0_rready(mlp_d0_rready),
  .m0_rdata(mlp_d0_rdata),.m0_rresp(mlp_d0_rresp),.m0_rlast(mlp_d0_rlast),
  .m1_arvalid(mlp_d1_arvalid),.m1_arready(mlp_d1_arready),
  .m1_araddr(mlp_d1_araddr),.m1_arlen(mlp_d1_arlen),
  .m1_arsize(mlp_d1_arsize),.m1_arburst(mlp_d1_arburst),
  .m1_rvalid(mlp_d1_rvalid),.m1_rready(mlp_d1_rready),
  .m1_rdata(mlp_d1_rdata),.m1_rresp(mlp_d1_rresp),.m1_rlast(mlp_d1_rlast),
  .p0_arvalid(ddr0_axi_arvalid),.p0_arready(ddr0_axi_arready),
  .p0_araddr(ddr0_axi_araddr),.p0_arlen(ddr0_axi_arlen),
  .p0_arsize(ddr0_axi_arsize),.p0_arburst(ddr0_axi_arburst),
  .p0_rvalid(ddr0_axi_rvalid),.p0_rready(ddr0_axi_rready),
  .p0_rdata(ddr0_axi_rdata),.p0_rresp(ddr0_axi_rresp),.p0_rlast(ddr0_axi_rlast),
  .p1_arvalid(ddr1_axi_arvalid),.p1_arready(ddr1_axi_arready),
  .p1_araddr(ddr1_axi_araddr),.p1_arlen(ddr1_axi_arlen),
  .p1_arsize(ddr1_axi_arsize),.p1_arburst(ddr1_axi_arburst),
  .p1_rvalid(ddr1_axi_rvalid),.p1_rready(ddr1_axi_rready),
  .p1_rdata(ddr1_axi_rdata),.p1_rresp(ddr1_axi_rresp),.p1_rlast(ddr1_axi_rlast),
  .core_quiescent(paired_core_quiescent),.error(paired_error),
  .accepted_attn_bursts(),
  .accepted_mlp_bursts(),.both_eligible_cycles(),
  .p0_hol_cycles(),.p1_hol_cycles(),
  .p0_tag_high_watermark(),.p1_tag_high_watermark());
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n)begin
   state<=IDLE;d_r<=0;result_valid<=0;result_error<=0;result_reset_required<=0;result_input_bytes<=0;result_output_bytes<=0;result_cycles<=0;cycles<=0;abort_pending<=0;
  end else begin
   result_valid<=0;
   if(state!=IDLE&&cycles!=32'hffffffff)cycles<=cycles+1'b1;
   if(abort_valid)abort_pending<=1;
   case(state)
    IDLE:if(submit_valid&&submit_ready)begin
     d_r<=submit_descriptor;cycles<=0;result_error<=0;result_reset_required<=0;result_input_bytes<=0;result_output_bytes<=0;abort_pending<=abort_valid;state<=CHECK;
    end
    CHECK:begin
     if(check_error!=0)begin result_error<=check_error;state<=FINISH;end
     else if(abort_pending||abort_valid)begin result_error<=FINAL_ERR_ABORTED;state<=FINISH;end
     else if(d_r[128+:32]==1)state<=START_A;else state<=START_M;
    end
    START_A:if(a_ready)state<=RUN_A;
    RUN_A:if(a_done)begin result_input_bytes<=a_input_bytes;result_output_bytes<=a_output_bytes;state<=FINISH;end
    START_M:if(m_ready)state<=RUN_M;
    RUN_M:if(m_done)begin result_input_bytes<=m_input_bytes;result_output_bytes<=m_output_bytes;state<=FINISH;end
    FINISH:if(paired_core_quiescent)begin
     result_valid<=1;result_cycles<=cycles;if(abort_pending||abort_valid)result_error<=FINAL_ERR_ABORTED;state<=IDLE;
    end
    FAULT:begin
     // Preserve every live AXI source and all response state. No soft clear is
     // issued. The sticky reset-required completion prevents buffer reuse.
     result_valid<=1;result_cycles<=cycles;state<=IDLE;
    end
    default:begin result_error<=FINAL_ERR_RESET_REQUIRED;result_reset_required<=1;state<=FAULT;end
   endcase
   if(state!=IDLE&&state!=CHECK&&state!=FAULT&&(paired_error||
      ((state==RUN_A||state==START_A)&&a_error)||((state==RUN_M||state==START_M)&&m_error)))begin
    result_error<=FINAL_ERR_ARITHMETIC;result_reset_required<=1;state<=FAULT;
   end
  end
 end
endmodule
