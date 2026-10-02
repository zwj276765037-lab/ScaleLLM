`timescale 1ns/1ps

module m4_sc_kv_boundary_top (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  clear,
    input  wire                  in_valid,
    output wire                  in_ready,
    input  wire [4*32*24-1:0]    in_s24,
    input  wire                  in_is_v,
    input  wire [11:0]           in_base_addr,
    input  wire                  k_rd_valid,
    output wire                  k_rd_ready,
    input  wire [11:0]           k_rd_addr,
    output wire                  k_rsp_valid,
    input  wire                  k_rsp_ready,
    output wire [383:0]          k_rsp_s12,
    output wire [15:0]           k_rsp_meta,
    input  wire                  v_rd_valid,
    output wire                  v_rd_ready,
    input  wire [11:0]           v_rd_addr,
    output wire                  v_rsp_valid,
    input  wire                  v_rsp_ready,
    output wire [383:0]          v_rsp_s12,
    output wire [15:0]           v_rsp_meta,
    output wire [31:0]           input_batch_count,
    output wire [31:0]           output_group_count,
    output wire [31:0]           k_write_count,
    output wire [31:0]           v_write_count,
    output wire [31:0]           k_read_count,
    output wire [31:0]           v_read_count,
    output wire [31:0]           format_error_count,
    output wire                  error
);
    reg batch_is_v_r;
    reg [11:0] batch_base_addr_r;
    wire quant_out_valid;
    wire quant_out_ready;
    wire [1:0] quant_out_lane;
    wire quant_out_batch_last;
    wire [383:0] quant_out_s12;
    wire [15:0] quant_out_meta;
    wire quant_error;
    wire cache_wr_ready;
    wire cache_error;
    wire in_fire = in_valid && in_ready;

    always @(posedge clk)
        if (in_fire) begin
            batch_is_v_r <= in_is_v;
            batch_base_addr_r <= in_base_addr;
        end

    hap_kv12_quantizer4 u_producer (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s24(in_s24),
        .out_valid(quant_out_valid), .out_ready(quant_out_ready),
        .out_lane(quant_out_lane),
        .out_batch_last(quant_out_batch_last), .out_s12(quant_out_s12),
        .out_meta(quant_out_meta), .input_batch_count(input_batch_count),
        .output_group_count(output_group_count), .error(quant_error)
    );
    assign quant_out_ready = cache_wr_ready;

    hap_kv12_cache u_cache (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(quant_out_valid), .wr_ready(cache_wr_ready),
        .wr_is_v(batch_is_v_r),
        .wr_addr(batch_base_addr_r + quant_out_lane),
        .wr_s12(quant_out_s12), .wr_meta(quant_out_meta),
        .k_rd_valid(k_rd_valid), .k_rd_ready(k_rd_ready),
        .k_rd_addr(k_rd_addr), .k_rsp_valid(k_rsp_valid),
        .k_rsp_ready(k_rsp_ready), .k_rsp_s12(k_rsp_s12),
        .k_rsp_meta(k_rsp_meta), .v_rd_valid(v_rd_valid),
        .v_rd_ready(v_rd_ready), .v_rd_addr(v_rd_addr),
        .v_rsp_valid(v_rsp_valid), .v_rsp_ready(v_rsp_ready),
        .v_rsp_s12(v_rsp_s12), .v_rsp_meta(v_rsp_meta),
        .k_write_count(k_write_count), .v_write_count(v_write_count),
        .k_read_count(k_read_count), .v_read_count(v_read_count),
        .format_error_count(format_error_count), .error(cache_error)
    );
    assign error = quant_error | cache_error;
endmodule

module m4_fp_kv_boundary #(
    parameter integer FP_W = 16
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clear,
    input  wire                     in_valid,
    output wire                     in_ready,
    input  wire [4*32*24-1:0]       in_s24,
    input  wire                     in_is_v,
    input  wire [11:0]              in_base_addr,
    input  wire                     k_rd_valid,
    output wire                     k_rd_ready,
    input  wire [11:0]              k_rd_addr,
    output wire                     k_rsp_valid,
    input  wire                     k_rsp_ready,
    output wire [32*FP_W-1:0]       k_rsp_fp,
    input  wire                     v_rd_valid,
    output wire                     v_rd_ready,
    input  wire [11:0]              v_rd_addr,
    output wire                     v_rsp_valid,
    input  wire                     v_rsp_ready,
    output wire [32*FP_W-1:0]       v_rsp_fp,
    output wire [31:0]              input_batch_count,
    output wire [31:0]              output_group_count,
    output wire [31:0]              converted_lane_count,
    output wire [31:0]              k_write_count,
    output wire [31:0]              v_write_count,
    output wire [31:0]              k_read_count,
    output wire [31:0]              v_read_count,
    output wire [31:0]              format_error_count,
    output wire                     error
);
    reg batch_is_v_r;
    reg [11:0] batch_base_addr_r;
    wire producer_out_valid;
    wire producer_out_ready;
    wire [1:0] producer_out_lane;
    wire producer_out_batch_last;
    wire [32*FP_W-1:0] producer_out_fp;
    wire producer_error;
    wire cache_wr_ready;
    wire cache_error;
    wire in_fire = in_valid && in_ready;

    always @(posedge clk)
        if (in_fire) begin
            batch_is_v_r <= in_is_v;
            batch_base_addr_r <= in_base_addr;
        end

    m4_fp_kv_producer #(.FP_W(FP_W)) u_producer (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(in_valid), .in_ready(in_ready), .in_s24(in_s24),
        .out_valid(producer_out_valid), .out_ready(producer_out_ready),
        .out_lane(producer_out_lane),
        .out_batch_last(producer_out_batch_last),
        .out_fp(producer_out_fp), .input_batch_count(input_batch_count),
        .output_group_count(output_group_count),
        .converted_lane_count(converted_lane_count), .error(producer_error)
    );
    assign producer_out_ready = cache_wr_ready;

    m4_fp_kv_cache #(.FP_W(FP_W)) u_cache (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .wr_valid(producer_out_valid), .wr_ready(cache_wr_ready),
        .wr_is_v(batch_is_v_r),
        .wr_addr(batch_base_addr_r + producer_out_lane),
        .wr_fp(producer_out_fp), .k_rd_valid(k_rd_valid),
        .k_rd_ready(k_rd_ready), .k_rd_addr(k_rd_addr),
        .k_rsp_valid(k_rsp_valid), .k_rsp_ready(k_rsp_ready),
        .k_rsp_fp(k_rsp_fp), .v_rd_valid(v_rd_valid),
        .v_rd_ready(v_rd_ready), .v_rd_addr(v_rd_addr),
        .v_rsp_valid(v_rsp_valid), .v_rsp_ready(v_rsp_ready),
        .v_rsp_fp(v_rsp_fp), .k_write_count(k_write_count),
        .v_write_count(v_write_count), .k_read_count(k_read_count),
        .v_read_count(v_read_count),
        .format_error_count(format_error_count), .error(cache_error)
    );
    assign error = producer_error | cache_error;
endmodule

module m4_fp16_kv_boundary_top (
    input wire clk, rst_n, clear, in_valid, input wire [3071:0] in_s24,
    input wire in_is_v, input wire [11:0] in_base_addr,
    output wire in_ready, input wire k_rd_valid, input wire [11:0] k_rd_addr,
    output wire k_rd_ready, output wire k_rsp_valid, input wire k_rsp_ready,
    output wire [511:0] k_rsp_fp, input wire v_rd_valid,
    input wire [11:0] v_rd_addr, output wire v_rd_ready,
    output wire v_rsp_valid, input wire v_rsp_ready,
    output wire [511:0] v_rsp_fp, output wire [31:0] input_batch_count,
    output wire [31:0] output_group_count, converted_lane_count,
    output wire [31:0] k_write_count, v_write_count, k_read_count,
    output wire [31:0] v_read_count, format_error_count, output wire error
);
    m4_fp_kv_boundary #(.FP_W(16)) u_boundary (.*);
endmodule

module m4_fp32_kv_boundary_top (
    input wire clk, rst_n, clear, in_valid, input wire [3071:0] in_s24,
    input wire in_is_v, input wire [11:0] in_base_addr,
    output wire in_ready, input wire k_rd_valid, input wire [11:0] k_rd_addr,
    output wire k_rd_ready, output wire k_rsp_valid, input wire k_rsp_ready,
    output wire [1023:0] k_rsp_fp, input wire v_rd_valid,
    input wire [11:0] v_rd_addr, output wire v_rd_ready,
    output wire v_rsp_valid, input wire v_rsp_ready,
    output wire [1023:0] v_rsp_fp, output wire [31:0] input_batch_count,
    output wire [31:0] output_group_count, converted_lane_count,
    output wire [31:0] k_write_count, v_write_count, k_read_count,
    output wire [31:0] v_read_count, format_error_count, output wire error
);
    m4_fp_kv_boundary #(.FP_W(32)) u_boundary (.*);
endmodule
