`timescale 1ns/1ps
// GU-only ordered URAM request/response adapter, depth-two FF boundary.
module hap_mlp_gu_metadata_scheduler #(
    parameter integer GATE_RECORDS = 229376,
    parameter integer GATE_ADDR_W = 18,
    parameter integer RESPONSE_FIFO_DEPTH = 2,
    parameter integer PRODUCTION_SHAPE = 1
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       clear,
    input  wire                       command_start,
    input  wire                       command_done,
    input wire [1:0]                  command_opcode,
    output wire                       drained,
    input  wire                       gate_enable,

    output wire                       gate_rd_valid,
    input  wire                       gate_rd_ready,
    output wire [GATE_ADDR_W-1:0]     gate_rd_addr,
    input  wire                       gate_rsp_valid,
    output wire                       gate_rsp_ready,
    input  wire [223:0]               gate_rsp_meta,
    output wire                       gate_meta_valid,
    input  wire                       gate_meta_ready,
    output wire [223:0]               gate_meta,


    output wire                       active,
    output reg  [31:0]                gate_issue_count,
    output reg  [31:0]                gate_delivery_count,
    output reg                        done,
    output reg                        error
);
 reg active_r,started_r;
 wire[31:0] expected_gate=started_r?GATE_RECORDS:0;
 (* ram_style="registers",shreg_extract="no" *) reg[223:0]gate_fifo_slot0_r,gate_fifo_slot1_r;
 reg gate_fifo_wr_ptr_r,gate_fifo_rd_ptr_r;reg[1:0]gate_fifo_count_r;
 wire rd_fire=gate_rd_valid&&gate_rd_ready;
 wire rsp_fire=gate_rsp_valid&&gate_rsp_ready;
 wire meta_fire=gate_meta_valid&&gate_meta_ready;
 assign active=active_r;
 assign drained=gate_issue_count==expected_gate&&gate_delivery_count==expected_gate&&
   gate_fifo_count_r==0&&!gate_rsp_valid;
 assign gate_rd_valid=active_r&&gate_enable&&gate_issue_count<expected_gate;
 assign gate_rd_addr=gate_issue_count[GATE_ADDR_W-1:0];
 assign gate_rsp_ready=active_r&&gate_enable&&gate_fifo_count_r<2;
 assign gate_meta_valid=active_r&&gate_enable&&gate_fifo_count_r!=0;
 assign gate_meta=gate_fifo_rd_ptr_r?gate_fifo_slot1_r:gate_fifo_slot0_r;
 always @(posedge clk)if(rsp_fire)begin
  if(gate_fifo_wr_ptr_r)gate_fifo_slot1_r<=gate_rsp_meta;else gate_fifo_slot0_r<=gate_rsp_meta;
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   active_r<=0;started_r<=0;gate_issue_count<=0;gate_delivery_count<=0;
   gate_fifo_wr_ptr_r<=0;gate_fifo_rd_ptr_r<=0;gate_fifo_count_r<=0;done<=0;error<=0;
  end else if(clear)begin
   active_r<=0;started_r<=0;gate_issue_count<=0;gate_delivery_count<=0;
   gate_fifo_wr_ptr_r<=0;gate_fifo_rd_ptr_r<=0;gate_fifo_count_r<=0;done<=0;error<=0;
  end else begin
   done<=0;
   if(command_start)begin
    if(active_r||command_opcode!=1)error<=1;
    else begin
     active_r<=1;started_r<=1;gate_issue_count<=0;gate_delivery_count<=0;
     gate_fifo_wr_ptr_r<=0;gate_fifo_rd_ptr_r<=0;gate_fifo_count_r<=0;error<=0;
    end
   end
   if(rd_fire)gate_issue_count<=gate_issue_count+1'b1;
   if(meta_fire)gate_delivery_count<=gate_delivery_count+1'b1;
   if(rsp_fire)gate_fifo_wr_ptr_r<=gate_fifo_wr_ptr_r+1'b1;
   if(meta_fire)gate_fifo_rd_ptr_r<=gate_fifo_rd_ptr_r+1'b1;
   case({rsp_fire,meta_fire})
    2'b10:gate_fifo_count_r<=gate_fifo_count_r+1'b1;
    2'b01:gate_fifo_count_r<=gate_fifo_count_r-1'b1;
    default:gate_fifo_count_r<=gate_fifo_count_r;
   endcase
   if(command_done)begin
    active_r<=0;done<=1;
    if(gate_issue_count+rd_fire!=expected_gate||gate_delivery_count+meta_fire!=expected_gate||
      (gate_rsp_valid&&!rsp_fire)||({1'b0,gate_fifo_count_r}+rsp_fire-meta_fire)!=0)error<=1;
   end
   if((meta_fire&&gate_delivery_count>=expected_gate)||gate_fifo_count_r>2)error<=1;
  end
 end
 initial begin
  if(PRODUCTION_SHAPE&&(GATE_RECORDS!=229376||GATE_ADDR_W!=18))$error("GU metadata production shape");
  if(RESPONSE_FIFO_DEPTH!=2||GATE_RECORDS<=0||GATE_RECORDS>229376)$error("GU metadata structural shape");
 end
endmodule
