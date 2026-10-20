"""A007 fixed-identity CPU tests for AT020 raw startpoint/clock diagnostics."""
from pathlib import Path
import importlib.util,json,unittest
P=Path(__file__).with_name('AT020_fixed_fixture')/'address_startpoint_semantics_v1/test_diagnostic.py'
s=importlib.util.spec_from_file_location('submitted',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Independent(unittest.TestCase):
 run_diag=m.StateSources.run_diag
 def test_nonregister_startpoint_without_Q_is_preserved(self):
  mutation=r"""
rename all_fanin original_all_fanin
proc all_fanin {args} {
 if {[lsearch -exact $args -startpoints_only]>=0 && [lsearch -exact $args -only_cells]<0} {return [concat [original_all_fanin {*}$args] {comb/O}]}
 return [original_all_fanin {*}$args]
}
rename get_property original_get_property
proc get_property {key objects} {if {$key eq {REF_NAME} && [lindex $objects 0] eq {comb}} {return LUT6};return [original_get_property $key $objects]}
rename get_pins original_get_pins
proc get_pins {args} {if {[lindex $args end] eq {REF_PIN_NAME == Q} && [lindex [lindex $args end-2] 0] eq {comb}} {return {}};return [original_get_pins {*}$args]}
"""
  p,r=self.run_diag(mutation);self.assertEqual(p.returncode,0,p.stderr)
  row=json.loads((r/'helper_D_sources.jsonl').read_text().splitlines()[0]);fact=row['actual_source_owner_facts'][-1]
  self.assertEqual(fact['raw_name'],'comb/O');self.assertEqual(fact['owner_refs'],['LUT6']);self.assertEqual(fact['owner_Q_pins'],[]);self.assertEqual(fact['owner_Q_in_full_fanin'],[])
 def test_unresolved_clock_does_not_fabricate_primary_port(self):
  p,r=self.run_diag('proc get_nets {args} {return {}}\nproc get_ports {args} {error {query on empty nets must not execute}}')
  self.assertEqual(p.returncode,0,p.stderr)
  rows=[json.loads(x) for x in (r/'uram_clock_sources.jsonl').read_text().splitlines()]
  self.assertTrue(all(x['nets']==x['leaf_drivers']==x['primary_ports']==x['primary_port_directions']==[] for x in rows))
 def test_ambiguous_source_owner_is_failure(self):
  p,r=self.run_diag('rename get_cells original_get_cells\nproc get_cells {args} {if {[lsearch -exact $args -hier]<0} {return {a b}};return [original_get_cells {*}$args]}')
  self.assertNotEqual(p.returncode,0);self.assertIn('Non-singleton startpoint owner',p.stderr);self.assertFalse((r/'diagnostic_complete.json').exists());self.assertTrue((r/'helper_D_sources.jsonl.partial').exists())
if __name__=='__main__':
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m),unittest.defaultTestLoader.loadTestsFromTestCase(Independent)])
 result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(0 if result.wasSuccessful() else 1)
