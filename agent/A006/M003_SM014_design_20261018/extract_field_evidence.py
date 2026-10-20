#!/usr/bin/env python3
"""SM014 sequential offline extraction; no Vivado query or production mutation."""
import csv,collections,datetime,hashlib,json,os,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'.research-agent/project.json').is_file())
AT=ROOT/'project/E009_m003_failed_net_attribution/experiment_results/runs/R001/attempts/AT003_failed_route_full_attribution_scalar_fix'
NATIVE=AT/'evidence/native'
BASE='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute'
SHARED=BASE+'/u_mlp/u_serial_command/u_shared_compute'
META=BASE+'/u_attention'
C01=BASE+'/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf'
TOP01=SHARED+'/u_branch1'
MANIFEST=json.loads((NATIVE/'attribution_manifest.json').read_text())['files']
VERIFIED={}

def rows(path):
 h=hashlib.sha256();count=0
 def lines():
  with path.open('rb') as f:
   for raw in f:h.update(raw);yield raw.decode('utf-8')
 for row in csv.DictReader(lines(),delimiter='\t'):count+=1;yield row
 actual=dict(bytes=path.stat().st_size,sha256=h.hexdigest())
 assert actual==MANIFEST[path.name],('changed native file',path,actual,MANIFEST[path.name])
 VERIFIED[path.name]=dict(path=str(path),rows=count,**actual)

def save(name,x):
 with (HERE/name).open('x') as f:f.write(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def table(name,header,data):
 with (HERE/name).open('x',newline='') as f:w=csv.writer(f,delimiter='\t');w.writerow(header);w.writerows(data)
def ident(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 assert not (HERE/'F1_extraction_summary.json').exists(),'append-only extraction'
 fields=json.loads((ROOT/'project/E009_m003_failed_net_attribution/experiment_source/SM014_parent_field_layout_baseline.json').read_text())['packed_fields']
 def field(bit):
  return next((f['field'] for f in fields if f['low']<=bit<=f['high']),'OUTSIDE_DECLARED_PAYLOAD')
 parent_pattern=re.compile('^'+re.escape(SHARED)+r'/parent_(head|tail)_r_reg\[(\d+)\](.*)$')
 meta_pattern=re.compile('^'+re.escape(META)+r'/meta_read_addr_r_reg\[(\d+)\](.*)$')
 cells={};regs={};uram={};critical={}
 critical_names={TOP01+'/clear_kernel_row_r_reg[0]','scalellm_vcu118_f05_bd_i/core/inst/u_core/u_paired_weight/maintenance_soft_clear_pulse_r_reg'}
 for row in rows(NATIVE/'deep_cells.tsv'):
  name=row['name'];cells[name]=row
  if row['REF_NAME'] in ('FDRE','FDSE','FDCE','FDPE'):
   match=parent_pattern.match(name)
   if match:regs[name]=dict(family=match.group(1),bit=int(match.group(2)),suffix=match.group(3),field=field(int(match.group(2))),cell=row)
   match=meta_pattern.match(name)
   if match:regs[name]=dict(family='meta',bit=int(match.group(1)),suffix=match.group(2),field='meta_read_addr',cell=row)
  if row['REF_NAME'].startswith('URAM') and name.startswith(META+'/u_meta/'):uram[name]=row
  if name in critical_names:critical[name]=row
 print('DEEP_CELLS_EXTRACTED',len(cells),'physical_regs',len(regs),'metadata_URAM',len(uram),flush=True)
 bynet=collections.defaultdict(list);byowner=collections.defaultdict(list);physical={}
 for row in rows(NATIVE/'candidate_endpoints.tsv'):
  bynet[row['canonical']].append(row);byowner[row['owner']].append(row)
  physical[row['LOC']]=dict(SLR=row['SLR'],clock_region=row['clock_region'])
 tiles=collections.defaultdict(list)
 for row in rows(NATIVE/'deep_site_tiles.tsv'):tiles[row['site']].append(row)
 print('CANDIDATE_ENDPOINTS_EXTRACTED',len(bynet),'nets',len(byowner),'owners',flush=True)
 def drivers(net):return [r for r in bynet[net] if (r['kind']=='LEAF_PIN' and r['DIRECTION']=='OUT') or (r['kind']=='TOP_PORT' and r['DIRECTION']=='IN')]
 def loads(net):return [r for r in bynet[net] if (r['kind']=='LEAF_PIN' and r['DIRECTION']=='IN') or (r['kind']=='TOP_PORT' and r['DIRECTION']=='OUT')]
 def classify(reader):
  owner=reader['owner']
  if owner in regs:return regs[owner]['family']+'_register_'+reader['REF_PIN_NAME']
  if owner.startswith(SHARED+'/u_branch0/'):return 'shared_compute_branch0'
  if owner.startswith(SHARED+'/u_branch1/'):return 'shared_compute_branch1'
  if owner in uram:return 'metadata_URAM'
  if owner.startswith(META+'/u_meta/'):return 'metadata_logic'
  return 'other'
 regpins=[];qreaders=[];dinputs=[];control=[];summary=collections.defaultdict(lambda:dict(logical_bits=set(),physical_FF=0,Q_covered=0,D_covered=0,CE_covered=0,C_covered=0,missing_Q=[],missing_D=[],Q_load_classes=collections.Counter(),Q_source_load_SLR=collections.Counter(),D_driver_SLR=collections.Counter()))
 for owner,reg in sorted(regs.items()):
  family=reg['family'];key=(family,reg['field']);s=summary[key];s['physical_FF']+=1;s['logical_bits'].add(reg['bit'])
  own=byowner.get(owner,[]);seenpins=collections.defaultdict(list)
  for row in own:seenpins[row['REF_PIN_NAME']].append(row)
  for pin in ('Q','D','CE','C','CLR','PRE','R','S'):
   ps=seenpins[pin]
   if pin in ('Q','D','CE','C'):s[pin+'_covered']+=bool(ps)
   if pin in ('Q','D') and not ps:s['missing_'+pin].append(owner)
   for ep in ps:
    ds=drivers(ep['canonical']);ls=loads(ep['canonical'])
    regpins.append([family,reg['field'],reg['bit'],owner,reg['cell']['REF_NAME'],reg['cell']['LOC'],pin,ep['canonical'],ep['SLR'],ep['clock_region'],len(ds),len(ls),json.dumps([d['name'] for d in ds])])
    if pin=='Q':
     for load in ls:
      cl=classify(load);s['Q_load_classes'][cl]+=1;s['Q_source_load_SLR'][(ep['SLR'],load['SLR'])]+=1
      qreaders.append([family,reg['field'],reg['bit'],owner,ep['canonical'],ep['SLR'],load['name'],load['owner'],load['REF_PIN_NAME'],load['LOC'],load['SLR'],load['clock_region'],cl])
    elif pin=='D':
     for d in ds:
      s['D_driver_SLR'][d['SLR']]+=1;props=cells.get(d['owner'],{});ins=[p for p in byowner.get(d['owner'],[]) if p['kind']=='LEAF_PIN' and p['DIRECTION']=='IN']
      dinputs.append([family,reg['field'],reg['bit'],owner,ep['canonical'],d['name'],d['owner'],props.get('REF_NAME','NOT_IN_DEEP_CELLS'),d['LOC'],d['SLR'],len(ins),json.dumps([dict(pin=p['name'],net=p['canonical'],drivers=[q['name'] for q in drivers(p['canonical'])]) for p in ins])])
    elif pin in ('CE','C','CLR','PRE','R','S'):
     control.append([family,reg['field'],reg['bit'],owner,pin,ep['canonical'],ep['SLR'],len(ls),json.dumps([dict(pin=d['name'],owner=d['owner'],SLR=d['SLR'],LOC=d['LOC']) for d in ds])])
 # Helpers are classified by actual primitive driver rather than alias/net spelling.
 helper_summary=collections.Counter();helper_rows=[]
 families={'MLP_PARENT_HEAD':'head','MLP_PARENT_TAIL':'tail','ATT_META_READ_ADDR':'meta'}
 for net,eps in bynet.items():
  tags=set(eps[0]['tags'].split(','));ds=drivers(net)
  for tag,family in families.items():
   if tag not in tags:continue
   real=[d for d in ds if d['owner'] in regs and regs[d['owner']]['family']==family and d['REF_PIN_NAME']=='Q']
   classification='REAL_REGISTER_Q' if real else 'HELPER_OR_OTHER_DRIVER'
   helper_summary[(tag,classification)]+=1
   if not real:helper_rows.append([tag,net,json.dumps([dict(pin=d['name'],owner=d['owner'],REF_NAME=cells.get(d['owner'],{}).get('REF_NAME','NOT_IN_DEEP_CELLS'),SLR=d['SLR'],LOC=d['LOC']) for d in ds]),len(loads(net))])
 out_summary=[]
 for (family,fname),s in sorted(summary.items()):
  x={k:v for k,v in s.items() if k not in ('logical_bits','Q_load_classes','Q_source_load_SLR','D_driver_SLR')}
  x.update(family=family,field=fname,logical_bit_count=len(s['logical_bits']),logical_bit_indices=sorted(s['logical_bits']),Q_load_classes=dict(s['Q_load_classes']),Q_source_load_SLR=[dict(source=a,load=b,pin_rows=count) for (a,b),count in sorted(s['Q_source_load_SLR'].items())],D_driver_SLR=dict(s['D_driver_SLR']));out_summary.append(x)
 table('F1_register_pins.tsv',['family','field','bit','register_owner','REF_NAME','register_LOC','pin','canonical','SLR','clock_region','driver_count','load_pin_count','driver_pin_IDs'],regpins)
 table('F1_Q_all_readers.tsv',['family','field','bit','register_owner','Q_canonical','source_SLR','load_pin','load_owner','load_ref_pin','load_LOC','load_SLR','load_clock_region','load_class'],qreaders)
 table('F1_D_drivers_and_selected_inputs.tsv',['family','field','bit','register_owner','D_canonical','driver_pin','driver_owner','driver_REF_NAME','driver_LOC','driver_SLR','selected_input_pin_count','selected_input_connections'],dinputs)
 table('F1_CE_clock_reset.tsv',['family','field','bit','register_owner','pin','canonical','register_SLR','total_net_load_pins','drivers'],control)
 table('F1_helpers_separate.tsv',['tag','canonical','actual_drivers','load_pin_count'],helper_rows)
 save('F1_field_summary.json',out_summary)
 physical_objects=[]
 for name,row in sorted(uram.items()):physical_objects.append(dict(**row,**physical.get(row['LOC'],dict(SLR='NOT_IN_SELECTED_ENDPOINTS',clock_region='NOT_IN_SELECTED_ENDPOINTS')),native_site_tiles=tiles[row['LOC']]))
 save('F4_metadata_URAM_objects.json',physical_objects)
 save('F4_parent_meta_register_objects.json',[dict(**reg['cell'],family=reg['family'],bit=reg['bit'],field=reg['field'],endpoint_physical=physical.get(reg['cell']['LOC'],{}),native_site_tiles=tiles[reg['cell']['LOC']]) for reg in regs.values()])
 save('F3_critical_control_objects.json',[dict(cell=row,selected_endpoints=byowner.get(name,[])) for name,row in critical.items()])
 x=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='SM014 sequential closed-table extraction only; no new EDA and no production edits',verified_input_files=VERIFIED,field_baseline=ident(ROOT/'project/E009_m003_failed_net_attribution/experiment_source/SM014_parent_field_layout_baseline.json'),actual_register_FF_by_family=dict(collections.Counter(reg['family'] for reg in regs.values())),logical_bits_by_family={family:len({reg['bit'] for reg in regs.values() if reg['family']==family}) for family in ['head','tail','meta']},helper_partition=[dict(tag=tag,classification=cl,canonical_nets=count) for (tag,cl),count in sorted(helper_summary.items())],metadata_URAM=len(uram),critical_control_cells_found=list(critical),C01_exact_root=C01,TOP01_exact_root=TOP01,identities_distinct=True,limitations=['Q consumers and D/CE/C connections cover only frozen selected native nets; absent pin/net marked missing, never guessed.', 'D-driver selected input cone is one hop within existing exported nets; unexported upstream input nets remain NOT_MEASURED.', 'Field widths are RTL declarations, helper count is not payload width.', 'No capacity/physical gain/selected candidate inferred.'],producer=ident(Path(__file__)))
 save('F1_extraction_summary.json',x);print(json.dumps(x,indent=2),flush=True)
if __name__=='__main__':main()
