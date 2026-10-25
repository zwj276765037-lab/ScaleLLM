`timescale 1ns / 1ps
// Records are independent of AXI burst boundaries; in_last is tensor-last.
module hap_mlp_linear_rec576_parser (
 input wire clk,input wire rst_n,input wire job_clear,
 input wire begin_valid,output wire begin_ready,input wire [1:0] begin_opcode,
 input wire in_valid,output wire in_ready,input wire [255:0] in_data,input wire in_last,
 output wire wr_valid,input wire wr_ready,output reg [8:0] wr_group,
 output wire [4095:0] wr_u8x16x32,output wire [383:0] wr_meta_u24x16,
 output reg done,output wire quiescent,output reg error,output reg [31:0] error_code,
 output reg [31:0] accepted_input_bytes
);
 localparam [31:0] E_PADDING=32'h2001,E_RESERVED=32'h2002,E_ZERO=32'h2003,E_LENGTH=32'h2004;
 reg active,out_valid;
 reg [8:0] expected_groups,group_index;
 reg [4:0] beat_index;
 reg [255:0] payload[0:15];
 reg [255:0] metadata_low;
 reg [383:0] metadata;
 wire [383:0] final_meta={in_data[127:0],metadata_low};
 reg [31:0] record_error;
 integer row;
 always @*begin
  record_error=0;
  if(in_data[255:128]!=0)record_error=E_PADDING;
  for(integer rr=0;rr<16;rr=rr+1)begin
   if(record_error==0&&final_meta[rr*24+22+:2]!=0)record_error=E_RESERVED;
   if(record_error==0&&final_meta[rr*24+8+:8]==0&&
       (final_meta[rr*24+:8]!=0||final_meta[rr*24+16+:6]!=0||payload[rr]!=0))record_error=E_ZERO;
  end
 end
 assign begin_ready=rst_n&&!job_clear&&!active&&!out_valid&&!error;
 assign in_ready=rst_n&&!job_clear&&active&&!out_valid;
 assign wr_valid=rst_n&&!job_clear&&out_valid;
 assign wr_meta_u24x16=metadata;
 assign quiescent=!active&&!out_valid;
 genvar r;
 generate for(r=0;r<16;r=r+1)begin:gen_payload
  // Each row has its own 256-bit write/capture enable.
  always @(posedge clk)if(in_valid&&in_ready&&beat_index==r)payload[r]<=in_data;
  assign wr_u8x16x32[r*256+:256]=payload[r];
 end endgenerate
 always @(posedge clk)begin
  if(!rst_n||job_clear)begin
   active<=0;out_valid<=0;expected_groups<=0;group_index<=0;beat_index<=0;
   metadata_low<=0;metadata<=0;wr_group<=0;done<=0;error<=0;error_code<=0;accepted_input_bytes<=0;
  end else begin
   done<=0;
   if(begin_valid&&begin_ready)begin
    if(begin_opcode==1||begin_opcode==2)begin
     active<=1;expected_groups<=begin_opcode==1?9'd128:9'd448;
    end else begin error<=1;error_code<=E_LENGTH;end
   end
   if(wr_valid&&wr_ready)begin
    out_valid<=0;
    accepted_input_bytes<=accepted_input_bytes+32'd576;
    if(wr_group==expected_groups-1)done<=1;
   end
   if(in_valid&&in_ready)begin
    if(in_last!=(group_index==expected_groups-1&&beat_index==17)&&!error)begin
     error<=1;error_code<=E_LENGTH;
    end
    if(beat_index==16)metadata_low<=in_data;
    if(beat_index==17)begin
     beat_index<=0;group_index<=group_index+1'b1;
     if(group_index==expected_groups-1)active<=0;
     if(!error&&record_error==0&&in_last==(group_index==expected_groups-1))begin
      metadata<=final_meta;wr_group<=group_index;out_valid<=1;
     end else begin
      if(!error&&record_error!=0)begin error<=1;error_code<=record_error;end
      if(group_index==expected_groups-1)done<=1;
     end
    end else beat_index<=beat_index+1'b1;
   end
  end
 end
endmodule
