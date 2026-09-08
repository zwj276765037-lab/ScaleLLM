`timescale 1ns / 1ps

module hap_attention_cohort16_context_store_ooc_wrapper (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 row_write_valid,
    input  wire [3:0]           row_write_row,
    input  wire [4:0]           row_write_head,
    input  wire [2:0]           row_write_tile,
    input  wire [383:0]         row_write_s24,
    input  wire                 read_issue,
    input  wire                 read_wave,
    input  wire [3:0]           read_slot,
    input  wire [6:0]           read_group,
    output wire [8*32*24-1:0]  activation_s24
);

    (* KEEP_HIERARCHY = "yes", DONT_TOUCH = "yes" *)
    hap_attention_cohort16_context_store u_context_store (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .row_write_valid(row_write_valid),
        .row_write_row(row_write_row),
        .row_write_head(row_write_head),
        .row_write_tile(row_write_tile),
        .row_write_s24(row_write_s24),
        .read_issue(read_issue), .read_wave(read_wave),
        .read_slot(read_slot), .read_group(read_group),
        .activation_s24(activation_s24)
    );

endmodule
