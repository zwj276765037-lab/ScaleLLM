`timescale 1ns / 1ps

package m3_fp_sim_pkg;
    function automatic [15:0] fp32_to_fp16(input [31:0] bits);
        reg sign; reg [7:0] exp32; reg [22:0] frac32;
        integer exp_unbiased, exp16, shift;
        reg [23:0] significand; reg [24:0] rounded;
        begin
            sign=bits[31]; exp32=bits[30:23]; frac32=bits[22:0];
            if(exp32==0) fp32_to_fp16={sign,15'd0};
            else if(exp32==8'hff)
                fp32_to_fp16={sign,5'h1f,(frac32==0)?10'd0:10'h200};
            else begin
                exp_unbiased=exp32-127; exp16=exp_unbiased+15;
                significand={1'b1,frac32};
                if(exp16>=31) fp32_to_fp16={sign,5'h1f,10'd0};
                else if(exp16<=0) begin
                    shift=14-exp_unbiased;
                    if(shift>24) fp32_to_fp16={sign,15'd0};
                    else begin
                        rounded=significand+(25'd1<<(shift-1));
                        fp32_to_fp16={sign,5'd0,rounded>>shift};
                    end
                end else begin
                    rounded={1'b0,significand}+25'h00001000;
                    if(rounded[24]) begin
                        exp16=exp16+1;
                        fp32_to_fp16=(exp16>=31)?{sign,5'h1f,10'd0}:
                            {sign,exp16[4:0],10'd0};
                    end else
                        fp32_to_fp16={sign,exp16[4:0],rounded[22:13]};
                end
            end
        end
    endfunction

    function automatic [31:0] fp16_to_fp32(input [15:0] bits);
        reg sign; reg [4:0] exp16; reg [9:0] frac16;
        integer exponent; reg [7:0] exp32;
        begin
            sign=bits[15]; exp16=bits[14:10]; frac16=bits[9:0];
            if(exp16==0) begin
                if(frac16==0) fp16_to_fp32={sign,31'd0};
                else begin
                    exponent=-14;
                    while(!frac16[9]) begin
                        frac16=frac16<<1; exponent=exponent-1;
                    end
                    frac16=frac16&10'h1ff;
                    exp32=exponent+127;
                    fp16_to_fp32={sign,exp32,frac16,13'd0};
                end
            end else if(exp16==31)
                fp16_to_fp32={sign,8'hff,frac16,13'd0};
            else begin
                exp32=exp16-15+127;
                fp16_to_fp32={sign,exp32,frac16,13'd0};
            end
        end
    endfunction

    function automatic [15:0] fp16_mul(input[15:0]a,input[15:0]b);
        shortreal av,bv,rv;
        begin
            av=$bitstoshortreal(fp16_to_fp32(a));
            bv=$bitstoshortreal(fp16_to_fp32(b));
            rv=av*bv;
            fp16_mul=fp32_to_fp16($shortrealtobits(rv));
        end
    endfunction
endpackage

module m3_int21_to_fp32(input wire aclk,input wire s_axis_a_tvalid,
    input wire[23:0]s_axis_a_tdata,output reg m_axis_result_tvalid,
    output reg[31:0]m_axis_result_tdata);
    localparam L=6; reg[L-1:0]v; reg[31:0]d[0:L-1];
    integer i; integer signed x; shortreal r;
    always@(posedge aclk)begin
      v[0]<=s_axis_a_tvalid;
      if(s_axis_a_tvalid)begin x=$signed(s_axis_a_tdata);r=x;d[0]<=$shortrealtobits(r);end
      for(i=1;i<L;i=i+1)begin v[i]<=v[i-1];d[i]<=d[i-1];end
      m_axis_result_tvalid<=v[L-1];m_axis_result_tdata<=d[L-1];end
endmodule

module m3_fp32_mul(input wire aclk,input wire s_axis_a_tvalid,
 input wire[31:0]s_axis_a_tdata,input wire s_axis_b_tvalid,
 input wire[31:0]s_axis_b_tdata,output reg m_axis_result_tvalid,
 output reg[31:0]m_axis_result_tdata);
 localparam L=8;reg[L-1:0]v;reg[31:0]d[0:L-1];integer i;shortreal a,b,r;
 always@(posedge aclk)begin v[0]<=s_axis_a_tvalid&&s_axis_b_tvalid;
  if(s_axis_a_tvalid&&s_axis_b_tvalid)begin a=$bitstoshortreal(s_axis_a_tdata);
   b=$bitstoshortreal(s_axis_b_tdata);r=a*b;d[0]<=$shortrealtobits(r);end
  for(i=1;i<L;i=i+1)begin v[i]<=v[i-1];d[i]<=d[i-1];end
  m_axis_result_tvalid<=v[L-1];m_axis_result_tdata<=d[L-1];end
endmodule

module m3_fp32_to_fp16(input wire aclk,input wire s_axis_a_tvalid,
 input wire[31:0]s_axis_a_tdata,output reg m_axis_result_tvalid,
 output reg[15:0]m_axis_result_tdata);
 import m3_fp_sim_pkg::*;localparam L=3;reg[L-1:0]v;reg[15:0]d[0:L-1];integer i;
 always@(posedge aclk)begin v[0]<=s_axis_a_tvalid;
  if(s_axis_a_tvalid)d[0]<=fp32_to_fp16(s_axis_a_tdata);
  for(i=1;i<L;i=i+1)begin v[i]<=v[i-1];d[i]<=d[i-1];end
  m_axis_result_tvalid<=v[L-1];m_axis_result_tdata<=d[L-1];end
endmodule

module m3_fp16_mul(input wire aclk,input wire s_axis_a_tvalid,
 input wire[15:0]s_axis_a_tdata,input wire s_axis_b_tvalid,
 input wire[15:0]s_axis_b_tdata,output reg m_axis_result_tvalid,
 output reg[15:0]m_axis_result_tdata);
 import m3_fp_sim_pkg::*;localparam L=6;reg[L-1:0]v;reg[15:0]d[0:L-1];integer i;
 always@(posedge aclk)begin v[0]<=s_axis_a_tvalid&&s_axis_b_tvalid;
  if(s_axis_a_tvalid&&s_axis_b_tvalid)d[0]<=fp16_mul(s_axis_a_tdata,s_axis_b_tdata);
  for(i=1;i<L;i=i+1)begin v[i]<=v[i-1];d[i]<=d[i-1];end
  m_axis_result_tvalid<=v[L-1];m_axis_result_tdata<=d[L-1];end
endmodule

module m3_fp16_to_fp32(input wire aclk,input wire s_axis_a_tvalid,
 input wire[15:0]s_axis_a_tdata,output reg m_axis_result_tvalid,
 output reg[31:0]m_axis_result_tdata);
 import m3_fp_sim_pkg::*;localparam L=2;reg[L-1:0]v;reg[31:0]d[0:L-1];integer i;
 always@(posedge aclk)begin v[0]<=s_axis_a_tvalid;
  if(s_axis_a_tvalid)d[0]<=fp16_to_fp32(s_axis_a_tdata);
  for(i=1;i<L;i=i+1)begin v[i]<=v[i-1];d[i]<=d[i-1];end
  m_axis_result_tvalid<=v[L-1];m_axis_result_tdata<=d[L-1];end
endmodule

module m3_fp32_to_s42(input wire aclk,input wire s_axis_a_tvalid,
 input wire[31:0]s_axis_a_tdata,output reg m_axis_result_tvalid,
 output reg[47:0]m_axis_result_tdata);
 localparam L=6;reg[L-1:0]v;reg[47:0]d[0:L-1];integer i;
 shortreal a;real scaled;longint signed fixed;
 always@(posedge aclk)begin v[0]<=s_axis_a_tvalid;
  if(s_axis_a_tvalid)begin a=$bitstoshortreal(s_axis_a_tdata);
    scaled=a*16777216.0;fixed=$rtoi(scaled);d[0]<={{6{fixed[41]}},fixed[41:0]};end
  for(i=1;i<L;i=i+1)begin v[i]<=v[i-1];d[i]<=d[i-1];end
  m_axis_result_tvalid<=v[L-1];m_axis_result_tdata<=d[L-1];end
endmodule
