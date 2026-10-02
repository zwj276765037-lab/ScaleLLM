`timescale 1ns/1ps
module m8_fp_softmax #(
    parameter integer W=32,
    parameter integer CASE_ID=2
) (
    input wire clk,rst_n,clear,
    input wire in_valid,output wire in_ready,
    input wire in_first_key,in_last_key,in_mask,input wire[W-1:0]in_score,
    output wire out_valid,input wire out_ready,
    output wire[15:0]out_prob_u16,output wire[6:0]out_key_index,
    output wire out_last_key,output reg[31:0]input_score_count,
    output reg[31:0]output_prob_count,output reg[31:0]row_count,
    output reg error
);
    localparam ST_LOAD=0,ST_EXP_START=1,ST_EXP_WAIT=2,
      ST_SUM_START=3,ST_SUM_WAIT=4,ST_DIV_START=5,ST_DIV_WAIT=6,
      ST_CONV_WAIT=7,ST_MUL_WAIT=8,ST_FIX_WAIT=9,ST_OUTPUT=10;
    reg[3:0]st;reg[7:0]n;reg[6:0]i;reg[W-1:0]score[0:127];reg sub_seen,div_seen;
    reg masked[0:127];reg[W-1:0]mx;reg[W-1:0]expm[0:127];
    reg[W-1:0]sum;reg[15:0]prob;reg visible;
    wire fire=in_valid&&in_ready,pop=out_valid&&out_ready;
    wire subv,expv,addv,divv,backv,mulv,fixv;
    wire[W-1:0]delta,ev,addout,quot;
    wire[31:0]back,mulout;wire[23:0]fixout;
    wire[W-1:0]zero={W{1'b0}};

    function automatic fp_gt;
      input[W-1:0]a,b;
      begin
        if(a[W-1]!=b[W-1])fp_gt=!a[W-1];
        else if(!a[W-1])fp_gt=a[W-2:0]>b[W-2:0];
        else fp_gt=a[W-2:0]<b[W-2:0];
      end
    endfunction

    assign in_ready=rst_n&&!clear&&st==ST_LOAD;
    assign out_valid=rst_n&&!clear&&st==ST_OUTPUT;
    assign out_prob_u16=prob;assign out_key_index=i;
    assign out_last_key=i==n-1;

    generate if(CASE_ID==1)begin:g16
      m8_f16_sub us(.aclk(clk),.s_axis_a_tvalid(st==ST_EXP_START),
        .s_axis_a_tdata(score[i]),.s_axis_b_tvalid(st==ST_EXP_START),
        .s_axis_b_tdata(mx),.m_axis_result_tvalid(subv),
        .m_axis_result_tdata(delta));
      m8_f16_exp ue(.aclk(clk),.s_axis_a_tvalid(subv),
        .s_axis_a_tdata(delta),.m_axis_result_tvalid(expv),
        .m_axis_result_tdata(ev));
      m8_f16_add ua(.aclk(clk),.s_axis_a_tvalid(st==ST_SUM_START),
        .s_axis_a_tdata(sum),.s_axis_b_tvalid(st==ST_SUM_START),
        .s_axis_b_tdata(expm[i]),.m_axis_result_tvalid(addv),
        .m_axis_result_tdata(addout));
      m8_f16_div ud(.aclk(clk),.s_axis_a_tvalid(st==ST_DIV_START),
        .s_axis_a_tdata(expm[i]),.s_axis_b_tvalid(st==ST_DIV_START),
        .s_axis_b_tdata(sum),.m_axis_result_tvalid(divv),
        .m_axis_result_tdata(quot));
      m8_f16_to_f32 ub(.aclk(clk),.s_axis_a_tvalid(divv),
        .s_axis_a_tdata(quot),.m_axis_result_tvalid(backv),
        .m_axis_result_tdata(back));
    end else begin:g32
      m8_f32_sub us(.aclk(clk),.s_axis_a_tvalid(st==ST_EXP_START),
        .s_axis_a_tdata(score[i]),.s_axis_b_tvalid(st==ST_EXP_START),
        .s_axis_b_tdata(mx),.m_axis_result_tvalid(subv),
        .m_axis_result_tdata(delta));
      m8_f32_exp ue(.aclk(clk),.s_axis_a_tvalid(subv),
        .s_axis_a_tdata(delta),.m_axis_result_tvalid(expv),
        .m_axis_result_tdata(ev));
      m8_f32_add ua(.aclk(clk),.s_axis_a_tvalid(st==ST_SUM_START),
        .s_axis_a_tdata(sum),.s_axis_b_tvalid(st==ST_SUM_START),
        .s_axis_b_tdata(expm[i]),.m_axis_result_tvalid(addv),
        .m_axis_result_tdata(addout));
      m8_f32_div ud(.aclk(clk),.s_axis_a_tvalid(st==ST_DIV_START),
        .s_axis_a_tdata(expm[i]),.s_axis_b_tvalid(st==ST_DIV_START),
        .s_axis_b_tdata(sum),.m_axis_result_tvalid(divv),
        .m_axis_result_tdata(quot));
      assign backv=divv;assign back=quot;
    end endgenerate

    m8_f32_mul um(.aclk(clk),.s_axis_a_tvalid(backv),
      .s_axis_a_tdata(back),.s_axis_b_tvalid(backv),
      .s_axis_b_tdata(32'h47800000),.m_axis_result_tvalid(mulv),
      .m_axis_result_tdata(mulout));
    m8_f32_to_u17 uf(.aclk(clk),.s_axis_a_tvalid(mulv),
      .s_axis_a_tdata(mulout),.m_axis_result_tvalid(fixv),
      .m_axis_result_tdata(fixout));

    always@(posedge clk or negedge rst_n)begin
      if(!rst_n)begin st<=ST_LOAD;n<=0;i<=0;mx<=0;sum<=0;prob<=0;
        visible<=0;sub_seen<=0;div_seen<=0;input_score_count<=0;output_prob_count<=0;row_count<=0;error<=0;end
      else if(clear)begin st<=ST_LOAD;n<=0;i<=0;mx<=0;sum<=0;prob<=0;
        visible<=0;sub_seen<=0;div_seen<=0;input_score_count<=0;output_prob_count<=0;row_count<=0;error<=0;end
      else begin
        if(fire)begin
          if(in_first_key&&n!=0)error<=1;
          score[n]<=in_score;masked[n]<=in_mask;input_score_count<=input_score_count+1;
          if(!in_mask&&(!visible||fp_gt(in_score,mx)))mx<=in_score;
          if(!in_mask)visible<=1;n<=n+1;
          if(in_last_key)begin
            if(!visible&&in_mask)error<=1;
            else begin i<=0;st<=ST_EXP_START;end
          end
        end
        case(st)
          ST_EXP_START:begin sub_seen<=0;st<=ST_EXP_WAIT;end
          ST_EXP_WAIT:begin if(subv)sub_seen<=1;if(expv)begin
            expm[i]<=masked[i]?zero:ev;
            if(i==n-1)begin i<=0;sum<=zero;st<=ST_SUM_START;end
            else begin i<=i+1;st<=ST_EXP_START;end
          end end
          ST_SUM_START:st<=ST_SUM_WAIT;
          ST_SUM_WAIT:if(addv)begin
            sum<=addout;
            if(i==n-1)begin i<=0;st<=ST_DIV_START;end
            else begin i<=i+1;st<=ST_SUM_START;end
          end
          ST_DIV_START:begin div_seen<=0;st<=ST_DIV_WAIT;end
          ST_DIV_WAIT:if(divv)begin div_seen<=1;if(CASE_ID==2)st<=ST_MUL_WAIT;else st<=ST_CONV_WAIT;end
          ST_CONV_WAIT:if(backv)st<=ST_MUL_WAIT;
          ST_MUL_WAIT:if(mulv)st<=ST_FIX_WAIT;
          ST_FIX_WAIT:if(fixv)begin
            prob<=|fixout[23:16]?16'hffff:fixout[15:0];st<=ST_OUTPUT;
          end
          ST_OUTPUT:if(pop)begin
            output_prob_count<=output_prob_count+1;
            if(i==n-1)begin row_count<=row_count+1;n<=0;i<=0;visible<=0;mx<=0;st<=ST_LOAD;end
            else begin i<=i+1;st<=ST_DIV_START;end
          end
        endcase
      end
    end
endmodule

module m8_fp16_softmax(input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire in_first_key,in_last_key,in_mask,input wire[15:0]in_score,
 output wire out_valid,input wire out_ready,output wire[15:0]out_prob_u16,
 output wire[6:0]out_key_index,output wire out_last_key,
 output wire[31:0]input_score_count,output wire[31:0]output_prob_count,row_count,
 output wire error);m8_fp_softmax #(.W(16),.CASE_ID(1))u(.*);endmodule
module m8_fp32_softmax(input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire in_first_key,in_last_key,in_mask,input wire[31:0]in_score,
 output wire out_valid,input wire out_ready,output wire[15:0]out_prob_u16,
 output wire[6:0]out_key_index,output wire out_last_key,
 output wire[31:0]input_score_count,output wire[31:0]output_prob_count,row_count,
 output wire error);m8_fp_softmax #(.W(32),.CASE_ID(2))u(.*);endmodule
