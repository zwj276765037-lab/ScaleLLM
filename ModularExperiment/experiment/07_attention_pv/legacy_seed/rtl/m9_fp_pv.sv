`timescale 1ns/1ps
module m9_fp_pv #(parameter W=32,parameter CASE_ID=2)(
 input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire in_first_key,in_last_key,input wire[W-1:0]in_prob,
 input wire[16*W-1:0]in_v,output wire out_valid,input wire out_ready,
 output wire[383:0]out_context16_s24,output reg[31:0]input_key_count,
 output reg[31:0]output_row_count,output reg[31:0]saturation_count,
 output wire error);
 localparam IDLE=0,MUL_WAIT=1,ADD_WAIT=2,CONV_WAIT=3,OUTPUT=4;
 reg[2:0]st;reg first,last;reg[W-1:0]acc[0:15];
 wire fire=in_valid&&in_ready;wire[15:0]mv,av,bv,fv;
 wire[16*W-1:0]pd,ad;wire[511:0]back;wire[383:0]fix;
 reg[383:0]out;wire pop=out_valid&&out_ready;
 assign in_ready=rst_n&&!clear&&st==IDLE;
 assign out_valid=rst_n&&!clear&&st==OUTPUT;
 assign out_context16_s24=out;
 assign error=(mv!={16{mv[0]}})||(av!={16{av[0]}})||
   (bv!={16{bv[0]}})||(fv!={16{fv[0]}});
 genvar i;generate for(i=0;i<16;i=i+1)begin:g
  if(CASE_ID==1)begin:f16
   m9_f16_mul um(.aclk(clk),.s_axis_a_tvalid(fire),
    .s_axis_a_tdata(in_prob),.s_axis_b_tvalid(fire),
    .s_axis_b_tdata(in_v[i*W+:W]),.m_axis_result_tvalid(mv[i]),
    .m_axis_result_tdata(pd[i*W+:W]));
   m9_f16_add ua(.aclk(clk),.s_axis_a_tvalid(mv[i]),
    .s_axis_a_tdata(pd[i*W+:W]),.s_axis_b_tvalid(mv[i]),
    .s_axis_b_tdata(first?16'd0:acc[i]),.m_axis_result_tvalid(av[i]),
    .m_axis_result_tdata(ad[i*W+:W]));
   m9_f16_to_f32 ub(.aclk(clk),.s_axis_a_tvalid(av[i]&&last),
    .s_axis_a_tdata(ad[i*W+:W]),.m_axis_result_tvalid(bv[i]),
    .m_axis_result_tdata(back[i*32+:32]));
  end else begin:f32
   m9_f32_mul um(.aclk(clk),.s_axis_a_tvalid(fire),
    .s_axis_a_tdata(in_prob),.s_axis_b_tvalid(fire),
    .s_axis_b_tdata(in_v[i*W+:W]),.m_axis_result_tvalid(mv[i]),
    .m_axis_result_tdata(pd[i*W+:W]));
   m9_f32_add ua(.aclk(clk),.s_axis_a_tvalid(mv[i]),
    .s_axis_a_tdata(pd[i*W+:W]),.s_axis_b_tvalid(mv[i]),
    .s_axis_b_tdata(first?32'd0:acc[i]),.m_axis_result_tvalid(av[i]),
    .m_axis_result_tdata(ad[i*W+:W]));
   assign bv[i]=av[i]&&last;assign back[i*32+:32]=ad[i*W+:W];
  end
  m9_f32_to_s24 uf(.aclk(clk),.s_axis_a_tvalid(bv[i]),
   .s_axis_a_tdata(back[i*32+:32]),.m_axis_result_tvalid(fv[i]),
   .m_axis_result_tdata(fix[i*24+:24]));
  always@(posedge clk)if(av[i])acc[i]<=ad[i*W+:W];
 end endgenerate
 integer lane;integer satinc;
 always@(posedge clk or negedge rst_n)begin
  if(!rst_n)begin st<=IDLE;first<=0;last<=0;out<=0;
   input_key_count<=0;output_row_count<=0;saturation_count<=0;end
  else if(clear)begin st<=IDLE;first<=0;last<=0;out<=0;
   input_key_count<=0;output_row_count<=0;saturation_count<=0;end
  else begin
   if(fire)begin first<=in_first_key;last<=in_last_key;
    input_key_count<=input_key_count+1;st<=MUL_WAIT;end
   if(st==MUL_WAIT && (&mv))st<=ADD_WAIT;
   if(st==ADD_WAIT && (&av))begin if(last)st<=CONV_WAIT;else st<=IDLE;end
   if(st==CONV_WAIT && (&fv))begin
    out<=fix;satinc=0;
    for(lane=0;lane<16;lane=lane+1)
     if(fix[lane*24+:24]==24'h7fffff||fix[lane*24+:24]==24'h800000)
      satinc=satinc+1;
    saturation_count<=saturation_count+satinc;st<=OUTPUT;
   end
   if(pop)begin output_row_count<=output_row_count+1;st<=IDLE;end
  end
 end
endmodule
module m9_fp16_pv(input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire in_first_key,in_last_key,input wire[15:0]in_prob,
 input wire[255:0]in_v,output wire out_valid,input wire out_ready,
 output wire[383:0]out_context16_s24,output wire[31:0]input_key_count,
 output wire[31:0]output_row_count,saturation_count,output wire error);
 m9_fp_pv#(.W(16),.CASE_ID(1))u(.*);endmodule
module m9_fp32_pv(input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire in_first_key,in_last_key,input wire[31:0]in_prob,
 input wire[511:0]in_v,output wire out_valid,input wire out_ready,
 output wire[383:0]out_context16_s24,output wire[31:0]input_key_count,
 output wire[31:0]output_row_count,saturation_count,output wire error);
 m9_fp_pv#(.W(32),.CASE_ID(2))u(.*);endmodule
