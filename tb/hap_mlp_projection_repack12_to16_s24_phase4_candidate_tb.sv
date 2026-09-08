`timescale 1ns / 1ps

// Adapter lets the signed-off checker instantiate the isolated Run 0124
// candidate without editing or duplicating the checker itself.
module hap_mlp_projection_repack12_to16_s24 #(
    parameter integer ROWS = 16,
    parameter integer MATRICES = 2,
    parameter integer TAG_W = 9,
    parameter integer MATRIX_W = (MATRICES <= 1) ? 1 : $clog2(MATRICES)
) (
    input wire clk, input wire rst_n, input wire clear,
    input wire in_valid, output wire in_ready,
    input wire signed [ROWS*12*24-1:0] in_projection_s24xrowsx12,
    input wire [TAG_W-1:0] in_block_tag,
    input wire [1:0] in_pass_index,
    input wire [MATRIX_W-1:0] in_matrix,
    input wire [11:0] in_col_valid_u12,
    input wire in_last_pass,
    output wire out_valid, input wire out_ready,
    output wire signed [ROWS*16*24-1:0] out_projection_s24xrowsx16,
    output wire [TAG_W-1:0] out_block_tag,
    output wire [1:0] out_record_index,
    output wire [MATRIX_W-1:0] out_matrix,
    output wire [15:0] out_col_valid_u16,
    output wire out_last_record,
    output wire [31:0] input_pass_count,
    output wire [31:0] output_record_count,
    output wire error
);
    // Diagnostic aliases expected by the existing deadlock message.
    wire sequence_active_r = candidate.sequence_active_r;
    wire [TAG_W-1:0] expected_block_r = candidate.expected_block_r;
    wire [1:0] expected_pass_r = candidate.expected_pass_r;
    wire [MATRIX_W-1:0] expected_matrix_r = candidate.expected_matrix_r;
    wire order_legal_c = candidate.order_legal_c;
    wire output_capacity = candidate.output_capacity;
    hap_mlp_projection_repack12_to16_s24_phase4_candidate #(
        .ROWS(ROWS), .MATRICES(MATRICES), .TAG_W(TAG_W),
        .MATRIX_W(MATRIX_W)
    ) candidate (.*);
endmodule

`include "hap_mlp_projection_repack12_to16_s24_tb.sv"
