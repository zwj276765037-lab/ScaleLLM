`timescale 1ns / 1ps

// Fixed physical production variant: columns 0:1 / 2:13 / 14:15 form three
// complete SLR-local shards.  The wrapper owns the only tag FIFO and all
// cross-shard lockstep events, so no shard can accept, accumulate or retire a
// transaction independently of the others.
module hap_a8w8_array_16x16_s42_col3 #(
    parameter integer ROWS = 16,
    parameter integer ACTIVE_ROWS = 8,
    parameter integer COLS = 16,
    parameter integer GROUP_SIZE = 32,
    parameter integer TAG_DEPTH = 32,
    parameter integer DUAL_CONTEXT = 0
) (
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              clear,
    input  wire                              in_valid,
    output wire                              in_ready,
    input  wire                              in_first_group,
    input  wire                              in_last_group,
    input  wire                              in_wave,
    input  wire [ACTIVE_ROWS*4*GROUP_SIZE*8-1:0] region_act_u8,
    input  wire [ACTIVE_ROWS*COLS*8-1:0]     lane_act_zero_point,
    input  wire [ROWS*8-1:0]                 row_act_scale_code,
    input  wire [ROWS*6-1:0]                 row_act_scale_shift,
    input  wire [COLS*GROUP_SIZE*8-1:0]      col_wgt_s8,
    input  wire [COLS*8-1:0]                 col_wgt_scale_code,
    input  wire [COLS*6-1:0]                 col_wgt_scale_shift,
    output wire                              out_valid,
    input  wire                              out_ready,
    output wire                              out_wave,
    output wire [ROWS*COLS*24-1:0]           out_s24,
    output reg  [31:0]                       accepted_group_count,
    output reg  [31:0]                       accumulated_group_count,
    output reg  [31:0]                       output_tile_count,
    output wire [31:0]                       saturation_count,
    output wire                              error
);

    localparam integer TAG_PTR_W = $clog2(TAG_DEPTH);
    localparam integer TAG_COUNT_W = $clog2(TAG_DEPTH + 1);

    reg tag_first_mem [0:TAG_DEPTH-1];
    reg tag_last_mem [0:TAG_DEPTH-1];
    reg tag_wave_mem [0:TAG_DEPTH-1];
    reg [TAG_PTR_W-1:0] tag_wr_ptr_r;
    reg [TAG_PTR_W-1:0] tag_rd_ptr_r;
    reg [TAG_COUNT_W-1:0] tag_count_r;
    reg tile_inflight_r;
    reg last_group_accepted_r;
    reg expected_input_wave_r;
    reg expected_guard_wave_r;
    reg pair_first_r;
    reg pair_last_r;
    reg control_error_r;

    wire left_capture_ready;
    wire center_capture_ready;
    wire right_capture_ready;
    wire single_sequence_legal = !in_wave &&
        (in_first_group ? !tile_inflight_r :
            (tile_inflight_r && !last_group_accepted_r));
    wire dual_wave0_legal = !in_wave &&
        ((in_first_group && !tile_inflight_r) ||
         (!in_first_group && tile_inflight_r && !last_group_accepted_r));
    wire dual_wave1_legal = in_wave && tile_inflight_r &&
        !last_group_accepted_r &&
        (in_first_group == pair_first_r) &&
        (in_last_group == pair_last_r);
    wire dual_sequence_legal = (in_wave == expected_input_wave_r) &&
        (in_wave ? dual_wave1_legal : dual_wave0_legal);
    wire input_sequence_legal = (DUAL_CONTEXT != 0) ?
        dual_sequence_legal : single_sequence_legal;
    // The center shard is the lockstep owner.  Returning readiness through all
    // three SLRs created a four-crossing combinational path from clear/out_valid
    // to accumulator CE.  Owner-driven events cross each SLR once; the equality
    // local shard checks below retain fail-closed lockstep diagnostics.
    wire input_capacity = center_capture_ready &&
        (tag_count_r < TAG_DEPTH) && !last_group_accepted_r;
    wire input_fire = in_valid && in_ready;

    wire left_launch_ready;
    wire center_launch_ready;
    wire right_launch_ready;
    wire launch = center_launch_ready;

    wire left_guard_valid;
    wire center_guard_valid;
    wire right_guard_valid;
    wire left_accum_ready;
    wire center_accum_ready;
    wire right_accum_ready;
    wire guard_sequence_legal = (DUAL_CONTEXT == 0) ?
        !tag_wave_mem[tag_rd_ptr_r] :
        (tag_wave_mem[tag_rd_ptr_r] == expected_guard_wave_r);
    wire guard_commit = center_guard_valid && (tag_count_r != 0) &&
        center_accum_ready && guard_sequence_legal;
    wire tag_head_first = tag_first_mem[tag_rd_ptr_r];
    wire tag_head_last = tag_last_mem[tag_rd_ptr_r];
    wire tag_head_wave = tag_wave_mem[tag_rd_ptr_r];

    wire left_out_valid;
    wire center_out_valid;
    wire right_out_valid;
    wire left_out_wave;
    wire center_out_wave;
    wire right_out_wave;
    wire shard_out_ready = out_ready && center_out_valid;
    wire out_fire = out_valid && out_ready;

    wire signed [671:0] left_guard_s42;
    wire signed [4031:0] center_guard_s42;
    wire signed [671:0] right_guard_s42;
    wire [383:0] left_out_s24;
    wire [2303:0] center_out_s24;
    wire [383:0] right_out_s24;
    wire [31:0] left_accumulated_count;
    wire [31:0] center_accumulated_count;
    wire [31:0] right_accumulated_count;
    wire [31:0] left_output_count;
    wire [31:0] center_output_count;
    wire [31:0] right_output_count;
    wire [31:0] left_saturation_count;
    wire [31:0] center_saturation_count;
    wire [31:0] right_saturation_count;
    wire left_error;
    wire center_error;
    wire right_error;

    wire [2047:0] left_capture_act_u8;
    wire [8191:0] center_capture_act_u8;
    wire [2047:0] right_capture_act_u8;
    wire [127:0] left_capture_zero;
    wire [767:0] center_capture_zero;
    wire [127:0] right_capture_zero;

    genvar map_row;
    genvar map_col;
    generate
        for (map_row = 0; map_row < ACTIVE_ROWS;
             map_row = map_row + 1) begin : g_input_row
            assign left_capture_act_u8[map_row*256 +: 256] =
                region_act_u8[(map_row*4+0)*256 +: 256];
            assign center_capture_act_u8[(map_row*4+0)*256 +: 256] =
                region_act_u8[(map_row*4+0)*256 +: 256];
            assign center_capture_act_u8[(map_row*4+1)*256 +: 256] =
                region_act_u8[(map_row*4+1)*256 +: 256];
            assign center_capture_act_u8[(map_row*4+2)*256 +: 256] =
                region_act_u8[(map_row*4+2)*256 +: 256];
            assign center_capture_act_u8[(map_row*4+3)*256 +: 256] =
                region_act_u8[(map_row*4+3)*256 +: 256];
            assign right_capture_act_u8[map_row*256 +: 256] =
                region_act_u8[(map_row*4+3)*256 +: 256];
            for (map_col = 0; map_col < 2; map_col = map_col + 1)
                assign left_capture_zero[(map_row*2+map_col)*8 +: 8] =
                    lane_act_zero_point[(map_row*16+map_col)*8 +: 8];
            for (map_col = 0; map_col < 12; map_col = map_col + 1)
                assign center_capture_zero[(map_row*12+map_col)*8 +: 8] =
                    lane_act_zero_point[(map_row*16+map_col+2)*8 +: 8];
            for (map_col = 0; map_col < 2; map_col = map_col + 1)
                assign right_capture_zero[(map_row*2+map_col)*8 +: 8] =
                    lane_act_zero_point[(map_row*16+map_col+14)*8 +: 8];
        end
    endgenerate

    hap_a8w8_col_shard_left2_s42 #(
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_left2 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(input_fire), .capture_ready(left_capture_ready),
        .capture_act_u8(left_capture_act_u8),
        .capture_act_zero_point(left_capture_zero),
        .capture_act_scale_code(row_act_scale_code[63:0]),
        .capture_act_scale_shift(row_act_scale_shift[47:0]),
        .capture_wgt_s8(col_wgt_s8[0 +: 512]),
        .capture_wgt_scale_code(col_wgt_scale_code[0 +: 16]),
        .capture_wgt_scale_shift(col_wgt_scale_shift[0 +: 12]),
        .launch_ready(left_launch_ready), .launch(launch),
        .guard_valid(left_guard_valid), .guard_s42(left_guard_s42),
        .accum_ready(left_accum_ready), .guard_commit(guard_commit),
        .guard_wave(tag_head_wave), .guard_first(tag_head_first),
        .guard_last(tag_head_last),
        .out_valid(left_out_valid), .out_ready(shard_out_ready),
        .out_wave(left_out_wave), .out_s24(left_out_s24),
        .accumulated_group_count(left_accumulated_count),
        .output_tile_count(left_output_count),
        .saturation_count(left_saturation_count), .error(left_error)
    );

    hap_a8w8_col_shard_center12_s42 #(
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_center12 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(input_fire), .capture_ready(center_capture_ready),
        .capture_act_u8(center_capture_act_u8),
        .capture_act_zero_point(center_capture_zero),
        .capture_act_scale_code(row_act_scale_code[63:0]),
        .capture_act_scale_shift(row_act_scale_shift[47:0]),
        .capture_wgt_s8(col_wgt_s8[2*256 +: 12*256]),
        .capture_wgt_scale_code(col_wgt_scale_code[2*8 +: 12*8]),
        .capture_wgt_scale_shift(col_wgt_scale_shift[2*6 +: 12*6]),
        .launch_ready(center_launch_ready), .launch(launch),
        .guard_valid(center_guard_valid), .guard_s42(center_guard_s42),
        .accum_ready(center_accum_ready), .guard_commit(guard_commit),
        .guard_wave(tag_head_wave), .guard_first(tag_head_first),
        .guard_last(tag_head_last),
        .out_valid(center_out_valid), .out_ready(shard_out_ready),
        .out_wave(center_out_wave), .out_s24(center_out_s24),
        .accumulated_group_count(center_accumulated_count),
        .output_tile_count(center_output_count),
        .saturation_count(center_saturation_count), .error(center_error)
    );

    hap_a8w8_col_shard_right2_s42 #(
        .DUAL_CONTEXT(DUAL_CONTEXT)
    ) u_right2 (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .capture_valid(input_fire), .capture_ready(right_capture_ready),
        .capture_act_u8(right_capture_act_u8),
        .capture_act_zero_point(right_capture_zero),
        .capture_act_scale_code(row_act_scale_code[63:0]),
        .capture_act_scale_shift(row_act_scale_shift[47:0]),
        .capture_wgt_s8(col_wgt_s8[14*256 +: 512]),
        .capture_wgt_scale_code(col_wgt_scale_code[14*8 +: 16]),
        .capture_wgt_scale_shift(col_wgt_scale_shift[14*6 +: 12]),
        .launch_ready(right_launch_ready), .launch(launch),
        .guard_valid(right_guard_valid), .guard_s42(right_guard_s42),
        .accum_ready(right_accum_ready), .guard_commit(guard_commit),
        .guard_wave(tag_head_wave), .guard_first(tag_head_first),
        .guard_last(tag_head_last),
        .out_valid(right_out_valid), .out_ready(shard_out_ready),
        .out_wave(right_out_wave), .out_s24(right_out_s24),
        .accumulated_group_count(right_accumulated_count),
        .output_tile_count(right_output_count),
        .saturation_count(right_saturation_count), .error(right_error)
    );

    generate
        for (map_row = 0; map_row < ROWS; map_row = map_row + 1) begin : g_out_row
            for (map_col = 0; map_col < COLS;
                 map_col = map_col + 1) begin : g_out_col
                if (map_row < ACTIVE_ROWS && map_col < 2) begin : g_left
                    assign out_s24[(map_row*16+map_col)*24 +: 24] =
                        left_out_s24[(map_row*2+map_col)*24 +: 24];
                end else if (map_row < ACTIVE_ROWS && map_col < 14) begin : g_center
                    assign out_s24[(map_row*16+map_col)*24 +: 24] =
                        center_out_s24[(map_row*12+map_col-2)*24 +: 24];
                end else if (map_row < ACTIVE_ROWS) begin : g_right
                    assign out_s24[(map_row*16+map_col)*24 +: 24] =
                        right_out_s24[(map_row*2+map_col-14)*24 +: 24];
                end else begin : g_inactive
                    assign out_s24[(map_row*16+map_col)*24 +: 24] = 24'd0;
                end
            end
        end
    endgenerate

    assign in_ready = rst_n && !clear && !control_error_r &&
        input_capacity && input_sequence_legal;
    assign out_valid = rst_n && !clear && center_out_valid;
    assign out_wave = center_out_wave;
    // Each shard counter is already cumulative, so expose their cumulative
    // sum directly.  Adding that sum again at every tile retirement would
    // double-count all preceding tiles.
    assign saturation_count = left_saturation_count +
        center_saturation_count + right_saturation_count;
    assign error = control_error_r | left_error | center_error | right_error;

    always @(posedge clk) begin
        if (input_fire) begin
            tag_first_mem[tag_wr_ptr_r] <= in_first_group;
            tag_last_mem[tag_wr_ptr_r] <= in_last_group;
            tag_wave_mem[tag_wr_ptr_r] <= in_wave;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
            tile_inflight_r <= 1'b0;
            last_group_accepted_r <= 1'b0;
            expected_input_wave_r <= 1'b0;
            expected_guard_wave_r <= 1'b0;
            pair_first_r <= 1'b0;
            pair_last_r <= 1'b0;
            accepted_group_count <= 32'd0;
            accumulated_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
            tile_inflight_r <= 1'b0;
            last_group_accepted_r <= 1'b0;
            expected_input_wave_r <= 1'b0;
            expected_guard_wave_r <= 1'b0;
            pair_first_r <= 1'b0;
            pair_last_r <= 1'b0;
            accepted_group_count <= 32'd0;
            accumulated_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (input_fire) begin
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
                accepted_group_count <= accepted_group_count + 32'd1;
                if (DUAL_CONTEXT != 0) begin
                    expected_input_wave_r <= ~expected_input_wave_r;
                    if (!in_wave) begin
                        pair_first_r <= in_first_group;
                        pair_last_r <= in_last_group;
                    end
                end
                if (in_first_group &&
                    ((DUAL_CONTEXT == 0) || !in_wave))
                    tile_inflight_r <= 1'b1;
                if (in_last_group &&
                    ((DUAL_CONTEXT == 0) || in_wave))
                    last_group_accepted_r <= 1'b1;
            end
            if (guard_commit) begin
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
                accumulated_group_count <= accumulated_group_count + 32'd1;
                if (DUAL_CONTEXT != 0)
                    expected_guard_wave_r <= ~expected_guard_wave_r;
            end
            case ({input_fire, guard_commit})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase
            if (out_fire) begin
                output_tile_count <= output_tile_count + 32'd1;
                if ((DUAL_CONTEXT == 0) || out_wave) begin
                    tile_inflight_r <= 1'b0;
                    last_group_accepted_r <= 1'b0;
                end
            end
            // Remote shards diagnose owner events locally.  Keeping only the
            // owner/tag invariants here removes the ready/valid return network
            // that previously crossed SLR0->SLR1->SLR2->SLR1 in one cycle.
            if ((tag_count_r > TAG_DEPTH) ||
                (in_valid && input_capacity && !input_sequence_legal) ||
                (center_guard_valid && (tag_count_r != 0) &&
                    center_accum_ready && !guard_sequence_legal))
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if (ROWS != 16 || ACTIVE_ROWS != 8 || COLS != 16 ||
            GROUP_SIZE != 32 || TAG_DEPTH != 32)
            $error("hap_a8w8_array_16x16_s42_col3 production parameters are fixed");
        if (DUAL_CONTEXT != 0 && DUAL_CONTEXT != 1)
            $error("hap_a8w8_array_16x16_s42_col3 DUAL_CONTEXT must be 0 or 1");
    end

endmodule
