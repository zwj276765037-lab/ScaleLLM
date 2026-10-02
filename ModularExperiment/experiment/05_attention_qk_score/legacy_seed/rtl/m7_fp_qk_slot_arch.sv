`timescale 1ns/1ps

// Floating-point replacement for the one, shared production QK slot.
//
// The external interface deliberately remains the cache's group32 ABI.  A
// group is accepted every two clocks and one physical bank of sixteen
// multipliers launches its low and high halves on consecutive clocks.  The
// four group results of a key are combined by a balanced 128-input tree, so
// independent keys remain pipelined at the production eight-clock launch
// interval.  SCORE_DEPTH reservations include keys in the arithmetic
// pipeline as well as scores waiting at the output; consequently arbitrary
// downstream backpressure cannot overwrite a score or its descriptor.
module m7_fp_qk_slot_arch #(
    parameter integer FP_W = 16
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         query_load_valid,
    output wire                         query_load_ready,
    input  wire [1:0]                   query_load_group,
    input  wire [32*FP_W-1:0]           query_group_fp,
    output wire                         query_ready,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_first_key,
    input  wire                         in_last_key,
    input  wire [1:0]                   in_group,
    input  wire                         in_mask,
    input  wire [32*FP_W-1:0]           key_group_fp,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire signed [19:0]           out_score_q14_s20,
    output wire                         out_mask,
    output wire [6:0]                   out_key_index,
    output wire                         out_last_key,
    output reg  [31:0]                  input_group_count,
    output reg  [31:0]                  output_score_count,
    output reg  [31:0]                  clip_count,
    output wire                         error
);
    localparam integer GROUP_W = 32*FP_W;
    // Four cache groups/key and a depth of 32 reserve enough complete scores
    // to cover the FP tree latency without throttling a valid 128-key row.
    localparam integer SCORE_DEPTH = 32;
    localparam integer SCORE_PTR_W = $clog2(SCORE_DEPTH);

    // The four query records are explicit registers, matching the production
    // slot and avoiding an asynchronous distributed-memory read on the lane
    // multiplier inputs.
    reg [GROUP_W-1:0] query_group0_r;
    reg [GROUP_W-1:0] query_group1_r;
    reg [GROUP_W-1:0] query_group2_r;
    reg [GROUP_W-1:0] query_group3_r;
    reg [GROUP_W-1:0] query_scaled0_r;
    reg [GROUP_W-1:0] query_scaled1_r;
    reg [GROUP_W-1:0] query_scaled2_r;
    reg [GROUP_W-1:0] query_scaled3_r;
    reg [3:0] query_loaded_r;
    reg fp16_query_ready_r;
    reg qscale_busy_r;
    reg qscale_issue_r;
    reg [2:0] qscale_issue_index_r;
    reg [2:0] qscale_result_index_r;
    reg [1:0] key_group_index_r;
    reg row_input_complete_r;
    reg control_error_r;

    reg [GROUP_W-1:0] selected_query_raw;
    reg [GROUP_W-1:0] selected_query_scaled;
    always @* begin
        case (key_group_index_r)
            2'd0: begin
                selected_query_raw = query_group0_r;
                selected_query_scaled = query_scaled0_r;
            end
            2'd1: begin
                selected_query_raw = query_group1_r;
                selected_query_scaled = query_scaled1_r;
            end
            2'd2: begin
                selected_query_raw = query_group2_r;
                selected_query_scaled = query_scaled2_r;
            end
            default: begin
                selected_query_raw = query_group3_r;
                selected_query_scaled = query_scaled3_r;
            end
        endcase
    end

    wire query_load_fire = query_load_valid && query_load_ready;
    wire [3:0] query_loaded_next = query_loaded_r |
        (4'b0001 << query_load_group);
    assign query_load_ready = rst_n && !clear &&
        !query_loaded_r[query_load_group] && !row_input_complete_r;
    assign query_ready = (FP_W == 16) ? fp16_query_ready_r :
        (&query_loaded_r);

    // Elastic group register.  A replacement group may be captured while
    // the current high half launches, preserving the cache ABI's II=2.
    reg [GROUP_W-1:0] key_group_r;
    reg key_group_valid_r;
    reg key_half_high_r;
    reg [1:0] expected_group_r;
    reg [6:0] input_key_index_r;
    reg current_key_mask_r;

    reg [5:0] reserved_score_count_r;
    wire reservation_available = (expected_group_r != 2'd0) ||
        (reserved_score_count_r < SCORE_DEPTH);
    wire input_register_ready = !key_group_valid_r || key_half_high_r;
    assign in_ready = rst_n && !clear && query_ready &&
        !row_input_complete_r && input_register_ready &&
        reservation_available && !control_error_r;
    wire input_fire = in_valid && in_ready;
    wire key_half_issue = key_group_valid_r && query_ready;

    // Descriptor FIFO is written only when group 3 is accepted.  This is
    // important because production asserts in_last_key on group 3, not on
    // group 0.  Reservation itself occurs at group 0.
    reg desc_mask_mem [0:SCORE_DEPTH-1];
    reg desc_last_mem [0:SCORE_DEPTH-1];
    reg [SCORE_PTR_W-1:0] desc_wr_ptr_r;
    reg [SCORE_PTR_W-1:0] desc_rd_ptr_r;
    reg [5:0] desc_count_r;
    wire descriptor_push = input_fire && (in_group == 2'd3);

    // One shared 16-lane multiplier bank.  In FP16 mode it first prescales
    // all eight query halves by the exactly rounded half constant 0x2da8;
    // after that, the same instances calculate Q*K products.
    wire [16*FP_W-1:0] lane_mul_a;
    wire [16*FP_W-1:0] lane_mul_b;
    wire lane_mul_issue = qscale_issue_r || key_half_issue;
    wire [15:0] lane_mul_valid;
    wire [16*FP_W-1:0] lane_mul_result;
    wire [15:0] lane_f32_valid;
    wire [511:0] lane_f32_result;
    reg lane_mode_mem [0:SCORE_DEPTH-1];
    reg [SCORE_PTR_W-1:0] lane_mode_wr_ptr_r;
    reg [SCORE_PTR_W-1:0] lane_mode_rd_ptr_r;
    reg [5:0] lane_mode_count_r;
    wire lane_mul_output_valid = lane_mul_valid[0];
    wire lane_mul_output_qscale = lane_mode_mem[lane_mode_rd_ptr_r];
    wire lane_mul_output_product = lane_mul_output_valid &&
        !lane_mul_output_qscale;

    genvar lane;
    generate
        if (FP_W == 16) begin : g_fp16_lanes
            for (lane = 0; lane < 16; lane = lane + 1) begin : g_lane
                wire [15:0] qscale_a =
                    (qscale_issue_index_r[2:1] == 2'd0) ?
                        query_group0_r[
                            (qscale_issue_index_r[0]*16+lane)*16 +: 16] :
                    (qscale_issue_index_r[2:1] == 2'd1) ?
                        query_group1_r[
                            (qscale_issue_index_r[0]*16+lane)*16 +: 16] :
                    (qscale_issue_index_r[2:1] == 2'd2) ?
                        query_group2_r[
                            (qscale_issue_index_r[0]*16+lane)*16 +: 16] :
                        query_group3_r[
                            (qscale_issue_index_r[0]*16+lane)*16 +: 16];
                assign lane_mul_a[lane*16 +: 16] = qscale_issue_r ?
                    qscale_a : selected_query_scaled[
                        (key_half_high_r*16+lane)*16 +: 16];
                assign lane_mul_b[lane*16 +: 16] = qscale_issue_r ?
                    16'h2da8 : key_group_r[
                        (key_half_high_r*16+lane)*16 +: 16];
                m7_f16_mul u_mul (
                    .aclk(clk),
                    .s_axis_a_tvalid(lane_mul_issue),
                    .s_axis_a_tdata(lane_mul_a[lane*16 +: 16]),
                    .s_axis_b_tvalid(lane_mul_issue),
                    .s_axis_b_tdata(lane_mul_b[lane*16 +: 16]),
                    .m_axis_result_tvalid(lane_mul_valid[lane]),
                    .m_axis_result_tdata(lane_mul_result[lane*16 +: 16])
                );
                // Query-scale results never overlap key products: key input
                // is held until the eighth scale result has been received.
                m7_f16_to_f32 u_product_to_f32 (
                    .aclk(clk),
                    .s_axis_a_tvalid(lane_mul_valid[lane] &&
                        lane_mul_output_product),
                    .s_axis_a_tdata(lane_mul_result[lane*16 +: 16]),
                    .m_axis_result_tvalid(lane_f32_valid[lane]),
                    .m_axis_result_tdata(lane_f32_result[lane*32 +: 32])
                );
            end
        end else begin : g_fp32_lanes
            for (lane = 0; lane < 16; lane = lane + 1) begin : g_lane
                assign lane_mul_a[lane*32 +: 32] = selected_query_raw[
                    (key_half_high_r*16+lane)*32 +: 32];
                assign lane_mul_b[lane*32 +: 32] = key_group_r[
                    (key_half_high_r*16+lane)*32 +: 32];
                m7_f32_mul u_mul (
                    .aclk(clk),
                    .s_axis_a_tvalid(key_half_issue),
                    .s_axis_a_tdata(lane_mul_a[lane*32 +: 32]),
                    .s_axis_b_tvalid(key_half_issue),
                    .s_axis_b_tdata(lane_mul_b[lane*32 +: 32]),
                    .m_axis_result_tvalid(lane_mul_valid[lane]),
                    .m_axis_result_tdata(lane_mul_result[lane*32 +: 32])
                );
                assign lane_f32_valid[lane] = lane_mul_valid[lane];
                assign lane_f32_result[lane*32 +: 32] =
                    lane_mul_result[lane*32 +: 32];
            end
        end
    endgenerate

    wire group_sum_valid;
    wire [31:0] group_sum_f32;
    wire reduce_error;
    m7_arch_reduce_group32 u_group_reduce (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .lane_valid(lane_f32_valid), .lane_f32(lane_f32_result),
        .out_valid(group_sum_valid), .out_sum_f32(group_sum_f32),
        .error(reduce_error)
    );

    // Collect four ordered group sums and launch both first-level key-tree
    // additions together on group 3.  No recurrent FP accumulator exists;
    // a new independent key may enter this balanced tree every eight clocks.
    reg [1:0] result_group_index_r;
    reg [31:0] group0_sum_r;
    reg [31:0] group1_sum_r;
    reg [31:0] group2_sum_r;
    wire key_tree_launch = group_sum_valid &&
        (result_group_index_r == 2'd3);
    wire [1:0] key_l1_valid;
    wire [63:0] key_l1_sum;
    wire key_dot_valid;
    wire [31:0] key_dot_f32;
    m7_f32_add u_key_add01 (
        .aclk(clk),
        .s_axis_a_tvalid(key_tree_launch), .s_axis_a_tdata(group0_sum_r),
        .s_axis_b_tvalid(key_tree_launch), .s_axis_b_tdata(group1_sum_r),
        .m_axis_result_tvalid(key_l1_valid[0]),
        .m_axis_result_tdata(key_l1_sum[31:0])
    );
    m7_f32_add u_key_add23 (
        .aclk(clk),
        .s_axis_a_tvalid(key_tree_launch), .s_axis_a_tdata(group2_sum_r),
        .s_axis_b_tvalid(key_tree_launch), .s_axis_b_tdata(group_sum_f32),
        .m_axis_result_tvalid(key_l1_valid[1]),
        .m_axis_result_tdata(key_l1_sum[63:32])
    );
    m7_f32_add u_key_add_final (
        .aclk(clk),
        .s_axis_a_tvalid(key_l1_valid[0]),
        .s_axis_a_tdata(key_l1_sum[31:0]),
        .s_axis_b_tvalid(key_l1_valid[1]),
        .s_axis_b_tdata(key_l1_sum[63:32]),
        .m_axis_result_tvalid(key_dot_valid),
        .m_axis_result_tdata(key_dot_f32)
    );

    // FP16 has already folded head scale into Q using the shared half bank.
    // FP32 performs the production 1/sqrt(128) operation after the dot tree.
    wire scaled_valid;
    wire [31:0] scaled_f32;
    generate
        if (FP_W == 32) begin : g_fp32_head_scale
            m7_f32_mul u_head_scale (
                .aclk(clk),
                .s_axis_a_tvalid(key_dot_valid),
                .s_axis_a_tdata(key_dot_f32),
                .s_axis_b_tvalid(key_dot_valid),
                .s_axis_b_tdata(32'h3db50800),
                .m_axis_result_tvalid(scaled_valid),
                .m_axis_result_tdata(scaled_f32)
            );
        end else begin : g_fp16_head_scale
            assign scaled_valid = key_dot_valid;
            assign scaled_f32 = key_dot_f32;
        end
    endgenerate

    // Do not inspect a truncated S20 result to decide whether clipping was
    // required.  Compare the complete IEEE-754 magnitude before conversion.
    // Values outside the production +/-16 interval are first clamped, then
    // passed to the common Float-to-fixed IP.  Thus the narrow converter can
    // never wrap before the explicit production +/-16 saturation decision.
    wire [31:0] scaled_abs_f32 = {1'b0, scaled_f32[30:0]};
    // 16 + half of one Q14 LSB is FP32 0x41800010.  At the exact tie,
    // convergent-even conversion still produces 262144, so clipping starts
    // strictly above it (the result value is identical at the tie).
    wire full_value_clips = scaled_abs_f32 > 32'h41800010;
    wire [31:0] bounded_f32 = full_value_clips ?
        (scaled_f32[31] ? 32'hc1800000 : 32'h41800000) : scaled_f32;
    wire convert_valid;
    wire [23:0] converted_s24;
    m7_f32_to_s20 u_convert_score (
        .aclk(clk),
        .s_axis_a_tvalid(scaled_valid),
        .s_axis_a_tdata(bounded_f32),
        .m_axis_result_tvalid(convert_valid),
        .m_axis_result_tdata(converted_s24)
    );

    // Conversion clip tags are latency-independent; they follow the same
    // ordered transaction stream through a small reservation-bounded FIFO.
    reg clip_tag_mem [0:SCORE_DEPTH-1];
    reg [SCORE_PTR_W-1:0] clip_tag_wr_ptr_r;
    reg [SCORE_PTR_W-1:0] clip_tag_rd_ptr_r;
    reg [5:0] clip_tag_count_r;

    reg [19:0] score_mem [0:SCORE_DEPTH-1];
    reg score_mask_mem [0:SCORE_DEPTH-1];
    reg score_last_mem [0:SCORE_DEPTH-1];
    reg [SCORE_PTR_W-1:0] score_wr_ptr_r;
    reg [SCORE_PTR_W-1:0] score_rd_ptr_r;
    reg [5:0] score_count_r;
    reg [6:0] output_key_index_r;
    wire output_fire = out_valid && out_ready;
    wire score_commit = convert_valid &&
        ((score_count_r < SCORE_DEPTH) || output_fire) &&
        (desc_count_r != 0) && (clip_tag_count_r != 0);

    assign out_valid = rst_n && !clear && (score_count_r != 0);
    assign out_score_q14_s20 = score_mem[score_rd_ptr_r];
    assign out_mask = score_mask_mem[score_rd_ptr_r];
    assign out_last_key = score_last_mem[score_rd_ptr_r];
    assign out_key_index = output_key_index_r;

    wire lane_valid_error =
        (lane_mul_valid != {16{lane_mul_valid[0]}}) ||
        (lane_f32_valid != {16{lane_f32_valid[0]}});
    assign error = control_error_r || reduce_error || lane_valid_error ||
        (key_l1_valid != {2{key_l1_valid[0]}});

    integer qlane;
    always @(posedge clk) begin
        if (query_load_fire) begin
            case (query_load_group)
                2'd0: query_group0_r <= query_group_fp;
                2'd1: query_group1_r <= query_group_fp;
                2'd2: query_group2_r <= query_group_fp;
                default: query_group3_r <= query_group_fp;
            endcase
        end
        if (input_fire) begin
            key_group_r <= key_group_fp;
        end
        if (lane_mul_issue)
            lane_mode_mem[lane_mode_wr_ptr_r] <= qscale_issue_r;
        if ((FP_W == 16) && lane_mul_output_valid &&
                lane_mul_output_qscale) begin
            for (qlane = 0; qlane < 16; qlane = qlane + 1) begin
                case (qscale_result_index_r[2:1])
                    2'd0: query_scaled0_r[
                        (qscale_result_index_r[0]*16+qlane)*16 +: 16]
                            <= lane_mul_result[qlane*16 +: 16];
                    2'd1: query_scaled1_r[
                        (qscale_result_index_r[0]*16+qlane)*16 +: 16]
                            <= lane_mul_result[qlane*16 +: 16];
                    2'd2: query_scaled2_r[
                        (qscale_result_index_r[0]*16+qlane)*16 +: 16]
                            <= lane_mul_result[qlane*16 +: 16];
                    default: query_scaled3_r[
                        (qscale_result_index_r[0]*16+qlane)*16 +: 16]
                            <= lane_mul_result[qlane*16 +: 16];
                endcase
            end
        end
        if (group_sum_valid) begin
            case (result_group_index_r)
                2'd0: group0_sum_r <= group_sum_f32;
                2'd1: group1_sum_r <= group_sum_f32;
                2'd2: group2_sum_r <= group_sum_f32;
                default: group2_sum_r <= group2_sum_r;
            endcase
        end
        if (descriptor_push) begin
            desc_mask_mem[desc_wr_ptr_r] <= current_key_mask_r;
            desc_last_mem[desc_wr_ptr_r] <= in_last_key;
        end
        if (scaled_valid)
            clip_tag_mem[clip_tag_wr_ptr_r] <= full_value_clips;
        if (score_commit) begin
            score_mem[score_wr_ptr_r] <= converted_s24[19:0];
            score_mask_mem[score_wr_ptr_r] <= desc_mask_mem[desc_rd_ptr_r];
            score_last_mem[score_wr_ptr_r] <= desc_last_mem[desc_rd_ptr_r];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            query_loaded_r <= 4'd0;
            fp16_query_ready_r <= 1'b0;
            qscale_busy_r <= 1'b0;
            qscale_issue_r <= 1'b0;
            qscale_issue_index_r <= 3'd0;
            qscale_result_index_r <= 3'd0;
            lane_mode_wr_ptr_r <= '0;
            lane_mode_rd_ptr_r <= '0;
            lane_mode_count_r <= 6'd0;
            key_group_valid_r <= 1'b0;
            key_half_high_r <= 1'b0;
            key_group_index_r <= 2'd0;
            row_input_complete_r <= 1'b0;
            expected_group_r <= 2'd0;
            input_key_index_r <= 7'd0;
            current_key_mask_r <= 1'b0;
            reserved_score_count_r <= 6'd0;
            desc_wr_ptr_r <= '0;
            desc_rd_ptr_r <= '0;
            desc_count_r <= 6'd0;
            result_group_index_r <= 2'd0;
            clip_tag_wr_ptr_r <= '0;
            clip_tag_rd_ptr_r <= '0;
            clip_tag_count_r <= 6'd0;
            score_wr_ptr_r <= '0;
            score_rd_ptr_r <= '0;
            score_count_r <= 6'd0;
            output_key_index_r <= 7'd0;
            input_group_count <= 32'd0;
            output_score_count <= 32'd0;
            clip_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            query_loaded_r <= 4'd0;
            fp16_query_ready_r <= 1'b0;
            qscale_busy_r <= 1'b0;
            qscale_issue_r <= 1'b0;
            qscale_issue_index_r <= 3'd0;
            qscale_result_index_r <= 3'd0;
            lane_mode_wr_ptr_r <= '0;
            lane_mode_rd_ptr_r <= '0;
            lane_mode_count_r <= 6'd0;
            key_group_valid_r <= 1'b0;
            key_half_high_r <= 1'b0;
            key_group_index_r <= 2'd0;
            row_input_complete_r <= 1'b0;
            expected_group_r <= 2'd0;
            input_key_index_r <= 7'd0;
            current_key_mask_r <= 1'b0;
            reserved_score_count_r <= 6'd0;
            desc_wr_ptr_r <= '0;
            desc_rd_ptr_r <= '0;
            desc_count_r <= 6'd0;
            result_group_index_r <= 2'd0;
            clip_tag_wr_ptr_r <= '0;
            clip_tag_rd_ptr_r <= '0;
            clip_tag_count_r <= 6'd0;
            score_wr_ptr_r <= '0;
            score_rd_ptr_r <= '0;
            score_count_r <= 6'd0;
            output_key_index_r <= 7'd0;
            input_group_count <= 32'd0;
            output_score_count <= 32'd0;
            clip_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (lane_mul_issue)
                lane_mode_wr_ptr_r <= lane_mode_wr_ptr_r + 1'b1;
            if (lane_mul_output_valid) begin
                lane_mode_rd_ptr_r <= lane_mode_rd_ptr_r + 1'b1;
                if (lane_mode_count_r == 0)
                    control_error_r <= 1'b1;
            end
            case ({lane_mul_issue, lane_mul_output_valid})
                2'b10: lane_mode_count_r <= lane_mode_count_r + 1'b1;
                2'b01: lane_mode_count_r <= lane_mode_count_r - 1'b1;
                default: lane_mode_count_r <= lane_mode_count_r;
            endcase
            if (query_load_fire) begin
                query_loaded_r[query_load_group] <= 1'b1;
                if ((FP_W == 16) && (query_loaded_next == 4'hf)) begin
                    qscale_busy_r <= 1'b1;
                    qscale_issue_r <= 1'b1;
                    qscale_issue_index_r <= 3'd0;
                    qscale_result_index_r <= 3'd0;
                end
            end

            if (qscale_issue_r) begin
                if (qscale_issue_index_r == 3'd7) begin
                    qscale_issue_r <= 1'b0;
                    qscale_issue_index_r <= 3'd0;
                end else begin
                    qscale_issue_index_r <= qscale_issue_index_r + 1'b1;
                end
            end
            if ((FP_W == 16) && lane_mul_output_valid &&
                    lane_mul_output_qscale) begin
                if (qscale_result_index_r == 3'd7) begin
                    qscale_result_index_r <= 3'd0;
                    qscale_busy_r <= 1'b0;
                    fp16_query_ready_r <= 1'b1;
                end else begin
                    qscale_result_index_r <= qscale_result_index_r + 1'b1;
                end
            end

            if (key_group_valid_r) begin
                if (key_half_high_r) begin
                    key_group_valid_r <= input_fire;
                    key_half_high_r <= 1'b0;
                end else begin
                    key_half_high_r <= 1'b1;
                end
            end else if (input_fire) begin
                key_group_valid_r <= 1'b1;
                key_half_high_r <= 1'b0;
            end

            if (input_fire) begin
                key_group_index_r <= in_group;
                input_group_count <= input_group_count + 32'd1;
                if (in_group != expected_group_r)
                    control_error_r <= 1'b1;
                if (in_first_key != ((input_key_index_r == 0) &&
                        (in_group == 0)))
                    control_error_r <= 1'b1;
                if (in_last_key && (in_group != 3))
                    control_error_r <= 1'b1;
                if (in_group == 0) begin
                    current_key_mask_r <= in_mask;
                    if (reserved_score_count_r == SCORE_DEPTH)
                        control_error_r <= 1'b1;
                end else if (in_mask != current_key_mask_r) begin
                    control_error_r <= 1'b1;
                end
                expected_group_r <= expected_group_r + 1'b1;
                if (in_group == 3) begin
                    desc_wr_ptr_r <= desc_wr_ptr_r + 1'b1;
                    input_key_index_r <= input_key_index_r + 1'b1;
                    if (in_last_key)
                        row_input_complete_r <= 1'b1;
                end
            end

            if (group_sum_valid)
                result_group_index_r <= result_group_index_r + 1'b1;

            if (convert_valid) begin
                if ((desc_count_r == 0) || (clip_tag_count_r == 0) ||
                        ((score_count_r == SCORE_DEPTH) && !output_fire))
                    control_error_r <= 1'b1;
                if (score_commit) begin
                    desc_rd_ptr_r <= desc_rd_ptr_r + 1'b1;
                    clip_tag_rd_ptr_r <= clip_tag_rd_ptr_r + 1'b1;
                    score_wr_ptr_r <= score_wr_ptr_r + 1'b1;
                    if (clip_tag_mem[clip_tag_rd_ptr_r])
                        clip_count <= clip_count + 32'd1;
                end
            end
            if (scaled_valid) begin
                if (clip_tag_count_r == SCORE_DEPTH)
                    control_error_r <= 1'b1;
                clip_tag_wr_ptr_r <= clip_tag_wr_ptr_r + 1'b1;
            end
            if (output_fire) begin
                score_rd_ptr_r <= score_rd_ptr_r + 1'b1;
                output_score_count <= output_score_count + 32'd1;
                if (out_last_key) begin
                    output_key_index_r <= 7'd0;
                    input_key_index_r <= 7'd0;
                    row_input_complete_r <= 1'b0;
                    query_loaded_r <= 4'd0;
                    fp16_query_ready_r <= 1'b0;
                end else begin
                    output_key_index_r <= output_key_index_r + 1'b1;
                end
            end

            case ({(input_fire && (in_group == 0)), output_fire})
                2'b10: reserved_score_count_r <=
                    reserved_score_count_r + 1'b1;
                2'b01: reserved_score_count_r <=
                    reserved_score_count_r - 1'b1;
                default: reserved_score_count_r <=
                    reserved_score_count_r;
            endcase

            case ({descriptor_push, score_commit})
                2'b10: desc_count_r <= desc_count_r + 1'b1;
                2'b01: desc_count_r <= desc_count_r - 1'b1;
                default: desc_count_r <= desc_count_r;
            endcase
            case ({scaled_valid, score_commit})
                2'b10: clip_tag_count_r <= clip_tag_count_r + 1'b1;
                2'b01: clip_tag_count_r <= clip_tag_count_r - 1'b1;
                default: clip_tag_count_r <= clip_tag_count_r;
            endcase
            case ({score_commit, output_fire})
                2'b10: score_count_r <= score_count_r + 1'b1;
                2'b01: score_count_r <= score_count_r - 1'b1;
                default: score_count_r <= score_count_r;
            endcase

            if ((reserved_score_count_r > SCORE_DEPTH) ||
                    (lane_mode_count_r > SCORE_DEPTH) ||
                    (desc_count_r > SCORE_DEPTH) ||
                    (clip_tag_count_r > SCORE_DEPTH) ||
                    (score_count_r > SCORE_DEPTH) ||
                    (score_count_r > reserved_score_count_r) ||
                    (desc_count_r > reserved_score_count_r))
                control_error_r <= 1'b1;
        end
    end

    initial begin
        if ((FP_W != 16) && (FP_W != 32))
            $error("m7_fp_qk_slot_arch FP_W must be 16 or 32");
    end
endmodule

// Balanced 16-lane reduction followed by an ordered low/high-half add.  The
// module accepts a new half every clock and emits one group32 sum every two
// clocks, with no recurrent dependency between groups or keys.
module m7_arch_reduce_group32 (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clear,
    input  wire [15:0]  lane_valid,
    input  wire [511:0] lane_f32,
    output wire         out_valid,
    output wire [31:0]  out_sum_f32,
    output wire         error
);
    wire [7:0] l1_valid;
    wire [255:0] l1_sum;
    wire [3:0] l2_valid;
    wire [127:0] l2_sum;
    wire [1:0] l3_valid;
    wire [63:0] l3_sum;
    wire half_valid;
    wire [31:0] half_sum;
    reg low_half_valid_r;
    reg [31:0] low_half_sum_r;
    wire group_launch = half_valid && low_half_valid_r;

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : g_l1
            m7_f32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(lane_valid[2*i]),
                .s_axis_a_tdata(lane_f32[(2*i)*32 +: 32]),
                .s_axis_b_tvalid(lane_valid[2*i+1]),
                .s_axis_b_tdata(lane_f32[(2*i+1)*32 +: 32]),
                .m_axis_result_tvalid(l1_valid[i]),
                .m_axis_result_tdata(l1_sum[i*32 +: 32])
            );
        end
        for (i = 0; i < 4; i = i + 1) begin : g_l2
            m7_f32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(l1_valid[2*i]),
                .s_axis_a_tdata(l1_sum[(2*i)*32 +: 32]),
                .s_axis_b_tvalid(l1_valid[2*i+1]),
                .s_axis_b_tdata(l1_sum[(2*i+1)*32 +: 32]),
                .m_axis_result_tvalid(l2_valid[i]),
                .m_axis_result_tdata(l2_sum[i*32 +: 32])
            );
        end
        for (i = 0; i < 2; i = i + 1) begin : g_l3
            m7_f32_add u_add (
                .aclk(clk),
                .s_axis_a_tvalid(l2_valid[2*i]),
                .s_axis_a_tdata(l2_sum[(2*i)*32 +: 32]),
                .s_axis_b_tvalid(l2_valid[2*i+1]),
                .s_axis_b_tdata(l2_sum[(2*i+1)*32 +: 32]),
                .m_axis_result_tvalid(l3_valid[i]),
                .m_axis_result_tdata(l3_sum[i*32 +: 32])
            );
        end
    endgenerate
    m7_f32_add u_half_final (
        .aclk(clk),
        .s_axis_a_tvalid(l3_valid[0]), .s_axis_a_tdata(l3_sum[31:0]),
        .s_axis_b_tvalid(l3_valid[1]), .s_axis_b_tdata(l3_sum[63:32]),
        .m_axis_result_tvalid(half_valid),
        .m_axis_result_tdata(half_sum)
    );
    m7_f32_add u_group_final (
        .aclk(clk),
        .s_axis_a_tvalid(group_launch), .s_axis_a_tdata(low_half_sum_r),
        .s_axis_b_tvalid(group_launch), .s_axis_b_tdata(half_sum),
        .m_axis_result_tvalid(out_valid),
        .m_axis_result_tdata(out_sum_f32)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            low_half_valid_r <= 1'b0;
            low_half_sum_r <= 32'd0;
        end else if (clear) begin
            low_half_valid_r <= 1'b0;
            low_half_sum_r <= 32'd0;
        end else if (half_valid) begin
            if (low_half_valid_r) begin
                low_half_valid_r <= 1'b0;
            end else begin
                low_half_valid_r <= 1'b1;
                low_half_sum_r <= half_sum;
            end
        end
    end

    assign error =
        (lane_valid != {16{lane_valid[0]}}) ||
        (l1_valid != {8{l1_valid[0]}}) ||
        (l2_valid != {4{l2_valid[0]}}) ||
        (l3_valid != {2{l3_valid[0]}});
endmodule
