#!/usr/bin/env python3
"""Independent CPU-only reconstruction from native TSVs, after export closes."""
import argparse,collections,csv,datetime,hashlib,json,os,re
from pathlib import Path

def rows(path):
 with path.open(newline='') as f:yield from csv.DictReader(f,delimiter='\t')
def identity(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for part in iter(lambda:f.read(4*1024*1024),b''):h.update(part)
 return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=h.hexdigest())
def run(out,plan):
 # Primitive membership and native site relationships are independent inputs.
 cell_loc={};dsp_parent={}
 for row in rows(out/'cells.tsv'):
  cell_loc[row['name']]=row['LOC']
  if row['REF_NAME'].startswith('DSP'):dsp_parent[row['name']]=row['name'].rsplit('/',1)[0]
 site_slr={row['site']:row['SLR'] for row in rows(out/'sites.tsv')}
 base=plan['normalization_base']
 def module(owner):
  if owner=='TOP_PORT':return owner
  containing=owner.rsplit('/',1)[0] if '/' in owner else ''
  if containing.startswith(base+'/'):return base+'/'+'/'.join(containing[len(base)+1:].split('/')[:4])
  return '/'.join(containing.split('/')[:4]) or 'ROOT'
 def slr(owner):
  if owner=='TOP_PORT':return owner
  current=owner
  while current in cell_loc and not cell_loc[current] and current in dsp_parent:current=dsp_parent[current]
  return site_slr.get(cell_loc.get(current,''),'UNKNOWN')
 inventory={}
 for row in rows(out/'net_inventory.tsv'):
  name=row['canonical'];assert name not in inventory,'duplicate native canonical inventory'
  inventory[name]=dict(conflict=int(row['conflict']),aliases=int(row['aliases']),tags=row['seed_tags'],drivers=0,driver_module=None,source=None,load_slrs=set(),loads=0,inouts=0,unknowns=0)
 segments={};alias_counts=collections.Counter();smallest_segment={};alias_rows=0;duplicate_alias_rows=0
 for row in rows(out/'aliases.tsv'):
  alias_rows+=1;name=row['segment'];canonical=row['canonical']
  assert canonical in inventory,'alias maps outside complete inventory'
  if name in segments:
   assert segments[name]==canonical,'native segment maps to multiple canonical IDs'
   duplicate_alias_rows+=1
  else:
   segments[name]=canonical;alias_counts[canonical]+=1
   smallest_segment[canonical]=min(smallest_segment.get(canonical,name),name)
 for canonical,record in inventory.items():
  assert alias_counts[canonical]==record['aliases'],'native closure cardinality differs from inventory'
  assert canonical==smallest_segment[canonical],'canonical ID is not lexical minimum native segment'
 raw_count=0;mapped=collections.Counter()
 for row in rows(out/'raw_conflicts.tsv'):
  raw_count+=1;canonical=segments[row['native_net']]
  assert inventory[canonical]['conflict']==1,'raw CONFLICTS maps to supplementary-only canonical'
  mapped[canonical]+=1
 failed={name for name,record in inventory.items() if record['conflict']}
 assert set(mapped)==failed,'raw conflict closure and inventory canonical IDs differ'
 del segments
 endpoint_count=0
 for row in rows(out/'endpoints.tsv'):
  endpoint_count+=1;record=inventory[row['canonical']];direction=row['DIRECTION']
  if row['kind']=='TOP_PORT':
   role={'IN':'driver','OUT':'load'}.get(direction,'inout')
  else:role={'OUT':'driver','IN':'load','INOUT':'inout'}.get(direction,'unknown')
  if role=='driver':
   record['drivers']+=1;record['driver_module']=module(row['owner']);record['source']=slr(row['owner'])
  elif role=='load':record['loads']+=1;record['load_slrs'].add(slr(row['owner']))
  elif role=='inout':record['inouts']+=1
  else:record['unknowns']+=1
 groups=collections.Counter();computed={};unknown=collections.Counter()
 for name in failed:
  record=inventory[name]
  if record['inouts']:driver,source,bucket='INOUT_OR_AMBIGUOUS','AMBIGUOUS','INOUT_OR_AMBIGUOUS'
  elif record['drivers']>1:driver,source,bucket='MULTIDRIVER','MULTIPLE','MULTIDRIVER'
  elif not record['drivers']:driver,source,bucket='UNKNOWN_DRIVER','UNKNOWN','UNKNOWN_DRIVER'
  else:driver,source,bucket=record['driver_module'],record['source'],'SINGLE_DRIVER'
  load_slrs=','.join(sorted(record['load_slrs']));key=(driver,source,load_slrs or 'NO_LOADS')
  groups[key]+=1;computed[name]=(key,bucket);unknown[bucket]+=1
  unknown['source_SLR_UNKNOWN']+=source=='UNKNOWN';unknown['load_SLR_UNKNOWN']+='UNKNOWN' in record['load_slrs']
 seen=set()
 for row in rows(out/'failed_nets.tsv'):
  name=row['canonical'];assert name in failed and name not in seen,'extra or duplicate failed output net'
  seen.add(name);record=inventory[name];key,bucket=computed[name]
  assert key==(row['driver_module'],row['source_SLR'],row['load_SLRs'] or 'NO_LOADS'),'raw endpoint classifier disagrees with primary output'
  assert bucket==row['bucket'],'raw endpoint bucket mismatch'
  assert [record[k] for k in ['drivers','loads','inouts','unknowns']]==[int(row[k]) for k in ['driver_count','load_pin_count','INOUT_count','unknown_endpoint_count']],'raw endpoint cardinality mismatch'
 assert seen==failed,'failed-net output misses canonical IDs'
 ordered=sorted(groups,key=lambda key:(-groups[key],key))
 table=list(rows(out/'module_region_summary.tsv'))
 assert [(row['driver_module'],row['source_SLR'],row['load_SLR_set']) for row in table]==ordered,'primary sort/group key differs'
 assert [int(row['unique_conflict_nets']) for row in table]==[groups[key] for key in ordered],'raw unique group counts differ'
 top=set(ordered[:20]);main={name for name,(key,_) in computed.items() if key in top}
 supplementary={name for name in failed if inventory[name]['tags']};combined=main|supplementary
 coverage=json.loads((out/'unknowns_and_coverage.json').read_text())
 expected=dict(native_raw_conflict_objects=raw_count,canonical_conflict_nets=len(failed),primary_groups=len(groups),primary_group_sum=sum(groups.values()),top20_unique_conflict_nets=len(main),supplemental_unique_conflict_nets=len(supplementary),top20_plus_supplemental_union=len(combined))
 for field,value in expected.items():assert coverage[field]==value,'coverage field differs: '+field
 supplemental_summary=[]
 tags=sorted({tag for record in inventory.values() for tag in record['tags'].split(',') if tag})
 for tag in tags:
  selected={name for name,record in inventory.items() if tag in record['tags'].split(',')}
  cross=collections.Counter()
  for name in selected&failed:
   key,_=computed[name]
   cross[(key[1],key[2])]+=1
  supplemental_summary.append(dict(tag=tag,canonical_total=len(selected),conflict_canonical=len(selected&failed),conflict_source_load_groups=[dict(source_SLR=key[0],load_SLR_set=key[1],unique_nets=count) for key,count in sorted(cross.items(),key=lambda pair:(-pair[1],pair[0]))]))
 native_counts={}
 for line in (out/'native_route_status.rpt').read_text().splitlines():
  match=re.match(r'^\s*(.*?)\s*:\s*(\d+)\s*:\s*$',line)
  if match:native_counts[match.group(1).rstrip('.').strip()]=int(match.group(2))
 current_conflict_count=native_counts['# of nets with resource conflicts']
 result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Independent raw native TSV alias/canonical and endpoint classification audit; no EDA queries',assertions_passed=True,**expected,frozen_E008_conflict_nets=547548,canonical_minus_E008_baseline=len(failed)-547548,current_native_route_status=native_counts,current_native_report_conflict_nets=current_conflict_count,canonical_minus_current_native_report=len(failed)-current_conflict_count,native_report_reconciliation='EXACT' if len(failed)==current_conflict_count else 'DIFFERENT_COUNTS_RETAINED_REQUIRES_REVIEW',alias_rows=alias_rows,unique_segments=sum(alias_counts.values()),duplicate_identical_alias_rows=duplicate_alias_rows,raw_mapped_unique_canonical=len(mapped),native_endpoint_rows=endpoint_count,top20_and_supplemental_overlap=len(main&supplementary),coverage_fraction=len(combined)/len(failed) if failed else None,buckets=dict(unknown),top20=[dict(rank=index+1,driver_module=key[0],source_SLR=key[1],load_SLR_set=key[2],unique_nets=groups[key]) for index,key in enumerate(ordered[:20])],supplementary=supplemental_summary,unmeasured=['full overlap node mapping','full cut TNS','per-net SLL'],G1='PENDING_INDEPENDENT_REVIEW')
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',type=Path,required=True);a=ap.parse_args();at=a.attempt.resolve();out=at/'evidence/native'
 assert (at/'status.json').exists() and json.loads((at/'status.json').read_text())['exit_code']==0,'Successful natural native closure required'
 assert (out/'native_completed.txt').exists(),'Native extraction completion required'
 target=at/'independent_raw_attribution_audit_v2.json';assert not target.exists(),'Append-only audit'
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 result=run(out,json.loads((at/'sources/query_plan.json').read_text()));result['producer']=identity(Path(__file__));result['status']=identity(at/'status.json')
 with target.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
