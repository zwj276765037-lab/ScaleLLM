`timescale 1ns / 1ps

// Local 4-KiB AXI-Lite control plane.  Production address routing reserves
// 0x000..0x0ff for the signed-off Attention v3 ABI and sends 0x100..0x2ff to
// this block without changing the address value.
module hap_mlp_gu_axil_control #(
    parameter integer PRODUCTION_INTEGRATION = 0,
    parameter integer COMMAND_TIMEOUT_CYCLES = 10000000
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire [11:0]   s_axil_awaddr,
    input  wire          s_axil_awvalid,
    output wire          s_axil_awready,
    input  wire [31:0]   s_axil_wdata,
    input  wire [3:0]    s_axil_wstrb,
    input  wire          s_axil_wvalid,
    output wire          s_axil_wready,
    output wire [1:0]    s_axil_bresp,
    output wire          s_axil_bvalid,
    input  wire          s_axil_bready,
    input  wire [11:0]   s_axil_araddr,
    input  wire          s_axil_arvalid,
    output wire          s_axil_arready,
    output wire [31:0]   s_axil_rdata,
    output wire [1:0]    s_axil_rresp,
    output wire          s_axil_rvalid,
    input  wire          s_axil_rready,

    output reg           owner_request_valid,
    input  wire          owner_request_ready,
    input  wire          admission_pause,
    output reg  [1:0]    owner_request,
    input  wire          owner_request_done,
    input  wire [1:0]    active_owner,
    input  wire          owner_switch_pending,
    input  wire          attention_launch_enable,
    input  wire          mlp_launch_enable,
    input  wire          owner_protocol_error,
    input  wire [7:0]    ddr0_outstanding,
    input  wire [7:0]    ddr1_outstanding,
    input  wire          maintenance_busy,
    input  wire          maintenance_request_pending,
    input  wire          mlp_abort_complete,
    input  wire          paired_quiescent,
    input  wire [31:0]   paired_attn_bursts,
    input  wire [31:0]   paired_mlp_bursts,
    input  wire [31:0]   paired_both_cycles,
    input  wire [31:0]   paired_hol0,
    input  wire [31:0]   paired_hol1,
    input  wire [31:0]   paired_hwm0,
    input  wire [31:0]   paired_hwm1,

    output wire           mlp_command_valid,
    input  wire          mlp_command_ready,
    output reg           mlp_clear_pulse,
    output wire          mlp_abort_pending,
    output wire           mlp_command_bank,
    output wire  [31:0]   mlp_gate_ddr0_base_addr,
    output wire  [31:0]   mlp_gate_ddr1_base_addr,
    output wire  [31:0]   mlp_down_ddr0_base_addr,
    output wire  [31:0]   mlp_down_ddr1_base_addr,
    output wire  [31:0]   mlp_input_base_addr,
    output wire  [31:0]   mlp_output_base_addr,
    output wire  [31:0]   mlp_command_id,
    output wire  [31:0]   mlp_layer_id,
    input  wire [1:0]    mlp_input_bank_ready,
    input  wire          mlp_busy,
    input  wire          mlp_done,
    input  wire          mlp_error,
    input  wire [2:0]    mlp_phase,
    input  wire [1567:0] mlp_telemetry,
    input  wire [31:0]   mlp_down_output_saturation_count,
    input  wire [31:0]   mlp_total_shift_format_count,
    input  wire [31:0]   mlp_numeric_status,

    output wire           tensor_load_valid,
    input  wire          tensor_load_ready,
    output wire           tensor_store_valid,
    input  wire          tensor_store_ready,
    input  wire          tensor_store_armed,
    input  wire          tensor_dma_busy,
    input  wire          tensor_dma_done,
    input  wire          tensor_dma_error,
    input  wire [2:0]    tensor_dma_phase,
    input  wire [31:0]   tensor_input_beat_count,
    input  wire [31:0]   tensor_input_group_count,
    input  wire [31:0]   tensor_output_beat_count,
    input  wire [31:0]   tensor_output_tile_count,

    output reg  [31:0]   meta_gate_base_addr,
    output reg  [31:0]   meta_down_base_addr,
    input  wire          meta_dma_busy,
    input  wire          meta_dma_done,
    input  wire          meta_dma_error,
    input  wire [2:0]    meta_dma_phase,
    input  wire [31:0]   meta_dma_gate_record_count,
    input  wire [31:0]   meta_dma_down_record_count,
    input  wire [63:0]   meta_dma_physical_bytes,

    output reg           meta_load_begin_valid,
    input  wire          meta_load_begin_ready,
    output reg           meta_load_bank,
    output reg           meta_commit_valid,
    input  wire          meta_commit_ready,
    output reg           meta_commit_bank,
    output reg  [31:0]   meta_commit_generation,
    input  wire          meta_active_bank,
    input  wire [31:0]   meta_active_generation,
    input  wire [1:0]    meta_bank_valid,
    input  wire [1:0]    meta_bank_loading,
    input  wire [31:0]   meta_gate_write_count_bank0,
    input  wire [31:0]   meta_gate_write_count_bank1,
    input  wire [31:0]   meta_down_write_count_bank0,
    input  wire [31:0]   meta_down_write_count_bank1,
    input  wire          meta_error,

    output reg submit_valid,input wire submit_ready,output reg [543:0] submit_descriptor,
    input wire submit_result_valid,output wire submit_result_ready,input wire [31:0] submit_error,
    output reg epoch_valid,output reg [31:0] epoch_id,output wire [543:0] config_descriptor,
    input wire epoch_result_valid,input wire [31:0] epoch_error,
    output reg ack_valid,output reg [31:0] ack_id,input wire ack_result_valid,input wire ack_error,
    output reg abort_valid,output reg [31:0] abort_id,input wire abort_result_valid,input wire abort_error,
    input wire job_busy,input wire job_completion_valid,input wire job_quiescent,input wire job_reset_required,input wire [7:0] job_phase,
    input wire [543:0] done_descriptor,input wire [31:0] done_error,input wire [31:0] done_input_bytes,input wire [31:0] done_output_bytes,input wire [31:0] done_records,
    input wire [31:0] job_load_cycles,input wire [31:0] job_compute_cycles,input wire [31:0] job_store_cycles,input wire [31:0] job_stall_cycles,input wire [31:0] active_epoch,

    output wire          irq,
    output wire          done_sticky,
    output wire          error_sticky
);
    reg [543:0] config_r;
    reg aw_hold,w_hold,bvalid,rvalid;
    reg [11:0] awaddr;
    reg [31:0] wdata,rdata;
    reg [3:0] wstrb;
    reg [1:0] bresp,rresp;
    reg [2:0] waiting;
    reg [31:0] admission_error;
    reg owner_done;
    assign config_descriptor=config_r;
    assign submit_result_ready=waiting==1;
    assign s_axil_awready=rst_n&&!aw_hold&&!bvalid&&waiting==0;
    assign s_axil_wready=rst_n&&!w_hold&&!bvalid&&waiting==0;
    assign s_axil_bvalid=bvalid;assign s_axil_bresp=bresp;
    assign s_axil_arready=rst_n&&!rvalid;
    assign s_axil_rvalid=rvalid;assign s_axil_rresp=rresp;assign s_axil_rdata=rdata;
    assign irq=job_completion_valid||job_reset_required;
    assign done_sticky=job_completion_valid;assign error_sticky=(job_completion_valid&&done_error!=0)||job_reset_required||(job_busy&&(mlp_error||tensor_dma_error||meta_error||meta_dma_error));
    assign mlp_command_valid=0;assign mlp_command_bank=0;
    assign tensor_load_valid=0;assign tensor_store_valid=0;assign mlp_abort_pending=0;
    assign mlp_command_id=config_r[0+:32];
    assign mlp_layer_id=config_r[96+:32];
    assign mlp_input_base_addr=config_r[192+:32];
    assign mlp_output_base_addr=config_r[224+:32];
    assign mlp_gate_ddr0_base_addr=config_r[416+:32];
    assign mlp_gate_ddr1_base_addr=config_r[448+:32];
    assign mlp_down_ddr0_base_addr=config_r[480+:32];
    assign mlp_down_ddr1_base_addr=config_r[512+:32];
    function [7:0] legacy_status(input [31:0] code);
      begin
      if(code==0)legacy_status=0;
      else if(code>=32'h2100&&code<32'h2200)legacy_status=2;
      else if(code==32'h2050||code==32'h2051)legacy_status=3;
      else if(code==32'h2200)legacy_status=4;
      else if(code==32'h2201||code==32'h2202)legacy_status=5;
      else legacy_status=1;
      end
    endfunction
    function [31:0] merge(input [31:0] old,input [31:0] val,input [3:0] strb);
      integer i;begin merge=old;for(i=0;i<4;i=i+1)if(strb[i])merge[i*8+:8]=val[i*8+:8];end
    endfunction
    task reject(input [31:0] code);begin bresp<=2'b10;if(admission_error==0)admission_error<=code;end endtask
    always @(posedge clk)begin
      if(!rst_n)begin
        config_r<=0;config_r[160+:32]<=32'h48384605;
        aw_hold<=0;w_hold<=0;bvalid<=0;rvalid<=0;awaddr<=0;wdata<=0;wstrb<=0;rdata<=0;bresp<=0;rresp<=0;waiting<=0;admission_error<=0;
        owner_request_valid<=0;owner_request<=0;owner_done<=0;mlp_clear_pulse<=0;
        meta_gate_base_addr<=0;meta_down_base_addr<=0;meta_load_begin_valid<=0;meta_load_bank<=0;meta_commit_valid<=0;meta_commit_bank<=0;meta_commit_generation<=0;
        submit_valid<=0;submit_descriptor<=0;epoch_valid<=0;epoch_id<=0;ack_valid<=0;ack_id<=0;abort_valid<=0;abort_id<=0;
      end else begin
        owner_request_valid<=0;mlp_clear_pulse<=0;meta_load_begin_valid<=0;meta_commit_valid<=0;epoch_valid<=0;ack_valid<=0;abort_valid<=0;
        if(owner_request_done)owner_done<=1;
        if(submit_valid&&submit_ready)submit_valid<=0;
        if(bvalid&&s_axil_bready)bvalid<=0;
        if(rvalid&&s_axil_rready)rvalid<=0;
        if(s_axil_awvalid&&s_axil_awready)begin aw_hold<=1;awaddr<=s_axil_awaddr;end
        if(s_axil_wvalid&&s_axil_wready)begin w_hold<=1;wdata<=s_axil_wdata;wstrb<=s_axil_wstrb;end
        if(waiting==1&&submit_result_valid)begin waiting<=0;bvalid<=1;bresp<=0;if(submit_error!=0)reject(submit_error);end
        if(waiting==2&&epoch_result_valid)begin waiting<=0;bvalid<=1;bresp<=0;if(epoch_error!=0)reject(epoch_error);end
        if(waiting==3&&ack_result_valid)begin waiting<=0;bvalid<=1;bresp<=ack_error?2'b10:2'b00;end
        if(waiting==4&&abort_result_valid)begin waiting<=0;bvalid<=1;bresp<=abort_error?2'b10:2'b00;end
        if(aw_hold&&w_hold&&!bvalid&&waiting==0)begin
          aw_hold<=0;w_hold<=0;bvalid<=1;bresp<=0;
          case(awaddr)
            12'h118:config_r[0+:32]<=merge(config_r[0+:32],wdata,wstrb);
            12'h280:config_r[32+:32]<=merge(config_r[32+:32],wdata,wstrb);
            12'h284:config_r[64+:32]<=merge(config_r[64+:32],wdata,wstrb);
            12'h11c:config_r[96+:32]<=merge(config_r[96+:32],wdata,wstrb);
            12'h30c:config_r[128+:32]<=merge(config_r[128+:32],wdata,wstrb);
            12'h120:config_r[160+:32]<=merge(config_r[160+:32],wdata,wstrb);
            12'h124:config_r[192+:32]<=merge(config_r[192+:32],wdata,wstrb);
            12'h128:config_r[224+:32]<=merge(config_r[224+:32],wdata,wstrb);
            12'h310:config_r[256+:32]<=merge(config_r[256+:32],wdata,wstrb);
            12'h314:config_r[288+:32]<=merge(config_r[288+:32],wdata,wstrb);
            12'h318:config_r[320+:32]<=merge(config_r[320+:32],wdata,wstrb);
            12'h140:config_r[352+:32]<=merge(config_r[352+:32],wdata,wstrb);
            12'h31c:config_r[384+:32]<=merge(config_r[384+:32],wdata,wstrb);
            12'h12c:config_r[416+:32]<=merge(config_r[416+:32],wdata,wstrb);
            12'h130:config_r[448+:32]<=merge(config_r[448+:32],wdata,wstrb);
            12'h134:if(merge(0,wdata,wstrb)!=0)bresp<=2;
            12'h138:if(merge(0,wdata,wstrb)!=0)bresp<=2;
            12'h108:begin if(wstrb[0]&&owner_request_ready&&!admission_pause&&wdata[31:2]==0)begin owner_request<=wdata[1:0];owner_request_valid<=1;owner_done<=0;end else bresp<=2;end
            12'h110:begin
              if(wstrb==15&&wdata==2&&!maintenance_request_pending&&!maintenance_busy&&!owner_protocol_error)begin mlp_clear_pulse<=1;owner_done<=0;end
              else reject(32'h1003);
            end
            12'h13c:if(merge(0,wdata,wstrb)!=0)bresp<=2;
            12'h150:begin if(wstrb[0]&&wdata[31:1]==0)begin meta_load_bank<=wdata[0];meta_commit_bank<=wdata[0];end else bresp<=2;end
            12'h158:meta_commit_generation<=merge(meta_commit_generation,wdata,wstrb);
            12'h16c:meta_gate_base_addr<=merge(meta_gate_base_addr,wdata,wstrb);
            12'h170:if(merge(0,wdata,wstrb)!=0)bresp<=2;
            12'h154:begin
              if(wstrb[1:0]!=3||admission_pause||job_reset_required||wdata[31:2]!=0||wdata==0||wdata==3)bresp<=2;
              else if(wdata==1&&meta_load_begin_ready&&meta_gate_base_addr[4:0]==0&&meta_down_base_addr[4:0]==0)meta_load_begin_valid<=1;
              else if(wdata==2&&!job_busy&&!job_completion_valid&&meta_commit_ready)meta_commit_valid<=1;
              else bresp<=2;
            end
            12'h174:reject(32'h1003);
            12'h320:begin
              if(wstrb!=15)reject(32'h1002);
              else if(wdata==1)begin submit_descriptor<=config_r;submit_valid<=1;waiting<=1;bvalid<=0;end
              else if(wdata==4)begin abort_id<=config_r[0+:32];abort_valid<=1;waiting<=4;bvalid<=0;end
              else reject(32'h1001);
            end
            12'h36c:begin if(wstrb!=15)reject(32'h1002);else begin epoch_id<=wdata;epoch_valid<=1;waiting<=2;bvalid<=0;end end
            12'h2a0:begin if(wstrb!=15)bresp<=2;else begin ack_id<=wdata;ack_valid<=1;waiting<=3;bvalid<=0;end end
            12'h374:begin if(wstrb==15&&wdata==1)admission_error<=0;else bresp<=2;end
            default:bresp<=2;
          endcase
        end
        if(s_axil_arvalid&&s_axil_arready)begin
          rvalid<=1;rresp<=0;rdata<=0;
          case(s_axil_araddr)
            12'h100:rdata<=32'h48384605;
            12'h104:rdata<=32'h00070000;
            12'h10c:rdata<={ddr1_outstanding,ddr0_outstanding,9'd0,owner_done,owner_request_ready,mlp_launch_enable,attention_launch_enable,owner_switch_pending,active_owner};
            12'h114:rdata<={19'd0,meta_error,owner_protocol_error,meta_bank_valid,meta_active_bank,mlp_input_bank_ready,mlp_phase,error_sticky,done_sticky,job_busy};
            12'h118:rdata<=config_r[0+:32];
            12'h11c:rdata<=config_r[96+:32];
            12'h120:rdata<=config_r[160+:32];
            12'h124:rdata<=config_r[192+:32];
            12'h128:rdata<=config_r[224+:32];
            12'h12c:rdata<=config_r[416+:32];
            12'h130:rdata<=config_r[448+:32];
            12'h134:rdata<=0;
            12'h138:rdata<=0;
            12'h13c:rdata<=0;
            12'h140:rdata<=config_r[352+:32];
            12'h144:rdata<=meta_active_generation;
            12'h148:rdata<=done_error;
            12'h14c:rdata<={27'd0,meta_bank_loading,meta_bank_valid,meta_active_bank};
            12'h150:rdata<={31'd0,meta_commit_bank};
            12'h158:rdata<=meta_commit_generation;
            12'h15c:rdata<=meta_gate_write_count_bank0;
            12'h160:rdata<=meta_gate_write_count_bank1;
            12'h164:rdata<=0;
            12'h168:rdata<=0;
            12'h16c:rdata<=meta_gate_base_addr;
            12'h170:rdata<=meta_down_base_addr;
            12'h174:rdata<=0;
            12'h178:rdata<={16'd0,meta_dma_phase,tensor_dma_phase,meta_dma_done,tensor_dma_done,meta_dma_error,tensor_dma_error,meta_dma_busy,tensor_store_armed,tensor_dma_busy};
            12'h17c:rdata<=tensor_input_beat_count;
            12'h244:rdata<=tensor_input_group_count;
            12'h248:rdata<=tensor_output_beat_count;
            12'h24c:rdata<=tensor_output_tile_count;
            12'h250:rdata<=meta_dma_gate_record_count;
            12'h254:rdata<=0;
            12'h258:rdata<=meta_dma_physical_bytes[31:0];
            12'h25c:rdata<=meta_dma_physical_bytes[63:32];
            12'h260:rdata<={26'd0,paired_quiescent,maintenance_busy,owner_protocol_error,owner_switch_pending,active_owner};
            12'h264:rdata<=paired_attn_bursts;
            12'h268:rdata<=paired_mlp_bursts;
            12'h26c:rdata<=paired_both_cycles;
            12'h270:rdata<=paired_hol0;
            12'h274:rdata<=paired_hol1;
            12'h278:rdata<=paired_hwm0;
            12'h27c:rdata<=paired_hwm1;
            12'h280:rdata<=config_r[32+:32];
            12'h284:rdata<=config_r[64+:32];
            12'h288:rdata<=done_descriptor[32+:32];
            12'h28c:rdata<=done_descriptor[0+:32];
            12'h290:rdata<=done_descriptor[64+:32];
            12'h294:rdata<=done_descriptor[96+:32];
            12'h298:rdata<={5'd0,legacy_status(done_error),3'd1,done_descriptor[80+:16]};
            12'h29c:rdata<={30'd0,job_busy,job_completion_valid};
            12'h2a0:rdata<={31'd0,(admission_error!=0)};
            12'h2a4:rdata<=job_compute_cycles;
            12'h2a8:rdata<={30'd0,maintenance_request_pending,1'b0};
            12'h2ac:rdata<=0;
            12'h2b0:rdata<=mlp_total_shift_format_count;
            12'h2b4:rdata<=mlp_numeric_status;
            12'h2b8:rdata<=32'h4d303032;
            12'h300:rdata<=32'h4d4c0002;
            12'h304:rdata<=32'h0000001d;
            12'h308:rdata<=32'h00000001;
            12'h30c:rdata<=config_r[128+:32];
            12'h310:rdata<=config_r[256+:32];
            12'h314:rdata<=config_r[288+:32];
            12'h318:rdata<=config_r[320+:32];
            12'h31c:rdata<=config_r[384+:32];
            12'h324:rdata<={16'd0,job_phase,3'd0,job_reset_required,job_quiescent,error_sticky,job_completion_valid,job_busy};
            12'h328:rdata<=done_descriptor[128+:32];
            12'h32c:rdata<=done_descriptor[320+:32];
            12'h330:rdata<=done_descriptor[384+:32];
            12'h334:rdata<=done_descriptor[352+:32];
            12'h338:rdata<=done_descriptor[0+:32];
            12'h33c:rdata<=done_descriptor[32+:32];
            12'h340:rdata<=done_descriptor[64+:32];
            12'h344:rdata<=done_descriptor[96+:32];
            12'h348:rdata<=done_input_bytes;
            12'h34c:rdata<=done_output_bytes;
            12'h350:rdata<=done_error;
            12'h354:rdata<=job_compute_cycles;
            12'h358:rdata<=job_load_cycles;
            12'h35c:rdata<=job_store_cycles;
            12'h360:rdata<=job_stall_cycles;
            12'h364:rdata<=done_records;
            12'h368:rdata<=active_epoch;
            12'h370:rdata<=admission_error;
            12'h378:rdata<=0;
            12'h37c:rdata<=0;
            default:begin
              if(s_axil_araddr>=12'h180&&s_axil_araddr<=12'h240&&s_axil_araddr[1:0]==0)rdata<=mlp_telemetry[((s_axil_araddr-12'h180)>>2)*32+:32];
              else begin rdata<=0;rresp<=2;end
            end
          endcase
        end
      end
    end
endmodule
