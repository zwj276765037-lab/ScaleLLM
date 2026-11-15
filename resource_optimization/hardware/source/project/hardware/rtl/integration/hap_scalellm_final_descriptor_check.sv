`timescale 1ns/1ps
// All address/identity checks finish before DMA admission.
module hap_scalellm_final_descriptor_check(input wire [2047:0] descriptor,output reg [31:0] error_code);
 `include "hap_scalellm_final_abi.svh"
 wire [31:0] d[0:63];
 genvar g;generate for(g=0;g<64;g=g+1)begin:g_words assign d[g]=descriptor[g*32+:32];end endgenerate
 integer i,b;
 reg address_ok,reserved_ok,rows_ok;
 reg [31:0] expected_in,expected_out;
 always @*begin
  address_ok=0;reserved_ok=1;rows_ok=1;expected_in=0;expected_out=0;
  for(i=20;i<32;i=i+1)if(d[i]!=0)reserved_ok=0;
  for(i=0;i<16;i=i+1)begin
   if(d[32+2*i]>127)rows_ok=0;
   if(d[6][i])begin if(d[33+2*i]==0)rows_ok=0;end
   else if(d[32+2*i]!=0||d[33+2*i]!=0)rows_ok=0;
  end
  for(b=0;b<6;b=b+1)begin
   if(d[4]==1)begin expected_in=32'h56000000+b*32'h00100000;expected_out=32'h56080000+b*32'h00100000;end
   else begin expected_in=32'h10000000+b*32'h00800000;expected_out=32'h10100000+b*32'h00800000;end
   if(d[8]==expected_in&&d[9]==expected_out)address_ok=1;
  end
  if(d[4]==1)begin
   if(d[12]!=d[5]*32'h02800000||d[13]!=d[5]*32'h02800000+32'h01400000||
      d[14]!=32'h50000000+d[5]*32'h00280000||d[15]!=32'h57000000)address_ok=0;
  end else if(d[12]!=0||d[13]!=32'h01c00000||d[14]!=32'h20000000+d[5]*32'h00700000||d[15]!=0)address_ok=0;
  error_code=0;
  if(d[0]!=FINAL_ID_MAGIC||d[1]!=FINAL_ID_ABI)error_code=FINAL_ERR_BAD_MAGIC_ABI;
  else if(d[4]!=1&&d[4]!=2)error_code=FINAL_ERR_BAD_OPCODE;
  else if(d[2]==0||d[3]>65535||d[5]>31||d[6]==0||d[6]>65535||d[7]==0||d[16]==0)error_code=FINAL_ERR_BAD_IDENTITY;
  else if(d[17]!=0||!reserved_ok)error_code=FINAL_ERR_BAD_RESERVED;
  else if(!rows_ok)error_code=FINAL_ERR_BAD_ROW;
  else if((d[4]==1&&(d[18]!=FINAL_ID_ATTENTION_FORMAT||d[19]!=FINAL_ID_ATTENTION_LAYOUT))||
          (d[4]==2&&(d[18]!=FINAL_ID_MLP_FORMAT||d[19]!=FINAL_ID_MLP_LAYOUT)))error_code=FINAL_ERR_BAD_FORMAT_LAYOUT;
  else if(d[10]!=196608||d[11]!=(d[4]==1?196608:917504))error_code=FINAL_ERR_BAD_LENGTH;
  else if(!address_ok)error_code=FINAL_ERR_BAD_ADDRESS;
 end
endmodule
