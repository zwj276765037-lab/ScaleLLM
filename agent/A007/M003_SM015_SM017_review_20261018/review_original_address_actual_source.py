from pathlib import Path
import json,hashlib,datetime,ast,re
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018';B=R/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/original_address_selector_v1'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<4*1024*1024;b=p.read_bytes();return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(x):
 a=ident(x['path']);assert a['bytes']==x['bytes'] and a['sha256']==x['sha256'],x['path'];return a
package=B/'actual_applied_source_qualification.json';d=json.loads(package.read_text());assert ident(package)['sha256']=='bb4a16a33605117a9e3015432535d1b3018c5e5df39d369dcf20aa5edb5f3e7a'
refs={k:check(v) for k,v in d.items() if isinstance(v,dict) and 'path' in v}
old=json.loads(Path(d['previous_manifest']['path']).read_text());new=json.loads(Path(d['actual_manifest']['path']).read_text())
assert old['G2_sha256']==new['G2_sha256']==d['G2']['sha256']
oldrows={x['path']:x for x in old['sources']};newrows={x['path']:x for x in new['sources']}
assert len(oldrows)==len(newrows)==len(new['sources'])==45 and set(oldrows)==set(newrows)
delta=[{'before':oldrows[p],'after':newrows[p]} for p in oldrows if oldrows[p]!=newrows[p]]
assert delta==d['only_production_source_delta'] and len(delta)==1 and delta[0]['after']['path']==d['actual_checks']['path']
sources=[check(x) for x in new['sources']];rtls=[check(x) for x in d['three_RTL']]
candidate=json.loads(Path(d['candidate_package']['path']).read_text())
assert Path(d['actual_checks']['path']).read_bytes()==Path(candidate['candidate']['path']).read_bytes()
assert Path(d['actual_tests']['path']).read_bytes()==Path(candidate['proposed_regression']['path']).read_bytes()
accepted=json.loads(Path(d['candidate_independent_review']['path']).read_text())
assert accepted['no_blocker'] is True and accepted['candidate_sha256']==d['actual_checks']['sha256'] and accepted['proposed_regression_sha256']==d['actual_tests']['sha256']
apply=json.loads(Path(d['actual_application']['path']).read_text())
applyrefs={k:check(v) for k,v in apply.items() if isinstance(v,dict) and 'path'in v}
preserve=json.loads(Path(d['old_source_test_manifest_preservation']['path']).read_text());preserved=[]
for x in preserve['preserved']:
 a=check(x['preserved']);assert a['sha256']==x['original']['sha256'] and a['bytes']==x['original']['bytes'];preserved.append(a)
assert [x['sha256'] for x in preserved]==[candidate['production_before']['sha256'],candidate['before_regression']['sha256'],d['previous_manifest']['sha256']]
reg=json.loads(Path(d['actual_affected_regression']['path']).read_text())
regrefs={k:check(v) for k,v in reg.items() if isinstance(v,dict) and 'path'in v}
testrefs=[check(x) for x in reg['tests']]
assert reg['exit_code']==0 and reg['manifest']==d['actual_manifest'] and reg['checks']==d['actual_checks']
assert reg['command']==['/usr/bin/python3','-m','unittest','-v','tests.test_m003_joint_qualification','tests.test_m003_native_entry_repair']
assert reg['cwd']==str(R/'project/hardware')
assert reg['started_utc']>apply['applied_utc']
log=Path(reg['log']['path']).read_text();matches=re.findall(r'^(\w+) \(([^)]+)\) \.\.\. ok$',log,re.M)
assert len(matches)==62 and len({q for n,q in matches})==62 and '\nRan 62 tests in 8.691s\n\nOK\n' in log
assert not any(x in log for x in ['FAILED (',' ... FAIL',' ... ERROR',' ... skipped'])
expected=[]
for x in reg['tests']:
 tree=ast.parse(Path(x['path']).read_text());module='tests.'+Path(x['path']).stem
 for cls in tree.body:
  if isinstance(cls,ast.ClassDef):
   expected.extend(module+'.'+cls.name+'.'+fn.name for fn in cls.body if isinstance(fn,ast.FunctionDef) and fn.name.startswith('test_'))
assert set(q for n,q in matches)==set(expected)
added=[q for n,q in matches if '.OriginalAddressSelection.'in q];assert len(added)==3
e={'schema':'A007_actual_original_address_source_independent_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'package':ident(package),'references':refs,'application_references':applyrefs,'manifest_delta':delta,'actual45sources':sources,'source_bytes_hashed':sum(x['bytes'] for x in sources),'three_RTL':rtls,'preserved_old_files':preserved,'regression_references':regrefs,'regression_test_sources':testrefs,'actual62pass_identifiers':[q for n,q in matches],'added_three_pass_identifiers':added,'test_name_set_matches_actual_source_AST':True,'raw_log_summary':'Ran62tests in8.691s;OK; no skip/fail/error','no_independent_regression_rerun':'Exact accepted candidate already independently tested; actual source byte identity/current62raw log and identities checked here','DCP_read_or_hash':False}
ep=O/'original_address_actual_source_independent_evidence.json';ep.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n')
review={'schema':'A007_original_address_actual_applied_source_qualification_review_v1','reviewer':'A007','reviewed_utc':e['observed_utc'],'no_blocker':True,'package_sha256':ident(package)['sha256'],'execution':{'review':'completed','actual_source_application':'accepted','actual62_regression':'passed','AT017':'not yet reported started'},'verdict':{'source_qualification':'accepted for newAT017 sameR002 native recover-synth under existing authorization','native_apply_or_selected_graph':'not established','method_efficacy':'unassessed','G4':False,'place_admission':False},'applicability':{'actual_checks_sha256':d['actual_checks']['sha256'],'actual_tests_sha256':d['actual_tests']['sha256'],'actual_manifest_sha256':d['actual_manifest']['sha256'],'sources_verified':45,'three_RTL_and_G2':'unchanged','candidate_review':d['candidate_independent_review']},'review':{'production_delta':'Exact accepted083ac863 checks and e0a299ca tests byte-match candidates.45-source path set/G2 unchanged; only production manifest source delta is checks7419→083.','preservation':'Old checks7419, testsddc1 and manifest8b6 archived with exact matching identities. Historical original paths are not mistaken for current source bytes.','regression':'Actual applied files match receipt; cwd points productionhardware; execution after application.62 unique rawlog passIDs exactly match current two testmodules AST, including all3 new methods.8.691s, exit0, no skip/fail/error. No redundant full rerun needed after existing independent candidate tests.','evidence':ident(ep),'source_package':ident(package)},'next':'A006 may register/start newAT017 under sameR002 and provide actual source archive, original23producer/22consumer lineage binding, original PID/start and resources. Native apply/restore/full selectedgraph/budget then strict INIT/OPT/debug/preplace require separate review before G4.','limits':['Source qualification does not mean constraint application, whole-graph validity or route/timing closure.','OriginalAT003 andAT015 failures remain; AT014 malformed raw marker preserved.','No EDA,DCP contents/hash,production edit,process or lock control by A007.','TOP01 -2.896ns and report/canonical difference22049 remain OPEN.']}
p=O/'original_address_actual_source_qualification_review.json';p.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'review':ident(p),'evidence':ident(ep),'sources_hashed':45,'source_bytes':e['source_bytes_hashed'],'tests_passed':62},indent=2))
statep=R/'agent/A007/state.json';state=json.loads(statep.read_text());state.update({'reported_at':review['reviewed_utc'],'stage':'实际083/5b源资格与62回归独立通过，待新AT017原生回执','next_step':'A006新AT017同R002恢复；实际来源/谱系/原生apply与G4逐阶段续审','latest_review':str(p.relative_to(R)),'review_execution':'completed_original_address_actual_source_qualification','current_turn_state':'waiting_for_actual_AT017_start','delivery':'Actual source review prepared; real delivery follows'});statep.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
status=R/'agent/A007/status.md';status.write_text('# A007：严格地址选择器实际源资格独立通过\n\nexecution_state: running\nreview_execution: completed_original_address_actual_source_qualification\n\n[实际源资格审核](M003_SM015_SM017_review_20261018/original_address_actual_source_qualification_review.json)：actual083/e0a与已审候选字节一致，45源全核及新manifest5b仅checks一项变更，旧三文件保全，3RTL/G2不变。实际62项原log通过/8.691s，62个唯一passID精确匹配当前两测试模块AST，含新3项，无skip/fail/error。\n\nA006可新AT017恢复；尚未实际启动或图/apply/G4放行。A007无EDA、DCP内容/哈希、生产编辑或进程/锁控制。真实原生回执由A006直接续接审核。\n\n## 历史阶段（保留）\n\n'+status.read_text())
