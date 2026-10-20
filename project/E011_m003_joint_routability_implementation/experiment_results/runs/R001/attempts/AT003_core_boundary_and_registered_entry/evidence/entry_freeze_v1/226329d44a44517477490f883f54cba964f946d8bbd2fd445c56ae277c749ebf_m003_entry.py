#!/usr/bin/env python3
"""M003 immutable selected entry source binding and formal overlay policy checks."""
from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[4];HW=ROOT/'project/hardware'
MANIFEST=HW/'vivado/constraints/m003_entry_manifest.json'
G2='4424c426859b6b1e64be2f52a008ff6c03e1a6854f71570970cbba4941fff709'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_sources(manifest=MANIFEST):
 x=json.loads(manifest.read_text())
 if x.get('G2_sha256')!=G2 or sha(ROOT/'mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md')!=G2:raise ValueError('G2 source binding mismatch')
 if len(x['sources'])!=len({e['path'] for e in x['sources']}):raise ValueError('duplicate source binding')
 required=['m003_joint_locality.xdc','m003_joint_locality_data.tcl','m003_joint_locality_spec.json','m003_joint_checks.tcl','m003_joint_evidence.py','m003_entry.py','m003_resource_budget.py','create_vcu118_board.tcl','build_vcu118_board.tcl','m002_physical.tcl','m002_diagnostic_common.tcl']
 if not set(required)<={Path(e['path']).name for e in x['sources']}:raise ValueError('incomplete selected entry source set')
 for e in x['sources']:
  p=Path(e['path'])
  if not p.is_relative_to(HW) or not p.is_file() or sha(p)!=e['sha256']:raise ValueError('selected source identity changed: '+str(p))
 return x

def check_registration(rows):
 rows=[r for r in rows if r.get('NAME','').endswith('/m003_joint_locality.xdc')]
 if len(rows)!=1:raise ValueError('M003 overlay absent/duplicate registration')
 r=rows[0]
 if str(r.get('USED_IN_SYNTHESIS','')).lower() not in ('0','false') or str(r.get('USED_IN_IMPLEMENTATION','')).lower() not in ('1','true') or r.get('PROCESSING_ORDER')!='LATE' or str(r.get('IS_ENABLED','')).lower() not in ('1','true') or r.get('SCOPED_TO_REF')!='' or r.get('SCOPED_TO_CELLS')!='':raise ValueError('M003 overlay global/implementation-only/LATE policy changed')
 return True

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['check-sources','list-sources','check-runtime','freeze']);p.add_argument('--output',type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
 if a.command=='freeze':
  if MANIFEST.exists():raise ValueError('entry manifest already frozen; preserve prior before revision')
  paths=[p for p in (HW/'vivado/constraints').glob('m003_*') if p!=MANIFEST]
  paths+=list((HW/'vivado/scripts').glob('m003_*'))
  paths+=[HW/'vivado/scripts'/'run_m003_owned.py',HW/'vivado/scripts'/'run_m003_stage.py']
  paths+=[HW/'vivado/scripts'/n for n in ['m003_joint_checks.tcl','m003_joint_evidence.py','m003_entry.py','m003_resource_budget.py','create_vcu118_board.tcl','build_vcu118_board.tcl','m002_physical.tcl','m002_diagnostic_common.tcl']]
  paths+=[HW/'rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv',HW/'rtl/attention/hap_weight_meta_resident.sv',HW/'rtl/attention/hap_attention_board_cohort16_core.sv']
  x=dict(G2_sha256=G2,sources=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(set(paths))]);MANIFEST.write_text(json.dumps(x,indent=2)+'\n')
 else:x=check_sources()
 if a.command=='check-runtime':
  r=json.loads((a.report/'m003_candidate_registration.json').read_text());check_registration([r])
  if r['source_manifest_sha256']!=sha(MANIFEST) or r['overlay_sha256']!=sha(HW/'vivado/constraints/m003_joint_locality.xdc'):raise ValueError('runtime candidate/source registration identity mismatch')
 if a.command=='list-sources':
  print('\n'.join(e['path'] for e in x['sources'])+'\n'+str(MANIFEST));return
 print(json.dumps(dict(passed=True,sources=len(x['sources']),manifest_sha256=sha(MANIFEST))))
if __name__=='__main__':main()
