from pathlib import Path
import json,hashlib,datetime,difflib
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018';B=R/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/original_address_selector_v1'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<4*1024*1024;b=p.read_bytes();return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(x):
 a=ident(x['path']);assert a['bytes']==x['bytes'] and a['sha256']==x['sha256'],x['path'];return a
package=B/'selector_delivery.json';d=json.loads(package.read_text());assert ident(package)['sha256']=='8329dd25930eb66dff9353697d6848a9f8cd6d8b7881b62f50b5fe03d9b00406'
verified={}
def walk(o,key):
 if isinstance(o,dict):
  if all(x in o for x in ['path','bytes','sha256']):verified[key]=check(o)
  else:
   for k,v in o.items():walk(v,key+'/'+k)
 elif isinstance(o,list):
  for i,v in enumerate(o):walk(v,key+'/'+str(i))
walk(d,'delivery')
cpu=json.loads(Path(d['CPU_receipt']['path']).read_text());walk(cpu,'CPU')
extra=B/'proposed_production_regression_receipt.json';assert ident(extra)['sha256']=='88fd2faf992c1feaa2ae6507ff3f86be74bc174dd263825918383aaa1d4acccf';walk(json.loads(extra.read_text()),'proposed3')
failed=B/'cpu_actual_native_handles_receipt.json';f=json.loads(failed.read_text())
historical=f.pop('test_sources')
preserved=ident(B/'test_selector_before_singleton_collection_fixture_refresh.py')
assert preserved['bytes']==historical['bytes'] and preserved['sha256']==historical['sha256']
walk(f,'retained_failure');verified['retained_failure/historical_test_source_preserved_copy']=preserved
old=Path(d['production_before']['path']).read_text();new=Path(d['candidate']['path']).read_text();lo=old.index('proc m003::resolve');hi=old.index('# Per-object support reused',lo);delta=Path(d['exact_candidate_function_delta']['path']).read_text()
assert old[:lo]+delta+old[hi:]==new
assert ''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=d['production_before']['path'],tofile=d['candidate']['path']))==Path(d['production_source_delta']['path']).read_text()
a=(B/'test_selector_before_native_handle_fixture_refresh.py').read_text();mid=(B/'test_selector_before_singleton_collection_fixture_refresh.py').read_text();now=(B/'test_selector.py').read_text()
a=a.replace('def table(rows):','def table(rows,native_handles=False):').replace("id='obj'+str(i);","id=row['NAME'] if native_handles else 'obj'+str(i);").replace("lines.append('dict set pool '+id+' [dict create ","lines.append('dict set pool {'+id+'} [dict create ").replace('text,ids=table(rows);code=','text,ids=table(rows,native_handles=True);code=')
assert a==mid
old_api='proc get_property {args} {return [dict get $::pool [lindex $args end] [lindex $args end-1]]}'
new_api='proc get_property {args} {set object [lindex $args end];if {![dict exists $::pool $object] && [llength $object]==1} {set object [lindex $object 0]};return [dict get $::pool $object [lindex $args end-1]]}'
assert mid.replace(old_api,new_api)==now
ours=json.loads((O/'original_address_selector_independent_cpu_receipt.json').read_text());assert ours['all_passed'] and ours['existing_production_regression_AST_unchanged']
manifest=R/'project/hardware/vivado/constraints/m003_entry_manifest.json';assert ident(manifest)['sha256']=='8b6fbe902e3d7287b75b3aa56bdbaf1fc43f92fd12aed5ec2551978568bc6ac5'
review={'schema':'A007_M003_strict_original_address_selector_candidate_review_v1','reviewer':'A007','reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_blocker':True,'package_sha256':ident(package)['sha256'],'candidate_sha256':d['candidate']['sha256'],'proposed_regression_sha256':d['proposed_regression']['sha256'],
'execution':{'review':'completed','production_apply':'not yet done','independent_CPU':'6 engineering selector reruns +6 independent candidate tests +3 proposed production tests all passed','engineering_combined_replay':'7-test receipt/source/retained failure audited; full AT014 tables not redundantly rescanned by reviewer'},
'verdict':{'source_candidate':'accepted for exact ordinary entry repair','native_selected_graph':'not qualified','method_efficacy':'unassessed','G4':False,'place_admission':False},
'applicability':{'production_before':d['production_before'],'current_manifest':ident(manifest),'candidate':d['candidate'],'proposed_regression':d['proposed_regression'],'AT016_native_facts_review':d['native_facts_independent_review']},
'review':{
'exact_source_delta':'Verified byte-exact reconstruction: insert only original_address_members and replace old original-address block with its call; all other checks/payload/property/pools/apply/snapshot behavior unchanged. Source diff matches actual full candidates.',
'selector_behavior':['Preserves broad primitive candidate query; detects duplicate returned object IDs and requires exact scope.','Only two measured exact relative CARRY8 names with CARRY8 ref may be excluded; no blanket non-FF skip and unknown neighbors reject.','Direct canonical decimal state bit0..16, unique bits, approved FF ref family and exact17 coverage required.','Malformed/nested/replicated/foreign/wrong-ref/missing/duplicate cases reject; measured nonstate objects may be absent without weakening state coverage.'],
'FF_ref_boundary':'FDRE/FDCE/FDSE/FDPE are accepted as state-role primitive classes, not asserted functionally equivalent. Actual AT016 state primitives are all FDCE; reset/polarity/graph checks remain required downstream.',
'production_tests':'Three methods added in new OriginalAddressSelection class; entire prior module AST unchanged after removing that class. New methods independently executed against byte-identical isolated candidate Tcl.',
'engineering_fixture_history':'Retained6-pass/1-fail raw receipt51a07b3a and log checked. Historical receipt test_sources path names the then-current fixture; its bytes/hash exactly match preserved before_singleton copy, not present repaired file. Native handle/string serialization changes match exact narrow replacements, without assertion changes. Earlier filename/handle failures have attribution records but no captured raw logs; not treated as raw-log evidence.',
'replay_provenance':'AT014 measured full payload/CE/meta names and four selected attributes plus AT016 actual19 original candidates and4control INIT. CE INIT2 is only AT015 control-flow-derived fixture data. Module roots and C01 one-member fixture are synthetic. No all-native whole-design qualification.',
'CPU_receipt':ident(O/'original_address_selector_independent_cpu_receipt.json'),'supplementary_engineer_proposed3':ident(extra),'verified_references':verified},
'next':'A006 may apply exact083ac863 checks and e0a299ca proposed tests under existing authorization, preserve old source/test/manifest, refresh45-source manifest with only checks source delta, run all62 affected tests, then submit actual-source qualification for review before newAT017 native recovery.',
'constraints':['No production source modified by reviewer; current checks7419/manifest8b6 remain unchanged at observation.','No EDA,DCP read/hash, process or lock control, GPU or descendants.','OriginalAT003/AT015 failures and AT014 raw marker remain preserved.','Actual apply/restore/current graph and strict INIT/OPT/debug/preplace remain necessary before G4; no shortcut gate clearance.']}
p=O/'original_address_selector_v1_candidate_review.json';p.write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'review':ident(p),'verified_reference_entries':len(verified)},indent=2))
statep=R/'agent/A007/state.json';s=json.loads(statep.read_text());s.update({'reported_at':review['reviewed_utc'],'stage':'AT016实证严格17state候选083独立无阻断，待实际来源与62回归资格','latest_review':str(p.relative_to(R)),'next_step':'A006实际应用/源manifest/62回归后提交小包续审；AT017与严格G4仍待','review_execution':'completed_original_address_selector_candidate','current_turn_state':'waiting_for_actual_source_qualification','delivery':'Candidate review prepared; real delivery follows'});statep.write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n')
status=R/'agent/A007/status.md';status.write_text('# A007：实证严格17位地址选择器候选独立通过\n\nexecution_state: running\nreview_execution: completed_original_address_selector_candidate\n\n[候选审核](M003_SM015_SM017_review_20261018/original_address_selector_v1_candidate_review.json)：精确083ac863仅新增地址状态函数及resolve调用，byte重构/diff通过；两实测CARRY8按名字+类型限定排除，17位/作用域/重复/坏名/未知邻居拒绝保持。6工程独立复跑+6独立候选测试+3拟新增回归均通过，原测试AST全部保持。\n\n工程混合resolver回放7项原log已审；CE INIT推断、C01和module roots模拟与实测明确分开。生产尚未apply，checks7419/manifest8b6保持；下一为A006实际083应用/45源及62回归资格，再新AT017。G4未过；无EDA、DCP内容/哈希或生产编辑。\n\n## 历史阶段（保留）\n\n'+status.read_text())
