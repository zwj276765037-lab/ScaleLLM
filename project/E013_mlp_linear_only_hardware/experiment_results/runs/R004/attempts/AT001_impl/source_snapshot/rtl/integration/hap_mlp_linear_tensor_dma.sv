`timescale 1ns/1ps
module hap_mlp_linear_tensor_dma # (
 parameter integer AXI_ADDR_W=32,
 parameter integer GU_OUTPUT_RECORDS=1792,DOWN_OUTPUT_RECORDS=256,
 parameter integer ENFORCE_PRODUCTION_SHAPE=1)(
 input wire clk,input wire rst_n,input wire job_clear,
 input wire load_valid,output wire load_ready,input wire [1:0] load_opcode,
 input wire [31:0] load_base,input wire [31:0] load_bytes,output reg load_done,
 input wire store_valid,output wire store_ready,input wire [1:0] store_opcode,
 input wire [31:0] store_base,input wire [31:0] store_bytes,
 output wire store_armed,output reg store_done,
 output wire cache_wr_valid,input wire cache_wr_ready,output wire [8:0] cache_wr_group,
 output wire [4095:0] cache_wr_u8x16x32,output wire [383:0] cache_wr_meta_u24x16,
 input wire gu_valid,output wire gu_ready,input wire [6143:0] gu_s24x16x16,
 input wire [9:0] gu_tile,input wire gu_matrix,input wire gu_last,
 input wire down_valid,output wire down_ready,input wire [8191:0] down_s32x16x16,
 input wire [7:0] down_tile,input wire down_last,
 output wire busy,output wire quiescent,output wire transport_quiescent,output wire axi_active,output wire flow_stall,output wire error,output wire [31:0] error_code,
 output wire [31:0] input_bytes,output reg [31:0] output_bytes,
 output reg [31:0] record_count,
    output wire                     m_axi_arvalid,
    input  wire                     m_axi_arready,
    output wire [AXI_ADDR_W-1:0]    m_axi_araddr,
    output wire [7:0]               m_axi_arlen,
    output wire [2:0]               m_axi_arsize,
    output wire [1:0]               m_axi_arburst,
    input  wire                     m_axi_rvalid,
    output wire                     m_axi_rready,
    input  wire [255:0]             m_axi_rdata,
    input  wire [1:0]               m_axi_rresp,
    input  wire                     m_axi_rlast,
    output wire                     m_axi_awvalid,
    input  wire                     m_axi_awready,
    output wire [AXI_ADDR_W-1:0]    m_axi_awaddr,
    output wire [7:0]               m_axi_awlen,
    output wire [2:0]               m_axi_awsize,
    output wire [1:0]               m_axi_awburst,
    output wire                     m_axi_wvalid,
    input  wire                     m_axi_wready,
    output wire [255:0]             m_axi_wdata,
    output wire [31:0]              m_axi_wstrb,
    output wire                     m_axi_wlast,
    input  wire                     m_axi_bvalid,
    output wire                     m_axi_bready,
    input  wire [1:0]               m_axi_bresp,

    output wire [31:0] read_beat_count,output wire [31:0] write_beat_count
);
 localparam [1:0] IDLE=0,LOAD=1,STORE=2;
 reg [1:0] state,opcode;
 reg dma_read_done,parser_finished;
 reg output_error;reg [31:0] output_error_code;
 reg write_command_pending;reg [31:0] output_address,write_commands;reg [7:0] write_burst_beats;
 wire dma_ready,dma_done,dma_error,dma_transport_quiescent;wire [31:0] dma_error_code;
 wire rd_valid,rd_ready,rd_last;wire [255:0] rd_data;
 wire parser_begin_ready,parser_done,parser_quiescent,parser_error;wire [31:0] parser_error_code;
 reg gu_buffer_valid,down_buffer_valid;
 reg [4:0] beat_index;
 reg [255:0] gu_buffer[0:23];reg [255:0] down_buffer[0:31];
 wire load_fire=load_valid&&load_ready,store_fire=store_valid&&store_ready;
 wire write_command_valid=state==STORE&&!write_command_pending&&dma_ready&&
   (opcode==1?gu_buffer_valid:down_buffer_valid)&&!output_error;
 wire write_command_fire=write_command_valid&&dma_ready;
 wire wr_valid=state==STORE&&(opcode==1?gu_buffer_valid:down_buffer_valid);
 wire wr_ready;wire [255:0] wr_data=opcode==1?gu_buffer[beat_index]:down_buffer[beat_index];
 wire [31:0] expected_records=opcode==1?GU_OUTPUT_RECORDS:DOWN_OUTPUT_RECORDS;
 wire wr_fire=wr_valid&&wr_ready;
 assign load_ready=rst_n&&!job_clear&&state==IDLE&&dma_ready&&parser_begin_ready&&!error;
 assign store_ready=rst_n&&!job_clear&&state==IDLE&&dma_ready&&parser_quiescent&&!error;
 assign store_armed=state==STORE;
 assign gu_ready=rst_n&&!job_clear&&state==STORE&&opcode==1&&!gu_buffer_valid&&record_count<GU_OUTPUT_RECORDS;
 assign down_ready=rst_n&&!job_clear&&state==STORE&&opcode==2&&!down_buffer_valid&&record_count<DOWN_OUTPUT_RECORDS;
 assign busy=state!=IDLE;
 assign flow_stall=busy&&((rd_valid&&!rd_ready)||(wr_valid&&!wr_ready)||
   (cache_wr_valid&&!cache_wr_ready)||(gu_valid&&!gu_ready)||(down_valid&&!down_ready)||
   (m_axi_arvalid&&!m_axi_arready)||(m_axi_rvalid&&!m_axi_rready)||
   (m_axi_awvalid&&!m_axi_awready)||(m_axi_wvalid&&!m_axi_wready)||
   (m_axi_bvalid&&!m_axi_bready));
 assign transport_quiescent=dma_transport_quiescent;
 assign axi_active=!dma_transport_quiescent;
 assign quiescent=state==IDLE&&dma_ready&&parser_quiescent&&!gu_buffer_valid&&!down_buffer_valid;
 assign error=dma_error||parser_error||output_error;
 assign error_code=dma_error?dma_error_code:output_error?output_error_code:parser_error_code;
 hap_mlp_linear_rec576_parser parser(
 .clk(clk),.rst_n(rst_n),.job_clear(job_clear),.begin_valid(load_fire),.begin_ready(parser_begin_ready),.begin_opcode(load_opcode),
 .in_valid(rd_valid),.in_ready(rd_ready),.in_data(rd_data),.in_last(rd_last),
 .wr_valid(cache_wr_valid),.wr_ready(cache_wr_ready),.wr_group(cache_wr_group),.wr_u8x16x32(cache_wr_u8x16x32),.wr_meta_u24x16(cache_wr_meta_u24x16),
 .done(parser_done),.quiescent(parser_quiescent),.error(parser_error),.error_code(parser_error_code),.accepted_input_bytes(input_bytes));
 hap_mlp_linear_axi256_dma dma(
 .clk(clk),.rst_n(rst_n),.clear(job_clear),.cmd_valid(load_fire||write_command_valid),.cmd_ready(dma_ready),.cmd_write(write_command_valid),
 .cmd_base_addr(write_command_valid?output_address:load_base),.cmd_beat_count(write_command_valid?(opcode==1?24:32):(load_bytes>>5)),
 .busy(),.transport_quiescent(dma_transport_quiescent),.done(dma_done),.error(dma_error),.error_code(dma_error_code),.confirmed_write_bytes(),
 .rd_valid(rd_valid),.rd_ready(rd_ready),.rd_data(rd_data),.rd_last(rd_last),.wr_valid(wr_valid),.wr_ready(wr_ready),.wr_data(wr_data),
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
 .command_count(),.read_beat_count(read_beat_count),.write_beat_count(write_beat_count),.burst_count(),.protocol_error_count());
 genvar b;
 generate for(b=0;b<24;b=b+1)begin:gen_gu_beat
 always @(posedge clk)if(gu_valid&&gu_ready)gu_buffer[b]<=gu_s24x16x16[b*256+:256];
 end
 for(b=0;b<32;b=b+1)begin:gen_down_beat
 always @(posedge clk)if(down_valid&&down_ready)down_buffer[b]<=down_s32x16x16[b*256+:256];
 end endgenerate
 always @(posedge clk)begin
 if(!rst_n||job_clear)begin
 state<=IDLE;opcode<=0;dma_read_done<=0;parser_finished<=0;output_error<=0;output_error_code<=0;
 gu_buffer_valid<=0;down_buffer_valid<=0;beat_index<=0;record_count<=0;load_done<=0;store_done<=0;
 write_command_pending<=0;write_commands<=0;output_address<=0;output_bytes<=0;write_burst_beats<=0;
 end else begin
 load_done<=0;store_done<=0;
 if(load_fire)begin state<=LOAD;opcode<=load_opcode;dma_read_done<=0;parser_finished<=0;end
 if(state==LOAD)begin
 if(dma_done)dma_read_done<=1;
 if(parser_done)parser_finished<=1;
 if((dma_read_done||dma_done)&&(parser_finished||parser_done)&&parser_quiescent)begin state<=IDLE;load_done<=1;end
 end
 if(store_fire)begin state<=STORE;opcode<=store_opcode;record_count<=0;output_address<=store_base;output_bytes<=0;write_commands<=0;end
 if(write_command_fire)begin write_command_pending<=1;write_commands<=write_commands+1;end
 if(m_axi_awvalid&&m_axi_awready)write_burst_beats<=m_axi_awlen+1'b1;
 if(m_axi_bvalid&&m_axi_bready&&m_axi_bresp==0)output_bytes<=output_bytes+write_burst_beats*32;
 if(gu_valid&&gu_ready)begin
 gu_buffer_valid<=1;record_count<=record_count+1;
 if((gu_tile!=record_count/2||gu_matrix!=record_count[0]||gu_last!=(record_count==GU_OUTPUT_RECORDS-1))&&!output_error)begin output_error<=1;output_error_code<=32'h2040;end
 end
 if(down_valid&&down_ready)begin
 down_buffer_valid<=1;record_count<=record_count+1;
 if((down_tile!=record_count||down_last!=(record_count==DOWN_OUTPUT_RECORDS-1))&&!output_error)begin output_error<=1;output_error_code<=32'h2040;end
 end
 if(wr_fire)begin
 if(beat_index==(opcode==1?23:31))begin beat_index<=0;if(opcode==1)gu_buffer_valid<=0;else down_buffer_valid<=0;end
 else beat_index<=beat_index+1'b1;
 end
 if(state==STORE&&dma_done&&write_command_pending)begin
 write_command_pending<=0;output_address<=output_address+(opcode==1?768:1024);
 if(write_commands==expected_records)begin
 state<=IDLE;store_done<=1;
 if((record_count!=expected_records||gu_buffer_valid||down_buffer_valid)&&!output_error)begin output_error<=1;output_error_code<=32'h2040;end
 end
 end
 end
 end
 initial begin
 if(ENFORCE_PRODUCTION_SHAPE&&(GU_OUTPUT_RECORDS!=1792||DOWN_OUTPUT_RECORDS!=256))$error("linear tensor DMA production shape required");
 if(GU_OUTPUT_RECORDS<=0||GU_OUTPUT_RECORDS>1792||(GU_OUTPUT_RECORDS%2)!=0||DOWN_OUTPUT_RECORDS<=0||DOWN_OUTPUT_RECORDS>256)$error("linear tensor DMA test shape invalid");
 end
endmodule
