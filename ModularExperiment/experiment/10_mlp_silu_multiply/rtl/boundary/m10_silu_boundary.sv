`timescale 1ns / 1ps

// One native-FP SwiGLU lane beginning at the common Gate/Up S24 Q8.16
// boundary.  A reservation-counted FIFO absorbs downstream stalls after the
// non-blocking fixed-to-float pipeline, so accepted input remains II=1.
module m10_fp_silu_boundary #(
    parameter integer FP_W = 16,
    parameter integer CASE_ID = 1,
    parameter integer FIFO_DEPTH = 32,
    parameter integer PTR_W = $clog2(FIFO_DEPTH)
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire signed [23:0]   gate_s24,
    input  wire signed [23:0]   up_s24,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire signed [31:0]   out_product_s32,
    output reg  [31:0]          input_count,
    output reg  [31:0]          conversion_count,
    output reg  [31:0]          core_input_count,
    output reg  [31:0]          output_count,
    output reg                  error
);
    reg [2*FP_W-1:0] pair_fifo [0:FIFO_DEPTH-1];
    reg [PTR_W-1:0] write_pointer_r;
    reg [PTR_W-1:0] read_pointer_r;
    reg [PTR_W:0] fifo_count_r;
    reg [PTR_W:0] conversion_inflight_r;
    wire [PTR_W+1:0] reserved_count =
        fifo_count_r + conversion_inflight_r;
    wire in_fire = in_valid && in_ready;

    wire gate32_valid;
    wire up32_valid;
    wire [31:0] gate_fp32;
    wire [31:0] up_fp32;
    m10_boundary_s24q16_to_fp32 u_gate_fixed (
        .aclk(clk), .s_axis_a_tvalid(in_fire), .s_axis_a_tdata(gate_s24),
        .m_axis_result_tvalid(gate32_valid),
        .m_axis_result_tdata(gate_fp32));
    m10_boundary_s24q16_to_fp32 u_up_fixed (
        .aclk(clk), .s_axis_a_tvalid(in_fire), .s_axis_a_tdata(up_s24),
        .m_axis_result_tvalid(up32_valid),
        .m_axis_result_tdata(up_fp32));

    wire converted_gate_valid;
    wire converted_up_valid;
    wire [FP_W-1:0] converted_gate;
    wire [FP_W-1:0] converted_up;
    generate
        if (FP_W == 16) begin : g_narrow
            m10_boundary_fp32_to_fp16 u_gate_narrow (
                .aclk(clk), .s_axis_a_tvalid(gate32_valid),
                .s_axis_a_tdata(gate_fp32),
                .m_axis_result_tvalid(converted_gate_valid),
                .m_axis_result_tdata(converted_gate));
            m10_boundary_fp32_to_fp16 u_up_narrow (
                .aclk(clk), .s_axis_a_tvalid(up32_valid),
                .s_axis_a_tdata(up_fp32),
                .m_axis_result_tvalid(converted_up_valid),
                .m_axis_result_tdata(converted_up));
        end else begin : g_fp32
            assign converted_gate_valid = gate32_valid;
            assign converted_up_valid = up32_valid;
            assign converted_gate = gate_fp32;
            assign converted_up = up_fp32;
        end
    endgenerate
    wire conversion_event = converted_gate_valid && converted_up_valid;

    wire core_in_ready;
    wire core_error;
    wire core_in_valid = fifo_count_r != 0;
    wire core_in_fire = core_in_valid && core_in_ready;
    wire [2*FP_W-1:0] selected_pair = pair_fifo[read_pointer_r];
    wire core_out_fire = out_valid && out_ready;
    m10_fp_silu_mul #(.W(FP_W), .CASE_ID(CASE_ID)) u_core (
        .clk(clk), .rst_n(rst_n), .clear(clear),
        .in_valid(core_in_valid), .in_ready(core_in_ready),
        .gate_fp(selected_pair[0 +: FP_W]),
        .up_fp(selected_pair[FP_W +: FP_W]),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_product_s32(out_product_s32), .error(core_error));

    assign in_ready = rst_n && !clear &&
        reserved_count < FIFO_DEPTH-2;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_pointer_r <= '0;
            read_pointer_r <= '0;
            fifo_count_r <= '0;
            conversion_inflight_r <= '0;
            input_count <= 32'd0;
            conversion_count <= 32'd0;
            core_input_count <= 32'd0;
            output_count <= 32'd0;
            error <= 1'b0;
        end else if (clear) begin
            write_pointer_r <= '0;
            read_pointer_r <= '0;
            fifo_count_r <= '0;
            conversion_inflight_r <= '0;
            input_count <= 32'd0;
            conversion_count <= 32'd0;
            core_input_count <= 32'd0;
            output_count <= 32'd0;
            error <= 1'b0;
        end else begin
            if (in_fire)
                input_count <= input_count + 1'b1;
            if (conversion_event) begin
                pair_fifo[write_pointer_r] <= {converted_up,converted_gate};
                write_pointer_r <= write_pointer_r + 1'b1;
                conversion_count <= conversion_count + 1'b1;
            end
            if (core_in_fire) begin
                read_pointer_r <= read_pointer_r + 1'b1;
                core_input_count <= core_input_count + 1'b1;
            end
            if (core_out_fire)
                output_count <= output_count + 1'b1;
            case ({conversion_event,core_in_fire})
                2'b10: fifo_count_r <= fifo_count_r + 1'b1;
                2'b01: fifo_count_r <= fifo_count_r - 1'b1;
                default: fifo_count_r <= fifo_count_r;
            endcase
            case ({in_fire,conversion_event})
                2'b10: conversion_inflight_r <= conversion_inflight_r + 1'b1;
                2'b01: conversion_inflight_r <= conversion_inflight_r - 1'b1;
                default: conversion_inflight_r <= conversion_inflight_r;
            endcase
            if (core_error || gate32_valid != up32_valid ||
                converted_gate_valid != converted_up_valid ||
                (conversion_event && conversion_inflight_r == 0) ||
                (conversion_event && fifo_count_r == FIFO_DEPTH) ||
                (core_in_fire && fifo_count_r == 0) ||
                fifo_count_r > FIFO_DEPTH ||
                conversion_inflight_r > FIFO_DEPTH)
                error <= 1'b1;
        end
    end

    initial begin
        if (FP_W != 16 && FP_W != 32)
            $error("M10 boundary FP_W must be 16 or 32");
        if ((CASE_ID == 1) != (FP_W == 16))
            $error("M10 boundary CASE_ID/FP_W mismatch");
        if (FIFO_DEPTH < 16 || (FIFO_DEPTH & (FIFO_DEPTH-1)) != 0)
            $error("M10 boundary FIFO_DEPTH must be a power of two >=16");
    end
endmodule


module m10_fp_silu_boundary_x2 #(
    parameter integer FP_W = 16,
    parameter integer CASE_ID = 1
) (
    input wire clk, rst_n, clear,
    input wire [1:0] in_valid,
    output wire [1:0] in_ready,
    input wire signed [47:0] gate_s24, up_s24,
    output wire [1:0] out_valid,
    input wire [1:0] out_ready,
    output wire signed [63:0] out_product_s32,
    output wire [63:0] input_count, conversion_count,
    core_input_count, output_count,
    output wire [1:0] error
);
    genvar lane;
    generate
        for (lane = 0; lane < 2; lane = lane + 1) begin : g_lane
            m10_fp_silu_boundary #(.FP_W(FP_W), .CASE_ID(CASE_ID)) u_lane (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid[lane]), .in_ready(in_ready[lane]),
                .gate_s24(gate_s24[lane*24 +: 24]),
                .up_s24(up_s24[lane*24 +: 24]),
                .out_valid(out_valid[lane]), .out_ready(out_ready[lane]),
                .out_product_s32(out_product_s32[lane*32 +: 32]),
                .input_count(input_count[lane*32 +: 32]),
                .conversion_count(conversion_count[lane*32 +: 32]),
                .core_input_count(core_input_count[lane*32 +: 32]),
                .output_count(output_count[lane*32 +: 32]),
                .error(error[lane]));
        end
    endgenerate
endmodule


module m10_fp16_silu_boundary_x2 (
    input wire clk, rst_n, clear,
    input wire [1:0] in_valid,
    output wire [1:0] in_ready,
    input wire signed [47:0] gate_s24, up_s24,
    output wire [1:0] out_valid,
    input wire [1:0] out_ready,
    output wire signed [63:0] out_product_s32,
    output wire [63:0] input_count, conversion_count,
    core_input_count, output_count,
    output wire [1:0] error
);
    m10_fp_silu_boundary_x2 #(.FP_W(16), .CASE_ID(1)) u_core (.*);
endmodule


module m10_fp32_silu_boundary_x2 (
    input wire clk, rst_n, clear,
    input wire [1:0] in_valid,
    output wire [1:0] in_ready,
    input wire signed [47:0] gate_s24, up_s24,
    output wire [1:0] out_valid,
    input wire [1:0] out_ready,
    output wire signed [63:0] out_product_s32,
    output wire [63:0] input_count, conversion_count,
    core_input_count, output_count,
    output wire [1:0] error
);
    m10_fp_silu_boundary_x2 #(.FP_W(32), .CASE_ID(2)) u_core (.*);
endmodule


module m10_sc_silu_boundary_x2 (
    input wire clk, rst_n, clear,
    input wire [1:0] in_valid,
    output wire [1:0] in_ready,
    input wire signed [47:0] gate_s24, up_s24,
    output wire [1:0] out_valid,
    input wire [1:0] out_ready,
    output wire signed [63:0] out_product_s32,
    output wire [63:0] input_count, conversion_count,
    core_input_count, output_count,
    output wire [1:0] error
);
    assign error = 2'b00;
    genvar lane;
    generate
        for (lane = 0; lane < 2; lane = lane + 1) begin : g_lane
            reg [31:0] input_count_r;
            reg [31:0] output_count_r;
            wire input_fire = in_valid[lane] && in_ready[lane];
            wire output_fire = out_valid[lane] && out_ready[lane];
            hap_mlp_silu_mul #(
                .LUT_FILE("/home/user/EDA-202/zhuowenjun/ScaleLLM/data/mlp_silu_q16.mem")
            ) u_lane (
                .clk(clk), .rst_n(rst_n), .clear(clear),
                .in_valid(in_valid[lane]), .in_ready(in_ready[lane]),
                .gate_s24(gate_s24[lane*24 +: 24]),
                .up_s24(up_s24[lane*24 +: 24]),
                .out_valid(out_valid[lane]), .out_ready(out_ready[lane]),
                .out_product_s32(out_product_s32[lane*32 +: 32]));
            assign input_count[lane*32 +: 32] = input_count_r;
            assign conversion_count[lane*32 +: 32] = input_count_r;
            assign core_input_count[lane*32 +: 32] = input_count_r;
            assign output_count[lane*32 +: 32] = output_count_r;
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    input_count_r <= 32'd0;
                    output_count_r <= 32'd0;
                end else if (clear) begin
                    input_count_r <= 32'd0;
                    output_count_r <= 32'd0;
                end else begin
                    if (input_fire)
                        input_count_r <= input_count_r + 1'b1;
                    if (output_fire)
                        output_count_r <= output_count_r + 1'b1;
                end
            end
        end
    endgenerate
endmodule
