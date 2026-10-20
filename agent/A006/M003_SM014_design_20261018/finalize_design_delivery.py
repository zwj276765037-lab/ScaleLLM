#!/usr/bin/env python3
"""Freeze engineering proposal identities and observe this offline process resources."""
import collections,datetime,fcntl,hashlib,json,os,re,resource,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'.research-agent/project.json').is_file())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity(p):return {'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(name,x):
 p=HERE/name;assert not p.exists();p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 start=now();pid=os.getpid();stat=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split();start_ticks=int(stat[19])
 assert sorted(os.sched_getaffinity(0))==list(range(8)) and os.getpriority(os.PRIO_PROCESS,0)==5
 baseline=ROOT/'project/E009_m003_failed_net_attribution/experiment_source/AT003_scalar_property_fix/baseline.json'
 prod=json.loads(baseline.read_text())['production_inputs'];checked=[]
 for expected in prod:
  p=Path(expected['path']);actual=identity(p)
  assert all(actual[k]==expected[k] for k in ('path','bytes','sha256')),('production input changed',str(p))
  checked.append(actual)
 assert len(checked)==144
 # Reconstruct mapping under observed CPU/nice and compare exact persisted bit partitions.
 old=json.loads((HERE/'F4_parent_meta_register_objects.json').read_text());new=json.loads((HERE/'F1_F3_C_M2_region_groups.json').read_text())
 reference={}
 for fam in ('head','tail'):
  buckets=collections.defaultdict(list)
  for r in old:
   if r['family']==fam:buckets[(r['endpoint_physical']['SLR'],r['endpoint_physical']['clock_region'])].append(r['bit'])
  for (slr,cr),bits in buckets.items():
   for start in range(0,len(bits),256):reference[f'{fam}_{cr}_{start//256:02d}']=(slr,cr,sorted(bits)[start:start+256])
 assert len(reference)==81
 for g in new['groups']:assert reference.pop(g['id'])==(g['SLR'],g['clock_region'],g['bits'])
 assert not reference
 links=[]
 for md in HERE.glob('*.md'):
  for link in re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)',md.read_text()):
   if '://' not in link:
    p=(md.parent/link).resolve();assert p.exists(),('broken link',str(md),link);links.append(str(p))
 lock=ROOT/'project/hardware/vivado/.m002_eda.lock'
 with lock.open('r') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);lock_free=True;fcntl.flock(f,fcntl.LOCK_UN)
 inputs={'observed_utc':now(),'production_inputs_verified_unchanged':144,'baseline_identity':identity(baseline),'production_inputs':checked,'existing_native_extraction_manifests':[identity(HERE/n) for n in ('F1_extraction_summary.json','F4_full_metadata_inventory.json','F4_C_A3_resource_pool_inventory.json')],'applicability':'SM014 engineering design inputs; no future synthesis/implementation input identity claimed'}
 save('design_input_identities.json',inputs)
 receipt={'observed_utc':now(),'started_utc':start,'pid':pid,'pid_start_ticks':start_ticks,'affinity_observed':sorted(os.sched_getaffinity(0)),'nice_observed':os.getpriority(os.PRIO_PROCESS,0),'max_threads':1,'ru_maxrss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'disk_free_bytes':shutil.disk_usage(ROOT).free,'sole_EDA_lock_observed_free_then_released':lock_free,'production_inputs_current_equals_E009_baseline':144,'M2_group_mapping_independently_reconstructed':81,'local_markdown_links_verified':len(links),'no_EDA_loaded':True,'no_production_write':True,'historical_receipt_boundary':'This is actual observation for this final verification process. Earlier tiny map-building helpers did not retain live affinity/PID receipts; their output is recomputed here, no retrospective affinity is invented. Extraction/proof scripts set affinity/nice in their executed source and returned exit0.'}
 save('finalization_cpu_receipt.json',receipt)
 excluded={'design_delivery_manifest.json','delivery_execution_receipt.json','delivery_console.json','delivery_completion.json'}
 files=[identity(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in excluded]
 manifest={'created_utc':now(),'execution_state':'engineering_design_package_completed','verdict':'PROPOSED_M2_A3_C_P1_ROOT_NOT_SELECTED','G2_approved':False,'production_changed':False,'new_EDA':False,'owner':'A006 /root/m002_build_verify','authoritative_design':['engineering_recommendations_one_page.md','F1_fields_drivers_and_consumers.md','F2_state_sampling_and_assertions.md','F3_complete_costs_and_budgets.md','F4_C_M2_region_distribution_rules.md','F4_C_A3_two_slice_resource_rules.md','integration_files_tests_and_freeze_plan.md','F1_F3_C_M2_region_groups.json'],'prototype_not_selected':['F1_F3_C_M2_exact_groups.json','build_M2_groups.py'],'known_boundaries':['G1 report-vs-canonical difference22049 remains OPEN','tail D/meta D-CE/all C physical fields absent in old fixed scope','New graph cascade/RDW/compatibility/actual objects belong SM017 G4','Structure and design-equation checks do not prove RTL simulation or timing/routing success'],'files':files}
 save('design_delivery_manifest.json',manifest)
 print(json.dumps({'manifest':identity(HERE/'design_delivery_manifest.json'),'CPU_receipt':identity(HERE/'finalization_cpu_receipt.json'),'files':len(files),'production_inputs_unchanged':144,'exact_M2_groups_recomputed':81,'execution':'completed; script final instruction reached'},indent=2))
if __name__=='__main__':main()
