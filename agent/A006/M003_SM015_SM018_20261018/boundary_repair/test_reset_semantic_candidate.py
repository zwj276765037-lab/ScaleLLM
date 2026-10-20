"""Offline proposed validator checks; never a replacement for current native run."""
from pathlib import Path
import copy,importlib.util,importlib.machinery,json,sys,unittest
R=Path(__file__).resolve().parents[4];W=Path(__file__).resolve().parent;S=R/'project/hardware/vivado/scripts';sys.path.insert(0,str(S));from m003_snapshot_decode import decode
loader=importlib.machinery.SourceFileLoader('reset_candidate',str(W/'m003_joint_evidence.reset_semantics.py.proposed'));sp=importlib.util.spec_from_loader(loader.name,loader);E=importlib.util.module_from_spec(sp);loader.exec_module(E)
RAW=json.loads((R/'project/hardware/vivado/reports/m003_E011_R002_AT025_boundary_sources_postreport_recovery/m003_native_synth.json').read_text());BASE=decode(RAW);SPEC=json.loads((R/'project/hardware/vivado/constraints/m003_joint_locality_spec.json').read_text());PROVENANCE=[json.loads(l) for l in (R/'project/hardware/vivado/reports/m003_E011_R002_AT026_fresh_core_reset_provenance/reset_provenance.jsonl').read_text().splitlines()];PREFIX='scalellm_vcu118_f05_bd_i/core/'
def aligned_records():
 rows=copy.deepcopy(PROVENANCE);root=next(r for r in rows if r['kind']=='root');gid=root['group'];rootnets=E.words(BASE['control_sources']['reset']);driver=next(E.words(p['drivers'])[0] for p in BASE['helper_pins'] if p['pin']=='I0' and p['cell'].endswith('address_r[16]_i_2'))
 for row in rows:
  for field in ['cell','actual_pin','CLR_pin','output_pin']:
   if row.get(field,'').startswith('inst/'):row[field]=PREFIX+row[field]
  if row['kind']=='group':
   if row['id']==gid:row.update(nets=' '.join(rootnets),actual_segment_count=str(len(rootnets)),direct_net=rootnets[0],leaf_drivers=driver,primary_ports='',source_directions='OUT')
   else:
    row['nets']=' '.join(PREFIX+n for n in E.words(row['nets']));row['direct_net']=PREFIX+row['direct_net'];row['leaf_drivers']=' '.join(PREFIX+n for n in E.words(row['leaf_drivers']))
  if row['kind']=='root':row.clear();row.update(kind='root',group=gid,anchor=PREFIX+'inst/u_core/u_compute/u_attention/core_rst_n',actual_source=driver,direction='OUT')
 return rows
def sample():
 s=copy.deepcopy(BASE);s['reset_provenance']=aligned_records();return s

def check(s):
 errors=[];originals=[c for c in s['cells'] if c['role']=='core_address'];helpers=[c for c in s['cells'] if c['role']=='address'];sources={k:set(E.words(v)) for k,v in s['control_sources'].items()};E.validate_native_reset(s,originals,helpers,sources,lambda ok,msg:errors.append(msg) if not ok else None);return errors
class SemanticReset(unittest.TestCase):
 def test_actual51_projection_same_function_and_empty_cell_preserved(self):
  s=sample();self.assertEqual(check(s),[]);self.assertEqual({r['IS_CLR_INVERTED'] for r in s['reset_provenance'] if r['kind']=='endpoint'},{''})
 def test_entire_original_snapshot_34_alias_errors_replaced_by_actual_semantic_proof(self):
  self.assertFalse(E.validate(BASE,SPEC,fixture=False)['passed'])
  result=E.validate(sample(),SPEC,fixture=False);self.assertTrue(result['passed'],result['errors'])
 def test_missing_wrong_polarity_known_conflict_and_INIT_reject(self):
  for mode in ['missing_cell','missing_pin','bad_pin','invert_pin','bad_cell','cell_conflict','wrong_init','wrong_ref']:
   with self.subTest(mode=mode):
    s=sample();ep=next(r for r in s['reset_provenance'] if r['kind']=='endpoint')
    if mode=='missing_cell':ep.pop('IS_CLR_INVERTED')
    if mode=='missing_pin':ep.pop('pin_IS_INVERTED')
    if mode=='bad_pin':ep['pin_IS_INVERTED']='unknown'
    if mode=='invert_pin':ep['pin_IS_INVERTED']='1'
    if mode=='bad_cell':ep['IS_CLR_INVERTED']='unknown'
    if mode=='cell_conflict':ep['IS_CLR_INVERTED']='1'
    if mode=='wrong_init':ep['INIT']="1'b1"
    if mode=='wrong_ref':ep['REF_NAME']='FDRE'
    self.assertTrue(check(s))
 def test_wrong_reset_function_constant_source_and_unknown_primitive_reject(self):
  for ref,init in [('LUT1',"2'h2"),('LUT1',"2'h0"),('LUT1',"2'h3"),('MUXF7',"2'h1")]:
   s=sample();next(r for r in s['reset_provenance'] if r['kind']=='node').update(REF_NAME=ref,INIT=init);self.assertTrue(check(s))
 def test_missing_duplicate_foreign_and_vector_truncation_reject(self):
  for mode in ['missing','duplicate_endpoint','wrong_anchor','wrong_root_nets','short_count','duplicate_NAME','empty_source','wrong_direction','extra_group','missing_input','wrong_input','cycle']:
   with self.subTest(mode=mode):
    s=sample();rows=s['reset_provenance'];ep=next(r for r in rows if r['kind']=='endpoint');group=next(r for r in rows if r['kind']=='group');root=next(r for r in rows if r['kind']=='root');ip=next(r for r in rows if r['kind']=='input');node=next(r for r in rows if r['kind']=='node')
    if mode=='missing':s.pop('reset_provenance')
    if mode=='duplicate_endpoint':rows.append(copy.deepcopy(ep));next(r for r in rows if r['kind']=='complete')['endpoints']='52'
    if mode=='wrong_anchor':root['anchor']='foreign'
    if mode=='wrong_root_nets':group['nets']='foreign';group['direct_net']='foreign';group['actual_segment_count']='1'
    if mode=='short_count':group['actual_segment_count']='1'
    if mode=='duplicate_NAME':group['nets']+=' '+E.words(group['nets'])[0]
    if mode=='empty_source':group['leaf_drivers']='{}';root['actual_source']=''
    if mode=='wrong_direction':group['source_directions']='IN'
    if mode=='extra_group':extra=copy.deepcopy(group);extra['id']='FOREIGN';rows.append(extra)
    if mode=='missing_input':rows.remove(ip)
    if mode=='wrong_input':ip['direction']='OUT'
    if mode=='cycle':ip['group']=node['output_group']
    self.assertTrue(check(s))
if __name__=='__main__':unittest.main(verbosity=2)
