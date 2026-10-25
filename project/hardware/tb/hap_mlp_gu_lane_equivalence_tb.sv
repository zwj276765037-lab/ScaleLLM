`timescale 1ns/1ps
module hap_mlp_gu_lane_equivalence_tb;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0,clear=0,in_valid=0,out_ready=0;
 reg [585:0] input_word=0;
 wire signed[287:0] activation_s9x32=input_word[0+:288];
 wire signed[127:0] weight0_s4x32=input_word[288+:128],weight1_s4x32=input_word[416+:128];
 wire[7:0] activation_code_u8=input_word[544+:8],weight0_code_u8=input_word[558+:8],weight1_code_u8=input_word[572+:8];
 wire[5:0] activation_shift_u6=input_word[552+:6],weight0_shift_u6=input_word[566+:6],weight1_shift_u6=input_word[580+:6];
 wire old_ready,new_ready,old_valid,new_valid,old_over,new_over,old_fmt,new_fmt,old_error,new_error;
 wire signed[36:0] old0,old1,new0,new1;
 wire[31:0] old_shift,new_shift,old_in,new_in,old_out,new_out;
 reg[585:0] stimulus[0:511];reg[73:0] gold[0:511];
 integer cycle=0,received=0,checks=0;
 hap_a8w4_group32_lane2_s37 #(.DOWN_MODE_ENABLE(1)) old_gu(
  .clk(clk),.rst_n(rst_n),.clear(clear),.down_mode(1'b0),.in_valid(in_valid),.in_ready(old_ready),
  .activation_s9x32(activation_s9x32),.weight0_s4x32(weight0_s4x32),.weight1_s4x32(weight1_s4x32),
  .activation_code_u8(activation_code_u8),.activation_shift_u6(activation_shift_u6),
  .weight0_code_u8(weight0_code_u8),.weight0_shift_u6(weight0_shift_u6),
  .weight1_code_u8(weight1_code_u8),.weight1_shift_u6(weight1_shift_u6),
  .out_valid(old_valid),.out_ready(out_ready),.guard0_s37(old0),.guard1_s37(old1),
  .guard0_s45(),.guard1_s45(),.out_down(),.guard_overflow(old_over),
  .total_shift_format_count(old_shift),.format_error(old_fmt),
  .input_group_count(old_in),.output_group_count(old_out),.error(old_error));
 hap_a8w4_gu_group32_lane2_s37 new_gu(
  .clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(new_ready),
  .activation_s9x32(activation_s9x32),.weight0_s4x32(weight0_s4x32),.weight1_s4x32(weight1_s4x32),
  .activation_code_u8(activation_code_u8),.activation_shift_u6(activation_shift_u6),
  .weight0_code_u8(weight0_code_u8),.weight0_shift_u6(weight0_shift_u6),
  .weight1_code_u8(weight1_code_u8),.weight1_shift_u6(weight1_shift_u6),
  .out_valid(new_valid),.out_ready(out_ready),.guard0_s37(new0),.guard1_s37(new1),
  .guard_overflow(new_over),.total_shift_format_count(new_shift),.format_error(new_fmt),
  .input_group_count(new_in),.output_group_count(new_out),.error(new_error));
 always @(negedge clk)begin
  if(rst_n&&!clear)out_ready=(cycle%127>=73)&&(cycle%5!=0);
  else out_ready=0;
 end
 always @(posedge clk)begin
  cycle=cycle+1;
  if(cycle>30000)$fatal(1,"lane watchdog");
  if(!rst_n||clear)received=0;
  else begin
   if({new_ready,new_valid,new_over,new_fmt,new_error,new_shift,new_in,new_out} !==
      {old_ready,old_valid,old_over,old_fmt,old_error,old_shift,old_in,old_out})
       $fatal(1,"lane control mismatch cycle%0d",cycle);
   checks=checks+1;
   if(new_valid)begin
    if({new1,new0}!=={old1,old0})$fatal(1,"old/new guard mismatch");
    if({new1,new0}!==gold[received])$fatal(1,"Python integer gold mismatch vector%0d",received);
    if(out_ready)received=received+1;
   end
  end
 end
 task send(input integer index);
 begin
  @(negedge clk);input_word=stimulus[index];in_valid=1;
  @(posedge clk);while(!new_ready)@(posedge clk);
 end endtask
 initial begin
  $readmemh("data/mlp_gu_lane/stimulus.mem",stimulus);
  $readmemh("data/mlp_gu_lane/gold.mem",gold);
  repeat(5)@(negedge clk);rst_n=1;
  for(integer i=0;i<48;i=i+1)send(i);
  @(negedge clk);clear=1;in_valid=0;
  repeat(4)@(negedge clk);clear=0;
  for(integer i=0;i<512;i=i+1)send(i);
  @(negedge clk);in_valid=0;
  wait(received==512);repeat(5)@(negedge clk);
  if(new_in!=512||new_out!=512||!new_fmt||!new_error||new_over)$fatal(1,"lane terminal counters/errors");
  $display("GU_LANE_EQUIVALENCE vectors512 plus pending clear checks%0d",checks);
  $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
