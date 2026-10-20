import copy,importlib.util,json,sys,unittest
from pathlib import Path
HW=Path(__file__).resolve().parents[1]
def module(name):
 spec=importlib.util.spec_from_file_location(name,HW/'vivado/scripts'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
E=module('m003_joint_evidence');B=module('m003_resource_budget');ENTRY=module('m003_entry')
SPEC=json.loads((HW/'vivado/constraints/m003_joint_locality_spec.json').read_text())
def cell(name,role,ref,**kw):
 return dict(NAME=name,role=role,REF_NAME=ref,IS_LOC_FIXED='0',IS_BEL_FIXED='0',MACRO_NAME='',**kw)
def fixture():
 s=dict(meta=dict(kind='fixture',part='xcvu9p-flga2104-2L-e',phase='opt'),cells=[],ce_edges=[],master_inputs=[],memory_pins=[],pblocks=[],target_sites={},boundaries=[])
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
  for bit in range(17):s['cells'].append(cell(p+'/address/'+str(bit),'address','FDCE',slice=i,bit=bit,DONT_TOUCH='1',PBLOCKS=addresspb,D_startpoints=p+'/address/'+str(bit)+'/Q',C_nets='clk',CLR_nets='rst',CE_nets=p+'ce'))
  for name,ref,value in [('u_local_ce','LUT3',"8'hfe"),('u_local_increment','LUT2',"4'h2")]:s['cells'].append(cell(p+'/'+name,'address_logic',ref,slice=i,DONT_TOUCH='1',INIT=value,PBLOCKS=addresspb))
  for k in range(40):s['cells'].append(cell(p+'/uram/'+str(k),'memory','URAM288',slice=i,PBLOCKS='m003_meta_slice'+str(i)+'_uram'))
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
 def test_cross_slice_source(self):self.reject(lambda s:s['memory_pins'][0].update(drivers='slice1/address/0/Q'),'cross-slice')
 def test_lost_C01_protection(self):self.reject(lambda s:next(r for r in s['cells'] if r['NAME'] in SPEC['C01_protected_names']).update(DONT_TOUCH='0'),'C01 original protection')
 def test_lost80_protection(self):self.reject(lambda s:s['boundaries'][0].update(DONT_TOUCH='0'),'80-boundary')
 def test_macro_requires_qualification(self):self.reject(lambda s:s['cells'][0].update(MACRO_NAME='foreign_macro'),'macro requires')
 def test_fixed_policy_unknown(self):self.reject(lambda s:s['cells'][0].update(IS_LOC_FIXED='NOT_SUPPORTED'),'unknown resource fixed')
 def test_wrong_pool(self):self.reject(lambda s:next(p for p in s['pblocks'] if p['NAME']=='m003_meta_slice0_uram').update(actual_sites='URAM_X0Y0'),'resource set mismatch')
 def test_restored_constraints_missing(self):self.reject(lambda s:s['pblocks'].clear(),'overlay omitted')
 def test_soft_constraint(self):self.reject(lambda s:s['pblocks'][0].update(IS_SOFT='1'),'hard/nonexclusive')
 def test_extra_URAM(self):self.reject(lambda s:s['cells'].append(cell('extra','memory','URAM288',slice=0,PBLOCKS='m003_meta_slice0_uram')),'URAM40')
 def test_registration_policy(self):
  row=dict(NAME='/constraints/m003_joint_locality.xdc',USED_IN_SYNTHESIS='false',USED_IN_IMPLEMENTATION='true',PROCESSING_ORDER='LATE',SCOPED_TO_REF='',SCOPED_TO_CELLS='')
  self.assertTrue(ENTRY.check_registration([row]))
  for key,value in [('USED_IN_SYNTHESIS','true'),('USED_IN_IMPLEMENTATION','false'),('PROCESSING_ORDER','NORMAL'),('SCOPED_TO_REF','wrong')]:
   with self.assertRaises(ValueError):ENTRY.check_registration([{**row,key:value}])
  with self.assertRaises(ValueError):ENTRY.check_registration([])
 def test_source_mismatch(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.json';p.write_text(json.dumps(dict(G2_sha256='wrong',sources=[])))
   with self.assertRaises(ValueError):ENTRY.check_sources(p)
 def test_same_stage_metric_parser(self):
  base=Path(B.BASE);x=json.loads(base.read_text());h=Path(x['reports'][0]['path']);g=Path(x['reports'][1]['path'])
  observed=B.parse_hierarchy(h);expected={k:{m:v[m] for m in B.KEYS} for k,v in x['hierarchical_resources'].items()}
  self.assertEqual(observed,expected);self.assertEqual(B.parse_carry(g),54364)
  self.assertTrue(B.compare(observed,expected,54364,54364)['passed'])
  for scope,key,delta in [('top','total_LUTs',178),('u_meta','FFs_report_including_AND_OR',35),('u_shared_compute','FFs_report_including_AND_OR',1),('top','URAM',1)]:
   bad=copy.deepcopy(observed);bad[scope][key]+=delta;self.assertFalse(B.compare(bad,expected,54364,54364)['passed'])
  self.assertFalse(B.compare(observed,expected,54373,54364)['passed'])
if __name__=='__main__':unittest.main()
