`timescale 1ns / 1ps

// ScaleCode recovery lane with default, unforced multiplier mapping.
module m13_sc_recover2_q24_auto (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire signed [16:0]   dot0_s17,
    input  wire signed [16:0]   dot1_s17,
    input  wire [7:0]           activation_code_u8,
    input  wire [5:0]           activation_shift_u6,
    input  wire [7:0]           weight0_code_u8,
    input  wire [5:0]           weight0_shift_u6,
    input  wire [7:0]           weight1_code_u8,
    input  wire [5:0]           weight1_shift_u6,
    output wire                 out_valid,
    output wire signed [35:0]   contribution0_s36_q24,
    output wire signed [35:0]   contribution1_s36_q24,
    output wire                 error
);
    wire recover_valid;
    wire signed [32:0] raw0_s33;
    wire signed [32:0] raw1_s33;
    wire tag_valid;
    wire [13:0] total_shift_tag;
    wire [6:0] total0 = {1'b0,activation_shift_u6} +
        {1'b0,weight0_shift_u6};
    wire [6:0] total1 = {1'b0,activation_shift_u6} +
        {1'b0,weight1_shift_u6};

    m13_scalecode_recover2_auto u_recover (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17),
        .activation_code_u8(activation_code_u8),
        .weight0_code_u8(weight0_code_u8),
        .weight1_code_u8(weight1_code_u8),
        .out_valid(recover_valid), .out_ready(1'b1),
        .raw0_s33(raw0_s33), .raw1_s33(raw1_s33)
    );

    m13_delay_bus #(.WIDTH(14), .DEPTH(3)) u_shift_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && in_ready), .in_data({total1,total0}),
        .out_valid(tag_valid), .out_data(total_shift_tag)
    );

    function automatic signed [35:0] align_raw_s36_q24;
        input signed [32:0] raw_s33;
        input [6:0] total_shift;
        reg signed [35:0] extended;
        begin
            extended = {{3{raw_s33[32]}},raw_s33};
            if (raw_s33 == 0 || total_shift < 21 || total_shift > 44)
                align_raw_s36_q24 = 36'sd0;
            else if (total_shift < 24)
                align_raw_s36_q24 = extended <<< (24-total_shift);
            else
                align_raw_s36_q24 = extended >>> (total_shift-24);
        end
    endfunction

    assign out_valid = rst_n && !clear && recover_valid && tag_valid;
    assign contribution0_s36_q24 = align_raw_s36_q24(
        raw0_s33,total_shift_tag[0 +: 7]);
    assign contribution1_s36_q24 = align_raw_s36_q24(
        raw1_s33,total_shift_tag[7 +: 7]);
    assign error = rst_n && !clear && (recover_valid != tag_valid);
endmodule
