`timescale 1ns / 1ps

// Exception-free registered boundary for the 16-row down activation cache.
module hap_mlp_down_activation_cache16_registered_ooc_harness (
    input wire clk
);
    localparam integer PAYLOAD_W = 16*32*8 + 16*24;
    localparam integer SRC_W = 5 + PAYLOAD_W;
    localparam integer SINK_W = 4 + PAYLOAD_W + 2*32;
    localparam integer S_RST_N = 0;
    localparam integer S_CLEAR = 1;
    localparam integer S_IN_VALID = 2;
    localparam integer S_REPLAY = 3;
    localparam integer S_OUT_READY = 4;
    localparam integer S_PAYLOAD = 5;

    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SRC_W-1:0] src_r;
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [SINK_W-1:0] sink_r;
    always @(posedge clk)
        src_r <= {src_r[SRC_W-2:0], ~src_r[SRC_W-1]};

    wire in_ready;
    wire out_valid;
    wire [16*32*8-1:0] out_u8x16x32;
    wire [16*24-1:0] out_meta_u24x16;
    wire full;
    wire [31:0] write_group_count;
    wire [31:0] read_group_count;
    wire error;
    wire [SINK_W-1:0] dut_outputs = {
        error, read_group_count, write_group_count, full,
        out_meta_u24x16, out_u8x16x32, out_valid, in_ready
    };
    always @(posedge clk)
        sink_r <= dut_outputs;

    (* DONT_TOUCH = "yes", KEEP_HIERARCHY = "yes" *)
    hap_mlp_down_activation_cache16 u_dut (
        .clk(clk), .rst_n(src_r[S_RST_N]), .clear(src_r[S_CLEAR]),
        .in_valid(src_r[S_IN_VALID]), .in_ready(in_ready),
        .in_u8x16x32(src_r[S_PAYLOAD +: 16*32*8]),
        .in_meta_u24x16(src_r[S_PAYLOAD + 16*32*8 +: 16*24]),
        .replay_enable(src_r[S_REPLAY]), .out_valid(out_valid),
        .out_ready(src_r[S_OUT_READY]), .out_u8x16x32(out_u8x16x32),
        .out_meta_u24x16(out_meta_u24x16), .full(full),
        .write_group_count(write_group_count),
        .read_group_count(read_group_count), .error(error)
    );

    initial begin
        if (S_PAYLOAD + PAYLOAD_W != SRC_W ||
            $bits(dut_outputs) != SINK_W)
            $error("down activation cache registered OOC vector mismatch");
    end
endmodule
