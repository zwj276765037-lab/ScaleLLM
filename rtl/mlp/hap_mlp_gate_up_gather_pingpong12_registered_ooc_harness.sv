`timescale 1ns / 1ps

// Timing-only registered-boundary OOC harness for the V5 gate/up ping-pong
// gather.  The only top-level port is the real 150 MHz core clock.  Resetless
// source and sink FFs model the required production registered boundaries and
// remove abstract OOC partition-pin placement from the timing result.
//
// This harness is not a functional command source.  One-to-one recirculation
// prevents constant trimming while avoiding a wide parity/checksum cone.
module hap_mlp_gate_up_gather_pingpong12_registered_ooc_harness (
    input wire clk
);
    localparam integer GROUPS = 128;
    localparam integer BLOCK_W = 10;
    localparam integer GROUP_W = 7;
    localparam integer SRC_W = 2318;
    localparam integer SINK_W = 1870;

    localparam integer S_RST_N       = 0;
    localparam integer S_CLEAR       = 1;
    localparam integer S_IN_VALID    = 2;
    localparam integer S_BLOCK       = 3;
    localparam integer S_COLUMNS     = S_BLOCK + BLOCK_W;
    localparam integer S_MATRIX      = S_COLUMNS + 6;
    localparam integer S_RECORD      = S_MATRIX + 1;
    localparam integer S_GROUP       = S_RECORD + 2;
    localparam integer S_WEIGHTS     = S_GROUP + GROUP_W;
    localparam integer S_META        = S_WEIGHTS + 2048;
    localparam integer S_MASK        = S_META + 224;
    localparam integer S_OUT_READY   = S_MASK + 16;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire [BLOCK_W-1:0] out_block;
    wire out_matrix;
    wire [1:0] out_pass;
    wire [GROUP_W-1:0] out_group;
    wire out_first;
    wire out_last;
    wire out_last_pass;
    wire out_last_block;
    wire signed [1535:0] out_weights;
    wire [167:0] out_meta;
    wire [11:0] out_mask;
    wire [31:0] input_transactions;
    wire [31:0] input_blocks;
    wire [31:0] output_transactions;
    wire [31:0] output_blocks;
    wire error;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error, output_blocks, output_transactions, input_blocks,
        input_transactions, out_mask, out_meta, out_weights, out_last_block,
        out_last_pass, out_last, out_first, out_group, out_pass, out_matrix,
        out_block, out_valid, in_ready
    };

    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_gate_up_gather_pingpong12 #(
        .GROUPS(GROUPS), .BLOCK_W(BLOCK_W), .GROUP_W(GROUP_W),
        .BANK_DEPTH(8*GROUPS)
    ) u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .in_block_index(src_r[S_BLOCK +: BLOCK_W]),
        .in_block_valid_columns(src_r[S_COLUMNS +: 6]),
        .in_matrix(src_r[S_MATRIX]),
        .in_record_index(src_r[S_RECORD +: 2]),
        .in_k_group(src_r[S_GROUP +: GROUP_W]),
        .in_weights_s4x16x32(src_r[S_WEIGHTS +: 2048]),
        .in_weight_meta_u224(src_r[S_META +: 224]),
        .in_col_valid_u16(src_r[S_MASK +: 16]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .out_block_index(out_block), .out_matrix(out_matrix),
        .out_pass_index(out_pass), .out_k_group(out_group),
        .out_first_group(out_first), .out_last_group(out_last),
        .out_last_pass(out_last_pass),
        .out_last_block_transaction(out_last_block),
        .out_weights_s4x12x32(out_weights),
        .out_weight_meta_u168(out_meta),
        .out_col_valid_u12(out_mask),
        .input_transaction_count(input_transactions),
        .input_block_count(input_blocks),
        .output_transaction_count(output_transactions),
        .output_block_count(output_blocks), .error(error)
    );

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("gate/up gather registered OOC vector layout mismatch");
    end

endmodule
