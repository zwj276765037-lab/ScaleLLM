`timescale 1ns / 1ps

module m05_boundary_delay_bus #(
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
            $error("m05_boundary_delay_bus requires positive WIDTH/DEPTH");
    end
endmodule


// Shared 16-lane Q/K boundary converter.  A group32 is issued as low and high
// halves on consecutive clocks, so the accepted group cadence is II=2.  Both
// inputs are presented to one S28 Q12.16 fixed-to-FP32 format: Q S24 Q8.16 is
// sign extended, while K S12 integer is concatenated with sixteen zero
// fractional bits.  FP16 narrows both operands before the K scale multiply.
module m05_fp_group32_dequant16 #(
    parameter integer FP_W = 16,
    parameter integer ADDRESS_W = 9
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         clear,
    input  wire                         in_valid,
    output wire                         in_ready,
    input  wire                         in_is_key,
    input  wire [ADDRESS_W-1:0]         in_address,
    input  wire signed [32*24-1:0]      in_query_s24x32,
    input  wire signed [32*12-1:0]      in_key_s12x32,
    input  wire [FP_W-1:0]              in_key_scale_fp,
    output reg                          out_valid,
    output reg                          out_is_key,
    output reg  [ADDRESS_W-1:0]         out_address,
    output reg  [32*FP_W-1:0]           out_group_fp,
    output reg  [31:0]                  input_group_count,
    output reg  [31:0]                  output_group_count,
    output wire                         idle,
    output reg                          error
);
    localparam integer CONVERT_LAT = 6;
    localparam integer NARROW_LAT = FP_W == 16 ? 3 : 0;
    localparam integer BASE_LAT = CONVERT_LAT + NARROW_LAT;
    localparam integer MUL_LAT = FP_W == 16 ? 6 : 8;
    localparam integer META_W = FP_W + ADDRESS_W + 2;
    localparam integer HALF_W = 16*FP_W;

    reg high_pending_r;
    reg high_is_key_r;
    reg [ADDRESS_W-1:0] high_address_r;
    reg signed [32*24-1:0] high_query_r;
    reg signed [32*12-1:0] high_key_r;
    reg [FP_W-1:0] high_scale_r;
    reg [5:0] outstanding_group_count_r;
    wire in_fire = in_valid && in_ready;
    wire issue_valid = in_fire || high_pending_r;
    wire issue_high = high_pending_r;
    wire issue_is_key = high_pending_r ? high_is_key_r : in_is_key;
    wire [ADDRESS_W-1:0] issue_address = high_pending_r ?
        high_address_r : in_address;
    wire signed [32*24-1:0] issue_query = high_pending_r ?
        high_query_r : in_query_s24x32;
    wire signed [32*12-1:0] issue_key = high_pending_r ?
        high_key_r : in_key_s12x32;
    wire [FP_W-1:0] issue_scale = high_pending_r ?
        high_scale_r : in_key_scale_fp;

    assign in_ready = rst_n && !clear && !high_pending_r &&
        outstanding_group_count_r < 32;
    assign idle = !high_pending_r && outstanding_group_count_r == 0;

    wire [16*32-1:0] converted_fp32;
    wire [15:0] converted_valid;
    genvar lane;
    generate
        for (lane = 0; lane < 16; lane = lane + 1) begin : g_convert
            wire signed [23:0] query_lane = issue_query[
                (lane + (issue_high ? 16 : 0))*24 +: 24];
            wire signed [11:0] key_lane = issue_key[
                (lane + (issue_high ? 16 : 0))*12 +: 12];
            wire signed [27:0] fixed_q12_16 = issue_is_key ?
                {key_lane,16'd0} : {{4{query_lane[23]}},query_lane};
            m05_s28q16_to_fp32 u_fixed_to_fp32 (
                .aclk(clk), .s_axis_a_tvalid(issue_valid),
                .s_axis_a_tdata({{4{fixed_q12_16[27]}},fixed_q12_16}),
                .m_axis_result_tvalid(converted_valid[lane]),
                .m_axis_result_tdata(converted_fp32[lane*32 +: 32]));
        end
    endgenerate

    wire converted_all_valid = &converted_valid;
    wire converted_any_valid = |converted_valid;
    wire base_meta_valid;
    wire [META_W-1:0] base_meta;
    m05_boundary_delay_bus #(.WIDTH(META_W), .DEPTH(BASE_LAT)) u_base_meta (
        .clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(issue_valid),
        .in_data({issue_scale,issue_is_key,issue_high,issue_address}),
        .out_valid(base_meta_valid), .out_data(base_meta));

    wire [FP_W-1:0] base_scale =
        base_meta[ADDRESS_W+2 +: FP_W];
    wire base_is_key = base_meta[ADDRESS_W+1];
    wire base_high = base_meta[ADDRESS_W];
    wire [ADDRESS_W-1:0] base_address = base_meta[0 +: ADDRESS_W];
    wire [HALF_W-1:0] base_fp;
    wire [15:0] base_valid_lane;

    generate
        if (FP_W == 16) begin : g_base_fp16
            for (lane = 0; lane < 16; lane = lane + 1) begin : g_narrow
                m05_fp32_to_fp16 u_narrow (
                    .aclk(clk),
                    .s_axis_a_tvalid(converted_valid[lane]),
                    .s_axis_a_tdata(converted_fp32[lane*32 +: 32]),
                    .m_axis_result_tvalid(base_valid_lane[lane]),
                    .m_axis_result_tdata(base_fp[lane*16 +: 16]));
            end
        end else begin : g_base_fp32
            assign base_valid_lane = converted_valid;
            assign base_fp = converted_fp32;
        end
    endgenerate

    wire base_all_valid = &base_valid_lane;
    wire base_any_valid = |base_valid_lane;
    wire key_mul_issue = base_all_valid && base_meta_valid && base_is_key;
    wire [HALF_W-1:0] key_mul_fp;
    wire [15:0] key_mul_valid_lane;
    generate
        if (FP_W == 16) begin : g_key_mul_fp16
            for (lane = 0; lane < 16; lane = lane + 1) begin : g_mul
                m05_boundary_fp16_mul u_mul (
                    .aclk(clk), .s_axis_a_tvalid(key_mul_issue),
                    .s_axis_a_tdata(base_fp[lane*16 +: 16]),
                    .s_axis_b_tvalid(key_mul_issue),
                    .s_axis_b_tdata(base_scale),
                    .m_axis_result_tvalid(key_mul_valid_lane[lane]),
                    .m_axis_result_tdata(key_mul_fp[lane*16 +: 16]));
            end
        end else begin : g_key_mul_fp32
            for (lane = 0; lane < 16; lane = lane + 1) begin : g_mul
                m05_boundary_fp32_mul u_mul (
                    .aclk(clk), .s_axis_a_tvalid(key_mul_issue),
                    .s_axis_a_tdata(base_fp[lane*32 +: 32]),
                    .s_axis_b_tvalid(key_mul_issue),
                    .s_axis_b_tdata(base_scale),
                    .m_axis_result_tvalid(key_mul_valid_lane[lane]),
                    .m_axis_result_tdata(key_mul_fp[lane*32 +: 32]));
            end
        end
    endgenerate

    wire key_mul_all_valid = &key_mul_valid_lane;
    wire key_mul_any_valid = |key_mul_valid_lane;
    wire key_tag_valid;
    wire [ADDRESS_W:0] key_tag;
    m05_boundary_delay_bus #(.WIDTH(ADDRESS_W+1), .DEPTH(MUL_LAT)) u_key_tag (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(key_mul_issue), .in_data({base_high,base_address}),
        .out_valid(key_tag_valid), .out_data(key_tag));

    wire query_half_valid = base_all_valid && base_meta_valid && !base_is_key;
    wire key_half_valid = key_mul_all_valid && key_tag_valid;
    wire half_valid = query_half_valid || key_half_valid;
    wire half_is_key = key_half_valid;
    wire half_high = key_half_valid ? key_tag[ADDRESS_W] : base_high;
    wire [ADDRESS_W-1:0] half_address = key_half_valid ?
        key_tag[0 +: ADDRESS_W] : base_address;
    wire [HALF_W-1:0] half_fp = key_half_valid ? key_mul_fp : base_fp;

    reg low_pending_r;
    reg low_is_key_r;
    reg [ADDRESS_W-1:0] low_address_r;
    reg [HALF_W-1:0] low_fp_r;
    wire output_group_event = half_valid && half_high;

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            high_pending_r <= 1'b0;
            outstanding_group_count_r <= '0;
            low_pending_r <= 1'b0;
            out_valid <= 1'b0;
            input_group_count <= 32'd0;
            output_group_count <= 32'd0;
            error <= 1'b0;
        end else begin
            out_valid <= 1'b0;
            if (in_fire) begin
                high_pending_r <= 1'b1;
                high_is_key_r <= in_is_key;
                high_address_r <= in_address;
                high_query_r <= in_query_s24x32;
                high_key_r <= in_key_s12x32;
                high_scale_r <= in_key_scale_fp;
                input_group_count <= input_group_count + 1'b1;
            end else if (high_pending_r) begin
                high_pending_r <= 1'b0;
            end

            case ({in_fire,output_group_event})
                2'b10: outstanding_group_count_r <=
                    outstanding_group_count_r + 1'b1;
                2'b01: outstanding_group_count_r <=
                    outstanding_group_count_r - 1'b1;
                default: outstanding_group_count_r <=
                    outstanding_group_count_r;
            endcase

            if (half_valid) begin
                if (!half_high) begin
                    if (low_pending_r)
                        error <= 1'b1;
                    low_pending_r <= 1'b1;
                    low_is_key_r <= half_is_key;
                    low_address_r <= half_address;
                    low_fp_r <= half_fp;
                end else begin
                    if (!low_pending_r || low_is_key_r != half_is_key ||
                        low_address_r != half_address)
                        error <= 1'b1;
                    low_pending_r <= 1'b0;
                    out_valid <= 1'b1;
                    out_is_key <= half_is_key;
                    out_address <= half_address;
                    out_group_fp <= {half_fp,low_fp_r};
                    output_group_count <= output_group_count + 1'b1;
                end
            end

            if ((converted_any_valid && !converted_all_valid) ||
                (base_any_valid && !base_all_valid) ||
                (base_all_valid != base_meta_valid) ||
                (key_mul_any_valid && !key_mul_all_valid) ||
                (key_mul_all_valid != key_tag_valid) ||
                (query_half_valid && key_half_valid) ||
                (output_group_event && outstanding_group_count_r == 0))
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("m05_fp_group32_dequant16 FP_W must be 16 or 32");
        if (ADDRESS_W < 2)
            $error("m05_fp_group32_dequant16 ADDRESS_W must be >= 2");
    end
endmodule
