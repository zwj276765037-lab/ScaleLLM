`timescale 1ns / 1ps

// Timing-only local registered-boundary proxy for the V5 8x12 kernel.
// The real production hierarchy launches and captures the entire payload in
// the same SLR as the slice.  Only clk is exposed here, eliminating abstract
// functional PARTPIN gaps while retaining every source/sink bit as one-to-one
// resetless FFs.  This module is not part of the functional production path.
module hap_a8w4_slice8x12_group_registered_ooc_harness (
    input wire clk
);
    localparam integer SRC_W = 4136;
    localparam integer SINK_W = 3523;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_ACTIVATION = 3;
    localparam integer S_WEIGHTS = S_ACTIVATION + 2304;
    localparam integer S_ACT_CODE = S_WEIGHTS + 1536;
    localparam integer S_ACT_SHIFT = S_ACT_CODE + 64;
    localparam integer S_WEIGHT_CODE = S_ACT_SHIFT + 48;
    localparam integer S_WEIGHT_SHIFT = S_WEIGHT_CODE + 96;
    localparam integer S_COLUMN_VALID = S_WEIGHT_SHIFT + 72;
    localparam integer S_OUT_READY = S_COLUMN_VALID + 12;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire signed [3455:0] guard_s36x8x12;
    wire [31:0] input_group_count;
    wire [31:0] output_group_count;
    wire error;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error, output_group_count, input_group_count,
        guard_s36x8x12, out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_a8w4_slice8x12_group_s36 u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .activation_s9x8x32(src_r[S_ACTIVATION +: 2304]),
        .weights_s4x12x32(src_r[S_WEIGHTS +: 1536]),
        .activation_code_u8x8(src_r[S_ACT_CODE +: 64]),
        .activation_shift_u6x8(src_r[S_ACT_SHIFT +: 48]),
        .weight_code_u8x12(src_r[S_WEIGHT_CODE +: 96]),
        .weight_shift_u6x12(src_r[S_WEIGHT_SHIFT +: 72]),
        .column_valid_u12(src_r[S_COLUMN_VALID +: 12]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .guard_s36x8x12(guard_s36x8x12),
        .input_group_count(input_group_count),
        .output_group_count(output_group_count), .error(error)
    );

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("kernel12 registered OOC vector layout mismatch");
    end
endmodule
