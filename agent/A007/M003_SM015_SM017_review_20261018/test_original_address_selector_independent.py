from pathlib import Path
import copy,json,subprocess,unittest
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
TCL=OUT/'original_address_candidate_cpu_tree/vivado/scripts/m003_joint_checks.tcl'
FACT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT016_fresh_core_original_address_attribution/evidence/AT016_closed_native_facts_and_terminal.json'
ROWS=json.loads(FACT.read_text())['actual_native_rows']['original_address_broad']
SCOPE='inst/u_core/u_compute/u_attention'
class Candidate(unittest.TestCase):
 def execute(self,rows=None,force=None,scope=SCOPE):
  rows=copy.deepcopy(ROWS if rows is None else rows)
  code='source {'+str(TCL)+'}\nset ::m003::core_meta_scope {'+scope+'}\nset pool [dict create]\n'
  for i,row in enumerate(rows):
   code+='dict set pool c'+str(i)+' [dict create '+' '.join(k+' {'+str(v)+'}' for k,v in row.items())+']\n'
  code+=r'''
proc get_cells {args} {
 set expected [format {IS_PRIMITIVE == 1 && NAME =~ "%s/*meta_read_addr_r_reg*"} $::m003::core_meta_scope]
 if {[lindex $args end] ne $expected || [lrange $args 0 2] ne {-quiet -hier -filter}} {error "query scope changed"}
 return $::selection
}
proc get_property {key cell} {return [dict get $::pool $cell $key]}
'''
  ids=[f'c{i}' for i in range(len(rows))]
  code+='set selection {'+' '.join(ids if force is None else force)+'}\n'
  code+=r'''
if {[catch {m003::original_address_members} selected]} {puts "REJECT:$selected";exit 7}
for {set bit 0} {$bit<17} {incr bit} {
 set actual [get_property NAME [dict get $selected $bit]]
 puts "$bit=$actual"
}
'''
  p=subprocess.run(['tclsh'],input='if {[catch {\n'+code+'\n} error]} {puts stderr $error;exit 9}\n',text=True,capture_output=True,cwd=ROOT/'project/hardware')
  return p
 def accept(self,rows=None,scope=SCOPE):
  p=self.execute(rows,scope=scope);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertEqual(p.stdout.splitlines(),[f'{i}={scope}/meta_read_addr_r_reg[{i}]' for i in range(17)])
 def reject(self,rows=None,force=None):
  p=self.execute(rows,force);self.assertEqual(p.returncode,7,p.stdout+p.stderr);self.assertTrue(p.stdout.startswith('REJECT:'))
 def test_exact_measured_objects_mapping_and_board_scope(self):
  self.accept()
  prefix='scalellm_vcu118_f05_bd_i/core/'
  self.accept([{**x,'NAME':prefix+x['NAME']} for x in ROWS],prefix+SCOPE)
 def test_nonstate_neighbors_optional_without_weakening_17state_coverage(self):
  states=[x for x in ROWS if x['REF_NAME']=='FDCE'];self.accept(states)
  self.reject(states[:-1])
 def test_every_wrong_reference_for_measured_nonstate_name_rejected(self):
  index=next(i for i,x in enumerate(ROWS) if x['REF_NAME']=='CARRY8')
  for ref in ['FDCE','FDRE','LUT1','VCC','CARRY4','']:
   with self.subTest(ref=ref):
    rows=copy.deepcopy(ROWS);rows[index]['REF_NAME']=ref;self.reject(rows)
 def test_unknown_nonstate_combinational_is_not_blanket_skipped(self):
  for ref in ['CARRY8','LUT3','GND','VCC']:
   with self.subTest(ref=ref):
    self.reject(ROWS+[{'NAME':SCOPE+'/meta_read_addr_r_reg[4]_i_9','REF_NAME':ref,'IS_PRIMITIVE':'1','DONT_TOUCH':''}])
 def test_duplicate_selected_carry_object_and_duplicate_state_name_rejected(self):
  i=next(i for i,x in enumerate(ROWS) if x['REF_NAME']=='CARRY8')
  self.reject(force=[f'c{x}' for x in range(19)]+[f'c{i}'])
  self.reject(ROWS+[next(x for x in ROWS if x['REF_NAME']=='FDCE')])
 def test_noncanonical_or_foreign_state_names_rejected(self):
  ix=next(i for i,x in enumerate(ROWS) if x['NAME'].endswith('[0]'))
  bad=['meta_read_addr_r_reg[00]','meta_read_addr_r_reg[+0]','meta_read_addr_r_reg[-0]','meta_read_addr_r_reg[17]','meta_read_addr_r_reg[18446744073709551616]','nested/meta_read_addr_r_reg[0]','meta_read_addr_r_reg[0]_replica','meta_read_addr_r_reg[0]/child']
  for leaf in bad:
   with self.subTest(leaf=leaf):
    rows=copy.deepcopy(ROWS);rows[ix]['NAME']=SCOPE+'/'+leaf;self.reject(rows)
  rows=copy.deepcopy(ROWS);rows[ix]['NAME']=SCOPE+'_impostor/meta_read_addr_r_reg[0]';self.reject(rows)
if __name__=='__main__':unittest.main(verbosity=2)
