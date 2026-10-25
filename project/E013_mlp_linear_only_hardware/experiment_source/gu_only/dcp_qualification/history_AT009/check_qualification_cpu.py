#!/usr/bin/env python3
"""CPU-only exact-origin negative checks and Tcl hierarchical-name fixtures."""
from pathlib import Path
import copy,hashlib,importlib.util,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[5];HW=ROOT/'project/hardware';sys.path.insert(0,str(HW/'vivado/scripts'))
import run_mlp_gu_board as runner
SCOPE=Path(__file__).resolve().parent;OUT=ROOT/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R007/attempts/AT008_qualification_cpu'
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
 text=(HW/'vivado/scripts/build_mlp_gu_board.tcl').read_text();pattern=re.search(r'\[regexp \{([^\n]+)\} \$local_name -> channel bit\]',text).group(1)
 # Real full paths contain generated [] segments. Exact basename matching must
 # retain both channel and bit and reject aliases/extra suffixes.
 code='set pattern {'+pattern+'}\nset tests {\n'
 for bit in range(37):
  for ch in range(2):code+='{root/gen_row[7].gen_pair[5].u_lane/guard'+str(ch)+'_s37['+str(bit)+']} '+str(ch)+' '+str(bit)+'\n'
 code+='}\nset count 0\nforeach {name expected_ch expected_bit} $tests {\nset local [string range $name [expr {[string last / $name]+1}] end]\nif {![regexp $pattern $local -> c b] || $c!=$expected_ch || $b!=$expected_bit} {error "bad guard fixture $name"}\nincr count\n}\nforeach name {guard0_s37_extra[0] guard2_s37[0] xguard0_s37[0] guard0_s37[0]/D} {if {[regexp $pattern $name]} {error "bad alias accepted"}}\nputs "PIN_NAME_FIXTURES_PASS $count"\n'
 native=subprocess.run(['tclsh'],input=code,text=True,capture_output=True);(OUT/'pin_name_fixture.tcl').write_text(code);(OUT/'pin_name_fixture.log').write_text(native.stdout+native.stderr)
 assert native.returncode==0 and native.stdout.strip()=='PIN_NAME_FIXTURES_PASS 74';checks.append('system_tcl_74_native_name_fixtures_and_4_alias_rejections_not_native_query_proof')
 (OUT/'qualification_validation.json').write_text(json.dumps(actual,indent=2)+'\n');(OUT/'qualification_negative_cases.json').write_text(json.dumps(outcomes,indent=2)+'\n')
 inputs={str(p):sha(p) for p in [Path(__file__).resolve(),transition,Path(record['origin_record']),HW/'vivado/scripts/build_mlp_gu_board.tcl',HW/'vivado/scripts/run_mlp_gu_board.py',runner.INPUTS]}
 (OUT/'qualification_preflight.json').write_text(json.dumps(dict(verdict='PASS',scope='CPU exact origin/patch and Tcl name parsing; native guard query NOT_RUN',checks=checks,inputs=inputs),indent=2)+'\n');print('QUALIFICATION_CPU_PASS',len(checks))
if __name__=='__main__':main()
