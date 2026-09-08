`timescale 1ns / 1ps

// Hold one cohort16 product A8 group while the W4 reader walks every down
// output tile.  U8 activations are centered once (u8-zero_point -> S9); the
// same centered group/code/shift is then paired with TILES consecutive W4
// payloads.  This is the control boundary that realizes group-major loop
// order without caching all 448 activation groups.
module hap_mlp_down_activation_replay16 #(
    parameter integer TILES = 256,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES),
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          activation_valid,
    output wire                          activation_ready,
    input  wire [16*32*8-1:0]            activation_u8x16x32,
    input  wire [16*24-1:0]              activation_meta_u24x16,
    input  wire                          weight_valid,
    output wire                          weight_ready,
    input  wire [16*32*4-1:0]            weights_s4x16x32,
    input  wire [223:0]                  weight_meta_u224,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire                          out_first_group,
    output wire                          out_last_group,
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*32*9-1:0]     out_activation_s9x16x32,
    output wire signed [16*32*4-1:0]     out_weights_s4x16x32,
    output wire [16*8-1:0]               out_activation_code_u8x16,
    output wire [16*6-1:0]               out_activation_shift_u6x16,
    output wire [16*8-1:0]               out_weight_code_u8x16,
    output wire [16*6-1:0]               out_weight_shift_u6x16,
    output reg  [31:0]                   activation_group_count,
    output reg  [31:0]                   weight_tile_count,
    output reg  [31:0]                   completed_group_count,
    output reg                           error
);

    reg active_r;
    reg [GROUP_W-1:0] group_r;
    reg [TILE_W-1:0] tile_r;
    reg signed [16*32*9-1:0] activation_s9_r;
    reg [16*8-1:0] activation_code_r;
    reg [16*6-1:0] activation_shift_r;
    wire activation_fire = activation_valid && activation_ready;
    wire weight_fire = out_valid && out_ready;

    assign activation_ready = rst_n && !clear && !active_r &&
        completed_group_count < GROUPS;
    assign weight_ready = rst_n && !clear && active_r && out_ready;
    assign out_valid = rst_n && !clear && active_r && weight_valid;
    assign out_first_group = group_r == 0;
    assign out_last_group = group_r == GROUPS-1;
    assign out_tile_index = tile_r;
    assign out_activation_s9x16x32 = activation_s9_r;
    assign out_weights_s4x16x32 = weights_s4x16x32;
    assign out_activation_code_u8x16 = activation_code_r;
    assign out_activation_shift_u6x16 = activation_shift_r;
    assign out_weight_code_u8x16 = weight_meta_u224[127:0];
    assign out_weight_shift_u6x16 = weight_meta_u224[223:128];

    integer row;
    integer lane;
    reg [7:0] zero_point;
    reg [7:0] activation_value;
    reg signed [8:0] centered;
    always @(posedge clk) begin
        if (!rst_n || clear) begin
            active_r <= 1'b0;
            group_r <= '0;
            tile_r <= '0;
            activation_group_count <= 32'd0;
            weight_tile_count <= 32'd0;
            completed_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (activation_fire) begin
                active_r <= 1'b1;
                tile_r <= '0;
                activation_group_count <= activation_group_count + 32'd1;
                for (row = 0; row < 16; row = row + 1) begin
                    zero_point = activation_meta_u24x16[row*24 +: 8];
                    activation_code_r[row*8 +: 8] <=
                        activation_meta_u24x16[row*24+8 +: 8];
                    activation_shift_r[row*6 +: 6] <=
                        activation_meta_u24x16[row*24+16 +: 6];
                    if (activation_meta_u24x16[row*24+22 +: 2] != 0 ||
                        (activation_meta_u24x16[row*24+8 +: 8] == 0 &&
                         activation_meta_u24x16[row*24+16 +: 6] != 0))
                        error <= 1'b1;
                    for (lane = 0; lane < 32; lane = lane + 1) begin
                        activation_value = activation_u8x16x32[
                            (row*32+lane)*8 +: 8];
                        centered = $signed({1'b0, activation_value}) -
                            $signed({1'b0, zero_point});
                        activation_s9_r[(row*32+lane)*9 +: 9] <=
                            centered;
                    end
                end
            end

            if (weight_fire) begin
                weight_tile_count <= weight_tile_count + 32'd1;
                if (tile_r == TILES-1) begin
                    active_r <= 1'b0;
                    tile_r <= '0;
                    completed_group_count <= completed_group_count + 32'd1;
                    if (group_r == GROUPS-1)
                        group_r <= group_r;
                    else
                        group_r <= group_r + 1'b1;
                end else begin
                    tile_r <= tile_r + 1'b1;
                end
            end

            if (weight_fire && weight_meta_u224[127:0] == 0 &&
                weight_meta_u224[223:128] != 0)
                error <= 1'b1;
            if (completed_group_count > GROUPS ||
                weight_tile_count > GROUPS*TILES)
                error <= 1'b1;
        end
    end

endmodule
