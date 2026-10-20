`timescale 1ns / 1ps

module hap_a8w8_col_shard_center12_s42 #(
    parameter integer DUAL_CONTEXT = 0
) (
    input  wire clk, input wire rst_n, input wire clear,
    input  wire capture_valid, output wire capture_ready,
    input  wire [8191:0] capture_act_u8,
    input  wire [767:0] capture_act_zero_point,
    input  wire [63:0] capture_act_scale_code,
    input  wire [47:0] capture_act_scale_shift,
    input  wire [3071:0] capture_wgt_s8,
    input  wire [95:0] capture_wgt_scale_code,
    input  wire [71:0] capture_wgt_scale_shift,
    output wire launch_ready, input wire launch,
    output wire guard_valid, output wire signed [4031:0] guard_s42,
    output wire accum_ready, input wire guard_commit,
    input wire guard_wave, input wire guard_first, input wire guard_last,
    output wire out_valid, input wire out_ready,
    output wire out_wave,
    output wire [2303:0] out_s24,
    output wire [31:0] accumulated_group_count,
    output wire [31:0] output_tile_count,
    output wire [31:0] saturation_count, output wire error
);
    // Preserve the external 12-column shard contract while giving each natural
    // activation region a complete local payload/lane/accumulator hierarchy.
    // The global columns are 2:3 / 4:7 / 8:11 / 12:13.
    wire [2047:0] region0_act_u8;
    wire [2047:0] region1_act_u8;
    wire [2047:0] region2_act_u8;
    wire [2047:0] region3_act_u8;
    wire [127:0] region0_zero;
    wire [255:0] region1_zero;
    wire [255:0] region2_zero;
    wire [127:0] region3_zero;

    wire region0_capture_ready, region1_capture_ready;
    wire region2_capture_ready, region3_capture_ready;
    wire region0_launch_ready, region1_launch_ready;
    wire region2_launch_ready, region3_launch_ready;
    wire region0_guard_valid, region1_guard_valid;
    wire region2_guard_valid, region3_guard_valid;
    wire region0_accum_ready, region1_accum_ready;
    wire region2_accum_ready, region3_accum_ready;
    wire region0_out_valid, region1_out_valid;
    wire region2_out_valid, region3_out_valid;
    wire region0_out_wave, region1_out_wave;
    wire region2_out_wave, region3_out_wave;
    wire signed [671:0] region0_guard;
    wire signed [1343:0] region1_guard;
    wire signed [1343:0] region2_guard;
    wire signed [671:0] region3_guard;
    wire [383:0] region0_out;
    wire [767:0] region1_out;
    wire [767:0] region2_out;
    wire [383:0] region3_out;
    wire [31:0] region0_accumulated, region1_accumulated;
    wire [31:0] region2_accumulated, region3_accumulated;
    wire [31:0] region0_output, region1_output;
    wire [31:0] region2_output, region3_output;
    wire [31:0] region0_saturation, region1_saturation;
    wire [31:0] region2_saturation, region3_saturation;
    wire region0_error, region1_error, region2_error, region3_error;
    reg owner_out_pending_r;
    reg owner_out_wave_r;
    wire owner_out_fire = owner_out_pending_r && out_ready;
    wire subshard_out_ready = owner_out_fire;
    // Region 1 is the local owner.  All four subshards are cycle-identical;
    // using one owner keeps readiness from forming a long combinational chain
    // through every region.  Each subshard latches any owner event that it
    // cannot accept, so diagnostics also remain local to their physical region.
    assign capture_ready = region1_capture_ready;
    assign launch_ready = region1_launch_ready;
    assign guard_valid = region1_guard_valid;
    assign accum_ready = region1_accum_ready;
    // Region 2 has the P16 no-bypass accumulator FIFO and retires one cycle
    // after the local owner.  Delay the owner event locally before releasing
    // all four regions; this preserves owner-only timing and group II.
    assign out_valid = owner_out_pending_r;
    assign out_wave = owner_out_wave_r;
    assign accumulated_group_count = region1_accumulated;
    assign output_tile_count = region1_output;
    assign saturation_count = region0_saturation + region1_saturation +
        region2_saturation + region3_saturation;
    assign error = region0_error | region1_error | region2_error |
        region3_error;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            owner_out_pending_r <= 1'b0;
            owner_out_wave_r <= 1'b0;
        end else if (clear) begin
            owner_out_pending_r <= 1'b0;
            owner_out_wave_r <= 1'b0;
        end else if (!owner_out_pending_r && region1_out_valid) begin
            owner_out_pending_r <= 1'b1;
            owner_out_wave_r <= region1_out_wave;
        end else if (owner_out_fire) begin
            owner_out_pending_r <= 1'b0;
        end
    end

    genvar map_row;
    generate
        for (map_row = 0; map_row < 8; map_row = map_row + 1) begin : g_map
            assign region0_act_u8[map_row*256 +: 256] =
                capture_act_u8[(map_row*4+0)*256 +: 256];
            assign region1_act_u8[map_row*256 +: 256] =
                capture_act_u8[(map_row*4+1)*256 +: 256];
            assign region2_act_u8[map_row*256 +: 256] =
                capture_act_u8[(map_row*4+2)*256 +: 256];
            assign region3_act_u8[map_row*256 +: 256] =
                capture_act_u8[(map_row*4+3)*256 +: 256];

            assign region0_zero[map_row*16 +: 16] =
                capture_act_zero_point[(map_row*12+0)*8 +: 16];
            assign region1_zero[map_row*32 +: 32] =
                capture_act_zero_point[(map_row*12+2)*8 +: 32];
            assign region2_zero[map_row*32 +: 32] =
                capture_act_zero_point[(map_row*12+6)*8 +: 32];
            assign region3_zero[map_row*16 +: 16] =
                capture_act_zero_point[(map_row*12+10)*8 +: 16];

            assign guard_s42[(map_row*12+0)*42 +: 2*42] =
                region0_guard[map_row*2*42 +: 2*42];
            assign guard_s42[(map_row*12+2)*42 +: 4*42] =
                region1_guard[map_row*4*42 +: 4*42];
            assign guard_s42[(map_row*12+6)*42 +: 4*42] =
                region2_guard[map_row*4*42 +: 4*42];
            assign guard_s42[(map_row*12+10)*42 +: 2*42] =
                region3_guard[map_row*2*42 +: 2*42];

            assign out_s24[(map_row*12+0)*24 +: 2*24] =
                region0_out[map_row*2*24 +: 2*24];
            assign out_s24[(map_row*12+2)*24 +: 4*24] =
                region1_out[map_row*4*24 +: 4*24];
            assign out_s24[(map_row*12+6)*24 +: 4*24] =
                region2_out[map_row*4*24 +: 4*24];
            assign out_s24[(map_row*12+10)*24 +: 2*24] =
                region3_out[map_row*2*24 +: 2*24];
        end
    endgenerate

    hap_a8w8_col_shard_s42 #(
        .COLS(2), .ACT_REGIONS(1), .GLOBAL_COL_BASE(2),
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_region0_cols2_3 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(capture_valid), .capture_ready(region0_capture_ready),
        .capture_act_u8(region0_act_u8),
        .capture_act_zero_point(region0_zero),
        .capture_act_scale_code(capture_act_scale_code),
        .capture_act_scale_shift(capture_act_scale_shift),
        .capture_wgt_s8(capture_wgt_s8[0 +: 512]),
        .capture_wgt_scale_code(capture_wgt_scale_code[0 +: 16]),
        .capture_wgt_scale_shift(capture_wgt_scale_shift[0 +: 12]),
        .launch_ready(region0_launch_ready), .launch(launch),
        .guard_valid(region0_guard_valid), .guard_s42(region0_guard),
        .accum_ready(region0_accum_ready), .guard_commit(guard_commit),
        .guard_wave(guard_wave), .guard_first(guard_first),
        .guard_last(guard_last),
        .out_valid(region0_out_valid), .out_ready(subshard_out_ready),
        .out_wave(region0_out_wave), .out_s24(region0_out),
        .accumulated_group_count(region0_accumulated),
        .output_tile_count(region0_output),
        .saturation_count(region0_saturation), .error(region0_error)
    );

    hap_a8w8_col_shard_s42 #(
        .COLS(4), .ACT_REGIONS(1), .GLOBAL_COL_BASE(4),
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_region1_cols4_7 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(capture_valid), .capture_ready(region1_capture_ready),
        .capture_act_u8(region1_act_u8),
        .capture_act_zero_point(region1_zero),
        .capture_act_scale_code(capture_act_scale_code),
        .capture_act_scale_shift(capture_act_scale_shift),
        .capture_wgt_s8(capture_wgt_s8[2*256 +: 4*256]),
        .capture_wgt_scale_code(capture_wgt_scale_code[2*8 +: 4*8]),
        .capture_wgt_scale_shift(capture_wgt_scale_shift[2*6 +: 4*6]),
        .launch_ready(region1_launch_ready), .launch(launch),
        .guard_valid(region1_guard_valid), .guard_s42(region1_guard),
        .accum_ready(region1_accum_ready), .guard_commit(guard_commit),
        .guard_wave(guard_wave), .guard_first(guard_first),
        .guard_last(guard_last),
        .out_valid(region1_out_valid), .out_ready(subshard_out_ready),
        .out_wave(region1_out_wave), .out_s24(region1_out),
        .accumulated_group_count(region1_accumulated),
        .output_tile_count(region1_output),
        .saturation_count(region1_saturation), .error(region1_error)
    );

    hap_a8w8_col_shard_s42 #(
        .COLS(4), .ACT_REGIONS(1), .GLOBAL_COL_BASE(8),
        .DUAL_CONTEXT(DUAL_CONTEXT),
        .SPLIT_DUAL_ACCUMULATOR(DUAL_CONTEXT != 0),
        .BUFFER_DUAL_ACCUMULATOR(DUAL_CONTEXT != 0)
    ) u_region2_cols8_11 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(capture_valid), .capture_ready(region2_capture_ready),
        .capture_act_u8(region2_act_u8),
        .capture_act_zero_point(region2_zero),
        .capture_act_scale_code(capture_act_scale_code),
        .capture_act_scale_shift(capture_act_scale_shift),
        .capture_wgt_s8(capture_wgt_s8[6*256 +: 4*256]),
        .capture_wgt_scale_code(capture_wgt_scale_code[6*8 +: 4*8]),
        .capture_wgt_scale_shift(capture_wgt_scale_shift[6*6 +: 4*6]),
        .launch_ready(region2_launch_ready), .launch(launch),
        .guard_valid(region2_guard_valid), .guard_s42(region2_guard),
        .accum_ready(region2_accum_ready), .guard_commit(guard_commit),
        .guard_wave(guard_wave), .guard_first(guard_first),
        .guard_last(guard_last),
        .out_valid(region2_out_valid), .out_ready(subshard_out_ready),
        .out_wave(region2_out_wave), .out_s24(region2_out),
        .accumulated_group_count(region2_accumulated),
        .output_tile_count(region2_output),
        .saturation_count(region2_saturation), .error(region2_error)
    );

    hap_a8w8_col_shard_s42 #(
        .COLS(2), .ACT_REGIONS(1), .GLOBAL_COL_BASE(12),
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_region3_cols12_13 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(capture_valid), .capture_ready(region3_capture_ready),
        .capture_act_u8(region3_act_u8),
        .capture_act_zero_point(region3_zero),
        .capture_act_scale_code(capture_act_scale_code),
        .capture_act_scale_shift(capture_act_scale_shift),
        .capture_wgt_s8(capture_wgt_s8[10*256 +: 2*256]),
        .capture_wgt_scale_code(capture_wgt_scale_code[10*8 +: 2*8]),
        .capture_wgt_scale_shift(capture_wgt_scale_shift[10*6 +: 2*6]),
        .launch_ready(region3_launch_ready), .launch(launch),
        .guard_valid(region3_guard_valid), .guard_s42(region3_guard),
        .accum_ready(region3_accum_ready), .guard_commit(guard_commit),
        .guard_wave(guard_wave), .guard_first(guard_first),
        .guard_last(guard_last),
        .out_valid(region3_out_valid), .out_ready(subshard_out_ready),
        .out_wave(region3_out_wave), .out_s24(region3_out),
        .accumulated_group_count(region3_accumulated),
        .output_tile_count(region3_output),
        .saturation_count(region3_saturation), .error(region3_error)
    );

endmodule
