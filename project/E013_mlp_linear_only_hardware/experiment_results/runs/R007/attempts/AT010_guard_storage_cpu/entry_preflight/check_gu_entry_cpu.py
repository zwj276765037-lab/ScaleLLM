#!/usr/bin/env python3
"""Reproducible CPU-only source guard checks; never launches EDA."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[4]
HW=ROOT/'project/hardware'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('attempt');a=parser.parse_args()
 out=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts'/a.attempt;out.mkdir(parents=True,exist_ok=False)
 script=HW/'vivado/scripts/m006_gu_entry.py';spec=importlib.util.spec_from_file_location('gu_entry',script);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 checks=[];m.production_shape();checks.append('current_source_bound_shape')
 files=['rtl/integration/hap_attention_mlp_production_core_gu_only.sv','rtl/integration/hap_attention_mlp_resource_top_gu_only.sv','rtl/integration/hap_attention_mlp_board_core_gu_only.sv','rtl/mlp/hap_mlp_gu_compute16_s44.sv','rtl/mlp/hap_mlp_gu_cache16.sv','rtl/mlp/hap_a8w4_gu_group32_lane2_s37.sv']
 mutations=[(files[0],'INTERMEDIATE_COLUMNS=14336','INTERMEDIATE_COLUMNS=128'),(files[1],'HIDDEN_COLUMNS=4096','HIDDEN_COLUMNS=64'),(files[2],'.ENFORCE_PRODUCTION_SHAPE(1)','.ENFORCE_PRODUCTION_SHAPE(0)'),(files[3],'HIDDEN_GROUPS=128','HIDDEN_GROUPS=4'),(files[4],'memory[0:127]','memory[0:447]'),(files[4],'wr_group<128','wr_group[6:0]<128'),(files[5],'[36:0] guard0_mem','[44:0] guard0_mem')]
 with tempfile.TemporaryDirectory() as t:
  m.HW=Path(t)
  for f in files:
   q=m.HW/f;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HW/f,q)
  for index,(f,old,new) in enumerate(mutations):
   q=m.HW/f;original=q.read_text();assert old in original,(f,old);q.write_text(original.replace(old,new,1))
   try:m.production_shape()
   except (ValueError,KeyError):checks.append('reject_source_mutation_'+str(index))
   else:raise AssertionError('accepted source mutation '+str(index))
   q.write_text(original)
  m.HW=HW
 names={}
 for f in m.selected_hdl():
  for name in re.findall(r'^module\s+(\w+)',f.read_text(),re.M):
   assert name not in names,(name,f,names.get(name));names[name]=str(f)
 checks.append('selected_modules_unique_'+str(len(names)))
 paths=m.closure();m.check_graph(paths);checks.append('attention44_source_hashes_and_no_down_selected')
 for name in ['create_mlp_gu_board.tcl','build_mlp_gu_board.tcl']:
  q=HW/'vivado/scripts'/name
  command='set h [open {'+str(q)+'} r]\nset s [read $h]\nclose $h\nif {![info complete $s]} {exit 1}\nputs COMPLETE\n'
  r=subprocess.run(['tclsh'],input=command,text=True,capture_output=True)
  (out/(name+'.syntax.log')).write_text(r.stdout+r.stderr);assert r.returncode==0 and r.stdout.strip()=='COMPLETE';checks.append(name+'_system_tcl_complete_not_native_query')
 for name in ['m006_gu_entry.py','run_mlp_gu_board.py']:
  compile((HW/'vivado/scripts'/name).read_text(),name,'exec');checks.append(name+'_python_compile')
 # Snapshot exact executed checker and complete production dependency closure.
 identity={str(q):sha(q) for q in paths+[Path(__file__).resolve()]}
 for q in paths:
  target=out/'source_snapshot'/q.relative_to(HW);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,target)
 shutil.copy2(__file__,out/'check_gu_entry_cpu.py')
 (out/'result.json').write_text(json.dumps(dict(verdict='PASS',scope='CPU source guards and system Tcl syntax; no native query proof',checks=checks,inputs=identity,command=['python3',str(Path(__file__).resolve()),a.attempt]),indent=2)+'\n')
 print('CPU_PASS',len(checks),out)
if __name__=='__main__':main()
