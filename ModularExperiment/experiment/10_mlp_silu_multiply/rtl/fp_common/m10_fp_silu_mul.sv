`timescale 1ns/1ps

// Fully pipelined operator-only FP SiLU(gate)*up baseline.  Xilinx FP IPs use
// non-blocking flow control and preserve transaction order.  Small ordering
// FIFOs align gate/up side data without relying on undocumented IP latency;
// the output FIFO and pending-credit rule preserve ready/valid backpressure.
module m10_fp_silu_mul #(
    parameter integer W = 32,
    parameter integer CASE_ID = 2,
    parameter integer FIFO_DEPTH = 128,
    parameter integer CREDIT_LIMIT = 112
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 in_valid,
    output wire                 in_ready,
    input  wire [W-1:0]         gate_fp,
    input  wire [W-1:0]         up_fp,
    output wire                 out_valid,
    input  wire                 out_ready,
    output wire signed [31:0]   out_product_s32,
    output reg                  error
);
    reg [W-1:0] gate_fifo [0:FIFO_DEPTH-1];
    reg [W-1:0] up_fifo [0:FIFO_DEPTH-1];
    reg [31:0] result_fifo [0:FIFO_DEPTH-1];
    reg [6:0] gate_write_pointer, gate_read_pointer;
    reg [6:0] up_write_pointer, up_read_pointer;
    reg [6:0] result_write_pointer, result_read_pointer;
    reg [7:0] pending_count;
    reg [7:0] result_count;
    reg [7:0] pipeline_token_count;

    wire input_fire = in_valid && in_ready;
    assign in_ready = rst_n && !clear && (pending_count < CREDIT_LIMIT);
    assign out_valid = rst_n && !clear && (result_count != 0);
    assign out_product_s32 = result_fifo[result_read_pointer];
    wire output_fire = out_valid && out_ready;
    wire [W-1:0] negative_gate = {~gate_fp[W-1],gate_fp[W-2:0]};
    wire [W-1:0] one = CASE_ID == 1 ? W'(16'h3c00) : W'(32'h3f800000);

    wire exp_valid, add_valid, div_valid, mul_valid, product_f32_valid, fixed_valid;
    wire [W-1:0] exp_value, denominator, silu_value, product_value;
    wire [31:0] product_f32;
    wire [31:0] fixed_value;

    generate
        if (CASE_ID == 1) begin : fp16_path
            m10_f16_exp exp_ip (
                .aclk(clk), .s_axis_a_tvalid(input_fire),
                .s_axis_a_tdata(negative_gate),
                .m_axis_result_tvalid(exp_valid),
                .m_axis_result_tdata(exp_value));
            m10_f16_add add_ip (
                .aclk(clk), .s_axis_a_tvalid(exp_valid),
                .s_axis_a_tdata(exp_value),
                .s_axis_b_tvalid(exp_valid), .s_axis_b_tdata(one),
                .m_axis_result_tvalid(add_valid),
                .m_axis_result_tdata(denominator));
            m10_f16_div div_ip (
                .aclk(clk), .s_axis_a_tvalid(add_valid),
                .s_axis_a_tdata(gate_fifo[gate_read_pointer]),
                .s_axis_b_tvalid(add_valid), .s_axis_b_tdata(denominator),
                .m_axis_result_tvalid(div_valid),
                .m_axis_result_tdata(silu_value));
            m10_f16_mul mul_ip (
                .aclk(clk), .s_axis_a_tvalid(div_valid),
                .s_axis_a_tdata(silu_value),
                .s_axis_b_tvalid(div_valid),
                .s_axis_b_tdata(up_fifo[up_read_pointer]),
                .m_axis_result_tvalid(mul_valid),
                .m_axis_result_tdata(product_value));
            m10_f16_to_f32 widen_ip (
                .aclk(clk), .s_axis_a_tvalid(mul_valid),
                .s_axis_a_tdata(product_value),
                .m_axis_result_tvalid(product_f32_valid),
                .m_axis_result_tdata(product_f32));
        end else begin : fp32_path
            m10_f32_exp exp_ip (
                .aclk(clk), .s_axis_a_tvalid(input_fire),
                .s_axis_a_tdata(negative_gate),
                .m_axis_result_tvalid(exp_valid),
                .m_axis_result_tdata(exp_value));
            m10_f32_add add_ip (
                .aclk(clk), .s_axis_a_tvalid(exp_valid),
                .s_axis_a_tdata(exp_value),
                .s_axis_b_tvalid(exp_valid), .s_axis_b_tdata(one),
                .m_axis_result_tvalid(add_valid),
                .m_axis_result_tdata(denominator));
            m10_f32_div div_ip (
                .aclk(clk), .s_axis_a_tvalid(add_valid),
                .s_axis_a_tdata(gate_fifo[gate_read_pointer]),
                .s_axis_b_tvalid(add_valid), .s_axis_b_tdata(denominator),
                .m_axis_result_tvalid(div_valid),
                .m_axis_result_tdata(silu_value));
            m10_f32_mul mul_ip (
                .aclk(clk), .s_axis_a_tvalid(div_valid),
                .s_axis_a_tdata(silu_value),
                .s_axis_b_tvalid(div_valid),
                .s_axis_b_tdata(up_fifo[up_read_pointer]),
                .m_axis_result_tvalid(mul_valid),
                .m_axis_result_tdata(product_value));
            assign product_f32_valid = mul_valid;
            assign product_f32 = product_value;
        end
    endgenerate

    m10_f32_to_s32 fixed_ip (
        .aclk(clk), .s_axis_a_tvalid(product_f32_valid),
        .s_axis_a_tdata(product_f32),
        .m_axis_result_tvalid(fixed_valid),
        .m_axis_result_tdata(fixed_value));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gate_write_pointer <= 0;
            gate_read_pointer <= 0;
            up_write_pointer <= 0;
            up_read_pointer <= 0;
            result_write_pointer <= 0;
            result_read_pointer <= 0;
            pending_count <= 0;
            result_count <= 0;
            pipeline_token_count <= 0;
            error <= 1'b0;
        end else if (clear) begin
            gate_write_pointer <= 0;
            gate_read_pointer <= 0;
            up_write_pointer <= 0;
            up_read_pointer <= 0;
            result_write_pointer <= 0;
            result_read_pointer <= 0;
            pending_count <= 0;
            result_count <= 0;
            pipeline_token_count <= 0;
            error <= 1'b0;
        end else begin
            if (input_fire) begin
                gate_fifo[gate_write_pointer] <= gate_fp;
                up_fifo[up_write_pointer] <= up_fp;
                gate_write_pointer <= gate_write_pointer + 1'b1;
                up_write_pointer <= up_write_pointer + 1'b1;
            end
            if (add_valid)
                gate_read_pointer <= gate_read_pointer + 1'b1;
            if (div_valid)
                up_read_pointer <= up_read_pointer + 1'b1;
            if (fixed_valid && (pipeline_token_count != 0)) begin
                result_fifo[result_write_pointer] <= fixed_value;
                result_write_pointer <= result_write_pointer + 1'b1;
            end else if (fixed_valid) begin
                error <= 1'b1;
            end
            if (output_fire)
                result_read_pointer <= result_read_pointer + 1'b1;

            case ({input_fire,output_fire})
                2'b10: pending_count <= pending_count + 1'b1;
                2'b01: pending_count <= pending_count - 1'b1;
                default: pending_count <= pending_count;
            endcase
            case ({fixed_valid && (pipeline_token_count != 0),output_fire})
                2'b10: result_count <= result_count + 1'b1;
                2'b01: result_count <= result_count - 1'b1;
                default: result_count <= result_count;
            endcase
            case ({input_fire,fixed_valid && (pipeline_token_count != 0)})
                2'b10: pipeline_token_count <= pipeline_token_count + 1'b1;
                2'b01: pipeline_token_count <= pipeline_token_count - 1'b1;
                default: pipeline_token_count <= pipeline_token_count;
            endcase
            if ((result_count >= FIFO_DEPTH-1) ||
                (pipeline_token_count >= FIFO_DEPTH-1))
                error <= 1'b1;
        end
    end
endmodule

module m10_fp16_silu_mul (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire[15:0]gate_fp,up_fp,output wire out_valid,input wire out_ready,
    output wire signed[31:0]out_product_s32,output wire error
);
    m10_fp_silu_mul #(.W(16),.CASE_ID(1)) u (.*);
endmodule

module m10_fp32_silu_mul (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire[31:0]gate_fp,up_fp,output wire out_valid,input wire out_ready,
    output wire signed[31:0]out_product_s32,output wire error
);
    m10_fp_silu_mul #(.W(32),.CASE_ID(2)) u (.*);
endmodule

module m10_fp16_silu_mul_x2 (
    input wire clk,rst_n,clear,input wire[1:0]in_valid,
    output wire[1:0]in_ready,input wire[31:0]gate_fp,up_fp,
    output wire[1:0]out_valid,input wire[1:0]out_ready,
    output wire[63:0]out_product_s32,output wire[1:0]error
);
    genvar i; generate for(i=0;i<2;i=i+1)begin:lanes
        m10_fp16_silu_mul u(.clk(clk),.rst_n(rst_n),.clear(clear),
            .in_valid(in_valid[i]),.in_ready(in_ready[i]),
            .gate_fp(gate_fp[i*16+:16]),.up_fp(up_fp[i*16+:16]),
            .out_valid(out_valid[i]),.out_ready(out_ready[i]),
            .out_product_s32(out_product_s32[i*32+:32]),.error(error[i]));
    end endgenerate
endmodule

module m10_fp32_silu_mul_x2 (
    input wire clk,rst_n,clear,input wire[1:0]in_valid,
    output wire[1:0]in_ready,input wire[63:0]gate_fp,up_fp,
    output wire[1:0]out_valid,input wire[1:0]out_ready,
    output wire[63:0]out_product_s32,output wire[1:0]error
);
    genvar i; generate for(i=0;i<2;i=i+1)begin:lanes
        m10_fp32_silu_mul u(.clk(clk),.rst_n(rst_n),.clear(clear),
            .in_valid(in_valid[i]),.in_ready(in_ready[i]),
            .gate_fp(gate_fp[i*32+:32]),.up_fp(up_fp[i*32+:32]),
            .out_valid(out_valid[i]),.out_ready(out_ready[i]),
            .out_product_s32(out_product_s32[i*32+:32]),.error(error[i]));
    end endgenerate
endmodule
