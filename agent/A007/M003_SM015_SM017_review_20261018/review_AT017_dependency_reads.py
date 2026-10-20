from pathlib import Path
import json,hashlib,re,datetime
R=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');O=R/'agent/A007/M003_SM015_SM017_review_20261018'
E=R/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT017_original_address_entry_postreport_recovery/evidence'
def ident(p):
 p=Path(p);assert p.suffix!='.dcp';assert p.stat().st_size<1024*1024;b=p.read_bytes();return {'path':str(p.relative_to(R)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(x):
 a=ident(x['path']);assert a['bytes']==x['bytes'] and a['sha256']==x['sha256'],x['path'];return a
package=E/'AT017_dependency_read_facts.json';d=json.loads(package.read_text());assert ident(package)['sha256']=='9122bae1a7f46d032c4f4bb4d40933bdf9283a4d7cdd968bfa6067b6436feea1'
refs={k:check(v) for k,v in d.items() if isinstance(v,dict) and 'path'in v}
prefix=Path(d['observed_native_log_prefix']['path']).read_bytes()
live=E/'jobs/native_postreport/launcher.log'
with live.open('rb') as h:assert h.read(len(prefix))==prefix
lines=prefix.decode().splitlines();assert len(lines)==69
pairs=[]
for i,line in enumerate(lines,1):
 m=re.search(r"INFO: \[Project 1-454\] Reading design checkpoint '([^']+)' for cell '([^']+)'",line)
 if m:pairs.append({'cell':m[2],'path':m[1],'line':i})
assert len(pairs)==22 and len({(x['cell'],x['path']) for x in pairs})==22 and pairs[-1]['line']==69
assert [{'cell':x['cell'],'path':x['path']} for x in pairs]==d['cell_path_pairs']
raw=json.loads(Path(d['original_AT003_lineage']['path']).read_text())
expected=[(x['cell'],x['consumed']['path']) for x in raw['produced_consumed']]
assert len(expected)==22 and {(x['cell'],x['path']) for x in pairs}==set(expected)
assert raw['native_exit_code']==1 and raw['run_count']==23 and raw['consumed_count']==22
metadata=json.loads(Path(d['native_metadata']['path']).read_text());assert len(metadata)==23
original_runs={x['run']:str(Path(x['checkpoint']['path']).parent) for x in raw['run_records']}
assert len(original_runs)==23 and {x['NAME']:x['DIRECTORY'] for x in metadata}==original_runs
assert all(x['STATUS']=='synth_design Complete!' and x['PROGRESS']=='100%' and x['NEEDS_REFRESH']=='0' for x in metadata)
q=json.loads(Path(d['native_content_admission']['path']).read_text());assert q==d['native_run_qualification']
assert q['passed'] is True and q['actual_stale_runs']==[] and q['native_status_modified'] is False and q['new_synthesis_launched'] is False
assert q['raw_lineage']==d['original_AT003_lineage'] and q['native_metadata']==d['native_metadata']
for k in ['source_manifest','raw_lineage','native_metadata']:check(q[k])
assert q['source_manifest']['sha256']=='5b307ca76c685ae4ca8cbf9758f452cd221d167e42d984764323aa6967c53199'
copy=O/'AT017_dependency_read_verified_prefix.txt';copy.write_bytes(prefix)
e={'schema':'A007_AT017_dependency_read_independent_evidence_v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'package':ident(package),'small_references':refs,'verified_exact_prefix':ident(copy),'live_prefix_source':str(live.relative_to(R)),'live_prefix_matched':True,'prefix_lines':69,'actual22_read_message_pairs':pairs,'original_AT003_outer_native_exit_code':1,'original23_run_names_directories_and_current_native_metadata':metadata,'native_content_admission':q,'source_scope':'Read-only small native logs/metadata. Native content qualification is reported by already reviewed native verification; no DCP content/hash independently accessed.','log_stage':'Immutable prefix through22nd read message; current log remains live, no final graph/apply/G4 claim'}
ep=O/'AT017_dependency_read_independent_evidence.json';ep.write_text(json.dumps(e,indent=2)+'\n')
review={'schema':'A007_AT017_native_dependency_read_review_v1','reviewer':'A007','reviewed_utc':e['observed_utc'],'execution':{'review':'completed','current_native':'ongoing as last engineer message; terminal not assessed'},'verdict':{'current_dependency_read_inventory':'accepted:22unique native checkpoint-read cell/path records exactly match original consumed22','current_native_run_metadata':'accepted:23exactoriginal names/directories,all synth_designComplete!/100%/NEEDS_REFRESH0','native_content_admission_binding':'accepted exact current5bmanifest/original2blineage,staleempty,nomodifiedstatus,nonewsynthesis','actual_overlay_apply_selected_graph_or_budget':'pending','G4':False,'place_admission':False},'applicability':{'manifest_sha256':q['source_manifest']['sha256'],'original_lineage_sha256':q['raw_lineage']['sha256'],'native_metadata_sha256':q['native_metadata']['sha256'],'original_AT003_outer_native_exit_code':1,'prior_actual_start_review':ident(O/'AT017_actual_start_review.json')},'review':{'package':ident(package),'evidence':ident(ep),'raw_prefix':'Exact13522-byte69-line immutableprefix independently matches current launcher.log prefix,through22nd read message;not a final native log','native_qualification':'Read source/currentnative metadata and admission receipts;DCP content verification remains A006/native owned,not newly performed byA007','boundary':'Full22read-record inventory is established; completion of whole design load,success ofoverlay/graph checks and finalnative status are separate later evidence.'},'next':'A006 continues normally; actual overlay/apply/selectedgraph/budget or anomaly/terminal triggers next directfollowup. StrictINIT/OPT/debug/preplace required beforeG4.','limits':['No production edit,EDA,DCPcontent/hash,process/lockcontrol or large table scan.','OriginalAT003outer1 and previous evidence retained.','No native0,route/timing success or background monitoring inferred.']}
p=O/'AT017_native_dependency_read_review.json';p.write_text(json.dumps(review,indent=2)+'\n');print(json.dumps({'review':ident(p),'evidence':ident(ep),'prefix':ident(copy),'pairs':len(pairs),'metadata_runs':len(metadata)},indent=2))
statep=R/'agent/A007/state.json';state=json.loads(statep.read_text());state.update({'reported_at':review['reviewed_utc'],'stage':'AT017实际22读取记录/23原run元数据及内容准入独立通过','next_step':'等待A006实际overlay/apply、当前图预算或异常/自然终态，直接followup续审；G4另审','latest_review':str(p.relative_to(R)),'review_execution':'completed_AT017_dependency_increment','current_turn_state':'yielding_wait_for_external_native_evidence','delivery':'Dependency review prepared; real delivery follows'});statep.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
status=R/'agent/A007/status.md';status.write_text('# A007：AT017全部22依赖读取记录独立审核通过\n\nexecution_state: running\nreview_execution: completed_AT017_dependency_increment\ncurrent_turn_state: yielding_wait_for_external_native_evidence\n\n[依赖读取审核](M003_SM015_SM017_review_20261018/AT017_native_dependency_read_review.json)：13522B/69行冻结日志前缀与当前launcher原字节匹配，22unique cell/path精确等于AT003原消费清单；23run名字/目录一致、Complete!/100%/refresh0，stale空，source5b/original2b内容准入绑定正确，无新综合/状态篡改。原AT003 outer1保留。\n\n本增量只确认完整22读取记录及元数据资格，非整图加载终态、actualapply/图预算/G4。A006正常原生继续；下一真实里程碑直接followup现有A007。无EDA、DCP内容/哈希、生产修改或进程/锁控制；无后台监控声明。\n\n## 历史阶段（保留）\n\n'+status.read_text())
