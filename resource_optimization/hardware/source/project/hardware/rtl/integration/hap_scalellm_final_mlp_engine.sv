`timescale 1ns/1ps
// Final online MLP, one resident metadata image, no cohort lease dependency.
module hap_scalellm_final_mlp_engine #(
 parameter integer INTERMEDIATE_COLUMNS=14336,parameter integer ENFORCE_PRODUCTION_SHAPE=1
)(
 input wire core_clk,input wire core_rst_n,input wire start,input wire[2047:0]descriptor,
 output wire ready,output reg done,output wire error,output wire weight_source_quiescent,
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
 output wire[31:0]input_bytes,output wire[31:0]output_bytes
);
 localparam integer TILES=INTERMEDIATE_COLUMNS/16,META_RECORDS=2*TILES*128;
 localparam[3:0]IDLE=0,CLEAR=1,META_CMD=2,META_DATA=3,META_DRAIN=4,INPUT_CMD=5,INPUT_DATA=6,
 STORE_CMD=7,BEGIN=8,RUN=9,FAULT=15;
 reg[3:0]state;reg[2047:0]d_r;wire[31:0]d[0:63];genvar g;
 generate for(g=0;g<64;g=g+1)begin:g_d assign d[g]=d_r[g*32+:32];end endgenerate
 wire clear=state==CLEAR;
 wire dma_cmd_ready,dma_busy,dma_done,dma_error,dma_rd_valid,dma_rd_last,dma_wr_ready;
 wire[255:0]dma_rd_data;wire dma_rd_ready,dma_wr_valid;wire[255:0]dma_wr_data;
 wire dma_cmd_valid=state==META_CMD||state==INPUT_CMD||state==STORE_CMD;
 wire[31:0]dma_base=state==META_CMD?d[14]:state==INPUT_CMD?d[8]:d[9];
 wire[31:0]dma_beats=state==META_CMD?META_RECORDS:state==INPUT_CMD?6144:TILES*32;
 reg[17:0]artifact_index;reg[31:0]input_bytes_r,output_bytes_r;
 assign input_bytes=input_bytes_r;assign output_bytes=output_bytes_r;
 assign ready=state==IDLE;
    hap_axi256_dma u_dma (
        .clk(core_clk), .rst_n(core_rst_n), .clear(clear),
        .cmd_valid(dma_cmd_valid), .cmd_ready(dma_cmd_ready),
        .cmd_write(state==STORE_CMD), .cmd_base_addr(dma_base),
        .cmd_beat_count(dma_beats), .busy(dma_busy), .done(dma_done),
        .error(dma_error), .rd_valid(dma_rd_valid),
        .rd_ready(dma_rd_ready), .rd_data(dma_rd_data),
        .rd_last(dma_rd_last), .wr_valid(dma_wr_valid),
        .wr_ready(dma_wr_ready), .wr_data(dma_wr_data),
        .m_axi_arvalid(m_axi_arvalid), .m_axi_arready(m_axi_arready),
        .m_axi_araddr(m_axi_araddr), .m_axi_arlen(m_axi_arlen),
        .m_axi_arsize(m_axi_arsize), .m_axi_arburst(m_axi_arburst),
        .m_axi_rvalid(m_axi_rvalid), .m_axi_rready(m_axi_rready),
        .m_axi_rdata(m_axi_rdata), .m_axi_rresp(m_axi_rresp),
        .m_axi_rlast(m_axi_rlast), .m_axi_awvalid(m_axi_awvalid),
        .m_axi_awready(m_axi_awready), .m_axi_awaddr(m_axi_awaddr),
        .m_axi_awlen(m_axi_awlen), .m_axi_awsize(m_axi_awsize),
        .m_axi_awburst(m_axi_awburst), .m_axi_wvalid(m_axi_wvalid),
        .m_axi_wready(m_axi_wready), .m_axi_wdata(m_axi_wdata),
        .m_axi_wstrb(m_axi_wstrb), .m_axi_wlast(m_axi_wlast),
        .m_axi_bvalid(m_axi_bvalid), .m_axi_bready(m_axi_bready),
        .m_axi_bresp(m_axi_bresp), .command_count(), .read_beat_count(),
        .write_beat_count(), .burst_count(), .protocol_error_count()
    );

 wire meta_write_idle,meta_response_idle,meta_rd_valid,meta_rd_ready,meta_rsp_valid,meta_rsp_ready;
 wire[17:0]meta_rd_addr;wire[223:0]meta_rsp,gate_meta;wire gate_meta_valid,gate_meta_ready;
 wire meta_active,meta_error,meta_drained;
 wire meta_wr_valid=state==META_DATA&&dma_rd_valid&&dma_rd_data[255:224]==0&&!dma_error;
 hap_mlp_gu_weight_meta_uram_leaf #(.DEPTH(META_RECORDS))u_meta(
 .clk(core_clk),.rst_n(core_rst_n),.clear(clear),.wr_valid(meta_wr_valid),.wr_bank(1'b0),.wr_addr(artifact_index),.wr_data(dma_rd_data[223:0]),
 .rd_valid(meta_rd_valid),.rd_ready(meta_rd_ready),.rd_addr(meta_rd_addr),.rsp_valid(meta_rsp_valid),.rsp_ready(meta_rsp_ready),.rsp_data(meta_rsp),
 .response_idle(meta_response_idle),.write_idle(meta_write_idle));
 wire begin_ready,compute_done,compute_busy,compute_error;
 wire compute_begin=state==BEGIN&&begin_ready;
 hap_mlp_gu_metadata_scheduler #(.GATE_RECORDS(META_RECORDS),.PRODUCTION_SHAPE(ENFORCE_PRODUCTION_SHAPE))u_meta_schedule(
 .clk(core_clk),.rst_n(core_rst_n),.clear(clear),.command_start(compute_begin),.command_done(compute_done),.command_opcode(2'd1),
 .drained(meta_drained),.gate_enable(1'b1),.gate_rd_valid(meta_rd_valid),.gate_rd_ready(meta_rd_ready),.gate_rd_addr(meta_rd_addr),
 .gate_rsp_valid(meta_rsp_valid),.gate_rsp_ready(meta_rsp_ready),.gate_rsp_meta(meta_rsp),.gate_meta_valid(gate_meta_valid),.gate_meta_ready(gate_meta_ready),
 .gate_meta(gate_meta),.active(meta_active),.gate_issue_count(),.gate_delivery_count(),.done(),.error(meta_error));
 wire input_wr_ready,in_valid,in_ready,input_error;wire[8:0]in_group;wire[12287:0]in_data;
 hap_scalellm_final_input16 u_input(.clk(core_clk),.rst_n(core_rst_n),.clear(clear),.active_mask(d[6][15:0]),
 .wr_valid(state==INPUT_DATA&&dma_rd_valid),.wr_ready(input_wr_ready),.wr_addr(artifact_index[12:0]),.wr_data(dma_rd_data),
 .load_start(compute_begin),.out_valid(in_valid),.out_ready(in_ready),.out_group(in_group),.out_s24(in_data),.error(input_error));
 wire out_valid,out_ready,out_last;wire[8191:0]out_data;wire[9:0]out_tile;wire[31:0]out_tag;
 reg[8191:0]tile_buffer;reg tile_valid;reg[4:0]beat;reg[9:0]expected_tile;reg tensor_error;
 reg compute_complete,store_complete;
 wire[8191:0]masked_out;
 generate for(g=0;g<16;g=g+1)begin:g_outmask assign masked_out[g*512+:512]=d[6][g]?out_data[g*512+:512]:512'd0;end endgenerate
 assign out_ready=!tile_valid&&state==RUN;
 assign dma_wr_valid=tile_valid;assign dma_wr_data=tile_buffer[beat*256+:256];
 assign dma_rd_ready=state==META_DATA?1'b1:state==INPUT_DATA?input_wr_ready:state==FAULT?1'b1:1'b0;
 hap_mlp_online_compute16_s32 #(.INTERMEDIATE_COLUMNS(INTERMEDIATE_COLUMNS),.ENFORCE_PRODUCTION_SHAPE(ENFORCE_PRODUCTION_SHAPE))u_compute(
 .core_clk(core_clk),.core_rst_n(core_rst_n),.core_clear(clear),.begin_valid(state==BEGIN),.begin_ready(begin_ready),.begin_batch_tag(d[2]),
 .gate_ddr0_base_addr(d[12]),.gate_ddr1_base_addr(d[13]),.in_valid(in_valid),.in_ready(in_ready),.in_group(in_group),.in_s24x16x32(in_data),
 .gate_meta_valid(gate_meta_valid),.gate_meta_ready(gate_meta_ready),.gate_meta_u224(gate_meta),
 .ddr0_clk(ddr0_clk),
 .ddr0_rst_n(ddr0_rst_n),
 .ddr0_axi_arvalid(ddr0_axi_arvalid),
 .ddr0_axi_arready(ddr0_axi_arready),
 .ddr0_axi_araddr(ddr0_axi_araddr),
 .ddr0_axi_arlen(ddr0_axi_arlen),
 .ddr0_axi_arsize(ddr0_axi_arsize),
 .ddr0_axi_arburst(ddr0_axi_arburst),
 .ddr0_axi_rvalid(ddr0_axi_rvalid),
 .ddr0_axi_rready(ddr0_axi_rready),
 .ddr0_axi_rdata(ddr0_axi_rdata),
 .ddr0_axi_rresp(ddr0_axi_rresp),
 .ddr0_axi_rlast(ddr0_axi_rlast),
 .ddr1_clk(ddr1_clk),
 .ddr1_rst_n(ddr1_rst_n),
 .ddr1_axi_arvalid(ddr1_axi_arvalid),
 .ddr1_axi_arready(ddr1_axi_arready),
 .ddr1_axi_araddr(ddr1_axi_araddr),
 .ddr1_axi_arlen(ddr1_axi_arlen),
 .ddr1_axi_arsize(ddr1_axi_arsize),
 .ddr1_axi_arburst(ddr1_axi_arburst),
 .ddr1_axi_rvalid(ddr1_axi_rvalid),
 .ddr1_axi_rready(ddr1_axi_rready),
 .ddr1_axi_rdata(ddr1_axi_rdata),
 .ddr1_axi_rresp(ddr1_axi_rresp),
 .ddr1_axi_rlast(ddr1_axi_rlast),
 .out_valid(out_valid),.out_ready(out_ready),.out_s32x16x16(out_data),.out_tile(out_tile),.out_last(out_last),.out_batch_tag(out_tag),
 .busy(compute_busy),.done(compute_done),.error(compute_error),.weight_source_quiescent(weight_source_quiescent),
 .gu_saturation_count(),.gu_total_shift_format_count(),.gu_numeric_status());
 assign error=state==FAULT||dma_error||meta_error||compute_error||input_error||tensor_error;
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n)begin
   state<=IDLE;d_r<=0;done<=0;artifact_index<=0;input_bytes_r<=0;output_bytes_r<=0;tile_buffer<=0;tile_valid<=0;beat<=0;expected_tile<=0;
   tensor_error<=0;compute_complete<=0;store_complete<=0;
  end else begin
   done<=0;
   if(out_valid&&out_ready)begin
    tile_buffer<=masked_out;tile_valid<=1;beat<=0;expected_tile<=expected_tile+1;
    if(out_tile!=expected_tile||out_last!=(expected_tile==TILES-1)||out_tag!=d[2])tensor_error<=1;
   end
   if(dma_wr_valid&&dma_wr_ready)begin
    if(beat==31)begin beat<=0;tile_valid<=0;end else beat<=beat+1;
   end
   if(state==RUN&&dma_done)begin store_complete<=1;output_bytes_r<=TILES*1024;end
   if(compute_done)compute_complete<=1;
   case(state)
    IDLE:if(start&&ready)begin d_r<=descriptor;state<=CLEAR;end
    CLEAR:begin
     artifact_index<=0;input_bytes_r<=0;output_bytes_r<=0;tile_valid<=0;beat<=0;expected_tile<=0;tensor_error<=0;
     compute_complete<=0;store_complete<=0;state<=META_CMD;
    end
    META_CMD:if(dma_cmd_ready)begin artifact_index<=0;state<=META_DATA;end
    META_DATA:begin
     if(dma_rd_valid&&dma_rd_ready)begin
      artifact_index<=artifact_index+1'b1;
      if(dma_rd_data[255:224]!=0)tensor_error<=1;
     end
     if(dma_done)begin if(artifact_index!=META_RECORDS)state<=FAULT;else state<=META_DRAIN;end
    end
    META_DRAIN:if(meta_write_idle)state<=INPUT_CMD;
    INPUT_CMD:if(dma_cmd_ready)begin artifact_index<=0;state<=INPUT_DATA;end
    INPUT_DATA:begin
     if(dma_rd_valid&&dma_rd_ready)artifact_index<=artifact_index+1'b1;
     if(dma_done)begin if(artifact_index!=6144)state<=FAULT;else begin input_bytes_r<=196608;state<=STORE_CMD;end end
    end
    STORE_CMD:if(dma_cmd_ready)state<=BEGIN;
    BEGIN:if(begin_ready)state<=RUN;
    RUN:if((compute_complete||compute_done)&&(store_complete||dma_done)&&meta_drained&&meta_response_idle&&!dma_busy)begin
     if(expected_tile!=TILES||tile_valid)state<=FAULT;else begin done<=1;state<=IDLE;end
    end
    FAULT:begin end
    default:state<=FAULT;
   endcase
   if(state!=IDLE&&state!=CLEAR&&error)state<=FAULT;
  end
 end
endmodule
