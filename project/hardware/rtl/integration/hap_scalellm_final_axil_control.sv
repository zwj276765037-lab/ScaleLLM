`timescale 1ns/1ps
// Independent AW/W capture; immutable active/completion descriptors.
module hap_scalellm_final_axil_control (
 input wire clk,input wire rst_n,
 input wire [11:0] s_axil_awaddr,input wire s_axil_awvalid,output wire s_axil_awready,
 input wire [31:0] s_axil_wdata,input wire [3:0] s_axil_wstrb,input wire s_axil_wvalid,output wire s_axil_wready,
 output reg [1:0] s_axil_bresp,output reg s_axil_bvalid,input wire s_axil_bready,
 input wire [11:0] s_axil_araddr,input wire s_axil_arvalid,output wire s_axil_arready,
 output reg [31:0] s_axil_rdata,output reg [1:0] s_axil_rresp,output reg s_axil_rvalid,input wire s_axil_rready,
 output reg submit_valid,input wire submit_ready,output reg [2047:0] submit_descriptor,
 input wire result_valid,input wire [31:0] result_error,input wire result_reset_required,
 input wire [31:0] result_input_bytes,input wire [31:0] result_output_bytes,input wire [31:0] result_cycles,
 output reg abort_valid,output wire busy,output reg completion_valid,output reg reset_required,
 output wire irq
);
 `include "hap_scalellm_final_abi.svh"
 reg [31:0] shadow[0:63];
 reg [2047:0] completion_descriptor;
 reg [31:0] ack_id,abort_id,admission_error,done_error,done_input,done_output,done_cycles;
 reg running;
 reg aw_pending,w_pending;
 reg [11:0] awaddr_r;
 reg [31:0] wdata_r;
 reg [3:0] wstrb_r;
 integer i;
 wire write_fire=aw_pending&&w_pending&&!s_axil_bvalid;
 wire accept_abort_now=write_fire&&wstrb_r==4'hf&&awaddr_r==12'h020&&
  wdata_r==FINAL_ACTION_ABORT&&running&&abort_id==submit_descriptor[64+:32];
 assign s_axil_awready=!aw_pending&&!s_axil_bvalid;
 assign s_axil_wready=!w_pending&&!s_axil_bvalid;
 assign s_axil_arready=!s_axil_rvalid;
 assign busy=running;
 assign irq=completion_valid||reset_required;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   aw_pending<=0;w_pending<=0;s_axil_bvalid<=0;s_axil_bresp<=0;
   s_axil_rvalid<=0;s_axil_rdata<=0;s_axil_rresp<=0;
   submit_valid<=0;submit_descriptor<=0;completion_descriptor<=0;
   abort_valid<=0;running<=0;completion_valid<=0;reset_required<=0;
   ack_id<=0;abort_id<=0;admission_error<=0;done_error<=0;done_input<=0;done_output<=0;done_cycles<=0;
   awaddr_r<=0;wdata_r<=0;wstrb_r<=0;
   for(i=0;i<64;i=i+1)shadow[i]<=0;
  end else begin
   if(submit_valid&&submit_ready)submit_valid<=0;
   // Sticky per-command abort ownership survives pending submit and result
   // races. Only an admitted fresh START (or hard reset) clears the owner.
   if(s_axil_awvalid&&s_axil_awready)begin aw_pending<=1;awaddr_r<=s_axil_awaddr;end
   if(s_axil_wvalid&&s_axil_wready)begin w_pending<=1;wdata_r<=s_axil_wdata;wstrb_r<=s_axil_wstrb;end
   if(s_axil_bvalid&&s_axil_bready)s_axil_bvalid<=0;
   if(s_axil_rvalid&&s_axil_rready)s_axil_rvalid<=0;
   if(result_valid&&running)begin
    running<=0;completion_valid<=1;completion_descriptor<=submit_descriptor;
    done_error<=(abort_valid||accept_abort_now)?FINAL_ERR_ABORTED:result_error;
    done_input<=result_input_bytes;done_output<=result_output_bytes;done_cycles<=result_cycles;
    reset_required<=reset_required||result_reset_required;
   end
   if(write_fire)begin
    aw_pending<=0;w_pending<=0;s_axil_bvalid<=1;s_axil_bresp<=0;
    if(wstrb_r!=4'hf||awaddr_r[1:0]!=0)begin s_axil_bresp<=2;admission_error<=FINAL_ERR_BAD_STROBE;end
    else if(awaddr_r>=12'h400&&awaddr_r<12'h500)shadow[awaddr_r[7:2]]<=wdata_r;
    else case(awaddr_r)
     12'h028:ack_id<=wdata_r;
     12'h040:abort_id<=wdata_r;
     12'h02c:begin
      if(wdata_r==0)admission_error<=0;
      else begin s_axil_bresp<=2;admission_error<=FINAL_ERR_BAD_ACTION;end
     end
     12'h020:begin
      case(wdata_r)
       FINAL_ACTION_START:begin
        if(reset_required)begin s_axil_bresp<=2;admission_error<=FINAL_ERR_RESET_REQUIRED;end
        else if(running||!submit_ready)begin s_axil_bresp<=2;admission_error<=FINAL_ERR_BUSY;end
        else if(completion_valid)begin s_axil_bresp<=2;admission_error<=FINAL_ERR_COMPLETION_PENDING;end
        else begin
         for(i=0;i<64;i=i+1)submit_descriptor[i*32+:32]<=shadow[i];
         submit_valid<=1;running<=1;admission_error<=0;abort_valid<=0;
        end
       end
       FINAL_ACTION_ACK:begin
        if(!completion_valid||ack_id!=completion_descriptor[64+:32])begin
         s_axil_bresp<=2;admission_error<=FINAL_ERR_STALE_ACK;
        end else begin completion_valid<=0;admission_error<=0;end
       end
       FINAL_ACTION_ABORT:begin
        if(!running||abort_id!=submit_descriptor[64+:32])begin
         s_axil_bresp<=2;admission_error<=FINAL_ERR_STALE_ABORT;
        end else begin abort_valid<=1;admission_error<=0;end
       end
       default:begin s_axil_bresp<=2;admission_error<=FINAL_ERR_BAD_ACTION;end
      endcase
     end
     default:begin s_axil_bresp<=2;admission_error<=FINAL_ERR_BAD_ACTION;end
    endcase
   end
   if(s_axil_arvalid&&s_axil_arready)begin
    s_axil_rvalid<=1;s_axil_rresp<=0;s_axil_rdata<=0;
    if(s_axil_araddr[1:0]!=0)s_axil_rresp<=2;
    else if(s_axil_araddr>=12'h400&&s_axil_araddr<12'h500)s_axil_rdata<=shadow[s_axil_araddr[7:2]];
    else if(s_axil_araddr>=12'h500&&s_axil_araddr<12'h600)s_axil_rdata<=completion_descriptor[s_axil_araddr[7:2]*32+:32];
    else case(s_axil_araddr)
     12'h000:s_axil_rdata<=FINAL_ID_MAGIC;
     12'h004:s_axil_rdata<=FINAL_ID_ABI;
     12'h008:s_axil_rdata<=FINAL_ID_CAPABILITIES;
     12'h00c:s_axil_rdata<=FINAL_ID_CORE_HZ;
     12'h010:s_axil_rdata<=FINAL_ID_ATTENTION_LAYOUT;
     12'h014:s_axil_rdata<=FINAL_ID_MLP_LAYOUT;
     12'h018:s_axil_rdata<=FINAL_ID_ATTENTION_FORMAT;
     12'h01c:s_axil_rdata<=FINAL_ID_MLP_FORMAT;
     12'h024:s_axil_rdata<={29'd0,reset_required,completion_valid,running};
     12'h028:s_axil_rdata<=ack_id;
     12'h02c:s_axil_rdata<=admission_error;
     12'h030:s_axil_rdata<=done_error;
     12'h034:s_axil_rdata<=done_input;
     12'h038:s_axil_rdata<=done_output;
     12'h03c:s_axil_rdata<=done_cycles;
     12'h040:s_axil_rdata<=abort_id;
     default:s_axil_rresp<=2;
    endcase
   end
  end
 end
endmodule
