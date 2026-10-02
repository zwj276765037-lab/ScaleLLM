`timescale 1ns / 1ps

// Fixed-latency sideband pipeline used beside nonblocking Floating-Point IP.
module m09_delay_bus #(
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
        if (!rst_n || clear) begin
            valid_r <= '0;
        end else begin
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
            $error("m09_delay_bus requires positive WIDTH and DEPTH");
    end
endmodule


// Boundary-inclusive native-FP A8W4 pair lane.
//
// The integer producer is the production packed two-column group32 dot.
// Unlike a fixed-point shortcut, each dot is then converted to FP, multiplied
// by activation and weight scales in FP, and accumulated for all 128 groups by
// a real AMD Floating-Point accumulator with input rate one.  TLAST closes a
// tile.  Only the completed FP sum is converted to the common S24 Q8.16 output.
module m09_fp_a8w4_lane2_accum #(
    parameter integer FP_W = 16,
    parameter integer GROUPS = 128,
    parameter integer META_DEPTH = 32,
    parameter integer RESULT_DEPTH = 2
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     in_valid,
    output wire                     in_ready,
    input  wire                     in_first_group,
    input  wire                     in_last_group,
    input  wire signed [32*9-1:0]  activation_s9x32,
    input  wire signed [32*4-1:0]  weight0_s4x32,
    input  wire signed [32*4-1:0]  weight1_s4x32,
    input  wire [FP_W-1:0]          activation_scale_fp,
    input  wire [FP_W-1:0]          weight0_scale_fp,
    input  wire [FP_W-1:0]          weight1_scale_fp,
    output wire                     out_valid,
    input  wire                     out_ready,
    output wire signed [23:0]       out0_s24,
    output wire signed [23:0]       out1_s24,
    output reg  [31:0]              input_group_count,
    output reg  [31:0]              output_tile_count,
    output reg                      error
);
    localparam integer META_PTR_W = $clog2(META_DEPTH);
    localparam integer META_COUNT_W = $clog2(META_DEPTH+1);
    localparam integer META_W = 3*FP_W + 2;
    localparam integer GROUP_W = $clog2(GROUPS);

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

    reg signed [23:0] result0_mem [0:RESULT_DEPTH-1];
    reg signed [23:0] result1_mem [0:RESULT_DEPTH-1];
    reg result_wr_ptr_r;
    reg result_rd_ptr_r;
    reg [1:0] result_count_r;
    reg [1:0] outstanding_tiles_r;
    reg [GROUP_W-1:0] group_index_r;
    reg [GROUP_W-1:0] dot_group_index_r;

    wire out_fire = out_valid && out_ready;
    wire tile_credit = outstanding_tiles_r < RESULT_DEPTH || out_fire;
    wire in_fire = in_valid && in_ready;
    wire dot_fire = dot_out_valid && dot_out_ready;
    wire result_full = result_count_r == RESULT_DEPTH;
    wire result_empty = result_count_r == 0;

    assign in_ready = rst_n && !clear && dot_in_ready && !meta_full &&
        (!in_first_group || tile_credit);
    assign dot_out_ready = !meta_empty;
    assign out_valid = rst_n && !clear && !result_empty;
    assign out0_s24 = result0_mem[result_rd_ptr_r];
    assign out1_s24 = result1_mem[result_rd_ptr_r];

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
    wire dot_first = dot_meta[3*FP_W];
    wire dot_last = dot_meta[3*FP_W+1];

    wire fixed0_valid;
    wire fixed1_valid;
    wire [23:0] fixed0_s24;
    wire [23:0] fixed1_s24;
    wire result_push = fixed0_valid && fixed1_valid;

    generate
        if (FP_W == 32) begin : g_fp32
            localparam integer INT_LAT = 6;
            localparam integer MUL_LAT = 8;
            wire int0_valid;
            wire int1_valid;
            wire [31:0] int0_fp32;
            wire [31:0] int1_fp32;
            wire int_meta_valid;
            wire [3*32:0] int_meta;
            wire mul0a_valid;
            wire mul1a_valid;
            wire [31:0] mul0a_fp32;
            wire [31:0] mul1a_fp32;
            wire weight_meta_valid;
            wire [64:0] weight_meta;
            wire mul0b_valid;
            wire mul1b_valid;
            wire [31:0] mul0b_fp32;
            wire [31:0] mul1b_fp32;
            wire last_valid;
            wire last_data;
            wire accum0_valid;
            wire accum1_valid;
            wire accum0_last;
            wire accum1_last;
            wire [31:0] accum0_fp32;
            wire [31:0] accum1_fp32;

            m09_int17_to_fp32 u_i0 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot0_s17[16]}},dot0_s17}),
                .m_axis_result_tvalid(int0_valid),
                .m_axis_result_tdata(int0_fp32));
            m09_int17_to_fp32 u_i1 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot1_s17[16]}},dot1_s17}),
                .m_axis_result_tvalid(int1_valid),
                .m_axis_result_tdata(int1_fp32));
            m09_delay_bus #(.WIDTH(97), .DEPTH(INT_LAT)) u_int_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(dot_fire),
                .in_data({dot_last,dot_weight1_scale,dot_weight0_scale,
                    dot_act_scale}),
                .out_valid(int_meta_valid), .out_data(int_meta));

            m09_fp32_mul u_m0a (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .s_axis_b_tvalid(int_meta_valid),
                .s_axis_b_tdata(int_meta[0 +: 32]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp32));
            m09_fp32_mul u_m1a (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .s_axis_b_tvalid(int_meta_valid),
                .s_axis_b_tdata(int_meta[0 +: 32]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp32));
            m09_delay_bus #(.WIDTH(65), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(int_meta_valid),
                .in_data({int_meta[96],int_meta[64 +: 32],
                    int_meta[32 +: 32]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));

            m09_fp32_mul u_m0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 32]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(mul0b_fp32));
            m09_fp32_mul u_m1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp32),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[32 +: 32]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(mul1b_fp32));
            m09_delay_bus #(.WIDTH(1), .DEPTH(MUL_LAT)) u_last (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(weight_meta_valid), .in_data(weight_meta[64]),
                .out_valid(last_valid), .out_data(last_data));

            m09_fp32_acc u_a0 (
                .aclk(clk), .aresetn(rst_n && !clear),
                .s_axis_a_tvalid(mul0b_valid),
                .s_axis_a_tdata(mul0b_fp32),
                .s_axis_a_tlast(last_valid && last_data),
                .s_axis_operation_tvalid(mul0b_valid),
                .s_axis_operation_tdata(8'h00),
                .m_axis_result_tvalid(accum0_valid),
                .m_axis_result_tdata(accum0_fp32),
                .m_axis_result_tlast(accum0_last));
            m09_fp32_acc u_a1 (
                .aclk(clk), .aresetn(rst_n && !clear),
                .s_axis_a_tvalid(mul1b_valid),
                .s_axis_a_tdata(mul1b_fp32),
                .s_axis_a_tlast(last_valid && last_data),
                .s_axis_operation_tvalid(mul1b_valid),
                .s_axis_operation_tdata(8'h00),
                .m_axis_result_tvalid(accum1_valid),
                .m_axis_result_tdata(accum1_fp32),
                .m_axis_result_tlast(accum1_last));
            m09_fp32_to_s24 u_o0 (
                .aclk(clk),
                .s_axis_a_tvalid(accum0_valid && accum0_last),
                .s_axis_a_tdata(accum0_fp32),
                .m_axis_result_tvalid(fixed0_valid),
                .m_axis_result_tdata(fixed0_s24));
            m09_fp32_to_s24 u_o1 (
                .aclk(clk),
                .s_axis_a_tvalid(accum1_valid && accum1_last),
                .s_axis_a_tdata(accum1_fp32),
                .m_axis_result_tvalid(fixed1_valid),
                .m_axis_result_tdata(fixed1_s24));
        end else begin : g_fp16
            localparam integer INT_LAT = 6;
            localparam integer NARROW_LAT = 3;
            localparam integer MUL_LAT = 6;
            wire int0_valid;
            wire int1_valid;
            wire [31:0] int0_fp32;
            wire [31:0] int1_fp32;
            wire int_meta_valid;
            wire [48:0] int_meta;
            wire narrow0_valid;
            wire narrow1_valid;
            wire [15:0] narrow0_fp16;
            wire [15:0] narrow1_fp16;
            wire narrow_meta_valid;
            wire [48:0] narrow_meta;
            wire mul0a_valid;
            wire mul1a_valid;
            wire [15:0] mul0a_fp16;
            wire [15:0] mul1a_fp16;
            wire weight_meta_valid;
            wire [32:0] weight_meta;
            wire mul0b_valid;
            wire mul1b_valid;
            wire [15:0] mul0b_fp16;
            wire [15:0] mul1b_fp16;
            wire last_valid;
            wire last_data;
            wire accum0_valid;
            wire accum1_valid;
            wire accum0_last;
            wire accum1_last;
            wire [15:0] accum0_fp16;
            wire [15:0] accum1_fp16;
            wire wide0_valid;
            wire wide1_valid;
            wire [31:0] wide0_fp32;
            wire [31:0] wide1_fp32;

            m09_int17_to_fp32 u_i0 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot0_s17[16]}},dot0_s17}),
                .m_axis_result_tvalid(int0_valid),
                .m_axis_result_tdata(int0_fp32));
            m09_int17_to_fp32 u_i1 (
                .aclk(clk), .s_axis_a_tvalid(dot_fire),
                .s_axis_a_tdata({{7{dot1_s17[16]}},dot1_s17}),
                .m_axis_result_tvalid(int1_valid),
                .m_axis_result_tdata(int1_fp32));
            m09_delay_bus #(.WIDTH(49), .DEPTH(INT_LAT)) u_int_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(dot_fire),
                .in_data({dot_last,dot_weight1_scale,dot_weight0_scale,
                    dot_act_scale}),
                .out_valid(int_meta_valid), .out_data(int_meta));
            m09_fp32_to_fp16 u_n0 (
                .aclk(clk), .s_axis_a_tvalid(int0_valid),
                .s_axis_a_tdata(int0_fp32),
                .m_axis_result_tvalid(narrow0_valid),
                .m_axis_result_tdata(narrow0_fp16));
            m09_fp32_to_fp16 u_n1 (
                .aclk(clk), .s_axis_a_tvalid(int1_valid),
                .s_axis_a_tdata(int1_fp32),
                .m_axis_result_tvalid(narrow1_valid),
                .m_axis_result_tdata(narrow1_fp16));
            m09_delay_bus #(.WIDTH(49), .DEPTH(NARROW_LAT)) u_narrow_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(int_meta_valid), .in_data(int_meta),
                .out_valid(narrow_meta_valid), .out_data(narrow_meta));

            m09_fp16_mul u_m0a (
                .aclk(clk), .s_axis_a_tvalid(narrow0_valid),
                .s_axis_a_tdata(narrow0_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0a_valid),
                .m_axis_result_tdata(mul0a_fp16));
            m09_fp16_mul u_m1a (
                .aclk(clk), .s_axis_a_tvalid(narrow1_valid),
                .s_axis_a_tdata(narrow1_fp16),
                .s_axis_b_tvalid(narrow_meta_valid),
                .s_axis_b_tdata(narrow_meta[0 +: 16]),
                .m_axis_result_tvalid(mul1a_valid),
                .m_axis_result_tdata(mul1a_fp16));
            m09_delay_bus #(.WIDTH(33), .DEPTH(MUL_LAT)) u_weight_meta (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(narrow_meta_valid),
                .in_data({narrow_meta[48],narrow_meta[32 +: 16],
                    narrow_meta[16 +: 16]}),
                .out_valid(weight_meta_valid), .out_data(weight_meta));
            m09_fp16_mul u_m0b (
                .aclk(clk), .s_axis_a_tvalid(mul0a_valid),
                .s_axis_a_tdata(mul0a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[0 +: 16]),
                .m_axis_result_tvalid(mul0b_valid),
                .m_axis_result_tdata(mul0b_fp16));
            m09_fp16_mul u_m1b (
                .aclk(clk), .s_axis_a_tvalid(mul1a_valid),
                .s_axis_a_tdata(mul1a_fp16),
                .s_axis_b_tvalid(weight_meta_valid),
                .s_axis_b_tdata(weight_meta[16 +: 16]),
                .m_axis_result_tvalid(mul1b_valid),
                .m_axis_result_tdata(mul1b_fp16));
            m09_delay_bus #(.WIDTH(1), .DEPTH(MUL_LAT)) u_last (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(weight_meta_valid), .in_data(weight_meta[32]),
                .out_valid(last_valid), .out_data(last_data));

            m09_fp16_acc u_a0 (
                .aclk(clk), .aresetn(rst_n && !clear),
                .s_axis_a_tvalid(mul0b_valid),
                .s_axis_a_tdata(mul0b_fp16),
                .s_axis_a_tlast(last_valid && last_data),
                .s_axis_operation_tvalid(mul0b_valid),
                .s_axis_operation_tdata(8'h00),
                .m_axis_result_tvalid(accum0_valid),
                .m_axis_result_tdata(accum0_fp16),
                .m_axis_result_tlast(accum0_last));
            m09_fp16_acc u_a1 (
                .aclk(clk), .aresetn(rst_n && !clear),
                .s_axis_a_tvalid(mul1b_valid),
                .s_axis_a_tdata(mul1b_fp16),
                .s_axis_a_tlast(last_valid && last_data),
                .s_axis_operation_tvalid(mul1b_valid),
                .s_axis_operation_tdata(8'h00),
                .m_axis_result_tvalid(accum1_valid),
                .m_axis_result_tdata(accum1_fp16),
                .m_axis_result_tlast(accum1_last));
            m09_fp16_to_fp32 u_w0 (
                .aclk(clk),
                .s_axis_a_tvalid(accum0_valid && accum0_last),
                .s_axis_a_tdata(accum0_fp16),
                .m_axis_result_tvalid(wide0_valid),
                .m_axis_result_tdata(wide0_fp32));
            m09_fp16_to_fp32 u_w1 (
                .aclk(clk),
                .s_axis_a_tvalid(accum1_valid && accum1_last),
                .s_axis_a_tdata(accum1_fp16),
                .m_axis_result_tvalid(wide1_valid),
                .m_axis_result_tdata(wide1_fp32));
            m09_fp32_to_s24 u_o0 (
                .aclk(clk), .s_axis_a_tvalid(wide0_valid),
                .s_axis_a_tdata(wide0_fp32),
                .m_axis_result_tvalid(fixed0_valid),
                .m_axis_result_tdata(fixed0_s24));
            m09_fp32_to_s24 u_o1 (
                .aclk(clk), .s_axis_a_tvalid(wide1_valid),
                .s_axis_a_tdata(wide1_fp32),
                .m_axis_result_tvalid(fixed1_valid),
                .m_axis_result_tdata(fixed1_s24));
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            meta_wr_ptr_r <= '0;
            meta_rd_ptr_r <= '0;
            meta_count_r <= '0;
            result_wr_ptr_r <= 1'b0;
            result_rd_ptr_r <= 1'b0;
            result_count_r <= '0;
            outstanding_tiles_r <= '0;
            group_index_r <= '0;
            dot_group_index_r <= '0;
            input_group_count <= 32'd0;
            output_tile_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire) begin
                meta_mem[meta_wr_ptr_r] <= {in_last_group,in_first_group,
                    weight1_scale_fp,weight0_scale_fp,activation_scale_fp};
                meta_wr_ptr_r <= meta_wr_ptr_r + 1'b1;
                input_group_count <= input_group_count + 1'b1;
                if (in_first_group != (group_index_r == 0) ||
                    in_last_group != (group_index_r == GROUPS-1))
                    error <= 1'b1;
                if (in_last_group)
                    group_index_r <= '0;
                else
                    group_index_r <= group_index_r + 1'b1;
            end
            if (dot_fire) begin
                meta_rd_ptr_r <= meta_rd_ptr_r + 1'b1;
                if (dot_first != (dot_group_index_r == 0) ||
                    dot_last != (dot_group_index_r == GROUPS-1))
                    error <= 1'b1;
                if (dot_last)
                    dot_group_index_r <= '0;
                else
                    dot_group_index_r <= dot_group_index_r + 1'b1;
            end
            case ({in_fire,dot_fire})
                2'b10: meta_count_r <= meta_count_r + 1'b1;
                2'b01: meta_count_r <= meta_count_r - 1'b1;
                default: meta_count_r <= meta_count_r;
            endcase

            if (result_push) begin
                result0_mem[result_wr_ptr_r] <= fixed0_s24;
                result1_mem[result_wr_ptr_r] <= fixed1_s24;
                result_wr_ptr_r <= result_wr_ptr_r + 1'b1;
            end
            if (out_fire) begin
                result_rd_ptr_r <= result_rd_ptr_r + 1'b1;
                output_tile_count <= output_tile_count + 1'b1;
            end
            case ({result_push,out_fire})
                2'b10: result_count_r <= result_count_r + 1'b1;
                2'b01: result_count_r <= result_count_r - 1'b1;
                default: result_count_r <= result_count_r;
            endcase
            case ({in_fire && in_first_group,out_fire})
                2'b10: outstanding_tiles_r <= outstanding_tiles_r + 1'b1;
                2'b01: outstanding_tiles_r <= outstanding_tiles_r - 1'b1;
                default: outstanding_tiles_r <= outstanding_tiles_r;
            endcase

            if (result_push && result_full && !out_fire)
                error <= 1'b1;
            if (fixed0_valid != fixed1_valid)
                error <= 1'b1;
            if (meta_count_r > META_DEPTH ||
                outstanding_tiles_r > RESULT_DEPTH ||
                result_count_r > RESULT_DEPTH)
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m09_fp_a8w4_lane2_accum FP_W must be 16 or 32");
        if (GROUPS != 128)
            $error("m09 FP gate/up lane freezes GROUPS=128");
        if (META_DEPTH < 16 || (META_DEPTH & (META_DEPTH-1)) != 0)
            $error("m09 META_DEPTH must be a power of two >=16");
        if (RESULT_DEPTH != 2)
            $error("m09 result queue is frozen at depth two");
    end
endmodule
