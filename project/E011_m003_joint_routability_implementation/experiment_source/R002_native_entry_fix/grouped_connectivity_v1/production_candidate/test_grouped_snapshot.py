import copy,importlib.util,json,subprocess,sys,tempfile,types,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[5];HW=ROOT/'project/hardware';OLD=HERE.parent.parent/'effective_memory_snapshot_v1'
sys.path.insert(0,str(HERE));sys.path.insert(1,str(HW/'vivado/scripts'))
from m003_snapshot_decode import decode
spec=importlib.util.spec_from_file_location('grouped_candidate_evidence',HERE/'m003_joint_evidence.py');E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)
Q=types.ModuleType('unchanged_v2_fixture');Q.__file__=str(HW/'tests/test_m003_joint_qualification.py');exec(compile((OLD/'test_m003_joint_qualification.py.proposed').read_text(),Q.__file__,'exec'),Q.__dict__)
def norm(s):
 s=copy.deepcopy(s);s['meta']['kind']='native';s['schema']='M003_native_grouped_stream_v1';s['connection_groups']=[dict(id='G0',nets=['clk'],canonical_top_net='clk',leaf_drivers=[],driver_cells=[],driver_refs=[],primary_ports=['clk'],primary_port_directions=['IN'])];ends=[]
 for row in s['cells']:
  if 'C_nets' in row:
   assert row.pop('C_nets')=='clk';row['C_nets_group']='G0';ends.append(dict(pin=row['NAME']+'/C',group='G0',direct_nets=['clk']))
 for row in s['memory_pins']:
  if row['pin']=='CLK':
   for k in ('nets','drivers','driver_cells','driver_refs','primary_ports','primary_port_directions'):row.pop(k)
   row['connection_group']='G0';ends.append(dict(pin=row['cell']+'/CLK',group='G0',direct_nets=['clk']))
 for row in s['helper_pins']:
  if row.get('pin')=='C':
   assert row.pop('nets')=='clk';assert row.pop('drivers')=='';row['clock_connection_group']='G0'
 s['control_sources'].pop('clock');s['control_sources'].update(clock_group='G0',clock_pin='selected_meta/clk');ends.append(dict(pin='selected_meta/clk',group='G0',direct_nets=['clk']))
 s['connection_endpoints']=ends;s['connection_counts']=dict(endpoints=len(ends),groups=1);s['connection_api_counts']={};return s
BASE=Q.fixture()
for row in list(BASE['cells']):
 if row['role']=='payload':row['C_nets']='clk'
 if row['role']=='address':BASE['helper_pins'].append(dict(slice=row['slice'],cell=row['NAME'],pin='C',nets='clk',drivers=''))
class GroupedSnapshot(unittest.TestCase):
 def test_full_431x80_equivalence_and_v2_qualification(self):
  normalized=norm(BASE);expanded=decode(normalized);expected=copy.deepcopy(BASE);expected['meta']['kind']='native';self.assertEqual(expanded,expected)
  expanded['meta']['kind']='fixture';r=E.validate(expanded,Q.SPEC,fixture=True);self.assertTrue(r['passed'],r['errors'][:10]);self.assertEqual(len(expanded['memory_pins']),80*431)
  clocks=[r['nets'] for r in expanded['memory_pins'] if r['pin']=='CLK'];self.assertTrue(all(x is clocks[0] for x in clocks))
 def test_strict_group_reference_negatives(self):
  mutations=[lambda s:s['connection_endpoints'].pop(),lambda s:s['connection_endpoints'].append(copy.deepcopy(s['connection_endpoints'][0])),lambda s:s['connection_endpoints'][0].update(group='unknown'),lambda s:s['connection_endpoints'][0].update(direct_nets=['foreign']),lambda s:s['connection_groups'].append(copy.deepcopy(s['connection_groups'][0])),lambda s:s['connection_groups'][0].update(canonical_top_net='foreign'),lambda s:s['connection_groups'][0].update(primary_port_directions=['OUT']),lambda s:s['connection_groups'][0].update(leaf_drivers=['x/O'],driver_cells=['x'],driver_refs=['BUFG']),lambda s:s['connection_counts'].update(endpoints=0),lambda s:s['cells'][0].update(C_nets='forged'),lambda s:next(r for r in s['memory_pins'] if r['pin']=='CLK').update(nets='forged'),lambda s:s['control_sources'].update(clock='forged'),lambda s:s.update(schema='bad'),lambda s:s['meta'].update(kind='fixture'),lambda s:s['connection_endpoints'].append(dict(pin='unused/C',group='G0',direct_nets=['clk']))]
  for i,mutation in enumerate(mutations):
   with self.subTest(i=i):
    s=norm(BASE);mutation(s)
    with self.assertRaises(ValueError):decode(s)
 def run_tcl(self,body):
  checks=(HERE/'m003_joint_checks.tcl').read_text();jsonprocs=checks[checks.index('proc m003::jq'):checks.index('proc m003::write_jarray')]
  script='namespace eval m003 {}\n'+jsonprocs+'\nsource {'+str(HERE/'m003_snapshot_stream.tcl')+'}\n'+body
  r=subprocess.run(['tclsh'],input='if {[catch {\n'+script+'\n} message options]} {puts stderr [dict get $options -errorinfo];exit 1}\n',capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);return r.stdout
 def test_row_stream_emits_incrementally_and_retains_partial_on_error(self):
  with tempfile.TemporaryDirectory() as td:
   body='set out {'+td+'}\n'+r'''
proc m003_conn::event {args} {}
'''
   # Define stub namespace before source/test; no native API is used here.
   body='namespace eval m003_conn {}\n'+body+r'''
m003::stream_begin unit $out
for {set i 0} {$i<4096} {incr i} {m003::stream_row cells [dict create NAME cell$i literal {quote" slash\ newline} value $i]}
set st $::m003::stream_state
set path [dict get $st paths cells]
if {[file size $path]==0 || [dict get $st counts cells]!=4096} {error {row output was retained instead of emitted}}
if {[dict exists $st rows] || [dict exists $st payload]} {error {retained full row array}}
m003::stream_abort
if {![file exists $path] || [file exists [file join $out m003_native_unit.json]]} {error {error partial preservation failed}}
puts PASS
'''
   self.assertIn('PASS',self.run_tcl(body));rows=[json.loads(x) for x in (Path(td)/'m003_stream_unit_cells.jsonl.partial').read_text().splitlines()];self.assertEqual(len(rows),4096);self.assertEqual(rows[-1]['value'],'4095')
 def test_stream_finalize_and_normalized_decoder(self):
  # Use the independently asserted 80-different-direct-alias CPU API spy.
  sys.path.insert(0,str(HERE.parent));from test_grouped_clock import MOCK
  prefix=MOCK[:MOCK.index('set code [catch {')]
  checks=(HERE/'m003_joint_checks.tcl').read_text();procs=checks[checks.index('proc m003::jq'):checks.index('proc m003::cell_row')]
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);script=prefix+'\nnamespace eval m003 {}\n'+procs+'\nsource {'+str(HERE/'m003_snapshot_stream.tcl')+'}\n'+r'''
set ::m003::connection_token [m003_conn::begin synth [file join $report trace] [file join $report m003_connection_synth_groups.jsonl.partial] [file join $report m003_connection_synth_endpoints.jsonl.partial]]
m003::stream_begin synth $report
for {set i 0} {$i<34} {incr i} {
 dict set ::props pc$i NAME helper$i/C;dict set ::props pc$i REF_PIN_NAME C;dict set ::pinmap pc$i n[expr {$i+80}]
 set b [m003_conn::bind $::m003::connection_token pc$i]
 m003::stream_row cells [dict create role address NAME helper$i C_nets_group [dict get $b group]]
 m003::stream_row helper_pins [m003::helper_pin_row $::m003::connection_token [expr {$i/17}] helper$i pc$i 1]
}
for {set i 0} {$i<80} {incr i} {dict set ::props p$i REF_PIN_NAME CLK;m003::stream_row memory_pins [m003::memory_pin_row [expr {$i/40}] [get_property NAME c$i] p$i]}
dict set ::props boundary NAME selected_meta/clk;dict set ::pinmap boundary n0
set b [m003_conn::bind $::m003::connection_token boundary]
set cs [dict create clock_group [dict get $b group] clock_pin [dict get $b pin]]
set stats [m003_conn::finish $::m003::connection_token]
m003::stream_finish [file join $report snapshot.json] [dict create kind native phase synth] {} $cs $stats
'''
   (p/'test.tcl').write_text(script);r=subprocess.run(['tclsh',str(p/'test.tcl'),'one',str(p),str(HERE.parent)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   raw=json.loads((p/'snapshot.json').read_text());expanded=decode(raw);self.assertEqual(len(expanded['memory_pins']),80);self.assertEqual(raw['connection_counts'],dict(endpoints=115,groups=1));self.assertEqual(raw['connection_api_counts']['direct_net']['calls'],115);self.assertEqual(len(expanded['helper_pins']),34);self.assertEqual(raw['connection_api_counts']['segments']['calls'],1);self.assertEqual(raw['connection_api_counts']['canonical']['calls'],1)
   self.assertFalse(list(p.glob('*.partial')));self.assertTrue((p/'m003_stream_synth_memory_pins.jsonl').exists());self.assertEqual(expanded['memory_pins'][0]['primary_ports'],'core_clk')
 def test_helper_clock_reference_is_only_exact_second_address_C(self):
  for mutate in [lambda s:s['helper_pins'].append(copy.deepcopy(next(r for r in s['helper_pins'] if 'clock_connection_group' in r))),lambda s:next(r for r in s['helper_pins'] if 'clock_connection_group' in r).update(cell='foreign'),lambda s:next(r for r in s['helper_pins'] if 'clock_connection_group' in r).update(pin='D'),lambda s:next(r for r in s['helper_pins'] if 'clock_connection_group' in r).update(nets='forged')]:
   with self.subTest(mutate=mutate):
    s=norm(BASE);mutate(s)
    with self.assertRaises(ValueError):decode(s)
 def test_required_clock_witness_cannot_fall_back_to_raw_fields(self):
  for section,select,field in [('cells',lambda r:r.get('role')=='payload','C_nets_group'),('cells',lambda r:r.get('role')=='address','C_nets_group'),('helper_pins',lambda r:r.get('pin')=='C','clock_connection_group')]:
   s=norm(BASE);row=next(r for r in s[section] if select(r));row.pop(field);row['C_nets' if section=='cells' else 'nets']='clk'
   with self.assertRaises(ValueError):decode(s)
  s=norm(BASE);s['helper_pins']=[r for r in s['helper_pins'] if r.get('pin')!='C']
  with self.assertRaises(ValueError):decode(s)
 def test_entry_only_helper_closure_is_exact(self):
  spec=importlib.util.spec_from_file_location('grouped_recovery',HERE/'m003_synth_recovery.py');rec=importlib.util.module_from_spec(spec);spec.loader.exec_module(rec)
  names={'m003_native_init.py','m003_synth_recovery.py','m003_recover_synthesis.tcl','m003_shared_connectivity.tcl','m003_snapshot_stream.tcl','m003_snapshot_decode.py'}
  self.assertEqual({x.name for x in rec.ADDITIONS},names)
  old=HW/'vivado/scripts/m003_joint_evidence.py';prior={old:{'sha256':'a'}};new={old:{'sha256':'b'},**{x:{'sha256':'x'} for x in rec.ADDITIONS}}
  self.assertEqual(rec.validate_delta(prior,new)['changed'],[str(old)])
  for foreign in [HW/'rtl/forbidden.sv',HW/'vivado/scripts/undeclared.py']:
   with self.assertRaises(ValueError):rec.validate_delta(prior,{**new,foreign:{'sha256':'x'}})
 def test_entire_candidate_tcl_is_syntactically_complete(self):
  for n in ('m003_joint_checks.tcl','m003_shared_connectivity.tcl','m003_snapshot_stream.tcl'):
   self.run_tcl('set h [open {'+str(HERE/n)+'} r];set text [read $h];close $h\nif {![info complete $text]} {error {incomplete Tcl}}')
if __name__=='__main__':unittest.main(verbosity=2)
