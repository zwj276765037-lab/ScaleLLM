"""Write an evidence-bounded user report after aggregate, audits and plot agree.

Only explicitly supplied completed generic audit JSONs are accepted.  Full
publication requires all1024 frozen documents, all25 GPU attempts, the three
domain quotas, and all15 preselected raw-audit documents.  --allow-partial
produces a visibly incomplete qualification preview, never a precision verdict.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

DOMAINS = {'web': 512, 'news': 256, 'reviews': 256}
FAMILIES = {'linear': '线性层', 'rope': '旋转位置编码', 'qk': '注意力打分', 'softmax': '概率归一化', 'pv': '注意力加权'}
EXPECTED_WITNESS_FILES = {'linear': 224, 'rope': 64, 'qk': 32, 'softmax': 32, 'pv': 32}
PROJECT = Path(__file__).resolve().parents[5]
CONTRACT = Path(__file__).resolve().parents[1] / 'source/numerical_fidelity_contract_v3.md'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def read_json(path):
    return json.loads(Path(path).read_text())


def verify(spec):
    actual = identity(spec['path'])
    require(actual['sha256'] == spec['sha256'], 'source/output SHA mismatch: ' + actual['path'])
    require('bytes' not in spec or actual['bytes'] == spec['bytes'], 'source/output byte count differs')
    return actual


def count(value, label):
    require(type(value) is int and value >= 0, 'invalid nonnegative count: ' + label)
    return value


def same_number(a, b):
    return a is None and b is None or (type(a) in (int, float) and type(b) in (int, float)
        and math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12))


def build_summary(aggregate_path, audit_paths, overview_path, *, allow_partial=False):
    aggregate_path, overview_path = Path(aggregate_path).resolve(), Path(overview_path).resolve()
    aggregate, overview = read_json(aggregate_path), read_json(overview_path)
    require(aggregate.get('schema') == 'm005_formal_numerical_aggregate_v1' and aggregate.get('execution_state') == 'completed', 'wrong/incomplete formal aggregate')
    require(overview.get('schema') == 'm005_formal_numerical_plot_v1', 'wrong formal overview source')
    docs = aggregate['documents']; n = count(aggregate['completed_documents'], 'measured documents')
    require(aggregate['planned_documents'] == 1024 and 0 < n <= 1024 and len(docs) == n, 'wrong formal target/document count')
    ids = {row['doc_id'] for row in docs}
    require(len(ids) == n and len({row['duplicate_cluster'] for row in docs}) == n, 'duplicate document/cluster in aggregate')
    require(all(row['split'] == 'eval' and row['evidence_role'] == 'formal_eval' for row in docs), 'development/nonformal document cannot enter formal report')
    require(aggregate['domain_counts_planned'] == DOMAINS, 'wrong target domain quotas')
    actual_domains = Counter(row['domain'] for row in docs)
    require(actual_domains == Counter(aggregate['domain_counts_completed']) and not (set(actual_domains) - set(DOMAINS)), 'measured domain accounting differs')
    require(all(actual_domains[key] <= target for key, target in DOMAINS.items()), 'domain over quota')
    complete = n == 1024
    require(aggregate['missing_documents'] == 1024-n and aggregate['collection_complete'] is complete, 'collection/missing accounting differs')
    require(complete or allow_partial, 'full1024 data required; use --allow-partial only for a labelled preview')
    if complete:
        require(actual_domains == Counter(DOMAINS) and not aggregate['missing_doc_ids'], 'incomplete full target/quota')
    require(aggregate.get('failed_supplied_attempts') == aggregate.get('invalid_supplied_attempts') == 0, 'failed/invalid attempts in aggregate')
    evidence = {str(Path(row['path']).resolve()): row for row in aggregate['evidence_files']}
    # This small frozen plan/stream links source selection and raw-audit membership.
    plans = [row for path, row in evidence.items() if Path(path).name == 'formal_batch_plan.json']
    require(len(plans) == 1, 'unique frozen formal batch plan identity required')
    verify(plans[0]); plan = read_json(plans[0]['path'])
    stream_source = verify(plan['input_stream_manifest']); stream = read_json(stream_source['path'])
    target_docs = stream['documents']; target_ids = {row['doc_id'] for row in target_docs}
    require(len(target_docs) == len(target_ids) == 1024 and ids <= target_ids, 'aggregate documents differ from frozen target')
    expected = {row['doc_id']: row for row in target_docs}
    for row in docs:
        source = expected[row['doc_id']]
        require(all(row[key] == source[key] for key in ('domain','split','evidence_role','text_sha256','duplicate_cluster','tokens')), 'aggregate document identity differs from frozen stream')
        require(row['coverage'] == dict(hidden_layers=32,local_coordinates=384,dynamic_coordinates=384,final_norm=1), 'aggregate document coverage is incomplete')
        require([item['layer'] for item in row['propagation']] == list(range(32)), 'missing/duplicate propagation layer')
    require(set(aggregate['missing_doc_ids']) == target_ids-ids and len(aggregate['missing_doc_ids']) == 1024-n, 'missing document IDs do not match target difference')
    planned_raw = {row['doc_id'] for row in target_docs if row['raw_tensor_audit_selected']}
    require(len(planned_raw) == 15, 'expected15 predeclared raw-audit documents')
    required_raw = planned_raw & ids
    aggregate_identity = identity(aggregate_path)
    require(verify(overview['aggregate_source'])['sha256'] == aggregate_identity['sha256'], 'overview references another aggregate')
    require(overview['measured_documents'] == n and overview['planned_documents'] == 1024
            and overview['missing_documents'] == 1024-n and overview['collection_complete'] is complete,
            'overview document accounting differs')
    require(overview['domain_counts'] == aggregate['domain_counts_completed'], 'overview domain counts differ')
    pool = aggregate['distributions']['fixed_quota_pool']
    require(overview['pooled_local'] == {key:pool['local_'+key] for key in FAMILIES}
            and overview['final_normalization'] == pool['final_normalization_bound'], 'overview values differ from aggregate')
    require(len(overview['propagation']) == 32 and all(row['layer'] == index+1
            and row['statistics'] == pool[f'propagation_layer_{index:02d}'] for index,row in enumerate(overview['propagation'])), 'overview propagation differs')
    image_sources = [verify(row) for row in overview['outputs']]
    require(len(image_sources) == 2 and {Path(row['path']).suffix for row in image_sources} == {'.png','.pdf'}, 'PNG and PDF overview identities required')
    attempts = aggregate['accepted_attempts']
    attempt_by_path = {str(Path(row['path']).resolve()): row for row in attempts}
    require(len(attempt_by_path) == len(attempts) and len(attempts) == (25 if complete else len(attempts)), 'complete formal report requires25 distinct GPU attempts')
    require(sum(row['documents'] for row in attempts) == n, 'attempt document counts differ')
    paths = [Path(path).resolve() for path in audit_paths]
    require(paths and len(paths) == len(set(paths)) == len(attempts), 'exactly one explicit generic audit per accepted attempt required')
    audit_sources, audit_records = [], []
    seen_attempts, audited_docs, raw_seen = set(), set(), set()
    witness = {family: dict(files=0,expanded=0,applicable=0,excluded=0) for family in FAMILIES}
    checks = Counter(); source_sha = None; independent_full_hidden = set(); hidden_saved = 0
    for path in paths:
        audit = read_json(path); audit_sources.append(identity(path))
        require(audit.get('schema') == 'm005_independent_formal_attempt_audit_v1'
                and audit.get('execution_state') == 'completed' and audit.get('review') == 'limited_evidence_verified',
                'generic audit failed/incomplete/wrong schema')
        attempt = str(Path(audit['attempt']).resolve())
        require(attempt in attempt_by_path and attempt not in seen_attempts, 'audit attempt missing/duplicate/not in aggregate')
        seen_attempts.add(attempt)
        selected = {row['doc_id'] for row in docs if str(Path(row['attempt']).resolve()) == attempt}
        final_rows = audit['final_norm_by_doc']; final_ids = [row['doc_id'] for row in final_rows]
        require(len(final_ids) == len(set(final_ids)) and set(final_ids) == selected, 'audit document set differs from aggregate attempt')
        require(not audited_docs.intersection(selected), 'document repeated across independent audits')
        audited_docs.update(selected)
        require(audit['formal_eval_documents'] == len(selected) and audit['full_target_documents'] == 1024,
                'audit formal document counts differ')
        require(set(audit['audits']) == selected, 'per-document current/reference audit set differs')
        require(audit['checks'].get('final_norm_formula_documents') == len(selected), 'independent final-norm formula coverage missing')
        own_source = verify(audit['source_identity'])
        require(source_sha is None or source_sha == own_source['sha256'], 'mixed independent-auditor versions need explicit qualification')
        source_sha = own_source['sha256']
        raw = set(audit['audit_doc_ids'])
        require(len(raw) == len(audit['audit_doc_ids']) and raw == required_raw & selected and not raw_seen.intersection(raw), 'raw audit selection differs from frozen stream')
        raw_seen.update(raw)
        manifest_path = Path(attempt)/'paired_worker_manifest.json'
        require(str(manifest_path) in evidence, 'attempt manifest identity absent from aggregate evidence')
        verify(evidence[str(manifest_path)]); manifest = read_json(manifest_path)
        require(set(manifest['audit_document_ids']) == raw, 'generic/worker audit selection differs')
        policies = {row['doc_id']:row for row in manifest['raw_policy']['records']}
        expected_hidden = {(doc,layer) for doc in raw for layer in policies[doc]['raw_hidden_layers']}
        actual_hidden = [(row['doc_id'],row['layer']) for row in audit['hidden_by_layer']]
        require(len(actual_hidden) == len(set(actual_hidden)) and set(actual_hidden) == expected_hidden, 'independent raw-hidden layer coverage differs from frozen policy')
        require(set(audit.get('independent_final_by_doc',{})) == raw
                and set(audit.get('independent_dynamic_saved_scope',{})) == raw, 'raw final/dynamic audit document coverage differs')
        independent_full_hidden.update(doc for doc in raw if policies[doc]['raw_hidden_layers'] == list(range(32)))
        hidden_saved += len(actual_hidden)
        for row in final_rows:
            doc = next(item for item in docs if item['doc_id'] == row['doc_id'])
            require(row['tokens'] == doc['tokens'], 'audit real token length differs')
            reference = doc['final_normalization']['relative_error']
            for key in ('signal_energy','error_energy'):
                if key in reference:
                    require(same_number(row[key],reference[key]), 'audit/aggregate final energy differs')
            require(same_number(row['relative_l2_percent'],reference['value']), 'audit/aggregate final ratio differs')
        files = applicable = expanded = 0
        for family in FAMILIES:
            entries = audit['witness_counts']; bounds = audit['bound_counts']
            number = count(entries.get(family+'_saved',0),family+' files')
            scalar = count(entries.get(family+'_scalars',0),family+' expanded')
            valid = count(bounds.get(family+'_applicable',0),family+' applicable')
            excluded = count(bounds.get(family+'_excluded',0),family+' excluded')
            require(number == EXPECTED_WITNESS_FILES[family]*len(raw), 'witness coordinate coverage incomplete')
            require(scalar == valid+excluded, 'expanded witness outputs do not equal applicable+excluded')
            if raw:
                require(scalar > 0, 'raw audit missing scalar witnesses')
            for key,value in (('files',number),('expanded',scalar),('applicable',valid),('excluded',excluded)):
                witness[family][key] += value
            files += number; applicable += valid; expanded += scalar
        require(audit['checks'].get('witness_files',0) == files and audit['theory_evaluated_outputs'] == applicable,
                'witness/theory denominator mismatch')
        require(audit['checks'].get('independent_hidden_tensors',0) == len(actual_hidden), 'raw hidden audit count differs')
        require(audit.get('code_mismatches') == (0 if files else None)
                and audit.get('raw_theory_violations') == (0 if applicable else None), 'independent audit has a failure or unsupported zero-violation claim')
        checks.update({key:count(value,key) for key,value in audit['checks'].items()})
        audit_records.append(dict(attempt=attempt,documents=len(selected),raw_audit_doc_ids=sorted(raw),
                                  witness_files=files,expanded_outputs=expanded,theory_applicable_outputs=applicable,
                                  code_mismatches=audit.get('code_mismatches'),raw_theory_violations=audit.get('raw_theory_violations')))
    require(seen_attempts == set(attempt_by_path) and audited_docs == ids and raw_seen == required_raw,
            'independent audit attempt/document/raw sets are not complete')
    if complete:
        require(len(paths) == 25 and len(raw_seen) == 15, 'full target requires25 generic audits and15 preselected raw documents')
    for domain,metrics in aggregate['distributions'].items():
        for stat in metrics.values():
            for point in stat['quantiles'].values():
                require(not (domain == 'fixed_quota_pool' or not complete) or point.get('interval') is None,
                        'pooled/partial confidence interval cannot be published')
    contract_source = identity(CONTRACT)
    return dict(schema='m005_user_numerical_report_v1',execution_state='report_generated',
                report_kind='full_collection' if complete else 'partial_preview',full_collection=complete,
                numerical_acceptance_verdict='not_assigned; completion and zero observed audit violations are not fidelity acceptance',
                planned_documents=1024,measured_documents=n,missing_documents=1024-n,
                domain_counts=dict(actual_domains),domain_targets=DOMAINS,
                independent_unit='operational source-document cluster; population iid/semantic independence not verified',
                actual_token_range=[min(row['tokens'] for row in docs),max(row['tokens'] for row in docs)],
                model_scope='one Llama-3.1-8B-Instruct checkpoint,32-layer prefill,max128 real unpadded tokens; no decode/long-context/task-score claim',
                changed_factor='additional intermediate arithmetic rounding only; same weights,base quantization,Hadamard,LUT/coefficients and common exits',
                local_maximum='per document,per family maximum over all32 layers and all required sites; five-family overall maximum excludes unmeasured operations',
                distributions=aggregate['distributions'],zero_infinite_unestimable_policy=dict(original_zero_zero_ratio='null',
                    exact_zero_document_bound='0,explicit all_zero_exact count',unbounded='null value with unbounded flag; included after all finite values',
                    unestimable='not omitted; no successful-subset primary quantile'),
                audits=dict(generic_reports=len(paths),accepted_attempts=len(attempts),audited_documents=len(audited_docs),
                            planned_raw_documents=15,observed_raw_documents=len(raw_seen),raw_doc_ids=sorted(raw_seen),
                            full32_raw_hidden_documents=len(independent_full_hidden),raw_hidden_tensors=hidden_saved,
                            witness_by_family=witness,expanded_outputs=sum(row['expanded'] for row in witness.values()),
                            theory_applicable_outputs=sum(row['applicable'] for row in witness.values()),
                            excluded_outputs=sum(row['excluded'] for row in witness.values()),
                            code_mismatches=0 if any(row['files'] for row in witness.values()) else None,
                            raw_theory_violations=0 if any(row['applicable'] for row in witness.values()) else None,
                            checks=dict(checks),attempts=audit_records,independent_auditor_sha256=source_sha),
                limitations=['SwiGLU and Host conversion diagnostics do not provide complete independent raw witness coverage',
                             'aggregate counters do not establish strict numerical eligibility per output',
                             'G/K-dependent bounds only within their stated domain; no universal fidelity threshold',
                             'same-input local comparisons differ from two recomputed continuous trajectories',
                             'relative L2 is numerical deviation,not ACC/PPL or task noninferiority',
                             'fixed-quota pooled quantiles descriptive; within-domain rank CIs conditional on unverified iid and pointwise only'],
                overview_files=image_sources,
                source_files=[identity(aggregate_path),identity(overview_path),plans[0],stream_source,contract_source,
                              own_source,*audit_sources,identity(__file__)],theory_contract=contract_source)


def value_text(point):
    if point is None:return '不可估'
    if point.get('state') == 'unbounded':return '∞'
    value=point.get('value')
    if value is None:return point.get('value_decimal') or '不可估'
    return f'{value:.4g}%'


def quantile(stat,p):
    return value_text(stat.get('quantiles',{}).get(p))


def markdown(summary):
    n=summary['measured_documents'];complete=summary['full_collection'];audits=summary['audits']
    pool=summary['distributions']['fixed_quota_pool'];title='数值精度实测报告' if complete else '数值精度部分预览'
    lines=[f'# {title}：已测 {n}/1024 篇文本','',
        (f"已完整采集1024篇：网页512、新闻256、影评256，{audits['generic_reports']}份独立审核报告与全部GPU批次一一对应。" if complete else
         f"当前只完成{n}/1024篇，仍缺{1024-n}篇；网页{summary['domain_counts'].get('web',0)}/512、新闻{summary['domain_counts'].get('news',0)}/256、影评{summary['domain_counts'].get('reviews',0)}/256。本页是资格预览，不是完整目标结论。"),
        '执行完成和已检查见证中的零违例，只说明采集与限定范围核查完成；本报告不据此判定“精度保持通过”。','',
        '比较两路只改变额外的中间算术舍入，保持同一checkpoint权重、基础量化、Hadamard变换、查表与系数、算子出口规则。参考保留中间精度后采用共同出口。局部比较固定同一输入；连续传播两路各自重算激活量化，后续量化码可以随误差改变。','',
        '相对L2误差定义为 `100 × ‖当前实现 − 参考‖₂ / ‖参考‖₂`。它衡量数值偏差，不等于准确率ACC，也不说明任务表现或困惑度PPL不变。本次不重跑任务评分。','',
        '每篇文本先在每类算子的全部32层、全部调用位置取最大相对误差，再在文本之间计算分位数。下表为固定域配额合池的描述值；五类中的总最大仅覆盖这些已测算子，并非全部软件操作。','',
        '| 算子类别 | 中位数（50%） | 95%分位 | 99%分位 |','|---|---:|---:|---:|']
    for key,label in FAMILIES.items():
        stat=pool['local_'+key];lines.append(f"| {label} | {quantile(stat,'p50')} | {quantile(stat,'p95')} | {quantile(stat,'p99')} |")
    final=pool['final_normalization_bound'];overall=pool['local_five_family_bound']
    lines += ['',f"五类算子总最大误差的文档中位数为{quantile(overall,'p50')}，95%分位为{quantile(overall,'p95')}，99%分位为{quantile(overall,'p99')}。最终归一化后隐藏向量误差的相应分位数为{quantile(final,'p50')}、{quantile(final,'p95')}、{quantile(final,'p99')}。32层传播分布与逐文档结果保存在聚合原件。",'']
    image=next(row for row in summary['overview_files'] if Path(row['path']).suffix=='.png')
    pdf=next(row for row in summary['overview_files'] if Path(row['path']).suffix=='.pdf')
    lines += [f"[查看双图PNG]({image['path']}) · [下载PDF]({pdf['path']})",'',
        ("已完成目标的域内秩置信区间仅在文档簇独立同分布这一未验证假设下成立，并且是逐指标、逐分位的点态区间，不是所有类别/域同时95%保证。固定网页/新闻/影评配额的合池始终只作描述统计。" if complete else
         "由于当前仅是部分目标，本页不发布完整目标置信区间，也不将小样本的99%分位解释为总体尾部保证。固定域配额合池仅作描述。"),
        '统计单位是源文档簇；文本/URL去重不证明总体独立同分布或语义独立。层、调用位置、token和标量均不能当作新增独立文本。','',
        f"预定原始张量审计子集为15篇，本次已覆盖其中{audits['observed_raw_documents']}篇；其中{audits['full32_raw_hidden_documents']}篇完成全部32层隐藏输出的原数组复算，其余按冻结存储策略复核所保存层。全量文档的统计覆盖、来源、输入身份和公式检查，与该子集的原始数组/整数及Fraction独立复算是不同证据范围，不能互相替代。",'',
        f"五类节点见证共展开{audits['expanded_outputs']:,}个输出，其中理论界适用{audits['theory_applicable_outputs']:,}个，排除{audits['excluded_outputs']:,}个；三类计数分别保留。排除项按原始掩码或资格原因单列，不计入理论界适用分母；结构掩码坐标也不计入有效输出误差统计，已接受的异常输出仍保留主统计与异常计数。见证码不一致计数为{audits['code_mismatches'] if audits['code_mismatches'] is not None else '无见证，未评价'}，适用域理论违例计数为{audits['raw_theory_violations'] if audits['raw_theory_violations'] is not None else '无适用输出，未评价'}。这些结果不构成全模型精度验收。",'',
        '原相对比值0/0保持空值；所有所需位置均为精确零匹配时，最小非负误差约束为0并另列计数。零参考但非零误差记为无穷并进入扩展排序；缺失、非法或不可估项不会被删除后对其余样本求主分位数。各域和合池的零值、无穷、不可估计数保存在summary.json。','',
        f"适用范围为同一Llama-3.1-8B-Instruct模型、32层prefill、最多128个真实未补齐token；本批实际长度为{summary['actual_token_range'][0]}–{summary['actual_token_range'][1]}。不延伸到decode、长上下文、其他模型或任务分数。SwiGLU与Host转换保留共同路径/诊断，尚缺完整独立原始见证覆盖；聚合审计计数也不等于逐输出严格数值域资格。",'',
        f"条件误差界、组数/序列长度前提和正式统计定义以[冻结的v3数值合同]({summary['theory_contract']['path']})为准；本报告不重写或扩大该理论证明。源文件及输出SHA256见summary.json和report_manifest.json。",'']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate',type=Path,required=True)
    parser.add_argument('--audit',type=Path,action='append',required=True)
    parser.add_argument('--overview-source',type=Path,required=True)
    parser.add_argument('--allow-partial',action='store_true')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    summary=build_summary(args.aggregate,args.audit,args.overview_source,allow_partial=args.allow_partial)
    text=markdown(summary)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    require(not any(args.output_dir.iterdir()),'use a new empty report directory')
    report=args.output_dir/'numerical_report.md'
    with report.open('x') as handle:handle.write(text)
    summary['output_files']=[identity(report)]
    target=args.output_dir/'summary.json'
    with target.open('x') as handle:json.dump(summary,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n')
    manifest=dict(schema='m005_numerical_report_identity_v1',source_files=summary['source_files'],
                  output_files=[identity(report),identity(target)],note='external manifest avoids a circular self-hash')
    with (args.output_dir/'report_manifest.json').open('x') as handle:json.dump(manifest,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps(dict(output=str(args.output_dir.resolve()),kind=summary['report_kind'],measured=summary['measured_documents'],planned=1024,
                          audit_reports=summary['audits']['generic_reports'],outputs=manifest['output_files']),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
