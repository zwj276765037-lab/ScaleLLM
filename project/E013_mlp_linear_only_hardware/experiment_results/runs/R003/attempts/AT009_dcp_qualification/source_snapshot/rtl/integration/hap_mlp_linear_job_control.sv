`timescale 1ns/1ps
module hap_mlp_linear_job_control #(
 parameter integer COMMAND_TIMEOUT_CYCLES=10000000,
 parameter integer GU_OUTPUT_RECORDS=1792,DOWN_OUTPUT_RECORDS=256,
 parameter integer ENFORCE_PRODUCTION_SHAPE=1)(
 input wire clk,input wire rst_n,input wire hard_clear,
 input wire submit_valid,output wire submit_ready,input wire [543:0] submit_descriptor,
 output reg submit_result_valid,input wire submit_result_ready,output reg [31:0] submit_error,
 input wire epoch_valid,input wire [31:0] epoch_id,input wire [543:0] epoch_descriptor,
 output reg epoch_result_valid,output reg [31:0] epoch_error,
 input wire ack_valid,input wire [31:0] ack_id,output reg ack_result_valid,output reg ack_error,
 input wire abort_valid,input wire [31:0] abort_id,output reg abort_result_valid,output reg abort_error,
 input wire admission_enable,input wire maintenance_pending,
 input wire meta_active_bank,input wire [31:0] meta_generation,input wire meta_valid,
 input wire meta_loading,input wire meta_commit_pending,
 input wire paths_quiescent,input wire paths_error,input wire [31:0] paths_error_code,input wire paths_reset_required,
 output reg job_clear,output reg [543:0] active_descriptor,
 output wire cache_begin_valid,input wire cache_begin_ready,
 output wire cache_seal_valid,input wire cache_seal_ready,input wire cache_sealed,
 output wire load_valid,input wire load_ready,input wire load_done,
 output wire store_valid,input wire store_ready,input wire store_armed,input wire store_done,
 output wire compute_valid,input wire compute_ready,input wire compute_done,
 input wire [31:0] input_bytes,input wire [31:0] output_bytes,input wire [31:0] record_count,input wire stall,
 output wire busy,output reg completion_valid,output reg reset_required,output reg [7:0] phase,
 output reg [543:0] done_descriptor,output reg [31:0] done_error,
 output reg [31:0] done_input_bytes,output reg [31:0] done_output_bytes,output reg [31:0] done_records,
 output reg [31:0] load_cycles,output reg [31:0] compute_cycles,output reg [31:0] store_cycles,output reg [31:0] stall_cycles,
 output wire maintenance_request,
 output wire [31:0] active_epoch
);
 localparam IDLE=0,VALIDATE=1,LOAD=2,ARM=3,COMPUTE=4,DRAIN=5,COMPLETE=6,ABORT_DRAIN=7,FAULT=8;
 reg [543:0] candidate_descriptor;
 reg [31:0] epoch_r,epoch_meta;reg epoch_bank,epoch_bound;
 reg [31:0] epoch_layer;reg [127:0] epoch_bases;
 reg begun,load_started,store_started,compute_started,store_seen;
 reg abort_pending,active_owned;reg [31:0] live_error,total_cycles;
 wire [31:0] opcode=active_descriptor[128+:32];
 wire [31:0] expected_records=opcode==1?GU_OUTPUT_RECORDS:DOWN_OUTPUT_RECORDS;
 wire [31:0] candidate_opcode=candidate_descriptor[128+:32];
 wire [31:0] slot_base=32'h10000000+(candidate_descriptor[80+:16]*32'h00800000);
 wire [31:0] expected_in=slot_base+(candidate_opcode==1?0:32'h00300000);
 wire [31:0] expected_out=slot_base+(candidate_opcode==1?32'h00100000:32'h00400000);
 wire canonical_bases=candidate_descriptor[416+:32]==0&&candidate_descriptor[448+:32]==32'h01c00000&&
  candidate_descriptor[480+:32]==32'h03800000&&candidate_descriptor[512+:32]==32'h04600000;
 wire epoch_canonical_bases=epoch_descriptor[416+:32]==0&&epoch_descriptor[448+:32]==32'h01c00000&&
  epoch_descriptor[480+:32]==32'h03800000&&epoch_descriptor[512+:32]==32'h04600000;
 assign maintenance_request=abort_pending&&completion_valid&&phase==COMPLETE;
 assign active_epoch=epoch_bound?epoch_r:0;
 assign busy=phase!=IDLE&&phase!=COMPLETE&&(phase!=FAULT||!paths_quiescent);
 assign submit_ready=rst_n&&!hard_clear&&phase!=VALIDATE&&!submit_result_valid&&!job_clear;
 assign cache_begin_valid=phase==LOAD&&!begun;
 assign load_valid=phase==LOAD&&begun&&!load_started;
 assign cache_seal_valid=phase==ARM&&!cache_sealed;
 assign store_valid=phase==ARM&&cache_sealed&&!store_started;
 assign compute_valid=phase==COMPUTE&&!compute_started&&store_armed;
 wire fatal_now=paths_error&&paths_reset_required;
 wire abort_fire=abort_valid&&active_owned&&busy&&abort_id==active_descriptor[0+:32]&&!reset_required&&!fatal_now;
 wire timeout_now=active_owned&&phase>=LOAD&&phase<=DRAIN&&COMMAND_TIMEOUT_CYCLES>0&&total_cycles>=COMMAND_TIMEOUT_CYCLES-1;
 // Frozen first error wins. New simultaneous sources use the contract order.
 wire [31:0] selected_error=live_error!=0?live_error:paths_error?paths_error_code:
   timeout_now?32'h2200:abort_fire?32'h2201:maintenance_pending?32'h2202:abort_pending?32'h2201:0;
 function [31:0] inc(input [31:0] x);inc=x == 32'hffffffff ? x : x+1;endfunction
 reg [31:0] admission;
 always @*begin
 admission=0;
 if(reset_required||(paths_error&&paths_reset_required))admission=32'h1007;
 else if(completion_valid)admission=32'h1005;
 else if(!admission_enable||maintenance_pending)admission=32'h1006;
 else if(candidate_descriptor[128+:32]!=1&&candidate_descriptor[128+:32]!=2)admission=32'h1010;
 else if(candidate_descriptor[160+:32]!=32'h48384605)admission=32'h1011;
 else if(candidate_descriptor[96+:32]>=32||candidate_descriptor[80+:16]>=6||candidate_descriptor[64+:16]>1||
   candidate_descriptor[80+:16]/3!=candidate_descriptor[64+:16]||candidate_descriptor[320+:32]==0)admission=32'h1012;
 else if(candidate_descriptor[256+:32]!=(candidate_opcode==1?73728:258048)||candidate_descriptor[288+:32]!=(candidate_opcode==1?GU_OUTPUT_RECORDS*768:DOWN_OUTPUT_RECORDS*1024))admission=32'h1013;
 else if(candidate_descriptor[192+:32]!=expected_in||candidate_descriptor[224+:32]!=expected_out||!canonical_bases)admission=32'h1014;
 else if(!meta_valid||meta_loading||meta_commit_pending)admission=32'h1020;
 else if(candidate_descriptor[352+:32]!=meta_generation)admission=32'h1021;
 else if(!epoch_bound||candidate_descriptor[384+:32]==0)admission=32'h1022;
 else if(candidate_descriptor[384+:32]!=epoch_r||candidate_descriptor[96+:32]!=epoch_layer||
   candidate_descriptor[416+:128]!=epoch_bases||meta_generation!=epoch_meta||meta_active_bank!=epoch_bank)admission=32'h1023;
 else if(!paths_quiescent)admission=32'h1004;
 end
 task snapshot(input [31:0] code);begin
 completion_valid<=1;done_descriptor<=active_descriptor;done_error<=code;
 done_input_bytes<=input_bytes;done_output_bytes<=output_bytes;done_records<=record_count;
 end endtask
 always @(posedge clk)begin
 if(!rst_n)begin
 phase<=IDLE;epoch_r<=0;epoch_meta<=0;epoch_bank<=0;epoch_layer<=0;epoch_bases<=0;epoch_bound<=0;
 active_descriptor<=0;candidate_descriptor<=0;done_descriptor<=0;done_error<=0;done_input_bytes<=0;done_output_bytes<=0;done_records<=0;
 submit_result_valid<=0;submit_error<=0;epoch_result_valid<=0;epoch_error<=0;ack_result_valid<=0;ack_error<=0;abort_result_valid<=0;abort_error<=0;
 job_clear<=0;completion_valid<=0;reset_required<=0;active_owned<=0;begun<=0;load_started<=0;store_started<=0;compute_started<=0;store_seen<=0;abort_pending<=0;live_error<=0;
 load_cycles<=0;compute_cycles<=0;store_cycles<=0;stall_cycles<=0;total_cycles<=0;
 end else begin
 job_clear<=0;if(submit_result_valid&&submit_result_ready)submit_result_valid<=0;epoch_result_valid<=0;ack_result_valid<=0;abort_result_valid<=0;
 if(epoch_bound&&(meta_generation!=epoch_meta||meta_active_bank!=epoch_bank))epoch_bound<=0;
 if(hard_clear)begin
 epoch_bound<=0;reset_required<=0;phase<=(completion_valid||active_owned)?COMPLETE:IDLE;job_clear<=1;active_owned<=0;
 if(active_owned&&!completion_valid)snapshot(selected_error!=0?selected_error:32'h2202);
 begun<=0;load_started<=0;store_started<=0;compute_started<=0;store_seen<=0;abort_pending<=0;live_error<=0;
 end else begin
 if(epoch_valid)begin
 epoch_result_valid<=1;epoch_error<=0;
 if(epoch_id==0)epoch_error<=32'h1025;
 else if(epoch_bound&&epoch_id==epoch_r)epoch_error<=32'h1023;
 else if(phase!=IDLE||completion_valid||!paths_quiescent||!admission_enable||maintenance_pending||reset_required||paths_error||!meta_valid||meta_loading||meta_commit_pending||epoch_descriptor[96+:32]>=32||!epoch_canonical_bases)epoch_error<=32'h1024;
 else begin epoch_bound<=1;epoch_r<=epoch_id;epoch_layer<=epoch_descriptor[96+:32];epoch_bases<=epoch_descriptor[416+:128];epoch_meta<=meta_generation;epoch_bank<=meta_active_bank;end
 end
 if(ack_valid)begin
 ack_result_valid<=1;ack_error<=1;
 if(completion_valid&&ack_id==done_descriptor[0+:32]&&!reset_required&&paths_quiescent&&!busy&&!maintenance_pending&&!fatal_now)begin
 ack_error<=0;completion_valid<=0;phase<=IDLE;job_clear<=1;active_owned<=0;
 end
 end
 if(abort_valid)begin
 abort_result_valid<=1;abort_error<=1;
 if(abort_fire)begin abort_error<=0;abort_pending<=1;end
 end
 if(submit_valid&&submit_ready)begin
 if(phase!=IDLE||completion_valid||reset_required||fatal_now)begin submit_result_valid<=1;submit_error<=(reset_required||fatal_now)?32'h1007:completion_valid?32'h1005:32'h1004;end
 else begin candidate_descriptor<=submit_descriptor;phase<=VALIDATE;end
 end
 if(phase==VALIDATE)begin
 submit_result_valid<=1;submit_error<=admission;
 if(admission!=0)phase<=IDLE;
 else begin
 phase<=LOAD;active_owned<=1;active_descriptor<=candidate_descriptor;job_clear<=1;begun<=0;load_started<=0;store_started<=0;compute_started<=0;store_seen<=0;abort_pending<=0;live_error<=0;
 load_cycles<=0;compute_cycles<=0;store_cycles<=0;stall_cycles<=0;total_cycles<=0;
 end
 end
 if(phase>=LOAD&&phase<=DRAIN)begin
 if(maintenance_pending&&!abort_pending)abort_pending<=1;
 if(live_error==0&&selected_error!=0)live_error<=selected_error;
 total_cycles<=inc(total_cycles);if(stall)stall_cycles<=inc(stall_cycles);
 if(phase==LOAD)load_cycles<=inc(load_cycles);
 if((compute_started||(compute_valid&&compute_ready))&&phase<=COMPUTE)compute_cycles<=inc(compute_cycles);
 if(store_started||(store_valid&&store_ready))store_cycles<=inc(store_cycles);
 if(store_done)store_seen<=1;
 if(cache_begin_valid&&cache_begin_ready)begun<=1;
 if(load_valid&&load_ready)load_started<=1;
 if(phase==LOAD&&load_done)begin
 if(paths_error)phase<=DRAIN;
 else phase<=ARM;
 end
 if(store_valid&&store_ready)store_started<=1;
 if(phase==ARM&&store_started&&store_armed)phase<=COMPUTE;
 if(compute_valid&&compute_ready)compute_started<=1;
 if(phase==COMPUTE&&compute_done)phase<=DRAIN;
 if(phase==DRAIN&&paths_quiescent&&((store_seen||store_done)||selected_error!=0))begin
 if(selected_error!=0)snapshot(selected_error);
 else if(input_bytes!=active_descriptor[256+:32]||output_bytes!=active_descriptor[288+:32]||record_count!=expected_records)begin snapshot(32'h2030);reset_required<=1;end
 else snapshot(0);
 phase<=COMPLETE;
 end
 if(timeout_now)begin
 if(!completion_valid)snapshot(selected_error);reset_required<=1;phase<=FAULT;
 end
 end
 // Severity can rise while idle or while an unACKed DONE is held. It never
 // fabricates a task owner or rewrites an existing completion snapshot.
 if(fatal_now)begin
 reset_required<=1;phase<=FAULT;
 if(active_owned&&!completion_valid)snapshot(selected_error);
 end
 end
 end
 end
 initial begin
 if(ENFORCE_PRODUCTION_SHAPE&&(GU_OUTPUT_RECORDS!=1792||DOWN_OUTPUT_RECORDS!=256))$error("linear job production shape required");
 if(GU_OUTPUT_RECORDS<=0||GU_OUTPUT_RECORDS>1792||(GU_OUTPUT_RECORDS%2)!=0||DOWN_OUTPUT_RECORDS<=0||DOWN_OUTPUT_RECORDS>256)$error("linear job test shape invalid");
 end
endmodule
