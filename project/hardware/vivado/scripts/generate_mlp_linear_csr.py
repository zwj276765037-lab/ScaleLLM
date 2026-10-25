from pathlib import Path
import re,json
hw=Path(__file__).resolve().parents[2]
x=json.loads((hw/'source/mlp_linear/abi.json').read_text())
s=(hw/'rtl/integration/hap_mlp_axil_control.sv').read_text();head=s[:s.index('    localparam [31:0] FULL_FORMAT_ID')].replace('module hap_mlp_axil_control','module hap_mlp_linear_axil_control')
extra='''    output reg submit_valid,input wire submit_ready,output reg [543:0] submit_descriptor,
    input wire submit_result_valid,output wire submit_result_ready,input wire [31:0] submit_error,
    output reg epoch_valid,output reg [31:0] epoch_id,output wire [543:0] config_descriptor,
    input wire epoch_result_valid,input wire [31:0] epoch_error,
    output reg ack_valid,output reg [31:0] ack_id,input wire ack_result_valid,input wire ack_error,
    output reg abort_valid,output reg [31:0] abort_id,input wire abort_result_valid,input wire abort_error,
    input wire job_busy,input wire job_completion_valid,input wire job_quiescent,input wire job_reset_required,input wire [7:0] job_phase,
    input wire [543:0] done_descriptor,input wire [31:0] done_error,input wire [31:0] done_input_bytes,input wire [31:0] done_output_bytes,input wire [31:0] done_records,
    input wire [31:0] job_load_cycles,input wire [31:0] job_compute_cycles,input wire [31:0] job_store_cycles,input wire [31:0] job_stall_cycles,input wire [31:0] active_epoch,
'''
head=head.replace('    output wire          irq,',extra+'\n    output wire          irq,')
# These legacy outputs retain their config observation only; job actions use the new channels.
for n in ['mlp_command_valid','mlp_command_bank','mlp_gate_ddr0_base_addr','mlp_gate_ddr1_base_addr','mlp_down_ddr0_base_addr','mlp_down_ddr1_base_addr','mlp_input_base_addr','mlp_output_base_addr','mlp_command_id','mlp_layer_id','tensor_load_valid','tensor_store_valid']:
 head=re.sub(r'(output) reg(\s+(?:\[31:0\]\s+)?)('+n+r'\b)',r'\1 wire\2\3',head)
body='''    reg [543:0] config_r;
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
'''
alias={'mlp_command_id':'command_id','mlp_layer_id':'layer_id','mlp_input_base_addr':'input_base','mlp_output_base_addr':'output_base','mlp_gate_ddr0_base_addr':'gate_half0_base','mlp_gate_ddr1_base_addr':'gate_half1_base','mlp_down_ddr0_base_addr':'down_half0_base','mlp_down_ddr1_base_addr':'down_half1_base'}
flds={f['name']:f for f in x['descriptor']['fields']}
for n,f in alias.items():body+=f'    assign {n}=config_r[{flds[f]["lsb"]}+:32];\n'
body+='''    function [7:0] legacy_status(input [31:0] code);
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
'''
for f in x['descriptor']['fields']:
 body+=f'            12\'h{f["csr"]:03x}:config_r[{f["lsb"]}+:32]<=merge(config_r[{f["lsb"]}+:32],wdata,wstrb);\n'
body+='''            12'h108:begin if(wstrb[0]&&owner_request_ready&&!admission_pause&&wdata[31:2]==0)begin owner_request<=wdata[1:0];owner_request_valid<=1;owner_done<=0;end else bresp<=2;end
            12'h110:begin
              if(wstrb==15&&wdata==2&&!maintenance_request_pending&&!maintenance_busy&&!owner_protocol_error)begin mlp_clear_pulse<=1;owner_done<=0;end
              else reject(32'h1003);
            end
            12'h13c:if(merge(0,wdata,wstrb)!=0)bresp<=2;
            12'h150:begin if(wstrb[0]&&wdata[31:1]==0)begin meta_load_bank<=wdata[0];meta_commit_bank<=wdata[0];end else bresp<=2;end
            12'h158:meta_commit_generation<=merge(meta_commit_generation,wdata,wstrb);
            12'h16c:meta_gate_base_addr<=merge(meta_gate_base_addr,wdata,wstrb);
            12'h170:meta_down_base_addr<=merge(meta_down_base_addr,wdata,wstrb);
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
'''
read_map={
0x10c:"{ddr1_outstanding,ddr0_outstanding,9'd0,owner_done,owner_request_ready,mlp_launch_enable,attention_launch_enable,owner_switch_pending,active_owner}",
0x114:"{19'd0,meta_error,owner_protocol_error,meta_bank_valid,meta_active_bank,mlp_input_bank_ready,mlp_phase,error_sticky,done_sticky,job_busy}",
0x13c:'0',0x144:'meta_active_generation',0x148:'done_error',0x14c:"{27'd0,meta_bank_loading,meta_bank_valid,meta_active_bank}",0x150:"{31'd0,meta_commit_bank}",0x158:'meta_commit_generation',0x15c:'meta_gate_write_count_bank0',0x160:'meta_gate_write_count_bank1',0x164:'meta_down_write_count_bank0',0x168:'meta_down_write_count_bank1',0x16c:'meta_gate_base_addr',0x170:'meta_down_base_addr',0x174:'0',0x178:"{16'd0,meta_dma_phase,tensor_dma_phase,meta_dma_done,tensor_dma_done,meta_dma_error,tensor_dma_error,meta_dma_busy,tensor_store_armed,tensor_dma_busy}",0x17c:'tensor_input_beat_count',0x244:'tensor_input_group_count',0x248:'tensor_output_beat_count',0x24c:'tensor_output_tile_count',0x250:'meta_dma_gate_record_count',0x254:'meta_dma_down_record_count',0x258:'meta_dma_physical_bytes[31:0]',0x25c:'meta_dma_physical_bytes[63:32]',0x260:"{26'd0,paired_quiescent,maintenance_busy,owner_protocol_error,owner_switch_pending,active_owner}",
0x264:'paired_attn_bursts',0x268:'paired_mlp_bursts',0x26c:'paired_both_cycles',0x270:'paired_hol0',0x274:'paired_hol1',0x278:'paired_hwm0',0x27c:'paired_hwm1',
0x288:'done_descriptor[32+:32]',0x28c:'done_descriptor[0+:32]',0x290:'done_descriptor[64+:32]',0x294:'done_descriptor[96+:32]',0x298:"{5'd0,legacy_status(done_error),3'd1,done_descriptor[80+:16]}",0x29c:"{30'd0,job_busy,job_completion_valid}",0x2a0:"{31'd0,(admission_error!=0)}",0x2a4:'job_compute_cycles',0x2a8:"{30'd0,maintenance_request_pending,1'b0}",0x2ac:'mlp_down_output_saturation_count',0x2b0:'mlp_total_shift_format_count',0x2b4:'mlp_numeric_status',
0x324:"{16'd0,job_phase,3'd0,job_reset_required,job_quiescent,error_sticky,job_completion_valid,job_busy}",
0x328:'done_descriptor[128+:32]',0x32c:'done_descriptor[320+:32]',0x330:'done_descriptor[384+:32]',0x334:'done_descriptor[352+:32]',0x338:'done_descriptor[0+:32]',0x33c:'done_descriptor[32+:32]',0x340:'done_descriptor[64+:32]',0x344:'done_descriptor[96+:32]',0x348:'done_input_bytes',0x34c:'done_output_bytes',0x350:'done_error',0x354:'job_compute_cycles',0x358:'job_load_cycles',0x35c:'job_store_cycles',0x360:'job_stall_cycles',0x364:'done_records',0x368:'active_epoch',0x370:'admission_error',0x378:'0',0x37c:'0'}
for f in x['descriptor']['fields']:read_map[f['csr']]=f'config_r[{f["lsb"]}+:32]'
for reg in x['registers']:
 if reg['access']=='RO' and reg['offset'] not in read_map:read_map[reg['offset']]=f"32'h{reg['reset']:08x}"
for addr,exp in sorted(read_map.items()):body+=f"            12'h{addr:03x}:rdata<={exp};\n"
body+='''            default:begin
              if(s_axil_araddr>=12'h180&&s_axil_araddr<=12'h240&&s_axil_araddr[1:0]==0)rdata<=mlp_telemetry[((s_axil_araddr-12'h180)>>2)*32+:32];
              else begin rdata<=0;rresp<=2;end
            end
          endcase
        end
      end
    end
endmodule
'''
(hw/'rtl/integration/hap_mlp_linear_axil_control.sv').write_text(head+body)
