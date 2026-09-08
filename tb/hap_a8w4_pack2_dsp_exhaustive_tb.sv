`timescale 1ns / 1ps

module hap_a8w4_pack2_dsp_exhaustive_tb;
    localparam integer VECTOR_COUNT=511*16*16;
    reg clk=0; always #3.333 clk=~clk;
    reg rst_n=0,clear=0,out_ready=1;
    wire in_valid,in_ready,out_valid;
    wire signed [8:0] activation_s9;
    wire signed [3:0] weight0_s4,weight1_s4;
    wire signed [11:0] product0_s12,product1_s12;
    integer send_a=-255,send_w0=-8,send_w1=-8;
    integer exp_a[0:VECTOR_COUNT-1];
    integer exp_w0[0:VECTOR_COUNT-1];
    integer exp_w1[0:VECTOR_COUNT-1];
    integer send_count=0,recv_count=0,cycle_count=0,mismatch_count=0;

    hap_a8w4_pack2_dsp dut(
      .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),
      .in_ready(in_ready),.activation_s9(activation_s9),
      .weight0_s4(weight0_s4),.weight1_s4(weight1_s4),
      .out_valid(out_valid),.out_ready(out_ready),
      .product0_s12(product0_s12),.product1_s12(product1_s12));

    initial begin repeat(5)@(posedge clk);rst_n<=1;end

    assign in_valid=send_count<VECTOR_COUNT;
    assign activation_s9=send_a;
    assign weight0_s4=send_w0;
    assign weight1_s4=send_w1;

    always @(posedge clk)begin
      if(!rst_n)begin
        send_a<=-255;send_w0<=-8;send_w1<=-8;
        send_count<=0;recv_count<=0;cycle_count<=0;mismatch_count<=0;
      end else begin
        cycle_count<=cycle_count+1;
        if(in_valid&&in_ready)begin
          exp_a[send_count]<=send_a;
          exp_w0[send_count]<=send_w0;
          exp_w1[send_count]<=send_w1;
          send_count<=send_count+1;
          if(send_w1==7)begin
            send_w1<=-8;
            if(send_w0==7)begin
              send_w0<=-8;send_a<=send_a+1;
            end else send_w0<=send_w0+1;
          end else send_w1<=send_w1+1;
        end
        if(out_valid&&out_ready)begin
          if($signed(product0_s12)!==exp_a[recv_count]*exp_w0[recv_count]||
             $signed(product1_s12)!==exp_a[recv_count]*exp_w1[recv_count])begin
            if(mismatch_count<10)$display(
              "MISMATCH i=%0d a=%0d w0=%0d w1=%0d got=%0d/%0d expected=%0d/%0d",
              recv_count,exp_a[recv_count],exp_w0[recv_count],
              exp_w1[recv_count],$signed(product0_s12),
              $signed(product1_s12),exp_a[recv_count]*exp_w0[recv_count],
              exp_a[recv_count]*exp_w1[recv_count]);
            mismatch_count<=mismatch_count+1;
          end
          recv_count<=recv_count+1;
          if(recv_count+1==VECTOR_COUNT)begin
            if(mismatch_count==0)$display(
              "PASS: hap_a8w4_pack2_dsp exhaustive vectors=%0d cycles=%0d mismatches=0",
              VECTOR_COUNT,cycle_count);
            else $fatal(1,"FAIL: mismatches=%0d",mismatch_count);
            if(mismatch_count==0)$finish;
          end
        end
        if(cycle_count>VECTOR_COUNT+100)begin
          $fatal(1,"FAIL: timeout send=%0d recv=%0d",send_count,recv_count);
        end
      end
    end
endmodule
