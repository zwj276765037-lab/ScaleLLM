#!/usr/bin/env python3
"""Fail-closed validation of native M003 role/pin/pblock evidence; fixtures are explicit."""
from __future__ import annotations
import argparse,collections,datetime,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
G2_SHA='4424c426859b6b1e64be2f52a008ff6c03e1a6854f71570970cbba4941fff709'
DESIGN_SHA='6d74e85db325a939c8b1ffbd637de6dbd35e2016188bdd0050d62cc5a2b9706b'
MAP_SHA='75abfae1d81cb75d13a8543a63f4f79ef1c70e25fee08d19d77a2c0f1627ad0f'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def words(v):return [s.strip('{}') for s in str(v).split()]
def yes(v):return str(v).lower() in ('1','true','yes')
def init(v):
 m=re.fullmatch(r"\d+'([hHbB])([0-9a-fA-F]+)",v)
 if not m:raise ValueError('unknown INIT encoding '+v)
 return int(m[2],16 if m[1].lower()=='h' else 2)
def cr(v):return str(v).removeprefix('CLOCKREGION_')
def isff(ref):return ref in ('FDRE','FDCE','FDSE','FDPE')
def lut(ref):return bool(re.fullmatch(r'LUT[1-6](?:_2)?',ref))
def validate(s,spec,*,fixture=False):
 errors=[]
 def require(c,message):
  if not c:errors.append(message)
 meta=s.get('meta',{})
 require(meta.get('kind')==('fixture' if fixture else 'native'),'native/fixture mode mismatch')
 require(meta.get('part')=='xcvu9p-flga2104-2L-e','wrong device identity')
 require(spec.get('G2_sha256')==G2_SHA and spec.get('design_manifest_sha256')==DESIGN_SHA and spec.get('group_map_sha256')==MAP_SHA,'wrong frozen design identity')
 rows=s.get('cells',[]);names=[r.get('NAME') for r in rows]
 require(len(names)==len(set(names)),'duplicate native role/object identity')
 role=collections.defaultdict(list)
 for r in rows:role[r.get('role')].append(r)
 groups={g['id']:g for g in spec['groups']}
 buffers={r.get('group'):r for r in role['buffer']}
 require(len(role['buffer'])==81 and set(buffers)==set(groups),'M2 buffer missing/duplicate/count')
 payload={}
 for r in role['payload']:
  try:k=(r['family'],int(r['bit']))
  except (KeyError,ValueError):errors.append('invalid payload role fields');continue
  require(k not in payload,'duplicate payload bit');payload[k]=r
  require(isff(r.get('REF_NAME')),'unknown payload compatible resource')
 require(set(payload)=={(f,b) for f in ('head','tail') for b in range(6560)},'M2 payload bit coverage/count')
 edges=collections.defaultdict(list)
 for e in s.get('ce_edges',[]):edges[e.get('group')].append(e)
 bit_group={(g['family'],b):g['id'] for g in groups.values() for b in g['bits']}
 placed=meta.get('phase') in ('place','physopt','route')
 for gid,g in groups.items():
  r=buffers.get(gid,{})
  require(r.get('REF_NAME')=='LUT1' and yes(r.get('DONT_TOUCH')),'M2 protected LUT1 lost: '+gid)
  try:require(init(r.get('INIT',''))==2,'M2 INIT mismatch: '+gid)
  except ValueError as e:errors.append(str(e))
  expected={payload.get((g['family'],b),{}).get('NAME') for b in g['bits']}
  actual=[e.get('load') for e in edges[gid]]
  require(None not in expected and set(actual)==expected and len(actual)==len(expected),'M2 CE pin partition/duplicate mismatch: '+gid)
  require(all(e.get('pin')=='CE' and e.get('source')==r.get('NAME') for e in edges[gid]),'M2 non-CE or wrong driver: '+gid)
  pb='m003_parent_'+g['clock_region']
  for member in [r]+[payload.get((g['family'],b),{}) for b in g['bits']]:
   require(pb in words(member.get('PBLOCKS','')),'M2 region binding absent: '+str(member.get('NAME')))
   if placed:require(cr(member.get('clock_region'))==g['clock_region'] and member.get('SLR')==g['SLR'],'M2 placed locality mismatch: '+str(member.get('NAME')))
 require(set(edges)<=set(groups),'unknown CE group')
 masters=collections.defaultdict(set)
 master_groups=[]
 for e in s.get('master_inputs',[]):
  master_groups.append(e.get('group'))
  g=groups.get(e.get('group'))
  require(g is not None and g.get('family')==e.get('family'),'unknown master/group identity')
  masters[e.get('family')].add(e.get('driver'))
  if g and 'load_pins' in e:
   expected={buffers[z]['NAME']+'/I0' for z,v in groups.items() if v['family']==g['family'] and z in buffers}
   require(set(words(e['load_pins']))==expected,'master has missing/extra/unbuffered load')
 require(len(s.get('master_inputs',[]))==81 and len(masters['head'])==len(masters['tail'])==1 and masters['head']!=masters['tail'],'master source partition mismatch')
 require(len(master_groups)==len(set(master_groups)) and set(master_groups)==set(groups),'master group exact coverage missing/duplicate')
 original_addr=role['core_address']
 require(len(original_addr)==17 and {str(r.get('bit')) for r in original_addr}=={str(b) for b in range(17)} and all(isff(r.get('REF_NAME')) for r in original_addr),'original core address17 state missing')
 original_clr={tuple(sorted(words(r.get('CLR_nets','')))) for r in original_addr}
 require(len(original_clr)==1 and bool(next(iter(original_clr),())),'original core address reset unresolved')
 addr={};helper_rows=role['address']+role['address_logic']
 for r in role['address']:
  try:k=(int(r['slice']),int(r['bit']))
  except (KeyError,ValueError):errors.append('invalid address identity');continue
  require(k not in addr,'duplicate address bit');addr[k]=r
  require(isff(r.get('REF_NAME')) and yes(r.get('DONT_TOUCH')),'address FF/protection missing')
 require(set(addr)=={(i,b) for i in (0,1) for b in range(17)},'address34 missing/duplicate')
 helper_luts=sum(lut(r.get('REF_NAME','')) for r in helper_rows)
 helper_ff=sum(isff(r.get('REF_NAME')) for r in helper_rows)
 helper_carry=sum(r.get('REF_NAME')=='CARRY8' for r in helper_rows)
 require(helper_ff==34 and helper_luts<=96 and helper_carry<=8,'exact added helper cone resource budget exceeded')
 controls=[]
 for i in (0,1):
  rows_i=[r for r in helper_rows if str(r.get('slice'))==str(i)]
  for suffix,ref,value in [('u_local_ce','LUT3',254),('u_local_increment','LUT2',2)]:
   selected=[r for r in rows_i if r.get('NAME','').endswith('/'+suffix)]
   require(len(selected)==1,'local control missing/merged '+str(i)+'/'+suffix)
   if selected:
    z=selected[0];controls.append(z)
    require(z.get('REF_NAME')==ref and yes(z.get('DONT_TOUCH')),'local control primitive/protection changed')
    try:require(init(z.get('INIT',''))==value,'local control INIT mismatch')
    except ValueError as e:errors.append(str(e))
  pool=spec['meta_pools'][i];allowed=set(pool['CLB_sites']);allowed_cr=set(pool['CLB_clock_regions'])
  own_q={addr[(i,b)]['NAME']+'/Q' for b in range(17) if (i,b) in addr}
  other_q={z['NAME']+'/Q' for (j,b),z in addr.items() if j!=i}
  for z in rows_i:
   require('m003_meta_slice'+str(i)+'_address' in words(z.get('PBLOCKS','')),'address cone pblock absent')
   if placed:require(z.get('LOC') in allowed and cr(z.get('clock_region')) in allowed_cr and z.get('SLR')=='SLR1','address cone outside compatible pool')
   if z.get('role')=='address':
    own_controls=[c for c in controls if str(c.get('slice'))==str(i) and c.get('NAME','').endswith('/u_local_ce')]
    require(len(own_controls)==1 and set(words(z.get('CE_drivers','')))=={own_controls[0]['NAME']+'/O'},'address CE does not use own protected local CE')
    fanin=set(words(z.get('D_startpoints','')))
    require(bool(fanin&own_q) and not(fanin&other_q) and not any('meta_read_addr_r_reg[' in n for n in fanin),'address D does not use own state or takes other/core address')
    require(bool(words(z.get('C_nets',''))) and bool(words(z.get('CLR_nets',''))) and bool(words(z.get('CE_nets',''))),'address clock/reset/CE missing')
    require(tuple(sorted(words(z.get('CLR_nets','')))) in original_clr,'helper asynchronous reset differs from original core address')
 memories={i:[r for r in role['memory'] if str(r.get('slice'))==str(i)] for i in (0,1)}
 for i,ms in memories.items():
  require(len(ms)==40 and all(r.get('REF_NAME')=='URAM288' for r in ms),'URAM40 slice mapping/resource mismatch')
  allowed=set(spec['meta_pools'][i]['URAM_sites'])
  for z in ms:
   require('m003_meta_slice'+str(i)+'_uram' in words(z.get('PBLOCKS','')),'URAM pool binding absent')
   if placed:require(z.get('LOC') in allowed and z.get('SLR')=='SLR1','URAM outside fixed pool/SLR')
  if placed:
   regions={cr(z.get('clock_region')) for z in ms}
   regions|={cr(z.get('clock_region')) for z in helper_rows if str(z.get('slice'))==str(i)}
   coords=[re.fullmatch(r'X(\d+)Y(\d+)',v) for v in regions]
   require(all(c and c[1]=='4' for c in coords),'meta horizontal CR mismatch')
   ys=[int(c[2]) for c in coords if c]
   require(bool(ys) and max(ys)-min(ys)<=2,'meta CR span exceeded')
 q_to_slice={z['NAME']+'/Q':i for (i,b),z in addr.items()}
 read_roots=collections.defaultdict(set);reader_bits=collections.defaultdict(set)
 for p in s.get('memory_pins',[]):
  try:i=int(p['slice'])
  except (KeyError,ValueError):errors.append('memory pin slice unknown');continue
  require(any(r.get('NAME')==p.get('cell') for r in memories.get(i,[])),'memory pin unknown object')
  direct=words(p.get('drivers',''));points=set(direct)|set(words(p.get('startpoints','')))
  if str(p.get('pin','')).startswith('ADDR'):
   require(not any('meta_read_addr_r_reg[' in n for n in points),'old core address still drives memory')
   for n in points:
    if n in q_to_slice:
     require(q_to_slice[n]==i,'cross-slice address source')
     require(str(p['pin']).startswith('ADDR_A['),'read-address port changed from measured old ADDR_A')
     read_roots[i].add(p['cell']);reader_bits[i].add(n)
 for i in (0,1):
  require(bool(read_roots[i]) and len(reader_bits[i])==17,'address replica unloaded/missing bit or not connected to own read roots')
 pb_by_name={p.get('NAME'):p for p in s.get('pblocks',[])}
 expected_pb={'m003_parent_'+r['clock_region'] for r in spec['regions']}
 expected_pb|={'m003_meta_slice'+str(i)+'_'+k for i in (0,1) for k in ('uram','address')}
 expected_pb.add('m002_exact_hotspot_SLR2')
 require(set(pb_by_name)==expected_pb,'overlay omitted or pblock name/count/identity wrong')
 for name,p in pb_by_name.items():
  require(all(not yes(p.get(k)) and str(p.get(k)) not in ('NOT_SUPPORTED','None','') for k in ('IS_SOFT','EXCLUDE_PLACEMENT','CONTAIN_ROUTING')),'hard/nonexclusive/noncontained policy changed: '+str(name))
 for i in (0,1):
  for suffix,key in [('uram','URAM_sites'),('address','CLB_sites')]:
   p=pb_by_name.get('m003_meta_slice'+str(i)+'_'+suffix,{})
   require(set(words(p.get('actual_sites','')))==set(spec['meta_pools'][i][key]),'meta exact native resource set mismatch')
 for row in spec['regions']:
  p=pb_by_name.get('m003_parent_'+row['clock_region'],{})
  target=words(s.get('target_sites',{}).get('m003_parent_'+row['clock_region'],''))
  require(len(target)==row['native_CLB_site_count'] and len(target)==len(set(target)),'M2 target native CR resource identity/count missing')
  require(set(words(p.get('actual_sites','')))==set(target),'M2 exact target CR resource set mismatch')
 target_c01=set(words(s.get('target_sites',{}).get('m002_exact_hotspot_SLR2','')))
 require(bool(target_c01) and set(words(pb_by_name.get('m002_exact_hotspot_SLR2',{}).get('actual_sites','')))==target_c01,'C01 exact SLR2 resource set mismatch')
 c01=role['c01'];by_name={r['NAME']:r for r in c01}
 require(bool(c01),'C01 missing')
 for name in spec['C01_protected_names']:require(name in by_name and yes(by_name[name].get('DONT_TOUCH')),'C01 original protection lost: '+name)
 require(sum(r.get('REF_NAME')=='RAMB36E2' for r in c01)==6 and sum(r.get('REF_NAME')=='DSP48E2' for r in c01)==2,'C01 hardblock role counts changed/unresolved parent')
 for r in c01:
  require('m002_exact_hotspot_SLR2' in words(r.get('PBLOCKS','')),'C01 hard-SLR2 binding missing')
  if placed:require(r.get('SLR')=='SLR2','C01 outside SLR2')
 for r in rows:
  for k in ('IS_LOC_FIXED','IS_BEL_FIXED'):
   require(str(r.get(k)) not in ('','None','NOT_SUPPORTED'),'unknown resource fixed policy')
  require(str(r.get('MACRO_NAME','')) in ('','NOT_SUPPORTED'),'native macro requires explicit compatibility qualification')
 boundary=collections.defaultdict(list)
 for r in s.get('boundaries',[]):boundary[r.get('tag')].append(r)
 for tag,count,ref,width in [('input',48,'LUT6',256),('gate',16,'LUT1',384),('down',16,'LUT1',512)]:
  require(len(boundary[tag])==count,'original 80-boundary role count changed: '+tag)
  for r in boundary[tag]:
   require(r.get('REF_NAME')==ref and yes(r.get('DONT_TOUCH')),'original 80-boundary primitive/protection lost')
   require(int(r.get('load_count',-1))==width and set(words(r.get('load_terminals','')))=={'CE'},'original boundary CE graph changed')
 # Enforce selected S/L/R/clock wiring from native boundary aliases and
 # primitive ports. Simulation is separate evidence for collision/old-value data.
 sources={k:set(words(v)) for k,v in s.get('control_sources',{}).items()}
 require(set(sources)=={'S','L','R','clock','reset'} and all(sources.values()),'native S/L/R/clock/reset boundary unresolved')
 helper_pins=s.get('helper_pins',[])
 for i in (0,1):
  own=[r for r in helper_rows if str(r.get('slice'))==str(i)]
  for suffix,mapping in [('u_local_ce',{'I0':'S','I1':'L','I2':'R'}),('u_local_increment',{'I0':'R','I1':'S'})]:
   objs=[r for r in own if r.get('NAME','').endswith('/'+suffix)]
   if len(objs)!=1:continue
   for terminal,signal in mapping.items():
    ps=[p for p in helper_pins if p.get('cell')==objs[0]['NAME'] and p.get('pin')==terminal]
    require(len(ps)==1 and bool(set(words(ps[0].get('nets','')))&sources.get(signal,set())),'local control S/L/R pin source mismatch')
  for z in own:
   if z.get('role')=='address':require(bool(set(words(z.get('C_nets','')))&sources.get('clock',set())),'address clock differs from original metadata clock')
 memory_identity={z['NAME']:i for i,ms in memories.items() for z in ms}
 for name,i in memory_identity.items():
  for terminal,constant in [('RDB_WR_A','GND'),('RDB_WR_B','VCC')]:
   ps=[p for p in s.get('memory_pins',[]) if p.get('cell')==name and p.get('pin')==terminal]
   require(len(ps)==1 and words(ps[0].get('driver_refs',''))==[constant],'URAM native read-A/write-B configuration unresolved')
 for p in s.get('memory_pins',[]):
  if str(p.get('pin','')).startswith('CAS_IN'):
   for driver in words(p.get('drivers','')):
    other=memory_identity.get(driver.rsplit('/',1)[0])
    require(other is None or str(other)==str(p.get('slice')),'URAM cascade crosses selected slice pool')
 require(len(s.get('uram_configs',[]))==80 and {r.get('NAME') for r in s.get('uram_configs',[])}==set(memory_identity),'URAM native configuration inventory incomplete')
 # Exact new helper resources, and module/global observations, are separate units.
 return dict(passed=not errors,errors=errors,phase=meta.get('phase'),fixture=fixture,exact_new_M2_LUT1=len(role['buffer']),exact_new_address_FF=helper_ff,exact_helper_LUT=helper_luts,exact_helper_CARRY8=helper_carry,protected_added_LUT=len(role['buffer'])+len(controls),URAM_per_slice={str(i):len(m) for i,m in memories.items()},actual_address_root_counts={str(i):len(v) for i,v in read_roots.items()},limits_not_timing_proof=True,stage_note='Exact helper/M2 resources plus native connectivity; same-stage total module/global resource deltas are checked separately against qualified synthesis reports. Old failed-route net differences cannot prove synthesis budgets.')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixture',action='store_true');a=p.parse_args()
 spec=json.loads(a.spec.read_text());snapshot=json.loads(a.snapshot.read_text())
 result=validate(snapshot,spec,fixture=a.fixture)
 if snapshot.get('meta',{}).get('spec_sha256')!=sha(a.spec):result['errors'].append('source/spec identity mismatch');result['passed']=False
 if not a.fixture:
  from m003_entry import check_sources,MANIFEST
  check_sources()
  if snapshot.get('meta',{}).get('source_manifest_sha256')!=sha(MANIFEST):result['errors'].append('native source manifest binding changed');result['passed']=False
  for e in spec['source_RTL']:
   if not Path(e['path']).is_file() or sha(e['path'])!=e['sha256']:result['errors'].append('selected RTL source identity changed');result['passed']=False
  if sha(ROOT/'mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md')!=G2_SHA:result['errors'].append('G2 source binding changed');result['passed']=False
 result.update(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),snapshot_sha256=sha(a.snapshot),spec_sha256=sha(a.spec),execution='completed',verdict='FIXTURE_CHECKS_ONLY' if a.fixture else 'NATIVE_STRUCTURE_ONLY_NOT_TIMING_OR_OVERALL_G4')
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 return 0 if result['passed'] else 1
if __name__=='__main__':sys.exit(main())
