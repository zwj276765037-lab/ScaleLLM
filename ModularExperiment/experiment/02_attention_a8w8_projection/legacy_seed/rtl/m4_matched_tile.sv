`timescale 1ns / 1ps

module m4_matched_tile #(
    parameter integer CASE_ID = 0
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [8*32*8-1:0]     in_act_u8,
    input  wire [16*32*8-1:0]    in_wgt_s8,
    input  wire [8*8-1:0]        in_zp_rows,
    input  wire [(8+16)*16-1:0]  in_meta16,
    input  wire [(8+16)*32-1:0]  in_meta32,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [8*16*24-1:0]    out_s24,
    output reg  [31:0]           accepted_group_count,
    output wire [31:0]           accumulated_group_count,
    output wire [31:0]           output_tile_count,
    output wire [31:0]           saturation_count,
    output wire                  error
);
    localparam integer ROWS = 8;
    localparam integer COLS = 16;
    localparam integer LANES = ROWS*COLS;

    wire [LANES-1:0] lane_in_ready;
    wire [LANES-1:0] lane_out_valid;
    wire [LANES-1:0] lane_error;
    wire signed [LANES*42-1:0] lane_guard_s42;
    wire owner_in_ready = lane_in_ready[0];
    wire owner_out_valid = lane_out_valid[0];
    wire accum_in_ready;
    wire accum_error;
    wire in_fire = in_valid && in_ready;
    wire group_fire = owner_out_valid && accum_in_ready;

    assign in_ready = rst_n && !clear && owner_in_ready &&
        (accepted_group_count < 128);
    assign error = (|lane_error) | accum_error |
        (lane_in_ready != {LANES{owner_in_ready}}) |
        (lane_out_valid != {LANES{owner_out_valid}});

    genvar row, col;
    generate
        for (row=0; row<ROWS; row=row+1) begin : g_row
            for (col=0; col<COLS; col=col+1) begin : g_col
                localparam integer LANE = row*COLS+col;
                wire [31:0] lane_input_count_unused;
                wire [31:0] lane_output_count_unused;
                if (CASE_ID == 0) begin : g_mac
                    m3_mac_only_lane u_lane (
                        .clk(clk),.rst_n(rst_n),.clear(clear),
                        .in_valid(in_valid && in_ready),.in_ready(lane_in_ready[LANE]),
                        .in_act_u8(in_act_u8[row*32*8 +: 32*8]),
                        .in_wgt_s8(in_wgt_s8[col*32*8 +: 32*8]),
                        .in_act_zero_point(in_zp_rows[row*8 +: 8]),
                        .out_valid(lane_out_valid[LANE]),.out_ready(group_fire),
                        .out_guard_s42(lane_guard_s42[LANE*42 +: 42]),
                        .input_group_count(lane_input_count_unused),
                        .output_group_count(lane_output_count_unused),
                        .error(lane_error[LANE]));
                end else if (CASE_ID == 1) begin : g_scalecode
                    hap_a8w8_group32_lane_s42 u_lane (
                        .clk(clk),.rst_n(rst_n),.clear(clear),
                        .in_valid(in_valid && in_ready),.in_ready(lane_in_ready[LANE]),
                        .in_act_u8(in_act_u8[row*32*8 +: 32*8]),
                        .in_wgt_s8(in_wgt_s8[col*32*8 +: 32*8]),
                        .in_act_zero_point(in_zp_rows[row*8 +: 8]),
                        .in_act_scale_code(in_meta16[row*16 +: 8]),
                        .in_act_scale_shift(in_meta16[row*16+8 +: 6]),
                        .in_wgt_scale_code(in_meta16[(ROWS+col)*16 +: 8]),
                        .in_wgt_scale_shift(in_meta16[(ROWS+col)*16+8 +: 6]),
                        .out_valid(lane_out_valid[LANE]),.out_ready(group_fire),
                        .out_guard_s42(lane_guard_s42[LANE*42 +: 42]),
                        .input_group_count(lane_input_count_unused),
                        .output_group_count(lane_output_count_unused),
                        .error(lane_error[LANE]));
                end else if (CASE_ID == 2) begin : g_fp16
                    m3_fp16_scale_lane u_lane (
                        .clk(clk),.rst_n(rst_n),.clear(clear),
                        .in_valid(in_valid && in_ready),.in_ready(lane_in_ready[LANE]),
                        .in_act_u8(in_act_u8[row*32*8 +: 32*8]),
                        .in_wgt_s8(in_wgt_s8[col*32*8 +: 32*8]),
                        .in_act_zero_point(in_zp_rows[row*8 +: 8]),
                        .in_act_scale_fp16(in_meta16[row*16 +: 16]),
                        .in_wgt_scale_fp16(in_meta16[(ROWS+col)*16 +: 16]),
                        .out_valid(lane_out_valid[LANE]),.out_ready(group_fire),
                        .out_guard_s42(lane_guard_s42[LANE*42 +: 42]),
                        .input_group_count(lane_input_count_unused),
                        .output_group_count(lane_output_count_unused),
                        .error(lane_error[LANE]));
                end else begin : g_fp32
                    m3_fp32_scale_lane u_lane (
                        .clk(clk),.rst_n(rst_n),.clear(clear),
                        .in_valid(in_valid && in_ready),.in_ready(lane_in_ready[LANE]),
                        .in_act_u8(in_act_u8[row*32*8 +: 32*8]),
                        .in_wgt_s8(in_wgt_s8[col*32*8 +: 32*8]),
                        .in_act_zero_point(in_zp_rows[row*8 +: 8]),
                        .in_act_scale_fp32(in_meta32[row*32 +: 32]),
                        .in_wgt_scale_fp32(in_meta32[(ROWS+col)*32 +: 32]),
                        .out_valid(lane_out_valid[LANE]),.out_ready(group_fire),
                        .out_guard_s42(lane_guard_s42[LANE*42 +: 42]),
                        .input_group_count(lane_input_count_unused),
                        .output_group_count(lane_output_count_unused),
                        .error(lane_error[LANE]));
                end
            end
        end
    endgenerate

    hap_linear_tile_accum_s42 #(.LANES(LANES)) u_accum (
        .clk(clk),.rst_n(rst_n),.clear(clear),
        .in_valid(owner_out_valid),.in_ready(accum_in_ready),
        .in_first_group(accumulated_group_count == 0),
        .in_last_group(accumulated_group_count == 127),
        .in_guard_s42(lane_guard_s42),
        .out_valid(out_valid),.out_ready(out_ready),.out_s24(out_s24),
        .input_group_count(accumulated_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count),.error(accum_error));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) accepted_group_count <= 0;
        else if (clear) accepted_group_count <= 0;
        else if (in_fire) accepted_group_count <= accepted_group_count + 1;
    end
endmodule

module m4_mac_only_tile(
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire [2047:0]in_act_u8,input wire[4095:0]in_wgt_s8,
    input wire[63:0]in_zp_rows,input wire[383:0]in_meta16,
    input wire[767:0]in_meta32,output wire out_valid,input wire out_ready,
    output wire[3071:0]out_s24,output wire[31:0]accepted_group_count,
    output wire[31:0]accumulated_group_count,output wire[31:0]output_tile_count,
    output wire[31:0]saturation_count,output wire error);
    m4_matched_tile #(.CASE_ID(0)) u(.*);
endmodule
module m4_scalecode_tile(
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire [2047:0]in_act_u8,input wire[4095:0]in_wgt_s8,
    input wire[63:0]in_zp_rows,input wire[383:0]in_meta16,
    input wire[767:0]in_meta32,output wire out_valid,input wire out_ready,
    output wire[3071:0]out_s24,output wire[31:0]accepted_group_count,
    output wire[31:0]accumulated_group_count,output wire[31:0]output_tile_count,
    output wire[31:0]saturation_count,output wire error);
    m4_matched_tile #(.CASE_ID(1)) u(.*);
endmodule
module m4_fp16_tile(
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire [2047:0]in_act_u8,input wire[4095:0]in_wgt_s8,
    input wire[63:0]in_zp_rows,input wire[383:0]in_meta16,
    input wire[767:0]in_meta32,output wire out_valid,input wire out_ready,
    output wire[3071:0]out_s24,output wire[31:0]accepted_group_count,
    output wire[31:0]accumulated_group_count,output wire[31:0]output_tile_count,
    output wire[31:0]saturation_count,output wire error);
    m4_matched_tile #(.CASE_ID(2)) u(.*);
endmodule
module m4_fp32_tile(
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire [2047:0]in_act_u8,input wire[4095:0]in_wgt_s8,
    input wire[63:0]in_zp_rows,input wire[383:0]in_meta16,
    input wire[767:0]in_meta32,output wire out_valid,input wire out_ready,
    output wire[3071:0]out_s24,output wire[31:0]accepted_group_count,
    output wire[31:0]accumulated_group_count,output wire[31:0]output_tile_count,
    output wire[31:0]saturation_count,output wire error);
    m4_matched_tile #(.CASE_ID(3)) u(.*);
endmodule
