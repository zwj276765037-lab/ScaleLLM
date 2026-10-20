"""CPU replay of CLOSED native source facts; not a new native/G4 pass."""
from pathlib import Path
import importlib.util,importlib.machinery,json,unittest,sys,copy
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[4]
sys.path.insert(0,str(BASE))
from test_effective_memory_candidate import E,BASE_S
REPORT=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT019_fresh_core_uram_address_attribution'
HELPER=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT020_fresh_core_state_source_semantics/helper_D_sources.jsonl'
def rows(path):return [json.loads(x) for x in path.read_text().splitlines()]
def conv(x):return ' '.join(map(str,x))
class ClosedNativeAdaptation(unittest.TestCase):
 def test_closed34_real_helper_D_facts(self):
  rs=rows(HELPER);self.assertEqual(len(rs),34)
  orig={f'inst/u_core/u_compute/u_attention/meta_read_addr_r_reg[{b}]' for b in range(17)}
  for r in rs:
   z=dict(NAME=r['cell'],D_startpoints=conv(r['raw_startpoints']),D_full_fanin=conv(r['raw_full_fanin']),D_startpoint_cells=conv(r['raw_startpoint_only_cells']),D_startpoint_cell_refs=conv(r['raw_startpoint_only_cell_refs']),D_source_facts=json.dumps([{k:conv(v) if isinstance(v,list) else v for k,v in f.items()} for f in r['actual_source_owner_facts']]))
   own={x['cell']+'/Q' for x in rs if x['slice']==r['slice']};other={x['cell']+'/Q' for x in rs if x['slice']!=r['slice']};errors=[]
   E.validate_address_state(z,own,other,orig,lambda ok,msg:errors.append(msg) if not ok else None);self.assertEqual(errors,[],(r['cell'],errors))
 def test_closed80configs7360address160mode_with_explicit_fixture_auxiliary(self):
  # Measured address/config/mode rows are replayed unchanged as strings.
  # Auxiliary/enable/clock rows remain explicit fixture data and certify no
  # native CLK/EN/auxiliary result. AT020 CLK is still running.
  cs=rows(REPORT/'uram_configs.jsonl');ad=rows(REPORT/'uram_address_pins.jsonl');md=rows(REPORT/'uram_mode_pins.jsonl')
  self.assertEqual((len(cs),len(ad),len(md)),(80,7360,160))
  prefix='inst/u_core/u_compute/u_attention';meta=prefix+'/u_meta'
  name=lambda i,k:meta+f'/g_m003_width_slices.g_slice[{i}].meta_mem_reg_uram_{k}'
  address=lambda i,b:meta+f'/g_m003_width_slices.g_slice[{i}].u_addr/address_r_reg[{b}]'
  rename={f'slice{i}/uram/{k}':name(i,k) for i in (0,1) for k in range(40)}
  addr={(i,b):dict(NAME=address(i,b)) for i in (0,1) for b in range(17)}
  memory={i:[dict(NAME=name(i,k)) for k in range(40)] for i in (0,1)}
  fixture=[]
  for p in BASE_S['memory_pins']:
   if p['pin'].startswith(('ADDR','CAS_IN_ADDR')) or p['pin'].startswith('RDB_WR_'):continue
   z=copy.deepcopy(p);z['cell']=rename[z['cell']]
   for key in ('drivers','driver_cells','nets'):
    value=z[key]
    for old in sorted(rename,key=len,reverse=True):
     if value==old or value.startswith(old+'/'):value=rename[old]+value[len(old):];break
    z[key]=value
   fixture.append(z)
  native=[]
  for r in ad+md:
   native.append({**{k:r[k] for k in ('slice','cell','pin')},**{k:conv(r.get(k,[])) for k in ('nets','drivers','driver_cells','driver_refs','startpoints')},'primary_ports':'','primary_port_directions':''})
  snap=dict(memory_pins=fixture+native,uram_configs=[dict(NAME=c['cell'],**{k:v for k,v in c.items() if k!='cell'}) for c in cs])
  errors=[];out=E.validate_effective_memories(snap,memory,addr,{prefix+f'/meta_read_addr_r_reg[{b}]' for b in range(17)},{'clock':{'clk'},'read_enable':{'rd_fire'},'write_enable':{'meta_wr_valid'}},lambda ok,msg:errors.append(msg) if not ok else None)
  self.assertEqual(errors,[],errors[:15]);self.assertEqual(out,{'0':6,'1':6})
if __name__=='__main__':unittest.main(verbosity=2)
