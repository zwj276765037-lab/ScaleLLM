"""A007 additional adversarial cases only; no submitted suite rerun, no EDA."""
import pathlib,sys,json,copy,hashlib,datetime
ROOT=pathlib.Path(__file__).resolve().parents[3];OWN=pathlib.Path(__file__).resolve().parent
BASE=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/effective_memory_snapshot_v1'
expected='394a95a43c540ebb218cd2a47ee1cc99d42dfda12416c34e82fc10acf9891cbe'
assert hashlib.sha256((BASE/'m003_joint_evidence.py.proposed').read_bytes()).hexdigest()==expected
sys.path.insert(0,str(BASE))
from test_effective_memory_candidate import E,BASE_S,SPEC
cases=[]
def add_state(z,owner):
 f=json.loads(z['D_source_facts']);f.append(dict(raw_name=owner+'/C',**{'class':'pin'},owner_names=owner,owner_refs='FDCE',owner_Q_pins=owner+'/Q',owner_Q_in_full_fanin='1'))
 z['D_source_facts']=json.dumps(f);z['D_startpoints']+=' '+owner+'/C';z['D_full_fanin']+=' '+owner+'/C '+owner+'/Q';z['D_startpoint_cells']+=' '+owner;z['D_startpoint_cell_refs']+=' FDCE'
addr={(int(x['slice']),int(x['bit'])):x for x in BASE_S['cells'] if x['role']=='address'}
orig={x['NAME'] for x in BASE_S['cells'] if x['role']=='core_address'}
for label,owner,want in [('common_control_positive','inst/u_core/maintenance_soft_clear_pulse_r_reg',True),('old_core_address_replica_forbidden','core_addr/meta_read_addr_r_reg[0]_rep',False)]:
 z=copy.deepcopy(addr[(0,0)]);add_state(z,owner);errors=[]
 E.validate_address_state(z,{a['NAME']+'/Q' for (i,b),a in addr.items() if i==0},{a['NAME']+'/Q' for (i,b),a in addr.items() if i==1},orig,lambda ok,msg:errors.append(msg) if not ok else None)
 cases.append(dict(case=label,expected_accepted=want,actual_accepted=not errors,errors=errors,added_actual_source=owner))
# Use isolated effective-memory validator to avoid rerunning unrelated old tests.
def memory_case(label,s,expected,mutation):
 errors=[];mem={i:[x for x in s['cells'] if x['role']=='memory' and int(x['slice'])==i] for i in (0,1)};sources={k:set(E.words(v)) for k,v in s['control_sources'].items()}
 E.validate_effective_memories(s,mem,addr,orig,sources,lambda ok,msg:errors.append(msg) if not ok else None)
 cases.append(dict(case=label,expected_accepted=expected,actual_accepted=not errors,errors=errors,mutation=mutation))
s=copy.deepcopy(BASE_S);r=next(x for x in s['memory_pins'] if x['cell']=='slice0/uram/0' and x['pin']=='CLK');r.update(drivers='clock_buffer/O',driver_cells='clock_buffer',driver_refs='BUFGCE')
memory_case('clock_leaf_plus_primary_evidence',s,False,'One valid leaf driver added while existing primary_ports=clk/directions=IN retained')
s=copy.deepcopy(BASE_S);cs={x['NAME']:x for x in s['uram_configs']};a,b=cs['slice0/uram/1'],cs['slice0/uram/20']
keys=['SELF_ADDR_'+p for p in ('A','B')]+['MEM.PORT'+p+'.ADDRESS_'+edge for p in ('A','B') for edge in ('BEGIN','END')]
for k in keys:a[k],b[k]=b[k],a[k]
memory_case('duplicate_decode_within_chain_global_bins_preserved',s,False,'Swapped complete SELF_ADDR A/B and spans of slice0/uram/1(value1) and /20(value0); global 0..19 twice unchanged, chains now contain duplicate0 and duplicate1 respectively')
assert hashlib.sha256((BASE/'m003_joint_evidence.py.proposed').read_bytes()).hexdigest()==expected
out={'schema':'A007_effective_memory_v1_additional_negative_probe_v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_qualifier_sha256':expected,'submitted_tests_rerun':False,'cases':cases,'expectation_mismatches':sum(x['expected_accepted']!=x['actual_accepted'] for x in cases),'scope':'CPU synthetic adversarial snapshot checks only; no actual native defect or G4 verdict.'}
p=OWN/'effective_memory_v1_independent_negative_probe.json';assert not p.exists();p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,indent=2));print('OUTPUT',p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
