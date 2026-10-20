`timescale 1ns / 1ps

module hap_attention_head_group16 (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  query_load_valid,
    output wire                  query_load_ready,
    input  wire [1:0]            query_load_group,
    input  wire [32*24-1:0]      query_load_s24,
    output wire                  query_ready,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_key,
    input  wire                  in_last_key,
    input  wire [1:0]            in_group,
    input  wire                  in_mask,
    input  wire [32*12-1:0]      in_key_s12,
    input  wire [15:0]           in_key_meta16,
    input  wire [16*12-1:0]      in_value16_s12,
    input  wire [15:0]           in_value_meta16,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire [16*24-1:0]      out_context16_s24,
    output wire [31:0]           score_clip_count,
    output wire [31:0]           context_saturation_count,
    output reg  [31:0]           completed_row_count,
    output wire                  error
);

    localparam [1:0] ST_QUERY = 2'd0;
    localparam [1:0] ST_SCORE = 2'd1;
    localparam [1:0] ST_ERROR = 2'd2;
    reg [1:0] state_r;
    reg control_error_r;
    (* ram_style = "distributed" *) reg [16*12-1:0] value_mem [0:127];
    (* ram_style = "distributed" *) reg [15:0] value_meta_mem [0:127];
    reg [6:0] value_write_index_r;

    wire qk_query_load_ready;
    wire qk_query_ready;
    wire qk_in_ready;
    wire qk_out_valid;
    wire qk_out_ready;
    wire signed [19:0] qk_out_score;
    wire qk_out_mask;
    wire [6:0] qk_out_key_index;
    wire qk_out_last_key;
    wire [31:0] qk_input_group_count_unused;
    wire [31:0] qk_output_score_count_unused;
    wire qk_error;
    wire softmax_in_ready;
    wire softmax_out_valid;
    wire softmax_out_ready;
    wire [15:0] softmax_out_prob;
    wire [6:0] softmax_out_key_index;
    wire softmax_out_last_key;
    wire [31:0] softmax_input_count_unused;
    wire [31:0] softmax_output_count_unused;
    wire [31:0] softmax_row_count_unused;
    wire softmax_error;
    wire pv_in_ready;
    wire [31:0] pv_input_key_count_unused;
    wire [31:0] pv_output_row_count_unused;
    wire pv_error;
    wire input_fire = in_valid && in_ready;
    wire output_fire = out_valid && out_ready;

    assign query_load_ready = (state_r == ST_QUERY) && qk_query_load_ready;
    assign query_ready = (state_r == ST_SCORE) && qk_query_ready;
    assign in_ready = (state_r == ST_SCORE) && qk_in_ready;
    assign qk_out_ready = softmax_in_ready;
    assign softmax_out_ready = pv_in_ready;
    assign error = control_error_r | qk_error | softmax_error | pv_error;

    hap_qk_score_row_128 u_qk (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .query_load_valid(query_load_valid && (state_r == ST_QUERY)),
        .query_load_ready(qk_query_load_ready),
        .query_load_group(query_load_group),
        .query_load_s24(query_load_s24), .query_ready(qk_query_ready),
        .in_valid(in_valid && (state_r == ST_SCORE)), .in_ready(qk_in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_group(in_group), .in_mask(in_mask),
        .in_key_s12(in_key_s12), .in_key_meta16(in_key_meta16),
        .out_valid(qk_out_valid), .out_ready(qk_out_ready),
        .out_score_q14_s20(qk_out_score), .out_mask(qk_out_mask),
        .out_key_index(qk_out_key_index), .out_last_key(qk_out_last_key),
        .input_group_count(qk_input_group_count_unused),
        .output_score_count(qk_output_score_count_unused),
        .clip_count(score_clip_count), .error(qk_error)
    );

    hap_softmax_row_128 u_softmax (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(qk_out_valid), .in_ready(softmax_in_ready),
        .in_first_key(qk_out_key_index == 0),
        .in_last_key(qk_out_last_key), .in_mask(qk_out_mask),
        .in_score_q14_s20(qk_out_score),
        .out_valid(softmax_out_valid), .out_ready(softmax_out_ready),
        .out_prob_u16(softmax_out_prob),
        .out_key_index(softmax_out_key_index),
        .out_last_key(softmax_out_last_key), .busy(),
        .input_score_count(softmax_input_count_unused),
        .output_prob_count(softmax_output_count_unused),
        .row_count(softmax_row_count_unused), .error(softmax_error)
    );

    hap_pv_tile16_s43 u_pv (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(softmax_out_valid), .in_ready(pv_in_ready),
        .in_first_key(softmax_out_key_index == 0),
        .in_last_key(softmax_out_last_key),
        .in_prob_u16(softmax_out_prob),
        .in_v16_s12(value_mem[softmax_out_key_index]),
        .in_v_meta16(value_meta_mem[softmax_out_key_index]),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_context16_s24(out_context16_s24),
        .input_key_count(pv_input_key_count_unused),
        .output_row_count(pv_output_row_count_unused),
        .saturation_count(context_saturation_count), .error(pv_error)
    );

    always @(posedge clk) begin
        if (input_fire && (in_group == 0)) begin
            value_mem[value_write_index_r] <= in_value16_s12;
            value_meta_mem[value_write_index_r] <= in_value_meta16;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_r <= ST_QUERY;
            value_write_index_r <= 7'd0;
            completed_row_count <= 32'd0;
            control_error_r <= 1'b0;
        end else if (clear) begin
            state_r <= ST_QUERY;
            value_write_index_r <= 7'd0;
            completed_row_count <= 32'd0;
            control_error_r <= 1'b0;
        end else begin
            if ((state_r == ST_QUERY) && qk_query_ready)
                state_r <= ST_SCORE;
            if (input_fire && (in_group == 0)) begin
                if ((in_value_meta16[15:14] != 0) ||
                    ((in_value_meta16[7:0] == 0) &&
                        (in_value_meta16[13:8] != 0)) ||
                    ((in_value_meta16[7:0] != 0) &&
                        ((in_value_meta16[13:8] < 8) ||
                         (in_value_meta16[13:8] > 32))))
                    control_error_r <= 1'b1;
                if (value_write_index_r == 7'd127)
                    value_write_index_r <= 7'd0;
                else
                    value_write_index_r <= value_write_index_r + 1'b1;
            end
            if (output_fire) begin
                completed_row_count <= completed_row_count + 32'd1;
                value_write_index_r <= 7'd0;
                state_r <= ST_QUERY;
            end
            if (qk_error || softmax_error || pv_error || control_error_r)
                state_r <= ST_ERROR;
        end
    end

endmodule
