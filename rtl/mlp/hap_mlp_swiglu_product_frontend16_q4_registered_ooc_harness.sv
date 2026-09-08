`timescale 1ns / 1ps

// Registered-boundary physical harness for the production cohort16 SwiGLU.
// The only top-level port is the real core clock; all payload and control
// boundaries are protected FFs so OOC timing contains no abstract IO paths.
module hap_mlp_swiglu_product_frontend16_q4_registered_ooc_harness (
    input wire clk
);
    localparam integer SRC_W = 6150;
    localparam integer SINK_W = 4611;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_IN_IS_UP = 3;
    localparam integer S_IN_SECOND_HALF = 4;
    localparam integer S_PROJECTION = 5;
    localparam integer S_OUT_READY = S_PROJECTION + 16*16*24;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire [16*32*8-1:0] activation_u8;
    wire [16*24-1:0] activation_meta;
    wire [31:0] input_tile_count;
    wire [31:0] product_group_count;
    wire [31:0] activation_group_count;
    wire [31:0] frontend_busy_cycle_count;
    wire error;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error, frontend_busy_cycle_count, activation_group_count,
        product_group_count, input_tile_count, activation_meta,
        activation_u8, out_valid, in_ready
    };

    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_swiglu_product_frontend16_q4 u_dut (
        .clk(clk),
        .rst_n(src_r[S_RST_N]),
        .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]),
        .in_ready(in_ready),
        .in_is_up(src_r[S_IN_IS_UP]),
        .in_second_half(src_r[S_IN_SECOND_HALF]),
        .projection_s24x16x16(src_r[S_PROJECTION +: 16*16*24]),
        .out_valid(out_valid),
        .out_ready(src_r[S_OUT_READY]),
        .activation_u8x16x32(activation_u8),
        .activation_meta_u24x16(activation_meta),
        .input_tile_count(input_tile_count),
        .product_group_count(product_group_count),
        .activation_group_count(activation_group_count),
        .frontend_busy_cycle_count(frontend_busy_cycle_count),
        .error(error)
    );

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("SwiGLU registered OOC vector layout mismatch");
    end
endmodule
