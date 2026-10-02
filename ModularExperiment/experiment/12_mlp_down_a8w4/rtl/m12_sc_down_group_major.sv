`timescale 1ns / 1ps

// Thin experimental boundary around the production ScaleCode Down dual slice.
// Arithmetic, tag FIFOs, S45 tile banks and S24 finalization remain production
// RTL; this wrapper adds only explicit full-shape ordering telemetry.
module m12_sc_down_group_major #(
    parameter integer TILES = 342,
    parameter integer GROUPS = 448,
    parameter integer TILE_W = (TILES <= 2) ? 1 : $clog2(TILES),
    parameter integer GROUP_W = (GROUPS <= 2) ? 1 : $clog2(GROUPS)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_first_group,
    input  wire                          in_last_group,
    input  wire [TILE_W-1:0]             in_tile_index,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [12*32*4-1:0]     weights_s4x12x32,
    input  wire [16*8-1:0]               activation_code_u8x16,
    input  wire [16*6-1:0]               activation_shift_u6x16,
    input  wire [12*8-1:0]               weight_code_u8x12,
    input  wire [12*6-1:0]               weight_shift_u6x12,
    input  wire [11:0]                   column_valid_u12,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire [TILE_W-1:0]             out_tile_index,
    output wire signed [16*12*24-1:0]    projection_s24x16x12,
    output wire [31:0]                   input_transaction_count,
    output reg  [31:0]                   input_group_count,
    output wire [31:0]                   output_tile_count,
    output wire [31:0]                   saturation_count,
    output wire                          error
);
    wire core_error;
    reg order_error_r;
    reg [TILE_W-1:0] expected_tile_r;
    reg [GROUP_W-1:0] expected_group_r;
    wire in_fire = in_valid && in_ready;
    wire expected_mask = in_tile_index == TILES-1 ?
        column_valid_u12 == 12'h00f : column_valid_u12 == 12'hfff;

    assign error = core_error || order_error_r;

    hap_mlp_down_group_major_dual_slice16x12_s45 #(
        .TILES(TILES), .GROUPS(GROUPS), .TILE_W(TILE_W)
    ) u_production (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .in_first_group(in_first_group), .in_last_group(in_last_group),
        .in_tile_index(in_tile_index),
        .activation_s9x16x32(activation_s9x16x32),
        .weights_s4x12x32(weights_s4x12x32),
        .activation_code_u8x16(activation_code_u8x16),
        .activation_shift_u6x16(activation_shift_u6x16),
        .weight_code_u8x12(weight_code_u8x12),
        .weight_shift_u6x12(weight_shift_u6x12),
        .column_valid_u12(column_valid_u12),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_tile_index(out_tile_index),
        .projection_s24x16x12(projection_s24x16x12),
        .input_tile_count(input_transaction_count),
        .output_pass_count(output_tile_count),
        .saturation_count(saturation_count), .error(core_error)
    );

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            expected_tile_r <= '0;
            expected_group_r <= '0;
            input_group_count <= 32'd0;
            order_error_r <= 1'b0;
        end else if (in_fire) begin
            if (in_tile_index != expected_tile_r ||
                in_first_group != (expected_group_r == 0) ||
                in_last_group != (expected_group_r == GROUPS-1) ||
                !expected_mask)
                order_error_r <= 1'b1;
            if (expected_tile_r == TILES-1) begin
                expected_tile_r <= '0;
                input_group_count <= input_group_count + 1'b1;
                if (expected_group_r == GROUPS-1)
                    expected_group_r <= '0;
                else
                    expected_group_r <= expected_group_r + 1'b1;
            end else
                expected_tile_r <= expected_tile_r + 1'b1;
        end
    end
endmodule
