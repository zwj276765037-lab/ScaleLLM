#!/usr/bin/env python3
"""CPU-only positive and independent negative fixtures for raw attribution audit."""
from pathlib import Path
import csv,json,tempfile,subprocess,importlib.util,datetime,hashlib,sys,os
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
E=HERE.parent

def tab(p,header,records):
 with p.open('w',newline='') as f:w=csv.writer(f,delimiter='\t');w.writerow(header);w.writerows(records)
def load(p):
 spec=importlib.util.spec_from_file_location(p.stem,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 path=HERE/'audit_raw_attribution_v2.py';audit=load(path);negative={}
 with tempfile.TemporaryDirectory() as td:
  p=Path(td);base='b/u_compute';plan=dict(normalization_base=base,driver_normalization='frozen first-four module oracle',representative_nets_per_group=16)
  (p/'plan.json').write_text(json.dumps(plan));(p/'native_route_status.rpt').write_text(' # of nets with resource conflicts : 4 :\n')
  tab(p/'cells.tsv',['name','REF_NAME','LOC','BEL','IS_PRIMITIVE'],[[base+'/a/d','FDRE','S0','A',1],[base+'/b/l','LUT1','S1','A',1],[base+'/a/e','FDRE','S0','B',1]])
  tab(p/'sites.tsv',['site','SLR','clock_region'],[['S0','SLR0','CR0'],['S1','SLR1','CR1']])
  tab(p/'net_inventory.tsv',['canonical','aliases','conflict','seed_tags'],[['n1',2,1,'FIXED'],['n2',1,1,''],['n3',1,1,''],['n4',1,1,''],['n5',1,0,'FIXED']])
  tab(p/'aliases.tsv',['canonical','segment'],[['n1','n1'],['n1','n1_alias'],['n2','n2'],['n3','n3'],['n4','n4'],['n5','n5']])
  tab(p/'raw_conflicts.tsv',['native_net'],[['n1'],['n1_alias'],['n2'],['n3'],['n4']])
  ends=[]
  def ep(n,cell,pin,d):ends.append([n,'LEAF_PIN',cell+'/'+pin,d,pin,0,cell])
  ep('n1',base+'/a/d','Q','OUT');ep('n1',base+'/b/l','I0','IN');ep('n2',base+'/b/l','I0','IN')
  ep('n3',base+'/a/d','Q','OUT');ep('n3',base+'/a/e','Q','OUT');ep('n3',base+'/b/l','I0','IN');ep('n4',base+'/b/l','IO','INOUT');ep('n5',base+'/a/d','Q','OUT');ep('n5',base+'/b/l','I0','IN')
  tab(p/'endpoints.tsv',['canonical','kind','name','DIRECTION','REF_PIN_NAME','IS_CLOCK','owner'],ends)
  subprocess.run(['/usr/bin/python3',str(E/'experiment_source/AT003_scalar_property_fix/aggregate.py'),'--out',str(p),'--plan',str(p/'plan.json')],check=True,capture_output=True,text=True)
  first=audit.run(p,plan)
  assert first['native_raw_conflict_objects']==5 and first['canonical_conflict_nets']==4 and first['unique_segments']==6 and first['top20_and_supplemental_overlap']==1 and first['top20_plus_supplemental_union']==4
  assert first['buckets']['UNKNOWN_DRIVER']==first['buckets']['MULTIDRIVER']==first['buckets']['INOUT_OR_AMBIGUOUS']==1
  assert first['current_native_report_conflict_nets']==4 and first['native_report_reconciliation']=='EXACT' and first['frozen_E008_conflict_nets']==547548 and first['canonical_minus_E008_baseline']==-547544
  original=(p/'failed_nets.tsv').read_text();changed=original.replace('SLR0\tSLR1','SLR2\tSLR1',1);assert changed!=original;(p/'failed_nets.tsv').write_text(changed)
  try:audit.run(p,plan)
  except AssertionError as ex:negative['incorrect_source_SLR']=str(ex)
  else:raise AssertionError('incorrect source-SLR classification accepted')
  assert negative['incorrect_source_SLR']=='raw endpoint classifier disagrees with primary output';(p/'failed_nets.tsv').write_text(original)
  original_alias=(p/'aliases.tsv').read_text()
  with (p/'aliases.tsv').open('a') as f:f.write('n2\tn1_alias\n')
  try:audit.run(p,plan)
  except AssertionError as ex:negative['contradictory_alias_assignment']=str(ex)
  else:raise AssertionError('contradictory alias assignment accepted')
  assert negative['contradictory_alias_assignment']=='native segment maps to multiple canonical IDs';(p/'aliases.tsv').write_text(original_alias)
  for name in ['net_inventory.tsv','aliases.tsv','endpoints.tsv','failed_nets.tsv']:
   with (p/name).open() as f:reader=csv.DictReader(f,delimiter='\t');header=reader.fieldnames;data=list(reader)
   for row in data:
    if row['canonical']=='n1':row['canonical']='zzz_noncanonical'
   tab(p/name,header,[[row[k] for k in header] for row in data])
  # v1 accepted a consistent arbitrary ID rename; v2 must recover the actual
  # minimum segment identity, rather than checking derived tables agree.
  assert load(HERE/'audit_raw_attribution.py').run(p,plan)['assertions_passed']
  try:audit.run(p,plan)
  except AssertionError as ex:negative['consistent_nonminimal_canonical_rename']=str(ex)
  else:raise AssertionError('nonminimal canonical ID accepted')
  assert negative['consistent_nonminimal_canonical_rename']=='canonical ID is not lexical minimum native segment'
  result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),producer=dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()),actual_exit_code=0,assertions_passed=True,positive=dict(raw_objects=5,canonical=4,groups=4,unique_segments=6,unknown_multidriver_inout_each=1,top20_supplement_overlap=1,union=4,nonconflict_supplementary_distinct=True,current_native_report=4,E008_baseline=547548,native_report_reconciliation='EXACT'),negative=negative,native_eda_executed=False,scope='Synthetic independent CPU reconstruction only; actual AT003 audit pending natural native success')
  target=HERE/'audit_raw_attribution_v2_cpu_checks.json'
  with target.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result,indent=2))
if __name__=='__main__':main()
