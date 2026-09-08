`timescale 1ns / 1ps

module hap_a8w8_array_16x16_s42 #(
    parameter integer ROWS = 16,
    parameter integer ACTIVE_ROWS = 8,
    parameter integer COLS = 16,
    parameter integer GROUP_SIZE = 32,
    parameter integer TAG_DEPTH = 32
) (
    input  wire                              clk,
    input  wire                              rst_n,
    input  wire                              clear,
    input  wire                              in_valid,
    output wire                              in_ready,
    input  wire                              in_first_group,
    input  wire                              in_last_group,
    input  wire [ACTIVE_ROWS*4*GROUP_SIZE*8-1:0]
                                                region_act_u8,
    input  wire [ACTIVE_ROWS*COLS*8-1:0]     lane_act_zero_point,
    input  wire [ROWS*8-1:0]                 row_act_scale_code,
    input  wire [ROWS*6-1:0]                 row_act_scale_shift,
    input  wire [COLS*GROUP_SIZE*8-1:0]      col_wgt_s8,
    input  wire [COLS*8-1:0]                 col_wgt_scale_code,
    input  wire [COLS*6-1:0]                 col_wgt_scale_shift,
    output wire                              out_valid,
    input  wire                              out_ready,
    output wire [ROWS*COLS*24-1:0]           out_s24,
    output reg  [31:0]                       accepted_group_count,
    output wire [31:0]                       accumulated_group_count,
    output wire [31:0]                       output_tile_count,
    output wire [31:0]                       saturation_count,
    output wire                              error
);

    localparam integer LANES = ACTIVE_ROWS * COLS;
    localparam integer TAG_PTR_W = $clog2(TAG_DEPTH);
    localparam integer TAG_COUNT_W = $clog2(TAG_DEPTH + 1);

    wire [LANES-1:0] lane_in_ready;
    wire [LANES-1:0] lane_out_valid;
    wire [LANES-1:0] lane_error;
    wire signed [LANES*42-1:0] lane_out_guard_s42;
    wire owner_in_ready = lane_in_ready[0];
    wire owner_out_valid = lane_out_valid[0];

    reg tag_first_mem [0:TAG_DEPTH-1];
    reg tag_last_mem [0:TAG_DEPTH-1];
    reg [TAG_PTR_W-1:0] tag_wr_ptr_r;
    reg [TAG_PTR_W-1:0] tag_rd_ptr_r;
    reg [TAG_COUNT_W-1:0] tag_count_r;
    reg tile_inflight_r;
    reg last_group_accepted_r;
    reg control_error_r;

    // Full elastic boundary between the projection group registers and the
    // 128 lane engines.  The previous array input_fire combined group-tag
    // decode, sequence legality, global ready and lane state before driving
    // DSP CEs across an SLR.  Capture all payload and tags first so the lane
    // launch is driven only by this local valid register.  A lane consumes a
    // group every two clocks, therefore this one-entry stage preserves II=2.
    // Keep one valid source per lane so this timing boundary does not create
    // a new 128-sink cross-SLR launch net.  All bits transition together and
    // lane 0 remains the protocol owner, matching the existing lockstep
    // ready/valid contract.
    (* DONT_TOUCH = "yes" *) reg [LANES-1:0] input_stage_valid_r;
    reg input_stage_first_r;
    reg input_stage_last_r;
    (* DONT_TOUCH = "yes" *) reg [ACTIVE_ROWS*4*GROUP_SIZE*8-1:0]
        input_stage_act_u8_r;
    (* DONT_TOUCH = "yes" *) reg [ACTIVE_ROWS*COLS*8-1:0]
        input_stage_act_zero_point_r;
    (* DONT_TOUCH = "yes" *) reg [ROWS*8-1:0]
        input_stage_act_scale_code_r;
    (* DONT_TOUCH = "yes" *) reg [ROWS*6-1:0]
        input_stage_act_scale_shift_r;
    (* DONT_TOUCH = "yes" *) reg [COLS*GROUP_SIZE*8-1:0]
        input_stage_wgt_s8_r;
    (* DONT_TOUCH = "yes" *) reg [COLS*8-1:0]
        input_stage_wgt_scale_code_r;
    (* DONT_TOUCH = "yes" *) reg [COLS*6-1:0]
        input_stage_wgt_scale_shift_r;

    wire accum_in_ready;
    wire accum_error;
    wire [LANES*24-1:0] active_out_s24;
    wire input_sequence_legal = in_first_group ? !tile_inflight_r :
        (tile_inflight_r && !last_group_accepted_r);
    wire input_capacity = !input_stage_valid_r[0] &&
        (tag_count_r < TAG_DEPTH) && !last_group_accepted_r;
    wire input_fire = in_valid && in_ready;
    // Run 0138 measured 11,183 placed loads on input_fire and promoted it to
    // a data BUFG.  Keep input_fire as the architectural acceptance event,
    // but place combinational identity boundaries in front of each existing
    // payload bank.  No valid FF or cycle is added.  The act regions and
    // weight columns are already the natural 256-bit physical granularity.
    localparam integer INPUT_ACT_BASE = 0;
    localparam integer INPUT_WEIGHT_BASE = 32;
    localparam integer INPUT_ACT_ZERO_BASE = 48;
    localparam integer INPUT_ACT_SCALE_CODE_BASE = 56;
    localparam integer INPUT_ACT_SCALE_SHIFT_BASE = 64;
    localparam integer INPUT_WEIGHT_SCALE_CODE = 72;
    localparam integer INPUT_WEIGHT_SCALE_SHIFT = 73;
    localparam integer INPUT_FIRST_TAG = 74;
    localparam integer INPUT_LAST_TAG = 75;
    wire [75:0] input_fire_local;
    genvar input_capture_control;
    generate
        for (input_capture_control = 0; input_capture_control < 76;
             input_capture_control = input_capture_control + 1) begin : g_input_capture_control
            (* DONT_TOUCH = "yes" *)
            LUT1 #(.INIT(2'b10)) u_capture_buffer (
                .I0(input_fire),
                .O(input_fire_local[input_capture_control])
            );
        end
    endgenerate
    wire input_stage_fire = input_stage_valid_r[0] && owner_in_ready;
    reg group_stage_valid_r;
    reg group_stage_first_r;
    reg group_stage_last_r;
    wire group_stage_fire = group_stage_valid_r && accum_in_ready;
    // Capture only the high-fanout first/last tag.  Keep the corresponding
    // guard at the head of each lane FIFO until the accumulator consumes it
    // one cycle later.  This avoids both the tag-to-accumulator setup path and
    // a 5376-bit distributed-RAM-to-FF intra-site hold path.
    wire group_stage_capture = owner_out_valid && (tag_count_r != 0) &&
        !group_stage_valid_r;
    wire tag_head_first = tag_first_mem[tag_rd_ptr_r];
    wire tag_head_last = tag_last_mem[tag_rd_ptr_r];
    wire out_fire = out_valid && out_ready;

    assign in_ready = rst_n && !clear && !control_error_r &&
        input_capacity && input_sequence_legal;
    assign error = control_error_r | (|lane_error) | accum_error;

    genvar row;
    genvar col;
    generate
        for (row = 0; row < ACTIVE_ROWS; row = row + 1) begin : g_row
            for (col = 0; col < COLS; col = col + 1) begin : g_col
                localparam integer LANE = row * COLS + col;
                wire [31:0] unused_lane_input_count;
                wire [31:0] unused_lane_output_count;

                hap_a8w8_group32_lane_s42 u_lane (
                    .clk(clk), .rst_n(rst_n), .clear(clear),
                    // Each lane qualifies the replicated stage valid with its
                    // own local ready.  input_stage_fire uses lane 0 only to
                    // retire the shared stage after the lockstep acceptance;
                    // it is deliberately not fanned back across all SLRs.
                    .in_valid(input_stage_valid_r[LANE]),
                    .in_ready(lane_in_ready[LANE]),
                    .in_act_u8(input_stage_act_u8_r[
                        (row*4+(col/4))*GROUP_SIZE*8 +: GROUP_SIZE*8]),
                    .in_wgt_s8(input_stage_wgt_s8_r[
                        col*GROUP_SIZE*8 +: GROUP_SIZE*8]),
                    .in_act_zero_point(input_stage_act_zero_point_r[
                        (row*COLS+col)*8 +: 8]),
                    .in_act_scale_code(input_stage_act_scale_code_r[
                        row*8 +: 8]),
                    .in_act_scale_shift(input_stage_act_scale_shift_r[
                        row*6 +: 6]),
                    .in_wgt_scale_code(input_stage_wgt_scale_code_r[
                        col*8 +: 8]),
                    .in_wgt_scale_shift(input_stage_wgt_scale_shift_r[
                        col*6 +: 6]),
                    .out_valid(lane_out_valid[LANE]),
                    .out_ready(group_stage_fire),
                    .out_guard_s42(lane_out_guard_s42[
                        LANE*42 +: 42]),
                    .input_group_count(unused_lane_input_count),
                    .output_group_count(unused_lane_output_count),
                    .error(lane_error[LANE])
                );
            end
        end
    endgenerate

    hap_linear_tile_accum_s42 #(
        .LANES(LANES)
    ) u_accumulator (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(group_stage_valid_r), .in_ready(accum_in_ready),
        .in_first_group(group_stage_first_r),
        .in_last_group(group_stage_last_r),
        .in_guard_s42(lane_out_guard_s42),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_s24(active_out_s24),
        .input_group_count(accumulated_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(accum_error)
    );

    genvar map_row;
    genvar map_col;
    generate
        for (map_row = 0; map_row < ROWS; map_row = map_row + 1) begin : g_map_row
            for (map_col = 0; map_col < COLS;
                 map_col = map_col + 1) begin : g_map_col
                if (map_row < ACTIVE_ROWS) begin : g_active
                    assign out_s24[(map_row*COLS+map_col)*24 +: 24] =
                        active_out_s24[(map_row*COLS+map_col)*24 +: 24];
                end else begin : g_inactive
                    assign out_s24[(map_row*COLS+map_col)*24 +: 24] = 24'd0;
                end
            end
        end
    endgenerate

    integer input_capture_bank;
    always @(posedge clk) begin
        if (input_fire_local[INPUT_FIRST_TAG])
            input_stage_first_r <= in_first_group;
        if (input_fire_local[INPUT_LAST_TAG])
            input_stage_last_r <= in_last_group;
        for (input_capture_bank = 0; input_capture_bank < 32;
             input_capture_bank = input_capture_bank + 1)
            if (input_fire_local[INPUT_ACT_BASE + input_capture_bank])
                input_stage_act_u8_r[input_capture_bank*256 +: 256] <=
                    region_act_u8[input_capture_bank*256 +: 256];
        for (input_capture_bank = 0; input_capture_bank < 16;
             input_capture_bank = input_capture_bank + 1)
            if (input_fire_local[INPUT_WEIGHT_BASE + input_capture_bank])
                input_stage_wgt_s8_r[input_capture_bank*256 +: 256] <=
                    col_wgt_s8[input_capture_bank*256 +: 256];
        for (input_capture_bank = 0; input_capture_bank < 8;
             input_capture_bank = input_capture_bank + 1) begin
            if (input_fire_local[INPUT_ACT_ZERO_BASE + input_capture_bank])
                input_stage_act_zero_point_r[
                    input_capture_bank*16*8 +: 16*8] <=
                    lane_act_zero_point[
                        input_capture_bank*16*8 +: 16*8];
            if (input_fire_local[INPUT_ACT_SCALE_CODE_BASE +
                input_capture_bank])
                input_stage_act_scale_code_r[
                    input_capture_bank*16 +: 16] <=
                    row_act_scale_code[input_capture_bank*16 +: 16];
            if (input_fire_local[INPUT_ACT_SCALE_SHIFT_BASE +
                input_capture_bank])
                input_stage_act_scale_shift_r[
                    input_capture_bank*12 +: 12] <=
                    row_act_scale_shift[input_capture_bank*12 +: 12];
        end
        if (input_fire_local[INPUT_WEIGHT_SCALE_CODE])
            input_stage_wgt_scale_code_r <= col_wgt_scale_code;
        if (input_fire_local[INPUT_WEIGHT_SCALE_SHIFT])
            input_stage_wgt_scale_shift_r <= col_wgt_scale_shift;
        if (input_stage_fire) begin
            tag_first_mem[tag_wr_ptr_r] <= input_stage_first_r;
            tag_last_mem[tag_wr_ptr_r] <= input_stage_last_r;
        end
        if (group_stage_capture) begin
            group_stage_first_r <= tag_head_first;
            group_stage_last_r <= tag_head_last;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
            group_stage_valid_r <= 1'b0;
            input_stage_valid_r <= '0;
            tile_inflight_r <= 1'b0;
            last_group_accepted_r <= 1'b0;
            accepted_group_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            tag_wr_ptr_r <= '0;
            tag_rd_ptr_r <= '0;
            tag_count_r <= '0;
            group_stage_valid_r <= 1'b0;
            input_stage_valid_r <= '0;
            tile_inflight_r <= 1'b0;
            last_group_accepted_r <= 1'b0;
            accepted_group_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (input_fire) begin
                input_stage_valid_r <= {LANES{1'b1}};
                if (in_first_group)
                    tile_inflight_r <= 1'b1;
                if (in_last_group)
                    last_group_accepted_r <= 1'b1;
            end
            if (input_stage_fire) begin
                input_stage_valid_r <= '0;
                tag_wr_ptr_r <= tag_wr_ptr_r + 1'b1;
                accepted_group_count <= accepted_group_count + 32'd1;
            end
            if (group_stage_fire)
                tag_rd_ptr_r <= tag_rd_ptr_r + 1'b1;
            case ({input_stage_fire, group_stage_fire})
                2'b10: tag_count_r <= tag_count_r + 1'b1;
                2'b01: tag_count_r <= tag_count_r - 1'b1;
                default: tag_count_r <= tag_count_r;
            endcase

            if (group_stage_capture)
                group_stage_valid_r <= 1'b1;
            else if (group_stage_fire)
                group_stage_valid_r <= 1'b0;

            if (out_fire) begin
                tile_inflight_r <= 1'b0;
                last_group_accepted_r <= 1'b0;
            end

            if ((lane_in_ready != {LANES{owner_in_ready}}) ||
                (lane_out_valid != {LANES{owner_out_valid}}) ||
                (tag_count_r > TAG_DEPTH) ||
                (input_fire && !input_sequence_legal) ||
                (group_stage_capture && (tag_count_r == 0)) ||
                (group_stage_fire && !owner_out_valid) ||
                (input_stage_fire &&
                    (lane_in_ready != {LANES{owner_in_ready}})))
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if (ROWS != 16 || ACTIVE_ROWS != 8 || COLS != 16 || GROUP_SIZE != 32 ||
            TAG_DEPTH != 32)
            $error("hap_a8w8_array_16x16_s42 production parameters are fixed");
    end

endmodule
