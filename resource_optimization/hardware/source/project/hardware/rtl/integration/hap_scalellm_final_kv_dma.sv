`timescale 1ns/1ps
// One outstanding AXI256 command. Append acknowledgement means successful B,
// never merely acceptance of the final stream record. Prefix records remain
// tagged by the captured command/epoch until scratch accepts them.
module hap_scalellm_final_kv_dma (
 input wire clk,input wire rst_n,input wire clear,input wire begin_command,
 input wire [31:0] command_id,input wire [5:0] layer_id,input wire [15:0] active_mask,
 input wire [127:0] row_positions,input wire [511:0] row_epochs,
 input wire append_valid,output wire append_ready,input wire [31:0] append_command,
 input wire [5:0] append_layer,input wire [3:0] append_slot,input wire [31:0] append_epoch,
 input wire [6:0] append_position,input wire append_is_v,input wire [2:0] append_head,
 input wire [1:0] append_group,input wire [383:0] append_s12,input wire [15:0] append_meta,input wire append_last,
 output wire commit_valid,input wire commit_ready,output wire [31:0] commit_command,
 output wire [5:0] commit_layer,output wire [511:0] commit_epochs,output wire commit_success,
 input wire request_valid,output wire request_ready,input wire [31:0] request_command,
 input wire [5:0] request_layer,input wire [3:0] request_slot,input wire [31:0] request_epoch,input wire [7:0] request_length,
 output wire load_valid,input wire load_ready,output wire [31:0] load_command,
 output wire [4:0] load_layer,output wire [3:0] load_slot,output wire [31:0] load_epoch,
 output wire [6:0] load_position,output wire load_is_v,output wire [2:0] load_head,output wire [1:0] load_group,
 output wire [383:0] load_s12,output wire [15:0] load_meta,output wire load_last,output wire load_error,
 output wire dma_cmd_valid,input wire dma_cmd_ready,output wire dma_cmd_write,
 output wire [31:0] dma_cmd_base,output wire [31:0] dma_cmd_beats,input wire dma_done,input wire dma_error,
 input wire dma_rd_valid,output wire dma_rd_ready,input wire [255:0] dma_rd_data,
 output wire dma_wr_valid,input wire dma_wr_ready,output wire [255:0] dma_wr_data,
 output reg error,output wire idle,output reg [31:0] append_count,output reg [31:0] reload_count
);
 localparam[3:0]IDLE=0,APPEND=1,W_CMD=2,W_DATA=3,W_WAIT=4,COMMIT=5,REQUEST=6,R_CMD=7,R_DATA=8,R_WAIT=9,FAULT=10;
 reg[3:0]state;
 reg[31:0]command_r,base_r;reg[5:0]layer_r;reg[15:0]mask_r;
 reg[127:0]positions_r;reg[511:0]epochs_r;
 reg[1023:0]seen_r;reg[10:0]expected_r;
 reg[511:0]record_r;reg half_r,last_append_r;
 reg[3:0]slot_r;reg[31:0]epoch_r;reg[7:0]length_r;
 reg[13:0]record_index_r;reg read_half_r,record_valid_r,read_done_r;reg[511:0]read_record_r;
 wire[9:0]append_index={append_slot,append_is_v,append_head,append_group};
 wire append_identity=append_command==command_r&&append_layer==layer_r&&mask_r[append_slot]&&
  append_epoch==epochs_r[append_slot*32+:32]&&append_position==positions_r[append_slot*8+:8];
 wire[13:0]expected_records={length_r,6'd0};
 wire append_fire=append_valid&&append_ready;
 wire load_fire=load_valid&&load_ready;
 integer i;reg[10:0]popcount;
 always @*begin popcount=0;for(i=0;i<16;i=i+1)popcount=popcount+active_mask[i];end
 assign idle=state==IDLE||state==REQUEST;
 assign append_ready=state==APPEND&&!error;
 assign commit_valid=state==COMMIT&&!error;
 assign commit_command=command_r;assign commit_layer=layer_r;assign commit_epochs=epochs_r;assign commit_success=!error;
 assign request_ready=state==REQUEST&&!error;
 assign load_valid=state==R_DATA&&record_valid_r;
 assign load_command=command_r;assign load_layer=layer_r[4:0];assign load_slot=slot_r;assign load_epoch=epoch_r;
 assign load_position=record_index_r[12:6];assign load_is_v=record_index_r[5];
 assign load_head=record_index_r[4:2];assign load_group=record_index_r[1:0];
 assign load_s12=read_record_r[383:0];assign load_meta=read_record_r[399:384];
 assign load_last=record_index_r+1==expected_records;
 assign load_error=read_record_r[511:400]!=0||dma_error;
 assign dma_cmd_valid=state==W_CMD||state==R_CMD;
 assign dma_cmd_write=state==W_CMD;assign dma_cmd_base=base_r;
 assign dma_cmd_beats=state==W_CMD?32'd2:({24'd0,length_r}<<7);
 assign dma_wr_valid=state==W_DATA;assign dma_wr_data=half_r?record_r[511:256]:record_r[255:0];
 assign dma_rd_ready=(state==R_DATA&&!record_valid_r)||state==FAULT;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;command_r<=0;layer_r<=0;mask_r<=0;positions_r<=0;epochs_r<=0;
   seen_r<=0;expected_r<=0;record_r<=0;half_r<=0;last_append_r<=0;base_r<=0;
   slot_r<=0;epoch_r<=0;length_r<=0;record_index_r<=0;read_half_r<=0;record_valid_r<=0;read_done_r<=0;read_record_r<=0;
   error<=0;append_count<=0;reload_count<=0;
  end else if(clear)begin
   state<=IDLE;seen_r<=0;error<=0;append_count<=0;reload_count<=0;record_valid_r<=0;read_half_r<=0;read_done_r<=0;
  end else begin
   if(dma_error)error<=1;
   if(dma_done&&(state==R_DATA||state==R_WAIT))read_done_r<=1;
   case(state)
    IDLE:if(begin_command)begin
     command_r<=command_id;layer_r<=layer_id;mask_r<=active_mask;positions_r<=row_positions;epochs_r<=row_epochs;
     expected_r<=popcount<<6;append_count<=0;reload_count<=0;seen_r<=0;error<=0;state<=APPEND;
    end
    APPEND:if(append_fire)begin
     if(!append_identity||seen_r[append_index]||append_last!=(append_count+1==expected_r))begin error<=1;state<=FAULT;end
     else begin
      seen_r[append_index]<=1;append_count<=append_count+1;
      record_r<={112'd0,append_meta,append_s12};last_append_r<=append_last;half_r<=0;
      base_r<=32'h60000000+({26'd0,append_layer}<<23)+({28'd0,append_slot}<<19)+
        ({25'd0,append_position}<<12)+({31'd0,append_is_v}<<11)+({29'd0,append_head}<<8)+({30'd0,append_group}<<6);
      state<=W_CMD;
     end
    end
    W_CMD:if(dma_cmd_ready)state<=W_DATA;
    W_DATA:if(dma_wr_valid&&dma_wr_ready)begin if(half_r)state<=W_WAIT;else half_r<=1;end
    W_WAIT:if(dma_done)begin
     if(dma_error||error)begin error<=1;state<=FAULT;end
     else if(last_append_r)state<=COMMIT;
     else state<=APPEND;
    end
    COMMIT:if(commit_valid&&commit_ready)state<=REQUEST;
    REQUEST:if(request_valid&&request_ready)begin
     if(request_command!=command_r||request_layer!=layer_r||!mask_r[request_slot]||
       request_epoch!=epochs_r[request_slot*32+:32]||request_length!={1'b0,positions_r[request_slot*8+:7]}+1'b1||
       request_length==0||request_length>128)begin error<=1;state<=FAULT;end
     else begin
      slot_r<=request_slot;epoch_r<=request_epoch;length_r<=request_length;
      base_r<=32'h60000000+({26'd0,layer_r}<<23)+({28'd0,request_slot}<<19);
      record_index_r<=0;read_half_r<=0;record_valid_r<=0;state<=R_CMD;
     end
    end
    R_CMD:if(dma_cmd_ready)begin state<=R_DATA;read_done_r<=0;end
    R_DATA:begin
     if(dma_rd_valid&&dma_rd_ready)begin
      if(!read_half_r)begin read_record_r[255:0]<=dma_rd_data;read_half_r<=1;end
      else begin read_record_r[511:256]<=dma_rd_data;read_half_r<=0;record_valid_r<=1;end
     end
     if(load_fire)begin
      record_valid_r<=0;reload_count<=reload_count+1;
      if(load_error)begin error<=1;state<=FAULT;end
      else if(load_last)state<=R_WAIT;
      else record_index_r<=record_index_r+1;
     end
    end
    R_WAIT:if(read_done_r&&!dma_error&&!error)state<=REQUEST;
    FAULT:begin end
    default:begin state<=FAULT;error<=1;end
   endcase
  end
 end
endmodule
