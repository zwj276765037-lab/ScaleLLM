`timescale 1ns/1ps
module hap_mlp_gu_rec576_parser_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,job_clear=0,begin_valid=0,in_valid=0,in_last=0,wr_ready=0;
 reg [1:0] begin_opcode=1;
 reg [255:0] in_data;
 wire begin_ready,in_ready,wr_valid,done,quiescent,error;
 wire [8:0] wr_group;wire [4095:0] wr_u8x16x32;wire [383:0] wr_meta_u24x16;
 wire [31:0] error_code,accepted_input_bytes;
 hap_mlp_gu_rec576_parser dut(.*);
 integer writes=0,mode=0,seed=27;reg force_hold=0;
 reg [4607:0] record;
 function [7:0] value(input integer g,input integer r,input integer l);value=(g*19+r*23+l*7)&255;endfunction
 function [23:0] meta(input integer g,input integer r);meta={2'b0,6'(r+1),8'(g%255+1),8'(r+g)};endfunction
 always @(negedge clk)begin
  if(rst_n&&!job_clear)wr_ready=!force_hold&&($random(seed)&3)!=0;else wr_ready=0;
 end
 always @(posedge clk)if(wr_valid&&wr_ready)begin
  if(mode!=0&&!(mode==5&&writes<17))$fatal(1,"bad record propagated");
  if(wr_group!=writes)$fatal(1,"group order");
  for(integer r=0;r<16;r=r+1)begin
   for(integer l=0;l<32;l=l+1)if(wr_u8x16x32[r*256+l*8+:8]!==value(writes,r,l))$fatal(1,"payload");
   if(wr_meta_u24x16[r*24+:24]!==meta(writes,r))$fatal(1,"metadata crossing beat");
  end
  writes=writes+1;
 end
 task clear_job;begin
 @(negedge clk);job_clear=1;in_valid=0;begin_valid=0;
 @(negedge clk);job_clear=0;writes=0;
 end endtask
 task start(input integer op);begin
 @(negedge clk);begin_opcode=op;begin_valid=1;@(posedge clk);if(!begin_ready)$fatal(1,"begin not ready");
 @(negedge clk);begin_valid=0;
 end endtask
 task send_group(input integer g,input integer total);begin
 record=0;
 for(integer r=0;r<16;r=r+1)begin
 for(integer l=0;l<32;l=l+1)record[r*256+l*8+:8]=value(g,r,l);
 record[4096+r*24+:24]=meta(g,r);
 end
 if((mode==1&&g==0)||(mode==5&&g==17))record[4480]=1;
 if(mode==2&&g==0)record[4096+10*24+22]=1;
 if(mode==3&&g==0)record[4096+5*24+8+:8]=0;
 for(integer b=0;b<18;b=b+1)begin
 @(negedge clk);in_valid=1;in_data=record[b*256+:256];in_last=g==total-1&&b==17;
 if(mode==4&&g==0&&b==0)in_last=1;
 while(!in_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);in_valid=0;in_last=0;
 end
 end endtask
 initial begin
 repeat(3)@(negedge clk);rst_n=1;
 for(integer op=1;op<=1;op=op+1)begin
 start(op);for(integer g=0;g<128;g=g+1)send_group(g,128);
 while(!quiescent)@(negedge clk);
 if(error||writes!=128||accepted_input_bytes!=73728)$fatal(1,"valid counts");
 clear_job();
 end
 start(2);if(!error||error_code!=32'h1010||!quiescent||wr_valid||in_ready)$fatal(1,"DOWN parser admission");clear_job();
 for(mode=1;mode<=5;mode=mode+1)begin
 start(1);for(integer g=0;g<128;g=g+1)send_group(g,128);
 while(!quiescent)@(negedge clk);
 if(!error||writes!=(mode==5?17:0)||accepted_input_bytes!=(mode==5?17*576:0)||error_code!=(mode==5?32'h2001:32'h2000+mode))$fatal(1,"error mode %0d code %h",mode,error_code);
 clear_job();
 end
 mode=0;start(1);
 for(integer g=0;g<127;g=g+1)send_group(g,128);
 while(writes!=127||wr_valid)@(negedge clk);
 force_hold=1;send_group(127,128);
 while(!wr_valid)@(negedge clk);
 repeat(23)begin @(negedge clk);if(accepted_input_bytes!=127*576||done||writes!=127)$fatal(1,"uncommitted last record counted");end
 force_hold=0;while(!quiescent)@(negedge clk);
 if(writes!=128||accepted_input_bytes!=73728||error)$fatal(1,"last record commit");clear_job();
 $display("parser groups valid=256 malformed-drained=640 prefix-committed=17 final-record-stall=23");
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
 initial begin #2000000;$fatal(1,"watchdog");end
endmodule
