"""A007 one-pass closed-native-table verification; no EDA or DCP reads."""
from pathlib import Path
import json,hashlib,collections,re,datetime
ROOT=Path(__file__).resolve().parents[3]
OWN=Path(__file__).resolve().parent
AT=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT019_fresh_core_uram_address_attribution'
DELIVERY=json.loads((AT/'evidence/AT019_terminal_and_complete_native_facts.json').read_text())
FILES={Path(x['path']).name:x for x in DELIVERY['closed_report_outputs']}
identities=[];issues=[]
def need(value,message):
 if not value:issues.append(message)
def stream(name):
 rec=FILES[name];h=hashlib.sha256();size=0
 with Path(rec['path']).open('rb') as f:
  for line in f:
   h.update(line);size+=len(line)
   yield json.loads(line)
 assert size==rec['bytes'] and h.hexdigest()==rec['sha256'],name
 identities.append({'name':name,'bytes':size,'sha256':h.hexdigest()})
def cell_id(name):
 m=re.fullmatch(r'inst/u_core/u_compute/u_attention/u_meta/g_m003_width_slices.g_slice\[([01])\]\.meta_mem_reg_uram_(\d+)',name)
 if not m:raise ValueError(name)
 return int(m[1]),int(m[2])
configs=list(stream('uram_configs.jsonl'));cfg={x['cell']:x for x in configs}
need(len(configs)==len(cfg)==80,'config inventory is not unique80')
need({cell_id(x) for x in cfg}=={(s,n) for s in (0,1) for n in range(40)},'cell inventory differs')
addr=list(stream('uram_address_pins.jsonl'));by={(x['cell'],x['pin']):x for x in addr}
expected={f'{family}[{i}]' for family in ('ADDR_A','ADDR_B','CAS_IN_ADDR_A','CAS_IN_ADDR_B') for i in range(23)}
need(len(addr)==len(by)==7360,'address inventory duplicate/count')
for cell in cfg:need({x['pin'] for x in addr if x['cell']==cell}==expected,'address coverage '+cell)
patterns=collections.Counter();point_classes=collections.Counter();raw_counts={k:collections.Counter() for k in ('zero_startpoint_by_port','empty_directdriver_by_port','empty_nets_by_port')}
for x in addr:
 cell=x['cell'];port=x['pin'].split('[')[0]
 need(cell in cfg and x['slice']==cell_id(cell)[0] and x['pin_name']==cell+'/'+x['pin'] and x['ref']=='URAM288','row identity '+x['pin_name'])
 need(x['native_startpoint_count']==len(x['startpoints']),'startpoint count '+x['pin_name'])
 need(len(x['drivers'])==len(x['driver_cells'])==len(x['driver_refs']),'driver cardinality '+x['pin_name'])
 need(all(a.rsplit('/',1)[0]==b for a,b in zip(x['drivers'],x['driver_cells'])),'driver owner '+x['pin_name'])
 for p in x['drivers']+x['startpoints']:
  for sl in re.findall(r'g_slice\[([01])\]',p):need(int(sl)==x['slice'],'cross-slice source '+x['pin_name']+' <- '+p)
  need('meta_read_addr_r_reg[' not in p,'old core address '+x['pin_name'])
 if not x['startpoints']:raw_counts['zero_startpoint_by_port'][port]+=1
 if not x['drivers']:raw_counts['empty_directdriver_by_port'][port]+=1
 if not x['nets']:raw_counts['empty_nets_by_port'][port]+=1
 if not x['startpoints']:
  need(len(x['drivers'])==1 and x['driver_refs'] in [['GND'],['VCC']],'empty startpoint unresolved '+x['pin_name'])
  need(x['single_constant_driver']==1 and x['constant_value_from_single_driver_ref']==(x['driver_refs']==['VCC']),'constant annotation '+x['pin_name'])
 for p in x['startpoints']:
  point_classes['FF_C' if p.endswith('/C') else 'unconnected_pin_self' if p==x['pin_name'] else 'URAM_CAS_OUT' if '/CAS_OUT_ADDR_' in p else 'other']+=1
base='inst/u_core/u_compute/u_attention/u_meta';pred={};roots=[];classes=collections.Counter();decode=collections.defaultdict(collections.Counter)
for cell,c in cfg.items():
 sl,num=cell_id(cell);kind=c['CASCADE_ORDER_A'];patterns[kind+'/'+c['CASCADE_ORDER_B']]+=1
 need(c['slice']==sl and kind==c['CASCADE_ORDER_B'] and kind in {'FIRST','MIDDLE','LAST'},'config kind '+cell)
 for port in ('A','B'):
  for prop in ('IREG_PRE_','REG_CAS_','OREG_','USE_EXT_CE_'):need(c[prop+port]=='FALSE',prop+port+' '+cell)
  for prop in ('IS_RDB_WR_','IS_EN_'):need(c[prop+port+'_INVERTED']=="1'b0",prop+port+' '+cell)
  need(c['SELF_MASK_'+port]=="11'h7E0",'mask '+cell)
  value=int(c['SELF_ADDR_'+port].split("'h")[1],16)
  need(int(c['MEM.PORT'+port+'.ADDRESS_BEGIN'])==value*4096 and int(c['MEM.PORT'+port+'.ADDRESS_END'])==value*4096+4095,'native decode span '+cell+'/'+port)
  if port=='A':decode[sl][value]+=1
 need(c['SELF_ADDR_A']==c['SELF_ADDR_B'] and c['IS_CLK_INVERTED']=="1'b0",'A/B decode or clock '+cell)
 if kind=='FIRST':roots.append(cell);pred[cell]=None
 else:
  z=by[(cell,'CAS_IN_ADDR_A[0]')]
  need(len(z['driver_cells'])==1,'missing predecessor '+cell)
  pred[cell]=z['driver_cells'][0] if z['driver_cells'] else None
  need(pred[cell] in cfg and cell_id(pred[cell])[0]==sl and cfg[pred[cell]]['CASCADE_ORDER_A']!='LAST','invalid predecessor '+cell)
 for port in ('A','B'):
  for bit in range(23):
   direct=by[(cell,f'ADDR_{port}[{bit}]')];cascade=by[(cell,f'CAS_IN_ADDR_{port}[{bit}]')]
   if kind=='FIRST':
    if bit<17:
     if port=='A':expected_q=f'{base}/g_m003_width_slices.g_slice[{sl}].u_addr/address_r_reg[{bit}]/Q';need(direct['drivers']==[expected_q],'root ownQ '+direct['pin_name'])
     else:need(len(direct['drivers'])==1 and re.search(r'artifact_index_r_reg\['+str(bit)+r'\](?:_rep)?/Q$',direct['drivers'][0]),'root writeQ '+direct['pin_name'])
     need(direct['driver_refs']==['FDCE'] and direct['startpoints']==[direct['drivers'][0][:-1]+'C'],'root FF/C '+direct['pin_name']);classes['active_direct_dynamic']+=1
    else:
     need(direct['driver_refs']==['GND'] and not direct['startpoints'] and direct['constant_value_from_single_driver_ref']==0,'root high constant '+direct['pin_name']);classes['active_direct_masked_high_GND']+=1
    need(cascade['driver_refs']==['GND'] and not cascade['startpoints'],'root unused CAS constant '+cascade['pin_name']);classes['inactive_root_CAS_GND']+=1
   else:
    need(direct['nets']==[] and direct['drivers']==[] and direct['driver_refs']==[] and direct['startpoints']==[direct['pin_name']],'inactive direct raw shape '+direct['pin_name']);classes['inactive_direct_unconnected_self_startpoint']+=1
    need(cascade['driver_refs']==['URAM288'] and cascade['drivers']==[pred[cell]+f'/CAS_OUT_ADDR_{port}[{bit}]'] and bool(cascade['nets']),'cascade predecessor bit '+cascade['pin_name']);classes['active_CAS_predecessor']+=1
children=collections.defaultdict(list)
for cell,parent in pred.items():
 if parent is not None:children[parent].append(cell)
chains=[];covered=set()
for root in roots:
 chain=[];cell=root
 while cell is not None:
  need(cell not in chain,'cycle '+root)
  if cell in chain:break
  chain.append(cell);covered.add(cell);need(len(children[cell])<=1,'branching address cascade '+cell)
  cell=children[cell][0] if children[cell] else None
 need(cfg[chain[-1]]['CASCADE_ORDER_A']=='LAST','chain tail '+root)
 chains.append(chain)
 for cell in chain:
  for port in ('A','B'):
   for bit in range(23):
    selected=by[(cell,f'{"ADDR" if cell==root else "CAS_IN_ADDR"}_{port}[{bit}]')]
    if cell!=root:
     exp=by[(root,f'ADDR_{port}[{bit}]')]['startpoints'] if bit<17 else [root+f'/CAS_OUT_ADDR_{port}[{bit}]']
     need(selected['startpoints']==exp,'cascade raw startpoint ancestry '+selected['pin_name'])
need(covered==set(cfg),'uncovered cells')
for sl in (0,1):need(dict(decode[sl])=={n:2 for n in range(20)},'decode bins not0..19 twice '+str(sl))
modes=list(stream('uram_mode_pins.jsonl'));mode={(x['cell'],x['pin']):x for x in modes};need(len(modes)==len(mode)==160,'mode inventory')
mode_counts=collections.Counter()
for cell,c in cfg.items():
 for port in ('A','B'):
  x=mode[(cell,'RDB_WR_'+port)];value='GND' if c['CASCADE_ORDER_A']=='FIRST' and port=='A' else 'VCC';need(x['driver_refs']==[value],'direct mode ref '+cell+'/'+port);mode_counts[port+':'+value]+=1
aux_counts=collections.Counter();aux_empty_drivers=collections.Counter();aux_empty_nets=collections.Counter();aux_cells=collections.Counter();aux_keys=set();control={};clock=[];cross_aux=0
for x in stream('uram_auxiliary_pins.jsonl'):
 cell=x['cell'];pin=x['pin'];key=(cell,pin);need(cell in cfg and x['slice']==cell_id(cell)[0] and x['pin_name']==cell+'/'+pin,'aux identity '+str(key));need(key not in aux_keys,'duplicate aux '+str(key));aux_keys.add(key);aux_counts[pin]+=1;aux_cells[cell]+=1
 need('ADDR' not in pin and pin not in {'RDB_WR_A','RDB_WR_B'} and (any(v in pin for v in ('EN','WE','CLK','RDB_WR')) or pin.startswith('CAS')),'aux selection '+str(key))
 if not x['drivers']:aux_empty_drivers[pin]+=1
 if not x['nets']:aux_empty_nets[pin]+=1
 need(len(x['drivers'])==len(x['driver_cells'])==len(x['driver_refs']),'aux driver alignment '+str(key))
 for driver in x['drivers']:
  for sl in re.findall(r'g_slice\[([01])\]',driver):
   if int(sl)!=x['slice']:cross_aux+=1
 if pin=='CLK':clock.append({'cell':cell,'net_count':len(x['nets']),'net_list_sha256':hashlib.sha256(json.dumps(x['nets'],separators=(',',':')).encode()).hexdigest(),'driver_count':len(x['drivers'])})
 if pin in {'CAS_IN_RDB_WR_A','CAS_IN_RDB_WR_B','CAS_IN_EN_A','CAS_IN_EN_B','EN_A','EN_B'}:control[key]=x
need(len(aux_keys)==26960 and set(aux_cells.values())=={337},'aux total/cell count')
need(dict(aux_empty_drivers)=={'CLK':80} and not aux_empty_nets,'aux empty classifications')
control_edges=collections.Counter()
for cell,parent in pred.items():
 if parent is None:continue
 for signal in ('RDB_WR_A','RDB_WR_B','EN_A','EN_B'):
  x=control[(cell,'CAS_IN_'+signal)];expected=parent+'/CAS_OUT_'+signal
  need(x['drivers']==[expected] and x['driver_refs']==['URAM288'],'cascade control edge '+cell+'/'+signal)
  control_edges[signal]+=1
summary={'schema':'A007_AT019_closed_native_independent_analysis_v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'identities':identities,'issues':issues,'counts':{'cells':len(cfg),'address_rows':len(addr),'mode_rows':len(modes),'auxiliary_rows':len(aux_keys),'aux_per_cell':dict(collections.Counter(aux_cells.values()))},'cascade_configs':dict(patterns),'address_classifications':dict(classes),'raw_startpoint_classes':dict(point_classes),'raw_count_comparison':{k:dict(v) for k,v in raw_counts.items()},'chains':[{'slice':cell_id(x[0])[0],'members':[cell_id(c)[1] for c in x],'decode_values':[int(cfg[c]['SELF_ADDR_A'].split("'h")[1],16) for c in x]} for x in chains],'same_slice_acyclic_nonbranching_address_chain_coverage':len(covered),'direct_mode_refs':dict(mode_counts),'verified_active_cascade_control_edges':dict(control_edges),'effective_readwrite_interpretation':'All actual IREG_PRE/REG_CAS false and inversion0; FIRST directA GND/B VCC, subsequent actual CAS_IN_RDB_WR edges follow same preceding cell. Vendor selected-input model therefore supports effective A read/B write for these80. Direct RDB_WR_A on68nonFIRST is unused VCC.','aux_empty_drivers':dict(aux_empty_drivers),'aux_empty_nets':dict(aux_empty_nets),'aux_cross_slice_driver_mentions':cross_aux,'CLK_observations':{'rows':len(clock),'net_counts':dict(collections.Counter(x['net_count'] for x in clock)),'unique_net_list_hashes':sorted({x['net_list_sha256'] for x in clock}),'no_pin_driver':all(x['driver_count']==0 for x in clock),'primary_port':'UNPROVEN pending native port query'},'limits':['No rewriting FF/C toQ; actual own bit owners/cascade graph checked using separate fields.','Native timing startpoints alone are not proof of physical source: inactive direct pins return themselves; high CAS bits may stop at root CAS_OUT despite upstreamGND.','Decode0..19 twice per slice is verified; data width/return mapping/RDW/helperD/global budget/overlay/G4 are not certified by this diagnostic.','Auxiliary156793856B read exactly once line-by-line for hash/cardinality/control edges and empty-driver classification; no repeated large-table scan or DCP read.']}
out=OWN/'AT019_closed_native_independent_analysis.json';assert not out.exists();out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ['issues','counts','cascade_configs','address_classifications','raw_startpoint_classes','chains','direct_mode_refs','verified_active_cascade_control_edges','aux_empty_drivers','aux_cross_slice_driver_mentions','CLK_observations']},indent=2))
print('OUTPUT',out.stat().st_size,hashlib.sha256(out.read_bytes()).hexdigest())
