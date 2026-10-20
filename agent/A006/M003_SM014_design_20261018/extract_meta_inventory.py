#!/usr/bin/env python3
"""Targeted scan of existing light inventory for metadata URAM and two controls."""
import sys
sys.dont_write_bytecode=True
import csv,collections,datetime,json,os,hashlib
from pathlib import Path
import extract_field_evidence as p

def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 target=p.HERE/'F4_full_metadata_inventory.json';assert not target.exists()
 scope=p.META+'/u_meta/';critical_names={p.TOP01+'/clear_kernel_row_r_reg[0]','scalellm_vcu118_f05_bd_i/core/inst/u_core/u_paired_weight/maintenance_soft_clear_pulse_r_reg'}
 found=[];control=[]
 for r in p.rows(p.NATIVE/'cells.tsv'):
  if r['name'].startswith(scope) and r['REF_NAME'].startswith('URAM'):found.append(r)
  if r['name'] in critical_names:control.append(r)
 sites={r['LOC'] for r in found+control};site_rows={}
 for r in p.rows(p.NATIVE/'sites.tsv'):
  if r['site'] in sites:site_rows[r['site']]=r
 detailed={r['name']:r for r in json.loads((p.HERE/'F4_metadata_URAM_objects.json').read_text())}
 result=[]
 for r in found:
  d=detailed.get(r['name']);result.append(dict(**r,site_native_relationship=site_rows.get(r['LOC'],{'SLR':'NOT_MEASURED','clock_region':'NOT_MEASURED'}),detailed_native_properties=d if d else 'NOT_EXPORTED_IN_FIXED_DEEP_SCOPE',logical_bit_lane='NOT_MEASURED',CASCADE_ORDER_SELF_ADDR_properties='NOT_MEASURED',cascade_links='NOT_MEASURED'))
 x=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Targeted existing light cells/sites inventory scan only, not full conflict re-audit; no EDA',metadata_URAM_count=len(found),REF_NAME_counts=dict(collections.Counter(r['REF_NAME'] for r in found)),SLR_counts=dict(collections.Counter(site_rows[r['LOC']]['SLR'] for r in found)),clock_region_counts=dict(collections.Counter(site_rows[r['LOC']]['clock_region'] for r in found)),native_URAM_LOCs=[r['LOC'] for r in found],direct_address_consumer_URAM_with_deep_properties=len(detailed),logical_width_depth_and_cascade_qualification='NOT_MEASURED_FROM_FROZEN_FIELDS; RTL capacity81920x256 and physical80 URAM alone do not identify logical lane/cascade segmentation',objects=result,critical_control_sources=[dict(cell=r,site_native_relationship=site_rows.get(r['LOC'],{})) for r in control],critical_sources_not_found=sorted(critical_names-{r['name'] for r in control}),verified_input_files=p.VERIFIED,producer=p.ident(Path(__file__)))
 with target.open('x') as f:f.write(json.dumps(x,indent=2)+'\n')
 print(json.dumps({k:v for k,v in x.items() if k not in ['objects','native_URAM_LOCs']},indent=2),flush=True)
if __name__=='__main__':main()
