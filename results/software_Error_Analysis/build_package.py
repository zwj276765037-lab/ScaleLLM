#!/usr/bin/env python3
"""Rebuild the CPU-only software-error evidence package, or verify a relocated copy.

No models, CUDA, inference, large tensors, caches, or execution logs are copied.
Existing files with different content are never overwritten. The controller owns
the top-level README/report/acceptance documents; this script does not write them.
"""
from pathlib import Path
import argparse, csv, hashlib, html, io, json, math, os, re, sys, time
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
SECTIONS = ['01_full1024', '02_attention_mlp_layer32', '03_top1_margin',
            '04_qualitative_100', '05_layer32_diagnosis']

def identity(path):
    p = Path(path).resolve()
    h = hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda: f.read(8 << 20), b''):
            h.update(data)
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': h.hexdigest()}

def encode_json(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')

def encode_csv(rows):
    f = io.StringIO(newline='')
    writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return f.getvalue().encode('utf-8')

def quantile(values, q):
    x = sorted(values)
    i = (len(x) - 1) * q
    lo = math.floor(i)
    hi = math.ceil(i)
    return x[lo] if lo == hi else x[lo] + (x[hi] - x[lo]) * (i - lo)

def verify(output):
    manifest = json.loads((output / 'package_sources.json').read_text())
    for entry in manifest['files']:
        got = identity(output / entry['destination'])
        assert got['sha256'] == entry['destination_sha256'], entry['destination']
        assert got['bytes'] == entry['destination_bytes'], entry['destination']
    errors = verify_links(output)
    assert not errors, errors
    print(json.dumps({'verification': 'PASS', 'listed_files': len(manifest['files']),
                      'listed_bytes': sum(e['destination_bytes'] for e in manifest['files']),
                      'broken_or_nonportable_local_links': errors,
                      'source_files_required_for_verification': False}, ensure_ascii=False))

def local_target(target):
    raw = html.unescape(target.strip())
    if raw.startswith('<') and raw.endswith('>'):
        raw = raw[1:-1]
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return unquote(parsed.path), parsed.fragment

MD_LINK = re.compile(r'(!?\[[^\]\n]*\]\()(<[^>\n]+>|[^)\n]+)(\))')
HTML_LINK = re.compile(r'((?:href|src)\s*=\s*["\'])([^"\']+)(["\'])', re.I)

def text_links(text, suffix):
    regex = HTML_LINK if suffix == '.html' else MD_LINK
    for match in regex.finditer(text):
        yield match.group(2)

def verify_links(output):
    errors = []
    for section in SECTIONS:
        for p in (output / section).rglob('*'):
            if p.suffix not in ['.md', '.html']:
                continue
            for raw in text_links(p.read_text(), p.suffix):
                target = local_target(raw)
                if target is None:
                    continue
                rel, fragment = target
                resolved = (p.parent / rel).resolve()
                if Path(rel).is_absolute() or not resolved.is_relative_to(output.resolve()) or not resolved.exists():
                    errors.append({'file': str(p.relative_to(output)), 'target': raw})
    return errors

def build(project, output):
    started = time.monotonic()
    runs = project / 'project/E012_multistage_rounding_precision/experiment_results/runs'
    r6, r10, r11 = [runs / name for name in ['R006', 'R010', 'R011']]
    a6 = r6 / 'analysis'
    q = a6 / 'top1_margin_qualitative_sample_seed20261020_n100'
    roster = []
    def add(source, dest, scope):
        source = Path(source).resolve()
        assert source.is_file(), f'Missing required source: {source}'
        assert source.stat().st_size < 128 * (1 << 20), f'Unexpected large source: {source}'
        assert source.suffix.lower() in ['.json', '.jsonl', '.csv', '.tsv', '.md', '.html', '.png']
        assert dest.split('/')[0] in SECTIONS
        assert dest not in [r['destination'] for r in roster]
        roster.append({'source': source, 'destination': dest, 'scope': scope})
    def group(source_dir, names, dest_dir, scope):
        for name in names:
            add(source_dir / name, f'{dest_dir}/{name}', scope)

    group(a6 / 'aggregate_v2', ['integrated_aggregate.json', 'tv_aggregate.json',
          'per_position_tv.csv', 'per_document_tv.csv'], '01_full1024', '1024 documents /103700 real positions')
    add(a6 / 'layer_propagation_explanation/summary.json', '01_full1024/layer_propagation_summary.json', '1024 documents /32 layers + final norm/logits')
    add(a6 / 'png_v3/final_precision.png', '01_full1024/final_precision.png', 'Final approved full1024 figure; original image bytes')
    add(a6 / 'png_v3/source_data.json', '01_full1024/final_precision_source_data.json', 'All full1024 plotted source data')
    group(r6 / 'session_S001', ['analysis_manifest.json', 'session_gpu_receipt.json', 'session_launch_manifest.json'],
          '01_full1024/provenance', 'Original formal R006 session provenance; no weights/tensors')
    aggregate = json.loads((a6 / 'aggregate_v2/integrated_aggregate.json').read_text())
    tv = json.loads((a6 / 'aggregate_v2/tv_aggregate.json').read_text())
    def source_ref(record):
        path = Path(record['path'])
        # Permit rebuilding from the same project evidence tree at a new root.
        if '/project/' in str(path):
            path = project / 'project' / str(path).split('/project/', 1)[1]
        got = identity(path)
        assert got['sha256'] == record['sha256'], path
        return path
    for field, name in [('input_manifest', 'analysis_inputs.json'), ('formal_plan', 'formal_batch_plan.json'),
                        ('formal_stream', 'frozen_document_stream.json')]:
        add(source_ref(aggregate[field]), '01_full1024/provenance/' + name, 'Inherited formal input roster/plan; hashes retained')
    session_plan = source_ref(tv['plan'])
    if session_plan not in [r['source'] for r in roster]:
        add(session_plan, '01_full1024/provenance/r006_session_plan.json', 'R006 formal complete TV session plan')

    branch = r11 / 'branch_comparison'
    group(branch, ['pure_branch_comparison_v3.png', 'report_v2.md', 'summary.json', 'pure_branch_AB.csv',
          'per_document_pure_branch_AB.csv', 'mlp_AB_stages.csv', 'mlp_separate_trajectories.csv'],
          '02_attention_mlp_layer32', 'Only3 diagnostic documents /299 positions; before residual addition')
    group(r11 / 'independent_review', ['branch_comparison_review.json', 'gated_product_decomposition.json',
          'requantization_evidence.json'], '02_attention_mlp_layer32/independent_review', 'Independent CPU checks of3-document branch comparison')
    margin = a6 / 'top1_margin_stratification'
    group(margin, ['report.md', 'reference_logit_margin_top1_flips.png', 'buckets.csv', 'positions.csv',
          'top1_flips.csv', 'summary.json', 'protocol.json', 'validation.json', 'independent_csv_checks.json',
          'highest_margin_flips_top20.csv', 'high_margin_flips_ge1.csv', 'source_manifest.json', 'document_checks.csv'],
          '03_top1_margin', 'Full1024 /103700 positions /1053 top1 flips; reference raw-logit margin')
    add(a6 / 'top1_margin_independent_review.json', '03_top1_margin/top1_margin_independent_review.json', 'Independent full margin-stratification review')
    group(q, ['protocol.json', 'sample_manifest.json', 'samples.jsonl', 'samples.csv', 'review_packet.md',
          'review_packet.jsonl', 'validation.json', 'eligible_pool_keys.json', 'scope_clarification.json',
          'decode_source_manifest.json', 'document_identity_checks.json'],
          '04_qualitative_100', 'Seed20261020 simple-random100 of876 low-margin flips;93 documents')
    group(q / 'reconciled', ['report.md', 'review.html', 'annotated_samples.csv', 'annotations.jsonl',
          'summary.json', 'adjudication.json', 'artifact_manifest.json'],
          '04_qualitative_100/reconciled', 'Final reconciled100 local qualitative AI reviews;16 adjudicated cases')
    group(q / 'root_annotation', ['rubric.json', 'annotations_v1.jsonl', 'manual_annotations.tsv',
          'summary_v1.json', 'sampling_reproduction.json'],
          '04_qualitative_100/root_annotation', 'Frozen initial controller review and sampling reproduction')
    group(q / 'independent_annotation', ['rubric.md', 'annotations_v1.jsonl', 'summary_v1.json', 'review_note.md'],
          '04_qualitative_100/independent_annotation', 'Frozen initial independent AI review')

    round_dir = r10 / 'attempts/AT002_cpu_full_raw_analysis/analysis'
    group(round_dir, ['report.md', 'scalar_summary.json', 'scalar_threshold_table.csv', 'before_after_examples.csv',
          'independent_checks.json', 'existing1024_source_link.json'],
          '05_layer32_diagnosis/rounding_audit_15docs', 'Same-input original o/down exits;15 audit documents /1746 positions /14303232 scalars')
    group(r10 / 'analysis_existing', ['full1024_output_differences.json', 'full1024_compact_summary.csv',
          'full1024_output_differences_per_document.csv'],
          '05_layer32_diagnosis', 'Existing1024 same-F16 integer-exit differences; separate from15-document relative-loss audit')
    group(r10 / 'attempts/AT001_original_two_exit_scalar_audit', ['manifest.json', 'external_wait_receipt.json'],
          '05_layer32_diagnosis/rounding_provenance', 'Original bounded R010 replay input and actual exit receipts; no raw arrays')
    causal = r11 / 'attempts/AT003_cpu_causal_analysis/analysis'
    group(causal, ['report.md', 'causal_summary.json', 'stage_metrics.csv', 'independent_raw_checks.json'],
          '05_layer32_diagnosis/causal_diagnostic_3docs', 'Four trajectories and conditional suffix interventions;3 documents /299 positions')
    group(r11 / 'attempts/AT002_singleblock_fourway_v2', ['result.json', 'external_wait_receipt.json'],
          '05_layer32_diagnosis/causal_provenance', 'Original single-block R011 result/actual exit receipts; no raw arrays')
    add(r11 / 'root_analysis/layer32_error_location.png', '05_layer32_diagnosis/layer32_error_location.png', 'Existing full1024 stage-location figure; unchanged PNG')
    add(r11 / 'root_analysis/plot_sources.json', '05_layer32_diagnosis/layer32_error_location_plot_sources.json', 'Existing full1024 figure source identities')
    group(r10 / 'independent_review', ['scalar_audit_review.json', 'delivered_host_review.json',
          'output_differences_review.json', 'relative_tail_diagnostic.json'],
          '05_layer32_diagnosis/independent_review/R010', 'Independent R010 scalar/Host/full1024 checks; scopes retained')
    group(r11 / 'independent_review', ['actual_singleblock_review.json', 'existing_stage_review.json',
          'residual_cross_review.json', 'accumulation_explanation.json'],
          '05_layer32_diagnosis/independent_review/R011', 'Independent R011 three-case and existing full1024 checks; scopes retained')

    # Freeze every source before writing a destination. Old evidence remains read-only.
    for entry in roster:
        entry['source_identity'] = identity(entry['source'])
    missing = [str(e['source']) for e in roster if not e['source'].is_file()]
    assert not missing, missing
    mapping = {e['source']: output / e['destination'] for e in roster}
    mapping[(branch / 'pure_branch_comparison_v2.png').resolve()] = output / '02_attention_mlp_layer32/pure_branch_comparison_v3.png'
    files = []
    def put(relative, data):
        p = output / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            assert p.read_bytes() == data, f'Refusing to overwrite differing destination: {p}'
        else:
            with p.open('xb') as f:
                f.write(data)
        return p
    def rewrite(data, source, dest):
        text = data.decode('utf-8')
        edits = []
        regex = HTML_LINK if source.suffix == '.html' else MD_LINK
        def change(match):
            raw = match.group(2)
            target = local_target(raw)
            if target is None:
                return match.group(0)
            path, fragment = target
            resolved = (source.parent / path).resolve()
            if resolved not in mapping:
                raise AssertionError(f'Unpackaged report link: {source} -> {raw}; add its compact source explicitly')
            replacement = os.path.relpath(mapping[resolved], dest.parent).replace(os.sep, '/')
            if fragment:
                replacement += '#' + fragment
            if replacement != raw:
                reason = 'Make copied report link portable within package'
                if resolved.name == 'pure_branch_comparison_v2.png':
                    reason += '; point obsolete v2 image link to approved final v3, image/statistics unchanged'
                edits.append({'original_target': raw, 'package_target': replacement, 'reason': reason})
            return match.group(1) + replacement + match.group(3)
        return regex.sub(change, text).encode('utf-8'), edits
    for e in roster:
        data = e['source'].read_bytes()
        edits = []
        if e['source'].suffix in ['.md', '.html']:
            data, edits = rewrite(data, e['source'], output / e['destination'])
        p = put(e['destination'], data)
        got = identity(p)
        transformed = got['sha256'] != e['source_identity']['sha256']
        assert not transformed or edits, e['destination']
        if p.suffix == '.png':
            assert not transformed
        files.append({'destination': e['destination'], 'destination_bytes': got['bytes'],
                      'destination_sha256': got['sha256'], 'kind': 'copied',
                      'source': e['source_identity'], 'transformed': transformed,
                      'transformations': edits, 'scope': e['scope']})

    # Derive readable numeric tables without running the model or altering evidence.
    docs = aggregate['documents']
    assert len(docs) == aggregate['measured_documents'] == 1024
    assert sum(d['tokens'] for d in docs) == tv['real_positions'] == 103700
    assert aggregate['domain_counts'] == {'web': 512, 'news': 256, 'reviews': 256}
    assert tv['vocabulary'] == 128256 and tv['score_pairs'] == 13300147200
    aggregate_id = identity(a6 / 'aggregate_v2/integrated_aggregate.json')
    tv_id = identity(a6 / 'aggregate_v2/tv_aggregate.json')
    layer_id = identity(a6 / 'layer_propagation_explanation/summary.json')
    def generated(name, data, inputs, method, scope):
        if isinstance(data, str):
            data = data.encode('utf-8')
        p = put(name, data)
        got = identity(p)
        files.append({'destination': name, 'destination_bytes': got['bytes'], 'destination_sha256': got['sha256'],
                      'kind': 'derived', 'sources': inputs, 'method': method, 'scope': scope,
                      'transformed': True, 'transformations': [{'reason': method}]})
    labels = {
        'attention_linear': ('Attention四个线性投影', 128, '同输入局部差；Q/K/V/O四投影×32层，共128 sites'),
        'rope': ('RoPE', 64, '同输入局部差；Q/K两路×32层，共64 sites'),
        'qk': ('QK', 32, '同输入局部差；32层各1 site'),
        'softmax': ('Attention Softmax', 32, '同输入局部差；32层各1 site；不是最终词表Softmax TV'),
        'pv': ('PV', 32, '同输入局部差；32层各1 site'),
        'gate_proj': ('MLP Gate投影', 32, '同输入局部差；32层各1 site'),
        'up_proj': ('MLP Up投影', 32, '同输入局部差；32层各1 site'),
        'down_proj': ('MLP Down投影', 32, '同输入局部差；32层各1 site'),
        'gating_exit_loss': ('门控乘积含共同出口损失', 32, '实际LUT输出×Up的精确未舍入乘积，对比实际S32/F16共同出口；包含共享出口损失，非单独额外中间舍入'),
        'whole_mlp': ('整个MLP固定入口局部差', 32, '固定同一MLP入口；参考分支在内部重算动态量化；不是两条全轨迹纯MLP分支误差'),
        'fixed_residual': ('MLP加固定残差后的局部差', 32, '固定同一second-residual base，只比较MLP变化后的和；不是整层单算子'),
        'final_hidden': ('Final norm后Hidden', 1, '同一文本前缀下当前/参考全轨迹，32层后再经final norm'),
        'logits': ('全词表Logits', 1, '同一文本前缀下当前/参考全轨迹，共同FP32输出头，全128256词表'),
    }
    assert list(aggregate['distributions']['fixed_quota_pool']) == list(labels)
    operator_rows = []
    for category, (label, sites, scope) in labels.items():
        distribution = aggregate['distributions']['fixed_quota_pool'][category]
        assert distribution['documents'] == 1024
        assert distribution['finite'] == 1024 and distribution['unbounded'] == distribution['unestimable'] == 0
        values = [d['columns'][category]['value'] for d in docs]
        row = {'metric': category, '名称': label, '口径': scope,
               '单位': 'relative L2 percent:100*||current-reference||2/||reference||2',
               '文档数': 1024, '每文档site数': sites,
               '文档内归约': '跨预定义sites取最大tensor relativeL2' if sites > 1 else '文档全tensor relativeL2',
               '统计权重': '1024文档等权描述分布；无无条件CI',
               '有限文档数': distribution['finite'], '无界文档数': distribution['unbounded'],
               '不可估文档数': distribution['unestimable']}
        for label_q, key, qv in [('P50_percent', 'p50', .5), ('P95_percent', 'p95', .95),
                                  ('P99_percent', 'p99', .99), ('max_percent', 'maximum', 1)]:
            value = distribution[key]['value']
            assert math.isclose(value, quantile(values, qv), abs_tol=1e-12, rel_tol=1e-12)
            row[label_q] = value
        operator_rows.append(row)
    assert len(operator_rows) == 13 and docs[0]['columns']['whole_mlp']['max_coordinate'][0] == 2
    generated('01_full1024/operator_error_summary.csv', encode_csv(operator_rows), [aggregate_id],
              'Reformat all13 frozen metric distributions, preserving units/site reductions and exact stored numeric values', '1024 documents; first11 per-document maxima across sites; last2 free trajectories')
    propagation = json.loads((a6 / 'layer_propagation_explanation/summary.json').read_text())
    layer_rows = []
    for i, stage in enumerate(propagation['stages']):
        if i < 32:
            values = [d['propagation'][i]['ratio']['value'] for d in docs]
            assert all(d['propagation'][i]['layer'] == i for d in docs)
            stage_scope = '完整轨迹；此decoder输出，尚未final norm'
        else:
            category = ['final_hidden', 'logits'][i - 32]
            values = [d['columns'][category]['value'] for d in docs]
            stage_scope = '完整轨迹；final norm后' if i == 32 else '完整轨迹；共同FP32输出头全词表'
        assert math.isclose(quantile(values, .5), stage['median_percent'], abs_tol=1e-12)
        assert math.isclose(quantile(values, .95), stage['p95_percent'], abs_tol=1e-12)
        layer_rows.append({'stage': stage['stage'], '层号从1开始': i + 1 if i < 32 else '',
                           'layer_index从0开始': i if i < 32 else '', '文档数': 1024,
                           '口径': stage_scope, '单位': 'relative L2 percent', '统计权重': 'document equal weight',
                           'P50_percent': quantile(values, .5), 'P95_percent': quantile(values, .95),
                           'P99_percent': quantile(values, .99), 'max_percent': max(values)})
    assert len(layer_rows) == 34
    generated('01_full1024/layer_error_summary.csv', encode_csv(layer_rows), [aggregate_id, layer_id],
              'Per-document layer ratios; empirical linear quantiles; add P99 from all1024 saved document ratios', '32 decoder outputs plus final norm/logits;1024 documents')
    coverage = []
    for i, row in enumerate(aggregate['vocabulary_coverage']):
        assert row['score_total_count'] == 13300147200 and row['document_total_count'] == 1024
        assert sum(d['logits']['score_within_threshold_counts'][i] for d in docs) == row['score_within_count']
        assert sum(d['logits']['max_abs_logit_delta'] <= row['epsilon'] for d in docs) == row['document_within_count']
        coverage.append({**row, '阈值定义': 'abs(current_logit-reference_logit)<=epsilon',
                         'epsilon单位': '原始logit单位；非概率/百分比/相对误差',
                         'score_coverage_fraction': row['score_within_count'] / row['score_total_count'],
                         'score_coverage_percent': 100 * row['score_within_count'] / row['score_total_count'],
                         'document_all_scores_within_fraction': row['document_within_count'] / 1024,
                         'document_all_scores_within_percent': 100 * row['document_within_count'] / 1024})
    generated('01_full1024/vocabulary_coverage.csv', encode_csv(coverage), [aggregate_id],
              'Preserve complete12 threshold counts and calculate score/document coverage ratios with separate denominators', 'Full13300147200 logit pairs and1024 documents')
    top1 = dict(aggregate['top1'])
    assert sum(d['logits']['top1_match_count'] for d in docs) == top1['token_weighted_match_count'] == 102647
    top1.update({'documents': 1024, 'positions': 103700, 'vocabulary': 128256,
                 'token_weighted_flip_count': 1053, 'token_weighted_flip_rate_fraction': 1053 / 103700,
                 'token_weighted_flip_rate_percent': 100 * 1053 / 103700,
                 'token_weighted_agreement_percent': 100 * top1['token_weighted_agreement'],
                 'document_equal_weight_mean_agreement_percent': 100 * top1['document_equal_weight_mean'],
                 'definition': 'Fixed source-text prefixes; current top1 vocabulary ID differs from reference top1 ID. This is numerical agreement, not task accuracy.',
                 'tie_break': 'smallest vocabulary ID', 'source': aggregate_id})
    generated('01_full1024/top1_summary.json', encode_json(top1), [aggregate_id],
              'Retain original top1 fields and add1053 flip count plus explicitly weighted percentages', 'Full1024 /103700 positions; not semantic accuracy')
    tv_rows = []
    for pool_name, pool in tv['distributions'].items():
        for metric, weight, definition in [
                ('document_mean_tv', 'document equal weight', '先逐文档平均TV，再对文档均值取分布'),
                ('document_max_tv', 'document equal weight', '先逐文档最大TV，再对文档最大值取分布'),
                ('position_weighted_tv', 'position equal weight /length weighted across documents', '所有真实位置TV直接合池；长文档权重较大')]:
            row = pool[metric]
            out = {'pool': pool_name, 'metric': metric, '统计单位数': row['n'], '权重': weight,
                   '定义': definition, 'TV定义': '0.5*sum_vocab(abs(p_current-p_reference)),temperature=1',
                   'fraction单位': 'probability mass fraction', 'percent单位': '100*TV probability mass fraction'}
            for k in ['mean', 'p50', 'p95', 'p99', 'max']:
                out[k + '_fraction'] = row[k]
                out[k + '_percent'] = 100 * row[k]
            tv_rows.append(out)
    generated('01_full1024/TV_summary.csv', encode_csv(tv_rows), [tv_id],
              'Separate position-weighted TV, document mean TV and document maximum TV; keep all-pool/domain rows and fraction/percent units', '1024 documents /103700 positions; fixed-quota descriptive distributions')

    readmes = {
        '01_full1024': """# 全1024篇数值误差与词表统计

范围为 Llama-3.1-8B-Instruct 的32层、固定真实文本前缀；web512/news256/reviews256，共103700位置、128256词表。没有任务ACC/PPL或自由生成结论。

- [最终Python图](final_precision.png) 与 [全部图源数据](final_precision_source_data.json)。PNG逐字节复制。
- [完整1024文档aggregate](integrated_aggregate.json) 保留每文档13项指标、32层传播及logit覆盖。13项读表见 [operator_error_summary.csv](operator_error_summary.csv)。前11项先在每文档跨预定义sites取最大tensor relative L2，再汇总1024文档分布，不能解释为第32层或所有scalar的合池误差。Attention四投影×32=128 sites，RoPE两路×32=64，其余各32。
- `whole_mlp` 固定同一MLP入口，参考内部重算动态量化；`fixed_residual` 固定同一second-residual base，只比较MLP变化后的和，均非自由轨迹整体归因。`gating_exit_loss` 比较实际LUT输出×Up的精确未舍入乘积与S32/F16共同出口，包含共享出口损失。最后两项final_hidden/logits才是配对完整轨迹。
- [逐层P50/P95/P99/max](layer_error_summary.csv) 包含32个decoder输出、final norm和logits；[旧传播说明](layer_propagation_summary.json) 保留原始说明。所有relative L2数值单位是百分数。
- [词表覆盖](vocabulary_coverage.csv) 的epsilon是原始logit单位，条件为绝对logit差不超过epsilon；score比例分母为13300147200，document比例要求一篇内全部score均满足，分母1024。
- [Top1统计](top1_summary.json)：102647/103700匹配、1053翻转，只表示数值Top1一致性。
- [TV摘要](TV_summary.csv) 明确分离位置等权与文档等权；[TV完整JSON](tv_aggregate.json)、[每位置CSV](per_position_tv.csv)、[每文档CSV](per_document_tv.csv) 全保留。TV fraction是概率质量，百分数为100×TV，不是relative L2。
- `provenance/` 保存正式session、输入roster与冻结计划。JSON中的原始绝对source paths与SHA原样保留；其中13项/coverage/Top1继承R005已冻结数据，经R006全部1024旧head指标和final hidden身份一致后合并，TV为R006实测。没有复制模型权重/原始tensor。

固定配额集合仅作描述统计，未把位置或词表项视为独立文档，未新增无条件置信区间。所有文件来源和副本SHA见 [package_sources.json](../package_sources.json)。
""",
        '02_attention_mlp_layer32': """# 第32层Attention与MLP纯分支比较

仅3篇预声明诊断文档、299位置，每个纯分支1224704个数值；两分支均在残差相加前测量。不能标成1024篇纯分支比较：全1024缺同口径Attention自由轨迹分支原始统计。

入口见 [最终v3 Python图](pure_branch_comparison_v3.png)、[报告](report_v2.md) 和 [summary.json](summary.json)。纯分支、逐文档、MLP阶段、分开轨迹的4份CSV完整保留。报告副本只将旧v2图链接改到最终v3图，数值不改。

报告/CSV中 AB 是当前与参考完整轨迹；AC固定同一第32层入口比较两种算术；CB保留前31层不同输入、使用参考块。三者有交叉项，不可把AC变化移植为AB因果效应。OUTPUT_ONLY仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口和Host。

独审JSON在 `independent_review/`。MLP绝对RMSE高于Attention，同时参考RMS更大，而相对L2更低；尺度变化本身不是舍入因果放大的证明。来源/SHA见 [清单](../package_sources.json)。
""",
        '03_top1_margin': """# 参考Logit Margin分层：全1024篇

完整1024篇、103700位置、1053个Top1翻转。Margin=参考最高logit减第二高logit，温度1、softmax前的原始logit单位；不是概率差或百分比。

查看 [报告](report.md)、[最终Python图](reference_logit_margin_top1_flips.png)、[分桶表](buckets.csv)。`positions.csv`保留103700行，`top1_flips.csv`保留1053行。空的高Margin≥1翻转清单也保留表头；另有最大Margin20条。固定protocol、所有源SHA与独立CSV/全量独审记录均保留，未隐藏零翻转桶。

分桶为[0,.01)、[.01,.05)、[.05,.1)、[.1,.2)、[.2,.5)、[.5,1)、[1,2)、[2,∞)。并列零Margin单独校验但不重复计总数；空桶翻转率为NA。统计只描述此固定数据。来源/SHA见 [清单](../package_sources.json)。
""",
        '04_qualitative_100': """# 低Margin翻转100例：固定随机抽样与两次评阅

从Margin<0.05的876个翻转中，以random.Random(20261020).sample抽100个不同位置，先按(doc_id,整数position)排序。样本名单在解码前冻结；100例来自93篇文档：web54、reviews33、news13。

- [最终定性报告](reconciled/report.md)、[可搜索完整HTML](reconciled/review.html)、[最终100行CSV](reconciled/annotated_samples.csv)、[16例分歧裁决](reconciled/adjudication.json)。两次独立AI初始标签84例一致，初始rubric/100条标签/summary分别保存在root_annotation与independent_annotation，未用裁决覆盖初标。
- [原评阅包](review_packet.md) 隐藏原文下一token；[完整样本JSONL](samples.jsonl) 和CSV保留全部已保存prefix、两候选单token repr与联合decode。logits位置t预测下一token，prefix严格为input_ids[:t+1]。只追加一个候选，无真实suffix拼接和自由生成。
- [固定抽样manifest](sample_manifest.json)、[protocol](protocol.json)、[独立抽样复现](root_annotation/sampling_reproduction.json) 和 [数据核验](validation.json) 保留。原文实际next token仅是辅助，不能当金标；本样本100例均能从已存artifact取得。`scope_clarification.json`记录不再额外重分词的授权变更。

这是局部定性AI审阅，不是独立人工标注或任务准确率；不能把未知后续归为无害，也不能认定候选差别等于回答错误。两位评阅最初探查均意外看到S001辅助next字段，最终报告保留此限制。来源/SHA见 [清单](../package_sources.json)。
""",
        '05_layer32_diagnosis': """# 第32层定位与两出口逐数舍入核验

本目录保留三个不同范围，不混作同一全量因果测量：

- `rounding_audit_15docs/`：[报告](rounding_audit_15docs/report.md)、完整scalar_summary、阈值与原→后值CSV。仅15篇预声明audit文档、1746位置；o/down各7151616个scalar，总14303232。相同保存CURRENT量化输入，区分final cut8、total unrounded-reference loss、同F16出口额外中间舍入差与Host FP32转换；非零原值才进入直接相对误差分母。不能外推为1024篇逐值相对比例。
- [已有1024篇离散出口差](full1024_output_differences.json)：current对同F16 OUTPUT_ONLY出口，所有变化为−1/65536；它不是未舍入原数前/后损失，范围独立保留，附逐文档CSV。
- `causal_diagnostic_3docs/`：[报告](causal_diagnostic_3docs/report.md)、四轨迹分解/逐stage统计。仅3篇、299位置，固定保存hidden30重放第32层，并做条件后缀干预；用于区分本层新增舍入与上游输入差异传播。AC/CB能量有交叉项，不可解释成可加的固定归因百分比。参考仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口与Host。

[跳变位置Python图](layer32_error_location.png) 使用已有全1024统计，PNG原样复制。主要证据支持MLP残差合并是relative误差跳升点：信号两路相消而误差几乎不相消；不能把它误说为FP32加法自身舍入大。两出口自身舍入小也不等于全32层某量化算子全局因果占比已确定。

`independent_review/`分别保存R010/R011关键独审；`rounding_provenance/`和`causal_provenance/`是原有范围输入/结果与实际退出回执，没有复制模型或raw tensor。来源/SHA见 [清单](../package_sources.json)。
""",
    }
    for section, text in readmes.items():
        generated(section + '/README.md', text, [], 'New short package navigation and explicit measurement-scope/unit notes', section)
    # Include the reproducible builder itself; do not copy or overwrite controller-owned top-level prose.
    script_data = Path(__file__).read_bytes()
    target_script = put('build_package.py', script_data)
    files.append({'destination': 'build_package.py', 'destination_bytes': len(script_data),
                  'destination_sha256': hashlib.sha256(script_data).hexdigest(), 'kind': 'package_builder',
                  'source': identity(Path(__file__)), 'transformed': False, 'transformations': [],
                  'scope': 'CPU-only explicit-source rebuild and relocated-package SHA/link verification'})
    for e in roster:
        assert identity(e['source']) == e['source_identity'], f'Source changed during package build: {e["source"]}'
    manifest = {
        'schema': 'software_error_analysis_evidence_package_v1',
        'experiment': 'E012_multistage_rounding_precision',
        'source_project_root': str(project), 'package_root_at_build': str(output),
        'execution': 'CPU-only data copying/formatting; no GPU/model/EDA/inference',
        'source_boundary': 'Old sources read-only; no historical report/summary changes; no model weights, large raw tensors, caches or logs copied',
        'controller_owned_excluded_from_this_manifest': ['README.md', '完整分析报告.md', '验收记录 and any controller acceptance files'],
        'manifest_self_excluded_from_SHA_inventory': True,
        'JSON_source_paths_preserved_for_provenance': True,
        'all_PNG_bytes_equal_sources': True,
        'readable_report_links': 'Relative links within package; only link destinations transformed, source files unchanged',
        'source_files_unchanged_after_copy': True,
        'summary_checks': {'documents': 1024, 'positions': 103700, 'vocabulary': 128256,
                           'logit_pairs': 13300147200, 'top1_flips': 1053,
                           'operator_categories': 13, 'layer_stages': 34,
                           'pure_branch_documents': 3, 'pure_branch_positions': 299,
                           'scalar_audit_documents': 15, 'qualitative_sample': 100},
        'files': files,
        'file_count_excluding_self_and_controller_files': len(files),
        'total_bytes_excluding_self_and_controller_files': sum(e['destination_bytes'] for e in files),
    }
    put('package_sources.json', encode_json(manifest))
    verify(output)
    print(json.dumps({'build_state': 'completed', 'pid': os.getpid(),
                      'wall_seconds': time.monotonic() - started,
                      'file_count_including_manifest_excluding_controller_files': len(files) + 1,
                      'total_bytes_including_manifest_excluding_controller_files': sum(e['destination_bytes'] for e in files) + (output / 'package_sources.json').stat().st_size,
                      'copied_files': sum(e['kind'] == 'copied' for e in files),
                      'transformed_report_files': [e['destination'] for e in files if e['kind'] == 'copied' and e['transformed']],
                      'manifest': str(output / 'package_sources.json')}, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=HERE.parents[1])
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.verify_only:
        verify(args.output.resolve())
    else:
        build(args.project_root.resolve(), args.output.resolve())

if __name__ == '__main__':
    main()
