from pathlib import Path
import re,json,hashlib,datetime
root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware')
src=(root/'rtl/attention/hap_attention_board_cohort16_core.sv').read_text().split('localparam')[0]
ports=re.findall(r'input\s+(?:wire\s+)?(?:\[([^]]+)\]\s*)?(\w+)',src)
connections=[]
for width,name in ports:
 value={'core_clk':'clk','ddr0_clk':'clk','ddr1_clk':'clk','core_rst_n':'rst_n','ddr0_rst_n':'rst_n','ddr1_rst_n':'rst_n','engine_soft_clear':'s'}.get(name,"'0")
 connections.append('.'+name+'('+value+')')
out=root/'tb/hap_m003_core_metadata_sideband_tb.sv'
text='''`timescale 1ns/1ps
// Actual complete cohort core and frontend, targeted metadata boundary stimulus.
// Force only environment/state/test preload controls; counter/sidebands/tags/URAM RTL remain real.
module hap_m003_core_metadata_sideband_tb;
reg clk=0; always #5 clk=~clk;
reg rst_n=0,s=0,ready=0,command_ready=0,abort_only=0,write_valid=0;
reg [3:0] state=0;
reg [16:0] write_address=0;
reg [255:0] write_data=0;
integer expected=0,consumed=0,requests=0,stalls=0,combos=0;
integer pre_a,pre_p,exp_p;
reg sampled_s,sampled_l,sampled_r,sampled_q;
function automatic [255:0] value(input integer a);
 integer c;begin for(c=0;c<16;c=c+1)value[c*16+:16]=16'h0101+((a+c)&127);end
endfunction
hap_attention_board_cohort16_core dut (
'''+',\n'.join(connections)+''');
always @(posedge clk) if(rst_n) begin
 sampled_s=s;sampled_l=(state==7&&command_ready);
 sampled_r=dut.meta_rsp_fire;sampled_q=dut.meta_rd_fire;
 pre_a=expected;pre_p=dut.meta_read_pending_r;
 if(dut.u_meta.addr_system_clear!==s || dut.u_meta.addr_launch!==sampled_l)
   $fatal(1,"actual core S/L connection mismatch");
 if(dut.u_meta.g_m003_width_slices.g_slice[0].local_rd_addr!==expected ||
    dut.u_meta.g_m003_width_slices.g_slice[1].local_rd_addr!==expected ||
    dut.meta_read_addr_r!==expected) $fatal(1,"pre-edge address disagreement");
 if(dut.u_weight_frontend.meta_tile!==expected/128 ||
    dut.u_weight_frontend.meta_group!==expected%128) $fatal(1,"actual frontend tile/group tag mismatch");
 if(sampled_q)requests=requests+1;
 if(dut.meta_rsp_valid) begin
   if(dut.meta_rsp_data!==value(expected))$fatal(1,"core joined metadata data mismatch");
   if(sampled_r)consumed=consumed+1; else stalls=stalls+1;
 end
 if(sampled_s)begin expected=0;exp_p=0;end
 else begin
   exp_p=pre_p;
   if(sampled_l)begin expected=0;exp_p=0;end
   if(sampled_q)exp_p=1;
   if(sampled_r)begin expected=(pre_a+1)&131071;exp_p=0;end
 end
 #1;
 if(dut.meta_read_addr_r!==expected ||
    dut.u_meta.g_m003_width_slices.g_slice[0].local_rd_addr!==expected ||
    dut.u_meta.g_m003_width_slices.g_slice[1].local_rd_addr!==expected ||
    dut.meta_read_pending_r!==exp_p)$fatal(1,"post-edge core/helper/NBA mismatch");
end
task automatic tick(input [3:0] st,input bit sv,input bit lv,input bit rv,input bit av);
begin @(negedge clk);state=st;s=sv;command_ready=lv;ready=rv;abort_only=av;@(posedge clk);#2;end endtask
integer a,k;
initial begin
 force dut.state_r=state;
 force dut.weight_command_ready=command_ready;
 force dut.meta_rsp_ready=ready;
 force dut.command_abort_clear_r=abort_only;
 force dut.dma_rd_valid=write_valid;
 force dut.dma_rd_data=write_data;
 force dut.artifact_index_r=write_address;
 #2;if(dut.meta_read_addr_r!==0 || dut.u_meta.g_m003_width_slices.g_slice[0].local_rd_addr!==0)$fatal(1,"async reset mismatch");
 repeat(3)@(negedge clk);rst_n=1;
 // Actual common write path preload, both halves, including tag boundary 127/128.
 for(a=0;a<600;a=a+1)begin
  @(negedge clk);state=2;write_valid=1;write_address=a;write_data=value(a);
 end
 @(negedge clk);write_valid=0;state=0;
 tick(7,0,1,0,0);
 for(a=0;a<300;a=a+1)begin
   tick(8,0,0,0,0); // Q cannot increment A
   tick(8,0,0,0,0); // held real response
   tick(8,0,0,1,0); // real R increments same edge
 end
 // Existing response + real launch: trailing R increment overrides launch zero.
 tick(8,0,0,0,0);tick(7,0,1,1,0);
 // abort-only clears token without clearing original or helper address.
 tick(8,0,0,0,0);tick(0,0,0,0,1);tick(0,0,0,0,0);
 // Clear priority for all L/ready combinations; real R is suppressed by clear.
 for(k=0;k<4;k=k+1)begin tick(k[0]?7:0,1,k[0],k[1],0);combos=combos+1;end
 tick(0,0,0,0,0);tick(7,0,0,0,0); // no actual launch keeps A
 tick(7,0,1,0,0);
 tick(8,0,0,0,0);tick(8,0,0,1,0);
 @(negedge clk);rst_n=0;#1;
 if(dut.meta_read_addr_r!==0 || dut.u_meta.g_m003_width_slices.g_slice[1].local_rd_addr!==0)$fatal(1,"final async reset mismatch");
 if(consumed<302 || requests<303 || stalls<300 || combos!=4)$fatal(1,"coverage missing");
 $display("M003_CORE_BOUNDARY_PASS consumed=%0d requests=%0d stalls=%0d clear_combos=%0d tags_crossed_127_128=1",consumed,requests,stalls,combos);
 $finish;
end
endmodule
'''
out.write_text(text)
print(json.dumps(dict(test=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),scope='actual cohort core metadata boundary; forced environment/state, not end-to-end board command',inputs=len(ports))))
