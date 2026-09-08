`timescale 1ns / 1ps

// Gate/up command scheduler with the A8W4 projection array externalized.
// This lets gate/up and down reuse one physical dual-slice kernel while the
// scheduler retains cache walking, tile tags, SwiGLU, Hadamard and Robust A8.
module hap_mlp_gate_up_external_scheduler16_q4 #(
    parameter integer PROJECTION_TILES=1792,
    parameter integer GROUPS=128,
    parameter integer TILE_W=(PROJECTION_TILES<=2)?1:$clog2(PROJECTION_TILES),
    parameter SILU_LUT_FILE="data/mlp_silu_q16.mem"
) (
    input wire clk,input wire rst_n,input wire clear,
    input wire command_valid,output wire command_ready,
    input wire activation_bank,input wire activation_bank_ready,
    output wire cache_rd_req_valid,input wire cache_rd_req_ready,
    output wire cache_rd_req_bank,output wire [6:0] cache_rd_req_group,
    input wire cache_rd_rsp_valid,output wire cache_rd_rsp_ready,
    input wire cache_rd_rsp_bank,input wire [6:0] cache_rd_rsp_group,
    input wire [4095:0] cache_rd_rsp_u8x16x32,
    input wire [383:0] cache_rd_rsp_meta_u24x16,
    input wire weight_valid,output wire weight_ready,
    input wire signed [2047:0] weights_s4x16x32,
    input wire [223:0] weight_meta_u224,
    output wire compute_valid,input wire compute_ready,
    output wire compute_first,output wire compute_last,
    output wire signed [4607:0] compute_activation_s9x16x32,
    output wire signed [2047:0] compute_weights_s4x16x32,
    output wire [127:0] compute_activation_code_u8x16,
    output wire [95:0] compute_activation_shift_u6x16,
    output wire [127:0] compute_weight_code_u8x16,
    output wire [95:0] compute_weight_shift_u6x16,
    input wire projection_valid,output wire projection_ready,
    input wire signed [6143:0] projection_s24x16x16,
    output wire activation_out_valid,input wire activation_out_ready,
    output wire [4095:0] activation_out_u8x16x32,
    output wire [383:0] activation_out_meta_u24x16,
    output wire busy,output reg done,output reg error,
    output reg [31:0] cache_request_count,
    output reg [31:0] weight_group_count,
    output reg [31:0] projection_tile_count,
    output wire [31:0] product_group_count,
    output wire [31:0] activation_group_count
);
    reg active_r,active_bank_r;
    reg [TILE_W-1:0] request_tile_r,compute_tile_r,projection_tile_r;
    reg [6:0] request_group_r,compute_group_r;
    wire compute_fire=compute_valid&&compute_ready;
    wire request_fire=cache_rd_req_valid&&cache_rd_req_ready;
    wire output_fire=activation_out_valid&&activation_out_ready;
    wire swiglu_ready,swiglu_error;
    wire [31:0] swiglu_input_tiles;

    assign command_ready=rst_n&&!clear&&!active_r&&activation_bank_ready;
    assign busy=active_r;
    assign cache_rd_req_valid=active_r&&
        cache_request_count<PROJECTION_TILES*GROUPS;
    assign cache_rd_req_bank=active_bank_r;
    assign cache_rd_req_group=request_group_r;
    assign compute_valid=active_r&&cache_rd_rsp_valid&&weight_valid;
    assign cache_rd_rsp_ready=active_r&&weight_valid&&compute_ready;
    assign weight_ready=active_r&&cache_rd_rsp_valid&&compute_ready;
    assign compute_first=compute_group_r==0;
    assign compute_last=compute_group_r==GROUPS-1;
    assign compute_weights_s4x16x32=weights_s4x16x32;
    assign compute_weight_code_u8x16=weight_meta_u224[127:0];
    assign compute_weight_shift_u6x16=weight_meta_u224[223:128];
    assign projection_ready=swiglu_ready;

    genvar row,lane;
    generate for(row=0;row<16;row=row+1) begin:gen_row
        wire [7:0] zero=cache_rd_rsp_meta_u24x16[row*24+:8];
        assign compute_activation_code_u8x16[row*8+:8]=
            cache_rd_rsp_meta_u24x16[row*24+8+:8];
        assign compute_activation_shift_u6x16[row*6+:6]=
            cache_rd_rsp_meta_u24x16[row*24+16+:6];
        for(lane=0;lane<32;lane=lane+1) begin:gen_lane
            wire [7:0] value=cache_rd_rsp_u8x16x32[(row*32+lane)*8+:8];
            assign compute_activation_s9x16x32[(row*32+lane)*9+:9]=
                $signed({1'b0,value})-$signed({1'b0,zero});
        end
    end endgenerate

    hap_mlp_swiglu_product_frontend16_q4 #(.SILU_LUT_FILE(SILU_LUT_FILE))
    u_swiglu (
        .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(projection_valid),
        .in_ready(swiglu_ready),.in_is_up(projection_tile_r[0]),
        .in_second_half(projection_tile_r[1]),
        .projection_s24x16x16(projection_s24x16x16),
        .out_valid(activation_out_valid),.out_ready(activation_out_ready),
        .activation_u8x16x32(activation_out_u8x16x32),
        .activation_meta_u24x16(activation_out_meta_u24x16),
        .input_tile_count(swiglu_input_tiles),
        .product_group_count(product_group_count),
        .activation_group_count(activation_group_count),
        .frontend_busy_cycle_count(),.error(swiglu_error));

    always @(posedge clk) begin
      if(!rst_n||clear) begin
        active_r<=0;active_bank_r<=0;request_tile_r<='0;request_group_r<=0;
        compute_tile_r<='0;compute_group_r<=0;projection_tile_r<='0;
        done<=0;error<=0;cache_request_count<=0;weight_group_count<=0;
        projection_tile_count<=0;
      end else begin
        done<=0;
        if(command_valid&&command_ready) begin
          active_r<=1;active_bank_r<=activation_bank;request_tile_r<='0;
          request_group_r<=0;compute_tile_r<='0;compute_group_r<=0;
          projection_tile_r<='0;cache_request_count<=0;
          weight_group_count<=0;projection_tile_count<=0;
        end
        if(request_fire) begin
          cache_request_count<=cache_request_count+1;
          if(request_group_r==GROUPS-1) begin request_group_r<=0;
            if(request_tile_r!=PROJECTION_TILES-1)request_tile_r<=request_tile_r+1;
          end else request_group_r<=request_group_r+1;
        end
        if(compute_fire) begin
          weight_group_count<=weight_group_count+1;
          if(cache_rd_rsp_bank!=active_bank_r||
             cache_rd_rsp_group!=compute_group_r||
             cache_rd_rsp_meta_u24x16[383:382]!=0)error<=1;
          if(compute_group_r==GROUPS-1) begin compute_group_r<=0;
            if(compute_tile_r!=PROJECTION_TILES-1)compute_tile_r<=compute_tile_r+1;
          end else compute_group_r<=compute_group_r+1;
        end
        if(projection_valid&&projection_ready) begin
          projection_tile_count<=projection_tile_count+1;
          if(projection_tile_r!=PROJECTION_TILES-1)projection_tile_r<=projection_tile_r+1;
        end
        if(output_fire&&activation_group_count+1==PROJECTION_TILES/4) begin
          active_r<=0;done<=1;
        end
        if(swiglu_error||weight_group_count>cache_request_count||
           projection_tile_count>PROJECTION_TILES||
           swiglu_input_tiles>projection_tile_count)error<=1;
      end
    end
    initial begin
      if(GROUPS!=128)$error("gate scheduler requires 128 hidden groups");
      if(PROJECTION_TILES<=0||(PROJECTION_TILES&3)!=0)
        $error("gate tiles must be positive/multiple of four");
    end
endmodule
