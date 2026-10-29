`timescale 1ns/1ps
// Final request-aware Attention board engine. Dedicated DDR0 logical halves.
module hap_scalellm_final_attention_engine (
 input wire core_clk,input wire core_rst_n,input wire start,input wire [2047:0] descriptor,
 output wire ready,output reg done,output wire error,output wire weight_source_quiescent,
 output wire ddr_quiescent,output wire data_axi_busy,
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
 output wire [31:0] input_bytes,output wire [31:0] output_bytes
);
 localparam[3:0]ST_IDLE=0,ST_CLEAR=1,ST_META_CMD=2,ST_META_DATA=3,ST_ROPE_CMD=4,ST_ROPE_DATA=5,
 ST_INPUT_CMD=6,ST_INPUT_DATA=7,ST_LAUNCH=8,ST_RUN=9,ST_OUTPUT_CMD=10,ST_OUTPUT_DATA=11,ST_ERROR=15;
 reg[3:0]state_r;reg[2047:0]d_r;
 wire[31:0]d[0:63];genvar g;
 generate for(g=0;g<64;g=g+1)begin:g_d assign d[g]=d_r[g*32+:32];end endgenerate
 wire[127:0]positions;wire[511:0]epochs;
 generate for(g=0;g<16;g=g+1)begin:g_rows assign positions[g*8+:8]=d[32+2*g][7:0];assign epochs[g*32+:32]=d[33+2*g];end endgenerate
 wire datapath_clear=state_r==ST_CLEAR,system_clear=datapath_clear,compute_clear=datapath_clear;
 wire command_pause=1'b1;
 wire[31:0]active_weight_meta_base_r=d[14],active_rope_base_r=d[15],active_input_base_r=d[8],active_output_base_r=d[9];
 wire[31:0]active_weight_c0_base_r=d[12],active_weight_c1_base_r=d[13];
 wire engine_busy=state_r!=ST_IDLE;
 assign ready=state_r==ST_IDLE;assign input_bytes=(done||state_r>=ST_LAUNCH)?32'd196608:0;
 assign output_bytes=state_r==ST_IDLE&&done?32'd196608:0;
 wire compute_busy,compute_done,compute_error;
 reg compute_complete_r,rope_dma_complete_r;
 wire weight_command_ready;
 wire dma_done,dma_cmd_ready,dma_busy,dma_error;
 wire kv_cmd_valid,kv_cmd_ready,kv_cmd_write;wire[31:0]kv_cmd_base,kv_cmd_beats;
 wire kv_rd_ready,kv_wr_valid;wire[255:0]kv_wr_data;wire kv_error;
 wire dma_cmd_valid=(state_r==ST_META_CMD)||(state_r==ST_ROPE_CMD)||(state_r==ST_INPUT_CMD)||(state_r==ST_OUTPUT_CMD)||(state_r==ST_RUN&&kv_cmd_valid);
 wire dma_cmd_write=state_r==ST_OUTPUT_CMD||(state_r==ST_RUN&&kv_cmd_write);
 wire[31:0]dma_cmd_base=state_r==ST_META_CMD?active_weight_meta_base_r:state_r==ST_ROPE_CMD?active_rope_base_r:state_r==ST_INPUT_CMD?active_input_base_r:state_r==ST_RUN?kv_cmd_base:active_output_base_r;
 wire[31:0]dma_cmd_beats=state_r==ST_META_CMD?32'd81920:state_r==ST_ROPE_CMD?32'd256:state_r==ST_RUN?kv_cmd_beats:32'd6144;
 wire dma_rd_valid,dma_rd_ready,dma_rd_last;wire[255:0]dma_rd_data;
 wire dma_wr_valid,dma_wr_ready;wire[255:0]dma_wr_data;
 assign kv_cmd_ready=state_r==ST_RUN&&dma_cmd_ready;assign data_axi_busy=dma_busy;
    hap_axi256_dma u_dma (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
        .cmd_valid(dma_cmd_valid), .cmd_ready(dma_cmd_ready),
        .cmd_write(dma_cmd_write), .cmd_base_addr(dma_cmd_base),
        .cmd_beat_count(dma_cmd_beats), .busy(dma_busy), .done(dma_done),
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

    reg [16:0] artifact_index_r;
    wire meta_wr_valid = state_r==ST_META_DATA && dma_rd_valid;
    wire meta_wr_ready;
    wire meta_rd_ready, meta_rsp_valid, meta_rsp_ready;
    wire [255:0] meta_rsp_data;
    wire meta_store_error;
    reg [16:0] meta_read_addr_r;
    reg meta_read_pending_r;
    wire meta_rd_valid = state_r==ST_RUN &&
        (meta_read_addr_r < 17'd81920) && !meta_read_pending_r;
    wire meta_rd_fire = meta_rd_valid && meta_rd_ready;
    wire meta_rsp_fire = meta_rsp_valid && meta_rsp_ready;

    hap_weight_meta_resident #(.LOCAL_ADDR_COPIES(1)) u_meta (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
        .addr_system_clear(system_clear),
        .addr_launch(state_r==ST_LAUNCH && weight_command_ready),
        .wr_valid(meta_wr_valid), .wr_ready(meta_wr_ready),
        .wr_addr(artifact_index_r), .wr_meta16(dma_rd_data),
        .rd_valid(meta_rd_valid), .rd_ready(meta_rd_ready),
        .rd_addr(meta_read_addr_r), .rsp_valid(meta_rsp_valid),
        .rsp_ready(meta_rsp_ready), .rsp_meta16(meta_rsp_data),
        .write_count(), .read_count(), .format_error_count(),
        .error(meta_store_error)
    );

    reg rope_buffer_valid_r;
    reg [255:0] rope_buffer_r;
    reg [1:0] rope_subindex_r;
    reg [9:0] rope_record_addr_r;
    wire rope_wr_valid = state_r==ST_ROPE_DATA && rope_buffer_valid_r;
    wire rope_wr_ready;
    wire [63:0] rope_record =
        rope_buffer_r[rope_subindex_r*64 +: 64];

    wire input_wr_valid = state_r==ST_INPUT_DATA && dma_rd_valid;
    wire input_wr_ready;
    wire activation_valid, activation_ready;
    wire activation_wave;
    wire [6:0] activation_group;
    wire [6143:0] activation_s24;
    wire input_buffer_busy, input_buffer_error;
    wire input_load_start = state_r==ST_LAUNCH && weight_command_ready;
    hap_tensor24_input_buffer16 u_input_buffer (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
        .wr_valid(input_wr_valid), .wr_ready(input_wr_ready),
        .wr_addr(artifact_index_r[12:0]), .wr_data(dma_rd_data),
        .load_start(input_load_start),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_wave(activation_wave),
        .activation_group(activation_group),
        .activation_s24(activation_s24), .busy(input_buffer_busy),
        .error(input_buffer_error)
    );

    wire weight_command_valid = state_r==ST_LAUNCH;
    wire weight_frontend_busy, weight_frontend_error;
    assign ddr_quiescent = !engine_busy && !weight_frontend_busy;
    wire weight_valid, weight_ready;
    wire [9:0] weight_tile;
    wire [6:0] weight_group;
    wire [4095:0] weight_s8;
    wire [255:0] weight_meta16;
    hap_dual_ddr_weight_frontend u_weight_frontend (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_clear(datapath_clear), .command_valid(weight_command_valid),
        .command_ready(weight_command_ready),
        .ddr0_base_addr(active_weight_c0_base_r),
        .ddr1_base_addr(active_weight_c1_base_r),
        .group_count(17'd81920), .ddr0_clk(ddr0_clk),
        .ddr0_rst_n(ddr0_rst_n), .ddr0_axi_arvalid(ddr0_axi_arvalid),
        .ddr0_axi_arready(ddr0_axi_arready),
        .ddr0_axi_araddr(ddr0_axi_araddr), .ddr0_axi_arlen(ddr0_axi_arlen),
        .ddr0_axi_arsize(ddr0_axi_arsize),
        .ddr0_axi_arburst(ddr0_axi_arburst),
        .ddr0_axi_rvalid(ddr0_axi_rvalid),
        .ddr0_axi_rready(ddr0_axi_rready), .ddr0_axi_rdata(ddr0_axi_rdata),
        .ddr0_axi_rresp(ddr0_axi_rresp), .ddr0_axi_rlast(ddr0_axi_rlast),
        .ddr1_clk(ddr1_clk), .ddr1_rst_n(ddr1_rst_n),
        .ddr1_axi_arvalid(ddr1_axi_arvalid),
        .ddr1_axi_arready(ddr1_axi_arready),
        .ddr1_axi_araddr(ddr1_axi_araddr), .ddr1_axi_arlen(ddr1_axi_arlen),
        .ddr1_axi_arsize(ddr1_axi_arsize),
        .ddr1_axi_arburst(ddr1_axi_arburst),
        .ddr1_axi_rvalid(ddr1_axi_rvalid),
        .ddr1_axi_rready(ddr1_axi_rready), .ddr1_axi_rdata(ddr1_axi_rdata),
        .ddr1_axi_rresp(ddr1_axi_rresp), .ddr1_axi_rlast(ddr1_axi_rlast),
        .meta_valid(meta_rsp_valid), .meta_ready(meta_rsp_ready),
        .meta_tile(meta_read_addr_r[16:7]),
        .meta_group(meta_read_addr_r[6:0]), .meta16(meta_rsp_data),
        .out_valid(weight_valid), .out_ready(weight_ready),
        .out_tile(weight_tile), .out_group(weight_group),
        .out_weight_s8(weight_s8), .out_meta16(weight_meta16),
        .busy(weight_frontend_busy), .error(weight_frontend_error)
    );
assign weight_source_quiescent=!weight_command_valid&&!weight_frontend_busy;
    wire compute_out_valid, compute_out_ready;
    wire compute_out_wave;
    wire [7:0] compute_out_tile;
    wire [3071:0] compute_out_s24;
    wire output_image_ready, output_buffer_error;
    wire output_rd_valid, output_rd_ready, output_rsp_valid;
    wire [255:0] output_rsp_data;
    reg [12:0] output_read_addr_r;
    wire output_rsp_fire = output_rsp_valid && dma_wr_ready;
    assign dma_wr_valid = state_r==ST_RUN ? kv_wr_valid : state_r==ST_OUTPUT_DATA && output_rsp_valid;
    assign dma_wr_data = state_r==ST_RUN ? kv_wr_data : output_rsp_data;
    assign output_rd_valid = state_r==ST_OUTPUT_DATA &&
        (output_read_addr_r < 13'd6144);
    hap_tensor24_output_buffer16 u_output_buffer (
        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),
        .in_valid(compute_out_valid), .in_ready(compute_out_ready),
        .in_wave(compute_out_wave), .in_tile(compute_out_tile),
        .in_s24(compute_out_s24),
        .image_ready(output_image_ready), .image_release(dma_done &&
            state_r==ST_OUTPUT_DATA), .rd_valid(output_rd_valid),
        .rd_ready(output_rd_ready), .rd_addr(output_read_addr_r),
        .rsp_valid(output_rsp_valid), .rsp_ready(dma_wr_ready),
        .rsp_data(output_rsp_data), .error(output_buffer_error)
    );

 wire compute_start=state_r==ST_LAUNCH&&weight_command_ready;
 wire kv_append_valid,kv_append_ready,kv_append_is_v,kv_append_last;
 wire[31:0]kv_append_command,kv_append_epoch;wire[5:0]kv_append_layer;wire[3:0]kv_append_slot;
 wire[6:0]kv_append_position;wire[2:0]kv_append_head;wire[1:0]kv_append_group;
 wire[383:0]kv_append_s12;wire[15:0]kv_append_meta;
 wire write_commit_valid,write_commit_ready,write_commit_success;wire[31:0]write_commit_command;
 wire[5:0]write_commit_layer;wire[511:0]write_commit_epochs;
 wire kv_load_request_valid,kv_load_request_ready;wire[31:0]kv_load_request_command,kv_load_request_epoch;
 wire[5:0]kv_load_request_layer;wire[3:0]kv_load_request_slot;wire[7:0]kv_load_request_length;
 wire kv_load_valid,kv_load_ready,kv_load_is_v,kv_load_last,kv_load_error;
 wire[31:0]kv_load_command,kv_load_epoch;wire[4:0]kv_load_layer;wire[3:0]kv_load_slot;
 wire[6:0]kv_load_position;wire[2:0]kv_load_head;wire[1:0]kv_load_group;wire[383:0]kv_load_s12;wire[15:0]kv_load_meta;
 hap_attention_decode16_top u_compute(
 .clk(core_clk),.rst_n(core_rst_n),.clear(compute_clear),.start(compute_start),
 .format_id(d[18]),.command_id(d[2]),.batch_id(d[3][15:0]),.layer_id(d[5][5:0]),
 .active_mask(d[6][15:0]),.row_positions(positions),.row_epochs(epochs),
 .busy(compute_busy),.done(compute_done),.error(compute_error),
 .rope_wr_valid(rope_wr_valid),.rope_wr_ready(rope_wr_ready),.rope_wr_addr(rope_record_addr_r),
 .rope_wr_cos_s18(rope_record[17:0]),.rope_wr_sin_s18(rope_record[35:18]),
 .activation_valid(activation_valid),.activation_ready(activation_ready),.activation_wave(activation_wave),
 .activation_group(activation_group),.activation_s24(activation_s24),
 .weight_valid(weight_valid),.weight_ready(weight_ready),.weight_tile(weight_tile),.weight_group(weight_group),
 .weight_s8(weight_s8),.weight_meta16(weight_meta16),
 .out_valid(compute_out_valid),.out_ready(compute_out_ready),.out_wave(compute_out_wave),.out_tile(compute_out_tile),.out_s24(compute_out_s24),
 .kv_append_valid(kv_append_valid),
 .kv_append_ready(kv_append_ready),
 .kv_append_command(kv_append_command),
 .kv_append_layer(kv_append_layer),
 .kv_append_slot(kv_append_slot),
 .kv_append_epoch(kv_append_epoch),
 .kv_append_position(kv_append_position),
 .kv_append_is_v(kv_append_is_v),
 .kv_append_head(kv_append_head),
 .kv_append_group(kv_append_group),
 .kv_append_s12(kv_append_s12),
 .kv_append_meta(kv_append_meta),
 .kv_append_last(kv_append_last),
 .write_commit_valid(write_commit_valid),
 .write_commit_ready(write_commit_ready),
 .write_commit_command(write_commit_command),
 .write_commit_layer(write_commit_layer),
 .write_commit_epochs(write_commit_epochs),
 .write_commit_success(write_commit_success),
 .kv_load_request_valid(kv_load_request_valid),
 .kv_load_request_ready(kv_load_request_ready),
 .kv_load_request_command(kv_load_request_command),
 .kv_load_request_layer(kv_load_request_layer),
 .kv_load_request_slot(kv_load_request_slot),
 .kv_load_request_epoch(kv_load_request_epoch),
 .kv_load_request_length(kv_load_request_length),
 .kv_load_valid(kv_load_valid),
 .kv_load_ready(kv_load_ready),
 .kv_load_command(kv_load_command),
 .kv_load_layer(kv_load_layer),
 .kv_load_slot(kv_load_slot),
 .kv_load_epoch(kv_load_epoch),
 .kv_load_position(kv_load_position),
 .kv_load_is_v(kv_load_is_v),
 .kv_load_head(kv_load_head),
 .kv_load_group(kv_load_group),
 .kv_load_s12(kv_load_s12),
 .kv_load_meta(kv_load_meta),
 .kv_load_last(kv_load_last),
 .kv_load_error(kv_load_error)
 );
 hap_scalellm_final_kv_dma u_kv(
 .clk(core_clk),.rst_n(core_rst_n),.clear(datapath_clear),.begin_command(compute_start),
 .command_id(d[2]),.layer_id(d[5][5:0]),.active_mask(d[6][15:0]),.row_positions(positions),.row_epochs(epochs),
 .append_valid(kv_append_valid),
 .append_ready(kv_append_ready),
 .append_command(kv_append_command),
 .append_layer(kv_append_layer),
 .append_slot(kv_append_slot),
 .append_epoch(kv_append_epoch),
 .append_position(kv_append_position),
 .append_is_v(kv_append_is_v),
 .append_head(kv_append_head),
 .append_group(kv_append_group),
 .append_s12(kv_append_s12),
 .append_meta(kv_append_meta),
 .append_last(kv_append_last),
 .commit_valid(write_commit_valid),
 .commit_ready(write_commit_ready),
 .commit_command(write_commit_command),
 .commit_layer(write_commit_layer),
 .commit_epochs(write_commit_epochs),
 .commit_success(write_commit_success),
 .request_valid(kv_load_request_valid),
 .request_ready(kv_load_request_ready),
 .request_command(kv_load_request_command),
 .request_layer(kv_load_request_layer),
 .request_slot(kv_load_request_slot),
 .request_epoch(kv_load_request_epoch),
 .request_length(kv_load_request_length),
 .load_valid(kv_load_valid),
 .load_ready(kv_load_ready),
 .load_command(kv_load_command),
 .load_layer(kv_load_layer),
 .load_slot(kv_load_slot),
 .load_epoch(kv_load_epoch),
 .load_position(kv_load_position),
 .load_is_v(kv_load_is_v),
 .load_head(kv_load_head),
 .load_group(kv_load_group),
 .load_s12(kv_load_s12),
 .load_meta(kv_load_meta),
 .load_last(kv_load_last),
 .load_error(kv_load_error),
 .dma_cmd_valid(kv_cmd_valid),.dma_cmd_ready(kv_cmd_ready),.dma_cmd_write(kv_cmd_write),.dma_cmd_base(kv_cmd_base),.dma_cmd_beats(kv_cmd_beats),
 .dma_done(state_r==ST_RUN&&dma_done),.dma_error(dma_error),
 .dma_rd_valid(state_r==ST_RUN&&dma_rd_valid),.dma_rd_ready(kv_rd_ready),.dma_rd_data(dma_rd_data),
 .dma_wr_valid(kv_wr_valid),.dma_wr_ready(state_r==ST_RUN&&dma_wr_ready),.dma_wr_data(kv_wr_data),.error(kv_error),.idle(),.append_count(),.reload_count());
 assign dma_rd_ready=state_r==ST_META_DATA?meta_wr_ready:state_r==ST_ROPE_DATA?!rope_buffer_valid_r:
 state_r==ST_INPUT_DATA?input_wr_ready:state_r==ST_RUN?kv_rd_ready:state_r==ST_ERROR?1'b1:1'b0;
 assign error=state_r==ST_ERROR||dma_error||meta_store_error||input_buffer_error||weight_frontend_error||output_buffer_error||compute_error||kv_error;
 always @(posedge core_clk or negedge core_rst_n)begin
  if(!core_rst_n)begin
   state_r<=ST_IDLE;d_r<=0;done<=0;artifact_index_r<=0;rope_buffer_valid_r<=0;rope_buffer_r<=0;rope_subindex_r<=0;rope_record_addr_r<=0;
   meta_read_addr_r<=0;meta_read_pending_r<=0;output_read_addr_r<=0;compute_complete_r<=0;rope_dma_complete_r<=0;
  end else begin
   done<=0;
   if(meta_rd_fire)meta_read_pending_r<=1;
   if(meta_rsp_fire)begin meta_read_pending_r<=0;meta_read_addr_r<=meta_read_addr_r+1'b1;end
   if(output_rd_valid&&output_rd_ready)output_read_addr_r<=output_read_addr_r+1'b1;
   case(state_r)
    ST_IDLE:if(start&&ready)begin d_r<=descriptor;state_r<=ST_CLEAR;end
    ST_CLEAR:begin
     artifact_index_r<=0;rope_buffer_valid_r<=0;rope_subindex_r<=0;rope_record_addr_r<=0;meta_read_addr_r<=0;meta_read_pending_r<=0;
     output_read_addr_r<=0;compute_complete_r<=0;rope_dma_complete_r<=0;state_r<=ST_META_CMD;
    end
    ST_META_CMD:if(dma_cmd_ready)begin artifact_index_r<=0;state_r<=ST_META_DATA;end
    ST_META_DATA:begin
     if(dma_rd_valid&&dma_rd_ready)artifact_index_r<=artifact_index_r+1'b1;
     if(dma_done)begin if(artifact_index_r!=81920)state_r<=ST_ERROR;else state_r<=ST_ROPE_CMD;end
    end
    ST_ROPE_CMD:if(dma_cmd_ready)begin artifact_index_r<=0;state_r<=ST_ROPE_DATA;end
    ST_ROPE_DATA:begin
     if(dma_rd_valid&&dma_rd_ready)begin rope_buffer_r<=dma_rd_data;rope_buffer_valid_r<=1;rope_subindex_r<=0;artifact_index_r<=artifact_index_r+1'b1;end
     if(rope_wr_valid&&rope_wr_ready)begin
      rope_record_addr_r<=rope_record_addr_r+1'b1;
      if(rope_record[63:36]!=0)state_r<=ST_ERROR;
      if(rope_subindex_r==3)begin rope_subindex_r<=0;rope_buffer_valid_r<=0;end else rope_subindex_r<=rope_subindex_r+1'b1;
     end
     if(dma_done)rope_dma_complete_r<=1;
     if((rope_dma_complete_r||dma_done)&&!rope_buffer_valid_r&&!(dma_rd_valid&&dma_rd_ready))begin
      if(artifact_index_r!=256||rope_record_addr_r!=0)state_r<=ST_ERROR;else state_r<=ST_INPUT_CMD;
     end
    end
    ST_INPUT_CMD:if(dma_cmd_ready)begin artifact_index_r<=0;state_r<=ST_INPUT_DATA;end
    ST_INPUT_DATA:begin
     if(dma_rd_valid&&dma_rd_ready)artifact_index_r<=artifact_index_r+1'b1;
     if(dma_done)begin if(artifact_index_r!=6144)state_r<=ST_ERROR;else state_r<=ST_LAUNCH;end
    end
    ST_LAUNCH:if(weight_command_ready)state_r<=ST_RUN;
    ST_RUN:begin
     if(compute_done)compute_complete_r<=1;
     if((compute_complete_r||compute_done)&&output_image_ready&&!weight_frontend_busy&&!dma_busy)state_r<=ST_OUTPUT_CMD;
    end
    ST_OUTPUT_CMD:if(dma_cmd_ready)state_r<=ST_OUTPUT_DATA;
    ST_OUTPUT_DATA:if(dma_done)begin state_r<=ST_IDLE;done<=1;end
    ST_ERROR:begin end
    default:state_r<=ST_ERROR;
   endcase
   if(state_r!=ST_IDLE&&state_r!=ST_CLEAR&&error)state_r<=ST_ERROR;
  end
 end
endmodule
