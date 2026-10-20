"""A007 bounded CPU-only diagnostic boundary and evidence-preservation tests."""
from pathlib import Path
import json,os,subprocess,tempfile,unittest
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
TCL=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/original_address_diagnostic_v1/read_original_address.tcl'
BASE=r'''
set ::env(M003_ORIGINAL_ADDRESS_LIBRARY_ONLY) 1
source {%s}
set ::queries {}
proc get_cells {args} {
 set f [lindex $args end];lappend ::queries $f
 if {$f eq {IS_PRIMITIVE == 1 && NAME =~ "inst/u_core/u_compute/u_attention/*meta_read_addr_r_reg*"}} {
  return {{inst/u_core/u_compute/u_attention/meta_read_addr_r_reg[0]} {inst/u_core/u_compute/u_attention/meta_read_addr_r_reg[0]_i_1}}
 }
 if {$f eq {IS_PRIMITIVE == 1 && NAME =~ "inst/u_core/u_compute/u_attention/u_meta/*u_addr/u_local_*"}} {
  return {{inst/u_core/u_compute/u_attention/u_meta/g_slice[0].u_slice/u_addr/u_local_ce} {inst/u_core/u_compute/u_attention/u_meta/g_slice[1].u_slice/u_addr/u_local_increment}}
 }
 error "Unexpected native query $f"
}
proc get_property {args} {
 set field [lindex $args end-1];set object [lindex $args end]
 switch -- $field {
 NAME {return $object}
 REF_NAME {if {[string match *i_1 $object]} {return LUT6};if {[string match *u_local* $object]} {return LUT3};return FDRE}
 IS_PRIMITIVE {return 1}
 DONT_TOUCH {return {}}
 INIT {if {![string match *u_local* $object]} {error "INIT outside control query"};return {8'hFE}}
 default {error "Unsupported field $field"}
 }
}
'''
class Independent(unittest.TestCase):
 def run_diag(self,patch='',precreate=None):
  td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);p=Path(td.name)
  if precreate:
   for name,value in precreate.items():(p/name).write_text(value)
  code=BASE%TCL+patch+'\nif {[catch {m003_addr_diag::run {'+str(p)+'}} e]} {puts stderr $e;exit 1}\nputs "QUERY_COUNT=[llength $::queries]"\n'
  result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True,cwd=ROOT/'project/hardware')
  return result,p
 def test_exact_query_scope_preserves_nonFF_candidate_and_original_names(self):
  result,p=self.run_diag();self.assertEqual(result.returncode,0,result.stderr);self.assertIn('QUERY_COUNT=2',result.stdout)
  rows=[json.loads(x) for x in (p/'original_address_broad.jsonl').read_text().splitlines()]
  self.assertEqual([r['fields']['REF_NAME']['value'] for r in rows],['FDRE','LUT6'])
  for r in rows:self.assertEqual(r['object'],r['fields']['NAME']['value']);self.assertNotIn('INIT',r['fields']);self.assertEqual(r['fields']['DONT_TOUCH']['status'],'OK_EMPTY')
  controls=[json.loads(x) for x in (p/'local_control_luts.jsonl').read_text().splitlines()]
  self.assertTrue(all(r['fields']['INIT']['value']=="8'hFE" for r in controls))
 def test_second_collection_field_failure_preserves_first_closed_and_second_partial(self):
  result,p=self.run_diag('rename get_property get_property_ok\nproc get_property {args} {if {[lindex $args end-1] eq {INIT}} {error "native INIT failure"};return [get_property_ok {*}$args]}\n')
  self.assertNotEqual(result.returncode,0);self.assertTrue((p/'original_address_broad.jsonl').exists());self.assertTrue((p/'local_control_luts.jsonl.partial').exists());self.assertFalse((p/'query_counts.json').exists());self.assertFalse((p/'diagnostic_complete.json').exists())
  rows=[json.loads(x) for x in (p/'local_control_luts.jsonl.partial').read_text().splitlines()];self.assertTrue(all(r['fields']['INIT']['status']=='API_ERROR' for r in rows))
 def test_native_query_error_emits_no_false_completion(self):
  result,p=self.run_diag('proc get_cells {args} {error "native get_cells failure"}\n')
  self.assertNotEqual(result.returncode,0);self.assertFalse((p/'diagnostic_complete.json').exists());self.assertFalse((p/'query_counts.json').exists())
  events=[json.loads(x) for x in (p/'diagnostic_progress.jsonl').read_text().splitlines()]
  self.assertEqual(events[-1]['event'],'collection_begin')
 def test_full_2048_bound_exports_every_candidate(self):
  patch='proc get_cells {args} {set a {};for {set i 0} {$i<2048} {incr i} {lappend a "u_local_$i"};return $a}\n'
  result,p=self.run_diag(patch);self.assertEqual(result.returncode,0,result.stderr)
  for f in ['original_address_broad.jsonl','local_control_luts.jsonl']:
   rows=[json.loads(x) for x in (p/f).read_text().splitlines()];self.assertEqual([r['index'] for r in rows],list(range(2048)));self.assertEqual(len({r['object'] for r in rows}),2048)
  counts=json.loads((p/'query_counts.json').read_text());self.assertTrue(all(x['count']==2048 for x in counts['collections'].values()))
 def test_overbound_count_is_recorded_without_completion(self):
  patch='proc get_cells {args} {set a {};for {set i 0} {$i<2049} {incr i} {lappend a "u_local_$i"};return $a}\n'
  result,p=self.run_diag(patch);self.assertNotEqual(result.returncode,0);self.assertFalse((p/'diagnostic_complete.json').exists())
  events=[json.loads(x) for x in (p/'diagnostic_progress.jsonl').read_text().splitlines()]
  self.assertEqual(events[-1]['event'],'diagnostic_error');self.assertEqual(events[-1]['count'],'2049');self.assertEqual(events[-2]['event'],'collection_end')
 def test_prior_report_refused_and_preserved(self):
  result,p=self.run_diag(precreate={'diagnostic_progress.jsonl':'ORIGINAL EVIDENCE\n'})
  self.assertNotEqual(result.returncode,0);self.assertEqual((p/'diagnostic_progress.jsonl').read_text(),'ORIGINAL EVIDENCE\n');self.assertFalse((p/'diagnostic_complete.json').exists())
if __name__=='__main__':unittest.main(verbosity=2)
