from pathlib import Path
import json,hashlib,datetime,subprocess,ast,re,collections
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');D=Path(__file__).parent;E=R/'project/E011_m003_joint_routability_implementation/experiment_source';A=R/'agent/A006/M003_SM014_design_20261018/design_input_identities.json';B=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R001/attempts/AT003_core_boundary_and_registered_entry/evidence/joint_python_regression_closed_sources_v2'
def identity(p):
 p=Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
m=json.loads((D/'m003_entry_manifest.json').read_text());assert identity(D/'m003_entry_manifest.json')['sha256']=='cb7256c76ad5b5587a9f8384140c9f17d62c31181276b855cd908f11f11a955d';frozen={x['path']:x for x in m['sources']}
r=json.loads((B/'receipt.json').read_text());assert identity(B/'receipt.json')['sha256']=='928c7ccea630e80d547339d1540285d3ef9e8908bbecc4767788e797c81aa4d5';assert r['exit_code']==0 and r['source_unchanged'] is True and r['native_EDA'] is False
bindings=[]
for x in r['source_bindings']:
 a=identity(x['preserved']);assert a['sha256']==x['sha256'];bindings.append({'original_path':x['path'],'preserved':a})
 if x['path'] in frozen:assert x['sha256']==frozen[x['path']]['sha256']
assert len(bindings)==69 and set(frozen)<={x['original_path'] for x in bindings}
log=(B/'native.log').read_text();tests=re.findall(r'^(.+?) \(([^)]+)\) \.\.\. ok$',log,re.M);assert len(tests)==282 and 'Ran 282 tests in 33.471s\n\nOK' in log
classes=collections.Counter(x[1].rsplit('.',1)[0] for x in tests);nqual=sum(v for k,v in classes.items() if 'test_m003_joint_qualification' in k);assert nqual==36
base={x['path']:x for x in json.loads(A.read_text())['production_inputs']};audit=json.loads((E/'selected_input_audit_before_create.json').read_text());assert audit['baseline_entries']==144 and audit['unchanged']==137 and len(audit['changed'])==7 and not audit['unplanned_changes'];diffchecks=[]
for change in audit['changed']:
 assert change['before_sha256']==base[change['path']]['sha256'];assert change['after_sha256']==frozen[change['path']]['sha256']
 if '/scripts/' not in change['path']:continue
 name=Path(change['path']).name;old=E/'prechange_entry'/name;assert identity(old)['sha256']==change['before_sha256'];new=D/'sources'/name;assert identity(new)['sha256']==change['after_sha256'];record=E/(name+'.final.diff');diff=subprocess.run(['diff','-u',str(old),str(new)],capture_output=True,text=True);assert diff.returncode==1
 # Compare exact diff body independent of reviewer archive path header.
 expected='\n'.join(record.read_text().splitlines()[2:]);actual='\n'.join(diff.stdout.splitlines()[2:]);assert expected==actual
 diffchecks.append({'original':identity(old),'current_frozen':identity(new),'recorded_final_diff':identity(record),'actual_diff_body_exact':True})
assert len(diffchecks)==4
local_py={p.stem:p for p in (R/'project/hardware/vivado/scripts').glob('*.py')};missing=[]
for row in m['sources']:
 p=Path(row['path']);f=D/'sources'/p.name
 if p.suffix!='.py':continue
 for node in ast.walk(ast.parse(f.read_text())):
  names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else ([node.module.split('.')[0]] if node.module else [a.name for a in node.names]) if isinstance(node,ast.ImportFrom) else []
  for name in names:
   if name in local_py and str(local_py[name]) not in frozen:missing.append((p.name,name))
assert not missing
result={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'completed_bounded_subscope','verdict':'v2_regression_and_source_closure_and_four_entry_diff_verified','entry_manifest':identity(D/'m003_entry_manifest.json'),'sources':41,'regression_receipt':identity(B/'receipt.json'),'raw_log':identity(B/'native.log'),'actual_passing_tests':282,'M003_checks_included':36,'test_class_counts':dict(classes),'verified_archived_bindings':bindings,'baseline_audit':identity(E/'selected_input_audit_before_create.json'),'baseline_statement':'Engineering actual144 audit137unchanged; reviewer independently checked all7 changed identities and four old-source reconstruction/diff bodies. No independent full144 reread.','four_entry_diffs':diffchecks,'old_source_reconstruction_provenance':'Four original entry files reconstructed by engineering inverse patch and hash-equal to frozen SM014; do not label as pre-edit archival copies.','local_python_import_closure_missing':missing,'G3b_overall_no_blocker':False,'pending':'A006 identified missing probe_targets.tcl generation in qualify adapter; v3 in preparation. No native/source design change or G3a regression invalidation.'}
p=D/'regression_and_entry_review.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'review':identity(p),'tests':282,'bindings':69,'entry_diffs':4,'missing_imports':missing}))
