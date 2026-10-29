`timescale 1ns/1ps
// Parallel eight-row banks expose a complete sixteen-row group to online MLP.
module hap_scalellm_final_input16(
 input wire clk,input wire rst_n,input wire clear,input wire [15:0] active_mask,
 input wire wr_valid,output wire wr_ready,input wire[12:0]wr_addr,input wire[255:0]wr_data,
 input wire load_start,output wire out_valid,input wire out_ready,output wire[8:0]out_group,
 output wire[12287:0]out_s24,output wire error
);
 wire bank=wr_addr>=3072;wire[11:0]address=bank?wr_addr-3072:wr_addr[11:0];
 wire[1:0]wrready,v,busy,e;wire[6:0]group0,group1;wire[6143:0]data0,data1;
 assign wr_ready=wr_addr<6144&&(bank?wrready[1]:wrready[0]);
 assign out_valid=v[0]&&v[1];assign out_group={2'd0,group0};
 assign error=(|e)||(out_valid&&group0!=group1);
 genvar row;generate for(row=0;row<16;row=row+1)begin:g_mask
  if(row<8)assign out_s24[row*768+:768]=active_mask[row]?data0[row*768+:768]:768'd0;
  else assign out_s24[row*768+:768]=active_mask[row]?data1[(row-8)*768+:768]:768'd0;
 end endgenerate
 hap_tensor24_input_buffer u_wave0(.clk(clk),.rst_n(rst_n),.clear(clear),
 .wr_valid(wr_valid&&!bank&&wr_addr<6144),.wr_ready(wrready[0]),.wr_addr(address),.wr_data(wr_data),.load_start(load_start),
 .activation_valid(v[0]),.activation_ready(out_ready&&v[1]),.activation_group(group0),.activation_s24(data0),.busy(busy[0]),.error(e[0]));
 hap_tensor24_input_buffer u_wave1(.clk(clk),.rst_n(rst_n),.clear(clear),
 .wr_valid(wr_valid&&bank&&wr_addr<6144),.wr_ready(wrready[1]),.wr_addr(address),.wr_data(wr_data),.load_start(load_start),
 .activation_valid(v[1]),.activation_ready(out_ready&&v[0]),.activation_group(group1),.activation_s24(data1),.busy(busy[1]),.error(e[1]));
endmodule
