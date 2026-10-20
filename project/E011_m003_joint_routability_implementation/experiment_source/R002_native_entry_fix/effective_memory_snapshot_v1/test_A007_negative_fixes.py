"""Affected cases for A007's independently found candidate false accepts."""
import copy,json,unittest
from test_effective_memory_candidate import E,BASE_S,SPEC
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
if __name__=='__main__':unittest.main(verbosity=2)
