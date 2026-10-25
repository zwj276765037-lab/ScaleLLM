`timescale 1ns/1ps
module hap_mlp_gu_cache16_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,job_clear=0,begin_valid=0,wr_valid=0,seal_valid=0,rd_req_valid=0,rd_rsp_ready=0;
 reg [1:0] begin_opcode=1;
 reg [8:0] wr_group=0,rd_req_group=0;
 reg [4095:0] wr_u8x16x32;
 reg [383:0] wr_meta_u24x16;
 wire begin_ready,wr_ready,seal_ready,sealed,rd_req_ready,rd_rsp_valid,owned,quiescent,error;
 wire [8:0] rd_rsp_group,write_count,expected_groups;
 wire [4095:0] rd_rsp_u8x16x32;
 wire [383:0] rd_rsp_meta_u24x16;
 wire [31:0] error_code;
 hap_mlp_gu_cache16 dut(.*);
 integer g,r,l,k,groups,checks=0;
 function [7:0] value(input integer group_id,input integer row_id,input integer lane_id);
 value=(group_id*17+row_id*13+lane_id*3)&255;endfunction
 function [23:0] meta(input integer group_id,input integer row_id);
 meta={2'b0,6'(group_id%32),8'(row_id+1),8'(group_id+row_id)};endfunction
 task clear_job;begin
 @(negedge clk);job_clear=1;@(negedge clk);job_clear=0;
 if(owned||sealed||error||write_count)$fatal(1,"clear failed");
 end endtask
 task begin_job(input integer op);begin
 @(negedge clk);begin_opcode=op;begin_valid=1;
 @(posedge clk);if(!begin_ready)$fatal(1,"begin stalled");
 @(negedge clk);begin_valid=0;
 end endtask
 task write_group(input integer group_id);begin
 @(negedge clk);wr_group=group_id;
 for(r=0;r<16;r=r+1)begin
 for(l=0;l<32;l=l+1)wr_u8x16x32[r*256+l*8+:8]=value(group_id,r,l);
 wr_meta_u24x16[r*24+:24]=meta(group_id,r);
 end
 wr_valid=1;@(posedge clk);if(!wr_ready)$fatal(1,"write stalled");
 @(negedge clk);wr_valid=0;
 end endtask
 task read_group(input integer group_id);reg [4095:0] hold_data;begin
 @(negedge clk);rd_req_group=group_id;rd_req_valid=1;
 while(!rd_req_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);rd_req_valid=0;
 while(!rd_rsp_valid)@(negedge clk);
 hold_data=rd_rsp_u8x16x32;
 for(k=0;k<7;k=k+1)begin
 @(negedge clk);if(!rd_rsp_valid||rd_rsp_group!=group_id||rd_rsp_u8x16x32!==hold_data)$fatal(1,"response changed under stall");
 end
 for(r=0;r<16;r=r+1)begin
 for(l=0;l<32;l=l+1)if(rd_rsp_u8x16x32[r*256+l*8+:8]!==value(group_id,r,l))$fatal(1,"payload group%0d row%0d lane%0d",group_id,r,l);
 if(rd_rsp_meta_u24x16[r*24+:24]!==meta(group_id,r))$fatal(1,"meta mismatch");
 end
 rd_rsp_ready=1;@(posedge clk);@(negedge clk);rd_rsp_ready=0;checks=checks+1;
 end endtask
 initial begin
 repeat(3)@(negedge clk);rst_n=1;
 for(integer test=0;test<2;test=test+1)begin
 groups=128;begin_job(1);
 if(expected_groups!=groups)$fatal(1,"opcode group count");
 rd_req_valid=1;repeat(2)begin @(negedge clk);if(rd_req_ready)$fatal(1,"read before seal");end rd_req_valid=0;
 for(g=0;g<groups;g=g+1)write_group(g);
 @(negedge clk);seal_valid=1;@(posedge clk);if(!seal_ready)$fatal(1,"seal stalled");@(negedge clk);seal_valid=0;
 if(!sealed||write_count!=groups||wr_ready||begin_ready)$fatal(1,"seal owner state");
 // Permutation covers every legal GU address; range tests exercise both upper address bits.
 for(g=0;g<groups;g=g+1)read_group((g*73)%groups);
 if(error||!quiescent)$fatal(1,"legal replay failed");
 rd_req_group=(test==0?128:256);rd_req_valid=1;@(posedge clk);@(negedge clk);rd_req_valid=0;
 if(!error||rd_rsp_valid)$fatal(1,"out-of-range read not rejected");
 clear_job();
 end
 begin_job(1);write_group(0);
 @(negedge clk);seal_valid=1;@(posedge clk);@(negedge clk);seal_valid=0;
 if(!error||sealed)$fatal(1,"short seal not rejected");clear_job();
 begin_job(1);write_group(1);
 if(!error||write_count!=0)$fatal(1,"bad group wrote cache");clear_job();
 begin_job(1);write_group(128);
 if(!error||write_count!=0)$fatal(1,"group128 aliased group0");clear_job();
 begin_job(1);write_group(256);
 if(!error||write_count!=0)$fatal(1,"high group aliased group0");clear_job();
 begin_job(2);if(!error||owned||begin_ready||error_code!=32'h1010)$fatal(1,"DOWN opcode accepted");clear_job();
 begin_job(0);if(!error||owned||begin_ready)$fatal(1,"illegal opcode");clear_job();
 if(checks!=256)$fatal(1,"coverage count");
 $display("cache replay checks=%0d",checks);
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
 initial begin #1000000;$fatal(1,"watchdog");end
endmodule
