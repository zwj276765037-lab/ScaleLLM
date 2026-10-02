`timescale 1ns / 1ps

// Native floating-point recovery-only lane:
//   S17 -> FP, multiply activation scale, multiply weight scale,
//   then convert the contribution to the common S36 Q12.24 boundary.
// FP_W=16 deliberately narrows the S17 value to FP16 before both FP16
// multiplications, preserving the production AMD IP RNE/FTZ semantics.
module m13_fp_recover2_q24 #(
    parameter integer FP_W = 16
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire signed [16:0]   dot0_s17,
    input  wire signed [16:0]   dot1_s17,
    input  wire [FP_W-1:0]      activation_scale_fp,
    input  wire [FP_W-1:0]      weight0_scale_fp,
    input  wire [FP_W-1:0]      weight1_scale_fp,
    output wire                 out_valid,
    output wire signed [35:0]   contribution0_s36_q24,
    output wire signed [35:0]   contribution1_s36_q24,
    output wire                 error
);
    wire accept = in_valid && in_ready;
    wire fixed0_valid;
    wire fixed1_valid;
    wire [39:0] fixed0_axis;
    wire [39:0] fixed1_axis;

    assign in_ready = rst_n && !clear;
    assign out_valid = rst_n && !clear && fixed0_valid && fixed1_valid;
    assign contribution0_s36_q24 = fixed0_axis[35:0];
    assign contribution1_s36_q24 = fixed1_axis[35:0];
    assign error = rst_n && !clear && (fixed0_valid != fixed1_valid);

    generate
        if (FP_W == 32) begin : g_fp32
            localparam integer INT_LAT = 6;
            localparam integer MUL_LAT = 8;
            wire int0_valid;
            wire int1_valid;
            wire [31:0] int0_fp32;
            wire [31:0] int1_fp32;
            wire int_meta_valid;
            wire [95:0] int_meta;
            wire mul0a_valid;
            wire mul1a_valid;
            wire [31:0] mul0a_fp32;
            wire [31:0] mul1a_fp32;
            wire weight_meta_valid;
            wire [63:0] weight_meta;
            wire mul0b_valid;
            wire mul1b_valid;
            wire [31:0] mul0b_fp32;
            wire [31:0] mul1b_fp32;

            m13_int17_to_fp32 u_i0 (
                .aclk(clk), .s_axis_a_tvalid(accept),
                .s_axis_a_tdata({{7{dot0_s17[16]}},dot0_s17}),
                .m_axis_result_tvalid(int0_valid),
                .m_axis_result_tdata(int0_fp32));
            m13_int17_to_fp32 u_i1 (
                .aclk(clk), .s_axis_a_tvalid(accept),
                .s_axis_a_tdata({{7{dot1_s17[16]}},dot1_s17}),
                .m_axis_result_tvalid(int1_valid),
                .m_axis_result_tdata(int1_fp32));
            m13_delay_bus #(.WIDTH(96), .DEPTH(INT_LAT)) u_int_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(accept),
                .in_data({weight1_scale_fp,weight0_scale_fp,
                    activation_scale_fp}),
                .out_valid(int_meta_valid), .out_data(int_meta));

            m13_fp32_mul u_m0a (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .s_axis_b_tvalid(int_meta_valid),
                .s_axis_b_tdata(int_meta[0 +: 32]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp32));
            m13_fp32_mul u_m1a (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .s_axis_b_tvalid(int_meta_valid),
                .s_axis_b_tdata(int_meta[0 +: 32]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp32));
            m13_delay_bus #(.WIDTH(64), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(int_meta_valid),
                .in_data({int_meta[64 +: 32],int_meta[32 +: 32]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));

            m13_fp32_mul u_m0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 32]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(mul0b_fp32));
            m13_fp32_mul u_m1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[32 +: 32]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(mul1b_fp32));

            m13_fp32_to_s36 u_o0 (
                .aclk(clk), .s_axis_a_tvalid(mul0b_valid),
                .s_axis_a_tdata(mul0b_fp32),
                .m_axis_result_tvalid(fixed0_valid),
                .m_axis_result_tdata(fixed0_axis));
            m13_fp32_to_s36 u_o1 (
                .aclk(clk), .s_axis_a_tvalid(mul1b_valid),
                .s_axis_a_tdata(mul1b_fp32),
                .m_axis_result_tvalid(fixed1_valid),
                .m_axis_result_tdata(fixed1_axis));
        end else begin : g_fp16
            localparam integer INT_LAT = 6;
            localparam integer NARROW_LAT = 3;
            localparam integer MUL_LAT = 6;
            wire int0_valid;
            wire int1_valid;
            wire [31:0] int0_fp32;
            wire [31:0] int1_fp32;
            wire int_meta_valid;
            wire [47:0] int_meta;
            wire narrow0_valid;
            wire narrow1_valid;
            wire [15:0] narrow0_fp16;
            wire [15:0] narrow1_fp16;
            wire narrow_meta_valid;
            wire [47:0] narrow_meta;
            wire mul0a_valid;
            wire mul1a_valid;
            wire [15:0] mul0a_fp16;
            wire [15:0] mul1a_fp16;
            wire weight_meta_valid;
            wire [31:0] weight_meta;
            wire mul0b_valid;
            wire mul1b_valid;
            wire [15:0] mul0b_fp16;
            wire [15:0] mul1b_fp16;
            wire wide0_valid;
            wire wide1_valid;
            wire [31:0] wide0_fp32;
            wire [31:0] wide1_fp32;

            m13_int17_to_fp32 u_i0 (
                .aclk(clk), .s_axis_a_tvalid(accept),
                .s_axis_a_tdata({{7{dot0_s17[16]}},dot0_s17}),
                .m_axis_result_tvalid(int0_valid),
                .m_axis_result_tdata(int0_fp32));
            m13_int17_to_fp32 u_i1 (
                .aclk(clk), .s_axis_a_tvalid(accept),
                .s_axis_a_tdata({{7{dot1_s17[16]}},dot1_s17}),
                .m_axis_result_tvalid(int1_valid),
                .m_axis_result_tdata(int1_fp32));
            m13_delay_bus #(.WIDTH(48), .DEPTH(INT_LAT)) u_int_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(accept),
                .in_data({weight1_scale_fp,weight0_scale_fp,
                    activation_scale_fp}),
                .out_valid(int_meta_valid), .out_data(int_meta));

            m13_fp32_to_fp16 u_n0 (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .m_axis_result_tvalid(narrow0_valid),
                .m_axis_result_tdata(narrow0_fp16));
            m13_fp32_to_fp16 u_n1 (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .m_axis_result_tvalid(narrow1_valid),
                .m_axis_result_tdata(narrow1_fp16));
            m13_delay_bus #(.WIDTH(48), .DEPTH(NARROW_LAT)) u_narrow_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(int_meta_valid), .in_data(int_meta),
                .out_valid(narrow_meta_valid), .out_data(narrow_meta));

            m13_fp16_mul u_m0a (
                .aclk(clk), .s_axis_a_tvalid(narrow0_valid),
                .s_axis_a_tdata(narrow0_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp16));
            m13_fp16_mul u_m1a (
                .aclk(clk), .s_axis_a_tvalid(narrow1_valid),
                .s_axis_a_tdata(narrow1_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp16));
            m13_delay_bus #(.WIDTH(32), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(narrow_meta_valid),
                .in_data({narrow_meta[32 +: 16],
                    narrow_meta[16 +: 16]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));

            m13_fp16_mul u_m0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(mul0b_fp16));
            m13_fp16_mul u_m1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[16 +: 16]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(mul1b_fp16));

            m13_fp16_to_fp32 u_w0 (
                .aclk(clk), .s_axis_a_tvalid(mul0b_valid),
                .s_axis_a_tdata(mul0b_fp16),
                .m_axis_result_tvalid(wide0_valid),
                .m_axis_result_tdata(wide0_fp32));
            m13_fp16_to_fp32 u_w1 (
                .aclk(clk), .s_axis_a_tvalid(mul1b_valid),
                .s_axis_a_tdata(mul1b_fp16),
                .m_axis_result_tvalid(wide1_valid),
                .m_axis_result_tdata(wide1_fp32));
            m13_fp32_to_s36 u_o0 (
                .aclk(clk), .s_axis_a_tvalid(wide0_valid),
                .s_axis_a_tdata(wide0_fp32),
                .m_axis_result_tvalid(fixed0_valid),
                .m_axis_result_tdata(fixed0_axis));
            m13_fp32_to_s36 u_o1 (
                .aclk(clk), .s_axis_a_tvalid(wide1_valid),
                .s_axis_a_tdata(wide1_fp32),
                .m_axis_result_tvalid(fixed1_valid),
                .m_axis_result_tdata(fixed1_axis));
        end
    endgenerate

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m13_fp_recover2_q24 FP_W must be 16 or 32");
    end
endmodule
