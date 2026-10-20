#!/usr/bin/env python3
"""Frozen old parent vs selected current parent unit, and full real production-width dispatch."""
import datetime,hashlib,json,os,re
from pathlib import Path
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');HERE=Path(__file__).resolve().parent;HW=ROOT/'project/hardware'
def ident(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,s):assert not p.exists();p.write_text(s)
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 original=HERE/'prechange_RTL/hap_mlp_shared_dual_slice16x12_s44_s54.sv';current=HW/'rtl/mlp'/original.name
 old=original.read_text();new=current.read_text();name='hap_mlp_shared_dual_slice16x12_s44_s54'
 old_parent=old[:old.index('endmodule')+len('endmodule')];new_parent=new[:new.index('endmodule')+len('endmodule')]
 fixture=HW/'tb/hap_m003_parent_unit_models.sv'
 branch=old[old.index('module hap_mlp_shared_local_slice8x12_s44_s54'):];header=branch[:branch.index(');')+2]
 outs=re.findall(r'^\s*output\s+wire\s+(?:signed\s+)?(?:\[[^\]]+\]\s*)?(\w+)\s*[,)]?\s*$',header,re.M)
 assert len(outs)>10
 stub=header+'\n    reg test_ready=0;\n'+''.join(f"    assign {n} = {'test_ready' if n=='in_ready' else chr(39)+'0'};\n" for n in outs)+'endmodule\n'
 write(fixture,old_parent.replace('module '+name,'module hap_m003_old_parent',1)+'\n\n'+new_parent.replace('module '+name,'module hap_m003_new_parent',1)+'\n\n'+stub)
 top_header=old_parent[:old_parent.index(');')+2];ports=[]
 for m in re.finditer(r'^\s*(input|output)\s+(?:wire|reg)\s+(signed\s+)?(\[[^\]]+\]\s*)?(\w+)\s*,?\s*$',top_header,re.M):ports.append((m[1],m[2] or '',m[3] or '',m[4]))
 assert len(ports)>30
 declarations=[]
 for dr,sg,w,n in ports:
  if dr=='input':declarations.append(f"    reg {sg}{w}{n} = '0;")
  else:
   declarations.extend(f'    wire {sg}{w}{side}_{n};' for side in ('old','new'))
 inst=[]
 for side in ('old','new'):
  inst.append(f'    hap_m003_{side}_parent #(.TILE_W(9)) {side}_dut (\n'+',\n'.join(f"        .{n}({n if dr=='input' else side+'_'+n})" for dr,sg,w,n in ports)+'\n    );')
 tb='''`timescale 1ns / 1ps
module hap_m003_parent_cycle_diff_tb;
    localparam integer TILE_W=9;
'''+ '\n'.join(declarations)+'\n'+ '\n'.join(inst)+'''
    always #5 clk=~clk;
    reg r0=0,r1=0;
    reg [6559:0] stimulus=0;
    reg [6559:0] model_head,model_tail;
    integer model_count=0,checks=0,full_pop=0,both_events=0,unequal_ready=0,clear_seen=0;
    reg push,pop;
    reg [31:0] rng=32'h10a32026;
    task automatic next_stimulus;
        for(integer j=0;j<205;j=j+1) begin
            rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
            stimulus[j*32+:32]=rng;
        end
    endtask
    always_comb begin
        {column_valid_u12,weight_shift_u6x12,weight_code_u8x12,
         activation_shift_u6x16,activation_code_u8x16,
         weights_s4x12x32,activation_s9x16x32,in_tile,in_last,in_first,in_down}=stimulus;
    end
    always_comb begin
        old_dut.u_branch0.test_ready=r0;new_dut.u_branch0.test_ready=r0;
        old_dut.u_branch1.test_ready=r1;new_dut.u_branch1.test_ready=r1;
    end
    always @(posedge clk) begin
        if(old_in_ready!==(rst_n&&!clear&&(model_count!=2)) || new_in_ready!==old_in_ready)
            $fatal(1,"upstream credit mismatch");
        push=in_valid&&old_in_ready;
        pop=rst_n&&!clear&&(model_count!=0)&&r0&&r1;
        if(model_count==2&&pop) begin
            full_pop=full_pop+1;
            if(push||new_in_ready) $fatal(1,"full plus pop created same-cycle credit");
        end
        if(push&&pop) both_events=both_events+1;
        if(r0!=r1) unequal_ready=unequal_ready+1;
        if((new_dut.u_branch0.in_valid&&new_dut.u_branch0.in_ready) !== pop)
            $fatal(1,"branch0 atomic acceptance mismatch");
        if((new_dut.u_branch1.in_valid&&new_dut.u_branch1.in_ready) !== pop)
            $fatal(1,"branch1 atomic acceptance mismatch");
        if(!rst_n||clear) begin model_count=0;clear_seen=clear_seen+1;end
        else case({push,pop})
            2'b10:begin
                if(model_count==0) model_head=stimulus;else model_tail=stimulus;
                model_count=model_count+1;
            end
            2'b01:begin if(model_count==2) model_head=model_tail;model_count=model_count-1;end
            2'b11:model_head=stimulus;
            default:begin end
        endcase
        #1;
        if(new_dut.parent_count_r!==model_count[1:0] || old_dut.parent_count_r!==model_count[1:0])
            $fatal(1,"occupancy mismatch");
        if(new_dut.parent_head_r!==model_head || old_dut.parent_head_r!==model_head ||
           new_dut.parent_tail_r!==model_tail || old_dut.parent_tail_r!==model_tail)
            $fatal(1,"whole payload/reset/hold/tail move mismatch cycle=%0d",checks);
        if(new_dut.g_m003_parent_ce.head_ce!=={42{new_dut.parent_head_write_ce}} ||
           new_dut.g_m003_parent_ce.tail_ce!=={39{new_dut.parent_tail_write_ce}})
            $fatal(1,"CE identity primitive mismatch");
        checks=checks+1;
    end
    initial begin
        repeat(3) @(negedge clk);rst_n=1;in_valid=1;next_stimulus();
        repeat(5) @(negedge clk);
        r0=1;r1=0;repeat(4) @(negedge clk);
        r0=0;r1=1;repeat(4) @(negedge clk);
        r0=1;r1=1;repeat(8) @(negedge clk);
        for(integer i=0;i<3000;i=i+1) begin
            @(negedge clk);next_stimulus();
            rst_n=(i%137!=0);clear=(i%97==0);
            in_valid=rng[0]|rng[1];r0=rng[2];r1=rng[3];
        end
        @(negedge clk);in_valid=0;clear=0;rst_n=1;r0=1;r1=1;
        repeat(5) @(negedge clk);
        if(full_pop==0||both_events==0||unequal_ready==0||clear_seen<2||checks<3000)
            $fatal(1,"FIFO boundary coverage incomplete");
        $display("M003_M2_PARENT_CYCLE_DIFF_PASS");$finish;
    end
endmodule
'''
 write(HW/'tb/hap_m003_parent_cycle_diff_tb.sv',tb)
 write(HW/'vivado/manifests/m003_parent_unit.list','tb/hap_m003_parent_unit_models.sv\n')
 dispatch=HW/'tb/hap_mlp_shared_dual_s44_s54_dispatch_tb.sv';prod=dispatch.read_text()
 prod=prod.replace('module hap_mlp_shared_dual_s44_s54_dispatch_tb;','module hap_m003_shared_production_width_tb;',1)
 prod=prod.replace('reg [1:0] tile;','reg [8:0] tile;').replace('wire [1:0] down_tile;','wire [8:0] down_tile;').replace('reg [1:0] held_tile;','reg [8:0] held_tile;')
 prod=prod.replace('#(.DOWN_TILES(DT),.DOWN_GROUPS(DG))','#(.DOWN_TILES(DT),.DOWN_GROUPS(DG),.TILE_W(9))')
 prod=prod.replace('PASS:', 'PASS:') # Preserve the existing independent integer pass marker exactly.
 write(HW/'tb/hap_m003_shared_production_width_tb.sv',prod)
 files=[fixture,HW/'tb/hap_m003_parent_cycle_diff_tb.sv',HW/'vivado/manifests/m003_parent_unit.list',HW/'tb/hap_m003_shared_production_width_tb.sv']
 receipt=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_source=ident(original),new_source=ident(current),original_dispatch_reference=ident(dispatch),generated=[ident(p) for p in files],scope='Boundary test compiles literal old/current parent bodies with an explicit ready-only branch stub; full production-width dispatch separately compiles actual complete production RTL and real kernels. Neither result has run yet.',producer=ident(Path(__file__)))
 write(HERE/'M2_test_preparation.json',json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'generated':len(files),'parent_ports':len(ports),'stub_outputs':len(outs),'scope':receipt['scope']},indent=2))
if __name__=='__main__':main()
