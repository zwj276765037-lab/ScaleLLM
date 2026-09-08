`timescale 1ns / 1ps

// OOC-only physical wrapper.  The two independent interfaces keep both
// reciprocal and probability datapaths observable during implementation.
module hap_softmax_recip_prob_ooc (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          clear,
    input  wire          recip_in_valid,
    output wire          recip_in_ready,
    input  wire [23:0]   recip_in_row_sum_u24,
    output wire          recip_out_valid,
    input  wire          recip_out_ready,
    output wire [16:0]   recip_out_u17,
    input  wire          prob_in_valid,
    output wire          prob_in_ready,
    input  wire [16:0]   prob_in_exp_u17,
    input  wire [16:0]   prob_in_recip_u17,
    output wire          prob_out_valid,
    input  wire          prob_out_ready,
    output wire [15:0]   prob_out_u16,
    output wire          error
);

    wire [31:0] recip_input_count_unused;
    wire [31:0] recip_output_count_unused;
    wire [31:0] prob_clamp_count_unused;
    wire recip_error;
    wire prob_error;

    assign error = recip_error | prob_error;

    hap_softmax_recip_u17 u_recip (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(recip_in_valid), .in_ready(recip_in_ready),
        .in_row_sum_u24(recip_in_row_sum_u24),
        .out_valid(recip_out_valid), .out_ready(recip_out_ready),
        .out_recip_u17(recip_out_u17),
        .input_count(recip_input_count_unused),
        .output_count(recip_output_count_unused), .error(recip_error)
    );

    hap_softmax_prob_u16 u_prob (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(prob_in_valid), .in_ready(prob_in_ready),
        .in_exp_u17(prob_in_exp_u17),
        .in_recip_u17(prob_in_recip_u17),
        .out_valid(prob_out_valid), .out_ready(prob_out_ready),
        .out_prob_u16(prob_out_u16),
        .clamp_count(prob_clamp_count_unused), .error(prob_error)
    );

endmodule
