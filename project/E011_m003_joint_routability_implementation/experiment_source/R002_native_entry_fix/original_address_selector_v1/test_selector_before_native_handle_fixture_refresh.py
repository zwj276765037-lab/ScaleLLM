"""Real native-role data CPU replay; measured/synthetic boundaries stay explicit."""
from pathlib import Path
import hashlib,json,re,subprocess,tempfile,unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];HW=ROOT/'project/hardware'
FACT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT016_fresh_core_original_address_attribution/evidence/AT016_closed_native_facts_and_terminal.json'
assert hashlib.sha256(FACT.read_bytes()).hexdigest()=='9b0e5b737967d5419d1f0ee2495bec5f0a0820451e8a8712a553dd4e1106d274'
FACTS=json.loads(FACT.read_text());ORIG=FACTS['actual_native_rows']['original_address_broad'];CONTROL={x['NAME']:x for x in FACTS['actual_native_rows']['local_control_luts']};CORE='inst/u_core/u_compute/u_attention'
PROD=HW/'vivado/scripts/m003_joint_checks.tcl';CAND=HERE/'m003_joint_checks.tcl.proposed'
assert hashlib.sha256(PROD.read_bytes()).hexdigest()=='7419a97d224e848f3c414659f01e64962432139c9b7127a45713a28145fb3003'
old=PROD.read_text();new=CAND.read_text();lo=old.index('proc m003::resolve');hi=old.index('# Per-object support reused',lo);delta=(HERE/'resolver_delta.tcl').read_text();assert old[:lo]+delta+old[hi:]==new
old_role=old[old.index('    set original_address [dict create]',lo):old.index('    set meta [primitive_scope $meta_scope]',lo)]
API=r"""
proc get_cells {args} {
 if {[info exists ::forced_return]} {return $::forced_return}
 set f [lindex $args end];set patterns [regexp -all -inline {NAME (=~|==) "([^"]+)"} $f];set result {}
 dict for {id row} $::pool {
  if {[string first {IS_PRIMITIVE == 1} $f]>=0 && ![dict get $row IS_PRIMITIVE]} {continue}
  foreach {all op pattern} $patterns {
   set name [dict get $row NAME]
   if {($op eq {==} && $name eq $pattern) || ($op eq {=~} && [string match $pattern $name])} {lappend result $id;break}
  }
 }
 return $result
}
proc get_property {args} {return [dict get $::pool [lindex $args end] [lindex $args end-1]]}
"""
def table(rows):
 lines=['set pool [dict create]'];ids={}
 for i,row in enumerate(rows):
  assert all(not any(c in str(v) for c in '{}\\') for v in row.values());id='obj'+str(i);ids[row['NAME']]=id
  lines.append('dict set pool '+id+' [dict create '+' '.join(k+' {'+str(v)+'}' for k,v in row.items())+']')
 return '\n'.join(lines)+'\n',ids
class Address(unittest.TestCase):
 def fixture(self,mutation='',body=None,rows=None,prefix=''):
  rows=[{**x,'NAME':prefix+x['NAME']} for x in (ORIG if rows is None else rows)];text,ids=table(rows)
  code='source {'+str(PROD)+'}\nsource {'+str(HERE/'resolver_delta.tcl')+'}\n'+text+'set ::m003::core_meta_scope {'+prefix+CORE+'}\n'+API
  if body is None:body='set found [m003::original_address_members]\nfor {set bit 0} {$bit<17} {incr bit} {if {[get_property NAME [dict get $found $bit]] ne "$::m003::core_meta_scope/meta_read_addr_r_reg\\[$bit\\]"} {error wrong_bit}}\nputs [dict size $found]'
  code+=mutation+'\n'+body+'\n';p=subprocess.run(['tclsh'],input='if {[catch {\n'+code+'\n} msg]} {puts stderr $msg;exit 1}\n',text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr);return p.stdout.strip(),ids
 def test_all19_measured_candidates_select_exact17(self):self.assertEqual(self.fixture()[0],'17')
 def test_full_board_prefix_CPU_assembly(self):self.assertEqual(self.fixture(prefix='scalellm_vcu118_f05_bd_i/core/')[0],'17')
 def test_old_literal_parser_actually_fails_measured_carry(self):
  proc='proc m003::old_address_members {} {variable core_meta_scope;variable resolved;\n'+old_role+'\nreturn $original_address}\n'
  out,_=self.fixture(body=proc+'puts [catch {m003::old_address_members}]\nputs [dict size [m003::original_address_members]]');self.assertEqual(out,'1\n17')
 def test_compatible_FFs_and_optional_nonstate_neighbors(self):
  rows=[dict(x) for x in ORIG if x['REF_NAME']=='FDCE']
  for i,ref in enumerate(['FDRE','FDSE','FDPE']):rows[i]['REF_NAME']=ref
  self.assertEqual(self.fixture(rows=rows)[0],'17')
 def test_missing_wrong_type_extra_replica_malformed_and_foreign_rejected(self):
  _,ids=self.fixture();zero=ids[CORE+'/meta_read_addr_r_reg[0]'];last=ids[CORE+'/meta_read_addr_r_reg[16]'];carry=ids[CORE+'/meta_read_addr_r_reg[16]_i_5']
  cases=[f'dict unset pool {last}',f'dict set pool {zero} REF_NAME LUT3',f'dict set pool {carry} REF_NAME LUT2',f'dict set pool duplicate [dict get $pool {zero}]',f'set forced_return [concat [dict keys $pool] {zero}]']
  for tail,ref in [('meta_read_addr_r_reg[17]','FDCE'),('meta_read_addr_r_reg[00]','FDCE'),('meta_read_addr_r_reg[-1]','FDCE'),('meta_read_addr_r_reg[x]','FDCE'),('meta_read_addr_r_reg[0]_replica','FDCE'),('g_foreign/meta_read_addr_r_reg[0]','FDCE'),('meta_read_addr_r_reg[3]_i_1','CARRY8'),('meta_read_addr_r_reg[16]_i_6','CARRY8'),('meta_read_addr_r_reg[16]_i_5/child','CARRY8')]:cases.append('dict set pool extra [dict create NAME {'+CORE+'/'+tail+'} REF_NAME '+ref+' IS_PRIMITIVE 1 DONT_TOUCH {}]')
  cases.append('dict set pool extra [dict create NAME {other/meta_read_addr_r_reg[0]} REF_NAME FDCE IS_PRIMITIVE 1 DONT_TOUCH {}]\nset forced_return [dict keys $pool]')
  for mutation in cases:
   with self.subTest(mutation=mutation):self.assertEqual(self.fixture(mutation,body='puts [catch {m003::original_address_members}]')[0],'1')
 def test_filtered_foreign_nonfamily_never_admitted(self):
  out,_=self.fixture('dict set pool foreign [dict create NAME {other/meta_read_addr_r_reg[0]} REF_NAME FDCE IS_PRIMITIVE 1 DONT_TOUCH {}]');self.assertEqual(out,'17')
class ResolverReplay(unittest.TestCase):
 def test_closed_native_role_replay_with_explicit_synthetic_C01_and_CE_INIT_provenance(self):
  # No native all-graph claim: C01 root/primitive and module roots are synthetic;
  # CE INIT=2 comes from AT015 control-flow reachability, not AT014 field export.
  rep=HW/'vivado/reports/m003_E011_R002_AT014_fresh_core_native_role_attribution_v2';rows=[]
  for name in ['parent_payload_and_count_native','parent_buffer_native','metadata_native_names']:
   for line in (rep/(name+'.jsonl')).read_text().splitlines():
    field=json.loads(line)['fields'];x={key:field[key]['value'] for key in ['NAME','REF_NAME','IS_PRIMITIVE','DONT_TOUCH']}
    if name=='parent_buffer_native':x['INIT']="2'h2" # explicitly inferred CPU fixture value
    if x['NAME'] in CONTROL:x['INIT']=CONTROL[x['NAME']]['INIT'] # AT016 measured
    rows.append(x)
  rows.extend(ORIG);parent='inst/u_core/u_compute/u_mlp/u_serial_command/u_shared_compute';meta=CORE+'/u_meta';c01='inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf'
  rows.extend({'NAME':name,'REF_NAME':'SYNTHETIC_CPU_MODULE','IS_PRIMITIVE':'0','DONT_TOUCH':''} for name in [parent,meta,CORE,c01]);rows.append({'NAME':c01+'/synthetic_unqualified_member','REF_NAME':'FDRE','IS_PRIMITIVE':'1','DONT_TOUCH':''})
  text,ids=table(rows);code='source {'+str(PROD)+'}\nsource {'+str(HERE/'resolver_delta.tcl')+'}\n'+text+API
  for k,v in [('parent_scope',parent),('meta_scope',meta),('core_meta_scope',CORE),('c01_root',c01)]:code+='set ::m003::'+k+' {'+v+'}\n'
  code+='set found [m003::resolve]\nputs "[dict size [dict get $found core_address]] [dict size [dict get $found addresses 0]] [dict size [dict get $found addresses 1]] [llength [dict get $found memory 0]] [llength [dict get $found memory 1]]"\n'
  p=subprocess.run(['tclsh'],input='if {[catch {\n'+code+'\n} msg]} {puts stderr $msg;exit 1}\n',text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'17 17 17 40 40')
if __name__=='__main__':unittest.main(verbosity=2)
