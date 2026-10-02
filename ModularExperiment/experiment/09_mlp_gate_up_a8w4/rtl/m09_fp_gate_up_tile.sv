`timescale 1ns / 1ps

// Full 16-row x 12-column matched-throughput native-FP Gate/Up tile.
// Ninety-six production packed-dot lanes each own two FP scale/multiply/
// accumulator paths, so every group32 is accepted at II=1 when unstalled.
module m09_fp_gate_up_tile #(
    parameter integer FP_W = 16
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire                          clear,
    input  wire                          in_valid,
    output wire                          in_ready,
    input  wire                          in_first_group,
    input  wire                          in_last_group,
    input  wire signed [16*32*9-1:0]     activation_s9x16x32,
    input  wire signed [12*32*4-1:0]     weights_s4x12x32,
    input  wire [16*FP_W-1:0]            activation_scale_fpx16,
    input  wire [12*FP_W-1:0]            weight_scale_fpx12,
    input  wire [11:0]                   column_valid_u12,
    output wire                          out_valid,
    input  wire                          out_ready,
    output wire signed [16*12*24-1:0]    projection_s24x16x12,
    output reg [31:0]                    input_group_count,
    output reg [31:0]                    output_tile_count,
    output reg                           error
);
    localparam integer ROWS = 16;
    localparam integer COLS = 12;
    localparam integer PAIRS = 6;
    localparam integer LANES = ROWS*PAIRS;

    wire [LANES-1:0] lane_in_ready;
    wire [LANES-1:0] lane_out_valid;
    wire [LANES-1:0] lane_out_ready;
    wire [LANES-1:0] lane_error;
    wire signed [LANES*2*24-1:0] lane_result_s24;
    wire in_fire = in_valid && in_ready;
    wire out_fire = out_valid && out_ready;
    wire mask_is_legal = column_valid_u12 == 12'hfff ||
        column_valid_u12 == 12'h0ff || column_valid_u12 == 12'h00f;

    assign in_ready = rst_n && !clear && lane_in_ready[0];
    assign out_valid = rst_n && !clear && &lane_out_valid;
    assign lane_out_ready = {LANES{out_fire}};

    genvar row;
    genvar pair;
    generate
        for (row = 0; row < ROWS; row = row + 1) begin : g_row
            for (pair = 0; pair < PAIRS; pair = pair + 1) begin : g_pair
                localparam integer LANE = row*PAIRS+pair;
                localparam integer COL0 = pair*2;
                localparam integer COL1 = pair*2+1;
                wire [FP_W-1:0] weight0_scale =
                    column_valid_u12[COL0] ?
                    weight_scale_fpx12[COL0*FP_W +: FP_W] : '0;
                wire [FP_W-1:0] weight1_scale =
                    column_valid_u12[COL1] ?
                    weight_scale_fpx12[COL1*FP_W +: FP_W] : '0;
                wire signed [32*4-1:0] weight0 =
                    column_valid_u12[COL0] ?
                    weights_s4x12x32[COL0*32*4 +: 32*4] : '0;
                wire signed [32*4-1:0] weight1 =
                    column_valid_u12[COL1] ?
                    weights_s4x12x32[COL1*32*4 +: 32*4] : '0;
                wire [31:0] lane_input_count_unused;
                wire [31:0] lane_output_count_unused;

                m09_fp_a8w4_lane2_accum #(.FP_W(FP_W)) u_lane (
                    .clk(clk), .rst_n(rst_n), .clear(clear),
                    .in_valid(in_valid && in_ready),
                    .in_ready(lane_in_ready[LANE]),
                    .in_first_group(in_first_group),
                    .in_last_group(in_last_group),
                    .activation_s9x32(
                        activation_s9x16x32[row*32*9 +: 32*9]),
                    .weight0_s4x32(weight0), .weight1_s4x32(weight1),
                    .activation_scale_fp(
                        activation_scale_fpx16[row*FP_W +: FP_W]),
                    .weight0_scale_fp(weight0_scale),
                    .weight1_scale_fp(weight1_scale),
                    .out_valid(lane_out_valid[LANE]),
                    .out_ready(lane_out_ready[LANE]),
                    .out0_s24(lane_result_s24[(LANE*2)*24 +: 24]),
                    .out1_s24(lane_result_s24[(LANE*2+1)*24 +: 24]),
                    .input_group_count(lane_input_count_unused),
                    .output_tile_count(lane_output_count_unused),
                    .error(lane_error[LANE])
                );

                assign projection_s24x16x12[
                    (row*COLS+COL0)*24 +: 24] =
                    lane_result_s24[(LANE*2)*24 +: 24];
                assign projection_s24x16x12[
                    (row*COLS+COL1)*24 +: 24] =
                    lane_result_s24[(LANE*2+1)*24 +: 24];
            end
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire)
                input_group_count <= input_group_count + 1'b1;
            if (out_fire)
                output_tile_count <= output_tile_count + 1'b1;
            if (|lane_error ||
                lane_in_ready != {LANES{lane_in_ready[0]}} ||
                ((|lane_out_valid) && lane_out_valid !=
                    {LANES{lane_out_valid[0]}}) ||
                (in_fire && !mask_is_legal))
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m09_fp_gate_up_tile FP_W must be 16 or 32");
    end
endmodule


module m09_fp16_gate_up_tile (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_group, in_last_group,
    input wire signed [16*32*9-1:0] activation_s9x16x32,
    input wire signed [12*32*4-1:0] weights_s4x12x32,
    input wire [16*16-1:0] activation_scale_fpx16,
    input wire [12*16-1:0] weight_scale_fpx12,
    input wire [11:0] column_valid_u12,
    output wire out_valid,
    input wire out_ready,
    output wire signed [16*12*24-1:0] projection_s24x16x12,
    output wire [31:0] input_group_count,
    output wire [31:0] output_tile_count,
    output wire error
);
    m09_fp_gate_up_tile #(.FP_W(16)) u_core (.*);
endmodule


module m09_fp32_gate_up_tile (
    input wire clk, rst_n, clear, in_valid,
    output wire in_ready,
    input wire in_first_group, in_last_group,
    input wire signed [16*32*9-1:0] activation_s9x16x32,
    input wire signed [12*32*4-1:0] weights_s4x12x32,
    input wire [16*32-1:0] activation_scale_fpx16,
    input wire [12*32-1:0] weight_scale_fpx12,
    input wire [11:0] column_valid_u12,
    output wire out_valid,
    input wire out_ready,
    output wire signed [16*12*24-1:0] projection_s24x16x12,
    output wire [31:0] input_group_count,
    output wire [31:0] output_tile_count,
    output wire error
);
    m09_fp_gate_up_tile #(.FP_W(32)) u_core (.*);
endmodule
