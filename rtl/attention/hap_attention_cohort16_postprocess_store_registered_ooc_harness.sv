`timescale 1ns / 1ps

module hap_attention_cohort16_postprocess_store_registered_ooc_harness (
    input wire clk
);
    localparam integer S_CAPTURE_VALID = 0;
    localparam integer S_TILE = S_CAPTURE_VALID + 1;
    localparam integer S_WAVE = S_TILE + 10;
    localparam integer S_PROJECTION = S_WAVE + 1;
    localparam integer S_SHIFT_VALID = S_PROJECTION + 3072;
    localparam integer S_INPUT_ROW = S_SHIFT_VALID + 1;
    localparam integer S_STORE_VALID = S_INPUT_ROW + 4;
    localparam integer S_OUTPUT_INDEX = S_STORE_VALID + 1;
    localparam integer S_Y0 = S_OUTPUT_INDEX + 9;
    localparam integer S_Y1 = S_Y0 + 24;
    localparam integer S_QUANT_ROW = S_Y1 + 24;
    localparam integer SRC_W = S_QUANT_ROW + 4;
    localparam integer SINK_W = 48 + 3072;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire [47:0] rope_input_pair_s24;
    wire [3071:0] quant_s24;
    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        quant_s24, rope_input_pair_s24};

    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_attention_cohort16_postprocess_store u_dut (
        .clk(clk),
        .projection_capture_valid(src_r[S_CAPTURE_VALID]),
        .projection_tile(src_r[S_TILE +: 10]),
        .projection_wave(src_r[S_WAVE]),
        .projection_s24(src_r[S_PROJECTION +: 3072]),
        .rope_shift_valid(src_r[S_SHIFT_VALID]),
        .rope_input_row(src_r[S_INPUT_ROW +: 4]),
        .rope_store_valid(src_r[S_STORE_VALID]),
        .rope_output_index(src_r[S_OUTPUT_INDEX +: 9]),
        .rope_y0_s24(src_r[S_Y0 +: 24]),
        .rope_y1_s24(src_r[S_Y1 +: 24]),
        .quant_row(src_r[S_QUANT_ROW +: 4]),
        .rope_input_pair_s24(rope_input_pair_s24),
        .quant_s24(quant_s24)
    );

    initial begin
        if (SRC_W != 3151 || SINK_W != 3120)
            $error("Postprocess registered OOC vector layout mismatch");
    end
endmodule
