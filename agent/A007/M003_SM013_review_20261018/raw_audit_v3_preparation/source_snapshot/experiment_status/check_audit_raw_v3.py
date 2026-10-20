#!/usr/bin/env python3
"""Independent raw-audit fixtures including constants and exact deep selection."""
from pathlib import Path
import csv,json,tempfile,subprocess,importlib.util,datetime,hashlib,sys,os
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
E=HERE.parent

def tab(p,header,data):
 with p.open('w',newline='') as f:w=csv.writer(f,delimiter='\t');w.writerow(header);w.writerows(data)
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 path=HERE/'audit_raw_attribution_v3.py';spec=importlib.util.spec_from_file_location('raw_v3',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 with tempfile.TemporaryDirectory() as td:
  p=Path(td);b='b/u_compute';plan=dict(normalization_base=b,driver_normalization='frozen first-four module oracle',representative_nets_per_group=16)
  (p/'plan.json').write_text(json.dumps(plan));(p/'native_route_status.rpt').write_text(' # of nets with resource conflicts : 26 :\n')
  tab(p/'cells.tsv',['name','REF_NAME','LOC','BEL','IS_PRIMITIVE'],[[b+'/a/d','FDRE','S0','A',1],[b+'/b/l','LUT1','S1','A',1],[b+'/a/e','FDRE','S0','B',1],[b+'/const/g','GND','','',1],[b+'/const/v','VCC','','',1],[b+'/unplaced/l','FDRE','','',1]])
  tab(p/'sites.tsv',['site','SLR','clock_region'],[['S0','SLR0','CR0'],['S1','SLR1','CR1']])
  names=['n'+str(i) for i in range(1,9)]+[f'nd{i:02}' for i in range(20)]
  tags={'n1':'FIXED','n5':'FIXED','n7':'META'}
  tab(p/'net_inventory.tsv',['canonical','aliases','conflict','seed_tags'],[[n,2 if n=='n1' else 1,int(n!='n5'),tags.get(n,'')] for n in names])
  tab(p/'aliases.tsv',['canonical','segment'],[[n,n] for n in names]+[['n1','n1_alias']])
  tab(p/'raw_conflicts.tsv',['native_net'],[[n] for n in names if n!='n5']+[['n1_alias']])
  ends=[]
  def ep(n,cell,pin,d,k=0):ends.append([n,'LEAF_PIN',cell+'/'+pin,d,pin,k,cell])
  ep('n1',b+'/a/d','Q','OUT');ep('n1',b+'/b/l','I0','IN');ep('n2',b+'/b/l','I0','IN')
  ep('n3',b+'/a/d','Q','OUT');ep('n3',b+'/a/e','Q','OUT');ep('n3',b+'/b/l','I0','IN');ep('n4',b+'/b/l','IO','INOUT');ep('n5',b+'/a/d','Q','OUT');ep('n5',b+'/b/l','I0','IN')
  ep('n6',b+'/const/g','G','OUT');ep('n6',b+'/b/l','CE','IN');ep('n7',b+'/const/v','P','OUT');ep('n7',b+'/unplaced/l','CLK','IN',1);ep('n8',b+'/a/d','Q','OUT')
  for n in names[8:]:ep(n,b+'/a/d','Q','OUT');ep(n,b+'/b/l','I0','IN')
  tab(p/'endpoints.tsv',['canonical','kind','name','DIRECTION','REF_PIN_NAME','IS_CLOCK','owner'],ends)
  subprocess.run(['/usr/bin/python3',str(E/'experiment_source/AT003_scalar_property_fix/aggregate.py'),'--out',str(p),'--plan',str(p/'plan.json')],check=True,capture_output=True,text=True)
  first=audit.run(p,plan)
  assert first['native_raw_conflict_objects']==28 and first['canonical_conflict_nets']==27 and first['primary_groups']==7 and first['unique_segments']==29
  assert first['top20_and_supplemental_overlap']==2 and first['top20_plus_supplemental_union']==27
  assert first['buckets']['UNKNOWN_DRIVER']==first['buckets']['MULTIDRIVER']==first['buckets']['INOUT_OR_AMBIGUOUS']==1
  assert first['native_type_incidence']=={'DATA_OR_UNCLASSIFIED':25,'CONSTANT':2,'CONTROL_SINK_NATIVE':1,'CLOCK_SINK_NATIVE':1}
  assert first['current_native_report_conflict_nets']==26 and first['canonical_minus_current_native_report']==1 and first['frozen_E008_conflict_nets']==547548
  assert first['deep_selected_unique']==23 and first['deep_exact_ID_tag_scope_verified'] and first['deep_tag_incidence']['TOP01']==16 and first['deep_tag_incidence']['FIXED']==2
  assert len(first['constant_cross'])==2 and all(row['unique_nets']==1 and row['source_SLR_unknown'] and not row['no_loads'] for row in first['constant_cross'])
  backups={name:(p/name).read_text() for name in ['failed_nets.tsv','aliases.tsv','net_inventory.tsv','endpoints.tsv','deep_selected.tsv']};negative={}
  def restore():
   for name,value in backups.items():(p/name).write_text(value)
  def rejected(name,expected):
   try:audit.run(p,plan)
   except AssertionError as ex:negative[name]=str(ex)
   else:raise AssertionError('negative fixture was accepted: '+name)
   assert negative[name]==expected,(name,negative[name]);restore()
  original=backups['failed_nets.tsv'];changed=original.replace('SLR0\tSLR1','SLR2\tSLR1',1);assert changed!=original;(p/'failed_nets.tsv').write_text(changed)
  rejected('incorrect_source_SLR','raw endpoint classifier disagrees with primary output')
  with (p/'aliases.tsv').open('a') as f:f.write('n2\tn1_alias\n')
  rejected('contradictory_alias_assignment','native segment maps to multiple canonical IDs')
  for name in ['net_inventory.tsv','aliases.tsv','endpoints.tsv','failed_nets.tsv']:
   with (p/name).open() as f:reader=csv.DictReader(f,delimiter='\t');header=reader.fieldnames;data=list(reader)
   for row in data:
    if row['canonical']=='n1':row['canonical']='zzz_noncanonical'
   tab(p/name,header,[[row[k] for k in header] for row in data])
  rejected('consistent_nonminimal_canonical_rename','canonical ID is not lexical minimum native segment')
  with (p/'deep_selected.tsv').open() as f:reader=csv.DictReader(f,delimiter='\t');header=reader.fieldnames;data=list(reader)
  for row in data:
   if row['canonical']=='n1':row['tags']=','.join(t for t in row['tags'].split(',') if t!='FIXED')
  tab(p/'deep_selected.tsv',header,[[row[k] for k in header] for row in data])
  rejected('missing_fixed_supplementary_tag','deep selected exact ID/tag scope mismatch')
  changed=backups['deep_selected.tsv'].replace('nd14\t','nd15\t',1);assert changed!=backups['deep_selected.tsv'];(p/'deep_selected.tsv').write_text(changed)
  rejected('wrong_lexical_sixteenth_representative','deep selected exact ID/tag scope mismatch')
  # Preserve counts/bucket/SLR while corrupting the native type label only.
  changed=backups['failed_nets.tsv'].replace('CONSTANT,CONTROL_SINK_NATIVE','DATA_OR_UNCLASSIFIED',1);assert changed!=backups['failed_nets.tsv'];(p/'failed_nets.tsv').write_text(changed)
  rejected('incorrect_native_type_label','raw native type classification mismatch')
  result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),producer=dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()),actual_exit_code=0,positive=dict(raw28_canonical27_groups7_segments29=True,union27_overlap2=True,unknown_multidriver_inout_each1=True,type_incidence=first['native_type_incidence'],constant_cross=first['constant_cross'],current_native_report26_baseline547548=True,deep_unique23_TOP01_lexical16_all_supp_ID_tags_verified=True),negative=negative,native_eda_executed=False,scope='Synthetic independent CPU audit only; actual AT003 reconstruction pending successful native closure')
  with (HERE/'audit_raw_attribution_v3_cpu_checks.json').open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result,indent=2))
if __name__=='__main__':main()
