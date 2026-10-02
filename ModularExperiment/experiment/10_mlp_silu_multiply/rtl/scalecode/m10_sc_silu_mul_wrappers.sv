`timescale 1ns/1ps

module m10_sc_silu_mul_single (
    input wire clk,rst_n,clear,in_valid,output wire in_ready,
    input wire signed[23:0]gate_s24,up_s24,
    output wire out_valid,input wire out_ready,
    output wire signed[31:0]out_product_s32
);
    hap_mlp_silu_mul #(
        .LUT_FILE("/home/user/EDA-202/zhuowenjun/ScaleLLM/data/mlp_silu_q16.mem")
    ) u (.*);
endmodule

module m10_sc_silu_mul_x2 (
    input wire clk,rst_n,clear,input wire[1:0]in_valid,
    output wire[1:0]in_ready,input wire[47:0]gate_s24,up_s24,
    output wire[1:0]out_valid,input wire[1:0]out_ready,
    output wire[63:0]out_product_s32
);
    genvar i;
    generate for(i=0;i<2;i=i+1)begin:lanes
        hap_mlp_silu_mul #(
            .LUT_FILE("/home/user/EDA-202/zhuowenjun/ScaleLLM/data/mlp_silu_q16.mem")
        ) u (
            .clk(clk),.rst_n(rst_n),.clear(clear),
            .in_valid(in_valid[i]),.in_ready(in_ready[i]),
            .gate_s24(gate_s24[i*24+:24]),.up_s24(up_s24[i*24+:24]),
            .out_valid(out_valid[i]),.out_ready(out_ready[i]),
            .out_product_s32(out_product_s32[i*32+:32]));
    end endgenerate
endmodule
