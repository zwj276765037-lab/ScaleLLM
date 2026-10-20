"""CPU-only positive/negative checks of the new narrow diagnostic, never EDA."""
from pathlib import Path
import json,subprocess,tempfile,unittest
TCL=Path(__file__).with_name('read_original_address.tcl').resolve()
BASE=r"""
set ::env(M003_ORIGINAL_ADDRESS_LIBRARY_ONLY) 1
source {%s}
proc get_cells {args} {
 if {[string match {*meta_read_addr*} [lindex $args end]]} {return {ff0 logic0}}
 return {control0 control1}
}
proc get_property {args} {
 set key [lindex $args end-1];set obj [lindex $args end]
 switch -- $key {
  NAME {return $obj}
  REF_NAME {if {$obj eq {logic0}} {return LUT3};if {[string match control* $obj]} {return LUT2};return FDCE}
  IS_PRIMITIVE {return 1}
  DONT_TOUCH {return {}}
  INIT {return {4'h2}}
  default {error "unexpected property $key"}
 }
}
"""
class Diagnostic(unittest.TestCase):
 def run_diag(self,mutation=''):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);report=Path(tmp.name)
  code=BASE%TCL+mutation+'\nif {[catch {m003_addr_diag::run {'+str(report)+'}} msg]} {puts stderr $msg;exit 1}\n'
  p=subprocess.run(['tclsh'],input=code,text=True,capture_output=True);return p,report
 def test_complete_and_every_JSON_output_parses(self):
  p,r=self.run_diag();self.assertEqual(p.returncode,0,p.stderr)
  complete=json.loads((r/'diagnostic_complete.json').read_text());self.assertEqual(complete['api_errors'],0);self.assertEqual(complete['execution'],'completed')
  counts=json.loads((r/'query_counts.json').read_text());self.assertFalse(counts['constraint_apply_requested']);self.assertFalse(counts['new_synthesis_launched']);self.assertEqual(counts['collections']['original_address_broad']['count'],2)
  for file in r.glob('*.jsonl'):
   rows=[json.loads(line) for line in file.read_text().splitlines()];self.assertTrue(rows,file)
  rows=[json.loads(x) for x in (r/'original_address_broad.jsonl').read_text().splitlines()];self.assertEqual([x['fields']['REF_NAME']['value'] for x in rows],['FDCE','LUT3']);self.assertEqual(rows[0]['fields']['DONT_TOUCH'],{'status':'OK_EMPTY','value':''})
  controls=[json.loads(x) for x in (r/'local_control_luts.jsonl').read_text().splitlines()];self.assertEqual(controls[0]['fields']['INIT']['value'],"4'h2")
  self.assertEqual(json.loads((r/'diagnostic_progress.jsonl').read_text().splitlines()[-1])['event'],'diagnostic_complete');self.assertFalse(list(r.glob('*.partial')))
 def test_field_error_preserves_partial_and_no_completion(self):
  p,r=self.run_diag('rename get_property original_get_property\nproc get_property {args} {if {[lindex $args end-1] eq "REF_NAME"} {error {forced native failure}};return [original_get_property {*}$args]}')
  self.assertNotEqual(p.returncode,0);self.assertFalse((r/'diagnostic_complete.json').exists());self.assertTrue((r/'original_address_broad.jsonl.partial').exists());row=json.loads((r/'original_address_broad.jsonl.partial').read_text().splitlines()[0]);self.assertEqual(row['fields']['REF_NAME']['status'],'API_ERROR')
 def test_empty_duplicate_or_excess_collection_has_no_success(self):
  for mutation in ['proc get_cells {args} {return {}}','proc get_cells {args} {return {same same}}','set ::m003_addr_diag::max_rows 1']:
   with self.subTest(mutation=mutation):
    p,r=self.run_diag(mutation);self.assertNotEqual(p.returncode,0);self.assertFalse((r/'diagnostic_complete.json').exists());self.assertIn('invalid_count',(r/'diagnostic_progress.jsonl').read_text())
 def test_quote_roundtrip(self):
  raw='quote" slash\\ braces{} brackets[]\nline\tlast'
  code='set ::env(M003_ORIGINAL_ADDRESS_LIBRARY_ONLY) 1\nsource {'+str(TCL)+'}\nputs [m003_addr_diag::quote {quote" slash\\ braces{} brackets[]\nline\tlast}]\n'
  p=subprocess.run(['tclsh'],input=code,text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout),raw)
 def test_library_mode_requires_no_native_commands(self):
  p=subprocess.run(['tclsh'],input='set ::env(M003_ORIGINAL_ADDRESS_LIBRARY_ONLY) 1\nsource {'+str(TCL)+'}\n',text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stderr,'')
if __name__=='__main__':unittest.main(verbosity=2)
