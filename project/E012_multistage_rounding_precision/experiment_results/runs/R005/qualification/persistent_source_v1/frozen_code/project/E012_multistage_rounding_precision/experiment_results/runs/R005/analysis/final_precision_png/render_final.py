"""Matplotlib PNG only. Requires a fully audited R0051024 aggregate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

LABELS = ('线性投影', '旋转位置\n编码', '注意力\n打分', '概率\n归一化', '注意力\n加权',
          '门投影', '上投影', '下投影', '门控乘积\n出口损失', '整个MLP\n分支', '同残差\n相加后',
          '最终隐藏\n向量', '全词表\n分数')
KEYS = ('attention_linear', 'rope', 'qk', 'softmax', 'pv', 'gate_proj', 'up_proj', 'down_proj',
        'gating_exit_loss', 'whole_mlp', 'fixed_residual', 'final_hidden', 'logits')
POSITIONS = (0, 1, 2, 3, 4, 5.2, 6.2, 7.2, 8.45, 9.7, 10.7, 12.1, 13.3)


def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def draw(aggregate, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager, pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    source = identity(aggregate)
    data = json.loads(Path(aggregate).read_text())
    require(data['schema'] == 'm005_r005_final_precision_aggregate_v1' and data['execution_state'] == 'completed'
            and data['target_complete'] is True and data['measured_documents'] == data['planned_documents'] == 1024
            and data['missing_documents'] == 0, 'final PNG cannot use development or partial data')
    documents = data['documents']
    require(len(documents) == 1024 and len({d['doc_id'] for d in documents}) == 1024, 'complete unique document points required')
    require(len(data['accepted_groups']) == data['actual_group_count'] > 0, 'actual audited groups required; no hardcoded group count')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), 'new empty PNG output directory required')
    font = subprocess.check_output(['fc-match', '-f', '%{file}', 'Noto Sans CJK SC'], text=True).strip()
    font_manager.fontManager.addfont(font)
    family = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({'font.family': family, 'font.size': 10, 'axes.unicode_minus': False,
                         'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#A6AFBC'})
    ink, gray, blue, orange = '#152D45', '#8F9CAA', '#27659A', '#C86E24'
    figure = plt.figure(figsize=(18.5, 11.6))
    grid = figure.add_gridspec(2, 2, left=.065, right=.975, top=.81, bottom=.17,
                              height_ratios=[2.6, 1.2], hspace=.55, wspace=.3)
    axis = figure.add_subplot(grid[0, :])
    cover = figure.add_subplot(grid[1, 0])
    top1_axis = figure.add_subplot(grid[1, 1])
    figure.suptitle('数值精度与预测一致性', y=.968, fontsize=23, fontweight='bold', color=ink)
    figure.text(.52, .926, '1024篇固定文本 · 全32层 · 相同文本前缀 · 最多128个实际词元', ha='center', fontsize=13, color='#566779')
    figure.legend(handles=[Line2D([], [], marker='o', color=gray, linestyle='', markersize=4, label='每篇文本'),
                           Line2D([], [], marker='o', color=blue, linestyle='', markersize=7, label='中位数（50%文本）'),
                           Line2D([], [], marker='D', color=orange, linestyle='', markersize=7, label='95%文本分位值')],
                  loc='upper center', bbox_to_anchor=(.52, .897), ncol=3, frameon=False, columnspacing=3.2, fontsize=11)
    positive = [d['columns'][key]['value'] for d in documents for key in KEYS
                if d['columns'][key]['state'] == 'finite' and d['columns'][key]['value'] > 0]
    lower, upper = (min(positive) / 1.8, max(positive) * 2.0) if positive else (1e-6, 1.)
    axis.set_yscale('log')
    axis.set_ylim(lower * .66, upper)
    axis.set_xlim(-.55, 13.9)
    groups = [(-.55, 4.6, 2, '#F2F6FB', '注意力：同输入局部'),
              (4.6, 7.8, 6.2, '#F0F7F3', '前馈投影'),
              (7.8, 9.05, 8.45, '#FFF0F0', '共同出口'),
              (9.05, 11.4, 10.2, '#F0F7F3', '整分支干预'),
              (11.4, 13.9, 12.7, '#FFF3E3', '连续路径')]
    for left, right, center, color, title in groups:
        axis.axvspan(left, right, color=color, zorder=0)
        if left > -.55:
            axis.axvline(left, color='#BCC8CE', lw=.8)
        axis.text(center, 1.07, title, transform=axis.get_xaxis_transform(), ha='center', color=ink, fontsize=11.2, fontweight='bold')
    render_counts = []
    for position, key in zip(POSITIONS, KEYS):
        buckets = {'finite_positive': [], 'zero': [], 'unbounded': [], 'unestimable': []}
        for doc in documents:
            bound = doc['columns'][key]
            jitter = (int(hashlib.sha256(doc['doc_id'].encode()).hexdigest()[:8], 16) / 0xffffffff - .5) * .43
            if bound['state'] == 'finite':
                require(bound['value'] is not None and math.isfinite(bound['value']) and bound['value'] >= 0,
                        'finite value is not representable for plotting')
                bucket = 'finite_positive' if bound['value'] > 0 else 'zero'
            else:
                bucket = bound['state']
            require(bucket in buckets, 'unknown bound state')
            buckets[bucket].append((position + jitter, bound['value']))
        for name, points in buckets.items():
            if not points:
                continue
            xs = [x for x, _ in points]
            ys = [y for _, y in points] if name == 'finite_positive' else [lower * .77 if name in ('zero', 'unestimable') else upper / 1.15] * len(points)
            marker = {'finite_positive': 'o', 'zero': 'v', 'unbounded': '^', 'unestimable': 'x'}[name]
            artist = axis.scatter(xs, ys, s=5 if name == 'finite_positive' else 12, marker=marker,
                                  color=gray, alpha=.15 if name == 'finite_positive' else .45, linewidths=0, zorder=2)
            require(len(artist.get_offsets()) == len(points), 'point dropped in rendering')
        if buckets['zero']:
            axis.text(position, lower * .67, f"0：{len(buckets['zero'])}", ha='center', va='bottom', fontsize=8)
        if buckets['unbounded']:
            axis.text(position, upper / 1.05, f"∞：{len(buckets['unbounded'])}", ha='center', va='top', fontsize=8)
        if buckets['unestimable']:
            axis.text(position, lower * .67, f"不可估：{len(buckets['unestimable'])}", ha='center', fontsize=8)
        statistics = data['distributions']['fixed_quota_pool'][key]
        for stat, offset, color, marker in [('p50', -.06, blue, 'o'), ('p95', .06, orange, 'D')]:
            point = statistics[stat]
            if point['state'] == 'finite':
                y = point['value'] if point['value'] > 0 else lower * .77
                label = f"{point['value']:.3g}%"
            elif point['state'] == 'unbounded':
                y, label = upper / 1.15, '∞'
            else:
                axis.text(position, upper / 1.1, '不可估', ha='center', color=orange, fontsize=9)
                continue
            axis.scatter(position + offset, y, color=color, marker=marker, s=51, edgecolors='white', linewidths=.7, zorder=5)
            if stat == 'p95':
                axis.annotate(label, (position + offset, y), xytext=(0, 12), textcoords='offset points',
                              ha='center', color=orange, fontweight='bold', fontsize=9.7)
        render_counts.append(dict(category=key, total_points=sum(len(x) for x in buckets.values()),
                                  **{name: len(points) for name, points in buckets.items()}))
    axis.set_xticks(POSITIONS, LABELS, fontsize=9.5)
    axis.tick_params(axis='x', length=0, pad=9)
    axis.set_ylabel('相对数值误差（%，对数坐标）', fontsize=11, labelpad=10)
    axis.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:g}'))
    axis.grid(axis='y', which='major', color='#D8E1E9', lw=.7)
    axis.set_axisbelow(True)

    coverage = data['vocabulary_coverage']
    eps = [row['epsilon'] for row in coverage]
    require(eps and min(eps) > 0, 'positive predeclared threshold grid required')
    cover.plot(eps, [100 * row['score_within_count'] / row['score_total_count'] for row in coverage],
               '-o', color=blue, ms=4, lw=1.7, label='所有词表分数（分数计数）')
    cover.plot(eps, [100 * row['document_within_count'] / row['document_total_count'] for row in coverage],
               '-s', color=orange, ms=4, lw=1.7, label='每篇全部分数（文档计数）')
    cover.set_xscale('log')
    cover.set_ylim(0, 103)
    cover.set_title('全词表分数误差的覆盖率', loc='left', fontsize=13, fontweight='bold', color=ink, pad=12)
    cover.set_xlabel('允许的绝对分数差 ε（对数坐标）', labelpad=7)
    cover.set_ylabel('满足条件的比例（%）')
    cover.grid(axis='y', color='#E2E7EC', lw=.7)
    cover.legend(loc='lower right', frameon=False, fontsize=9)
    cover.text(0, -.37, f"分数分母：{coverage[0]['score_total_count']:,} 对；文档分母：1024篇（每篇取全位置、全词表最大绝对差）。",
               transform=cover.transAxes, fontsize=8.7, color='#566779')
    top1 = data['top1']
    proportions = [top1['document_equal_weight_mean'], top1['token_weighted_agreement'], top1['all_positions_match_document_fraction']]
    bars = top1_axis.bar(range(3), [100 * x for x in proportions], width=.5, color=[blue, '#6A91AD', orange], alpha=.92)
    for bar, proportion in zip(bars, proportions):
        top1_axis.annotate(f'{100 * proportion:.4g}%', (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                           xytext=(0, 5), textcoords='offset points', ha='center', fontsize=10, color=ink)
    top1_axis.set_ylim(0, 110)
    top1_axis.set_yticks([0, 25, 50, 75, 100])
    top1_axis.set_xticks(range(3), ['每篇文本等权', '全部位置合计', '整篇全部一致'], fontsize=10)
    top1_axis.set_ylabel('最高分词一致率（%）')
    top1_axis.set_title('最高分词一致率：相同文本前缀', loc='left', fontsize=13, fontweight='bold', color=ink, pad=12)
    top1_axis.grid(axis='y', color='#E2E7EC', lw=.7)
    top1_axis.set_axisbelow(True)
    top1_axis.text(0, -.37, f"文档等权N=1024；位置一致 {top1['token_weighted_match_count']:,}/{top1['token_weighted_total_count']:,}；"
                   f"整篇一致 {top1['all_positions_match_documents']}/1024。", transform=top1_axis.transAxes, fontsize=8.7, color='#566779')
    mismatch = sum(doc['silu_semantic_counts'].get('product_common_exit_mismatch', 0) for doc in documents)
    overflow = sum(doc['silu_semantic_counts'].get('product_s32_overflow', 0) for doc in documents)
    figure.text(.065, .104, '上图：局部类别每篇跨32层取最大值；整体两列为自由传播终点。门控出口损失对同LUT精确乘积，其余局部对共同出口参考。', fontsize=9.4, color=ink)
    figure.text(.065, .076, f'SiLU同表/地址语义与实际乘积已测：不符 {mismatch}，越界 {overflow}；此核验不表示解析SiLU近似损失为零。', fontsize=9.4, color='#566779')
    figure.text(.065, .048, '相对误差 = 100 × ‖当前 − 参考‖ / ‖参考‖。文档为统计单位；固定域配额合池仅描述，无无条件置信保证；预测一致性不等于任务准确率。', fontsize=9.2, color='#566779')
    png = output / 'final_precision.png'
    figure.savefig(png, dpi=240, facecolor='white')
    plt.close(figure)
    require(sum(row['total_points'] for row in render_counts) == 13 * 1024, 'all13312 document points required')
    final_source = dict(schema='m005_r005_final_precision_png_source_v1', measured_documents=1024, planned_documents=1024,
                        target_complete=True, aggregate_source=source, renderer_source=identity(__file__),
                        categories=list(KEYS), all_document_points=[dict(doc_id=doc['doc_id'], domain=doc['domain'], tokens=doc['tokens'],
                            columns=doc['columns']) for doc in documents],
                        descriptive_quantiles=data['distributions'], vocabulary_coverage=coverage, top1=top1,
                        reference_notes=data['reference_notes'], accepted_groups=data['accepted_groups'],
                        render=dict(columns=render_counts, total_document_points=13 * 1024,
                            font=identity(font), matplotlib_version=matplotlib.__version__, size_inches=[18.5, 11.6], dpi=240,
                            zero_points='explicit0 display band only, no numeric epsilon added',
                            unbounded_points='explicit infinity top markers', unestimable_points='explicit invalid markers; no successful-subset quantiles',
                            no_unconditional_ci=True), output=identity(png))
    with (output / 'source_data.json').open('x') as stream:
        json.dump(final_source, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    with (output / 'output_manifest.json').open('x') as stream:
        json.dump(dict(aggregate=source, renderer=identity(__file__), outputs=[identity(png), identity(output / 'source_data.json')]), stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    draw(args.aggregate, args.output_dir)


if __name__ == '__main__':
    main()
