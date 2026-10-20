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
 s=dict(meta=dict(kind='fixture',part='xcvu9p-flga2104-2L-e',phase='opt'),cells=[],ce_edges=[],master_inputs=[],memory_pins=[],pblocks=[],target_sites={},boundaries=[],helper_pins=[],uram_configs=[],control_sources=dict(S='S',L='L',R='R',clock='clk',reset='rst',read_enable='rd_fire',write_enable='meta_wr_valid'))
 for bit in range(17):s['cells'].append(cell('core_addr/meta_read_addr_r_reg['+str(bit)+']','core_address','FDCE',bit=bit,C_nets='clk',CLR_nets='rst'))
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
  for bit in range(17):
   name=p+'/address/'+str(bit);owner=dict(raw_name=name+'/C',**{'class':'pin'},owner_names=name,owner_refs='FDCE',owner_Q_pins=name+'/Q',owner_Q_in_full_fanin='1')
   port=dict(raw_name='rst',**{'class':'port'},owner_names='',owner_refs='',owner_Q_pins='',owner_Q_in_full_fanin='')
   s['cells'].append(cell(name,'address','FDCE',slice=i,bit=bit,DONT_TOUCH='1',PBLOCKS=addresspb,D_startpoints=name+'/C rst',D_full_fanin=name+'/C '+name+'/Q rst',D_startpoint_cells=name,D_startpoint_cell_refs='FDCE',D_source_facts=json.dumps([owner,port]),C_nets='clk',CLR_nets='rst',CE_nets=p+'ce',CE_drivers=p+'/u_local_ce/O'))
  for name,ref,value in [('u_local_ce','LUT3',"8'hfe"),('u_local_increment','LUT2',"4'h2")]:s['cells'].append(cell(p+'/'+name,'address_logic',ref,slice=i,DONT_TOUCH='1',INIT=value,PBLOCKS=addresspb))
  for suffix,mapping in [('u_local_ce',{'I0':'S','I1':'L','I2':'R'}),('u_local_increment',{'I0':'R','I1':'S'})]:
   for pin,net in mapping.items():s['helper_pins'].append(dict(slice=i,cell=p+'/'+suffix,pin=pin,nets=net))
  # Explicit observed-profile graph: six chains per slice, low17 address
  # sources, masked high6, direct/CAS modes, and all431 selected input pins.
  lengths=(8,8,4,8,8,4);starts=(0,8,16,20,28,36);ends={a+n-1 for a,n in zip(starts,lengths)}
  for k in range(40):
   name=p+'/uram/'+str(k);root=max(a for a in starts if a<=k);rootname=p+'/uram/'+str(root)
   kind='FIRST' if k==root else 'LAST' if k in ends else 'MIDDLE'
   s['cells'].append(cell(name,'memory','URAM288',slice=i,PBLOCKS='m003_meta_slice'+str(i)+'_uram'))
   c=dict(NAME=name,slice=i,CASCADE_ORDER_A=kind,CASCADE_ORDER_B=kind,IS_CLK_INVERTED="1'b0")
   for port in ('A','B'):
    for stem in ('IREG_PRE_','REG_CAS_','OREG_','USE_EXT_CE_'):c[stem+port]='FALSE'
    for stem in ('IS_EN_','IS_RDB_WR_','IS_RST_'):c[stem+port+'_INVERTED']="1'b0"
    c['SELF_MASK_'+port]="11'h7E0";c['SELF_ADDR_'+port]="11'h%03X"%(k%20)
    c['MEM.PORT'+port+'.ADDRESS_BEGIN']=str((k%20)*4096);c['MEM.PORT'+port+'.ADDRESS_END']=str((k%20)*4096+4095)
   s['uram_configs'].append(c)
   # This independent terminal list follows the431 pins retained by the
   # original selection expression, rather than calling the validator.
   terminals=['RDB_WR_A','RDB_WR_B','CLK','EN_A','EN_B']
   for port in ('A','B'):
    for prefix,width in [('ADDR',23),('CAS_IN_ADDR',23),('BWE',9),('CAS_IN_BWE',9),('CAS_IN_DIN',72),('CAS_IN_DOUT',72)]:terminals.extend(f'{prefix}_{port}[{b}]' for b in range(width))
    terminals.extend(f'CAS_IN_{signal}_{port}' for signal in ('DBITERR','EN','RDACCESS','RDB_WR','SBITERR'))
   for terminal in terminals:
    z=dict(slice=i,cell=name,pin=terminal,drivers='constant/G',driver_cells='constant',driver_refs='GND',startpoints='',nets='constant_net',primary_ports='',primary_port_directions='')
    if terminal=='CLK':z.update(drivers='',driver_cells='',driver_refs='',nets='clk',primary_ports='clk',primary_port_directions='IN')
    elif terminal in ('RDB_WR_A','RDB_WR_B'):
     if terminal.endswith('_B') or kind!='FIRST':z.update(drivers='constant/P',driver_refs='VCC')
    elif terminal in ('EN_A','EN_B'):z.update(drivers='shared_slice0_control/O',driver_cells='shared_slice0_control',driver_refs='LUT6',nets='rd_fire' if terminal.endswith('_A') else 'meta_wr_valid')
    elif terminal.startswith('CAS_IN_EN_') or terminal.startswith('CAS_IN_RDB_WR_'):
     if kind!='FIRST':
      parent=p+'/uram/'+str(k-1);z.update(drivers=parent+'/'+terminal.replace('CAS_IN_','CAS_OUT_'),driver_cells=parent,driver_refs='URAM288',nets='edge/'+terminal)
    elif terminal.startswith('ADDR_') or terminal.startswith('CAS_IN_ADDR_'):
     port=terminal.split('_')[-1][0];bit=int(terminal.split('[')[1][:-1]);is_direct=terminal.startswith('ADDR_')
     def source_q():return (p+'/address/'+str(bit) if port=='A' else 'core_addr/artifact_index_r_reg['+str(bit)+']'+('_rep' if bit<9 else ''))+'/Q'
     if kind=='FIRST':
      if is_direct and bit<17:
       driver=source_q();z.update(drivers=driver,driver_cells=driver.rsplit('/',1)[0],driver_refs='FDCE',nets='address/'+terminal,startpoints=driver.rsplit('/',1)[0]+'/C')
     elif is_direct:z.update(drivers='',driver_cells='',driver_refs='',nets='',startpoints=name+'/'+terminal)
     else:
      parent=p+'/uram/'+str(k-1);z.update(drivers=parent+'/'+terminal.replace('CAS_IN_','CAS_OUT_'),driver_cells=parent,driver_refs='URAM288',nets='edge/'+terminal,startpoints=source_q().rsplit('/',1)[0]+'/C' if bit<17 else rootname+'/'+terminal.replace('CAS_IN_','CAS_OUT_'))
    s['memory_pins'].append(z)
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
 def test_unloaded_counter(self):self.reject(lambda s:s['memory_pins'].remove(next(p for p in s['memory_pins'] if p['pin']=='ADDR_A[0]')),'unloaded/missing bit')
 def test_reset_semantics_changed(self):self.reject(lambda s:next(r for r in s['cells'] if r['role']=='address').update(CLR_nets='datapath_clear'),'reset differs')
 def test_wrong_control_source(self):self.reject(lambda s:s['helper_pins'][0].update(nets='wrong'),'S/L/R pin source')
 def test_wrong_native_RDW_port(self):self.reject(lambda s:s['memory_pins'][0].update(driver_refs='VCC'),'read-A/write-B')
 def test_native_configuration_missing(self):self.reject(lambda s:s['uram_configs'].pop(),'configuration inventory')
 def test_cross_pool_cascade(self):self.reject(lambda s:next(p for p in s['memory_pins'] if p['cell']=='slice0/uram/1' and p['pin']=='CAS_IN_ADDR_A[0]').update(drivers='slice1/uram/0/CAS_OUT_ADDR_A[0]',driver_cells='slice1/uram/0'),'cascade crosses')
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


# Complete input/profile regression against ordinary imported entry modules.
REC=module('m003_synth_recovery')
BASE_S=fixture()
class EffectiveProfile(unittest.TestCase):
 def reject(self,change,part):
  s=copy.deepcopy(BASE_S);change(s);r=E.validate(s,SPEC,fixture=True)
  self.assertFalse(r['passed']);self.assertTrue(any(part in x for x in r['errors']),(part,r['errors'][:12]))
 def mem(self,s,cell='slice0/uram/0',pin='ADDR_A[0]'):return next(p for p in s['memory_pins'] if p['cell']==cell and p['pin']==pin)
 def cfg(self,s,cell='slice0/uram/0'):return next(c for c in s['uram_configs'] if c['NAME']==cell)
 def helper(self,s):return next(c for c in s['cells'] if c['role']=='address')
 def test_full_observed_profile_and_common_shared_controls(self):
  r=E.validate(BASE_S,SPEC,fixture=True);self.assertTrue(r['passed'],r['errors'][:15]);self.assertEqual(r['actual_address_root_counts'],{'0':6,'1':6});self.assertEqual(len(BASE_S['memory_pins']),80*431)
 def test_single_root_missing_bit_cannot_be_hidden_by_other_roots(self):self.reject(lambda s:self.mem(s).update(drivers='constant/G',driver_cells='constant',driver_refs='GND',startpoints=''),'unloaded/missing bit')
 def test_read_bit_swap_rejected(self):self.reject(lambda s:self.mem(s).update(drivers='slice0/address/1/Q',driver_cells='slice0/address/1'),'unloaded/missing bit')
 def test_root_write_full_scope_not_suffix(self):self.reject(lambda s:self.mem(s,pin='ADDR_B[0]').update(drivers='foreign/artifact_index_r_reg[0]_rep/Q',driver_cells='foreign/artifact_index_r_reg[0]_rep'),'write-address bit')
 def test_root_write_unmeasured_replica_rejected(self):self.reject(lambda s:self.mem(s,pin='ADDR_B[0]').update(drivers='core_addr/artifact_index_r_reg[0]_rep2/Q',driver_cells='core_addr/artifact_index_r_reg[0]_rep2'),'write-address bit')
 def test_root_write_wrong_Q_terminal_rejected(self):self.reject(lambda s:self.mem(s,pin='ADDR_B[0]').update(drivers='core_addr/artifact_index_r_reg[0]_rep/QN'),'write-address bit')
 def test_root_write_bit_swap_rejected(self):self.reject(lambda s:self.mem(s,pin='ADDR_B[0]').update(drivers='core_addr/artifact_index_r_reg[1]_rep/Q',driver_cells='core_addr/artifact_index_r_reg[1]_rep'),'write-address bit')
 def test_high_masked_pin_still_required(self):self.reject(lambda s:s['memory_pins'].remove(self.mem(s,pin='ADDR_A[22]')),'pin coverage')
 def test_high_masked_wrong_constant_rejected(self):self.reject(lambda s:self.mem(s,pin='ADDR_A[22]').update(driver_refs='VCC'),'masked high-address')
 def test_empty_active_address_unknown_rejected(self):self.reject(lambda s:self.mem(s).update(drivers='',driver_cells='',driver_refs='',nets='',startpoints=''),'required input')
 def test_unknown_direct_disconnection_not_generic_acceptance(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/1').update(nets='forged'),'unselected direct address raw')
 def test_missing_auxiliary_pin_rejected(self):self.reject(lambda s:s['memory_pins'].remove(self.mem(s,pin='CAS_IN_DOUT_A[71]')),'pin coverage')
 def test_duplicate_auxiliary_pin_rejected(self):self.reject(lambda s:s['memory_pins'].append(copy.deepcopy(self.mem(s,pin='BWE_A[0]'))),'duplicate native pin')
 def test_source_owner_ref_missing_rejected(self):self.reject(lambda s:self.mem(s).update(driver_cells=''),'owner/reference inventory')
 def test_mask_unknown_rejected(self):self.reject(lambda s:self.cfg(s).pop('SELF_MASK_A'),'mask changed')
 def test_decode_wrong_span_rejected(self):self.reject(lambda s:self.cfg(s).update({'MEM.PORTA.ADDRESS_BEGIN':'1'}),'decode span')
 def test_decode_missing_bank_rejected(self):self.reject(lambda s:self.cfg(s).update(SELF_ADDR_A="11'h001",SELF_ADDR_B="11'h001",**{'MEM.PORTA.ADDRESS_BEGIN':'4096','MEM.PORTA.ADDRESS_END':'8191','MEM.PORTB.ADDRESS_BEGIN':'4096','MEM.PORTB.ADDRESS_END':'8191'}),'decode coverage')
 def test_unknown_cascade_order_rejected(self):self.reject(lambda s:self.cfg(s).update(CASCADE_ORDER_A='NONE'),'unknown/mixed cascade')
 def test_nonzero_inversion_rejected(self):self.reject(lambda s:self.cfg(s).update(IS_EN_A_INVERTED="1'b1"),'unsupported input inversion')
 def test_missing_register_selection_rejected(self):self.reject(lambda s:self.cfg(s).pop('REG_CAS_A'),'register configuration')
 def test_clock_inversion_rejected(self):self.reject(lambda s:self.cfg(s).update(IS_CLK_INVERTED="1'b1"),'clock inversion')
 def test_mode_predecessor_must_match_address(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/2',pin='CAS_IN_RDB_WR_A').update(drivers='slice0/uram/0/CAS_OUT_RDB_WR_A',driver_cells='slice0/uram/0'),'predecessor/bit')
 def test_enable_predecessor_must_match_address(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/2',pin='CAS_IN_EN_A').update(drivers='slice0/uram/0/CAS_OUT_EN_A',driver_cells='slice0/uram/0'),'predecessor/bit')
 def test_cascade_address_bit_swap_rejected(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/1',pin='CAS_IN_ADDR_A[1]').update(drivers='slice0/uram/0/CAS_OUT_ADDR_A[0]'),'predecessor/bit')
 def test_cascade_address_port_swap_rejected(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/1',pin='CAS_IN_ADDR_A[1]').update(drivers='slice0/uram/0/CAS_OUT_ADDR_B[1]'),'predecessor/bit')
 def test_cascade_branch_rejected(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/2',pin='CAS_IN_ADDR_A[0]').update(drivers='slice0/uram/0/CAS_OUT_ADDR_A[0]',driver_cells='slice0/uram/0'),'branches')
 def test_cascade_rootless_cycle_rejected(self):self.reject(lambda s:self.mem(s,cell='slice0/uram/1',pin='CAS_IN_ADDR_A[0]').update(drivers='slice0/uram/2/CAS_OUT_ADDR_A[0]',driver_cells='slice0/uram/2'),'missing/rootless/cyclic')
 def test_cascade_tail_unknown_rejected(self):self.reject(lambda s:self.cfg(s,'slice0/uram/7').update(CASCADE_ORDER_A='MIDDLE',CASCADE_ORDER_B='MIDDLE'),'tail is not LAST')
 def test_root_enable_must_match_actual_boundary(self):self.reject(lambda s:self.mem(s,pin='EN_A').update(nets='unrelated'),'enable boundary')
 def test_clock_multiple_leaf_drivers_rejected(self):self.reject(lambda s:self.mem(s,pin='CLK').update(drivers='clock0/O clock1/O',driver_cells='clock0 clock1',driver_refs='BUFGCE BUFGCE'),'CLK source')
 def test_clock_single_actual_leaf_driver_accepted(self):
  s=copy.deepcopy(BASE_S);self.mem(s,pin='CLK').update(drivers='clock0/O',driver_cells='clock0',driver_refs='BUFGCE',primary_ports='',primary_port_directions='');r=E.validate(s,SPEC,fixture=True);self.assertTrue(r['passed'],r['errors'][:10])
 def test_clock_primary_port_direction_rejected(self):self.reject(lambda s:self.mem(s,pin='CLK').update(primary_port_directions='OUT'),'CLK source')
 def test_clock_unresolved_rejected(self):self.reject(lambda s:self.mem(s,pin='CLK').update(primary_ports='',primary_port_directions=''),'CLK source')
 def test_D_raw_C_is_preserved_not_rewritten(self):
  z=self.helper(BASE_S);self.assertIn('/C',z['D_startpoints']);self.assertNotIn('/Q',z['D_startpoints']);self.assertTrue(E.validate(BASE_S,SPEC,fixture=True)['passed'])
 def test_D_own_Q_membership_false_rejected(self):
  def change(s):
   z=self.helper(s);facts=json.loads(z['D_source_facts']);facts[0]['owner_Q_in_full_fanin']='0';z['D_source_facts']=json.dumps(facts)
  self.reject(change,'owner Q not in full fanin')
 def test_D_forged_owner_rejected(self):
  def change(s):
   z=self.helper(s);facts=json.loads(z['D_source_facts']);facts[0]['owner_names']='unrelated';z['D_source_facts']=json.dumps(facts)
  self.reject(change,'source owner identity')
 def test_D_other_slice_actual_Q_rejected(self):
  def change(s):
   z=self.helper(s);q='slice1/address/0';facts=json.loads(z['D_source_facts']);facts.insert(1,dict(raw_name=q+'/C',**{'class':'pin'},owner_names=q,owner_refs='FDCE',owner_Q_pins=q+'/Q',owner_Q_in_full_fanin='1'));z.update(D_startpoints=z['D_startpoints'].replace(' rst',' '+q+'/C rst'),D_full_fanin=z['D_full_fanin']+' '+q+'/C '+q+'/Q',D_source_facts=json.dumps(facts),D_startpoint_cells=z['D_startpoint_cells']+' '+q,D_startpoint_cell_refs='FDCE FDCE')
  self.reject(change,'other/core address state')
 def test_D_missing_only_cells_rejected(self):self.reject(lambda s:self.helper(s).update(D_startpoint_cells='',D_startpoint_cell_refs=''),'only_cells and actual owners')
 def test_D_missing_raw_startpoints_rejected(self):self.reject(lambda s:self.helper(s).update(D_startpoints=''),'own state raw startpoints')
 def test_declared_entry_only_delta_is_narrow(self):
  p=HW/'vivado/scripts/m003_joint_evidence.py';self.assertIn(p,REC.CHANGED)
  prior={p:{'sha256':'before'}};current={p:{'sha256':'after'},**{p:{'sha256':'added'} for p in REC.ADDITIONS}}
  self.assertEqual(REC.validate_delta(prior,current)['changed'],[str(p)])
  bad=HW/'rtl/forbidden.v';prior[bad]={'sha256':'a'};current[bad]={'sha256':'b'}
  with self.assertRaises(ValueError):REC.validate_delta(prior,current)


class IndependentNegativeFixes(unittest.TestCase):
 def add_state(self,z,owner):
  facts=json.loads(z['D_source_facts']);facts.append(dict(raw_name=owner+'/C',**{'class':'pin'},owner_names=owner,owner_refs='FDCE',owner_Q_pins=owner+'/Q',owner_Q_in_full_fanin='1'));z['D_source_facts']=json.dumps(facts);z['D_startpoints']+=' '+owner+'/C';z['D_full_fanin']+=' '+owner+'/C '+owner+'/Q';z['D_startpoint_cells']+=' '+owner;z['D_startpoint_cell_refs']+=' FDCE'
 def state(self,owner):
  address={(int(x['slice']),int(x['bit'])):x for x in BASE_S['cells'] if x['role']=='address'};orig={x['NAME'] for x in BASE_S['cells'] if x['role']=='core_address'};z=copy.deepcopy(address[(0,0)]);self.add_state(z,owner);errors=[]
  E.validate_address_state(z,{a['NAME']+'/Q' for (i,b),a in address.items() if i==0},{a['NAME']+'/Q' for (i,b),a in address.items() if i==1},orig,lambda ok,msg:errors.append(msg) if not ok else None);return errors
 def memory(self,s):
  errors=[];mem={i:[x for x in s['cells'] if x['role']=='memory' and int(x['slice'])==i] for i in (0,1)};addr={(int(x['slice']),int(x['bit'])):x for x in s['cells'] if x['role']=='address'};orig={x['NAME'] for x in s['cells'] if x['role']=='core_address'};sources={k:set(E.words(v)) for k,v in s['control_sources'].items()};E.validate_effective_memories(s,mem,addr,orig,sources,lambda ok,msg:errors.append(msg) if not ok else None);return errors
 def test_common_control_FF_stays_accepted(self):self.assertEqual(self.state('inst/u_core/maintenance_soft_clear_pulse_r_reg'),[])
 def test_original_core_address_replica_rejected(self):self.assertTrue(any('other/core address state' in x for x in self.state('core_addr/meta_read_addr_r_reg[0]_rep')))
 def test_original_core_unknown_replica_suffix_rejected(self):self.assertTrue(any('other/core address state' in x for x in self.state('core_addr/meta_read_addr_r_reg[0]_replica_2')))
 def test_original_profile_primary_clock_stays_accepted(self):self.assertEqual(self.memory(BASE_S),[])
 def test_leaf_clock_without_primary_stays_accepted(self):
  s=copy.deepcopy(BASE_S);p=next(x for x in s['memory_pins'] if x['cell']=='slice0/uram/0' and x['pin']=='CLK');p.update(drivers='clock_buffer/O',driver_cells='clock_buffer',driver_refs='BUFGCE',primary_ports='',primary_port_directions='');self.assertEqual(self.memory(s),[])
 def test_leaf_plus_primary_clock_rejected(self):
  s=copy.deepcopy(BASE_S);p=next(x for x in s['memory_pins'] if x['cell']=='slice0/uram/0' and x['pin']=='CLK');p.update(drivers='clock_buffer/O',driver_cells='clock_buffer',driver_refs='BUFGCE');self.assertTrue(any('exclusive actual leaf' in x for x in self.memory(s)))
 def test_leaf_plus_orphan_primary_direction_rejected(self):
  s=copy.deepcopy(BASE_S);p=next(x for x in s['memory_pins'] if x['cell']=='slice0/uram/0' and x['pin']=='CLK');p.update(drivers='clock_buffer/O',driver_cells='clock_buffer',driver_refs='BUFGCE',primary_ports='');self.assertTrue(any('exclusive actual leaf' in x for x in self.memory(s)))
 def test_chain_duplicate_decode_global_bins_unchanged_rejected(self):
  s=copy.deepcopy(BASE_S);cs={c['NAME']:c for c in s['uram_configs']};a,b=cs['slice0/uram/1'],cs['slice0/uram/20'];keys=['SELF_ADDR_'+p for p in ('A','B')]+['MEM.PORT'+p+'.ADDRESS_'+edge for p in ('A','B') for edge in ('BEGIN','END')]
  for k in keys:a[k],b[k]=b[k],a[k]
  errors=self.memory(s);self.assertTrue(any('decode within cascade chain' in x for x in errors));self.assertFalse(any('native decode coverage changed' in x for x in errors))
 def test_unique_but_unmeasured_chain_decode_profile_rejected(self):
  s=copy.deepcopy(BASE_S);cs={c['NAME']:c for c in s['uram_configs']};a,b=cs['slice0/uram/1'],cs['slice0/uram/2'];keys=['SELF_ADDR_'+p for p in ('A','B')]+['MEM.PORT'+p+'.ADDRESS_'+edge for p in ('A','B') for edge in ('BEGIN','END')]
  for k in keys:a[k],b[k]=b[k],a[k]
  errors=self.memory(s);self.assertTrue(any('per-chain decode profile' in x for x in errors));self.assertFalse(any('duplicate/missing decode' in x for x in errors))

if __name__ == '__main__':
    unittest.main()
