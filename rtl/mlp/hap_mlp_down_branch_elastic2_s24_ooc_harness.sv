`timescale 1ns / 1ps

// Registered OOC shell for the completed-down queue.  The shell prevents an
// unrealistically unconstrained top-level port route from hiding ingress or
// egress delay while leaving the queue implementation unchanged.
module hap_mlp_down_branch_elastic2_s24_ooc_harness #(
    parameter integer ROWS = 8,
    parameter integer COLS = 12,
    parameter integer TILE_W = 9,
    parameter integer PAYLOAD_W = ROWS*COLS*24
) (
    input wire clk
);

    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg rst_n_r = 1'b0;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg clear_r = 1'b1;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg in_valid_r = 1'b0;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [TILE_W-1:0] in_tile_r = '0;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg signed [PAYLOAD_W-1:0] in_projection_s24_r = '0;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg out_ready_r = 1'b0;

    wire in_ready;
    wire out_valid;
    wire [TILE_W-1:0] out_tile;
    wire signed [PAYLOAD_W-1:0] out_projection_s24;

    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg in_ready_sink_r;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg out_valid_sink_r;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg [TILE_W-1:0] out_tile_sink_r;
    (* DONT_TOUCH = "yes", SHREG_EXTRACT = "NO" *)
    reg signed [PAYLOAD_W-1:0] out_projection_s24_sink_r;

    always @(posedge clk) begin
        rst_n_r <= ~rst_n_r;
        clear_r <= rst_n_r & clear_r;
        in_valid_r <= in_ready ^ out_valid_sink_r;
        in_tile_r <= in_tile_r + {{(TILE_W-1){1'b0}}, 1'b1};
        in_projection_s24_r <= in_projection_s24_r +
            {{(PAYLOAD_W-1){1'b0}}, 1'b1};
        out_ready_r <= in_valid_r ^ out_valid;

        in_ready_sink_r <= in_ready;
        out_valid_sink_r <= out_valid;
        out_tile_sink_r <= out_tile;
        out_projection_s24_sink_r <= out_projection_s24;
    end

    (* keep_hierarchy = "yes", DONT_TOUCH = "yes" *)
    hap_mlp_down_branch_elastic2_s24 #(
        .ROWS(ROWS), .COLS(COLS), .TILE_W(TILE_W)
    ) u_queue (
        .clk(clk), .rst_n(rst_n_r), .clear(clear_r),
        .in_valid(in_valid_r), .in_ready(in_ready), .in_tile(in_tile_r),
        .in_projection_s24(in_projection_s24_r),
        .out_valid(out_valid), .out_ready(out_ready_r),
        .out_tile(out_tile), .out_projection_s24(out_projection_s24)
    );

endmodule
