`timescale 1ns / 1ps
module m3_lane_tb #(
 parameter integer CASE_ID=0,
 parameter string DATA_DIR="data",
 parameter integer CLOCK_PERIOD_PS=6667
);
 localparam N=256;
 reg clk=0,rst_n=0,clear=0,out_ready=0;
 wire in_ready,out_valid;wire signed[41:0]out_guard;
 wire[31:0]in_count,out_count;wire error;
 reg[255:0]act_mem[0:N-1],wgt_mem[0:N-1];reg[39:0]meta_mem[0:N-1];
 reg[31:0]fp16_mem[0:N-1];reg[63:0]fp32_mem[0:N-1];reg[41:0]expected[0:N-1];
 integer cycle=0,sent=0,received=0,mismatch=0,wait_cycles=0;
 integer first_accept=-1,first_output=-1,prev_accept=-1;
 integer ii_min=999999,ii_max=0,interval,total_cycles;
 wire in_valid=rst_n&&(sent<N);wire[7:0]zp=meta_mem[sent][7:0];
 // Functional regressions keep the historical 150 MHz default.  Power runs
 // override CLOCK_PERIOD_PS to 10000 so SAIF toggle rates match the 100 MHz
 // implementation checkpoint rather than requiring post-hoc scaling.
 always #(CLOCK_PERIOD_PS / 2000.0) clk=~clk;
 generate
  if(CASE_ID==0)m3_mac_only_lane dut(.clk(clk),.rst_n(rst_n),.clear(clear),
   .in_valid(in_valid),.in_ready(in_ready),.in_act_u8(act_mem[sent]),
   .in_wgt_s8(wgt_mem[sent]),.in_act_zero_point(zp),.out_valid(out_valid),
   .out_ready(out_ready),.out_guard_s42(out_guard),.input_group_count(in_count),
   .output_group_count(out_count),.error(error));
  else if(CASE_ID==1)hap_a8w8_group32_lane_s42 dut(.clk(clk),.rst_n(rst_n),
   .clear(clear),.in_valid(in_valid),.in_ready(in_ready),.in_act_u8(act_mem[sent]),
   .in_wgt_s8(wgt_mem[sent]),.in_act_zero_point(zp),
   .in_act_scale_code(meta_mem[sent][19:12]),
   .in_act_scale_shift(meta_mem[sent][25:20]),
   .in_wgt_scale_code(meta_mem[sent][33:26]),
   .in_wgt_scale_shift(meta_mem[sent][39:34]),.out_valid(out_valid),
   .out_ready(out_ready),.out_guard_s42(out_guard),.input_group_count(in_count),
   .output_group_count(out_count),.error(error));
  else if(CASE_ID==2) begin : g_fp16
   m3_fp16_scale_lane dut(.clk(clk),.rst_n(rst_n),.clear(clear),
   .in_valid(in_valid),.in_ready(in_ready),.in_act_u8(act_mem[sent]),
   .in_wgt_s8(wgt_mem[sent]),.in_act_zero_point(zp),
   .in_act_scale_fp16(fp16_mem[sent][15:0]),
   .in_wgt_scale_fp16(fp16_mem[sent][31:16]),.out_valid(out_valid),
   .out_ready(out_ready),.out_guard_s42(out_guard),.input_group_count(in_count),
   .output_group_count(out_count),.error(error));
  end
  else m3_fp32_scale_lane dut(.clk(clk),.rst_n(rst_n),.clear(clear),
   .in_valid(in_valid),.in_ready(in_ready),.in_act_u8(act_mem[sent]),
   .in_wgt_s8(wgt_mem[sent]),.in_act_zero_point(zp),
   .in_act_scale_fp32(fp32_mem[sent][31:0]),
   .in_wgt_scale_fp32(fp32_mem[sent][63:32]),.out_valid(out_valid),
   .out_ready(out_ready),.out_guard_s42(out_guard),.input_group_count(in_count),
   .output_group_count(out_count),.error(error));
 endgenerate
 initial begin
  $readmemh({DATA_DIR,"/act_u8.mem"},act_mem);
  $readmemh({DATA_DIR,"/weight_s8.mem"},wgt_mem);
  $readmemh({DATA_DIR,"/meta_scalecode.mem"},meta_mem);
  $readmemh({DATA_DIR,"/scale_fp16.mem"},fp16_mem);
  $readmemh({DATA_DIR,"/scale_fp32.mem"},fp32_mem);
  if(CASE_ID==0)$readmemh({DATA_DIR,"/expected_corr_s21.mem"},expected);
  else if(CASE_ID==1)$readmemh({DATA_DIR,"/expected_scalecode_s42.mem"},expected);
  else if(CASE_ID==2)$readmemh({DATA_DIR,"/expected_fp16_ip_s42.mem"},expected);
  else $readmemh({DATA_DIR,"/expected_fp32_s42.mem"},expected);
  repeat(8)@(posedge clk);rst_n<=1;
 end
 always@(negedge clk)out_ready<=(cycle<160)||((cycle%4)==0);
 always@(posedge clk)begin
  if(!rst_n)begin cycle<=0;sent<=0;received<=0;end else begin
   cycle<=cycle+1;
   if(in_valid&&in_ready)begin
    if(first_accept<0)first_accept=cycle;
    if(prev_accept>=0&&sent<64)begin interval=cycle-prev_accept;
      if(interval<ii_min)ii_min=interval;if(interval>ii_max)ii_max=interval;end
    prev_accept=cycle;sent<=sent+1;
   end else if(in_valid)wait_cycles=wait_cycles+1;
   if(out_valid&&out_ready)begin
    if(first_output<0)first_output=cycle;
    if(out_guard!==expected[received])begin mismatch<=mismatch+1;
      $display("MISMATCH case=%0d idx=%0d exp=%h got=%h",CASE_ID,received,expected[received],out_guard);end
    received<=received+1;
    if(received==N-1)begin total_cycles=cycle-first_accept+1;
     if(mismatch!=0||out_guard!==expected[received]||in_count!=N||
        out_count!=N-1||error)
      $display("FAIL: M3 case=%0d mismatch=%0d in=%0d out=%0d",CASE_ID,mismatch,in_count,out_count);
     else begin
      $display("M3_LANE_METRIC_JSON: {\"case_id\":%0d,\"vectors\":256,\"mismatches\":0,\"intrinsic_ii_min\":%0d,\"intrinsic_ii_max\":%0d,\"first_output_latency\":%0d,\"producer_wait_cycles\":%0d,\"total_cycles\":%0d,\"effective_group_per_cycle\":%0f,\"effective_gops_150mhz\":%0f}",CASE_ID,ii_min,ii_max,first_output-first_accept,wait_cycles,total_cycles,256.0/total_cycles,(256.0/total_cycles)*64.0*0.15);
      $display("PASS: M3 matched group32 lane case=%0d",CASE_ID);end
     $finish;end
   end
   if(error||cycle>10000)begin
    $display("FAIL: M3 case=%0d error=%0d timeout=%0d sent=%0d received=%0d in_count=%0d out_count=%0d in_ready=%0d out_valid=%0d",
      CASE_ID,error,(cycle>10000),sent,received,in_count,out_count,in_ready,out_valid);
    $finish;end
  end
 end
endmodule
module m3_mac_only_tb;m3_lane_tb#(.CASE_ID(0))t();endmodule
module m3_scalecode_tb;m3_lane_tb#(.CASE_ID(1))t();endmodule
module m3_fp16_tb;m3_lane_tb#(.CASE_ID(2))t();endmodule
module m3_fp32_tb;m3_lane_tb#(.CASE_ID(3))t();endmodule

// Unparameterized simulation tops keep XSim's SAIF instance identifiers free
// of parameter strings.  Vivado read_saif cannot parse the quotes and commas
// that XSim emits when a parameterized module itself is the simulation top.
module m3_power_sc_tb;
 m3_lane_tb #(.CASE_ID(1),
  .DATA_DIR("/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/data"),
  .CLOCK_PERIOD_PS(10000)) t();
endmodule
module m3_power_fp16_tb;
 m3_lane_tb #(.CASE_ID(2),
  .DATA_DIR("/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/data"),
  .CLOCK_PERIOD_PS(10000)) t();
endmodule
module m3_power_fp32_tb;
 m3_lane_tb #(.CASE_ID(3),
  .DATA_DIR("/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment/experiment/00_scale_apply_microkernel/legacy_seed/data"),
  .CLOCK_PERIOD_PS(10000)) t();
endmodule
