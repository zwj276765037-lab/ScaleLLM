`timescale 1ns/1ps
module m6_kv12_quantizer2(
 input wire clk,rst_n,clear,in_valid,output wire in_ready,input wire[3071:0]in_s24,
 output wire out_valid,input wire out_ready,output wire[1:0]out_lane,output wire out_batch_last,
 output wire[383:0]out_s12,output wire[15:0]out_meta,output reg[31:0]input_batch_count,
 output reg[31:0]output_group_count,output wire error);
 reg active,second_wave;reg[3:0]done;reg[3071:0]batch;wire[1:0]wi_ready,wi_valid,wo_valid,wo_ready,werr;wire[767:0]wdata;wire[31:0]wmeta;reg select;
 wire fire=in_valid&&in_ready;assign in_ready=rst_n&&!clear&&!active&&(&wi_ready);assign wi_valid={2{active&&((!second_wave&&done[1:0]==0)||(second_wave&&done[3:2]==0))}};
 always@*begin if(wo_valid[0]&&!done[(second_wave?2:0)])select=0;else select=1;end
 wire[1:0]onehot=2'b01<<select;wire any=|(wo_valid&~({done[second_wave?3:2],done[second_wave?2:1]}));
 assign out_valid=active&&any;assign out_lane={second_wave,select};assign out_batch_last=second_wave&&((done[3:2]|onehot)==2'b11);assign out_s12=wdata[select*384+:384];assign out_meta=wmeta[select*16+:16];assign error=|werr;
 genvar w;generate for(w=0;w<2;w=w+1)begin:g
  assign wo_ready[w]=out_ready&&out_valid&&(select==w);
  hap_kv12_quantizer q(.clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(wi_valid[w]),.in_ready(wi_ready[w]),.in_s24(batch[((second_wave?2:0)+w)*768+:768]),.out_valid(wo_valid[w]),.out_ready(wo_ready[w]),.out_s12(wdata[w*384+:384]),.out_meta(wmeta[w*16+:16]),.input_group_count(),.output_group_count(),.clip_count(),.cycle_count(),.error(werr[w]));
 end endgenerate
 wire ofire=out_valid&&out_ready;
 always@(posedge clk or negedge rst_n)if(!rst_n)begin active<=0;second_wave<=0;done<=0;input_batch_count<=0;output_group_count<=0;batch<=0;end else if(clear)begin active<=0;second_wave<=0;done<=0;input_batch_count<=0;output_group_count<=0;end else begin
  if(fire)begin batch<=in_s24;active<=1;second_wave<=0;done<=0;input_batch_count<=input_batch_count+1;end
  if(ofire)begin output_group_count<=output_group_count+1;if(!second_wave)begin done[select]<=1;if((done[1:0]|onehot)==2'b11)begin second_wave<=1;done[3:2]<=0;end end else begin done[2+select]<=1;if((done[3:2]|onehot)==2'b11)begin active<=0;second_wave<=0;done<=0;end end end
 end
endmodule
