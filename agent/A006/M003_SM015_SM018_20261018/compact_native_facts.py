"""Summarize closed native exports for independent review; never invokes EDA."""
from pathlib import Path
import argparse, collections, datetime, hashlib, json, re
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--phases',nargs='+',required=True);a=p.parse_args()
def fid(f):return dict(path=str(f.resolve()),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest())
def words(v):return [s.strip('{}') for s in str(v).split()]
def protected(row):return str(row.get('DONT_TOUCH')).lower() in ('1','true','yes')
def digest(values):return hashlib.sha256('\n'.join(sorted(values)).encode()).hexdigest()
result=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Derived bounded facts from closed actual native exports; raw identities/JSON field locators retained. No new EDA query and no independent G4 verdict.',phases={})
for phase in a.phases:
 sf=a.report/f'm003_native_{phase}.json';qf=a.report/f'm003_qualification_{phase}.json';s=json.loads(sf.read_text());q=json.loads(qf.read_text());assert s['meta']['kind']=='native' and not q['fixture'] and q['snapshot_sha256']==fid(sf)['sha256']
 roles=collections.defaultdict(list)
 for row in s['cells']:roles[row['role']].append(row)
 payload=collections.Counter(r.get('family') for r in roles['payload']);buffers=collections.Counter(r.get('group','').split('_')[0] for r in roles['buffer'])
 addr={(str(r['slice']),str(r['bit'])):r for r in roles['address']};address=[]
 for sl in ('0','1'):
  own={r['NAME']+'/Q' for (i,b),r in addr.items() if i==sl};other={r['NAME']+'/Q' for (i,b),r in addr.items() if i!=sl};rows=[r for (i,b),r in addr.items() if i==sl]
  address.append(dict(slice=sl,FF=len(rows),protected=sum(protected(r) for r in rows),own_Q_startpoints_present=sum(bool(set(words(r.get('D_startpoints','')))&own) for r in rows),other_Q_startpoints_present=sum(bool(set(words(r.get('D_startpoints','')))&other) for r in rows),core_address_startpoints_present=sum(any('meta_read_addr_r_reg[' in x for x in words(r.get('D_startpoints',''))) for r in rows),raw_locator='cells[role=address,slice='+sl+'].D_startpoints/CE_drivers/C_nets/CLR_nets'))
 config={}
 for row in s['uram_configs']:
  for k,v in row.items():
   if re.search('CASCADE|OREG|IREG|WRITE|READ|BWE|CLOCK|WIDTH|DEPTH',k):config.setdefault(k,collections.Counter())[str(v)]+=1
 config={k:dict(v) for k,v in sorted(config.items())}
 pools=[dict(NAME=r['NAME'],actual_site_count=len(set(words(r['actual_sites']))),actual_sites_sha256=digest(set(words(r['actual_sites']))),IS_SOFT=r['IS_SOFT'],EXCLUDE_PLACEMENT=r['EXCLUDE_PLACEMENT'],CONTAIN_ROUTING=r['CONTAIN_ROUTING'],raw_locator='pblocks[NAME='+r['NAME']+']') for r in s['pblocks']]
 c01=roles['c01'];boundary=collections.defaultdict(list)
 for row in s['boundaries']:boundary[row['tag']].append(row)
 metadata_names=[r for r in s['meta_ref_cells'] if re.search('rsp|response|read_data|read_valid|payload.*reg',r['NAME'],re.I)]
 item=dict(raw_snapshot=fid(sf),qualification_identity=fid(qf),qualification=q,role_counts={k:len(v) for k,v in roles.items()},payload_family_counts=dict(payload),CE_edges=len(s['ce_edges']),CE_group_count=len({e['group'] for e in s['ce_edges']}),master_group_count=len(s['master_inputs']),own_state=address,protected_M2_LUT1=sum(protected(r) for r in roles['buffer']),protected_helper_FF=sum(protected(r) for r in roles['address']),C01_members=len(c01),C01_reference_counts=dict(collections.Counter(r['REF_NAME'] for r in c01)),C01_protected_count=sum(protected(r) for r in c01),boundaries={tag:dict(count=len(rows),protected=sum(protected(r) for r in rows),load_counts=sorted({r['load_count'] for r in rows}),terminal_sets=sorted({tuple(sorted(set(words(r['load_terminals'])))) for r in rows})) for tag,rows in boundary.items()},URAM_configuration_unique_values=config,URAM_configuration_count=len(s['uram_configs']),native_hard_pool_facts=pools,metadata_ref_cell_count=len(s['meta_ref_cells']),metadata_response_related_name_count=len(metadata_names),metadata_response_related_examples=metadata_names[:16],metadata_locator='meta_ref_cells names/refs; uram_configs full native properties; memory_pins read-A/write-B constants,ADDR startpoints,CAS_IN drivers',facts_scope='Response candidates are names/refs, not an independent downstream-pin proof; functional collision/old-value tests and same-stage total budgets remain distinct evidence.')
 for name in [f'integrity_{phase}.json',f'constraints_{phase}.json',f'admission_{phase}.txt',f'{phase}_command_result.txt','m003_same_stage_budget.json']:
  f=a.report/name
  if f.exists():item.setdefault('additional_originals',[]).append(fid(f))
 result['phases'][phase]=item
assert not a.output.exists();a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(fid(a.output)))
