`timescale 1ns / 1ps

// Functional cohort16 down engine boundary.  One U8 product activation group
// is centered/replayed over all output tiles, then two physical 8x16 slices
// compute and update their local banked S45 states.  W4 payload enters once;
// the dual-slice hierarchy creates its two local physical copies.
module hap_mlp_down_group_major_engine16_s45 #(
    parameter integer TILES = 256,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES)
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
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*16*24-1:0]    projection_s24x16x16,
    output wire [31:0]                   activation_group_count,
    output wire [31:0]                   weight_tile_count,
    output wire [31:0]                   output_tile_count,
    output wire [31:0]                   saturation_count,
    output wire                          error
);

    wire replay_valid;
    wire replay_ready;
    wire replay_first;
    wire replay_last;
    wire [TILE_W-1:0] replay_tile;
    wire signed [16*32*9-1:0] replay_activation_s9;
    wire signed [16*32*4-1:0] replay_weights_s4;
    wire [16*8-1:0] replay_activation_code;
    wire [16*6-1:0] replay_activation_shift;
    wire [16*8-1:0] replay_weight_code;
    wire [16*6-1:0] replay_weight_shift;
    wire replay_error;
    wire down_error;
    wire [31:0] down_input_tiles;

    hap_mlp_down_activation_replay16 #(
        .TILES(TILES), .GROUPS(GROUPS)
    ) u_replay (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .activation_valid(activation_valid),
        .activation_ready(activation_ready),
        .activation_u8x16x32(activation_u8x16x32),
        .activation_meta_u24x16(activation_meta_u24x16),
        .weight_valid(weight_valid), .weight_ready(weight_ready),
        .weights_s4x16x32(weights_s4x16x32),
        .weight_meta_u224(weight_meta_u224),
        .out_valid(replay_valid), .out_ready(replay_ready),
        .out_first_group(replay_first), .out_last_group(replay_last),
        .out_tile_index(replay_tile),
        .out_activation_s9x16x32(replay_activation_s9),
        .out_weights_s4x16x32(replay_weights_s4),
        .out_activation_code_u8x16(replay_activation_code),
        .out_activation_shift_u6x16(replay_activation_shift),
        .out_weight_code_u8x16(replay_weight_code),
        .out_weight_shift_u6x16(replay_weight_shift),
        .activation_group_count(activation_group_count),
        .weight_tile_count(weight_tile_count),
        .completed_group_count(), .error(replay_error)
    );

    hap_mlp_down_group_major_dual_slice16x16_s45 #(
        .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_down (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(replay_valid), .in_ready(replay_ready),
        .in_first_group(replay_first), .in_last_group(replay_last),
        .in_tile_index(replay_tile),
        .activation_s9x16x32(replay_activation_s9),
        .weights_s4x16x32(replay_weights_s4),
        .activation_code_u8x16(replay_activation_code),
        .activation_shift_u6x16(replay_activation_shift),
        .weight_code_u8x16(replay_weight_code),
        .weight_shift_u6x16(replay_weight_shift),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .projection_s24x16x16(projection_s24x16x16),
        .input_tile_count(down_input_tiles),
        .output_tile_count(output_tile_count),
        .saturation_count(saturation_count), .error(down_error)
    );

    assign error = replay_error || down_error ||
        down_input_tiles > weight_tile_count;

endmodule
