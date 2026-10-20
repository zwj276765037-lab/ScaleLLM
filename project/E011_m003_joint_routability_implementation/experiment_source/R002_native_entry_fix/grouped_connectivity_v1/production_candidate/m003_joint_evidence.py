#!/usr/bin/env python3
"""Fail-closed validation of native M003 role/pin/pblock evidence; fixtures are explicit."""
from __future__ import annotations
import argparse,collections,datetime,hashlib,json,re,sys
from pathlib import Path
from m003_snapshot_decode import decode as decode_grouped_snapshot
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
# These helpers are inserted into the ordinary entry validator, not imported
# as an unmanifested runtime dependency. Raw native facts are never rewritten.
def validate_address_state(z, own_q, other_q, original_names, require):
    raw=words(z.get('D_startpoints',''))
    cone=set(words(z.get('D_full_fanin','')))
    only=words(z.get('D_startpoint_cells',''));onlyrefs=words(z.get('D_startpoint_cell_refs',''))
    try:facts=json.loads(z.get('D_source_facts',''))
    except (ValueError,TypeError):facts=[];require(False,'address D actual source evidence invalid')
    require(isinstance(facts,list),'address D actual source evidence is not rows')
    if not isinstance(facts,list):facts=[]
    require(bool(raw) and len(raw)==len(set(raw)) and [r.get('raw_name') for r in facts]==raw,'address D own state raw startpoints incomplete')
    require(len(only)==len(onlyrefs) and len(only)==len(set(only)),'address D only_cells inventory invalid')
    owners={};proven=set()
    for f in facts:
        name=f.get('raw_name','');kind=f.get('class','').lower()
        require(name in cone,'address D raw source absent from full fanin')
        ns=words(f.get('owner_names',''));refs=words(f.get('owner_refs',''))
        qs=words(f.get('owner_Q_pins',''));members=words(f.get('owner_Q_in_full_fanin',''))
        if kind=='port':
            require(not ns and not refs and not qs and not members,'address D primary-port owner fabricated')
            continue
        require(kind=='pin' and len(ns)==len(refs)==1,'address D source owner unresolved')
        if len(ns)!=1 or len(refs)!=1:continue
        require(name.rsplit('/',1)[0]==ns[0],'address D raw source owner identity changed')
        require(isff(refs[0]),'address D unknown state source primitive')
        require(len(qs)==len(members)==1 and qs==[ns[0]+'/Q'] and members==['1'] and qs[0] in cone,'address D actual owner Q not in full fanin')
        owners[ns[0]]=refs[0]
        if len(qs)==1 and members==['1'] and qs[0] in cone:proven.add(qs[0])
    require(owners==dict(zip(only,onlyrefs)),'address D only_cells and actual owners disagree')
    require(z.get('NAME','')+'/Q' in proven and bool(proven&own_q),'address D does not use own state')
    require(not(proven&other_q) and not(set(owners)&original_names) and not any('meta_read_addr_r_reg[' in owner for owner in owners),'address D takes other/core address state')
    require(not (cone&other_q) and not any(n.rsplit('/',1)[0] in original_names or 'meta_read_addr_r_reg[' in n for n in cone),'address D full fanin takes other/core address state')


def selected_uram_terminals():
    pins={'CLK','EN_A','EN_B','RDB_WR_A','RDB_WR_B'}
    for port in ('A','B'):
        for prefix,width in [('ADDR',23),('CAS_IN_ADDR',23),('BWE',9),('CAS_IN_BWE',9),('CAS_IN_DIN',72),('CAS_IN_DOUT',72)]:
            pins.update(f'{prefix}_{port}[{bit}]' for bit in range(width))
        pins.update(f'CAS_IN_{signal}_{port}' for signal in ('DBITERR','EN','RDACCESS','RDB_WR','SBITERR'))
    return pins


def validate_effective_memories(s, memories, addr, original_names, sources, require):
    identity={z['NAME']:i for i,ms in memories.items() for z in ms}
    configs=s.get('uram_configs',[]);cfg={c.get('NAME'):c for c in configs}
    require(len(configs)==len(cfg)==80 and set(cfg)==set(identity),'URAM native configuration inventory incomplete')
    table={};pin_counts=collections.Counter()
    for p in s.get('memory_pins',[]):
        key=(p.get('cell'),p.get('pin'));pin_counts[p.get('cell')]+=1
        require(key not in table,'URAM duplicate native pin evidence');table[key]=p
        require(p.get('cell') in identity and str(p.get('slice'))==str(identity.get(p.get('cell'))),'URAM pin identity/slice mismatch')
        ds=words(p.get('drivers',''));rs=words(p.get('driver_refs',''));os=words(p.get('driver_cells',''))
        require(len(ds)==len(rs)==len(os) and all(d.rsplit('/',1)[0]==o for d,o in zip(ds,os)),'URAM driver owner/reference inventory incomplete')
        if p.get('pin')!='CLK':
            # The only allowed disconnected inputs are unselected direct ADDR
            # on nonFIRST cells; their exact native shape is checked below.
            empty_direct=str(p.get('pin','')).startswith('ADDR_') and cfg.get(p.get('cell'),{}).get('CASCADE_ORDER_A') in ('MIDDLE','LAST')
            require(empty_direct or (bool(words(p.get('nets',''))) and len(ds)==1),'URAM required input net/driver unresolved')
        if str(p.get('pin','')).startswith('CAS_IN'):
            require(all(o not in identity or identity[o]==identity.get(p.get('cell')) for o in os),'URAM cascade crosses selected slice pool')
    expected=selected_uram_terminals()
    for name in identity:
        require(pin_counts[name]==len(expected) and {pin for cell,pin in table if cell==name}==expected,'URAM per-cell native pin coverage incomplete')
    def row(name,pin):return table.get((name,pin),{})
    def constant(p,ref,label):
        require(words(p.get('driver_refs',''))==[ref] and len(words(p.get('drivers','')))==1 and bool(words(p.get('nets',''))),label)
    def edge(name,pin,parent,out):
        p=row(name,pin)
        require(words(p.get('drivers',''))==[parent+'/'+out] and words(p.get('driver_cells',''))==[parent] and words(p.get('driver_refs',''))==['URAM288'] and bool(words(p.get('nets',''))),'URAM cascade predecessor/bit mismatch: '+name+'/'+pin)
    core_scopes={n.rsplit('/',1)[0] for n in original_names}
    require(len(core_scopes)==1,'URAM original core scope unresolved')
    core_scope=next(iter(core_scopes),'UNRESOLVED')
    pred={};roots=[];decode=collections.defaultdict(collections.Counter)
    for name,i in identity.items():
        c=cfg.get(name,{})
        require(str(c.get('slice'))==str(i),'URAM configuration slice changed')
        kind=c.get('CASCADE_ORDER_A');require(kind in ('FIRST','MIDDLE','LAST') and kind==c.get('CASCADE_ORDER_B'),'URAM unknown/mixed cascade input configuration')
        for port in ('A','B'):
            for stem in ('IREG_PRE_','REG_CAS_','OREG_','USE_EXT_CE_'):
                require(c.get(stem+port)=='FALSE','URAM unsupported selected-input register configuration: '+stem+port)
            for stem in ('IS_RDB_WR_','IS_EN_','IS_RST_'):
                require(c.get(stem+port+'_INVERTED')=="1'b0",'URAM unsupported input inversion: '+stem+port)
            require(c.get('SELF_MASK_'+port)=="11'h7E0",'URAM actual high-address mask changed')
            try:
                value=init(c.get('SELF_ADDR_'+port,''))
                require(int(c.get('MEM.PORT'+port+'.ADDRESS_BEGIN',''))==value*4096 and int(c.get('MEM.PORT'+port+'.ADDRESS_END',''))==value*4096+4095,'URAM native decode span changed')
                if port=='A':decode[i][value]+=1
            except (ValueError,TypeError):require(False,'URAM native decode configuration missing')
        require(c.get('SELF_ADDR_A')==c.get('SELF_ADDR_B') and c.get('IS_CLK_INVERTED')=="1'b0",'URAM A/B decode or clock inversion changed')
        if kind=='FIRST':pred[name]=None;roots.append(name)
        else:
            os=words(row(name,'CAS_IN_ADDR_A[0]').get('driver_cells',''))
            parent=os[0] if len(os)==1 else ''
            pred[name]=parent
            require(parent in identity and identity.get(parent)==i and cfg.get(parent,{}).get('CASCADE_ORDER_A') in ('FIRST','MIDDLE'),'URAM invalid cascade predecessor')
        for port in ('A','B'):
            if kind=='FIRST':
                constant(row(name,'RDB_WR_'+port),'GND' if port=='A' else 'VCC','URAM effective read-A/write-B configuration unresolved')
                for signal in ('RDB_WR','EN'):constant(row(name,'CAS_IN_'+signal+'_'+port),'GND','URAM inactive FIRST cascade input not actual GND')
                en=row(name,'EN_'+port)
                require(bool(set(words(en.get('nets','')))&sources.get('read_enable' if port=='A' else 'write_enable',set())),'URAM effective enable boundary source mismatch')
            elif pred.get(name) in identity:
                for signal in ('RDB_WR','EN'):edge(name,'CAS_IN_'+signal+'_'+port,pred[name],'CAS_OUT_'+signal+'_'+port)
                # Preserve the actual unused direct mode values as measured;
                # effective modes above follow CAS inputs from the root.
                constant(row(name,'RDB_WR_'+port),'VCC','URAM unused direct mode observation changed')
            for bit in range(23):
                direct=row(name,f'ADDR_{port}[{bit}]');cascade=row(name,f'CAS_IN_ADDR_{port}[{bit}]')
                if kind=='FIRST':
                    constant(cascade,'GND','URAM inactive root CAS address not actual GND')
                    require(not words(cascade.get('startpoints','')),'URAM root constant CAS raw startpoints changed')
                    if bit<17:
                        ds=words(direct.get('drivers',''));rs=words(direct.get('driver_refs',''))
                        if port=='A':
                            own=addr.get((i,bit),{}).get('NAME','')+'/Q'
                            require(ds==[own],'URAM root unloaded/missing bit or cross-slice own read-Q mapping')
                        else:
                            expected_write=core_scope+f'/artifact_index_r_reg[{bit}]'+('_rep' if bit<9 else '')+'/Q'
                            require(ds==[expected_write],'URAM root write-address bit source changed')
                        require(len(rs)==1 and isff(rs[0]),'URAM root address actual FF source unresolved')
                        # This is a check on separately recorded raw facts,
                        # not a replacement of native C timing startpoints.
                        require(len(ds)==1 and words(direct.get('startpoints',''))==[ds[0].rsplit('/',1)[0]+'/C'],'URAM root raw FF timing startpoint differs')
                        require(not any(d.rsplit('/',1)[0] in original_names for d in ds),'old core address still drives memory')
                    else:
                        constant(direct,'GND','URAM masked high-address input not actual GND')
                        require(not words(direct.get('startpoints','')),'URAM constant high address raw startpoints changed')
                elif kind in ('MIDDLE','LAST'):
                    require(not words(direct.get('nets','')) and not words(direct.get('drivers','')) and not words(direct.get('driver_refs','')) and words(direct.get('startpoints',''))==[name+f'/ADDR_{port}[{bit}]'],'URAM unselected direct address raw evidence changed')
                    if pred.get(name) in identity:edge(name,f'CAS_IN_ADDR_{port}[{bit}]',pred[name],f'CAS_OUT_ADDR_{port}[{bit}]')
        clock=row(name,'CLK')
        require(bool(set(words(clock.get('nets','')))&sources.get('clock',set())),'URAM CLK differs from selected clock boundary')
        clock_drivers=words(clock.get('drivers',''));ports=words(clock.get('primary_ports',''));directions=words(clock.get('primary_port_directions',''))
        require((len(clock_drivers)==1 and not ports and not directions) or (not clock_drivers and len(ports)==len(directions)==1 and directions==['IN']),'URAM CLK source is not one exclusive actual leaf driver or primary input')
    children=collections.defaultdict(list)
    for name,parent in pred.items():
        if parent in identity:children[parent].append(name)
    require(all(len(cs)<=1 for cs in children.values()),'URAM address cascade branches')
    covered=set();chains=[]
    for root in roots:
        chain=[];name=root
        while name in identity and name not in chain:
            chain.append(name);covered.add(name)
            cs=children[name];name=cs[0] if len(cs)==1 else None
        require(name is None,'URAM address cascade cycle/branch')
        require(cfg.get(chain[-1],{}).get('CASCADE_ORDER_A')=='LAST','URAM cascade tail is not LAST')
        require(all(cfg.get(n,{}).get('CASCADE_ORDER_A')=='MIDDLE' for n in chain[1:-1]),'URAM cascade interior is not MIDDLE')
        chains.append(chain)
        try:chain_decode=[init(cfg.get(n,{}).get('SELF_ADDR_A','')) for n in chain]
        except (ValueError,TypeError):chain_decode=[]
        require(len(chain_decode)==len(chain) and len(set(chain_decode))==len(chain_decode),'URAM duplicate/missing decode within cascade chain')
        for member in chain[1:]:
            for port in ('A','B'):
                for bit in range(23):
                    want=words(row(root,f'ADDR_{port}[{bit}]').get('startpoints','')) if bit<17 else [root+f'/CAS_OUT_ADDR_{port}[{bit}]']
                    require(words(row(member,f'CAS_IN_ADDR_{port}[{bit}]').get('startpoints',''))==want,'URAM cascade raw address ancestry changed')
    require(covered==set(identity),'URAM cascade missing/rootless/cyclic coverage')
    for i in (0,1):
        require(decode[i]==collections.Counter({n:2 for n in range(20)}),'URAM native decode coverage changed')
        require(sorted(len(c) for c in chains if identity[c[0]]==i)==[4,4,8,8,8,8],'URAM actual chain inventory changed')
        try:actual_decode_chains=collections.Counter(tuple(init(cfg.get(n,{}).get('SELF_ADDR_A','')) for n in chain) for chain in chains if identity[chain[0]]==i)
        except (ValueError,TypeError):actual_decode_chains=collections.Counter()
        expected_decode_chains=collections.Counter({tuple(range(0,8)):2,tuple(range(8,16)):2,tuple(range(16,20)):2})
        require(actual_decode_chains==expected_decode_chains,'URAM measured per-chain decode profile changed')
    return {str(i):sum(identity[r]==i for r in roots) for i in (0,1)}

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
    validate_address_state(z,own_q,other_q,{r['NAME'] for r in original_addr},require)
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
 require(set(sources)=={'S','L','R','clock','reset','read_enable','write_enable'} and all(sources.values()),'native S/L/R/clock/reset boundary unresolved')
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
 read_roots=validate_effective_memories(s,memories,addr,{r['NAME'] for r in original_addr},sources,require)
 # Exact new helper resources, and module/global observations, are separate units.
 return dict(passed=not errors,errors=errors,phase=meta.get('phase'),fixture=fixture,exact_new_M2_LUT1=len(role['buffer']),exact_new_address_FF=helper_ff,exact_helper_LUT=helper_luts,exact_helper_CARRY8=helper_carry,protected_added_LUT=len(role['buffer'])+len(controls),URAM_per_slice={str(i):len(m) for i,m in memories.items()},actual_address_root_counts=read_roots,limits_not_timing_proof=True,stage_note='Exact helper/M2 resources plus native connectivity; same-stage total module/global resource deltas are checked separately against qualified synthesis reports. Old failed-route net differences cannot prove synthesis budgets.')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fixture',action='store_true');a=p.parse_args()
 spec=json.loads(a.spec.read_text());snapshot=json.loads(a.snapshot.read_text())
 if not a.fixture:snapshot=decode_grouped_snapshot(snapshot)
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
