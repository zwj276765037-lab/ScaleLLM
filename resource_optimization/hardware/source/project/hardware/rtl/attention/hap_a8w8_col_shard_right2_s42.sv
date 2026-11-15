`timescale 1ns / 1ps

module hap_a8w8_col_shard_right2_s42 #(
    parameter integer DUAL_CONTEXT = 0
) (
    input  wire clk, input wire rst_n, input wire clear,
    input  wire capture_valid, output wire capture_ready,
    input  wire [2047:0] capture_act_u8,
    input  wire [127:0] capture_act_zero_point,
    input  wire [63:0] capture_act_scale_code,
    input  wire [47:0] capture_act_scale_shift,
    input  wire [511:0] capture_wgt_s8,
    input  wire [15:0] capture_wgt_scale_code,
    input  wire [11:0] capture_wgt_scale_shift,
    output wire launch_ready, input wire launch,
    output wire guard_valid, output wire signed [671:0] guard_s42,
    output wire accum_ready, input wire guard_commit,
    input wire guard_wave, input wire guard_first, input wire guard_last,
    output wire out_valid, input wire out_ready,
    output wire out_wave,
    output wire [383:0] out_s24,
    output wire [31:0] accumulated_group_count,
    output wire [31:0] output_tile_count,
    output wire [31:0] saturation_count, output wire error
);
    hap_a8w8_col_shard_s42 #(
        .COLS(2), .ACT_REGIONS(1), .GLOBAL_COL_BASE(14),
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_shard (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(capture_valid), .capture_ready(capture_ready),
        .capture_act_u8(capture_act_u8),
        .capture_act_zero_point(capture_act_zero_point),
        .capture_act_scale_code(capture_act_scale_code),
        .capture_act_scale_shift(capture_act_scale_shift),
        .capture_wgt_s8(capture_wgt_s8),
        .capture_wgt_scale_code(capture_wgt_scale_code),
        .capture_wgt_scale_shift(capture_wgt_scale_shift),
        .launch_ready(launch_ready), .launch(launch),
        .guard_valid(guard_valid), .guard_s42(guard_s42),
        .accum_ready(accum_ready), .guard_commit(guard_commit),
        .guard_wave(guard_wave), .guard_first(guard_first),
        .guard_last(guard_last),
        .out_valid(out_valid), .out_ready(out_ready), .out_wave(out_wave),
        .out_s24(out_s24),
        .accumulated_group_count(accumulated_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );
endmodule
