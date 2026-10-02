`timescale 1ns / 1ps

module m13_fp_recovery_array96 #(
    parameter integer FP_W = 16
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire signed [96*17-1:0]      dot0_s17x96,
    input  wire signed [96*17-1:0]      dot1_s17x96,
    input  wire [96*FP_W-1:0]           activation_scale_fpx96,
    input  wire [96*FP_W-1:0]           weight0_scale_fpx96,
    input  wire [96*FP_W-1:0]           weight1_scale_fpx96,
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
            m13_fp_recover2_q24 #(.FP_W(FP_W)) u_lane (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_fire), .in_ready(lane_ready[lane]),
                .dot0_s17(dot0_s17x96[lane*17 +: 17]),
                .dot1_s17(dot1_s17x96[lane*17 +: 17]),
                .activation_scale_fp(
                    activation_scale_fpx96[lane*FP_W +: FP_W]),
                .weight0_scale_fp(
                    weight0_scale_fpx96[lane*FP_W +: FP_W]),
                .weight1_scale_fp(
                    weight1_scale_fpx96[lane*FP_W +: FP_W]),
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

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m13_fp_recovery_array96 FP_W must be 16 or 32");
    end
endmodule

module m13_fp16_recovery_array96 (
    input wire clk, input wire rst_n, input wire clear,
    input wire in_valid, output wire in_ready,
    input wire signed [96*17-1:0] dot0_s17x96,
    input wire signed [96*17-1:0] dot1_s17x96,
    input wire [96*16-1:0] activation_scale_fpx96,
    input wire [96*16-1:0] weight0_scale_fpx96,
    input wire [96*16-1:0] weight1_scale_fpx96,
    output wire out_valid,
    output wire signed [96*36-1:0] contribution0_s36_q24x96,
    output wire signed [96*36-1:0] contribution1_s36_q24x96,
    output wire error
);
    m13_fp_recovery_array96 #(.FP_W(16)) u_array (.*);
endmodule

module m13_fp32_recovery_array96 (
    input wire clk, input wire rst_n, input wire clear,
    input wire in_valid, output wire in_ready,
    input wire signed [96*17-1:0] dot0_s17x96,
    input wire signed [96*17-1:0] dot1_s17x96,
    input wire [96*32-1:0] activation_scale_fpx96,
    input wire [96*32-1:0] weight0_scale_fpx96,
    input wire [96*32-1:0] weight1_scale_fpx96,
    output wire out_valid,
    output wire signed [96*36-1:0] contribution0_s36_q24x96,
    output wire signed [96*36-1:0] contribution1_s36_q24x96,
    output wire error
);
    m13_fp_recovery_array96 #(.FP_W(32)) u_array (.*);
endmodule
