`timescale 1ns/1ps

// Architecture-level replacement point for the production attention row.
// CASE_ID: 0=fixed ScaleCode, 1=FP16, 2=FP32.  Only u_qk changes; the
// Softmax, probability RAM, PV tile and row controller are common.
module m7_attention_row_arch #(
    parameter integer CASE_ID = 0
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire [7:0]            row_key_count,

    input  wire                  query_load_valid,
    output wire                  query_load_ready,
    input  wire [1:0]            query_load_group,
    input  wire [767:0]          query_group_fixed,
    input  wire [511:0]          query_group_fp16,
    input  wire [1023:0]         query_group_fp32,
    output wire                  query_ready,

    input  wire                  key_valid,
    output wire                  key_ready,
    input  wire                  key_first,
    input  wire                  key_last,
    input  wire [1:0]            key_group,
    input  wire                  key_mask,
    input  wire [383:0]          key_group_fixed,
    input  wire [15:0]           key_meta_fixed,
    input  wire [511:0]          key_group_fp16,
    input  wire [1023:0]         key_group_fp32,

    output wire                  value_phase,
    output wire [2:0]            value_tile_index,
    input  wire                  value_valid,
    output wire                  value_ready,
    input  wire [191:0]          value16_s12,
    input  wire [15:0]           value_meta16,

    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [2:0]            out_tile_index,
    output wire [383:0]          out_context16_s24,

    // Score-stream observation point.  score_fire is exactly the transfer
    // into the common production Softmax, so the TB can check each format.
    output wire                  score_fire,
    output wire signed [19:0]    score_q14_s20,
    output wire                  score_mask,
    output wire [6:0]            score_key_index,
    output wire                  score_last_key,
    output wire [31:0]           score_clip_count,
    output wire [31:0]           context_saturation_count,
    output reg  [31:0]           completed_row_count,
    output reg  [31:0]           completed_context_tile_count,
    output wire                  error
);
    localparam [2:0] ST_QUERY = 3'd0;
    localparam [2:0] ST_SCORE = 3'd1;
    localparam [2:0] ST_WAIT_PROB = 3'd2;
    localparam [2:0] ST_VALUE = 3'd3;
    localparam [2:0] ST_ERROR = 3'd4;

    reg [2:0] state_r;
    reg [2:0] value_tile_r;
    reg [6:0] value_key_r;
    reg [7:0] probability_write_count_r;
    reg [7:0] row_key_count_r;
    reg control_error_r;
    (* ram_style = "distributed" *) reg [15:0] probability_mem [0:127];

    wire qk_query_load_ready, qk_query_ready, qk_key_ready;
    wire qk_out_valid, qk_out_ready;
    wire signed [19:0] qk_out_score;
    wire qk_out_mask;
    wire [6:0] qk_out_key_index;
    wire qk_out_last_key;
    wire [31:0] qk_clip_count;
    wire qk_error;
    wire softmax_in_ready, softmax_out_valid, softmax_out_ready;
    wire [15:0] softmax_out_prob;
    wire [6:0] softmax_out_key_index;
    wire softmax_out_last_key;
    wire softmax_error;
    wire pv_in_ready, pv_out_valid;
    wire [383:0] pv_out_context;
    wire pv_error;

    wire key_fire = key_valid && key_ready;
    wire probability_fire = softmax_out_valid && softmax_out_ready;
    wire value_fire = value_valid && value_ready;
    wire output_fire = out_valid && out_ready;

    assign query_load_ready = (state_r == ST_QUERY) && qk_query_load_ready;
    assign query_ready = (state_r == ST_SCORE) && qk_query_ready;
    assign key_ready = (state_r == ST_SCORE) && qk_key_ready;
    assign qk_out_ready = softmax_in_ready;
    assign softmax_out_ready = (state_r == ST_SCORE) ||
        (state_r == ST_WAIT_PROB);
    assign value_phase = state_r == ST_VALUE;
    assign value_tile_index = value_tile_r;
    assign value_ready = (state_r == ST_VALUE) && pv_in_ready;
    assign out_valid = (state_r == ST_VALUE) && pv_out_valid;
    assign out_tile_index = value_tile_r;
    assign out_context16_s24 = pv_out_context;
    assign score_fire = qk_out_valid && qk_out_ready;
    assign score_q14_s20 = qk_out_score;
    assign score_mask = qk_out_mask;
    assign score_key_index = qk_out_key_index;
    assign score_last_key = qk_out_last_key;
    assign score_clip_count = qk_clip_count;
    assign error = control_error_r | qk_error | softmax_error | pv_error;

    generate
        if (CASE_ID == 0) begin : g_fixed
            hap_qk_score_row_128 u_qk (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid && (state_r == ST_QUERY)),
                .query_load_ready(qk_query_load_ready),
                .query_load_group(query_load_group),
                .query_load_s24(query_group_fixed),
                .query_ready(qk_query_ready),
                .in_valid(key_valid && (state_r == ST_SCORE)),
                .in_ready(qk_key_ready), .in_first_key(key_first),
                .in_last_key(key_last), .in_group(key_group),
                .in_mask(key_mask), .in_key_s12(key_group_fixed),
                .in_key_meta16(key_meta_fixed), .out_valid(qk_out_valid),
                .out_ready(qk_out_ready), .out_score_q14_s20(qk_out_score),
                .out_mask(qk_out_mask), .out_key_index(qk_out_key_index),
                .out_last_key(qk_out_last_key), .input_group_count(),
                .output_score_count(), .clip_count(qk_clip_count),
                .error(qk_error));
        end else if (CASE_ID == 1) begin : g_fp16
            m7_fp_qk_slot_arch #(.FP_W(16)) u_qk (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid && (state_r == ST_QUERY)),
                .query_load_ready(qk_query_load_ready),
                .query_load_group(query_load_group),
                .query_group_fp(query_group_fp16),
                .query_ready(qk_query_ready),
                .in_valid(key_valid && (state_r == ST_SCORE)),
                .in_ready(qk_key_ready), .in_first_key(key_first),
                .in_last_key(key_last), .in_group(key_group),
                .in_mask(key_mask), .key_group_fp(key_group_fp16),
                .out_valid(qk_out_valid), .out_ready(qk_out_ready),
                .out_score_q14_s20(qk_out_score), .out_mask(qk_out_mask),
                .out_key_index(qk_out_key_index),
                .out_last_key(qk_out_last_key), .input_group_count(),
                .output_score_count(), .clip_count(qk_clip_count),
                .error(qk_error));
        end else begin : g_fp32
            m7_fp_qk_slot_arch #(.FP_W(32)) u_qk (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .query_load_valid(query_load_valid && (state_r == ST_QUERY)),
                .query_load_ready(qk_query_load_ready),
                .query_load_group(query_load_group),
                .query_group_fp(query_group_fp32),
                .query_ready(qk_query_ready),
                .in_valid(key_valid && (state_r == ST_SCORE)),
                .in_ready(qk_key_ready), .in_first_key(key_first),
                .in_last_key(key_last), .in_group(key_group),
                .in_mask(key_mask), .key_group_fp(key_group_fp32),
                .out_valid(qk_out_valid), .out_ready(qk_out_ready),
                .out_score_q14_s20(qk_out_score), .out_mask(qk_out_mask),
                .out_key_index(qk_out_key_index),
                .out_last_key(qk_out_last_key), .input_group_count(),
                .output_score_count(), .clip_count(qk_clip_count),
                .error(qk_error));
        end
    endgenerate

    hap_softmax_row_128 u_softmax (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(qk_out_valid), .in_ready(softmax_in_ready),
        .in_first_key(qk_out_key_index == 0),
        .in_last_key(qk_out_last_key), .in_mask(qk_out_mask),
        .in_score_q14_s20(qk_out_score), .out_valid(softmax_out_valid),
        .out_ready(softmax_out_ready), .out_prob_u16(softmax_out_prob),
        .out_key_index(softmax_out_key_index),
        .out_last_key(softmax_out_last_key), .busy(), .input_score_count(),
        .output_prob_count(), .row_count(), .error(softmax_error));

    hap_pv_tile16_s43 u_pv (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(value_valid && (state_r == ST_VALUE)),
        .in_ready(pv_in_ready), .in_first_key(value_key_r == 0),
        .in_last_key(({1'b0, value_key_r} + 8'd1) == row_key_count_r),
        .in_prob_u16(probability_mem[value_key_r]),
        .in_v16_s12(value16_s12), .in_v_meta16(value_meta16),
        .out_valid(pv_out_valid), .out_ready(out_ready),
        .out_context16_s24(pv_out_context), .input_key_count(),
        .output_row_count(), .saturation_count(context_saturation_count),
        .error(pv_error));

    always @(posedge clk)
        if (probability_fire)
            probability_mem[softmax_out_key_index] <= softmax_out_prob;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_QUERY;
            value_tile_r <= 3'd0;
            value_key_r <= 7'd0;
            probability_write_count_r <= 8'd0;
            row_key_count_r <= 8'd128;
            completed_row_count <= 32'd0;
            completed_context_tile_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            state_r <= ST_QUERY;
            value_tile_r <= 3'd0;
            value_key_r <= 7'd0;
            probability_write_count_r <= 8'd0;
            row_key_count_r <= 8'd128;
            completed_row_count <= 32'd0;
            completed_context_tile_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if (query_load_valid && query_load_ready &&
                    (query_load_group == 0)) begin
                row_key_count_r <= row_key_count;
                if ((row_key_count == 0) || (row_key_count > 128))
                    control_error_r <= 1'b1;
            end
            if ((state_r == ST_QUERY) && qk_query_ready)
                state_r <= ST_SCORE;
            if (key_fire && key_last)
                state_r <= ST_WAIT_PROB;
            if (probability_fire) begin
                probability_write_count_r <= probability_write_count_r + 1'b1;
                if ((softmax_out_key_index != probability_write_count_r[6:0]) ||
                    (softmax_out_last_key !=
                     (probability_write_count_r + 8'd1 == row_key_count_r)))
                    control_error_r <= 1'b1;
                if (softmax_out_last_key) begin
                    value_tile_r <= 3'd0;
                    value_key_r <= 7'd0;
                    state_r <= ST_VALUE;
                end
            end
            if (value_fire) begin
                if ({1'b0, value_key_r} + 8'd1 == row_key_count_r)
                    value_key_r <= 7'd0;
                else
                    value_key_r <= value_key_r + 1'b1;
            end
            if (output_fire) begin
                completed_context_tile_count <=
                    completed_context_tile_count + 32'd1;
                if (value_tile_r == 3'd7) begin
                    completed_row_count <= completed_row_count + 32'd1;
                    probability_write_count_r <= 8'd0;
                    value_tile_r <= 3'd0;
                    state_r <= ST_QUERY;
                end else begin
                    value_tile_r <= value_tile_r + 1'b1;
                end
            end
            if ((key_fire && key_last && (key_group != 2'd3)) ||
                (value_fire && (value_meta16[15:14] != 0)) ||
                (value_fire && (value_meta16[7:0] == 0) &&
                 (value_meta16[13:8] != 0)) ||
                (value_fire && (value_meta16[7:0] != 0) &&
                 ((value_meta16[13:8] < 8) ||
                  (value_meta16[13:8] > 32))))
                control_error_r <= 1'b1;
            if (qk_error || softmax_error || pv_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

    initial begin
        if ((CASE_ID < 0) || (CASE_ID > 2))
            $error("m7_attention_row_arch CASE_ID must be 0, 1, or 2");
    end
endmodule
