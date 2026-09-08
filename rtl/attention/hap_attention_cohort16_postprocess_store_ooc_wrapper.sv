`timescale 1ns / 1ps

module hap_attention_cohort16_postprocess_store_ooc_wrapper (
    input  wire                 clk,
    input  wire                 projection_capture_valid,
    input  wire [9:0]           projection_tile,
    input  wire                 projection_wave,
    input  wire [8*16*24-1:0]  projection_s24,
    input  wire                 rope_shift_valid,
    input  wire [3:0]           rope_input_row,
    input  wire                 rope_store_valid,
    input  wire [8:0]           rope_output_index,
    input  wire signed [23:0]   rope_y0_s24,
    input  wire signed [23:0]   rope_y1_s24,
    input  wire [3:0]           quant_row,
    output wire [47:0]          rope_input_pair_s24,
    output wire [4*768-1:0]     quant_s24
);

    (* KEEP_HIERARCHY = "yes", DONT_TOUCH = "yes" *)
    hap_attention_cohort16_postprocess_store u_postprocess_store (
        .clk(clk),
        .projection_capture_valid(projection_capture_valid),
        .projection_tile(projection_tile),
        .projection_wave(projection_wave),
        .projection_s24(projection_s24),
        .rope_shift_valid(rope_shift_valid),
        .rope_input_row(rope_input_row),
        .rope_store_valid(rope_store_valid),
        .rope_output_index(rope_output_index),
        .rope_y0_s24(rope_y0_s24),
        .rope_y1_s24(rope_y1_s24),
        .quant_row(quant_row),
        .rope_input_pair_s24(rope_input_pair_s24),
        .quant_s24(quant_s24)
    );

endmodule
