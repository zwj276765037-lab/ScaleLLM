import copy,importlib.util,json,sys,unittest
from pathlib import Path
HW=Path(__file__).resolve().parents[1]
def module(name):
 sys.path.insert(0,str(HW/'vivado/scripts'))
 spec=importlib.util.spec_from_file_location(name,HW/'vivado/scripts'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
E=module('m003_joint_evidence');B=module('m003_resource_budget');ENTRY=module('m003_entry')
SPEC=json.loads((HW/'vivado/constraints/m003_joint_locality_spec.json').read_text())
def cell(name,role,ref,**kw):
 return dict(NAME=name,role=role,REF_NAME=ref,IS_LOC_FIXED='0',IS_BEL_FIXED='0',MACRO_NAME='',**kw)
def fixture():
 s=dict(meta=dict(kind='fixture',part='xcvu9p-flga2104-2L-e',phase='opt'),cells=[],ce_edges=[],master_inputs=[],memory_pins=[],pblocks=[],target_sites={},boundaries=[],helper_pins=[],uram_configs=[],control_sources=dict(S='S',L='L',R='R',clock='clk',reset='rst'))
 for bit in range(17):s['cells'].append(cell('core_addr/'+str(bit),'core_address','FDCE',bit=bit,C_nets='clk',CLR_nets='rst'))
 def pb(name,sites):s['pblocks'].append(dict(NAME=name,actual_sites=' '.join(sites),IS_SOFT='0',EXCLUDE_PLACEMENT='0',CONTAIN_ROUTING='0'))
 for r in SPEC['regions']:
  sites=[r['clock_region']+'_SLICE_'+str(i) for i in range(r['native_CLB_site_count'])]
  name='m003_parent_'+r['clock_region'];pb(name,sites);s['target_sites'][name]=' '.join(sites)
 for g in SPEC['groups']:
  name='buffer/'+g['id'];pbname='m003_parent_'+g['clock_region']
  s['cells'].append(cell(name,'buffer','LUT1',group=g['id'],DONT_TOUCH='1',INIT="2'h2",PBLOCKS=pbname))
  for bit in g['bits']:
   load=g['family']+'/'+str(bit)
   s['cells'].append(cell(load,'payload','FDRE',family=g['family'],bit=bit,PBLOCKS=pbname))
   s['ce_edges'].append(dict(group=g['id'],load=load,pin='CE',source=name))
  loads=['buffer/'+z['id']+'/I0' for z in SPEC['groups'] if z['family']==g['family']]
  s['master_inputs'].append(dict(group=g['id'],family=g['family'],driver=g['family']+'_master/O',load_pins=' '.join(loads)))
 for i,pool in enumerate(SPEC['meta_pools']):
  pb('m003_meta_slice'+str(i)+'_uram',pool['URAM_sites']);pb('m003_meta_slice'+str(i)+'_address',pool['CLB_sites'])
  p='slice'+str(i);addresspb='m003_meta_slice'+str(i)+'_address'
  for bit in range(17):s['cells'].append(cell(p+'/address/'+str(bit),'address','FDCE',slice=i,bit=bit,DONT_TOUCH='1',PBLOCKS=addresspb,D_startpoints=p+'/address/'+str(bit)+'/Q',C_nets='clk',CLR_nets='rst',CE_nets=p+'ce',CE_drivers=p+'/u_local_ce/O'))
  for name,ref,value in [('u_local_ce','LUT3',"8'hfe"),('u_local_increment','LUT2',"4'h2")]:s['cells'].append(cell(p+'/'+name,'address_logic',ref,slice=i,DONT_TOUCH='1',INIT=value,PBLOCKS=addresspb))
  for suffix,mapping in [('u_local_ce',{'I0':'S','I1':'L','I2':'R'}),('u_local_increment',{'I0':'R','I1':'S'})]:
   for pin,net in mapping.items():s['helper_pins'].append(dict(slice=i,cell=p+'/'+suffix,pin=pin,nets=net))
  for k in range(40):
   name=p+'/uram/'+str(k);s['cells'].append(cell(name,'memory','URAM288',slice=i,PBLOCKS='m003_meta_slice'+str(i)+'_uram'));s['uram_configs'].append(dict(NAME=name,slice=i,CASCADE_ORDER_A='NONE'))
   for terminal,ref in [('RDB_WR_A','GND'),('RDB_WR_B','VCC')]:s['memory_pins'].append(dict(slice=i,cell=name,pin=terminal,driver_refs=ref))
  for b in range(17):s['memory_pins'].append(dict(slice=i,cell=p+'/uram/0',pin='ADDR_A['+str(b)+']',drivers=p+'/address/'+str(b)+'/Q'))
 name='m002_exact_hotspot_SLR2';sites=['SLR2_SITE_'+str(i) for i in range(42)];pb(name,sites);s['target_sites'][name]=' '.join(sites)
 for n in SPEC['C01_protected_names']:s['cells'].append(cell(n,'c01','LUT1',DONT_TOUCH='1',PBLOCKS=name))
 for ref,n in [('RAMB36E2',6),('DSP48E2',2)]:
  for i in range(n):s['cells'].append(cell('C01/'+ref+'/'+str(i),'c01',ref,PBLOCKS=name))
 for tag,n,ref,width in [('input',48,'LUT6',256),('gate',16,'LUT1',384),('down',16,'LUT1',512)]:
  for i in range(n):s['boundaries'].append(dict(NAME=tag+'/'+str(i),tag=tag,REF_NAME=ref,DONT_TOUCH='1',load_count=width,load_terminals='CE'))
 return s
class Qualification(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.base=fixture()
 def test_positive_explicit_fixture(self):
  v=E.validate(self.base,SPEC,fixture=True);self.assertTrue(v['passed'],v['errors']);self.assertTrue(v['fixture']);self.assertTrue(v['limits_not_timing_proof'])
 def reject(self,mutation,match):
  s=copy.deepcopy(self.base);mutation(s);r=E.validate(s,SPEC,fixture=True)
  self.assertFalse(r['passed']);self.assertTrue(any(match in e for e in r['errors']),(match,r['errors'][:8]))
 def test_native_cannot_use_fixture(self):self.assertFalse(E.validate(self.base,SPEC)['passed'])
 def test_missing_overlay(self):self.reject(lambda s:s['pblocks'].pop(),'pblock name/count')
 def test_same_capacity_wrong_parent_region(self):self.reject(lambda s:s['pblocks'][0].update(actual_sites=' '.join('wrong'+str(i) for i in s['pblocks'][0]['actual_sites'].split())),'exact target CR')
 def test_same_capacity_wrong_C01_region(self):self.reject(lambda s:s['pblocks'][-1].update(actual_sites=s['pblocks'][-1]['actual_sites'].replace('SLR2','SLR1')),'exact SLR2')
 def test_duplicate_master_group(self):self.reject(lambda s:s['master_inputs'].__setitem__(0,s['master_inputs'][1]),'master group exact')
 def test_wrong_CE(self):self.reject(lambda s:s['ce_edges'][0].update(source='wrong'),'wrong driver')
 def test_wrong_payload_bit(self):self.reject(lambda s:next(r for r in s['cells'] if r['role']=='payload').update(bit=99999),'payload bit coverage')
 def test_unknown_compatible_resource(self):self.reject(lambda s:next(r for r in s['cells'] if r['role']=='payload').update(REF_NAME='UNKNOWN'),'unknown payload')
 def test_merged_counter(self):self.reject(lambda s:s['cells'].remove(next(r for r in s['cells'] if r['role']=='address')),'address34')
 def test_unloaded_counter(self):self.reject(lambda s:s['memory_pins'].pop(),'unloaded/missing bit')
 def test_reset_semantics_changed(self):self.reject(lambda s:next(r for r in s['cells'] if r['role']=='address').update(CLR_nets='datapath_clear'),'reset differs')
 def test_wrong_control_source(self):self.reject(lambda s:s['helper_pins'][0].update(nets='wrong'),'S/L/R pin source')
 def test_wrong_native_RDW_port(self):self.reject(lambda s:s['memory_pins'][0].update(driver_refs='VCC'),'read-A/write-B')
 def test_native_configuration_missing(self):self.reject(lambda s:s['uram_configs'].pop(),'configuration inventory')
 def test_cross_pool_cascade(self):self.reject(lambda s:s['memory_pins'].append(dict(slice=0,cell='slice0/uram/1',pin='CAS_IN_ADDR_A[0]',drivers='slice1/uram/0/CAS_OUT_ADDR_A[0]')),'cascade crosses')
 def test_counter_CE_crosses_slice(self):self.reject(lambda s:next(r for r in s['cells'] if r['role']=='address').update(CE_drivers='slice1/u_local_ce/O'),'own protected local CE')
 def test_cross_slice_source(self):self.reject(lambda s:next(p for p in s['memory_pins'] if p['pin']=='ADDR_A[0]').update(drivers='slice1/address/0/Q'),'cross-slice')
 def test_lost_C01_protection(self):self.reject(lambda s:next(r for r in s['cells'] if r['NAME'] in SPEC['C01_protected_names']).update(DONT_TOUCH='0'),'C01 original protection')
 def test_lost80_protection(self):self.reject(lambda s:s['boundaries'][0].update(DONT_TOUCH='0'),'80-boundary')
 def test_macro_requires_qualification(self):self.reject(lambda s:s['cells'][0].update(MACRO_NAME='foreign_macro'),'macro requires')
 def test_fixed_policy_unknown(self):self.reject(lambda s:s['cells'][0].update(IS_LOC_FIXED='NOT_SUPPORTED'),'unknown resource fixed')
 def test_wrong_pool(self):self.reject(lambda s:next(p for p in s['pblocks'] if p['NAME']=='m003_meta_slice0_uram').update(actual_sites='URAM_X0Y0'),'resource set mismatch')
 def test_restored_constraints_missing(self):self.reject(lambda s:s['pblocks'].clear(),'overlay omitted')
 def test_soft_constraint(self):self.reject(lambda s:s['pblocks'][0].update(IS_SOFT='1'),'hard/nonexclusive')
 def test_extra_URAM(self):self.reject(lambda s:s['cells'].append(cell('extra','memory','URAM288',slice=0,PBLOCKS='m003_meta_slice0_uram')),'URAM40')
 def test_registration_policy(self):
  row=dict(NAME='/constraints/m003_joint_locality.xdc',FILE_TYPE='TCL',USED_IN_SYNTHESIS='false',USED_IN_IMPLEMENTATION='true',IS_ENABLED='true',PROCESSING_ORDER='LATE',SCOPED_TO_REF='',SCOPED_TO_CELLS='')
  self.assertTrue(ENTRY.check_registration([row]))
  for key,value in [('FILE_TYPE','XDC'),('FILE_TYPE',''),('USED_IN_SYNTHESIS','true'),('USED_IN_IMPLEMENTATION','false'),('IS_ENABLED','false'),('PROCESSING_ORDER','NORMAL'),('SCOPED_TO_REF','wrong')]:
   with self.assertRaises(ValueError):ENTRY.check_registration([{**row,key:value}])
  with self.assertRaises(ValueError):ENTRY.check_registration([])
 def test_source_mismatch(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.json';p.write_text(json.dumps(dict(G2_sha256='wrong',sources=[])))
   with self.assertRaises(ValueError):ENTRY.check_sources(p)
 def test_renamed_route_wrong_part_missing_header(self):
  import tempfile
  base=json.loads(B.BASE.read_text());original=Path(base['reports'][0]['path']).read_text()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'utilization_hierarchical_post_synth.rpt'
   for bad in (original.replace('Synthesized','Routed'),original.replace('xcvu9p-flga2104-2L-e','xcvu9p-wrong'),original[original.index('Utilization Design Information'):],original.replace('Build 6299465','Build wrong')):
    p.write_text(bad)
    with self.assertRaises(ValueError):B.parse_hierarchy(p)
 def test_same_stage_metric_parser(self):
  base=Path(B.BASE);x=json.loads(base.read_text());h=Path(x['reports'][0]['path']);g=Path(x['reports'][1]['path'])
  observed=B.parse_hierarchy(h);expected={k:{m:v[m] for m in B.KEYS} for k,v in x['hierarchical_resources'].items()}
  self.assertEqual(observed,expected);self.assertEqual(B.parse_carry(g),54364)
  self.assertTrue(B.compare(observed,expected,54364,54364)['passed'])
  for scope,key,delta in [('top','total_LUTs',178),('u_meta','FFs_report_including_AND_OR',35),('u_shared_compute','FFs_report_including_AND_OR',1),('top','URAM',1)]:
   bad=copy.deepcopy(observed);bad[scope][key]+=delta;self.assertFalse(B.compare(bad,expected,54364,54364)['passed'])
  self.assertFalse(B.compare(observed,expected,54373,54364)['passed'])
if __name__=='__main__':unittest.main()

class TclEntryChecks(unittest.TestCase):
 def run_tcl(self,code):
  import subprocess
  r=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertNotIn('invalid command',r.stderr);return r
 def test_all_modified_tcl_complete(self):
  for name in ['m003_joint_checks.tcl','m003_physical.tcl','m003_recover_synthesis.tcl','create_vcu118_board.tcl','build_vcu118_board.tcl','m002_physical.tcl','m002_diagnostic_common.tcl']:
   p=HW/'vivado/scripts'/name
   r=self.run_tcl('set h [open {'+str(p)+'}];set code [read $h];close $h;puts [info complete $code]\n');self.assertEqual(r.stdout.strip(),'1',name)
 def test_serializer_roundtrip(self):
  import subprocess
  p=HW/'vivado/scripts/m003_joint_checks.tcl'
  r=self.run_tcl('source {'+str(p)+'}\nset value {quote" backslash\\ brackets[] braces{}\nline}\nputs [m003::jobject [dict create value $value]]\n')
  self.assertEqual(json.loads(r.stdout),{'value':'quote" backslash\\ brackets[] braces{}\nline'})
 def test_hard_conflict_macro_unknown_or_fixed_outside_rejected(self):
  p=HW/'vivado/scripts/m003_joint_checks.tcl'
  head='source {'+str(p)+'}\n'+r'''
set properties [dict create IS_LOC_FIXED 0 IS_BEL_FIXED 0 MACRO_NAME {} RLOC {} RLOC_ORIGIN {} LOC SLICE_X0Y0]
set others {}
proc list_property {object} {if {$object eq "cell"} {return [dict keys $::properties]};return {IS_SOFT}}
proc get_property {args} {set object [lindex $args end];set property [lindex $args end-1];if {$object eq "cell"} {return [dict get $::properties $property]};if {$property eq "IS_SOFT"} {return 0};error "unexpected fixture property: $object/$property"}
proc get_pblocks {args} {if {[lsearch $args -of_objects]>=0} {return $::others};return target}
proc get_sites {args} {return [lindex $args end]}
proc set_property {args} {}
proc resize_pblock {args} {}
proc add_cells_to_pblock {args} {}
if {[catch {m003::hard_pblock target SLICE_X0Y0 cell} msg]} {error "positive fixture failed: $msg"}
'''
  for mutation in ['dict set properties MACRO_NAME unknown','dict set properties RLOC X0Y0','dict set properties IS_LOC_FIXED NOT_SUPPORTED','dict set properties IS_LOC_FIXED 1;dict set properties LOC SLICE_X9Y9','set others foreign']:
   r=self.run_tcl(head+mutation+'\nputs [catch {m003::hard_pblock target SLICE_X0Y0 cell}]\n');self.assertEqual(r.stdout.strip(),'1',mutation)
 def test_restore_requires_verified_candidate_and_never_reapplies(self):
  text=(HW/'vivado/scripts/m003_physical.tcl').read_text();restore=text[text.index('open_checkpoint $::env(HAP_RECOVERY_CHECKPOINT)'):]
  self.assertIn('m003::snapshot restore',restore);self.assertNotIn('read_xdc',restore);self.assertNotRegex(restore,r'(?m)^\s*m003::apply(?:\s|$)')
  self.assertLess(text.index('set ::env(HAP_M003_RESTORE_VERIFY_ONLY) 1'),text.index('open_checkpoint $::env(HAP_RECOVERY_CHECKPOINT)'))
  source=(HW/'vivado/scripts/m003_joint_checks.tcl').read_text();self.assertIn('restore missing actual candidate registration qualification',source)
 def test_selected_stage_must_be_new_synthesis_and_fixed_strategy(self):
  text=(HW/'vivado/scripts/m003_physical.tcl').read_text()
  self.assertLess(text.index('m003_stage.py] lineage'),text.index('launch_runs impl_1'))
  self.assertIn('m003_command place {place_design -directive SSI_SpreadSLLs}',text)
  self.assertIn('m003_command physopt {phys_opt_design -directive Default}',text)
  self.assertIn('m003_command route {route_design -directive Default}',text)
  self.assertNotIn('write_bitstream',text)

class SourceClosure(unittest.TestCase):
 def test_frozen_local_import_and_safety_closure(self):
  x=ENTRY.check_sources();paths={Path(e['path']) for e in x['sources']}
  self.assertEqual(ENTRY.local_import_closure(paths),paths)
  for name in ['run_managed_eda.py','run_vcu118_board.sh','emit_current_board_evidence.py','m002_physical_evidence.py','m002_execution_profile.py','m002_synthesis_recovery.py','m002_fresh_project_opt_recovery.py','m002_impl_threads.tcl','m002_route_failure_capture.tcl']:
   self.assertIn(HW/'vivado/scripts'/name,paths)

class NativeProbeChecks(unittest.TestCase):
 def make(self):
  import tempfile
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);base=Path(d.name)
  report=base/'report';synth=base/'synth';project=base/'project'
  report.mkdir();synth.mkdir();run=project/'scalellm_vcu118_f05.runs/scalellm_vcu118_f05_bd_core_0_synth_1';run.mkdir(parents=True)
  (run/'runme.log').write_text('WARNING: [Synth 8-7137] Register u.test_reg[1] in module core has both set/reset\n')
  def cdc(src,dst):return 'CDC Report\nCDC-3 Info 1 synchronized\nCDC-10 Critical 1 Logic\nSource Clock: source_clk\nDestination Clock: dest_clk\n0  CDC-3  Info  Sync  4  False Path  info/Q  info/D\n1  CDC-10  Critical  Logic  4  Asynch  '+src+'  '+dst+'\n'
  (synth/'cdc_post_synth.rpt').write_text(cdc('old_source/Q','baseline/D'))
  (report/'cdc_opt.rpt').write_text(cdc('actual_source[0]/Q','actual_target[2]/D'))
  anchor=report/'anchor';anchor.write_text('fixed');(report/'stage_inputs.sha256').write_text(E.sha(anchor)+'  '+str(anchor)+'\n')
  return report,synth,project,cdc
 def test_phase_actual_CDC_and_warning_identity_and_safe_Tcl(self):
  S=module('m003_stage');r,b,p,cdc=self.make();v=S.prepare_probe(r,'opt',b,p,fixture=True)
  self.assertEqual(v['sources'],['actual_source[0]/Q']);self.assertEqual(v['targets'],['actual_target[2]/D'])
  import subprocess
  code='source {'+v['probe']['path']+'}\nputs [lindex $::m002_cdc_targets 0]\nputs [lindex $::m002_actual_critical_sources 0]\nputs [lindex $::m002_warning_registers 0]\n'
  result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.splitlines(),['baseline/D','actual_source[0]/Q','test_reg[1]'])
  with self.assertRaises(ValueError):S.verify_probe(r,'opt')
 def test_missing_current_report_rejected(self):
  S=module('m003_stage');r,b,p,cdc=self.make();(r/'cdc_opt.rpt').unlink()
  with self.assertRaises(FileNotFoundError):S.prepare_probe(r,'opt',b,p,fixture=True)
 def test_malformed_current_report_rejected(self):
  S=module('m003_stage');r,b,p,cdc=self.make();(r/'cdc_opt.rpt').write_text('CDC-10 fake')
  with self.assertRaises(ValueError):S.prepare_probe(r,'opt',b,p,fixture=True)
 def test_no_phase_overwrite(self):
  S=module('m003_stage');r,b,p,cdc=self.make();S.prepare_probe(r,'opt',b,p,fixture=True)
  with self.assertRaises(ValueError):S.prepare_probe(r,'opt',b,p,fixture=True)
 def test_multiple_phases_no_duplicate_sources(self):
  S=module('m003_stage');r,b,p,cdc=self.make();S.prepare_probe(r,'opt',b,p,fixture=True)
  (r/'cdc_debug_materialized.rpt').write_text(cdc('different/Q','new/D'));S.prepare_probe(r,'debug_materialized',b,p,fixture=True)
  self.assertEqual(len(S.old.input_manifest(r/'stage_inputs.sha256')),7)
 def test_probe_generated_before_native_reset_probes(self):
  text=(HW/'vivado/scripts/m002_diagnostic_common.tcl').read_text();start=text.rfind('m003_stage.py] prepare-probe')
  self.assertLess(start,text.index('if {$point in {init opt debug_materialized}} {m002_probe_netlist $point}',start))
  self.assertLess(start,text.index('m002_reset_snapshot $point',start))

class SystemPythonEnvironment(unittest.TestCase):
 def polluted(self,code):
  import os,subprocess,tempfile
  with tempfile.TemporaryDirectory() as d:
   env={**os.environ,'PYTHONHOME':d+'/wrong_python_home','PYTHONPATH':d+'/poisoned_modules'}
   return subprocess.run(['tclsh'],input=code,text=True,capture_output=True,env=env)
 def test_raw_system_python_reproduces_encoding_failure(self):
  r=self.polluted('puts [catch {exec /usr/bin/python3 -c {import encodings}} message]\nputs [string match {*encodings*} $message]\n')
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout.splitlines(),['1','1'])
 def test_clean_child_preserves_vivado_environment_and_argument_boundaries(self):
  script=HW/'vivado/scripts/m003_system_python.tcl'
  code='source {'+str(script)+'}\n'+r'''
set old_home $::env(PYTHONHOME)
set old_path $::env(PYTHONPATH)
puts [m003_python -c {import os,sys,encodings,json;print(json.dumps([sys.executable, "PYTHONHOME" in os.environ, "PYTHONPATH" in os.environ,sys.argv[1]]))} {spaces [literal] $body}]
puts [expr {$old_home eq $::env(PYTHONHOME) && $old_path eq $::env(PYTHONPATH)}]
'''
  r=self.polluted(code);self.assertEqual(r.returncode,0,r.stderr)
  lines=r.stdout.splitlines();self.assertEqual(json.loads(lines[0]),['/usr/bin/python3',False,False,'spaces [literal] $body']);self.assertEqual(lines[1],'1')
 def test_actual_selected_entry_source_command_in_polluted_env(self):
  script=HW/'vivado/scripts/m003_system_python.tcl';entry=HW/'vivado/scripts/m003_entry.py'
  r=self.polluted('source {'+str(script)+'}\nputs [m003_python {'+str(entry)+'} check-sources]\nputs [llength [split [m003_python {'+str(entry)+'} list-sources] "\\n"]]\n')
  self.assertEqual(r.returncode,0,r.stderr);lines=r.stdout.splitlines();self.assertTrue(json.loads(lines[0])['passed']);self.assertEqual(int(lines[1]),len(ENTRY.check_sources()['sources'])+1)
 def test_all_actual_M003_Tcl_python_calls_use_clean_wrapper(self):
  for name in ['create_vcu118_board.tcl','build_vcu118_board.tcl','m003_joint_checks.tcl','m003_physical.tcl','m003_recover_synthesis.tcl','m002_diagnostic_common.tcl']:
   text=(HW/'vivado/scripts'/name).read_text();self.assertNotIn('exec /usr/bin/python3',text);self.assertIn('m003_python',text)
  helper=(HW/'vivado/scripts/m003_system_python.tcl').read_text();self.assertIn('/usr/bin/env -u PYTHONHOME -u PYTHONPATH /usr/bin/python3 {*}$args',helper)
