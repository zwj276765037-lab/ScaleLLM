`timescale 1ns / 1ps

`ifndef HAP_ATTENTION_BOARD_MODULE
`define HAP_ATTENTION_BOARD_MODULE hap_attention_board_core
`endif

// Complete unchanged Attention core plus the GU-only cohort16 A8W4 command.
// The engine-native DDR ports are intentionally exposed separately.  The V4
// paired scheduler lives in the production integration layer so this compute
// block remains usable as a resource probe without duplicating the CDC leaf.
module hap_attention_mlp_resource_top_gu_only #(parameter integer INTERMEDIATE_COLUMNS=14336,HIDDEN_COLUMNS=4096,ENFORCE_PRODUCTION_SHAPE=1) (
    input wire core_clk,input wire core_rst_n,
    input wire ddr0_clk,input wire ddr0_rst_n,
    input wire ddr1_clk,input wire ddr1_rst_n,
    input wire command_pause,
    input wire engine_soft_clear,
    input wire mlp_abort_clear,
    input wire mlp_job_clear,
    input wire mlp_cache_begin_valid,output wire mlp_cache_begin_ready,
    input wire mlp_cache_seal_valid,output wire mlp_cache_seal_ready,
    output wire mlp_cache_sealed,output wire mlp_cache_quiescent,
    output wire mlp_compute_quiescent,output wire mlp_flow_stall,output wire [31:0] mlp_cache_error_code,
    input wire [1:0] mlp_command_opcode,
    output wire mlp_gu_valid,input wire mlp_gu_ready,
    output wire [6143:0] mlp_gu_s24x16x16,output wire [9:0] mlp_gu_tile,
    output wire mlp_gu_matrix,output wire mlp_gu_last,
    output wire attention_weight_source_quiescent,
    output wire mlp_weight_source_quiescent,
    input wire attention_launch_enable,
    output wire attention_quiescent,output wire attention_data_axi_busy,

    input wire [11:0] s_axil_awaddr,input wire s_axil_awvalid,
    output wire s_axil_awready,input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,input wire s_axil_wvalid,
    output wire s_axil_wready,output wire [1:0] s_axil_bresp,
    output wire s_axil_bvalid,input wire s_axil_bready,
    input wire [11:0] s_axil_araddr,input wire s_axil_arvalid,
    output wire s_axil_arready,output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,output wire s_axil_rvalid,
    input wire s_axil_rready,

    output wire m_axi_arvalid,input wire m_axi_arready,
    output wire [31:0] m_axi_araddr,output wire [7:0] m_axi_arlen,
    output wire [2:0] m_axi_arsize,output wire [1:0] m_axi_arburst,
    input wire m_axi_rvalid,output wire m_axi_rready,
    input wire [255:0] m_axi_rdata,input wire [1:0] m_axi_rresp,
    input wire m_axi_rlast,output wire m_axi_awvalid,
    input wire m_axi_awready,output wire [31:0] m_axi_awaddr,
    output wire [7:0] m_axi_awlen,output wire [2:0] m_axi_awsize,
    output wire [1:0] m_axi_awburst,output wire m_axi_wvalid,
    input wire m_axi_wready,output wire [255:0] m_axi_wdata,
    output wire [31:0] m_axi_wstrb,output wire m_axi_wlast,
    input wire m_axi_bvalid,output wire m_axi_bready,
    input wire [1:0] m_axi_bresp,output wire attention_irq,

    input wire mlp_input_valid,output wire mlp_input_ready,
    input wire mlp_input_bank,input wire [8:0] mlp_input_group,
    input wire [4095:0] mlp_input_u8x16x32,
    input wire [383:0] mlp_input_meta_u24x16,
    output wire [1:0] mlp_input_bank_ready,
    input wire mlp_command_valid,output wire mlp_command_ready,
    input wire mlp_command_bank,
    input wire [31:0] mlp_gate_ddr0_base_addr,
    input wire [31:0] mlp_gate_ddr1_base_addr,
    input wire mlp_gate_meta_valid,output wire mlp_gate_meta_ready,
    input wire [223:0] mlp_gate_meta_u224,
    output wire mlp_busy,output wire mlp_done,output wire mlp_error,
    output wire [2:0] mlp_phase,
    output wire [1567:0] mlp_telemetry,
    output wire [31:0] mlp_total_shift_format_count,
    output wire [31:0] mlp_numeric_status,

    output wire att_d0_arvalid,input wire att_d0_arready,
    output wire [31:0] att_d0_araddr,output wire [7:0] att_d0_arlen,
    output wire [2:0] att_d0_arsize,output wire [1:0] att_d0_arburst,
    input wire att_d0_rvalid,output wire att_d0_rready,
    input wire [511:0] att_d0_rdata,input wire [1:0] att_d0_rresp,
    input wire att_d0_rlast,
    output wire att_d1_arvalid,input wire att_d1_arready,
    output wire [31:0] att_d1_araddr,output wire [7:0] att_d1_arlen,
    output wire [2:0] att_d1_arsize,output wire [1:0] att_d1_arburst,
    input wire att_d1_rvalid,output wire att_d1_rready,
    input wire [511:0] att_d1_rdata,input wire [1:0] att_d1_rresp,
    input wire att_d1_rlast,
    output wire mlp_d0_arvalid,input wire mlp_d0_arready,
    output wire [31:0] mlp_d0_araddr,output wire [7:0] mlp_d0_arlen,
    output wire [2:0] mlp_d0_arsize,output wire [1:0] mlp_d0_arburst,
    input wire mlp_d0_rvalid,output wire mlp_d0_rready,
    input wire [511:0] mlp_d0_rdata,input wire [1:0] mlp_d0_rresp,
    input wire mlp_d0_rlast,
    output wire mlp_d1_arvalid,input wire mlp_d1_arready,
    output wire [31:0] mlp_d1_araddr,output wire [7:0] mlp_d1_arlen,
    output wire [2:0] mlp_d1_arsize,output wire [1:0] mlp_d1_arburst,
    input wire mlp_d1_rvalid,output wire mlp_d1_rready,
    input wire [511:0] mlp_d1_rdata,input wire [1:0] mlp_d1_rresp,
    input wire mlp_d1_rlast
);
    `HAP_ATTENTION_BOARD_MODULE u_attention(
      .core_clk(core_clk),.core_rst_n(core_rst_n),
      .s_axil_awaddr(s_axil_awaddr),.s_axil_awvalid(s_axil_awvalid),
      .s_axil_awready(s_axil_awready),.s_axil_wdata(s_axil_wdata),
      .s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),
      .s_axil_wready(s_axil_wready),.s_axil_bresp(s_axil_bresp),
      .s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
      .s_axil_araddr(s_axil_araddr),.s_axil_arvalid(s_axil_arvalid),
      .s_axil_arready(s_axil_arready),.s_axil_rdata(s_axil_rdata),
      .s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),
      .s_axil_rready(s_axil_rready),
      .m_axi_arvalid(m_axi_arvalid),.m_axi_arready(m_axi_arready),
      .m_axi_araddr(m_axi_araddr),.m_axi_arlen(m_axi_arlen),
      .m_axi_arsize(m_axi_arsize),.m_axi_arburst(m_axi_arburst),
      .m_axi_rvalid(m_axi_rvalid),.m_axi_rready(m_axi_rready),
      .m_axi_rdata(m_axi_rdata),.m_axi_rresp(m_axi_rresp),
      .m_axi_rlast(m_axi_rlast),.m_axi_awvalid(m_axi_awvalid),
      .m_axi_awready(m_axi_awready),.m_axi_awaddr(m_axi_awaddr),
      .m_axi_awlen(m_axi_awlen),.m_axi_awsize(m_axi_awsize),
      .m_axi_awburst(m_axi_awburst),.m_axi_wvalid(m_axi_wvalid),
      .m_axi_wready(m_axi_wready),.m_axi_wdata(m_axi_wdata),
      .m_axi_wstrb(m_axi_wstrb),.m_axi_wlast(m_axi_wlast),
      .m_axi_bvalid(m_axi_bvalid),.m_axi_bready(m_axi_bready),
      .m_axi_bresp(m_axi_bresp),.ddr0_clk(ddr0_clk),
      .ddr0_rst_n(ddr0_rst_n),.ddr0_axi_arvalid(att_d0_arvalid),
      .ddr0_axi_arready(att_d0_arready),.ddr0_axi_araddr(att_d0_araddr),
      .ddr0_axi_arlen(att_d0_arlen),.ddr0_axi_arsize(att_d0_arsize),
      .ddr0_axi_arburst(att_d0_arburst),
      .ddr0_axi_rvalid(att_d0_rvalid),
      .ddr0_axi_rready(att_d0_rready),.ddr0_axi_rdata(att_d0_rdata),
      .ddr0_axi_rresp(att_d0_rresp),.ddr0_axi_rlast(att_d0_rlast),
      .ddr1_clk(ddr0_clk),.ddr1_rst_n(ddr0_rst_n),
      .ddr1_axi_arvalid(att_d1_arvalid),.ddr1_axi_arready(att_d1_arready),
      .ddr1_axi_araddr(att_d1_araddr),.ddr1_axi_arlen(att_d1_arlen),
      .ddr1_axi_arsize(att_d1_arsize),.ddr1_axi_arburst(att_d1_arburst),
      .ddr1_axi_rvalid(att_d1_rvalid),
      .ddr1_axi_rready(att_d1_rready),.ddr1_axi_rdata(att_d1_rdata),
      .ddr1_axi_rresp(att_d1_rresp),.ddr1_axi_rlast(att_d1_rlast),
      .attention_launch_enable(attention_launch_enable),
      .engine_soft_clear(engine_soft_clear),
      .command_pause(command_pause),
      .weight_source_quiescent(attention_weight_source_quiescent),
      .ddr_quiescent(attention_quiescent),
      .data_axi_busy(attention_data_axi_busy),
      .irq(attention_irq));

    wire [31:0] c0,c1,c2,c3,g0,g1,g2,g3,g4,g5,g6,g7,g8,g9,g10,g11,g12,g13;
    wire [63:0] gp,gu;
    wire [31:0] d0,d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13;
    wire [63:0] dp=0,du=0;
    assign {d0,d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13}=0;
    wire [31:0] x0,x1,x2,x3,x4,x5,x6,x7,x8;
    assign {x3,x4,x5,x6,x7}=0; // v7 reserved observation slots have no Down logic.
    assign mlp_telemetry={x8,x7,x6,x5,x4,x3,x2,x1,x0,du,dp,
      d13,d12,d11,d10,d9,d8,d7,d6,d5,d4,d3,d2,d1,d0,gu,gp,
      g13,g12,g11,g10,g9,g8,g7,g6,g5,g4,g3,g2,g1,g0,c3,c2,c1,c0};

    wire mlp_engine_clear=engine_soft_clear||mlp_job_clear;
    wire req_valid,req_ready,rsp_valid,rsp_ready,req_bank;
    wire [8:0] req_group,rsp_group;
    wire [4095:0] rsp_u8;wire [383:0] rsp_meta;
    wire cache_error;wire [8:0] cache_write_count,cache_expected;wire cache_owned;
    wire compute_error;
    assign mlp_input_bank_ready={1'b0,mlp_cache_sealed};
    assign mlp_error=compute_error||cache_error;
    assign c0={23'd0,cache_write_count};assign c1=x0;assign c2=0;assign c3=0;
    hap_mlp_gu_cache16 u_cache(
      .clk(core_clk),.rst_n(core_rst_n),.job_clear(mlp_engine_clear),
      .begin_valid(mlp_cache_begin_valid),.begin_ready(mlp_cache_begin_ready),.begin_opcode(mlp_command_opcode),
      .wr_valid(mlp_input_valid),.wr_ready(mlp_input_ready),.wr_group(mlp_input_group),
      .wr_u8x16x32(mlp_input_u8x16x32),.wr_meta_u24x16(mlp_input_meta_u24x16),
      .seal_valid(mlp_cache_seal_valid),.seal_ready(mlp_cache_seal_ready),.sealed(mlp_cache_sealed),
      .rd_req_valid(req_valid),.rd_req_ready(req_ready),.rd_req_group(req_group),
      .rd_rsp_valid(rsp_valid),.rd_rsp_ready(rsp_ready),.rd_rsp_group(rsp_group),.rd_rsp_u8x16x32(rsp_u8),.rd_rsp_meta_u24x16(rsp_meta),
      .write_count(cache_write_count),.expected_groups(cache_expected),.owned(cache_owned),.quiescent(mlp_cache_quiescent),.error(cache_error),.error_code(mlp_cache_error_code));
// M002 logical channel names are preserved; both MLP readers use DDR1.
    hap_mlp_gu_compute16_s44 #(.INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS),.HIDDEN_COLUMNS(HIDDEN_COLUMNS),.ENFORCE_PRODUCTION_SHAPE(ENFORCE_PRODUCTION_SHAPE)) u_mlp(
      .core_clk(core_clk),.core_rst_n(core_rst_n),
      .core_clear(mlp_engine_clear),
      .command_pause(1'b0),
      .weight_source_quiescent(mlp_weight_source_quiescent),
      .command_valid(mlp_command_valid),.command_ready(mlp_command_ready),
      .command_opcode(mlp_command_opcode),.cache_sealed(mlp_cache_sealed),
      .cache_rd_req_valid(req_valid),.cache_rd_req_ready(req_ready),.cache_rd_req_bank(req_bank),.cache_rd_req_group(req_group),
      .cache_rd_rsp_valid(rsp_valid),.cache_rd_rsp_ready(rsp_ready),.cache_rd_rsp_bank(1'b0),.cache_rd_rsp_group(rsp_group),
      .cache_rd_rsp_u8x16x32(rsp_u8),.cache_rd_rsp_meta_u24x16(rsp_meta),
      .gu_out_valid(mlp_gu_valid),.gu_out_ready(mlp_gu_ready),.gu_out_s24x16x16(mlp_gu_s24x16x16),
      .gu_out_tile(mlp_gu_tile),.gu_out_matrix(mlp_gu_matrix),.gu_out_last(mlp_gu_last),.compute_quiescent(mlp_compute_quiescent),.flow_stall(mlp_flow_stall),
      .gate_ddr0_base_addr(mlp_gate_ddr0_base_addr),
      .gate_ddr1_base_addr(mlp_gate_ddr1_base_addr),
      .gate_meta_valid(mlp_gate_meta_valid),
      .gate_meta_ready(mlp_gate_meta_ready),.gate_meta_u224(mlp_gate_meta_u224),
      .ddr0_clk(ddr1_clk),.ddr0_rst_n(ddr1_rst_n),
      .ddr0_axi_arvalid(mlp_d0_arvalid),.ddr0_axi_arready(mlp_d0_arready),
      .ddr0_axi_araddr(mlp_d0_araddr),.ddr0_axi_arlen(mlp_d0_arlen),
      .ddr0_axi_arsize(mlp_d0_arsize),.ddr0_axi_arburst(mlp_d0_arburst),
      .ddr0_axi_rvalid(mlp_d0_rvalid),
      .ddr0_axi_rready(mlp_d0_rready),.ddr0_axi_rdata(mlp_d0_rdata),
      .ddr0_axi_rresp(mlp_d0_rresp),.ddr0_axi_rlast(mlp_d0_rlast),
      .ddr1_clk(ddr1_clk),.ddr1_rst_n(ddr1_rst_n),
      .ddr1_axi_arvalid(mlp_d1_arvalid),.ddr1_axi_arready(mlp_d1_arready),
      .ddr1_axi_araddr(mlp_d1_araddr),.ddr1_axi_arlen(mlp_d1_arlen),
      .ddr1_axi_arsize(mlp_d1_arsize),.ddr1_axi_arburst(mlp_d1_arburst),
      .ddr1_axi_rvalid(mlp_d1_rvalid),
      .ddr1_axi_rready(mlp_d1_rready),.ddr1_axi_rdata(mlp_d1_rdata),
      .ddr1_axi_rresp(mlp_d1_rresp),.ddr1_axi_rlast(mlp_d1_rlast),
      .busy(mlp_busy),.done(mlp_done),.error(compute_error),.phase(mlp_phase),
      .gate_ddr0_raw_beats(g0),.gate_ddr1_raw_beats(g1),
      .gate_ddr0_elapsed_cycles(g2),.gate_ddr1_elapsed_cycles(g3),
      .gate_ddr0_bursts(g4),.gate_ddr1_bursts(g5),
      .gate_ddr0_ar_stalls(g6),.gate_ddr1_ar_stalls(g7),
      .gate_ddr0_r_backpressure(g8),.gate_ddr1_r_backpressure(g9),
      .gate_ddr0_response_idle(g10),.gate_ddr1_response_idle(g11),
      .gate_ddr0_max_outstanding(g12),.gate_ddr1_max_outstanding(g13),
      .gate_physical_bytes(gp),.gate_useful_bytes(gu),
      .gate_cache_request_count(x0),.gate_weight_group_count(x1),
      .gate_projection_tile_count(x2),
      .saturation_count(x8),
      .total_shift_format_count(mlp_total_shift_format_count),
      .numeric_status(mlp_numeric_status));
 initial begin
 if(ENFORCE_PRODUCTION_SHAPE&&(INTERMEDIATE_COLUMNS!=14336||HIDDEN_COLUMNS!=4096))$error("M006 production output shape required");
 if(INTERMEDIATE_COLUMNS<=0||INTERMEDIATE_COLUMNS>14336||(INTERMEDIATE_COLUMNS%32)!=0||HIDDEN_COLUMNS!=4096)$error("M006 bounded test shape invalid");
 end
endmodule
