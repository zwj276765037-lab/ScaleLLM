`timescale 1ns / 1ps

// Timing-only registered-boundary proxy for hap_mlp_w4_repack48_to12.
// The raw leaf has 4,000+ functional boundary bits.  In mode OOC those
// abstract partition pins have no production launch/capture placement, so a
// raw route is dominated by PARTPIN gaps and is not a valid internal timing
// signature.  This harness supplies resetless local source/sink FFs, matching
// the intended integration contract: the repacker is placed beside the DDR
// join and the 8x12 kernel with registered boundaries.  The only top port is
// the real 150 MHz clock.
module hap_mlp_w4_repack48_to12_registered_ooc_harness (
    input wire clk
);
    localparam integer SRC_W = 2327;
    localparam integer SINK_W = 1850;

    // Source layout.
    localparam integer S_RST_N       = 0;
    localparam integer S_CLEAR       = 1;
    localparam integer S_IN_VALID    = 2;
    localparam integer S_WEIGHTS     = 3;
    localparam integer S_META        = S_WEIGHTS + 2048;
    localparam integer S_TAG         = S_META + 224;
    localparam integer S_RECORD      = S_TAG + 32;
    localparam integer S_MASK        = S_RECORD + 2;
    localparam integer S_FLUSH       = S_MASK + 16;
    localparam integer S_OUT_READY   = S_FLUSH + 1;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;

    // One-to-one recirculation prevents constant trimming without adding a
    // wide parity/checksum cone.  Proxy registers are intentionally resetless.
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire signed [1535:0] out_weights;
    wire [167:0] out_meta;
    wire [31:0] out_tag;
    wire [1:0] out_pass;
    wire [11:0] out_mask;
    wire out_last;
    wire [31:0] input_records;
    wire [31:0] input_supertiles;
    wire [31:0] output_passes;
    wire error;

    (* DONT_TOUCH = "yes", KEEP = "yes" *)
    wire [SINK_W-1:0] dut_outputs = {
        error, output_passes, input_supertiles, input_records,
        out_last, out_mask, out_pass, out_tag, out_meta, out_weights,
        out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_w4_repack48_to12 #(.TAG_W(32)) u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .in_weights_s4x16x32(src_r[S_WEIGHTS +: 2048]),
        .in_weight_meta_u224(src_r[S_META +: 224]),
        .in_tag(src_r[S_TAG +: 32]),
        .in_record_index(src_r[S_RECORD +: 2]),
        .in_col_valid_u16(src_r[S_MASK +: 16]),
        .in_flush(src_r[S_FLUSH]),
        .out_valid(out_valid), .out_ready(src_r[S_OUT_READY]),
        .out_weights_s4x12x32(out_weights),
        .out_weight_meta_u168(out_meta), .out_tag(out_tag),
        .out_pass_index(out_pass), .out_col_valid_u12(out_mask),
        .out_last_pass(out_last),
        .input_record_count(input_records),
        .input_supertile_count(input_supertiles),
        .output_pass_count(output_passes), .error(error)
    );

    initial begin
        if (S_OUT_READY != SRC_W-1 || $bits(dut_outputs) != SINK_W)
            $error("repack48 registered OOC proxy vector layout mismatch");
    end
endmodule
