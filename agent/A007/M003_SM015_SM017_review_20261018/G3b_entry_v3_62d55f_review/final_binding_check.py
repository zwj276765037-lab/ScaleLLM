from pathlib import Path
import json,hashlib,datetime,subprocess,re,collections,ast
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');D=Path(__file__).parent;O=D.parent;E=R/'project/E011_m003_joint_routability_implementation/experiment_source'
def ident(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(x):
 a=ident(x['path']);assert a['sha256']==x['sha256'] and a['bytes']==x['bytes'];return a
p=E/'G3b_delivery_v3.json';delivery=json.loads(p.read_text());bound={k:check(delivery[k]) for k in ['entry_manifest','previous_entry_manifest','selected_baseline_audit','same_version_joint_regression','protocol']};assert bound['entry_manifest']['sha256']=='62d55ff983e6d8062d448e2ac0e5c690d092b4eead0d8512e56a255c3dbfa96c'
m=json.loads(Path(bound['entry_manifest']['path']).read_text());frozen={x['path']:x for x in m['sources']};assert len(frozen)==41
for x in m['sources']:check(x);assert ident(D/'sources'/Path(x['path']).name)['sha256']==x['sha256']
rp=Path(bound['same_version_joint_regression']['path']);r=json.loads(rp.read_text());assert r['exit_code']==0 and r['source_unchanged'] is True and r['native_EDA'] is False
bindings=[]
for x in r['source_bindings']:
 a=ident(x['path']);b=ident(x['preserved']);assert a['sha256']==b['sha256']==x['sha256'];bindings.append({'current':a,'preserved':b})
assert len(bindings)==69 and set(frozen)<={x['current']['path'] for x in bindings}
log=(rp.parent/'native.log').read_text();tests=re.findall(r'^(.+?) \(([^)]+)\) \.\.\. ok$',log,re.M);assert len(tests)==288 and re.search(r'Ran 288 tests in .*s\n\nOK',log);classes=collections.Counter(x[1].rsplit('.',1)[0] for x in tests);assert sum(v for k,v in classes.items() if 'test_m003_joint_qualification' in k)==42
base={x['path']:x for x in json.loads((R/'agent/A006/M003_SM014_design_20261018/design_input_identities.json').read_text())['production_inputs']};audit=json.loads(Path(bound['selected_baseline_audit']['path']).read_text());assert audit['baseline_entries']==144 and audit['unchanged']==137 and len(audit['changed'])==7 and not audit['unplanned_changes'];diffchecks=[]
for change in audit['changed']:
 assert change['before_sha256']==base[change['path']]['sha256'] and change['after_sha256']==frozen[change['path']]['sha256']
 if '/scripts/' not in change['path']:continue
 name=Path(change['path']).name;old=E/'prechange_entry'/name;assert ident(old)['sha256']==change['before_sha256'];new=D/'sources'/name;record=E/(name+'.v3.diff');diff=subprocess.run(['diff','-u',str(old),str(new)],capture_output=True,text=True);assert diff.returncode==1 and diff.stdout.splitlines()[2:]==record.read_text().splitlines()[2:];diffchecks.append({'original':ident(old),'frozen_new':ident(new),'actual_diff_record':ident(record)})
# Four v2->v3 files changed; complete shared safety body still preserved except adapter/probe additions.
v2=json.loads((O/'G3b_entry_v2_cb7256_review/m003_entry_manifest.json').read_text());v2map={x['path']:x for x in v2['sources']};changed=sorted(Path(k).name for k in frozen if frozen[k]!=v2map[k]);assert changed==['m002_diagnostic_common.tcl','m003_physical_evidence.py','m003_stage.py','run_m003_stage.py']
def function(p,name):return next(x for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef) and x.name==name)
oldfun=ast.unparse(function(O/'G3b_entry_v2_cb7256_review/sources/m003_physical_evidence.py','hook_batch'));newfun=ast.unparse(function(D/'sources/m003_physical_evidence.py','hook_batch'));newfun=newfun.replace('    native_probe = selected.verify_probe(report, point)\n','').replace(", 'native_probe': native_probe",'');assert oldfun==newfun
record={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution':'completed','passed':True,'delivery':ident(p),'delivery_bindings':bound,'source_count':41,'frozen_source_total_bytes':sum(x['bytes'] for x in m['sources']),'source_identities':m['sources'],'final_regression_raw_log':ident(rp.parent/'native.log'),'final_regression_tests':288,'qualification_tests_included':42,'test_class_counts':dict(classes),'archive_bindings_verified':bindings,'baseline_audit_limit':'Engineering actual144/137 same independently bounded to7 changed records and4 source reconstructions/diffs; not duplicate full144 rescan','entry_original_provenance':'Engineering inverse patch reconstruction matched exact SM014 baseline hashes','four_entry_diffs':diffchecks,'v2_v3_changed_files':changed,'v3_hook_body_only_adds_native_probe_verification_and_receipt':True,'independent_42_tests_receipt':ident(D/'independent_test_receipt.json'),'independent_42_tests_log':ident(D/'independent_42_tests.log'),'Tcl_data_projection_review_reused':ident(O/'G3b_entry_v2_cb7256_review/data_projection_review.json'),'native_EDA':False}
p=D/'final_binding_check.json';p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'review':ident(p),'source_count':41,'bindings':69,'tests':288,'independent_tests':42,'changed_files':changed}))
