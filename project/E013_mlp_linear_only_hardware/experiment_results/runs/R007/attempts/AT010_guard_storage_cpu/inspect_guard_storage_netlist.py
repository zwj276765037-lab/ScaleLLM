#!/usr/bin/env python3
"""Inspect the actual generated functional netlist; never loads an EDA design."""
from pathlib import Path
import datetime,hashlib,json,re
ROOT=Path(__file__).resolve().parents[5];HW=ROOT/'project/hardware'
NETLIST=HW/'vivado/project/m006_gu_AT006_constructor/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ip/scalellm_vcu118_f05_bd_core_0/scalellm_vcu118_f05_bd_core_0_sim_netlist.v'
OUT=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT010_guard_storage_cpu'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=False);modules={};instances=[];current=None;interest=False
 module_re=re.compile(r'^module\s+(\S+)');fd_re=re.compile(r'^\s+(FD\w*)\s+\\(guard([01])_mem_reg\[(\d+)\]\[(\d+)\])\s*$');inst_re=re.compile(r'^\s+(\S*hap_a8w4_gu_group32_lane2_s37\S*)\s+\\(\S+)\s*$')
 with NETLIST.open() as f:
  for line_no,line in enumerate(f,1):
   m=module_re.match(line)
   if m:
    current=m[1];interest='hap_a8w4_gu_group32_lane2_s37' in current
    if interest:modules[current]=[]
   if interest:
    m=fd_re.match(line)
    if m:modules[current].append(dict(primitive=m[1],name=m[2],channel=int(m[3]),entry=int(m[4]),bit=int(m[5]),line=line_no))
   m=inst_re.match(line)
   if m:instances.append(dict(parent_module=current,ref=m[1],instance=m[2],line=line_no))
   if line.strip()=='endmodule':current=None;interest=False
 expected={(ch,entry,bit) for ch in range(2) for entry in range(2) for bit in range(37)};results=[]
 for mod,regs in modules.items():
  observed={(x['channel'],x['entry'],x['bit']) for x in regs};results.append(dict(module=mod,physical_registers=len(regs),complete_37x2x2=observed==expected and len(regs)==148,primitives=sorted(set(x['primitive'] for x in regs)),missing=sorted(expected-observed),extra=sorted(observed-expected)))
 counts={name:sum(x['ref']==name for x in instances) for name in modules}
 assert len(modules)==96 and len(instances)==96 and all(n==1 for n in counts.values())
 assert all(x['complete_37x2x2'] for x in results),results
 bound=json.loads((ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT007_synth/post_failure_generated_inventory.json').read_text());project=HW/'vivado/project/m006_gu_AT006_constructor';rel=str(NETLIST.relative_to(project));assert bound['files'][rel]==sha(NETLIST)
 record=dict(verdict='PASS',scope='actual core generated structural funcsim Verilog; exact primitive names/counts and per-type bindings; full-board native query still required',observed=datetime.datetime.now(datetime.timezone.utc).isoformat(),netlist=str(NETLIST),netlist_bytes=NETLIST.stat().st_size,netlist_sha256=sha(NETLIST),bound_to_AT007_post_failure_inventory=True,lane_module_definitions=len(modules),lane_instances=len(instances),all_instance_refs_bound_once=True,physical_guard_data_FF=sum(len(x) for x in modules.values()),per_lane_results=results,instances=instances,source_sha256=sha(Path(__file__)))
 (OUT/'guard_storage_netlist.json').write_text(json.dumps(record,indent=2)+'\n');(OUT/'guard_storage_cells.json').write_text(json.dumps(modules,indent=2)+'\n');(OUT/'result.json').write_text(json.dumps({k:v for k,v in record.items() if k not in ['per_lane_results','instances']},indent=2)+'\n');print('GUARD_STORAGE_NETLIST_PASS',len(modules),len(instances),sum(len(x) for x in modules.values()),sha(NETLIST))
if __name__=='__main__':main()
