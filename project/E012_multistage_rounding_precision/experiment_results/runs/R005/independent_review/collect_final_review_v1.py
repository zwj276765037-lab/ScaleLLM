"""Bounded CPU final evidence-ledger review; no model or numerical rerun."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import json,hashlib,math,time,datetime
from pathlib import Path
from collections import Counter
R=Path(__file__).resolve().parent.parent;S=R/'session_S001';A=R/'analysis/final_precision_png';start=time.monotonic();verified={};checks=Counter()
def require(v,label):
 if not v:raise AssertionError(label)
 checks['assertions']+=1
def read(p):return json.loads(Path(p).read_text())
def ident(p):
 p=Path(p).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8<<20):h.update(b)
 return {'path':str(p),'sha256':h.hexdigest(),'bytes':p.stat().st_size}
def verify(x):
 p=str(Path(x['path']).resolve());key=(p,x['sha256'])
 if key not in verified:
  z=ident(p);require(z['sha256']==x['sha256'],'SHA mismatch '+p);verified[key]=z
 return Path(p)
def same(a,b,label):require(math.isclose(a,b,rel_tol=2e-12,abs_tol=2e-13),label)
analysis=read(S/'analysis_manifest.json');plan=read(verify(analysis['plan']));launch=read(verify(analysis['session_launch_manifest']));gpu=read(verify(analysis['session_gpu_receipt']));end=read(S/'session_receipt.json')
require(gpu['execution_state']=='completed' and gpu['native_exit_code']==gpu['exit_code']==0 and gpu['worker_reaped'] and gpu['source_unchanged'] and gpu['stop_reason'] is None,'native complete/reaped/unchanged')
require(end['model_execution_state']==end['analysis_state']=='completed' and end['numerical_verdict']=='inconclusive','global execution/analysis distinction')
require(end['wall_seconds']<=plan['limits']['total_wall_seconds'] and gpu['max_observed_rss_bytes']<8*(1<<30) and gpu['max_observed_gpu_bytes']<24*(1<<30),'observed resource bounds')
for x in launch['source_identity']:verify(x)
require(len(plan['groups'])==len(analysis['ordered_groups'])==64 and len(plan['finalize_commands'])==67,'fixed complete group/finalizer roster')
require(analysis['actual_doc_ids']==analysis['expected_doc_ids'] and len(set(analysis['actual_doc_ids']))==1024 and not analysis['missing_doc_ids'],'global unique full1024')
for i,command in enumerate(plan['finalize_commands']):
 rec=read(S/f'finalize_{i:03d}/receipt.json');require(rec['exit_code']==0 and rec['stop_reason'] is None and rec['worker_reaped'] and rec['argv']==command['argv'],'finalizer actual receipt '+str(i))
 require(rec['wall_seconds']<=command['wall_seconds'] and rec['max_observed_rss_bytes']<8*(1<<30),'finite finalizer resources')
 for x in command['source_identities']:verify(x)
finalizer_wall=sum(read(S/f'finalize_{i:03d}/receipt.json')['wall_seconds'] for i in range(67))
for directory in ['aggregate_v1','png_v1']:
 manifest=read(A/directory/'output_manifest.json')
 for x in manifest['outputs']:verify(x)
 for key in ['input','source','aggregate','renderer']:
  if key in manifest:verify(manifest[key])
agg=read(A/'aggregate_v1/final_aggregate.json');png=read(A/'png_v1/source_data.json');inputs=read(verify(agg['input_manifest']));formal=read(verify(agg['formal_plan']));stream=read(verify(agg['formal_stream']));targets={d['doc_id']:d for d in stream['documents']};docs={d['doc_id']:d for d in agg['documents']}
require(len(docs)==len(agg['documents'])==1024 and set(docs)==set(targets)==set(analysis['actual_doc_ids']),'aggregate exact frozen membership')
require(Counter(d['domain'] for d in docs.values())==Counter({'web':512,'news':256,'reviews':256}),'domain quotas')
require(len({d['duplicate_cluster'] for d in docs.values()})==1024,'unique document clusters')
require(sum(d['tokens'] for d in docs.values())==103700 and max(d['tokens'] for d in docs.values())<=128,'actual unpadded token scope')
require(agg['actual_group_count']==64 and agg['target_complete'] and agg['measured_documents']==1024 and agg['missing_documents']==0,'aggregate complete')
for x in agg['evidence_files']:verify(x)
require(png['aggregate_source']['sha256']==ident(A/'aggregate_v1/final_aggregate.json')['sha256'],'PNG actual aggregate binding');verify(png['aggregate_source']);verify(png['renderer_source']);verify(png['output'])
require(png['descriptive_quantiles']==agg['distributions'] and png['vocabulary_coverage']==agg['vocabulary_coverage'] and png['top1']==agg['top1'],'PNG statistics equal audited aggregate')
require(png['all_document_points']==[{'doc_id':d['doc_id'],'domain':d['domain'],'tokens':d['tokens'],'columns':d['columns']} for d in agg['documents']],'PNG every actual document point')
require(png['render']['total_document_points']==13*1024,'all13312 plotted points')
keys=list(agg['distributions']['fixed_quota_pool']);require(len(keys)==13,'13 categories')
for key in keys:
 values=sorted(d['columns'][key]['value'] for d in docs.values());require(all(d['columns'][key]['state']=='finite' for d in docs.values()),'finite actual metric '+key)
 for name,p in [('p50',.5),('p95',.95),('p99',.99),('maximum',1.)]:
  rank=p*(len(values)-1);lo=int(rank);fr=rank-lo;value=values[lo] if not fr else values[lo]*(1-fr)+values[lo+1]*fr;same(agg['distributions']['fixed_quota_pool'][key][name]['value'],value,'independent document quantile '+key+name)
 require(not agg['distributions']['fixed_quota_pool'][key]['conditional_intervals'],'fixed quota pool has no CI')
 for domain in ['news','reviews']:
  require(agg['distributions']['domains'][domain][key]['conditional_intervals']['p99']['upper']['state']=='unbounded','N256 P99 infinite upper retained')
all_ids=[];raw_ids=[];core_counts=Counter();wc=Counter();bc=Counter();max_pair=Counter();extended=Counter();prod_max=0.;head_max=Counter();head_spots=0;head_exact_spots=0;head_rows=0;raw_by_doc=[];counter_totals={'current':Counter(),'reference':Counter()};source_shas=set();group_summaries=[]
for g in inputs['groups']:
 path=Path(g['attempt']);r=read(verify(next(x for x in analysis['ordered_groups'] if x['group_id']==g['group_id'])['receipt']))
 require(r['execution_state']=='completed' and r['coverage_complete'] and r['source_unchanged'] and r['exit_code']==0,'complete canonical segment')
 for x in r['output_identities']:verify(x)
 c=read(verify(g['core_audit']));e=read(verify(g['extension_audit']))
 for report,kind in [(c,'core'),(e,'extension')]:
  require(report['execution_state']=='completed' and report['review']=='limited_evidence_verified','audit completed '+kind)
  verify(report['source_identity']);source_shas.add(report['source_identity']['sha256'])
  binding=report['runtime_binding'];require(binding['shared_process'] and binding['shared_worker_identity']==gpu['shared_worker_identity'],'same real shared process');verify(binding['group_receipt']);verify(binding['global_receipt']);verify(binding['global_launch'])
  require(Path(report['attempt']).resolve()==path.resolve(),'audit canonical group identity')
 require(c['source_identity']['sha256']=='1b0eae5f16b2b6b7957d319b570c95c5ab918a2bec94b288a3a240ca8773e421' and e['source_identity']['sha256']=='e97a639c51a4925f2146f201b142967109b751d0ea66eac4af96fab30214bc48','exact frozen independent auditors')
 ids=g['doc_ids'];require(ids==r['doc_ids']==[d['doc_id'] for d in c['final_norm_by_doc']]==[d['doc_id'] for d in e['documents']],'both audits full document coverage')
 require(c['formal_eval_documents']==e['formal_eval_documents']==16,'formal16 per group');all_ids.extend(ids)
 expected_raw=[d for d in ids if targets[d]['raw_tensor_audit_selected']];require(c['audit_doc_ids']==e['audit_doc_ids']==expected_raw,'preselected audit docs complete');raw_ids.extend(expected_raw)
 require(c['code_mismatches']==(0 if expected_raw else None) and c['raw_theory_violations']==(0 if expected_raw else None),'measured mismatch/bound status or NA')
 wc.update(c['witness_counts']);bc.update(c['bound_counts']);core_counts.update(c['checks']);extended['raw_hidden_tensors_recomputed']+=e['raw_hidden_tensors_recomputed']
 for key,value in c['witness_max_pair_code'].items():max_pair[key]=max(max_pair[key],value)
 for d in c['final_norm_by_doc']:
  same(d['relative_l2_percent'],docs[d['doc_id']]['columns']['final_hidden']['value'],'actual final hidden aggregate')
 for d in ids:
  require([x['layer'] for x in docs[d]['propagation']]==list(range(32)),'all32 continuous hidden positions')
  for arm in counter_totals:
   counter_totals[arm].update({k:v for k,v in c['audits'][d][arm].items() if v is not None})
 for d in e['documents']:
  require(d['mlp']['mlp_rows']==416 and d['mlp']['aggregate_formula_verified'] and d['logits']['aggregate_formula_verified'],'full extension formulas')
  token=d['logits']['tokens'];require(token==docs[d['doc_id']]['tokens'] and d['logits']['score_pairs']==token*128256,'every actual full-vocabulary position')
  require(d['logits']['top1_match_count']==docs[d['doc_id']]['logits']['top1_match_count'],'aggregate top1 counts')
  for key in ['independent_product_samples','independent_host_conversion_samples','paired_output_spots_checked']:extended[key]+=d['mlp'][key]
  require(d['mlp']['product_bound_violations']==(0 if d['doc_id'] in expected_raw else None),'product witness bound status')
  require(d['mlp']['actual_full_array_semantic_counts']['product_common_exit_mismatch']==d['mlp']['actual_full_array_semantic_counts']['product_s32_overflow']==0,'actual product shared-exit semantics')
  if d['doc_id'] in expected_raw:
   raw_by_doc.append({'doc_id':d['doc_id'],'domain':docs[d['doc_id']]['domain'],'hidden_layers':len([x for x in c['hidden_by_layer'] if x['doc_id']==d['doc_id']]),'head_raw_positions':d['logits']['raw_positions'],'product_samples':d['mlp']['independent_product_samples'],'host_samples':d['mlp']['independent_host_conversion_samples']})
   prod_max=max(prod_max,d['mlp']['max_sample_product_absolute_error']);h=d['logits']['head_roundoff'];head_spots+=h['dots_checked'];head_exact_spots+=len(h['exact_dyadic_spots']);head_rows+=len(d['logits']['raw_positions'])
   for key in ['max_abs_current','max_abs_reference','max_abs_pair_delta_head_roundoff']:head_max[key]=max(head_max[key],h[key])
 group_summaries.append({'group_id':g['group_id'],'documents':16,'audit_doc_ids':expected_raw,'core':g['core_audit'],'extended':g['extension_audit'],'theory_applicable':c['theory_evaluated_outputs'],'witness_files':c['checks']['witness_files']})
require(all_ids==analysis['actual_doc_ids'] and len(set(all_ids))==1024,'all64 audits complete unique target in frozen order')
require(set(raw_ids)==set(formal['audit_candidate_doc_ids'])==set(agg['raw_audit_documents']) and len(raw_ids)==15,'all15 predefined raw audits')
require(Counter(x['hidden_layers'] for x in raw_by_doc)==Counter({32:3,3:12}),'declared full/thin raw hidden policy')
require(sum(v for k,v in wc.items() if k.endswith('_scalars'))==sum(bc.values()),'all expanded witnesses applicable or excluded')
score_pairs=sum(d['logits']['score_pairs'] for d in docs.values());top=sum(d['logits']['top1_match_count'] for d in docs.values());N=sum(d['tokens'] for d in docs.values())
require(score_pairs==103700*128256 and agg['top1']['token_weighted_match_count']==top and agg['top1']['token_weighted_total_count']==N,'all-score and top1 denominators')
for point in agg['vocabulary_coverage']:
 require(point['score_total_count']==score_pairs and point['document_total_count']==1024,'threshold coverage denominator')
 require(point['document_within_count']==sum(d['logits']['max_abs_logit_delta']<=point['epsilon'] for d in docs.values()),'document max-CDF independent count')
 require(point['score_within_count']==sum(d['logits']['score_within_threshold_counts'][d['logits']['score_thresholds'].index(point['epsilon'])] for d in docs.values()),'per-score coverage independent count')
report={'schema':'m005_r005_final_independent_evidence_review_v1','execution_state':'completed','review':'bounded_full_dataset_evidence_verified','overall_universal_precision_verdict':'inconclusive','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Completed formal1024 observed numerical evidence; finite sampled raw independent recomputation, not universal precision theorem. No model/GPU rerun in this review.','execution':{'gpu_native_exit':gpu['native_exit_code'],'worker_reaped':gpu['worker_reaped'],'sources_unchanged':gpu['source_unchanged'],'groups':64,'finalizers':67,'gpu_wall_seconds':gpu['wall_seconds'],'full_wall_seconds':end['wall_seconds'],'cpu_finalizer_wall_sum':finalizer_wall,'peak_gpu_bytes':gpu['max_observed_gpu_bytes'],'peak_rss_bytes':gpu['max_observed_rss_bytes']},'coverage':{'documents':1024,'domain_documents':dict(Counter(d['domain'] for d in docs.values())),'actual_tokens':N,'max_tokens':max(d['tokens'] for d in docs.values()),'layers':32,'hidden_statistic_cells':1024*32,'local_statistic_cells':1024*384,'mlp_statistic_cells':1024*416,'dynamic_event_cells':1024*384,'full_vocabulary_score_pairs':score_pairs,'core_audits':64,'extended_audits':64,'missing_documents':0,'raw_audit_documents':15,'raw_audit_by_doc':raw_by_doc},'core_independent_checks':{'reported_execution_checks':dict(core_counts),'witness_counts':dict(wc),'bound_counts':dict(bc),'maximum_observed_pair_difference_output_code_units':dict(max_pair),'applicable_bound_violations':0,'independent_current_or_reference_code_mismatches':0,'scope':'Counts inherited from authentic frozen CPU integer/Fraction audits, linked below; this final ledger rechecks identities/coverage rather than rerunning all raw arithmetic.'},'extension_raw_checks':{**dict(extended),'sample_product_bound_violations':0,'max_sample_product_absolute_error':prod_max,'head_raw_full_vocabulary_rows':head_rows,'head_scalar_dot_checks':head_spots,'head_exact_dyadic_spots':head_exact_spots,'selected_head_roundoff_maxima':dict(head_max),'scope':'Paired output spots include Host spots and must not be added as disjoint. Whole-MLP spots are not complete independent branch reruns. Head dots are selected diagnostic points, not a global floating-point head error bound.'},'production_counters':{k:dict(v) for k,v in counter_totals.items()},'observed_pooled_relative_l2_percent':{k:{q:agg['distributions']['fixed_quota_pool'][k][q]['value'] for q in ['p50','p95','p99','maximum']} for k in keys},'top1':agg['top1'],'statistics_scope':{'unit':'unique document source cluster','pool':'fixed2:1:1 domain quota descriptive; no unconditional CI','domain_intervals':'pointwise conditional on unverified within-domain IID; family1; N256 P99 upper infinity retained','unbounded_document_maxima':0,'unestimable_document_maxima':0},'unmeasured_or_unproved':['Full-sample post-softmax probability total-variation (TV) was not measured in this run.','No long-context or decode evidence; at most128 actual tokens and32-layer prefill.','No labeled task ACC/PPL rerun; Top1 agreement on identical prefixes is not task accuracy or free-running generation equivalence.','Most full raw hidden tensors and whole MLP branches were not independently recomputed; saved hidden policy is3documents×32layers plus12×3layers, with15 final states.','Shared quantized LUT semantics are measured; analytic SiLU/exp approximation loss is not isolated here.','Finite guards/accumulators removed in the reference are not audited as zero overflow; their counters are not applicable.','No universal relative-error threshold or global preservation verdict follows from zero sampled bound violations.'],'flagged_discrepancies':[],'limitations_to_report':['Production QK clipping is nonzero and reported separately; it is not an independent-code mismatch.','Sampled Softmax structural/padding-mask coordinates excluded from theorem bounds remain separately counted.','PNGv2 is a separate layout-only artifact under A015 review; this record verifies immutable png_v1 hashes/statistics.'],'artifacts':{'aggregate':ident(A/'aggregate_v1/final_aggregate.json'),'aggregate_manifest':ident(A/'aggregate_v1/output_manifest.json'),'png_v1':ident(A/'png_v1/final_precision.png'),'png_v1_manifest':ident(A/'png_v1/output_manifest.json'),'session_receipt':ident(S/'session_receipt.json'),'source':ident(__file__)},'groups':group_summaries,'final_ledger_checks':dict(checks),'unique_file_sha_rechecks':len(verified),'verified_file_manifest':list(verified.values()),'seconds':time.monotonic()-start}
for name in ['final_review.json','final_review.md']:require(not (R/'independent_review'/name).exists(),'new final review only')
with (R/'independent_review/final_review.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
with (R/'independent_review/final_review.md').open('x') as f:
 f.write('# R005 最终限定独审\n\n正式 1024 篇、64 组、67 项后处理完整完成；native0、worker 已回收、冻结源未变。64 份核心及 64 份扩展独审与冻结名单逐组一致，无遗漏或重复。执行/证据完整性已确认；普遍数值精度保持结论仍为 **inconclusive**。\n\n')
 f.write(f'统计覆盖 103,700 个实际 token、32 层 prefill、{score_pairs:,} 对全词表分数；网页/新闻/评论为512/256/256篇。aggregate_v1 与 png_v1 输出清单、SHA和全部13,312个文档图点已复核；独立重算文档分位、覆盖率计数及Top1分母一致。\n\n')
 f.write(f'预选15篇原始审计全部到齐：3篇保存全32层、12篇保存0/15/31层，共{core_counts["independent_hidden_tensors"]}个hidden张量对与15个末端。核心 {core_counts["witness_files"]} 个节点见证文件、{sum(v for k,v in wc.items() if k.endswith("_scalars")):,} 个展开输出；适用界 {sum(v for k,v in bc.items() if k.endswith("_applicable")):,} 个，排除 {sum(v for k,v in bc.items() if k.endswith("_excluded")):,} 个；适用范围内独立整数/Fraction码差异及理论界违例均0。排除项没有当成已验证界。\n\n')
 f.write(f'MLP独立乘积与Host样本各{extended["independent_product_samples"]:,}个；配对输出spot共{extended["paired_output_spots_checked"]:,}个（含Host，不能相加作独立总数）。输出头复核{head_rows}个预选完整词表行、{head_spots}个标量dot与{head_exact_spots}个精确二进制有理数spot；这不是全词表浮点归约误差上界。\n\n')
 f.write(f'生产QK裁剪计数 current={counter_totals["current"]["qk_score_clip"]:,}、reference={counter_totals["reference"]["qk_score_clip"]:,}，需单列，不能声称所有异常均0。\n\n')
 f.write('|指标（%）|P50|P95|P99|最大值|\n|---|---:|---:|---:|---:|\n')
 for k in ['whole_mlp','final_hidden','logits']:
  v=report['observed_pooled_relative_l2_percent'][k];f.write('|'+k+'|'+'|'.join(f'{v[q]:.6g}' for q in ['p50','p95','p99','maximum'])+'|\n')
 f.write(f'\n最高分词位置一致 {top:,}/{N:,}（{100*top/N:.6f}%），整篇所有位置一致 {agg["top1"]["all_positions_match_documents"]}/1024；均非任务准确率。合池固定配额仅描述；域内95%区间以未验证IID为条件，逐指标逐分位，不作联合保证；N256的P99无穷上端点已保留。\n\n')
 f.write('完整样本的 **Softmax后概率分布总变差TV未测**；不可宣称该指标完成。最多128实际token，未覆盖长上下文/decode；绝大多数完整raw张量与整个MLP分支未独立重跑；共同LUT核验不等于解析SiLU近似误差为零。零见证违例不等于普遍精度保持。PNGv2由A015单独核布局，本记录只核不可变png_v1。\n\n')
 f.write(f'详见 [final_review.json](final_review.json)：含所有组审计链接、来源/产物哈希、实际计数、限制；本次复核 {len(verified):,} 个文件SHA，CPU墙钟 {report["seconds"]:.3f}s，无GPU。\n')
print(json.dumps({k:report[k] for k in ['coverage','core_independent_checks','extension_raw_checks','top1','unique_file_sha_rechecks','seconds']},ensure_ascii=False))
