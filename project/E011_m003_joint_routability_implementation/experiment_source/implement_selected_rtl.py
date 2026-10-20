#!/usr/bin/env python3
"""Apply exactly the G2-selected M2/A3 RTL after checking preserved source identities."""
import datetime,difflib,hashlib,json,os
from pathlib import Path
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HERE=Path(__file__).resolve().parent
HW=ROOT/'project/hardware'
AT=HERE.parent/'experiment_results/runs/R001/attempts/AT001_selected_RTL_and_functional_integration'
def ident(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 result=AT/'selected_RTL_applied.json';assert not result.exists()
 orig=HERE/'prechange_RTL'
 paths=['rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv','rtl/attention/hap_weight_meta_resident.sv','rtl/attention/hap_attention_board_cohort16_core.sv']
 for rel in paths:assert (HW/rel).read_bytes()==(orig/Path(rel).name).read_bytes(),('concurrent production edit',rel)
 started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
 groups=json.loads((ROOT/'agent/A006/M003_SM014_design_20261018/F1_F3_C_M2_region_groups.json').read_text())['groups']
 def group_function(family):
  gs=[g for g in groups if g['family']==family]
  lines=[f'    function automatic integer m003_{family}_ce_group(input integer bit_index);','        case (bit_index)']
  for i,g in enumerate(gs):
   bits=g['bits']
   for j in range(0,len(bits),24):
    last=j+24>=len(bits);s=', '.join(str(v) for v in bits[j:j+24])
    lines.append('            '+s+(f': m003_{family}_ce_group = {i};' if last else ','))
  lines += [f'            default: m003_{family}_ce_group = -1;','        endcase','    endfunction']
  return '\n'.join(lines)
 p=HW/paths[0];old=p.read_text()
 start=old.index('    always @(posedge clk) begin\n        if (!rst_n || clear) begin\n            parent_count_r')
 end=old.index('    always @(posedge clk) begin\n        if (!rst_n || clear) begin\n            input_transaction_count',start)
 m2='''    // M003 C-M2: exact original case enables, buffered in the frozen native-CR groups.
    // These are combinational enables; payload capacity/data/latency remain unchanged.
    wire parent_head_write_ce = rst_n && !clear &&
        ((in_fire && !parent_pop && parent_empty) ||
         (!in_fire && parent_pop && parent_full) ||
         (in_fire && parent_pop));
    wire parent_tail_write_ce = rst_n && !clear &&
        in_fire && !parent_pop && !parent_empty;
    wire [PARENT_PAYLOAD_W-1:0] parent_head_write_data =
        (!in_fire && parent_pop && parent_full) ?
        parent_tail_r : parent_input_payload;

'''+group_function('head')+'\n\n'+group_function('tail')+'''

    generate
        if (TILE_W == 9 && PARENT_PAYLOAD_W == 6560) begin : g_m003_parent_ce
            (* KEEP = "yes" *) wire [41:0] head_ce;
            (* KEEP = "yes" *) wire [38:0] tail_ce;
            for (genvar group_index = 0; group_index < 42; group_index = group_index + 1) begin : g_head_ce
                (* DONT_TOUCH = "yes" *)
                LUT1 #(.INIT(2'b10)) u_ce_buffer (
                    .I0(parent_head_write_ce), .O(head_ce[group_index])
                );
            end
            for (genvar group_index = 0; group_index < 39; group_index = group_index + 1) begin : g_tail_ce
                (* DONT_TOUCH = "yes" *)
                LUT1 #(.INIT(2'b10)) u_ce_buffer (
                    .I0(parent_tail_write_ce), .O(tail_ce[group_index])
                );
            end
            for (genvar payload_bit = 0; payload_bit < PARENT_PAYLOAD_W; payload_bit = payload_bit + 1) begin : g_payload_bit
                localparam integer HEAD_GROUP = m003_head_ce_group(payload_bit);
                localparam integer TAIL_GROUP = m003_tail_ce_group(payload_bit);
                always @(posedge clk) begin
                    if (head_ce[HEAD_GROUP])
                        parent_head_r[payload_bit] <= parent_head_write_data[payload_bit];
                    if (tail_ce[TAIL_GROUP])
                        parent_tail_r[payload_bit] <= parent_input_payload[payload_bit];
                end
            end
        end else begin : g_original_parent_ce
            // Compatibility for reduced/nonproduction parameter instances.
            // Production structure checks require the 81-buffer branch above.
            always @(posedge clk) begin
                if (parent_head_write_ce)
                    parent_head_r <= parent_head_write_data;
                if (parent_tail_write_ce)
                    parent_tail_r <= parent_input_payload;
            end
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n || clear) begin
            parent_count_r <= 2'd0;
        end else begin
            case ({in_fire, parent_pop})
                2'b10: parent_count_r <= parent_count_r + 1'b1;
                2'b01: parent_count_r <= parent_count_r - 1'b1;
                2'b11: parent_count_r <= parent_count_r;
                default: parent_count_r <= parent_count_r;
            endcase
        end
    end

'''
 new=old[:start]+m2+old[end:]
 # The entire branch implementation must remain byte-for-byte unchanged.
 marker='module hap_mlp_shared_local_slice8x12_s44_s54'
 assert old[old.index(marker):]==new[new.index(marker):]
 p.write_text(new)
 p=HW/paths[1];old=p.read_text();new=old
 new=new.replace('parameter integer ADDR_W = 17','parameter integer ADDR_W = 17,\n    parameter integer LOCAL_ADDR_COPIES = 0',1)
 new=new.replace('    input  wire                  clear,','    input  wire                  clear,\n    input  wire                  addr_system_clear,\n    input  wire                  addr_launch,',1)
 new=new.replace('    (* ram_style = "ultra" *) reg [255:0] meta_mem [0:DEPTH-1];\n','',1)
 start=new.index('    always @(posedge clk) begin\n        if (wr_fire)')
 end=new.index('    always @(posedge clk or negedge rst_n) begin',start)
 new=new[:start]+'''    generate
        if (LOCAL_ADDR_COPIES == 1) begin : g_m003_width_slices
            for (genvar slice_index = 0; slice_index < 2; slice_index = slice_index + 1) begin : g_slice
                wire [ADDR_W-1:0] local_rd_addr;
                (* keep_hierarchy = "yes" *)
                hap_weight_meta_read_addr_copy #(.ADDR_W(ADDR_W)) u_addr (
                    .clk(clk), .rst_n(rst_n),
                    .system_clear(addr_system_clear), .launch(addr_launch),
                    .rsp_fire(rsp_fire), .addr(local_rd_addr)
                );
                (* ram_style = "ultra" *) reg [127:0] meta_mem [0:DEPTH-1];
                always @(posedge clk) begin
                    if (wr_fire)
                        meta_mem[wr_addr] <= wr_meta16[slice_index*128 +: 128];
                    if (rd_fire)
                        rsp_meta_r[slice_index*128 +: 128] <= meta_mem[local_rd_addr];
                end
            end
        end else begin : g_original_store
            (* ram_style = "ultra" *) reg [255:0] meta_mem [0:DEPTH-1];
            always @(posedge clk) begin
                if (wr_fire)
                    meta_mem[wr_addr] <= wr_meta16;
                if (rd_fire)
                    rsp_meta_r <= meta_mem[rd_addr];
            end
        end
    endgenerate

'''+new[end:]
 new=new.replace('inside the SLR2 metadata pblock','inside the metadata bank')
 new += '''

// M003 C-A3: independent same-edge memory-side address state.
// Only the address FF and the two local control LUTs are protected.
// system_clear intentionally excludes abort-only datapath_clear.
module hap_weight_meta_read_addr_copy #(
    parameter integer ADDR_W = 17
) (
    input wire clk,
    input wire rst_n,
    input wire system_clear,
    input wire launch,
    input wire rsp_fire,
    output wire [ADDR_W-1:0] addr
);
    (* KEEP = "yes" *) wire local_ce;
    (* KEEP = "yes" *) wire local_increment;
    (* DONT_TOUCH = "yes" *)
    LUT3 #(.INIT(8'hfe)) u_local_ce (
        .I0(system_clear), .I1(launch), .I2(rsp_fire), .O(local_ce)
    );
    (* DONT_TOUCH = "yes" *)
    LUT2 #(.INIT(4'h2)) u_local_increment (
        .I0(rsp_fire), .I1(system_clear), .O(local_increment)
    );
    (* DONT_TOUCH = "yes", KEEP = "yes", SHREG_EXTRACT = "NO" *)
    reg [ADDR_W-1:0] address_r;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            address_r <= {ADDR_W{1'b0}};
        else if (local_ce)
            address_r <= local_increment ? address_r + 1'b1 : {ADDR_W{1'b0}};
    end
    assign addr = address_r;
endmodule
'''
 assert new!=old;p.write_text(new)
 p=HW/paths[2];old=p.read_text()
 new=old.replace('    hap_weight_meta_resident u_meta (','    hap_weight_meta_resident #(.LOCAL_ADDR_COPIES(1)) u_meta (',1)
 needle='        .clk(core_clk), .rst_n(core_rst_n), .clear(datapath_clear),'
 pos=new.index(needle,new.index('hap_weight_meta_resident #'))
 new=new[:pos]+new[pos:].replace(needle,needle+'\n        .addr_system_clear(system_clear),\n        .addr_launch(state_r==ST_LAUNCH && weight_command_ready),',1)
 assert new!=old;p.write_text(new)
 changes=[]
 for rel in paths:
  p=HW/rel;b=orig/p.name
  diff=''.join(difflib.unified_diff(b.read_text().splitlines(True),p.read_text().splitlines(True),fromfile=str(b),tofile=str(p)))
  d=AT/(p.stem+'.diff');d.write_text(diff);changes.append(dict(before=ident(b),after=ident(p),diff=ident(d)))
 receipt=dict(started_utc=started_utc,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution='completed',verdict='RTL_APPLIED_NOT_COMPILED_OR_VERIFIED',selected=['C-M2','C-A3'],changes=changes,MLP_branch_implementation_byte_identical=True,M2_head_groups=42,M2_tail_groups=39,A3_local_address_FF_expected=34,A3_slices=2,A3_width=128,actual_affinity=sorted(os.sched_getaffinity(0)),actual_nice=os.getpriority(os.PRIO_PROCESS,0),producer=ident(Path(__file__)))
 result.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({k:v for k,v in receipt.items() if k!='changes'},indent=2))
if __name__=='__main__':main()
