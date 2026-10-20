#!/usr/bin/env python3
"""M003 immutable selected entry source binding and formal overlay policy checks."""
from pathlib import Path
import argparse,ast,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[4];HW=ROOT/'project/hardware'
MANIFEST=HW/'vivado/constraints/m003_entry_manifest.json'
G2='4424c426859b6b1e64be2f52a008ff6c03e1a6854f71570970cbba4941fff709'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def local_import_closure(paths):
 paths=set(paths);pending=list(paths)
 while pending:
  p=pending.pop()
  if p.suffix!='.py':continue
  tree=ast.parse(p.read_text(),str(p))
  for node in ast.walk(tree):
   names=[]
   if isinstance(node,ast.Import):names=[a.name.split('.')[0] for a in node.names]
   if isinstance(node,ast.ImportFrom):names=([node.module.split('.')[0]] if node.module else [a.name for a in node.names])
   for name in names:
    q=p.parent/(name+'.py')
    if q.is_file() and q not in paths:paths.add(q);pending.append(q)
 return paths
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
 if str(r.get('USED_IN_SYNTHESIS','')).lower() not in ('0','false') or str(r.get('USED_IN_IMPLEMENTATION','')).lower() not in ('1','true') or r.get('PROCESSING_ORDER')!='LATE' or str(r.get('IS_ENABLED','')).lower() not in ('1','true') or r.get('SCOPED_TO_REF')!='' or r.get('SCOPED_TO_CELLS')!='' or r.get('FILE_TYPE')!='TCL':raise ValueError('M003 overlay global/implementation-only/LATE/TCL policy changed')
 return True

def check_apply(report):
 records=sorted(report.glob('m003_apply_success_*.json'))
 if not records:raise ValueError('M003 no actual native overlay apply success receipt')
 seen=set()
 for path in records:
  row=json.loads(path.read_text());key=(int(row.get('pid',0)),int(row.get('attempt',0)))
  if row.get('kind')!='native' or str(row.get('success')).lower()!='true' or min(key)<=0 or key in seen or row.get('source_manifest_sha256')!=sha(MANIFEST) or row.get('overlay_sha256')!=sha(HW/'vivado/constraints/m003_joint_locality.xdc'):raise ValueError('M003 actual apply source/attempt binding mismatch')
  seen.add(key)
 return dict(passed=True,actual_native_apply_count=len(records),receipts=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in records])

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['check-sources','list-sources','check-runtime','check-apply','freeze']);p.add_argument('--output',type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
 if a.command=='freeze':
  if MANIFEST.exists():raise ValueError('entry manifest already frozen; preserve prior before revision')
  paths=[p for p in (HW/'vivado/constraints').glob('m003_*') if p!=MANIFEST]
  paths+=list((HW/'vivado/scripts').glob('m003_*'))
  paths+=[HW/'vivado/scripts'/'run_m003_owned.py',HW/'vivado/scripts'/'run_m003_stage.py']
  paths+=[HW/'vivado/scripts'/n for n in ['m003_joint_checks.tcl','m003_joint_evidence.py','m003_entry.py','m003_resource_budget.py','create_vcu118_board.tcl','build_vcu118_board.tcl','m002_physical.tcl','m002_diagnostic_common.tcl']]
  paths+=[HW/'rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv',HW/'rtl/attention/hap_weight_meta_resident.sv',HW/'rtl/attention/hap_attention_board_cohort16_core.sv']
  paths+=list((HW/'vivado/scripts').glob('m002_*.tcl'))
  paths+=[HW/'vivado/scripts'/n for n in ['run_managed_eda.py','run_vcu118_board.sh','emit_current_board_evidence.py','m002_physical_evidence.py','mission0004_metadata_physical.tcl','mission0005_coordinated_physical.tcl']]
  paths=local_import_closure(paths)
  x=dict(G2_sha256=G2,sources=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(set(paths))]);MANIFEST.write_text(json.dumps(x,indent=2)+'\n')
 else:x=check_sources()
 if a.command=='check-apply':print(json.dumps(check_apply(a.report)));return
 if a.command=='check-runtime':
  r=json.loads((a.report/'m003_candidate_registration.json').read_text());check_registration([r])
  if r['source_manifest_sha256']!=sha(MANIFEST) or r['overlay_sha256']!=sha(HW/'vivado/constraints/m003_joint_locality.xdc'):raise ValueError('runtime candidate/source registration identity mismatch')
 if a.command=='list-sources':
  print('\n'.join(e['path'] for e in x['sources'])+'\n'+str(MANIFEST));return
 print(json.dumps(dict(passed=True,sources=len(x['sources']),manifest_sha256=sha(MANIFEST))))
if __name__=='__main__':main()
