"""Read-only diagnosis of the failed finite queue; no process control/model work."""
import json,hashlib,time
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');BASE=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R004';OUT=Path(__file__).parent
begin=time.monotonic();sources={}
def source(p):
 p=Path(p).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1<<20),b''):h.update(x)
 x=dict(path=str(p),sha256=h.hexdigest());sources[str(p)]=x;return x
def read(p):source(p);return json.loads(Path(p).read_text())
def rows(p):
 source(p)
 with Path(p).open() as f:
  for line in f:yield json.loads(line)
def seconds(a,b):return (datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()
queue=read(BASE/'queues/Q001/queue_receipt.json');plan=read(ROOT/'.research-agent/decision_inputs/M005_R004_queue_v1/queue_plan_v2.json');groups=[]
for group in queue['groups']:
 p=Path(group['attempt_path']);r=read(p/'gpu_receipt.json');ev=list(rows(p/'paired_stages.jsonl'));docs=[x for x in ev if x['stage']=='document_completed'];attach=next(x for x in ev if x['stage']=='v5_attached');first=next(x for x in ev if x['stage']=='forward_started')
 resource=list(rows(p/'gpu_resources.jsonl'));document_results=[read(x) for x in sorted((p/'documents').glob('doc*/document_result.json'))]
 counters={}
 for file,fields in [('tensor_metrics.jsonl',['doc_id','layer']),('local_tensor_metrics.jsonl',['doc_id','layer','node','op']),('dynamic_metadata.jsonl',['doc_id','arm','layer','function','ordinal'])]:
  count=Counter(tuple(x[k] for k in fields) for x in rows(p/file));counters[file]=dict(unique_coordinates=len(count),duplicate_coordinates=sum(v-1 for v in count.values()))
  expected=len(document_results)*(32 if file=='tensor_metrics.jsonl' else 384);assert len(count)==expected and all(v==1 for v in count.values())
 groups.append(dict(group_id=group['group_id'],batch_ids=group['batch_ids'],attempt_path=str(p),state=group['execution_state'],gpu_receipt=r,
  completed_document_ids=group['completed_document_ids'],not_completed_document_ids=group['not_completed_document_ids'],durable_documents=len(document_results),
  durable_coverage_all_complete=all(d['coverage']['complete'] for d in document_results),raw_coordinate_counts=counters,
  last_document_completed_at=docs[-1]['at'],last_stage=ev[-1]['stage'],preparation_seconds=seconds(r['started_at'],attach['at']),
  forward_document_span_seconds=seconds(first['at'],docs[-1]['at']),post_last_document_seconds=seconds(docs[-1]['at'],r['ended_at']),
  maximum_document_seconds=max(d['seconds'] for d in docs),raw_evidence_bytes=sum(x.stat().st_size for x in p.rglob('*') if x.is_file()),
  minimum_observed_free_gpu_bytes=min(x['gpu_free_bytes'] for x in resource if x['gpu_free_bytes'] is not None),
  output_exists={name:(p/name).exists() for name in ['document_summary.json','local_document_summary.json','final_norm_document_summary.json','paired_result.json']},
  worker_process_present=Path('/proc',str(r['worker_pid'])).exists()))
depdir=BASE/'analysis/six_columns_after_queue';dependency=read(depdir/'control/receipt.json');dep_launch=read(depdir/'root_launch_receipt.json');depplan=read(depdir/'plan.json')
success=16+sum(len(g['completed_document_ids']) for g in groups if g['state']=='completed');partial=[g for g in groups if g['state']!='completed'];partial_ids=[i for g in partial for i in g['completed_document_ids']]
assert success==112 and len(queue['completed_document_ids'])==160 and len(queue['not_completed_document_ids'])==864 and len(partial_ids)==48
formal=read(BASE/'attempts/AT001_frozen_formal_input_plan/formal_batch_plan.json')
# Cost-only conservative option: each existing16doc logical batch from B008 onward.
remaining=[dict(batch_id=b['batch_id'],doc_ids=b['doc_ids'],audit_doc_ids=b['audit_doc_ids'],documents=b['selected_documents']) for b in formal['batches'][7:]]
report=dict(schema='m005_Q001_stop_diagnosis_v1',recorded_at=datetime.now(timezone.utc).isoformat(),queue_state=queue['execution_state'],
 stop=dict(trigger_group='G003',reason=groups[-1]['gpu_receipt']['stop_reason'],stage_wall_limit_seconds=900,observed_seconds=groups[-1]['gpu_receipt']['wall_seconds'],
  queue_global_wall_limit_seconds=plan['total_wall_seconds'],observed_queue_wall_seconds=queue['wall_seconds'],not_global_deadline=True,not_256MiB=True,not_rss_gpu_or_admission=True),
 ledger=dict(total_target=1024,successful_attempt_documents=success,independently_reviewed_documents=16,independent_scope='B001 only; G001/G002 postprocessing audits never ran',
  terminal_durable_documents=160,cost_stopped_attempt_durable_documents=48,never_completed_documents=864,
  successful_attempt_ids=['AT002','AT003','AT004'],cost_stopped_attempt='AT005',
  distinction='112 successful-attempt documents;48 more durable documents have no complete successful group receipt; do not label160 accepted'),
 groups=groups,completed_durable_document_ids=queue['completed_document_ids'],not_completed_document_ids=queue['not_completed_document_ids'],
 failed_attempt_durable_document_ids=partial_ids,dependency=dict(receipt=dependency,queue_process_present=Path('/proc/260261').exists(),
  dependency_process_present=Path('/proc',str(dep_launch['owned_dependency']['pid'])).exists(),final_figure_destination=depplan['output_dir'],final_figure_exists=Path(depplan['output_dir']).exists()),
 diagnosis=dict(facts=['All48 G003 paired forwards and durable document results finished before the wall stop.',
  'G003 stopped during post-document summary/finalization: hidden summary exists; local/final summaries and paired_result absent.',
  'G001/G002 each spent about254s after the final document and finished close to900s.',
  'G003 evidence69.3MB,peakRSS2.01GB,peakGPU15.62GB and minimumGPUfree35.27GB do not hit the corresponding caps.'],
  interpretation='insufficient per-group allowance for observed finalization overhead; exact slow function not established by timestamps; no method falsification',
  unmeasured='No extra CPU profiling, new model run, source edit, or GPU action in this diagnosis.'),
 continuation_proposal=dict(execution_authorized=False,new_plan_and_new_attempts_required=True,do_not_modify_old_queue=True,
  stable_precompleted_prefix=['B001','B002','B003','B004','B005','B006','B007'],
  conservative_remaining_documents=912,includes_failed_attempt48_again=True,
  conservative_groups=remaining,group_count=len(remaining),wall_per_group_seconds=900,evidence_per_group_mib=256,cpu_threads=1,max_rss_gib=8,max_gpu_gib=24,
  stage_wall_cap_sum_seconds=len(remaining)*900,
  observed16doc_B001_wall_seconds=484.948567,observed16doc_postlast_seconds=2.132564,
  estimated16doc_cost='rough estimate~500-600s including one audit and preparation; not a guarantee under new MLP coverage/load',
  conditional_larger_option='32doc consecutive batches only after an independent CPU finalization-cost qualification;48doc currently lacks margin',
  acceptance='Old AT005 remains cost_stop; no fabricated successful receipt or silent admission of its48 docs. Independent audit G001/G002 before final claims; preserve exact frozen order and audit membership.'),
 source_files=list(sources.values()),analysis_source=source(__file__),cpu_seconds_wall=time.monotonic()-begin,no_process_control=True,no_gpu=True)
with (OUT/'stop_diagnosis.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
lines=['# Q001 停止原因：只读终态核查','',f"核查时间{report['recorded_at']}。不启停进程、不改源码/计划、不重跑模型。",'',
'## 精确停止原因','', 'G003/AT005触发单组900秒预算，监督器在895秒预留退出后实际896.240821秒收尾，exit124/native−15，stop_reason=`assigned wall budget reached`。这是单组cost_stop；Q001因此stopped。队列总墙钟2707.120秒远小于23400秒，不是总deadline。', '',
'AT005证据69322263B（约66.11MiB）小于256MiB；peakRSS2008743936B小于8GiB，peakGPU15619588096B小于24GiB，最小GPU free35266756608B高于8GiB。source_unchanged=true/worker_reaped=true；worker284748、supervisor284742、queue260261核查时均无/proc记录。', '',
'## 完成数严格分开','', '|范围|文档数|资格|', '|---|---:|---|', '|B001|16|成功且A014独审|','|G001/AT003|48|完整成功；队列后置独审未运行|','|G002/AT004|48|完整成功；队列后置独审未运行|','|G003/AT005|48|durable两臂文档完整，但整组cost_stop|','|未完成剩余|864|后续组未启动|', '',
'因此完整成功attempt共112；terminal durable ledger160包含失败attempt的48篇，不等于160验收。完整ID列表见stop_diagnosis.json的completed_durable_document_ids/not_completed_document_ids/failed_attempt_durable_document_ids。', '',
'## 为什么48篇前向都结束仍触限','', '|组|加载/装配秒|文档前向区间秒|最后文档到终态秒|组耗时秒|', '|---|---:|---:|---:|---:|']
for g in groups:lines.append(f"|{g['group_id']}|{g['preparation_seconds']:.3f}|{g['forward_document_span_seconds']:.3f}|{g['post_last_document_seconds']:.3f}|{g['gpu_receipt']['wall_seconds']:.3f}|")
lines += ['', 'G003最后文档在05:41:44.504147Z完成，停止在05:45:16.066341Z，之间211.562秒。hidden document_summary已生成，local_document_summary/final_norm_document_summary/paired_result未生成，末尾无completed stage。G001/G002同一收尾区间约254秒。事实定位到前向之后的汇总/落盘收尾；未做CPU profiler，不能仅凭时间戳断言具体函数或系统争用原因。', '',
'## 六列依赖任务','', '依赖任务于05:45:20.899357Z停止：`original numerical queue did not complete successfully`；render_result=null、gpu_started=false，PID273406核查时已不存在。未生成figure_six_columns_final；已有16篇预览图不能冒充全1024最终图。Q001 analysis_results为空，25次后置独审/全量聚合/正式图/报告未运行。', '',
'## 最小可行延续建议（仅提案，不启动）','', '保持旧Q001与AT005原始终态。新计划可承认成功前缀B001–B007的112篇（先补G001/G002独审），从B008起按原57个16篇logical batch独立分组：剩余912篇包含G00348篇重测，成员/顺序/审计不变，每次900秒/CPU1/RSS8GiB/GPU24GiB/整AT256MiB。16篇B001实测484.949秒、收尾2.133秒，具更多成本余量；估算单组约500–600秒，实际受新MLP覆盖和资源负载影响，不能保证。57组阶段墙钟cap合计51300秒是上限而非预计耗时，新全局有限预算需Root重新冻结。', '',
'32篇选项应先仅CPU核收尾成本再确定；现存48篇已接近/撞上900秒，不能直接沿用。若以后从AT005原始48篇仅CPU恢复汇总，必须新派生证据与明确资格合同，旧cost_stop不得改为成功或伪造成功收据。本报告不做恢复、不写新runner。', '',
'具体freeze-ready logical batch/ID列表、来源SHA及各组原始证据路径见JSON。']
(OUT/'stop_diagnosis.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(output=str(OUT),successful_attempt_documents=112,independently_reviewed=16,durable=160,never_completed=864,cpu_wall=report['cpu_seconds_wall'])))
