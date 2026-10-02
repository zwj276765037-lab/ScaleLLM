`timescale 1ns / 1ps

module m13_sc_recovery_array96 (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire signed [96*17-1:0]      dot0_s17x96,
    input  wire signed [96*17-1:0]      dot1_s17x96,
    input  wire [96*8-1:0]              activation_code_u8x96,
    input  wire [96*6-1:0]              activation_shift_u6x96,
    input  wire [96*8-1:0]              weight0_code_u8x96,
    input  wire [96*6-1:0]              weight0_shift_u6x96,
    input  wire [96*8-1:0]              weight1_code_u8x96,
    input  wire [96*6-1:0]              weight1_shift_u6x96,
    output wire                         out_valid,
    output wire signed [96*36-1:0]      contribution0_s36_q24x96,
    output wire signed [96*36-1:0]      contribution1_s36_q24x96,
    output reg                          error
);
    localparam integer LANES = 96;
    wire [LANES-1:0] lane_ready;
    wire [LANES-1:0] lane_valid;
    wire [LANES-1:0] lane_error;
    wire in_fire = in_valid && in_ready;

    assign in_ready = rst_n && !clear && &lane_ready;
    assign out_valid = rst_n && !clear && &lane_valid;

    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin : g_lane
            m13_sc_recover2_q24 u_lane (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_fire), .in_ready(lane_ready[lane]),
                .dot0_s17(dot0_s17x96[lane*17 +: 17]),
                .dot1_s17(dot1_s17x96[lane*17 +: 17]),
                .activation_code_u8(
                    activation_code_u8x96[lane*8 +: 8]),
                .activation_shift_u6(
                    activation_shift_u6x96[lane*6 +: 6]),
                .weight0_code_u8(weight0_code_u8x96[lane*8 +: 8]),
                .weight0_shift_u6(weight0_shift_u6x96[lane*6 +: 6]),
                .weight1_code_u8(weight1_code_u8x96[lane*8 +: 8]),
                .weight1_shift_u6(weight1_shift_u6x96[lane*6 +: 6]),
                .out_valid(lane_valid[lane]),
                .contribution0_s36_q24(
                    contribution0_s36_q24x96[lane*36 +: 36]),
                .contribution1_s36_q24(
                    contribution1_s36_q24x96[lane*36 +: 36]),
                .error(lane_error[lane])
            );
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || clear)
            error <= 1'b0;
        else if (|lane_error ||
                 lane_ready != {LANES{lane_ready[0]}} ||
                 ((|lane_valid) && lane_valid != {LANES{lane_valid[0]}}))
            error <= 1'b1;
    end
endmodule
