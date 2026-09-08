`timescale 1ns / 1ps

// Timing-only registered-boundary proxy for the frozen gate/up configuration
// of hap_mlp_projection_repack12_to16_s24.  Functional RTL is unchanged.
// All non-clock inputs/outputs are anchored by same-clock resetless FFs so the
// only top-level partition pin is the real 150 MHz clock.
module hap_mlp_projection_repack12_to16_s24_registered_ooc_harness (
    input wire clk
);
    localparam integer ROWS = 16;
    localparam integer MATRICES = 2;
    localparam integer TAG_W = 9;
    localparam integer MATRIX_W = 1;
    localparam integer IN_W = ROWS*12*24;
    localparam integer OUT_W = ROWS*16*24;
    localparam integer SRC_W = 3 + IN_W + TAG_W + 2 + MATRIX_W + 12 + 2;
    localparam integer SINK_W = 2 + OUT_W + TAG_W + 2 + MATRIX_W +
        16 + 1 + 32 + 32 + 1;

    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_PAYLOAD = 3;
    localparam integer S_TAG = S_PAYLOAD + IN_W;
    localparam integer S_PASS = S_TAG + TAG_W;
    localparam integer S_MATRIX = S_PASS + 2;
    localparam integer S_MASK = S_MATRIX + MATRIX_W;
    localparam integer S_LAST = S_MASK + 12;
    localparam integer S_OUT_READY = S_LAST + 1;

    (* DONT_TOUCH="yes", KEEP="yes", SHREG_EXTRACT="NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH="yes", KEEP="yes", SHREG_EXTRACT="NO" *)
    reg [SINK_W-1:0] sink_r;
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready, out_valid, out_last, error;
    wire signed [OUT_W-1:0] out_payload;
    wire [TAG_W-1:0] out_tag;
    wire [1:0] out_record;
    wire [MATRIX_W-1:0] out_matrix;
    wire [15:0] out_mask;
    wire [31:0] input_count, output_count;
    wire [SINK_W-1:0] dut_outputs = {
        error, output_count, input_count, out_last, out_mask, out_matrix,
        out_record, out_tag, out_payload, out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH="yes", KEEP_HIERARCHY="yes" *)
    hap_mlp_projection_repack12_to16_s24 #(
        .ROWS(ROWS), .MATRICES(MATRICES), .TAG_W(TAG_W),
        .MATRIX_W(MATRIX_W)
    ) u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .in_projection_s24xrowsx12(src_r[S_PAYLOAD +: IN_W]),
        .in_block_tag(src_r[S_TAG +: TAG_W]),
        .in_pass_index(src_r[S_PASS +: 2]),
        .in_matrix(src_r[S_MATRIX +: MATRIX_W]),
        .in_col_valid_u12(src_r[S_MASK +: 12]),
        .in_last_pass(src_r[S_LAST]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .out_projection_s24xrowsx16(out_payload),
        .out_block_tag(out_tag), .out_record_index(out_record),
        .out_matrix(out_matrix), .out_col_valid_u16(out_mask),
        .out_last_record(out_last), .input_pass_count(input_count),
        .output_record_count(output_count), .error(error)
    );

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("projection repacker registered OOC vector layout mismatch");
    end
endmodule
