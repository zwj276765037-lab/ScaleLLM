"""Integrated figure from reviewed B001 evidence; no model forward or GPU."""
from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import subprocess

COLUMNS = (
    ('attention_linear', '线性投影', ('q_proj', 'k_proj', 'v_proj', 'o_proj')),
    ('rope', '旋转位置编码', ('query_rope', 'key_rope')),
    ('qk', '注意力打分', ('qk',)),
    ('softmax', '概率归一化', ('softmax',)),
    ('pv', '注意力加权', ('pv',)),
    ('gate_proj', '门投影', ('gate_proj',)),
    ('up_proj', '上投影', ('up_proj',)),
    ('down_proj', '下投影', ('down_proj',)),
    ('final_hidden', '整体输出误差', ()),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def bound(state, value=None, **extra):
    return dict(state=state, value=float(value) if value is not None else None,
                value_decimal=str(value) if value is not None else None, **extra)


def local_bound(row):
    m = row['metrics']['current_vs_reference']
    e, s = Decimal(str(m['error_energy'])), Decimal(str(m['signal_energy']))
    if (not e.is_finite() or not s.is_finite() or e < 0 or s < 0
            or m['valid_elements'] <= 0 or m['nonfinite_elements'] != 0):
        return bound('unestimable', reason='invalid_energy_or_domain')
    if s == 0:
        require(m['relative_l2_percent'] is None, 'zero reference ratio must remain null')
        if e == 0:
            return bound('finite', Decimal(0), exact_zero_match=True,
                         original_relative_l2_percent=None)
        return bound('unbounded', reason='zero_reference_nonzero_error')
    with localcontext() as ctx:
        ctx.prec = 60
        ratio = Decimal(100) * (e / s).sqrt()
    original = m['relative_l2_percent']
    require(original is not None and math.isclose(float(ratio), original, rel_tol=1e-12, abs_tol=1e-14),
            'original local ratio disagrees with raw energy')
    return bound('finite', ratio, exact_zero_match=False, original_relative_l2_percent=original)


def maximum(rows):
    pairs = [(row, local_bound(row)) for row in rows]
    if any(b['state'] == 'unestimable' for _, b in pairs):
        return bound('unestimable', reason='required_position_invalid', required_positions=len(rows),
                     observed_unbounded=any(b['state'] == 'unbounded' for _, b in pairs))
    if any(b['state'] == 'unbounded' for _, b in pairs):
        return bound('unbounded', reason='zero_reference_nonzero_error', required_positions=len(rows))
    value = max(Decimal(b['value_decimal']) for _, b in pairs)
    winners = [row for row, b in pairs if Decimal(b['value_decimal']) == value]
    winner = min(winners, key=lambda r: (r['layer'], r['node'], r['op']))
    return bound('finite', value, required_positions=len(rows),
                 all_zero_exact=all(b.get('exact_zero_match', False) for _, b in pairs),
                 exact_zero_match_positions=sum(b.get('exact_zero_match', False) for _, b in pairs),
                 max_coordinate={key: winner[key] for key in ('layer', 'node', 'op')},
                 tie_count=len(winners), argmax_metrics=winner['metrics']['current_vs_reference'])


def quantile(points, probability):
    if any(p['state'] == 'unestimable' for p in points):
        return bound('unestimable', reason='required_document_invalid')
    values = sorted(Decimal('Infinity') if p['state'] == 'unbounded' else Decimal(p['value_decimal']) for p in points)
    with localcontext() as ctx:
        ctx.prec = 60
        rank = (len(values) - 1) * Decimal(probability)
        lo = int(rank)
        fraction = rank - lo
        if not fraction:
            result = values[lo]
        elif values[lo].is_infinite() or values[lo + 1].is_infinite():
            result = Decimal('Infinity')
        else:
            result = values[lo] + fraction * (values[lo + 1] - values[lo])
    return bound('unbounded', reason='positive_weight_on_infinity') if result.is_infinite() else bound('finite', result)


def collect(attempt):
    paths = dict(local=attempt / 'local_tensor_metrics.jsonl',
                 aggregate=attempt / 'aggregate_v1/formal_aggregate.json',
                 audit=attempt / 'independent_audit/generic_v2.json')
    a = json.loads(paths['aggregate'].read_text())
    audit = json.loads(paths['audit'].read_text())
    require(a['execution_state'] == 'completed' and a['completed_documents'] == 16,
            'this figure requires reviewed completed B00116 evidence')
    require(audit['execution_state'] == 'completed' and audit['review'] == 'limited_evidence_verified'
            and audit['formal_eval_documents'] == 16, 'completed limited-evidence review required')
    require(Path(audit['attempt']).resolve() == attempt.resolve(), 'review attempt mismatch')
    require(a['failed_supplied_attempts'] == a['invalid_supplied_attempts'] == 0, 'failed evidence cannot be silently omitted')
    docs = a['documents']
    ids = {doc['doc_id'] for doc in docs}
    require(len(ids) == len(docs) == 16 and len({doc['duplicate_cluster'] for doc in docs}) == 16,
            'document/cluster accounting invalid')
    rows = [json.loads(line) for line in paths['local'].read_text().splitlines()]
    require(len(rows) == 16 * 384 and {row['doc_id'] for row in rows} == ids, 'local evidence coverage invalid')
    columns = []
    for key, label, ops in COLUMNS:
        points = []
        for doc in docs:
            meta = {name: doc[name] for name in ('doc_id', 'duplicate_cluster', 'domain', 'tokens')}
            if key == 'final_hidden':
                value = doc['final_normalization']['constraint_bound']
                meta['original_relative_error'] = doc['final_normalization']['relative_error']
            else:
                selected = [row for row in rows if row['doc_id'] == doc['doc_id'] and row['op'] in ops]
                require(len(selected) == 32 * len(ops), 'missing/duplicate required local site')
                require({(row['layer'], row['op']) for row in selected} == {(layer, op) for layer in range(32) for op in ops},
                        'required layer/op coordinates differ')
                require(all(row['trajectory'] == 'v5_current_local_paired'
                            and row['node_metadata']['comparison'] == 'current_vs_output_only_common_exit' for row in selected),
                        'incorrect local comparison')
                value = maximum(selected)
                if key in ('rope', 'qk', 'softmax', 'pv'):
                    published = doc['local_family_bounds'][key]
                    require(value['state'] == published['state'], 'published aggregate state differs')
                    if value['state'] == 'finite':
                        require(math.isclose(value['value'], published['value'], rel_tol=1e-14), 'published aggregate bound differs')
            points.append({**meta, 'bound': value})
        values = [point['bound'] for point in points]
        columns.append(dict(key=key, label=label, included_ops=list(ops), document_points=points,
                            per_document_required_positions=32 * len(ops) if ops else 1,
                            statistics=dict(p50=quantile(values, '.5'), p95=quantile(values, '.95'), maximum=quantile(values, '1')),
                            definition='same-input local tensor error, maximum over required32-layer sites' if ops else
                            'free-running paired final-normalized hidden vector; not logits or language-model head'))
    return dict(schema='m005_integrated_numerical_precision_v1',
                measured_documents=16, planned_documents=a['planned_documents'],
                missing_documents=a['missing_documents'], target_state='partial',
                input_attempt=identity(paths['audit'])['path'].rsplit('/independent_audit/', 1)[0],
                review='limited_evidence_verified; five-family raw audit on one preselected document, not full independent replay of all outputs',
                comparison='current versus retained-intermediate-precision reference, same base quantization/LUTs/common exits',
                local_denominator='all accepted real coordinates; no claim of strict per-output-domain qualification',
                independent_unit='document cluster; semantic/iid independence not verified',
                percentiles='linear interpolation over document bounds; descriptive only, no CI',
                zero_rules='local0/0 ratio remains null; exact-zero match imposes no bound; all-zero exact bound=0; nonzero error over zero reference=unbounded; invalid/missing=unestimable; no filtering/epsilon',
                columns=columns, input_identities={key: identity(path) for key, path in paths.items()},
                renderer_identity=identity(__file__),
                unmeasured=dict(
                    vocabulary_score_coverage=dict(state='not_measured', values=None, epsilon_grid=None,
                        definition='For each document d: max over same-prefix token positions t and all vocabulary entries v of abs(current_logits-reference_logits). Coverage(epsilon) is the proportion of documents whose maximum is <=epsilon.',
                        missing='full-vocabulary paired logits; no measured curve or value'),
                    top1_agreement=dict(state='not_measured', values=None,
                        definition='For each document, fraction of same-prefix token positions with equal argmax over full-vocabulary logits; summarize across documents, not generated divergent prefixes.',
                        missing='paired full-vocabulary highest-score token identities; no measured value'),
                    silu=dict(state='not_independently_measured'),
                    elementwise_gating_product=dict(state='not_independently_measured'),
                    entire_mlp_branch=dict(state='not_independently_measured'),
                    mlp_residual=dict(state='not_independently_measured')),
                missing_items=['full-vocabulary score-error coverage', 'same-prefix highest-score token agreement',
                               'independent SiLU', 'independent elementwise gating multiply', 'independent entire MLP branch', 'independent MLP residual'])


def draw(data, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager, pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    from matplotlib.patches import FancyBboxPatch
    font = subprocess.check_output(['fc-match', '-f', '%{file}', 'Noto Sans CJK SC'], text=True).strip()
    font_manager.fontManager.addfont(font)
    family = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({'font.family': family, 'font.size': 10.5, 'pdf.fonttype': 42,
                         'axes.unicode_minus': False, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#A6AFBC'})
    ink, gray, blue, orange = '#152D45', '#8796A6', '#27659A', '#C86E24'
    fig = plt.figure(figsize=(16, 9.8))
    grid = fig.add_gridspec(2, 2, left=.075, right=.975, bottom=.12, top=.79,
                           height_ratios=[3.0, 1.28], hspace=.45, wspace=.1)
    ax = fig.add_subplot(grid[0, :])
    left, right = fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])
    fig.suptitle('数值精度与预测一致性', y=.975, fontsize=21, fontweight='bold', color=ink)
    fig.text(.525, .927, '已审核16篇；词表指标待补测', ha='center', fontsize=13, color='#566779')
    fig.legend(handles=[Line2D([], [], marker='o', color=gray, linestyle='', label='每篇文本'),
                        Line2D([], [], marker='o', color=blue, linestyle='', markersize=7, label='中位数（50%文本）'),
                        Line2D([], [], marker='D', color=orange, linestyle='', markersize=7, label='95%文本分位值')],
               loc='upper center', bbox_to_anchor=(.525, .899), ncol=3, frameon=False, columnspacing=3, fontsize=11)
    ax.set_yscale('log')
    positive = [point['bound']['value'] for column in data['columns'] for point in column['document_points']
                if point['bound']['state'] == 'finite' and point['bound']['value'] > 0]
    lower, upper = (min(positive) / 1.9, max(positive) * 2.0) if positive else (1e-6, 1)
    ax.set_ylim(lower, upper)
    positions = [0, 1, 2, 3, 4, 5.3, 6.3, 7.3, 8.75]
    ax.set_xlim(-.55, 9.42)
    ax.axvspan(-.55, 4.67, color='#F2F6FB', zorder=0)
    ax.axvspan(4.67, 7.95, color='#F0F7F3', zorder=0)
    ax.axvspan(7.95, 9.42, color='#FFF3E3', zorder=0)
    for boundary in (4.67, 7.95):
        ax.axvline(boundary, color='#B8C4CB', lw=.9)
    for x, title in ((2.0, '注意力：同输入局部误差'), (6.3, '前馈网络：同输入局部误差'), (8.75, '自由传播终点')):
        ax.text(x, 1.07, title, transform=ax.get_xaxis_transform(), ha='center', color=ink, fontsize=11.5, fontweight='bold')
    rendered = []
    for x, column in zip(positions, data['columns']):
        counts = dict(finite_positive=0, zero=0, unbounded=0, unestimable=0)
        for point in column['document_points']:
            b = point['bound']
            jitter = (int(hashlib.sha256(point['doc_id'].encode()).hexdigest()[:8], 16) / 0xffffffff - .5) * .38
            if b['state'] == 'finite':
                value = b['value']
                require(value is not None and math.isfinite(value) and value >= 0, 'unrepresentable finite plot value')
                y, marker = (value, 'o') if value > 0 else (lower * 1.1, 'v')
                counts['finite_positive' if value > 0 else 'zero'] += 1
            elif b['state'] == 'unbounded':
                y, marker = upper / 1.2, '^'
                counts['unbounded'] += 1
            else:
                y, marker = lower * 1.1, 'x'
                counts['unestimable'] += 1
            ax.scatter(x + jitter, y, s=24, marker=marker, color=gray, alpha=.64, edgecolors='none' if marker != 'x' else None, zorder=3)
        for key, offset, color, marker in (('p50', -.065, blue, 'o'), ('p95', .065, orange, 'D')):
            q = column['statistics'][key]
            if q['state'] == 'finite':
                y = q['value'] if q['value'] > 0 else lower * 1.1
                text = f"{q['value']:.3g}%"
            elif q['state'] == 'unbounded':
                y, text = upper / 1.2, '∞'
            else:
                ax.text(x, upper / 1.3, '不可估', ha='center', fontsize=9)
                continue
            ax.scatter(x + offset, y, s=65, marker=marker, color=color, edgecolors='white', linewidths=.7, zorder=5)
            if key == 'p95':
                ax.annotate(text, (x + offset, y), xytext=(0, 13), textcoords='offset points', ha='center',
                            color=orange, fontsize=10.5, fontweight='bold')
        require(sum(counts.values()) == data['measured_documents'], 'lost document points')
        rendered.append(dict(key=column['key'], counts=counts, total_document_points=sum(counts.values())))
    ax.set_xticks(positions, [column['label'] for column in data['columns']], fontsize=10.3)
    ax.tick_params(axis='x', length=0, pad=10)
    ax.set_ylabel('相对数值误差（%，对数坐标）', labelpad=11, fontsize=11)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:g}'))
    ax.grid(axis='y', which='major', color='#D8E1E9', lw=.7)
    ax.set_axisbelow(True)

    for panel, title in ((left, '全词表分数误差的覆盖率'), (right, '最高分词一致率')):
        panel.set_axis_off()
        panel.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle='round,pad=0.014,rounding_size=.025',
                                      transform=panel.transAxes, linewidth=.8, edgecolor='#CED7E0', facecolor='#F8FAFC', clip_on=False))
        panel.text(.035, .83, title, fontsize=12.5, fontweight='bold', color=ink, transform=panel.transAxes)
        panel.text(.035, .59, '待补测 · 尚无实测曲线或数值', fontsize=11.5, color='#8A653C', transform=panel.transAxes)
    left.text(.035, .31, '对每篇文本，取所有位置、全词表的最大绝对分数差；', fontsize=10.2, color='#566779', transform=left.transAxes)
    left.text(.035, .12, '覆盖率 = 该最大绝对差不超过允许误差 ε 的文档比例。', fontsize=10.2, color='#566779', transform=left.transAxes)
    right.text(.035, .31, '使用同一文本前缀，比较每个位置的最高分词；', fontsize=10.2, color='#566779', transform=right.transAxes)
    right.text(.035, .12, '先算每篇文本的一致比例，再按文档汇总。', fontsize=10.2, color='#566779', transform=right.transAxes)
    fig.text(.075, .073, '前八列：每篇文本跨32层及该类调用取最大误差；第九列：最终归一化隐藏向量，非词表分数。每列16点，分位值不是置信区间。', fontsize=9.5, color=ink)
    fig.text(.075, .045, '相对误差 = 100 × ‖当前实现 − 参考‖ / ‖参考‖；参考保留中间精度、使用共同出口。SiLU、门控乘法、整个MLP及残差尚无独立记录。', fontsize=9.3, color='#566779')
    png, pdf = output / 'integrated_precision.png', output / 'integrated_precision.pdf'
    fig.savefig(png, dpi=230, facecolor='white')
    fig.savefig(pdf, facecolor='white')
    plt.close(fig)
    return dict(total_document_points=sum(row['total_document_points'] for row in rendered), columns=rendered,
                matplotlib_version=matplotlib.__version__, font=identity(font), font_family=family,
                size_inches=[16, 9.8], dpi=230, placeholder_measurements_drawn=False,
                no_logit_curves_or_values=True, confidence_intervals=False,
                outputs=[identity(png), identity(pdf)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    data = collect(args.attempt.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in ('integrated_precision.png', 'integrated_precision.pdf', 'source_data.json'):
        require(not (args.output_dir / name).exists(), 'existing artifacts must remain immutable')
    data['render'] = draw(data, args.output_dir)
    require(data['render']['total_document_points'] == 9 * 16, 'wrong total figure point count')
    with (args.output_dir / 'source_data.json').open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(document_points=data['render']['total_document_points'], measured_documents=16,
                          word_score_metrics='not_measured', output_dir=str(args.output_dir.resolve())), ensure_ascii=False))


if __name__ == '__main__':
    main()
