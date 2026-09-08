`timescale 1ns / 1ps

// Exception-free registered boundary for the production V5 96-lane gate
// accumulator.  Only the real 150 MHz clock reaches a top-level port.
module hap_mlp_tile_accum_s43_v5_96_registered_ooc_harness (
    input wire clk
);
    localparam integer LANES = 96;
    localparam integer SRC_W = 6 + LANES*36;
    localparam integer SINK_W = 3 + LANES*24 + 3*32;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_FIRST = 3;
    localparam integer S_LAST = 4;
    localparam integer S_OUT_READY = 5;
    localparam integer S_GUARD = 6;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire signed [LANES*24-1:0] out_projection_s24;
    wire [31:0] input_group_count;
    wire [31:0] output_tile_count;
    wire [31:0] saturation_count;
    wire error;
    wire [SINK_W-1:0] dut_outputs = {
        error, saturation_count, output_tile_count, input_group_count,
        out_projection_s24, out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_tile_accum_s36 #(
        .LANES(LANES), .ACC_W(43), .GROUPS(128),
        .ALLOW_V5_96_LANES(1)
    ) u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .in_first_group(src_r[S_FIRST]), .in_last_group(src_r[S_LAST]),
        .in_guard_s36(src_r[S_GUARD +: LANES*36]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .out_projection_s24(out_projection_s24),
        .input_group_count(input_group_count),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(error)
    );

    initial begin
        if (S_GUARD + LANES*36 != SRC_W ||
            $bits(dut_outputs) != SINK_W)
            $error("V5 gate accumulator registered OOC vector mismatch");
    end
endmodule
