`timescale 1ns/1ps
module hap_mlp_linear_job_fault_priority_tb;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,hard_clear=0,submit_valid=0,submit_result_ready=1,epoch_valid=0,ack_valid=0,abort_valid=0;
 reg [543:0] submit_descriptor=0,epoch_descriptor=0;
 reg [31:0] epoch_id=9,ack_id=0,abort_id=0;
 reg admission_enable=1,maintenance_pending=0,meta_active_bank=1,meta_valid=1,meta_loading=0,meta_commit_pending=0;
 reg [31:0] meta_generation=7;
 reg paths_quiescent=1,paths_error=0,paths_reset_required=0;
 reg [31:0] paths_error_code=0;
 wire submit_ready,submit_result_valid,epoch_result_valid,ack_result_valid,ack_error,abort_result_valid,abort_error;
 wire [31:0] submit_error,epoch_error;
 wire job_clear,cache_begin_valid,cache_seal_valid,load_valid,store_valid,compute_valid,busy,completion_valid,reset_required,maintenance_request;
 wire [543:0] active_descriptor,done_descriptor;
 wire [31:0] done_error,done_input_bytes,done_output_bytes,done_records,load_cycles,compute_cycles,store_cycles,stall_cycles,active_epoch;
 wire [7:0] phase;
 reg cache_begin_ready=1,cache_seal_ready=1,cache_sealed=0,load_ready=1,load_done=0,store_ready=1,store_armed=0,store_done=0,compute_ready=1,compute_done=0,stall=0;
 reg [31:0] input_bytes=0,output_bytes=0,record_count=0;
 integer begins=0,loads=0,stores=0,computes=0,clears=0,cycles=0;
 // Independent edge counts from public handshakes, never DUT internal flags.
 integer observed_compute_cycles=0,observed_store_cycles=0,observed_stall_cycles=0;
 reg observed_compute_active=0,observed_store_active=0;
 always @(posedge clk)begin
  if(!rst_n||job_clear)begin
   observed_compute_cycles=0;observed_store_cycles=0;observed_stall_cycles=0;
   observed_compute_active=0;observed_store_active=0;
  end else begin
   if(compute_valid&&compute_ready)observed_compute_active=1;
   if(store_valid&&store_ready)observed_store_active=1;
   if(phase>=2&&phase<=5)begin
    if(observed_compute_active)observed_compute_cycles=observed_compute_cycles+1;
    if(observed_store_active)observed_store_cycles=observed_store_cycles+1;
    if(stall)observed_stall_cycles=observed_stall_cycles+1;
   end
   if(compute_done)observed_compute_active=0;
  end
 end
 hap_mlp_linear_job_control #(.COMMAND_TIMEOUT_CYCLES(80))dut(.*);
 always @(posedge clk)begin
 cycles<=cycles+1;if(cycles>10000)$fatal(1,"watchdog");
 if(job_clear)begin cache_sealed<=0;store_armed<=0;clears<=clears+1;end
 if(cache_begin_valid&&cache_begin_ready)begins<=begins+1;
 if(cache_seal_valid&&cache_seal_ready)cache_sealed<=1;
 if(load_valid&&load_ready)loads<=loads+1;
 if(store_valid&&store_ready)begin stores<=stores+1;store_armed<=1;end
 if(compute_valid&&compute_ready)computes<=computes+1;
 end
 function [543:0] descriptor(input integer op,id,bid);
 reg [543:0] d;reg[31:0] b;begin
 d=0;b=32'h10000000+bid*32'h800000;
 d[0+:32]=id;d[32+:32]=32'h1234;d[64+:32]={16'(bid),16'(bid/3)};d[96+:32]=2;d[128+:32]=op;d[160+:32]=32'h48384605;
 d[192+:32]=b+(op==1?0:32'h300000);d[224+:32]=b+(op==1?32'h100000:32'h400000);
 d[256+:32]=op==1?73728:258048;d[288+:32]=op==1?1376256:262144;
 d[320+:32]=id+1;d[352+:32]=7;d[384+:32]=9;d[448+:32]=32'h1c00000;d[480+:32]=32'h3800000;d[512+:32]=32'h4600000;
 descriptor=d;end endfunction
 task commit_epoch(input integer code);begin
 @(negedge clk);epoch_valid=1;@(posedge clk);@(negedge clk);epoch_valid=0;
 if(!epoch_result_valid||epoch_error!=code)$fatal(1,"epoch result %h expected%h",epoch_error,code);
 end endtask
 task submit(input [543:0] d,input integer code);begin
 @(negedge clk);submit_descriptor=d;submit_valid=1;while(!submit_ready)@(negedge clk);
 @(posedge clk);@(negedge clk);submit_valid=0;
 while(!submit_result_valid)@(negedge clk);
 if(submit_error!=code)$fatal(1,"admission result %h expected%h",submit_error,code);
 @(negedge clk);
 end endtask
 task ack(input integer id,input integer bad);begin
 @(negedge clk);ack_id=id;ack_valid=1;@(posedge clk);@(negedge clk);ack_valid=0;
 if(!ack_result_valid||ack_error!=bad)$fatal(1,"ack result");
 @(negedge clk);
 end endtask
 task finish_job(input integer op,input integer expected_error);begin
 wait(loads>stores);@(negedge clk);paths_quiescent=0;
 repeat(5)@(negedge clk);input_bytes=op==1?73728:258048;load_done=1;
 @(negedge clk);load_done=0;
 wait(compute_valid&&compute_ready);@(negedge clk);
 for(integer edge_index=0;edge_index<11;edge_index=edge_index+1)begin @(negedge clk);stall=(edge_index%3)==0;end
 stall=0;record_count=op==1?1792:256;compute_done=1;
 @(negedge clk);compute_done=0;
 repeat(31)begin @(negedge clk);if(completion_valid)$fatal(1,"completion before final B");end
 output_bytes=op==1?1376256:262144;store_done=1;
 @(negedge clk);store_done=0;
 repeat(7)begin @(negedge clk);if(completion_valid)$fatal(1,"completion before all paths drain");end
 paths_quiescent=1;
 wait(completion_valid);@(negedge clk);
 if(compute_cycles!=observed_compute_cycles||store_cycles!=observed_store_cycles||stall_cycles!=observed_stall_cycles||observed_stall_cycles==0)
  $fatal(1,"inclusive counters compute %0d/%0d store %0d/%0d stall %0d/%0d",compute_cycles,observed_compute_cycles,store_cycles,observed_store_cycles,stall_cycles,observed_stall_cycles);
 if(done_error!=expected_error||done_input_bytes!=input_bytes||done_output_bytes!=output_bytes||done_records!=record_count||busy||reset_required)$fatal(1,"completion fields");
 end endtask
 task reset_case;
 begin
  @(negedge clk);rst_n=0;hard_clear=0;submit_valid=0;epoch_valid=0;ack_valid=0;abort_valid=0;
  paths_error=0;paths_reset_required=0;paths_error_code=0;paths_quiescent=1;maintenance_pending=0;
  load_done=0;compute_done=0;store_done=0;stall=0;cache_sealed=0;store_armed=0;
  input_bytes=0;output_bytes=0;record_count=0;meta_generation=7;meta_active_bank=1;epoch_id=9;
  repeat(3)@(negedge clk);rst_n=1;epoch_descriptor=descriptor(1,1,0);commit_epoch(0);
 end endtask
 task prepare_drain(input integer id);
 integer before_load,before_compute;
 begin
  before_load=loads;before_compute=computes;submit(descriptor(1,id,0),0);
  wait(loads>before_load);@(negedge clk);paths_quiescent=0;input_bytes=73728;load_done=1;
  @(negedge clk);load_done=0;wait(computes>before_compute);@(negedge clk);
  record_count=1792;output_bytes=1376256;compute_done=1;store_done=1;
  @(negedge clk);compute_done=0;store_done=0;wait(phase==5);
 end endtask
 task safe_clear_and_ack(input integer id);
 begin
  @(negedge clk);paths_error=0;paths_reset_required=0;paths_quiescent=1;hard_clear=1;
  @(negedge clk);hard_clear=0;ack(id,0);
 end endtask
 initial begin
 repeat(3)@(negedge clk);rst_n=1;epoch_descriptor=descriptor(1,1,0);
 commit_epoch(0);if(active_epoch!=9)$fatal(1,"epoch not active");
 begin : reject_vectors
 reg [543:0] d;
 d=descriptor(0,1,0);submit(d,32'h1010);if(loads!=0||completion_valid)$fatal(1,"reject side effect");
 d=descriptor(1,1,0);d[256+:32]=73729;submit(d,32'h1013);
 d=descriptor(1,1,0);d[192+:32]=32'h80000000;submit(d,32'h1014);
 d=descriptor(1,1,0);d[96+:32]=3;submit(d,32'h1023);
 end
 for(integer n=0;n<4;n=n+1)begin
 submit(descriptor(n%2+1,n+10,n<2?0:3),0);
 // Configuration/candidate stimulus changes cannot alter the active snapshot.
 submit_descriptor=0;
 if(active_descriptor[0+:32]!=n+10)$fatal(1,"active descriptor changed");
 finish_job(n%2+1,0);
 repeat(5)begin @(negedge clk);if(done_descriptor[0+:32]!=n+10||done_error)$fatal(1,"snapshot unstable");end
 submit(descriptor(1,99,0),32'h1005);commit_epoch(32'h1023);
 ack(n+99,1);if(!completion_valid)$fatal(1,"wrong ACK released");
 ack(n+10,0);if(completion_valid||active_epoch!=9||!meta_valid||meta_generation!=7)$fatal(1,"ACK damaged epoch/meta");
 input_bytes=0;output_bytes=0;record_count=0;
 end
 if(begins!=4||loads!=4||stores!=4||computes!=4)$fatal(1,"same epoch four jobs counts");
 // Result backpressure is a real channel, not a one-cycle notification.
 submit_result_ready=0;submit(descriptor(1,30,0),0);
 repeat(4)begin @(negedge clk);if(!submit_result_valid||submit_error)$fatal(1,"submit result lost");end
 submit_result_ready=1;
 wait(compute_valid&&compute_ready); // Load must be completed by explicit events below.
 end
 initial begin : tail
 wait(active_descriptor[0+:32]==30&&phase==2);
 wait(load_valid&&load_ready);@(negedge clk);paths_quiescent=0;input_bytes=73728;load_done=1;
 @(negedge clk);load_done=0;
 wait(compute_valid&&compute_ready);@(negedge clk);
 abort_id=999;abort_valid=1;@(negedge clk);abort_valid=0;if(!abort_error)$fatal(1,"bad abort accepted");
 abort_id=30;abort_valid=1;@(negedge clk);abort_valid=0;if(abort_error)$fatal(1,"matching abort refused");
 compute_done=1;record_count=1792;output_bytes=1376256;store_done=1;@(negedge clk);compute_done=0;store_done=0;paths_quiescent=1;
 wait(completion_valid);@(negedge clk);
 if(done_error!=32'h2201||!maintenance_request)$fatal(1,"abort result");
 maintenance_pending=1;ack(30,1);
 hard_clear=1;@(negedge clk);hard_clear=0;maintenance_pending=0;
 if(!completion_valid||done_error!=32'h2201||active_epoch!=0)$fatal(1,"hard clear lost abort snapshot");
 ack(30,0);
 // Active metadata switch invalidates a committed epoch.
 epoch_id=10;commit_epoch(0);meta_generation=8;@(negedge clk);
 if(active_epoch!=0)$fatal(1,"metadata switch kept epoch");
 // Accepted ABORT and successful DRAIN retirement on the same edge.
 reset_case();prepare_drain(40);
 @(negedge clk);paths_quiescent=1;abort_id=40;abort_valid=1;
 @(negedge clk);abort_valid=0;
 if(!completion_valid||done_error!=32'h2201||abort_error||done_descriptor[0+:32]!=40)$fatal(1,"same-edge ABORT lost to success");
 safe_clear_and_ack(40);
 // Earlier ABORT remains first error when LOAD later reports bad padding.
 reset_case();submit(descriptor(1,41,0),0);
 @(negedge clk);paths_quiescent=0;abort_id=41;abort_valid=1;
 @(negedge clk);abort_valid=0;paths_error=1;paths_error_code=32'h2001;load_done=1;input_bytes=4032;
 @(negedge clk);load_done=0;paths_quiescent=1;wait(completion_valid);@(negedge clk);
 if(done_error!=32'h2201||done_input_bytes!=4032)$fatal(1,"LOAD overwrote earlier ABORT");
 safe_clear_and_ack(41);
 // A recoverable sticky error cannot disable the active-command watchdog.
 reset_case();submit(descriptor(1,42,0),0);
 @(negedge clk);paths_quiescent=0;paths_error=1;paths_error_code=32'h2001;input_bytes=4032;
 wait(reset_required);@(negedge clk);
 if(!completion_valid||done_error!=32'h2001||done_descriptor[0+:32]!=42||done_input_bytes!=4032||!busy)$fatal(1,"recoverable-error watchdog/first-error snapshot");
 input_bytes=9999;repeat(3)@(negedge clk);
 if(done_input_bytes!=4032||done_error!=32'h2001)$fatal(1,"FAULT snapshot changed after timeout");
 safe_clear_and_ack(42);
 // New path error outranks a newly accepted ABORT on the same LOAD edge.
 reset_case();submit(descriptor(1,44,0),0);
 @(negedge clk);paths_quiescent=0;paths_error=1;paths_error_code=32'h2001;abort_id=44;abort_valid=1;load_done=1;
 @(negedge clk);abort_valid=0;load_done=0;paths_quiescent=1;wait(completion_valid);@(negedge clk);
 if(done_error!=32'h2001)$fatal(1,"simultaneous new path error priority");
 safe_clear_and_ack(44);
 // Late fatal and matching ACK on one edge must preserve the existing DONE.
 reset_case();prepare_drain(43);@(negedge clk);paths_quiescent=1;wait(completion_valid);@(negedge clk);
 if(done_error!=0)$fatal(1,"late-fatal setup expected successful DONE");
 paths_error=1;paths_reset_required=1;paths_error_code=32'h2110;ack_id=43;ack_valid=1;
 @(negedge clk);ack_valid=0;
 if(!ack_error||!reset_required||!completion_valid||done_error!=0||done_descriptor[0+:32]!=43||done_input_bytes!=73728||job_clear)$fatal(1,"late fatal ACK/DONE severity");
 safe_clear_and_ack(43);
 // Idle fatal with a stale old descriptor never creates a task completion.
 @(negedge clk);paths_error=1;paths_reset_required=1;paths_error_code=32'h2110;paths_quiescent=0;
 @(negedge clk);if(!reset_required||completion_valid)$fatal(1,"idle fatal fabricated DONE");
 submit(descriptor(1,45,0),32'h1007);
 @(negedge clk);paths_error=0;paths_reset_required=0;paths_quiescent=1;hard_clear=1;
 @(negedge clk);hard_clear=0;
 if(completion_valid||phase!=0)$fatal(1,"idle-fatal hard_clear used stale owner");
 // A fatal arriving with START must return an admission result, never hang.
 reset_case();@(negedge clk);paths_error=1;paths_reset_required=1;paths_error_code=32'h2110;paths_quiescent=0;
 submit_descriptor=descriptor(1,46,0);submit_valid=1;
 @(negedge clk);submit_valid=0;
 if(!submit_result_valid||submit_error!=32'h1007||completion_valid||job_clear)$fatal(1,"simultaneous fatal START lost response or fabricated owner");
 $display("job priority: same-edge ABORT/path/ACK, first-cause watchdog, late+idle transport severity/ownership; inclusive counters retained");
 $display("HARDWARE_AGENT_SIM_PASS");$finish;
 end
endmodule
