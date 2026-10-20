#!/usr/bin/env python3
"""Existing E009 native resource pools and current URAM occupancy, offline only."""
import sys
sys.dont_write_bytecode=True
import collections,datetime,json,os,re
from pathlib import Path
import extract_field_evidence as p

def xy(s):
 m=re.search(r'_X(\d+)Y(\d+)$',s);return tuple(map(int,m.groups()))

def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 target=p.HERE/'F4_C_A3_resource_pool_inventory.json';assert not target.exists()
 sites={r['site']:r for r in p.rows(p.NATIVE/'sites.tsv')}
 pools=[]
 # Existing native site universe contains exactly 80 URAM sites in this SLR1 column.
 # These are disjoint proposed resource pools, NOT unoccupied or compatible packing proof.
 for i,(lo,hi,crs) in enumerate(((80,119,{'X4Y5','X4Y6'}),(120,159,{'X4Y8','X4Y9'}))):
  us=sorted((s for s,r in sites.items() if s.startswith('URAM288_') and xy(s)[0]==3 and lo<=xy(s)[1]<=hi),key=xy)
  cs=sorted((s for s,r in sites.items() if s.startswith('SLICE_') and r['clock_region'] in crs and r['SLR']=='SLR1'),key=xy)
  assert len(us)==40 and all(sites[s]['SLR']=='SLR1' for s in us)
  pools.append(dict(slice=i,bits=[i*128,i*128+127],width=128,depth=81920,URAM_arithmetic=40,
    URAM_sites=us,URAM_native_clock_regions=dict(collections.Counter(sites[s]['clock_region'] for s in us)),
    local_CLB_sites=cs,local_CLB_site_count=len(cs),local_CLB_clock_regions=sorted(crs),
    local_CLB_coordinate_bounds={'X':[min(xy(s)[0] for s in cs),max(xy(s)[0] for s in cs)],'Y':[min(xy(s)[1] for s in cs),max(xy(s)[1] for s in cs)]},
    current_URAM_occupants=[]))
 assert not set(pools[0]['URAM_sites'])&set(pools[1]['URAM_sites'])
 assert not set(pools[0]['local_CLB_sites'])&set(pools[1]['local_CLB_sites'])
 us_to_pool={s:i for i,a in enumerate(pools) for s in a['URAM_sites']}
 all_uram=[]
 for r in p.rows(p.NATIVE/'cells.tsv'):
  if r['REF_NAME'].startswith('URAM'):
   a=dict(**r,site_native_relationship=sites.get(r['LOC'],{}));all_uram.append(a)
   if r['LOC'] in us_to_pool:pools[us_to_pool[r['LOC']]]['current_URAM_occupants'].append(a)
 meta=p.META+'/u_meta/'
 for a in pools:
  occ=a['current_URAM_occupants'];a['current_occupants_count']=len(occ)
  a['current_metadata_count']=sum(r['name'].startswith(meta) for r in occ)
  a['current_other_count']=len(occ)-a['current_metadata_count']
  a['native_unoccupied_count']=len(a['URAM_sites'])-len({r['LOC'] for r in occ})
  a['current_other_owner_roots']=dict(collections.Counter('/'.join(r['name'].split('/')[:-1]) for r in occ if not r['name'].startswith(meta)))
 result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Existing E009 sites/cells targeted URAM scan, no EDA, no production edits',
  pools=pools,SLR1_native_URAM_sites=sum(s.startswith('URAM288_') and r['SLR']=='SLR1' for s,r in sites.items()),
  SLR1_occupied_URAM_count=sum(r['site_native_relationship'].get('SLR')=='SLR1' for r in all_uram),
  missing_field_boundary=['Current exact fixed/macro/cascade properties of non-deep occupants are unexported','CLB site counts are nominal resource universe, not compatible free FF/LUT/control packing','New graph connectivity, cascade and legality require G4'],
  verified_input_files=p.VERIFIED,producer=p.ident(Path(__file__)))
 with target.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='pools'},indent=2))
 for a in pools:print(json.dumps({k:v for k,v in a.items() if k not in ('URAM_sites','local_CLB_sites','current_URAM_occupants')},indent=2))
if __name__=='__main__':main()
