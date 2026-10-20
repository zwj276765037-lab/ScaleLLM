#!/usr/bin/env python3
"""Authoritative M2 proposal: per-entry native clock-region buckets, <=256 FF."""
import sys
sys.dont_write_bytecode=True
import collections,datetime,json,re
from pathlib import Path
import extract_field_evidence as p

def crkey(t):
 slr,cr=t;m=re.fullmatch(r'X(\d+)Y(\d+)',cr);return (int(slr[3:]),*map(int,m.groups()))
def main():
 out=p.HERE/'F1_F3_C_M2_region_groups.json';assert not out.exists()
 x=json.loads((p.HERE/'F4_parent_meta_register_objects.json').read_text())
 sites=list(p.rows(p.NATIVE/'sites.tsv'));clb=collections.defaultdict(list)
 for s in sites:
  if s['site'].startswith('SLICE_'):clb[(s['SLR'],s['clock_region'])].append(s['site'])
 groups=[];regions=collections.defaultdict(lambda:dict(head_FF=0,tail_FF=0,head_buffers=0,tail_buffers=0))
 for family in ('head','tail'):
  bucket=collections.defaultdict(list)
  for r in x:
   if r['family']==family:bucket[(r['endpoint_physical']['SLR'],r['endpoint_physical']['clock_region'])].append(r)
  for key in sorted(bucket,key=crkey):
   rs=sorted(bucket[key],key=lambda r:r['bit']);regions[key][family+'_FF']+=len(rs)
   for start in range(0,len(rs),256):
    a=rs[start:start+256];regions[key][family+'_buffers']+=1
    groups.append(dict(id=f'{family}_{key[1]}_{start//256:02d}',family=family,SLR=key[0],clock_region=key[1],bits=[r['bit'] for r in a],width=len(a),FF_names=[r['name'] for r in a],old_LOCs=[r['LOC'] for r in a],FF_REF_counts=dict(collections.Counter(r['REF_NAME'] for r in a)),fixed_LOC_count=sum(r['IS_LOC_FIXED']=='1' for r in a),fixed_BEL_count=sum(r['IS_BEL_FIXED']=='1' for r in a),direct_macro_values=dict(collections.Counter(r['MACRO_NAME'] for r in a)),direct_RLOC_values=dict(collections.Counter(r['RLOC'] for r in a)),constraint_rule='one protected LUT1 plus these FF members hard inside their existing native clock region; no individual LOC/BEL; all data D/Q equations unchanged'))
 for family in ('head','tail'):
  assert sorted(b for g in groups if g['family']==family for b in g['bits'])==list(range(6560))
 rtable=[dict(SLR=k[0],clock_region=k[1],native_CLB_site_count=len(clb[k]),**v) for k,v in sorted(regions.items(),key=lambda a:crkey(a[0]))]
 result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='ENGINEERING_PROPOSAL_ROOT_NOT_SELECTED',supersedes_logical_27_group_prototype=True,groups_per_entry=dict(collections.Counter(g['family'] for g in groups)),total_LUT1=len(groups),distinct_local_CE_upper_bound=len(groups),control_set_delta_upper_bound=len(groups)-2,groups=groups,region_costs=rtable,verified_input_files=p.VERIFIED)
 out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='groups'},indent=2))
if __name__=='__main__':main()
