`timescale 1ns / 1ps

module m12_delay_bus #(
    parameter integer WIDTH = 1,
    parameter integer DEPTH = 1
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    input  wire [WIDTH-1:0]     in_data,
    output wire                 out_valid,
    output wire [WIDTH-1:0]     out_data
);
    reg [DEPTH-1:0] valid_r;
    reg [WIDTH-1:0] data_r [0:DEPTH-1];
    integer index;

    assign out_valid = valid_r[DEPTH-1];
    assign out_data = data_r[DEPTH-1];

    always @(posedge clk) begin
        if (!rst_n || clear)
            valid_r <= '0;
        else begin
            valid_r[0] <= in_valid;
            data_r[0] <= in_data;
            for (index = 1; index < DEPTH; index = index + 1) begin
                valid_r[index] <= valid_r[index-1];
                data_r[index] <= data_r[index-1];
            end
        end
    end

    initial begin
        if (WIDTH <= 0 || DEPTH <= 0)
            $error("m12_delay_bus requires positive WIDTH and DEPTH");
    end
endmodule


// Boundary-inclusive native-FP contribution for one row and two columns.
// The integer producer is the production packed group32 dot.  FP16 performs
// both scale multiplies in half precision and widens the contribution to an
// FP32 tile state; FP32 performs both multiplies directly in single precision.
module m12_fp_a8w4_lane2_partial #(
    parameter integer FP_W = 16,
    parameter integer META_DEPTH = 32
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     in_valid,
    output wire                     in_ready,
    input  wire signed [32*9-1:0]  activation_s9x32,
    input  wire signed [32*4-1:0]  weight0_s4x32,
    input  wire signed [32*4-1:0]  weight1_s4x32,
    input  wire [FP_W-1:0]          activation_scale_fp,
    input  wire [FP_W-1:0]          weight0_scale_fp,
    input  wire [FP_W-1:0]          weight1_scale_fp,
    output wire                     out_valid,
    output wire [31:0]              out0_fp32,
    output wire [31:0]              out1_fp32,
    output reg                      error
);
    localparam integer META_PTR_W = $clog2(META_DEPTH);
    localparam integer META_COUNT_W = $clog2(META_DEPTH+1);
    localparam integer META_W = 3*FP_W;

    wire dot_in_ready;
    wire dot_out_valid;
    wire dot_out_ready;
    wire signed [16:0] dot0_s17;
    wire signed [16:0] dot1_s17;
    reg [META_W-1:0] meta_mem [0:META_DEPTH-1];
    reg [META_PTR_W-1:0] meta_wr_ptr_r;
    reg [META_PTR_W-1:0] meta_rd_ptr_r;
    reg [META_COUNT_W-1:0] meta_count_r;
    wire meta_full = meta_count_r == META_DEPTH;
    wire meta_empty = meta_count_r == 0;
    wire in_fire = in_valid && in_ready;
    wire dot_fire = dot_out_valid && dot_out_ready;

    assign in_ready = rst_n && !clear && dot_in_ready && !meta_full;
    assign dot_out_ready = !meta_empty;

    hap_a8w4_group32_pack2_s17 u_dot (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid && in_ready), .in_ready(dot_in_ready),
        .activation_s9x32(activation_s9x32),
        .weight0_s4x32(weight0_s4x32),
        .weight1_s4x32(weight1_s4x32),
        .out_valid(dot_out_valid), .out_ready(dot_out_ready),
        .dot0_s17(dot0_s17), .dot1_s17(dot1_s17)
    );

    wire [META_W-1:0] dot_meta = meta_mem[meta_rd_ptr_r];
    wire [FP_W-1:0] dot_act_scale = dot_meta[0 +: FP_W];
    wire [FP_W-1:0] dot_weight0_scale = dot_meta[FP_W +: FP_W];
    wire [FP_W-1:0] dot_weight1_scale = dot_meta[2*FP_W +: FP_W];
    wire result0_valid;
    wire result1_valid;
    wire [31:0] result0_fp32;
    wire [31:0] result1_fp32;

    assign out_valid = result0_valid && result1_valid;
    assign out0_fp32 = result0_fp32;
    assign out1_fp32 = result1_fp32;

    generate
        if (FP_W == 32) begin : g_fp32
            localparam integer INT_LAT = 6;
            localparam integer MUL_LAT = 8;
            wire int0_valid, int1_valid, int_meta_valid;
            wire [31:0] int0_fp32, int1_fp32;
            wire [95:0] int_meta;
            wire mul0a_valid, mul1a_valid, weight_meta_valid;
            wire [31:0] mul0a_fp32, mul1a_fp32;
            wire [63:0] weight_meta;

            m12_int17_to_fp32 u_i0 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot0_s17[16]}},dot0_s17}),
                .m_axis_result_tvalid(int0_valid),
                .m_axis_result_tdata(int0_fp32));
            m12_int17_to_fp32 u_i1 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot1_s17[16]}},dot1_s17}),
                .m_axis_result_tvalid(int1_valid),
                .m_axis_result_tdata(int1_fp32));
            m12_delay_bus #(.WIDTH(96), .DEPTH(INT_LAT)) u_int_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(dot_fire),
                .in_data({dot_weight1_scale,dot_weight0_scale,
                    dot_act_scale}),
                .out_valid(int_meta_valid), .out_data(int_meta));

            m12_fp32_mul u_m0a (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .s_axis_b_tvalid(int_meta_valid),
                .s_axis_b_tdata(int_meta[0 +: 32]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp32));
            m12_fp32_mul u_m1a (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .s_axis_b_tvalid(int_meta_valid),
                .s_axis_b_tdata(int_meta[0 +: 32]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp32));
            m12_delay_bus #(.WIDTH(64), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(int_meta_valid),
                .in_data({int_meta[64 +: 32],int_meta[32 +: 32]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));

            m12_fp32_mul u_m0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 32]),
                .m_axis_result_tvalid(result0_valid),
                .m_axis_result_tdata(result0_fp32));
            m12_fp32_mul u_m1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[32 +: 32]),
                .m_axis_result_tvalid(result1_valid),
                .m_axis_result_tdata(result1_fp32));
        end else begin : g_fp16
            localparam integer INT_LAT = 6;
            localparam integer NARROW_LAT = 3;
            localparam integer MUL_LAT = 6;
            wire int0_valid, int1_valid, int_meta_valid;
            wire [31:0] int0_fp32, int1_fp32;
            wire [47:0] int_meta;
            wire narrow0_valid, narrow1_valid, narrow_meta_valid;
            wire [15:0] narrow0_fp16, narrow1_fp16;
            wire [47:0] narrow_meta;
            wire mul0a_valid, mul1a_valid, weight_meta_valid;
            wire [15:0] mul0a_fp16, mul1a_fp16;
            wire [31:0] weight_meta;
            wire mul0b_valid, mul1b_valid;
            wire [15:0] mul0b_fp16, mul1b_fp16;

            m12_int17_to_fp32 u_i0 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot0_s17[16]}},dot0_s17}),
                .m_axis_result_tvalid(int0_valid),
                .m_axis_result_tdata(int0_fp32));
            m12_int17_to_fp32 u_i1 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot1_s17[16]}},dot1_s17}),
                .m_axis_result_tvalid(int1_valid),
                .m_axis_result_tdata(int1_fp32));
            m12_delay_bus #(.WIDTH(48), .DEPTH(INT_LAT)) u_int_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(dot_fire),
                .in_data({dot_weight1_scale,dot_weight0_scale,
                    dot_act_scale}),
                .out_valid(int_meta_valid), .out_data(int_meta));

            m12_fp32_to_fp16 u_n0 (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .m_axis_result_tvalid(narrow0_valid),
                .m_axis_result_tdata(narrow0_fp16));
            m12_fp32_to_fp16 u_n1 (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .m_axis_result_tvalid(narrow1_valid),
                .m_axis_result_tdata(narrow1_fp16));
            m12_delay_bus #(.WIDTH(48), .DEPTH(NARROW_LAT)) u_narrow_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(int_meta_valid), .in_data(int_meta),
                .out_valid(narrow_meta_valid), .out_data(narrow_meta));

            m12_fp16_mul u_m0a (
                .aclk(clk), .s_axis_a_tvalid(narrow0_valid),
                .s_axis_a_tdata(narrow0_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp16));
            m12_fp16_mul u_m1a (
                .aclk(clk), .s_axis_a_tvalid(narrow1_valid),
                .s_axis_a_tdata(narrow1_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp16));
            m12_delay_bus #(.WIDTH(32), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(narrow_meta_valid),
                .in_data({narrow_meta[32 +: 16],
                    narrow_meta[16 +: 16]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));

            m12_fp16_mul u_m0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(mul0b_fp16));
            m12_fp16_mul u_m1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[16 +: 16]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(mul1b_fp16));
            m12_fp16_to_fp32 u_w0 (
                .aclk(clk), .s_axis_a_tvalid(mul0b_valid),
                .s_axis_a_tdata(mul0b_fp16),
                .m_axis_result_tvalid(result0_valid),
                .m_axis_result_tdata(result0_fp32));
            m12_fp16_to_fp32 u_w1 (
                .aclk(clk), .s_axis_a_tvalid(mul1b_valid),
                .s_axis_a_tdata(mul1b_fp16),
                .m_axis_result_tvalid(result1_valid),
                .m_axis_result_tdata(result1_fp32));
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            meta_wr_ptr_r <= '0;
            meta_rd_ptr_r <= '0;
            meta_count_r <= '0;
            error <= 1'b0;
        end else begin
            if (in_fire) begin
                meta_mem[meta_wr_ptr_r] <= {
                    weight1_scale_fp,weight0_scale_fp,activation_scale_fp};
                meta_wr_ptr_r <= meta_wr_ptr_r + 1'b1;
            end
            if (dot_fire)
                meta_rd_ptr_r <= meta_rd_ptr_r + 1'b1;
            case ({in_fire,dot_fire})
                2'b10: meta_count_r <= meta_count_r + 1'b1;
                2'b01: meta_count_r <= meta_count_r - 1'b1;
                default: meta_count_r <= meta_count_r;
            endcase
            if (result0_valid != result1_valid || meta_count_r > META_DEPTH)
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m12 FP_W must be 16 or 32");
        if (META_DEPTH < 16 || (META_DEPTH & (META_DEPTH-1)) != 0)
            $error("m12 META_DEPTH must be a power of two >=16");
    end
endmodule
