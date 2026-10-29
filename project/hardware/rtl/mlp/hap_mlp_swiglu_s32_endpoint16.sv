`timescale 1ns / 1ps

// Restored format05 G/U tiles -> S32/F16 products. No scale recovery, H32 or A8.
// The external tile order is G0,U0,G1,U1,... and row/lane order is preserved.
module hap_mlp_swiglu_s32_endpoint16 #(
    parameter integer INTERMEDIATE_COLUMNS = 14336,
    parameter SILU_LUT_FILE = "data/mlp_silu_q16.mem"
) (
    input wire clk,
    input wire rst_n,
    input wire clear,
    input wire in_valid,
    output wire in_ready,
    input wire [6143:0] in_s24x16x16,
    input wire [9:0] in_tile,
    input wire in_matrix,
    input wire in_last,
    output wire out_valid,
    input wire out_ready,
    output wire [8191:0] out_s32x16x16,
    output wire [9:0] out_tile,
    output wire out_last,
    output wire busy,
    output reg error,
    output reg [31:0] input_tile_count,
    output reg [31:0] product_tile_count
);
    localparam integer TILES = INTERMEDIATE_COLUMNS / 16;
    localparam [1:0] S_GATE = 0, S_UP = 1, S_PRODUCT = 2, S_OUTPUT = 3;
    reg [1:0] state_r;
    reg [9:0] tile_r;
    reg [6143:0] gate_r, up_r;
    reg [8191:0] product_r;
    reg [8:0] issue_r, retire_r;
    wire final_tile = tile_r == TILES - 1;
    wire input_fire = in_valid && in_ready;
    wire output_fire = out_valid && out_ready;
    wire leaf_in_ready, leaf_out_valid, leaf_overflow;
    wire signed [31:0] leaf_product;
    wire leaf_in_valid = rst_n && !clear && !error &&
        state_r == S_PRODUCT && issue_r < 256;
    wire leaf_out_ready = rst_n && !clear && !error && state_r == S_PRODUCT;
    wire leaf_in_fire = leaf_in_valid && leaf_in_ready;
    wire leaf_out_fire = leaf_out_valid && leaf_out_ready;

    assign in_ready = rst_n && !clear && !error &&
        (state_r == S_GATE || state_r == S_UP);
    assign out_valid = rst_n && !clear && !error && state_r == S_OUTPUT;
    assign out_s32x16x16 = product_r;
    assign out_tile = tile_r;
    assign out_last = final_tile;
    assign busy = state_r != S_GATE || tile_r != 0;

    hap_mlp_silu_mul #(.LUT_FILE(SILU_LUT_FILE)) u_silu (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(leaf_in_valid), .in_ready(leaf_in_ready),
        .gate_s24($signed(gate_r[issue_r[7:0]*24 +: 24])),
        .up_s24($signed(up_r[issue_r[7:0]*24 +: 24])),
        .out_valid(leaf_out_valid), .out_ready(leaf_out_ready),
        .out_product_s32(leaf_product), .product_overflow(leaf_overflow)
    );

    initial begin
        if (INTERMEDIATE_COLUMNS < 16 || INTERMEDIATE_COLUMNS > 16384 ||
                INTERMEDIATE_COLUMNS % 16 != 0)
            $fatal(1, "SwiGLU endpoint requires 1..1024 complete tiles");
    end

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            state_r <= S_GATE;
            tile_r <= 0;
            issue_r <= 0;
            retire_r <= 0;
            error <= 0;
            input_tile_count <= 0;
            product_tile_count <= 0;
        end else begin
            if (input_fire) begin
                if (input_tile_count != 32'hffffffff)
                    input_tile_count <= input_tile_count + 1'b1;
                if (in_tile != tile_r || in_matrix != (state_r == S_UP) ||
                        in_last != ((state_r == S_UP) && final_tile)) begin
                    error <= 1;
                end else if (state_r == S_GATE) begin
                    gate_r <= in_s24x16x16;
                    state_r <= S_UP;
                end else begin
                    up_r <= in_s24x16x16;
                    issue_r <= 0;
                    retire_r <= 0;
                    state_r <= S_PRODUCT;
                end
            end
            if (leaf_in_fire)
                issue_r <= issue_r + 1'b1;
            if (leaf_out_fire) begin
                product_r[retire_r[7:0]*32 +: 32] <= leaf_product;
                retire_r <= retire_r + 1'b1;
                if (retire_r == 255)
                    state_r <= S_OUTPUT;
            end
            if (leaf_overflow)
                error <= 1;
            if (output_fire) begin
                if (product_tile_count != 32'hffffffff)
                    product_tile_count <= product_tile_count + 1'b1;
                tile_r <= final_tile ? 10'd0 : tile_r + 1'b1;
                state_r <= S_GATE;
            end
        end
    end
endmodule
