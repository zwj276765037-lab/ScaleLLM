`timescale 1ns / 1ps

// A physically self-contained set of Attention projection columns.  The
// payload register, lane engines, lane FIFOs and tile accumulator are kept in
// the same hierarchy so the floorplan can move one complete column shard to
// an SLR without leaving a 42-bit-per-lane feedback path in SLR1.
module hap_a8w8_col_shard_s42 #(
    parameter integer COLS = 2,
    parameter integer ACT_REGIONS = 1,
    // Global projection-column index of local column zero.  Region selection
    // must remain global_col/4 after physical sharding; in particular the
    // center 2:13 shard spans all four activation regions.
    parameter integer GLOBAL_COL_BASE = 0,
    parameter integer ACTIVE_ROWS = 8,
    parameter integer GROUP_SIZE = 32,
    parameter integer DUAL_CONTEXT = 0
) (
    input  wire                                      clk,
    input  wire                                      rst_n,
    input  wire                                      clear,

    input  wire                                      capture_valid,
    output wire                                      capture_ready,
    input  wire [ACTIVE_ROWS*ACT_REGIONS*GROUP_SIZE*8-1:0]
                                                    capture_act_u8,
    input  wire [ACTIVE_ROWS*COLS*8-1:0]             capture_act_zero_point,
    input  wire [ACTIVE_ROWS*8-1:0]                  capture_act_scale_code,
    input  wire [ACTIVE_ROWS*6-1:0]                  capture_act_scale_shift,
    input  wire [COLS*GROUP_SIZE*8-1:0]              capture_wgt_s8,
    input  wire [COLS*8-1:0]                         capture_wgt_scale_code,
    input  wire [COLS*6-1:0]                         capture_wgt_scale_shift,

    output wire                                      launch_ready,
    input  wire                                      launch,
    output wire                                      guard_valid,
    output wire signed [ACTIVE_ROWS*COLS*42-1:0]     guard_s42,
    output wire                                      accum_ready,
    input  wire                                      guard_commit,
    input  wire                                      guard_wave,
    input  wire                                      guard_first,
    input  wire                                      guard_last,

    output wire                                      out_valid,
    input  wire                                      out_ready,
    output wire                                      out_wave,
    output wire [ACTIVE_ROWS*COLS*24-1:0]            out_s24,
    output wire [31:0]                               accumulated_group_count,
    output wire [31:0]                               output_tile_count,
    output wire [31:0]                               saturation_count,
    output wire                                      error
);

    localparam integer LANES = ACTIVE_ROWS * COLS;
    localparam integer REGION_BASE = GLOBAL_COL_BASE / 4;
    localparam integer ACT_CAPTURE_DOMAINS = ACTIVE_ROWS * ACT_REGIONS;

    reg stage_valid_r;
    (* DONT_TOUCH = "yes" *)
    reg [ACTIVE_ROWS*ACT_REGIONS*GROUP_SIZE*8-1:0] stage_act_u8_r;
    (* DONT_TOUCH = "yes" *)
    reg [ACTIVE_ROWS*COLS*8-1:0] stage_act_zero_point_r;
    (* DONT_TOUCH = "yes" *)
    reg [ACTIVE_ROWS*8-1:0] stage_act_scale_code_r;
    (* DONT_TOUCH = "yes" *)
    reg [ACTIVE_ROWS*6-1:0] stage_act_scale_shift_r;
    (* DONT_TOUCH = "yes" *)
    reg [COLS*GROUP_SIZE*8-1:0] stage_wgt_s8_r;
    (* DONT_TOUCH = "yes" *)
    reg [COLS*8-1:0] stage_wgt_scale_code_r;
    (* DONT_TOUCH = "yes" *)
    reg [COLS*6-1:0] stage_wgt_scale_shift_r;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [ACT_CAPTURE_DOMAINS-1:0] act_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [ACTIVE_ROWS-1:0] act_meta_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [COLS-1:0] wgt_capture_enable;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [LANES-1:0] lane_clear;
    (* DONT_TOUCH = "yes", KEEP = "yes" *) wire accumulator_clear;

    wire [LANES-1:0] lane_in_ready;
    wire [LANES-1:0] lane_out_valid;
    wire [LANES-1:0] lane_error;
    wire owner_in_ready = lane_in_ready[0];
    wire owner_out_valid = lane_out_valid[0];
    wire accum_error;
    reg control_error_r;

    wire capture_fire = capture_valid && capture_ready;
    assign capture_ready = rst_n && !clear && !stage_valid_r;
    assign launch_ready = stage_valid_r && owner_in_ready;
    assign guard_valid = owner_out_valid;
    assign error = control_error_r | (|lane_error) | accum_error;

    genvar capture_domain;
    generate
        for (capture_domain = 0; capture_domain < ACT_CAPTURE_DOMAINS;
             capture_domain = capture_domain + 1) begin : g_act_capture_control
            (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
            u_capture_enable (
                .I0(capture_fire),
                .O(act_capture_enable[capture_domain])
            );
        end
    endgenerate

    genvar capture_row;
    generate
        for (capture_row = 0; capture_row < ACTIVE_ROWS;
             capture_row = capture_row + 1) begin : g_meta_capture_control
            (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
            u_capture_enable (
                .I0(capture_fire),
                .O(act_meta_capture_enable[capture_row])
            );
        end
    endgenerate

    genvar capture_col;
    generate
        for (capture_col = 0; capture_col < COLS;
             capture_col = capture_col + 1) begin : g_wgt_capture_control
            (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
            u_capture_enable (
                .I0(capture_fire),
                .O(wgt_capture_enable[capture_col])
            );
        end
    endgenerate

    genvar row;
    genvar col;
    generate
        for (row = 0; row < ACTIVE_ROWS; row = row + 1) begin : g_row
            for (col = 0; col < COLS; col = col + 1) begin : g_col
                localparam integer LANE = row * COLS + col;
                localparam integer REGION = ((GLOBAL_COL_BASE + col) / 4) -
                    REGION_BASE;
                wire [31:0] unused_lane_input_count;
                wire [31:0] unused_lane_output_count;

                (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
                u_lane_clear (
                    .I0(clear),
                    .O(lane_clear[LANE])
                );

                hap_a8w8_group32_lane_s42 u_lane (
                    .clk(clk), .rst_n(rst_n), .clear(lane_clear[LANE]),
                    .in_valid(launch),
                    .in_ready(lane_in_ready[LANE]),
                    .in_act_u8(stage_act_u8_r[
                        (row*ACT_REGIONS+REGION)*GROUP_SIZE*8 +:
                        GROUP_SIZE*8]),
                    .in_wgt_s8(stage_wgt_s8_r[
                        col*GROUP_SIZE*8 +: GROUP_SIZE*8]),
                    .in_act_zero_point(stage_act_zero_point_r[
                        (row*COLS+col)*8 +: 8]),
                    .in_act_scale_code(stage_act_scale_code_r[
                        row*8 +: 8]),
                    .in_act_scale_shift(stage_act_scale_shift_r[
                        row*6 +: 6]),
                    .in_wgt_scale_code(stage_wgt_scale_code_r[
                        col*8 +: 8]),
                    .in_wgt_scale_shift(stage_wgt_scale_shift_r[
                        col*6 +: 6]),
                    .out_valid(lane_out_valid[LANE]),
                    .out_ready(guard_commit),
                    .out_guard_s42(guard_s42[LANE*42 +: 42]),
                    .input_group_count(unused_lane_input_count),
                    .output_group_count(unused_lane_output_count),
                    .error(lane_error[LANE])
                );
            end
        end
    endgenerate

    (* DONT_TOUCH = "yes", KEEP = "yes" *) LUT1 #(.INIT(2'h2))
    u_accumulator_clear (
        .I0(clear),
        .O(accumulator_clear)
    );

    generate
        if (DUAL_CONTEXT != 0) begin : g_dual_accumulator
            hap_linear_tile_accum_dual_s42 #(.LANES(LANES)) u_accumulator (
                .clk(clk), .rst_n(rst_n), .clear(accumulator_clear),
                .in_valid(guard_commit), .in_ready(accum_ready),
                .in_wave(guard_wave),
                .in_first_group(guard_first), .in_last_group(guard_last),
                .in_guard_s42(guard_s42),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_wave(out_wave), .out_s24(out_s24),
                .input_group_count(accumulated_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(saturation_count), .error(accum_error)
            );
        end else begin : g_single_accumulator
            assign out_wave = 1'b0;
            hap_linear_tile_accum_shard_s42 #(.LANES(LANES)) u_accumulator (
                .clk(clk), .rst_n(rst_n), .clear(accumulator_clear),
                .in_valid(guard_commit), .in_ready(accum_ready),
                .in_first_group(guard_first), .in_last_group(guard_last),
                .in_guard_s42(guard_s42),
                .out_valid(out_valid), .out_ready(out_ready),
                .out_s24(out_s24),
                .input_group_count(accumulated_group_count),
                .output_tile_count(output_tile_count),
                .saturation_count(saturation_count), .error(accum_error)
            );
        end
    endgenerate

    integer capture_index;
    always @(posedge clk) begin
        for (capture_index = 0; capture_index < ACT_CAPTURE_DOMAINS;
             capture_index = capture_index + 1)
            if (act_capture_enable[capture_index])
                stage_act_u8_r[capture_index*GROUP_SIZE*8 +:
                    GROUP_SIZE*8] <= capture_act_u8[
                    capture_index*GROUP_SIZE*8 +: GROUP_SIZE*8];
        for (capture_index = 0; capture_index < ACTIVE_ROWS;
             capture_index = capture_index + 1)
            if (act_meta_capture_enable[capture_index]) begin
                stage_act_zero_point_r[capture_index*COLS*8 +: COLS*8] <=
                    capture_act_zero_point[
                        capture_index*COLS*8 +: COLS*8];
                stage_act_scale_code_r[capture_index*8 +: 8] <=
                    capture_act_scale_code[capture_index*8 +: 8];
                stage_act_scale_shift_r[capture_index*6 +: 6] <=
                    capture_act_scale_shift[capture_index*6 +: 6];
            end
        for (capture_index = 0; capture_index < COLS;
             capture_index = capture_index + 1)
            if (wgt_capture_enable[capture_index]) begin
                stage_wgt_s8_r[capture_index*GROUP_SIZE*8 +: GROUP_SIZE*8] <=
                    capture_wgt_s8[
                        capture_index*GROUP_SIZE*8 +: GROUP_SIZE*8];
                stage_wgt_scale_code_r[capture_index*8 +: 8] <=
                    capture_wgt_scale_code[capture_index*8 +: 8];
                stage_wgt_scale_shift_r[capture_index*6 +: 6] <=
                    capture_wgt_scale_shift[capture_index*6 +: 6];
            end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage_valid_r <= 1'b0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            stage_valid_r <= 1'b0;
            control_error_r <= 1'b0;
        end else begin
            case ({capture_fire, launch})
                2'b10: stage_valid_r <= 1'b1;
                2'b01: stage_valid_r <= 1'b0;
                default: stage_valid_r <= stage_valid_r;
            endcase
            // capture_valid/out_ready are owner-issued lockstep events in the
            // production wrappers.  Detect a local refusal here so remote
            // ready/valid signals never need to return combinationally to the
            // cross-SLR owner solely for diagnostics.
            if ((capture_valid && !capture_ready) ||
                (launch && !launch_ready) ||
                (lane_in_ready != {LANES{owner_in_ready}}) ||
                (lane_out_valid != {LANES{owner_out_valid}}) ||
                (guard_commit && (!guard_valid || !accum_ready)) ||
                (out_ready && !out_valid))
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if (ACTIVE_ROWS != 8 || GROUP_SIZE != 32)
            $error("hap_a8w8_col_shard_s42 production row/group shape is fixed");
        if (DUAL_CONTEXT != 0 && DUAL_CONTEXT != 1)
            $error("hap_a8w8_col_shard_s42 DUAL_CONTEXT must be 0 or 1");
        if (!(((COLS == 2) && (ACT_REGIONS == 1) &&
               ((GLOBAL_COL_BASE == 0) || (GLOBAL_COL_BASE == 2) ||
                (GLOBAL_COL_BASE == 12) || (GLOBAL_COL_BASE == 14))) ||
              ((COLS == 4) && (ACT_REGIONS == 1) &&
               ((GLOBAL_COL_BASE == 4) || (GLOBAL_COL_BASE == 8))) ||
              ((COLS == 12) && (ACT_REGIONS == 4) &&
               (GLOBAL_COL_BASE == 2))))
            $error("hap_a8w8_col_shard_s42 illegal column/region shape");
    end

endmodule
