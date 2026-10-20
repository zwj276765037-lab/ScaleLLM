from pathlib import Path
import hashlib,json,datetime
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018'
E=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT017_original_address_entry_postreport_recovery/evidence'
REPORT=R/'project/hardware/vivado/reports/m003_E011_R002_AT017_original_address_entry_postreport_recovery'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<1024*1024;b=p.read_bytes();return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(x):
 a=ident(x['path']);assert a['bytes']==x['bytes'] and a['sha256']==x['sha256'],x['path'];return a
pkg=E/'first_apply_success_observation.json';d=json.loads(pkg.read_text());assert ident(pkg)['sha256']=='fd542f1a78cec784566ff1e84d0b4f404671f522f8923e727495332cb28c7ccc'
refs={k:check(v) for k,v in d.items() if isinstance(v,dict) and 'path'in v}
receipt_path=REPORT/'m003_apply_success_42854_1.json';raw=receipt_path.read_bytes();assert raw==Path(d['receipt']['path']).read_bytes()
receipt=json.loads(raw);assert receipt=={'kind':'native','success':'true','attempt':'1','pid':'42854','source_manifest_sha256':'5b307ca76c685ae4ca8cbf9758f452cd221d167e42d984764323aa6967c53199','overlay_sha256':'9124ea7eb710d8bbb4fe5c0c83e09f6cda1909d42e13d38bf6bae6765c9f3528'}
manifest=json.loads(Path(d['source_manifest']['path']).read_text());members={x['path']:x for x in manifest['sources']}
source_paths=[R/'project/hardware/vivado/scripts/m003_joint_checks.tcl',R/'project/hardware/vivado/constraints/m003_joint_locality.xdc',R/'project/hardware/vivado/scripts/m003_recover_synthesis.tcl']
source_ids=[check(members[str(p)]) for p in source_paths]
assert source_ids[0]['sha256']=='083ac863f89974dbb9e6a29d4409466485f64f7d7fd1140a3e73a42a553e7c54' and source_ids[1]['sha256']==receipt['overlay_sha256']
overlay=source_paths[1].read_text();assert 'source [file join $m003_script_root m003_joint_checks.tcl]\nm003::apply' in overlay
source=source_paths[0].read_text().splitlines()
assert 'set r [resolve]' in source[267] and 'm003_apply_success_' in source[296] and 'puts $h [jobject $d];close $h' in source[297]
success_chain=[{'line':n,'text':source[n-1]} for n in [260,261,262,266,267,268,280,286,287,290,291,292,293,296,297,298,299]]
prefix=Path(d['launcher_prefix']['path']).read_bytes()
with (E/'jobs/native_postreport/launcher.log').open('rb') as h:assert h.read(len(prefix))==prefix
ls=prefix.decode().splitlines();assert len(ls)==297
marker='M003_OVERLAY_APPLIED head42 tail39 URAM40+40 address34 C01_retained'
assert ls[284]==marker and sum(x==marker for x in ls)==1
trace=Path(d['trace_prefix']['path']).read_bytes();assert trace==b'attempt=1 restore_verify_only=0\n'
with (REPORT/'m003_apply_attempts_42854.txt').open('rb') as h:assert h.read(len(trace))==trace
sample=json.loads(Path(d['resource_sample']['path']).read_text())
assert sample['rss_bytes']==sum(x['rss_bytes'] for x in sample['processes'].values())
startup=json.loads((O/'AT017_actual_start_review.json').read_text());expected={str(x['pid']):x['start_ticks'] for x in startup['review']['process_identities']}
assert all(x['start_ticks']==expected[pid] and x['nice']==5 for pid,x in sample['processes'].items())
proc=Path('/proc/42854');stat=(proc/'stat').read_text();fields=stat[stat.rfind(')')+2:].split();assert int(fields[19])==1270755
env={}
for item in (proc/'environ').read_bytes().split(b'\0'):
 if b'=' not in item:continue
 k,v=item.split(b'=',1)
 if k in {b'HAP_M003_SCRIPTS_DIR',b'HAP_REPORT_DIR'}:env[k.decode()]=v.decode()
assert env=={'HAP_M003_SCRIPTS_DIR':str(R/'project/hardware/vivado/scripts'),'HAP_REPORT_DIR':str(REPORT)}
opkg=E/'open_run_completed_observation.json';od=json.loads(opkg.read_text());assert ident(opkg)['sha256']=='031ec10d6abb1189061049d3e277b9d89800c3918b452cfd62453bdaf611eb8e'
orefs={k:check(v) for k,v in od.items() if isinstance(v,dict) and 'path'in v}
oprefix=Path(od['launcher_prefix']['path']).read_bytes();assert oprefix.startswith(prefix)
with (E/'jobs/native_postreport/launcher.log').open('rb') as h:assert h.read(len(oprefix))==oprefix
ols=oprefix.decode().splitlines();assert len(ols)==319 and ols[-1]==od['actual_open_run_time_message'] and ols[-1].startswith('open_run: Time (s):')
recovery=source_paths[2].read_text().splitlines();assert recovery[34]=='open_run synth_1' and recovery[36]=='source $overlay' and recovery[38]=='m003::snapshot synth $report_dir'
e={'schema':'A007_AT017_first_apply_open_run_independent_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'first_apply_package':ident(pkg),'references':refs,'actual_native_receipt':ident(receipt_path),'raw_receipt_decoded_without_type_coercion':receipt,'source_chain_identities':source_ids,'source_success_write_order':success_chain,'actual_native_pid':42854,'actual_native_start_ticks':1270755,'approved_path_environment_only':env,'immutable_launcher_prefix_line_count':297,'native_success_marker':{'line':285,'text':ls[284]},'trace_prefix':trace.decode(),'resource_sample':sample,'resource_scope':'Historical immutable A00612:16sample reconciled with accepted startup identities and its ownRSSsum, not new resource sampling or timing attribution','open_run_package':ident(opkg),'open_run_references':orefs,'post_open_run_prefix_line_count':319,'open_run_native_time_line':ols[-1],'recovery_source_continuation':[{ 'line':i,'text':recovery[i-1]} for i in range(35,43)],'no_DCP_contents_or_hash':True,'scope':'First nativeapplysuccess and open_run completion only; live prefix not full final log, no selectedgraph/budget/restore/G4.'}
ep=O/'AT017_first_apply_success_independent_evidence.json';ep.write_text(json.dumps(e,indent=2)+'\n')
review={'schema':'A007_AT017_first_native_apply_success_review_v1','reviewer':'A007','reviewed_utc':e['observed_utc'],'execution':{'review':'completed','native_attempt':'ongoing at independent PID identity observation','first_apply':'nativeattempt1 success accepted','open_run':'completion accepted'},'verdict':{'actual_first_overlay_apply':'accepted','actual_open_run_completion':'accepted','selected_graph_budget_qualification':'pending','native_terminal_restore':'pending','G4':False,'physical_implementation':'not accepted'},'applicability':{'checks_sha256':source_ids[0]['sha256'],'manifest_sha256':receipt['source_manifest_sha256'],'overlay_sha256':receipt['overlay_sha256'],'native_pid':42854,'native_start_ticks':1270755},'review':{'first_apply_package':ident(pkg),'open_run_package':ident(opkg),'evidence':ident(ep),'receipt_authenticity':'Copied239B receipt exactly equals actual report/m003_apply_success_42854_1.json; originalJSON string values true/1/42854 preserved and interpreted per current serializer, not presented as native JSON boolean/numbers.','path_binding':'Observed same42854/start1270755 native process environment binds approved production scripts directory and exactAT017report; overlay sources checks there, currentsource hashes match acceptedmanifest.','success_semantics':'checks083 writes receipt only after runtimeguard, resolve, every configuredCR/meta/C01hard_pblock call and C01DONT_TOUCH guard return without an uncaught Tcl error. Exclusivecreate precedes successlog marker. This establishes completed firstTclconstraint application flow, not independent final membership/readback or allgraph qualification.','log_and_trace':'Exact103100B/297line prefix matches live launcher; source/apply-success/finish-source lines284–286 consistent.32B first-attempt trace matches live prefix and restore_verify_only0. Later additions outside frozenprefix unassessed.','open_run':'Exact104659B/319line prefix extends prior prefix and ends in native open_run timing line:cpu01:01:36,elapsed00:44:13. This is wholeopen_run timing, not apply/hard_pblock attribution. recovery Tcl35 then36clockchecks/37explicitoverlay/38applycheck/39snapshot/40budget remain separate downstream steps.','resource':'Immutable12:16sample carries sameoriginal4ownedPID identities and5nice;RSSsum internally consistent. No new resource limit decision or warning clearance.'},'next':'A006 continues normal native execution without intervention. Review actual subsequentapply/currentselectedgraph/budget and native terminal, then restore and strictINIT/OPT/debug/preplace under originalG4requirements.','limits':['No EDA/nativeAPI,DCPcontents/hash,productionedit,signals orlockcontrol;only bounded files and approvedPIDpathenvironment read.','Success marker counts are source-reported/guard-reachability evidence, not a replacement selected-object census.','No blanket constraint warning,reset/CDC/timing/DRC clearance.','TOP01 -2.896ns and report/canonicaldelta22049 remain OPEN; no normal time/silence stop.']}
p=O/'AT017_first_apply_success_review.json';p.write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps({'review':ident(p),'evidence':ident(ep)},indent=2))
statep=R/'agent/A007/state.json';state=json.loads(statep.read_text());state.update({'reported_at':review['reviewed_utc'],'stage':'AT017首次原生overlay apply1成功及open_run完成已独立核验','next_step':'等待后续实际apply/selected图预算/native终态及restore严格G4证据；正常运行继续','latest_review':str(p.relative_to(R)),'review_execution':'completed_AT017_first_apply_and_open_run_increment','current_turn_state':'waiting_for_actual_native_milestone','delivery':'First apply review prepared; real delivery follows'});statep.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
status=R/'agent/A007/status.md';status.write_text('# A007：AT017首次原生overlay应用成功及open_run完成独立通过\n\nexecution_state: running\nreview_execution: completed_AT017_first_apply_and_open_run_increment\n\n[首应用审核](M003_SM015_SM017_review_20261018/AT017_first_apply_success_review.json)：actual239B apply1回执与保全副本一致，native42854/start1270755及真实scripts/report路径、checks083/manifest5b/overlay9124绑定核实；103100B日志前缀实际成功marker与source顺序成立。回执只在runtime/resolve/全部pblock调用与C01保护检查返回后写出。open_run另104659B前缀确认完成，cpu01:01:36/elapsed00:44:13仅全open_run计时。\n\n这是首次Tcl应用流程成功，非最终对象图/预算/restore/native终态/G4或物理验收。A006正常原生继续；A007未改源、未EDA、未读hashDCP或控制进程/锁。真实下一阶段直接续审。\n\n## 历史阶段（保留）\n\n'+status.read_text())
