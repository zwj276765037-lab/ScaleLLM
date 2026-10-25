#!/usr/bin/env python3
"""CPU-only exact-origin negative checks and Tcl hierarchical-name fixtures."""
from pathlib import Path
import copy,hashlib,importlib.util,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[5];HW=ROOT/'project/hardware';sys.path.insert(0,str(HW/'vivado/scripts'))
import run_mlp_gu_board as runner
SCOPE=Path(__file__).resolve().parent;OUT=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT010_guard_storage_cpu'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 checks=[];transition=SCOPE/'AT007_requalification.json';freeze=sha(runner.INPUTS)
 actual=runner.validate_qualification_origin(transition,freeze);checks.append('positive_exact_AT007_origin_and_two_driver_patch')
 record=json.loads(transition.read_text());origin=json.loads(Path(record['origin_record']).read_text());cases=SCOPE/'negative_cases';cases.mkdir(exist_ok=True)
 mutations=[]
 r=copy.deepcopy(record);r['origin_record_sha256']='0'*64;mutations.append(('reject_origin_hash',r))
 r=copy.deepcopy(record);r['current_input_manifest_sha256']='0'*64;mutations.append(('reject_current_freeze',r))
 r=copy.deepcopy(record);r['changes'].pop('vivado/scripts/build_mlp_gu_board.tcl');mutations.append(('reject_missing_exact_change',r))
 r=copy.deepcopy(record);r['patches']['vivado/scripts/build_mlp_gu_board.tcl']['sha256']='0'*64;mutations.append(('reject_patch_hash',r))
 for name,field,value in [('reject_arbitrary_failure_parent','origin_evidence',str(ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT006_constructor')),('reject_missing_native_runs','native_synth_log_hashes',{}),('reject_dcp_identity','dcp_sha256','0'*64)]:
  o=copy.deepcopy(origin);o[field]=value;p=cases/(name+'_origin.json');p.write_text(json.dumps(o,indent=2)+'\n');r=copy.deepcopy(record);r['origin_record']=str(p);r['origin_record_sha256']=sha(p);mutations.append((name,r))
 outcomes=[]
 for name,r in mutations:
  p=cases/(name+'.json');p.write_text(json.dumps(r,indent=2)+'\n')
  try:runner.validate_qualification_origin(p,freeze)
  except (ValueError,KeyError) as e:checks.append(name);outcomes.append(dict(case=name,rejection=str(e),input=str(p),sha256=sha(p)))
  else:raise AssertionError('accepted '+name)
 text=(HW/'vivado/scripts/build_mlp_gu_board.tcl').read_text();pattern=re.search(r'\[regexp \{([^\n]+)\} \$name -> owner channel entry bit\]',text).group(1)
 cells=json.loads((OUT/'guard_storage_cells.json').read_text());names=[mod+'/'+x['name'] for mod,regs in cells.items() for x in regs]
 code='set pattern {'+pattern+'}\nset names {\n'+''.join('{'+name+'}\n' for name in names)+'}\n'
 code+='set observed {}\nforeach name $names {if {![regexp $pattern $name -> owner ch entry bit]} {error "actual cell name rejected: $name"};dict lappend observed $owner "$ch:$entry:$bit"}\n'
 code+='set expected {}\nforeach ch {0 1} {foreach entry {0 1} {for {set bit 0} {$bit<37} {incr bit} {lappend expected "$ch:$entry:$bit"}}}\nset expected [lsort -dictionary $expected]\n'
 code+='proc complete {actual expected} {expr {[llength $actual]==148 && [lsort -dictionary -unique $actual] eq $expected}}\n'
 code+='if {[dict size $observed]!=96} {error "lane definitions missing"}\nforeach {owner actual} $observed {if {![complete $actual $expected]} {error "incomplete actual cell indices: $owner"}}\n'
 code+='set good [lindex [dict values $observed] 0]\nforeach bad [list [lrange $good 1 end] [concat $good [lindex $good 0]] [lreplace $good 0 0 0:0:37] [lreplace $good 0 0 0:2:0]] {if {[complete $bad $expected]} {error "bad cell index set accepted"}}\n'
 code+='foreach name {scope/guard0_mem_reg[0][0]_replica scope/guard2_mem_reg[0][0]} {if {[regexp $pattern $name]} {error "unexpected alias accepted"}}\nputs "GUARD_CELL_FIXTURES_PASS [llength $names] [dict size $observed] 6"\n'
 native=subprocess.run(['tclsh'],input=code,text=True,capture_output=True);(OUT/'guard_cell_fixture.tcl').write_text(code);(OUT/'guard_cell_fixture.log').write_text(native.stdout+native.stderr)
 assert native.returncode==0 and native.stdout.strip()=='GUARD_CELL_FIXTURES_PASS 14208 96 6',(native.returncode,native.stdout,native.stderr);checks.append('system_tcl_actual_14208_cell_names_96_index_sets_and_6_rejections_not_native_query_proof')
 (OUT/'qualification_validation.json').write_text(json.dumps(actual,indent=2)+'\n');(OUT/'qualification_negative_cases.json').write_text(json.dumps(outcomes,indent=2)+'\n')
 inputs={str(p):sha(p) for p in [Path(__file__).resolve(),transition,Path(record['origin_record']),HW/'vivado/scripts/build_mlp_gu_board.tcl',HW/'vivado/scripts/run_mlp_gu_board.py',runner.INPUTS]}
 (OUT/'qualification_preflight.json').write_text(json.dumps(dict(verdict='PASS',scope='CPU exact origin/patch and actual generated-netlist cell naming/index parsing; native full-board query NOT_RUN',checks=checks,inputs=inputs),indent=2)+'\n');print('QUALIFICATION_CPU_PASS',len(checks))
if __name__=='__main__':main()
