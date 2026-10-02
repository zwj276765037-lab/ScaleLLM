`timescale 1ns / 1ps

module m3_fp32_scale_lane(
    input wire clk,rst_n,clear,in_valid,
    output wire in_ready,
    input wire [255:0] in_act_u8,in_wgt_s8,
    input wire [7:0] in_act_zero_point,
    input wire [31:0] in_act_scale_fp32,in_wgt_scale_fp32,
    output wire out_valid,input wire out_ready,
    output wire signed [41:0] out_guard_s42,
    output reg [31:0] input_group_count,
    output wire [31:0] output_group_count,
    output wire error
);
    reg [4:0] used;
    wire corr_valid; wire signed [20:0] corr; wire [63:0] meta;
    wire int_v,scale_v,final_v,fixed_v; wire [31:0] int_d,scale_d,final_d;
    wire [47:0] fixed_d; reg [1:0] int_delay_v; reg [31:0] int_delay_d[0:1];
    wire fifo_full,fifo_error,in_fire,out_fire;
    assign in_fire=in_valid&&in_ready;
    assign out_fire=out_valid&&out_ready;
    m3_precenter_mac_group32 #(.META_W(64)) mac(
      .clk(clk),.rst_n(rst_n),.clear(clear),.allow_input(used<16),
      .in_valid(in_valid),.in_ready(in_ready),.in_act_u8(in_act_u8),
      .in_wgt_s8(in_wgt_s8),.in_zero_point(in_act_zero_point),
      .in_meta({in_wgt_scale_fp32,in_act_scale_fp32}),
      .out_valid(corr_valid),.out_corr_s21(corr),.out_meta(meta));
    m3_int21_to_fp32 c0(.aclk(clk),.s_axis_a_tvalid(corr_valid),
      .s_axis_a_tdata({{3{corr[20]}},corr}),.m_axis_result_tvalid(int_v),.m_axis_result_tdata(int_d));
    m3_fp32_mul c1(.aclk(clk),.s_axis_a_tvalid(corr_valid),
      .s_axis_a_tdata(meta[31:0]),.s_axis_b_tvalid(corr_valid),
      .s_axis_b_tdata(meta[63:32]),.m_axis_result_tvalid(scale_v),
      .m_axis_result_tdata(scale_d));
    always @(posedge clk or negedge rst_n) begin
      if(!rst_n) int_delay_v<=0;
      else if(clear) int_delay_v<=0;
      else begin int_delay_v<={int_delay_v[0],int_v};
        int_delay_d[0]<=int_d;int_delay_d[1]<=int_delay_d[0];end
    end
    m3_fp32_mul c2(.aclk(clk),.s_axis_a_tvalid(int_delay_v[1]),
      .s_axis_a_tdata(int_delay_d[1]),.s_axis_b_tvalid(scale_v),
      .s_axis_b_tdata(scale_d),.m_axis_result_tvalid(final_v),
      .m_axis_result_tdata(final_d));
    m3_fp32_to_s42 c3(.aclk(clk),.s_axis_a_tvalid(final_v),
      .s_axis_a_tdata(final_d),.m_axis_result_tvalid(fixed_v),
      .m_axis_result_tdata(fixed_d));
    m3_s42_fifo fifo(.clk(clk),.rst_n(rst_n),.clear(clear),.push(fixed_v),
      .push_data(fixed_d[41:0]),.full(fifo_full),.out_valid(out_valid),.out_ready(out_ready),
      .out_data(out_guard_s42),.output_count(output_group_count),.error(fifo_error));
    assign error=fifo_error;
    always @(posedge clk or negedge rst_n) begin
      if(!rst_n)begin used<=0;input_group_count<=0;end
      else if(clear)begin used<=0;input_group_count<=0;end
      else begin if(in_fire)input_group_count<=input_group_count+1;
        case({in_fire,out_fire})2'b10:used<=used+1;2'b01:used<=used-1;default:used<=used;endcase end
    end
endmodule

module m3_fp16_scale_lane(
    input wire clk,rst_n,clear,in_valid,
    output wire in_ready,
    input wire [255:0] in_act_u8,in_wgt_s8,
    input wire [7:0] in_act_zero_point,
    input wire [15:0] in_act_scale_fp16,in_wgt_scale_fp16,
    output wire out_valid,input wire out_ready,
    output wire signed [41:0] out_guard_s42,
    output reg [31:0] input_group_count,
    output wire [31:0] output_group_count,
    output wire error
);
    // The FP16 boundary has a longer conversion/multiply pipeline than the
    // original 16-credit output queue can cover at the common MAC II=2.
    // Thirty-two credits preserve the single-core II=2 contract while still
    // bounding every in-flight result under downstream backpressure.
    reg [5:0] used;
    wire corr_valid;wire signed[20:0]corr;wire[31:0]meta;
    wire c32v,c16v,actv,finalv,backv,fixedv;
    wire[31:0]c32d,backd;wire[15:0]c16d,actd,finald;wire[47:0]fixedd;
    reg[8:0]meta_delay_v;reg[31:0]meta_delay_d[0:8];
    reg[5:0]weight_delay_v;reg[15:0]weight_delay_d[0:5];
    wire fifo_full,fifo_error,in_fire,out_fire;
    assign in_fire=in_valid&&in_ready;
    assign out_fire=out_valid&&out_ready;
    m3_precenter_mac_group32 #(.META_W(32)) mac(
      .clk(clk),.rst_n(rst_n),.clear(clear),.allow_input(used<32),
      .in_valid(in_valid),.in_ready(in_ready),.in_act_u8(in_act_u8),
      .in_wgt_s8(in_wgt_s8),.in_zero_point(in_act_zero_point),
      .in_meta({in_wgt_scale_fp16,in_act_scale_fp16}),
      .out_valid(corr_valid),.out_corr_s21(corr),.out_meta(meta));
    m3_int21_to_fp32 c0(.aclk(clk),.s_axis_a_tvalid(corr_valid),
      .s_axis_a_tdata({{3{corr[20]}},corr}),
      .m_axis_result_tvalid(c32v),.m_axis_result_tdata(c32d));
    m3_fp32_to_fp16 c1(.aclk(clk),.s_axis_a_tvalid(c32v),.s_axis_a_tdata(c32d),
      .m_axis_result_tvalid(c16v),.m_axis_result_tdata(c16d));
    integer di;always @(posedge clk or negedge rst_n)begin
      if(!rst_n)begin meta_delay_v<=0;weight_delay_v<=0;end
      else if(clear)begin meta_delay_v<=0;weight_delay_v<=0;end
      else begin
        meta_delay_v<={meta_delay_v[7:0],corr_valid};meta_delay_d[0]<=meta;
        for(di=1;di<9;di=di+1)meta_delay_d[di]<=meta_delay_d[di-1];
        // Carry the weight scale alongside the first FP16 multiply.  Using
        // actv here delays the validity by the multiplier latency a second
        // time and only appears aligned while the stream has no bubbles.
        weight_delay_v<={weight_delay_v[4:0],(c16v&&meta_delay_v[8])};
        weight_delay_d[0]<=meta_delay_d[8][31:16];
        for(di=1;di<6;di=di+1)weight_delay_d[di]<=weight_delay_d[di-1];
      end
    end
    m3_fp16_mul c2(.aclk(clk),.s_axis_a_tvalid(c16v&&meta_delay_v[8]),
      .s_axis_a_tdata(c16d),.s_axis_b_tvalid(c16v&&meta_delay_v[8]),
      .s_axis_b_tdata(meta_delay_d[8][15:0]),
      .m_axis_result_tvalid(actv),.m_axis_result_tdata(actd));
    m3_fp16_mul c3(.aclk(clk),.s_axis_a_tvalid(actv),.s_axis_a_tdata(actd),
      .s_axis_b_tvalid(weight_delay_v[5]),.s_axis_b_tdata(weight_delay_d[5]),
      .m_axis_result_tvalid(finalv),.m_axis_result_tdata(finald));
    m3_fp16_to_fp32 c4(.aclk(clk),.s_axis_a_tvalid(finalv),.s_axis_a_tdata(finald),
      .m_axis_result_tvalid(backv),.m_axis_result_tdata(backd));
    m3_fp32_to_s42 c5(.aclk(clk),.s_axis_a_tvalid(backv),.s_axis_a_tdata(backd),
      .m_axis_result_tvalid(fixedv),.m_axis_result_tdata(fixedd));
    m3_s42_fifo #(.DEPTH(32)) fifo(.clk(clk),.rst_n(rst_n),.clear(clear),
      .push(fixedv),.push_data(fixedd[41:0]),
      .full(fifo_full),.out_valid(out_valid),.out_ready(out_ready),.out_data(out_guard_s42),
      .output_count(output_group_count),.error(fifo_error));assign error=fifo_error;
    always @(posedge clk or negedge rst_n)begin
      if(!rst_n)begin used<=0;input_group_count<=0;end
      else if(clear)begin used<=0;input_group_count<=0;end
      else begin if(in_fire)input_group_count<=input_group_count+1;
        case({in_fire,out_fire})2'b10:used<=used+1;2'b01:used<=used-1;default:used<=used;endcase end
    end
endmodule
