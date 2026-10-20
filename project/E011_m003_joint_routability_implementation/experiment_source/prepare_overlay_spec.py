#!/usr/bin/env python3
"""Translate frozen bit/site sets to a production data source; no EDA."""
import sys
sys.dont_write_bytecode=True
import collections,csv,datetime,hashlib,json,os
from pathlib import Path
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');HW=ROOT/'project/hardware';HERE=Path(__file__).resolve().parent
DESIGN=ROOT/'agent/A006/M003_SM014_design_20261018'
sys.path.insert(0,str(DESIGN))
import extract_field_evidence as old
def ident(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def q(s):
 s=str(s);assert not any(c in s for c in '{}\n\r');return '{'+s+'}'
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 data=HW/'vivado/constraints/m003_joint_locality_data.tcl';spec=HW/'vivado/constraints/m003_joint_locality_spec.json'
 assert not data.exists() and not spec.exists()
 source=json.loads((DESIGN/'F1_F3_C_M2_region_groups.json').read_text())
 pools=json.loads((DESIGN/'F4_C_A3_resource_pool_inventory.json').read_text())['pools']
 indices=collections.Counter();groups=[]
 for a in source['groups']:
  fam=a['family'];i=indices[fam];indices[fam]+=1
  groups.append(dict(id=a['id'],family=fam,index=i,clock_region=a['clock_region'],SLR=a['SLR'],bits=a['bits'],width=a['width']))
 c01=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation/candidate_physical_members_route_failed.tsv'
 assert ident(c01)['sha256']=='66791ed1b4ae12c94923b4372e897559a5f7e96c59dea8b401e05b2d2b13b00c'
 with c01.open() as f:protected=[r['NAME'] for r in csv.DictReader(f,delimiter='\t') if r['DONT_TOUCH'].lower() in ('1','true')]
 assert len(protected)==25
 refcounts={'meta':collections.Counter(),'shared':collections.Counter(),'whole':collections.Counter()}
 for r in old.rows(old.NATIVE/'cells.tsv'):
  ref=r['REF_NAME'];refcounts['whole'][ref]+=1
  if r['name'].startswith(old.META+'/u_meta/'):refcounts['meta'][ref]+=1
  if r['name'].startswith(old.SHARED+'/'):refcounts['shared'][ref]+=1
 rtl=[HW/'rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv',HW/'rtl/attention/hap_weight_meta_resident.sv',HW/'rtl/attention/hap_attention_board_cohort16_core.sv']
 x=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),G2_sha256='4424c426859b6b1e64be2f52a008ff6c03e1a6854f71570970cbba4941fff709',design_manifest_sha256='6d74e85db325a939c8b1ffbd637de6dbd35e2016188bdd0050d62cc5a2b9706b',group_map_sha256='75abfae1d81cb75d13a8543a63f4f79ef1c70e25fee08d19d77a2c0f1627ad0f',base=old.BASE,parent_scope=old.SHARED,meta_scope=old.META+'/u_meta',core_meta_scope=old.META,C01_root=old.C01,groups=groups,regions=source['region_costs'],meta_pools=[dict(index=a['slice'],bits=a['bits'],URAM_sites=a['URAM_sites'],CLB_sites=a['local_CLB_sites'],URAM_CR_counts=a['URAM_native_clock_regions'],CLB_clock_regions=a['local_CLB_clock_regions']) for a in pools],C01_protected_names=protected,baseline_refs={k:dict(v) for k,v in refcounts.items()},baseline_stage='E009 failed route lightweight inventory; per-role native primitive counts, not same-stage performance comparison',baseline_inventory_identity=old.VERIFIED['cells.tsv'],source_RTL=[ident(p) for p in rtl],budgets=dict(M2_LUT1=81,new_address_FF=34,A3_LUT_delta_max=96,A3_CARRY8_delta_max=8,A3_FF_delta_max=34,joint_LUT_delta_max=177,joint_FF_delta_max=34,URAM_total=80,URAM_per_slice=40))
 spec.write_text(json.dumps(x,indent=2)+'\n')
 lines=['# Generated exactly from frozen G2 role/bit/native-site sets. No runtime query here.','namespace eval m003 {',f'    variable spec_path {q(str(spec))}',f'    variable parent_scope {q(old.SHARED)}',f'    variable meta_scope {q(old.META+"/u_meta")}',f'    variable core_meta_scope {q(old.META)}',f'    variable c01_root {q(old.C01)}','    variable groups [list \\']
 for a in groups:
  fields=' '.join(q(k)+' '+(q(' '.join(map(str,v))) if isinstance(v,list) else q(v)) for k,v in a.items())
  lines.append('        [dict create '+fields+'] \\')
 lines+=['    ]','    variable regions [dict create \\']
 for a in source['region_costs']:lines.append(f'        {q(a["clock_region"])} {a["native_CLB_site_count"]} \\')
 lines+=['    ]','    variable meta_pools [list \\']
 for a in x['meta_pools']:
  lines.append('        [dict create index '+str(a['index'])+' uram_sites '+q(' '.join(a['URAM_sites']))+' clb_sites '+q(' '.join(a['CLB_sites']))+'] \\')
 lines+=['    ]','    variable c01_protected '+q(' '.join(protected)),'}']
 data.write_text('\n'.join(lines)+'\n')
 out=HERE/'overlay_spec_prepared.json';out.write_text(json.dumps(dict(spec=ident(spec),Tcl_data=ident(data),producer=ident(Path(__file__)),native_inventory=old.VERIFIED,groups=len(groups),URAM_sites=80,CLB_sites=6960,C01_protected=len(protected)),indent=2)+'\n')
 print(json.dumps(dict(groups=len(groups),URAM_sites=80,CLB_sites=6960,C01_protected=len(protected),baseline_meta_refs=dict(refcounts['meta']),spec=ident(spec),Tcl=ident(data)),indent=2))
if __name__=='__main__':main()
