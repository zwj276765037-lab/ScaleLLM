from pathlib import Path
import copy,importlib.machinery,importlib.util,json,sys,types,unittest,subprocess
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[4];HW=ROOT/'project/hardware'
sys.path.insert(0,str(HW/'vivado/scripts'))
def candidate(name):
 p=BASE/(name+'.py.proposed');loader=importlib.machinery.SourceFileLoader(name+'_candidate',str(p));spec=importlib.util.spec_from_loader(loader.name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m);return m
E=candidate('m003_joint_evidence');REC=candidate('m003_synth_recovery')
Q=types.ModuleType('candidate_qualification_fixture');Q.__file__=str(HW/'tests/test_m003_joint_qualification.py')
exec(compile((BASE/'test_m003_joint_qualification.py.proposed').read_text(),Q.__file__,'exec'),Q.__dict__);Q.E=E
BASE_S=Q.fixture();SPEC=Q.SPEC
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
class NativeCollectorCPU(unittest.TestCase):
 def run_tcl(self,body):
  source=(BASE/'m003_joint_checks.tcl.proposed').read_text();helpers='namespace eval m003 {}\n'+source[source.index('proc m003::jq'):source.index('proc m003::cell_row')]
  code='if {[catch {\n'+helpers+'\n'+body+'\n} message options]} {puts stderr [dict get $options -errorinfo];exit 1}\n'
  p=subprocess.run(['tclsh'],input=code,text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr);return p.stdout.strip()
 def test_empty_raw_address_does_not_query_property(self):
  self.assertEqual(self.run_tcl('proc get_property {args} {error {must not query empty}}\nputs [llength [m003::memory_startpoint_names {ADDR_A[22]} {}]]'),'0')
 def test_nonempty_native_error_propagates(self):
  self.assertEqual(self.run_tcl('proc get_property {args} {return -code error -errorcode {NATIVE FAIL} {sentinel}}\nset code [catch {m003::memory_startpoint_names {ADDR_A[0]} bad} msg opts]\nputs "$code|$msg|[dict get $opts -errorcode]"'),'1|sentinel|NATIVE FAIL')
 def test_actual_proposed_Tcl_is_complete(self):
  self.assertEqual(self.run_tcl('set h [open {'+str(BASE/'m003_joint_checks.tcl.proposed')+'}];set text [read $h];close $h;puts [info complete $text]'),'1')
if __name__=='__main__':
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Q.Qualification),unittest.defaultTestLoader.loadTestsFromTestCase(EffectiveProfile),unittest.defaultTestLoader.loadTestsFromTestCase(NativeCollectorCPU)])
 result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
