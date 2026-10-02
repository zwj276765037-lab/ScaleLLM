`timescale 1ns/1ps
module m5_fp32_rope(
 input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire[31:0]in_x0_fp32,in_x1_fp32,in_cos_fp32,in_sin_fp32,
 output wire out_valid,input wire out_ready,output wire signed[23:0]out_y0_s24,out_y1_s24,
 output reg[31:0]input_pair_count,output wire[31:0]output_pair_count,output wire error);
 reg[5:0]used;wire fire;wire p0v,p1v,p2v,p3v,y0v,y1v,f0v,f1v;
 wire[31:0]p0,p1,p2,p3,y0,y1;wire[23:0]f0,f1;wire fifo_error;
 assign in_ready=rst_n&&!clear&&(used<32);
 assign fire=in_valid&&in_ready;
 m5_fp32_mul m0(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x0_fp32),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_cos_fp32),.m_axis_result_tvalid(p0v),.m_axis_result_tdata(p0));
 m5_fp32_mul m1(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x1_fp32),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_sin_fp32),.m_axis_result_tvalid(p1v),.m_axis_result_tdata(p1));
 m5_fp32_mul m2(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x0_fp32),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_sin_fp32),.m_axis_result_tvalid(p2v),.m_axis_result_tdata(p2));
 m5_fp32_mul m3(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x1_fp32),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_cos_fp32),.m_axis_result_tvalid(p3v),.m_axis_result_tdata(p3));
 m5_fp32_sub a0(.aclk(clk),.s_axis_a_tvalid(p0v),.s_axis_a_tdata(p0),.s_axis_b_tvalid(p1v),.s_axis_b_tdata(p1),.m_axis_result_tvalid(y0v),.m_axis_result_tdata(y0));
 m5_fp32_add a1(.aclk(clk),.s_axis_a_tvalid(p2v),.s_axis_a_tdata(p2),.s_axis_b_tvalid(p3v),.s_axis_b_tdata(p3),.m_axis_result_tvalid(y1v),.m_axis_result_tdata(y1));
 m5_fp32_to_s24 c0(.aclk(clk),.s_axis_a_tvalid(y0v),.s_axis_a_tdata(y0),.m_axis_result_tvalid(f0v),.m_axis_result_tdata(f0));
 m5_fp32_to_s24 c1(.aclk(clk),.s_axis_a_tvalid(y1v),.s_axis_a_tdata(y1),.m_axis_result_tvalid(f1v),.m_axis_result_tdata(f1));
 m5_pair_fifo fifo(.clk(clk),.rst_n(rst_n),.clear(clear),.push(f0v&&f1v),.push_data({f1,f0}),.out_valid(out_valid),.out_ready(out_ready),.out_data({out_y1_s24,out_y0_s24}),.output_count(output_pair_count),.error(fifo_error));
 assign error=fifo_error||(f0v!=f1v);
 always@(posedge clk or negedge rst_n)if(!rst_n)begin used<=0;input_pair_count<=0;end else if(clear)begin used<=0;input_pair_count<=0;end else begin if(fire)input_pair_count<=input_pair_count+1;case({fire,out_valid&&out_ready})2'b10:used<=used+1;2'b01:used<=used-1;endcase end
endmodule
module m5_fp16_rope(
 input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire[15:0]in_x0_fp16,in_x1_fp16,in_cos_fp16,in_sin_fp16,
 output wire out_valid,input wire out_ready,output wire signed[23:0]out_y0_s24,out_y1_s24,
 output reg[31:0]input_pair_count,output wire[31:0]output_pair_count,output wire error);
 reg[5:0]used;wire fire;wire p0v,p1v,p2v,p3v,y0v,y1v,b0v,b1v,f0v,f1v;
 wire[15:0]p0,p1,p2,p3,y0,y1;wire[31:0]b0,b1;wire[23:0]f0,f1;wire fifo_error;
 assign in_ready=rst_n&&!clear&&(used<32);assign fire=in_valid&&in_ready;
 m5_fp16_mul m0(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x0_fp16),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_cos_fp16),.m_axis_result_tvalid(p0v),.m_axis_result_tdata(p0));
 m5_fp16_mul m1(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x1_fp16),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_sin_fp16),.m_axis_result_tvalid(p1v),.m_axis_result_tdata(p1));
 m5_fp16_mul m2(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x0_fp16),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_sin_fp16),.m_axis_result_tvalid(p2v),.m_axis_result_tdata(p2));
 m5_fp16_mul m3(.aclk(clk),.s_axis_a_tvalid(fire),.s_axis_a_tdata(in_x1_fp16),.s_axis_b_tvalid(fire),.s_axis_b_tdata(in_cos_fp16),.m_axis_result_tvalid(p3v),.m_axis_result_tdata(p3));
 m5_fp16_sub a0(.aclk(clk),.s_axis_a_tvalid(p0v),.s_axis_a_tdata(p0),.s_axis_b_tvalid(p1v),.s_axis_b_tdata(p1),.m_axis_result_tvalid(y0v),.m_axis_result_tdata(y0));
 m5_fp16_add a1(.aclk(clk),.s_axis_a_tvalid(p2v),.s_axis_a_tdata(p2),.s_axis_b_tvalid(p3v),.s_axis_b_tdata(p3),.m_axis_result_tvalid(y1v),.m_axis_result_tdata(y1));
 m5_fp16_to_fp32 c0(.aclk(clk),.s_axis_a_tvalid(y0v),.s_axis_a_tdata(y0),.m_axis_result_tvalid(b0v),.m_axis_result_tdata(b0));
 m5_fp16_to_fp32 c1(.aclk(clk),.s_axis_a_tvalid(y1v),.s_axis_a_tdata(y1),.m_axis_result_tvalid(b1v),.m_axis_result_tdata(b1));
 m5_fp32_to_s24 d0(.aclk(clk),.s_axis_a_tvalid(b0v),.s_axis_a_tdata(b0),.m_axis_result_tvalid(f0v),.m_axis_result_tdata(f0));
 m5_fp32_to_s24 d1(.aclk(clk),.s_axis_a_tvalid(b1v),.s_axis_a_tdata(b1),.m_axis_result_tvalid(f1v),.m_axis_result_tdata(f1));
 m5_pair_fifo fifo(.clk(clk),.rst_n(rst_n),.clear(clear),.push(f0v&&f1v),.push_data({f1,f0}),.out_valid(out_valid),.out_ready(out_ready),.out_data({out_y1_s24,out_y0_s24}),.output_count(output_pair_count),.error(fifo_error));
 assign error=fifo_error||(f0v!=f1v);
 always@(posedge clk or negedge rst_n)if(!rst_n)begin used<=0;input_pair_count<=0;end else if(clear)begin used<=0;input_pair_count<=0;end else begin if(fire)input_pair_count<=input_pair_count+1;case({fire,out_valid&&out_ready})2'b10:used<=used+1;2'b01:used<=used-1;endcase end
endmodule
module m5_pair_fifo(input wire clk,rst_n,clear,push,input wire[47:0]push_data,output wire out_valid,input wire out_ready,output wire[47:0]out_data,output reg[31:0]output_count,output reg error);
 reg[47:0]mem[0:31];reg[4:0]wr,rd;reg[5:0]count;wire pop;assign pop=out_valid&&out_ready;assign out_valid=rst_n&&!clear&&(count!=0);assign out_data=mem[rd];
 always@(posedge clk)if(push&&((count!=32)||pop))mem[wr]<=push_data;
 always@(posedge clk or negedge rst_n)if(!rst_n)begin wr<=0;rd<=0;count<=0;output_count<=0;error<=0;end else if(clear)begin wr<=0;rd<=0;count<=0;output_count<=0;error<=0;end else begin if(push&&count==32&&!pop)error<=1;if(push&&((count!=32)||pop))wr<=wr+1;if(pop)begin rd<=rd+1;output_count<=output_count+1;end case({push&&((count!=32)||pop),pop})2'b10:count<=count+1;2'b01:count<=count-1;endcase end
endmodule
