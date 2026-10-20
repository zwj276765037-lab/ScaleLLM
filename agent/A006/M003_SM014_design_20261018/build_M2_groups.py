#!/usr/bin/env python3
"""Exact fixed 27-group payload partition, using already extracted actual FF objects."""
import collections,datetime,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
groups=[]
def add(label,bits):groups.append(dict(group=len(groups),label=label,bits=bits,width=len(bits)))
for branch in range(2):
 for part in range(9):
  lo=12+branch*2304+part*256;add(f'branch{branch}_activation_{part}',list(range(lo,lo+256)))
 add(f'branch{branch}_activation_metadata',list(range(6156+branch*64,6156+(branch+1)*64))+list(range(6284+branch*48,6284+(branch+1)*48)))
for part in range(6):
 lo=4620+part*256;add(f'common_weights_{part}',list(range(lo,lo+256)))
add('common_metadata',list(range(12))+list(range(6380,6560)))
assert len(groups)==27 and sorted(b for g in groups for b in g['bits'])==list(range(6560))
objs=json.loads((HERE/'F4_parent_meta_register_objects.json').read_text())
by={(r['family'],r['bit']):r for r in objs if r['family'] in ('head','tail')}
for g in groups:
 for family in ('head','tail'):
  rs=[by[(family,b)] for b in g['bits']]
  g[family]=dict(FF_names=[r['name'] for r in rs],SLR_counts=dict(collections.Counter(r['endpoint_physical']['SLR'] for r in rs)),clock_region_counts=dict(collections.Counter(r['endpoint_physical']['clock_region'] for r in rs)),LOCs=[r['LOC'] for r in rs])
out=HERE/'F1_F3_C_M2_exact_groups.json';assert not out.exists()
out.write_text(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),groups_per_entry=27,total_LUT1=54,payload_FF_unchanged=13120,max_group_width=256,groups=groups),indent=2)+'\n')
for g in groups:print(g['group'],g['label'],g['width'],'H',g['head']['SLR_counts'],g['head']['clock_region_counts'],'T',g['tail']['SLR_counts'],g['tail']['clock_region_counts'])
