`timescale 1ns/1ps

// Fixed-parameter wrappers keep the OOC source contract explicit.  The
// arithmetic implementation is shared with the checked 16-lane FP slot.
module m5_fp16_qk_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  query_load_valid,
    output wire                  query_load_ready,
    input  wire [1:0]            query_load_group,
    input  wire [511:0]          query_group_fp,
    output wire                  query_ready,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_key,
    input  wire                  in_last_key,
    input  wire [1:0]            in_group,
    input  wire                  in_mask,
    input  wire [511:0]          key_group_fp,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [19:0]    out_score_q14_s20,
    output wire                  out_mask,
    output wire [6:0]            out_key_index,
    output wire                  out_last_key,
    output wire [31:0]           input_group_count,
    output wire [31:0]           output_score_count,
    output wire [31:0]           clip_count,
    output wire                  error
);
    m7_fp_qk_slot_arch #(.FP_W(16)) u_qk (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .query_load_valid(query_load_valid),
        .query_load_ready(query_load_ready),
        .query_load_group(query_load_group),
        .query_group_fp(query_group_fp), .query_ready(query_ready),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_group(in_group), .in_mask(in_mask),
        .key_group_fp(key_group_fp), .out_valid(out_valid),
        .out_ready(out_ready), .out_score_q14_s20(out_score_q14_s20),
        .out_mask(out_mask), .out_key_index(out_key_index),
        .out_last_key(out_last_key), .input_group_count(input_group_count),
        .output_score_count(output_score_count), .clip_count(clip_count),
        .error(error)
    );
endmodule

module m5_fp32_qk_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  query_load_valid,
    output wire                  query_load_ready,
    input  wire [1:0]            query_load_group,
    input  wire [1023:0]         query_group_fp,
    output wire                  query_ready,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire                  in_first_key,
    input  wire                  in_last_key,
    input  wire [1:0]            in_group,
    input  wire                  in_mask,
    input  wire [1023:0]         key_group_fp,
    output wire                  out_valid,
    input  wire                  out_ready,
    output wire signed [19:0]    out_score_q14_s20,
    output wire                  out_mask,
    output wire [6:0]            out_key_index,
    output wire                  out_last_key,
    output wire [31:0]           input_group_count,
    output wire [31:0]           output_score_count,
    output wire [31:0]           clip_count,
    output wire                  error
);
    m7_fp_qk_slot_arch #(.FP_W(32)) u_qk (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .query_load_valid(query_load_valid),
        .query_load_ready(query_load_ready),
        .query_load_group(query_load_group),
        .query_group_fp(query_group_fp), .query_ready(query_ready),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_key(in_first_key), .in_last_key(in_last_key),
        .in_group(in_group), .in_mask(in_mask),
        .key_group_fp(key_group_fp), .out_valid(out_valid),
        .out_ready(out_ready), .out_score_q14_s20(out_score_q14_s20),
        .out_mask(out_mask), .out_key_index(out_key_index),
        .out_last_key(out_last_key), .input_group_count(input_group_count),
        .output_score_count(output_score_count), .clip_count(clip_count),
        .error(error)
    );
endmodule
