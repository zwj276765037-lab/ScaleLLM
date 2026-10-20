"""A compact, traceable two-panel view of measured development documents.

Only reads existing worker evidence.  It writes an additional PNG/PDF and the
complete plotted source data to a new directory; it does not change old plots,
metric records, or summaries.  No Torch, model loading, or GPU work is involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess


NODE_ORDER = ('linear', 'rope', 'qk', 'softmax', 'pv')
NODE_LABELS = ('线性层\nLinear', '旋转位置编码\nRoPE', '注意力打分\nQK', '概率归一化\nSoftmax', '注意力加权\nPV')
OP_LABELS = {'q_proj': '查询投影', 'k_proj': '键投影', 'v_proj': '值投影',
             'o_proj': '输出投影', 'gate_proj': '门控投影', 'up_proj': '升维投影',
             'down_proj': '降维投影', 'query_rope': '查询', 'key_rope': '键'}


def file_identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def read_jsonl(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def metric_row(row):
    metric = row['metrics']['current_vs_reference']
    signal, error = metric['signal_energy'], metric['error_energy']
    count = metric['valid_elements']
    value = metric['relative_l2_percent']
    if not count or not signal > 0 or not error >= 0 or value is None or not math.isfinite(value):
        raise ValueError('overview requires nonempty finite metrics with positive signal')
    recomputed = 100 * math.sqrt(error / signal)
    if not math.isclose(value, recomputed, rel_tol=1e-12, abs_tol=1e-14):
        raise ValueError('stored relative L2 does not match preserved signal/error energies')
    return dict(doc_id=row['doc_id'], layer_zero_based=row['layer'], layer_display=row['layer'] + 1,
                node=row['node'], op=row['op'], relative_l2_percent=value,
                accepted_elements=count, total_elements=metric['total_elements'],
                signal_energy=signal, error_energy=error,
                exact_pre_output_comparison=row.get('exact_pre_output_comparison', False),
                strict_valid_available=row.get('strict_valid_available', False))


def collect_data(attempt):
    attempt = Path(attempt).resolve()
    names = ('local_tensor_metrics.jsonl', 'tensor_metrics.jsonl')
    local_raw = read_jsonl(attempt / names[0])
    continuous_raw = read_jsonl(attempt / names[1])
    sources = [attempt / name for name in names]
    docs = {row['doc_id'] for row in local_raw + continuous_raw}
    if not 1 <= len(docs) <= 4:
        raise ValueError('this development overview supports one to four distinct documents')
    if any(row.get('evidence_role') != 'development' for row in local_raw + continuous_raw):
        raise ValueError('this development-check figure requires development-only evidence')
    if any(row.get('trajectory') != 'v5_current_local_paired' for row in local_raw):
        raise ValueError('unexpected local trajectory')
    if any(row.get('trajectory') != 'v5_continuous_paired' or row.get('node') != 'decoder_hidden' for row in continuous_raw):
        raise ValueError('unexpected propagation trajectory or output node')
    final_by_doc, input_by_doc = {}, {}
    legacy_final = attempt / 'final_norm_comparison.json'
    if legacy_final.is_file() and len(docs) == 1:
        final_raw = json.loads(legacy_final.read_text())
        if final_raw.get('measured_documents') != 1 or final_raw.get('formal_eval_documents') != 0:
            raise ValueError('unexpected legacy final-normalization denominator')
        doc_id = next(iter(docs))
        final_by_doc[doc_id] = dict(doc_id=doc_id, layer=31, node='final_norm', op='final_norm',
                                   metrics=final_raw['metrics'], scope=final_raw['scope'])
        order = [doc_id]
        maximum_tokens = None
        sources.append(legacy_final)
    else:
        result_path = attempt / 'paired_result.json'
        result = json.loads(result_path.read_text())
        if result.get('execution_state') != 'completed' or result.get('measured_documents') != len(docs) or result.get('formal_eval_documents') != 0:
            raise ValueError('multi-document plotting requires completed development-only evidence')
        order = [row['doc_id'] for row in result['documents']]
        if len(order) != len(docs) or len(set(order)) != len(order) or set(order) != docs:
            raise ValueError('completed document list and tensor metrics differ')
        maximum_tokens = result['maximum_tokens']
        sources.append(result_path)
        for path in sorted((attempt / 'documents').glob('doc*/final_norm_comparison.json')):
            final_raw = json.loads(path.read_text())
            input_path = path.parent / 'input_identity.json'
            identity = json.loads(input_path.read_text())
            doc_id = final_raw['doc_id']
            if doc_id in final_by_doc or identity['doc_id'] != doc_id:
                raise ValueError('duplicate or mismatched final-normalization document')
            report = next((row for row in result['documents'] if row['doc_id'] == doc_id), None)
            if report is None or report['tokens'] != identity['tokens']:
                raise ValueError('document result and real token identity differ')
            final_by_doc[doc_id], input_by_doc[doc_id] = final_raw, identity
            sources.extend((path, input_path))
        if set(final_by_doc) != docs:
            raise ValueError('not every document has a final-normalization endpoint')
    documents, local, continuous, maxima, finals = [], [], [], [], []
    clusters = []
    for index, doc_id in enumerate(order):
        doc_local_raw = [row for row in local_raw if row['doc_id'] == doc_id]
        doc_cont_raw = [row for row in continuous_raw if row['doc_id'] == doc_id]
        doc_local = [metric_row(row) for row in doc_local_raw]
        doc_cont = sorted((metric_row(row) for row in doc_cont_raw), key=lambda row: row['layer_zero_based'])
        if [row['layer_zero_based'] for row in doc_cont] != list(range(32)):
            raise ValueError('each document must contain every one of the 32 layers exactly once')
        shapes = {tuple(row['output_shape']) for row in doc_cont_raw}
        if len(shapes) != 1:
            raise ValueError('layer output shapes differ within a document')
        shape = next(iter(shapes))
        if len(shape) != 3 or shape[0] != 1 or not 1 <= shape[1] <= 128:
            raise ValueError('expected real unpadded [1,tokens,channels] output')
        if doc_id in input_by_doc and input_by_doc[doc_id]['tokens'] != shape[1]:
            raise ValueError('actual tokens and propagation shape differ')
        cluster_values = {row.get('duplicate_cluster') for row in doc_local_raw + doc_cont_raw}
        if len(cluster_values) != 1:
            raise ValueError('document source cluster changes between records')
        cluster = next(iter(cluster_values))
        if len(docs) > 1 and not cluster:
            raise ValueError('multi-document evidence needs duplicate-cluster identity')
        clusters.append(cluster)
        doc_maxima = []
        for node in NODE_ORDER:
            rows = [row for row in doc_local if row['node'] == node]
            if {row['layer_zero_based'] for row in rows} != set(range(32)):
                raise ValueError('document local node lacks a layer: ' + node)
            maximum = max(rows, key=lambda row: row['relative_l2_percent'])
            doc_maxima.append(dict(maximum, layer_site_cells=len(rows), independent_documents=1,
                                   aggregation='within one document: maximum across 32 layers and all sites of this node family'))
        if set(row['node'] for row in doc_local) != set(NODE_ORDER):
            raise ValueError('unexpected local node family')
        final_raw = final_by_doc[doc_id]
        if 'output_shape' in final_raw and tuple(final_raw['output_shape']) != shape:
            raise ValueError('final normalization and layer output shapes differ')
        final = metric_row(final_raw)
        final.update(layer_zero_based=None, layer_display=None, plot_position=35,
                     scope=final_raw.get('scope', 'after common final host normalization'))
        doc = dict(doc_id=doc_id, label=f'文档{index+1}', tokens=shape[1], channels=shape[2],
                   domain=doc_cont_raw[0].get('domain'), duplicate_cluster=cluster,
                   short_document=(maximum_tokens is not None and shape[1] < maximum_tokens),
                   local_maxima=doc_maxima, propagation_curve=doc_cont, final_normalization=final)
        documents.append(doc)
        local.extend(doc_local); continuous.extend(doc_cont); maxima.extend(doc_maxima); finals.append(final)
    if len(docs) > 1 and len(set(clusters)) != len(docs):
        raise ValueError('source-cluster duplicate cannot count as another independent document')
    count = len(documents)
    title = (f"开发检查：1 篇文档，{documents[0]['tokens']} token，尚非正式统计" if count == 1
             else f'开发检查：{count} 篇独立文档，尚非正式统计')
    return dict(schema_version=2, doc_id=order[0] if count == 1 else None, document_ids=order,
                measured_documents=count, independent_document_count=count,
                formal_eval_documents=0, tokens=(documents[0]['tokens'] if count == 1 else [doc['tokens'] for doc in documents]),
                channels=documents[0]['channels'], documents=documents, title=title,
                metric_definition='100 * ||current - reference||_2 / ||reference||_2',
                reference_definition='retain intermediate arithmetic precision, keep the same common node exits',
                local_scope='same-input paired nodes on the current trajectory; all accepted real coordinates',
                propagation_scope='paired continuous trajectories, independently recomputing activation quantization',
                independent_sampling_unit='document source cluster; not a population-IID certification',
                cross_attempt_data_merged=False, confidence_intervals=None, local_cells_are_independent_samples=False,
                local_maxima=maxima, local_metric_cells=local, propagation_curve=continuous,
                final_normalization=(finals[0] if count == 1 else None), final_normalizations=finals,
                source_files=[file_identity(path) for path in sources],
                limitations=[f'{count} development document(s); no population confidence interval',
                             'local maxima are descriptive maxima over layers/sites, not independent replications',
                             'reference is a common-exit arithmetic comparison, not an exact hidden-state oracle',
                             'strict per-output numerical domain has not been established for this GPU aggregate'])


def draw(data, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager, pyplot as plt
    from matplotlib.ticker import FuncFormatter

    # Fontconfig sees newly installed TTC collections before old Matplotlib
    # caches do.  Register that actual file explicitly, recording its identity.
    font_path = subprocess.check_output(['fc-match', '-f', '%{file}', 'Noto Sans CJK SC'], text=True).strip()
    if not font_path or 'NotoSansCJK' not in Path(font_path).name:
        raise ValueError('Noto Sans CJK font is required for the Chinese figure')
    font_manager.fontManager.addfont(font_path)
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams.update({'font.family': font_name, 'font.size': 11,
                         'axes.unicode_minus': False, 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#A6AFBC', 'axes.labelcolor': '#26364A',
                         'xtick.color': '#425369', 'ytick.color': '#425369'})
    if len(data['documents']) > 1:
        return draw_multiple(data, output, matplotlib, plt, font_path, font_name)
    blue, orange, ink, gray = '#27659A', '#C86E24', '#152D45', '#566779'
    fig, (left, right) = plt.subplots(1, 2, figsize=(13.9, 6.8), gridspec_kw={'width_ratios': [1.02, 1.12]})
    fig.subplots_adjust(left=.078, right=.976, top=.77, bottom=.27, wspace=.29)
    fig.suptitle(data['title'], fontsize=17, fontweight='bold', color=ink, y=.965)
    fig.text(.5, .89, '当前实现与保留中间精度的参考比较', ha='center', fontsize=12, color=gray)

    values = [row['relative_l2_percent'] for row in data['local_maxima']]
    if min(values) <= 0:
        raise ValueError('log-axis local overview requires positive measured maxima')
    lower = 10 ** math.floor(math.log10(min(values)) - .15)
    upper = max(values) * 4
    left.set_yscale('log')
    left.set_ylim(lower, upper)
    for i, (value, row) in enumerate(zip(values, data['local_maxima'])):
        left.vlines(i, lower, value, color=blue, alpha=.24, linewidth=4)
        left.scatter(i, value, s=68, color=blue, edgecolors='white', linewidths=.9, zorder=3)
        left.annotate(f'{value:.3g}%', (i, value), xytext=(0, 12), textcoords='offset points',
                      ha='center', color=ink, fontweight='bold', fontsize=11)
        site = OP_LABELS.get(row['op'])
        detail = f"第{row['layer_display']}层" + (f'·{site}' if site else '')
        left.text(i, .021, detail, transform=left.get_xaxis_transform(), ha='center',
                  va='bottom', color=gray, fontsize=9.1)
    left.set_ylim(lower, upper)
    left.set_xlim(-.55, 4.55)
    left.set_xticks(range(5), NODE_LABELS, fontsize=10.5)
    left.tick_params(axis='x', pad=10, length=0)
    left.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:g}'))
    left.set_ylabel('局部相对 L2 误差（%，对数刻度）', labelpad=9)
    left.set_title('(a) 同输入下，五类算子的局部误差', loc='left', color=ink, fontsize=13.1, pad=32)
    left.text(0, 1.035, '每类取跨 32 层及调用位置的最大值', transform=left.transAxes, fontsize=10.7, color=gray)
    left.grid(axis='y', which='major', color='#DDE4EB', linewidth=.7)
    left.set_axisbelow(True)

    layers = [row['layer_display'] for row in data['propagation_curve']]
    errors = [row['relative_l2_percent'] for row in data['propagation_curve']]
    final = data['final_normalization']
    right.plot(layers, errors, color=blue, linewidth=2.1, marker='o', markersize=3.4, label='逐层输出')
    right.plot([32, final['plot_position']], [errors[-1], final['relative_l2_percent']],
               color=orange, linestyle=(0, (3, 3)), linewidth=1.5)
    right.scatter([final['plot_position']], [final['relative_l2_percent']], marker='D',
                  color=orange, edgecolors='white', linewidths=.8, s=66, zorder=4, label='末端归一化后')
    right.annotate(f"第32层  {errors[-1]:.3g}%", (32, errors[-1]), xytext=(-16, -25),
                   textcoords='offset points', ha='right', fontsize=10.7, color=blue,
                   arrowprops=dict(arrowstyle='-', color=blue, linewidth=.8))
    right.annotate(f"终点  {final['relative_l2_percent']:.3g}%", (final['plot_position'], final['relative_l2_percent']),
                   xytext=(-6, 14), textcoords='offset points', ha='right',
                   fontsize=11, fontweight='bold', color=orange)
    right.set_xlim(0, 37.2)
    right.set_ylim(0, max(max(errors), final['relative_l2_percent']) * 1.2)
    right.set_xticks([1, 8, 16, 24, 32, 35], ['1', '8', '16', '24', '32', '末端\n归一化'])
    right.tick_params(axis='x', pad=7)
    right.set_xlabel('解码层（1–32）与归一化终点', labelpad=8)
    right.set_ylabel('层输出相对 L2 误差（%）', labelpad=9)
    right.set_title('(b) 两路连续计算，误差随层传播', loc='left', color=ink, fontsize=13.1, pad=32)
    right.text(0, 1.035, '各自重算激活量化；一条实测文档曲线', transform=right.transAxes, fontsize=10.7, color=gray)
    right.grid(axis='y', color='#DDE4EB', linewidth=.7)
    right.set_axisbelow(True)
    right.legend(loc='upper left', frameon=False, fontsize=10)

    fig.text(.078, .145, '相对 L2 误差 = 100 × ‖当前实现 − 参考‖ / ‖参考‖；参考保留中间精度，两路采用相同算子出口。',
             fontsize=11, color=ink)
    fig.text(.078, .094, f"局部比较固定同一输入；传播比较允许后续输入随误差改变。{len(data['local_metric_cells'])} 个层与调用位置均来自同一篇文档。",
             fontsize=10.4, color=gray)
    fig.text(.078, .046, '采用已接受输出；这些位置不视为独立样本，本图不代表总体统计或逐输出严格误差保证。',
             fontsize=10.4, color=gray)
    fig.savefig(output / 'numerical_overview.png', dpi=220, facecolor='white')
    fig.savefig(output / 'numerical_overview.pdf', facecolor='white')
    plt.close(fig)
    return dict(matplotlib=matplotlib.__version__, python=platform.python_version(),
                font=file_identity(font_path), font_family=font_name, png_dpi=220, size_inches=[13.9, 6.8],
                left_scale='logarithmic', right_scale='linear')


def draw_multiple(data, output, matplotlib, plt, font_path, font_name):
    """Show every document, without pooled points, intervals, or scalar inference."""
    colors = ('#27659A', '#C86E24', '#4B8875', '#9D6596')
    ink, gray = '#152D45', '#566779'
    docs = data['documents']
    count = len(docs)
    values = [row['relative_l2_percent'] for doc in docs for row in doc['local_maxima']]
    positive = [value for value in values if value > 0]
    lower = 10 ** math.floor(math.log10(min(positive)) - .25) if positive else 1e-6
    upper = max(positive) * 5 if positive else 1e-3
    fig, (left, right) = plt.subplots(1, 2, figsize=(14.3, 7.1), gridspec_kw={'width_ratios': [1.03, 1.15]})
    fig.subplots_adjust(left=.077, right=.977, top=.76, bottom=.28, wspace=.30)
    fig.suptitle(data['title'], fontsize=17, fontweight='bold', color=ink, y=.966)
    lengths = ' / '.join(str(doc['tokens']) for doc in docs)
    fig.text(.5, .892, f'文档1–{count}的实际长度：{lengths} token；短文保留真实长度，不补成128 token',
             ha='center', fontsize=11.7, color=gray)
    left.set_yscale('log')
    left.set_ylim(lower, upper)
    for index, (doc, color) in enumerate(zip(docs, colors)):
        jitter = (index - (count-1)/2) * .135
        for category, row in enumerate(doc['local_maxima']):
            value = row['relative_l2_percent']
            x, y = category + jitter, value if value > 0 else lower * 1.16
            left.vlines(x, lower, y, color=color, alpha=.17, linewidth=2.3)
            left.scatter(x, y, marker='o' if value > 0 else 'v', color=color,
                         s=51, edgecolors='white', linewidths=.7, zorder=3)
            if value == 0:
                left.annotate('0', (x, y), xytext=(0, 7), textcoords='offset points',
                              ha='center', fontsize=8, color=color)
    for category in range(5):
        maximum = max(doc['local_maxima'][category]['relative_l2_percent'] for doc in docs)
        if maximum > 0:
            left.annotate(f'最高 {maximum:.3g}%', (category, maximum), xytext=(0, 15),
                          textcoords='offset points', ha='center', fontsize=10, fontweight='bold', color=ink)
    left.set_xlim(-.57, 4.57)
    left.set_xticks(range(5), NODE_LABELS, fontsize=10.5)
    left.tick_params(axis='x', pad=11, length=0)
    from matplotlib.ticker import FuncFormatter
    left.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:g}'))
    left.set_ylabel('同输入局部相对 L2 误差（%，对数刻度）', labelpad=9)
    left.set_title(f'(a) 每类显示全部 {count} 篇文档的局部最大值', loc='left', fontsize=12.9, color=ink, pad=32)
    left.text(0, 1.035, '每点先在该文档内跨32层及调用位置取最大值', transform=left.transAxes,
              fontsize=10.4, color=gray)
    left.grid(axis='y', which='major', color='#DDE4EB', linewidth=.7)
    left.set_axisbelow(True)
    ends = []
    for index, (doc, color) in enumerate(zip(docs, colors)):
        layers = [row['layer_display'] for row in doc['propagation_curve']]
        errors = [row['relative_l2_percent'] for row in doc['propagation_curve']]
        final = doc['final_normalization']['relative_l2_percent']
        endpoint_x = 35 + (index - (count-1)/2) * .17
        label = f"{doc['label']} · {doc['tokens']} token" + ('（短文）' if doc['short_document'] else '')
        label += f' · 终点 {final:.3g}%'
        right.plot(layers, errors, color=color, linewidth=1.8, marker='o', markersize=2.4, label=label)
        right.plot([32, endpoint_x], [errors[-1], final], color=color, linestyle=(0, (3, 3)), linewidth=1.2)
        right.scatter(endpoint_x, final, marker='D', s=49, color=color, edgecolors='white', linewidths=.7, zorder=5)
        ends.extend(errors + [final])
    right.set_xlim(0, 37.4)
    right.set_ylim(0, max(ends) * 1.22 if max(ends) > 0 else 1)
    right.set_xticks([1, 8, 16, 24, 32, 35], ['1', '8', '16', '24', '32', '末端\n归一化'])
    right.tick_params(axis='x', pad=7)
    right.set_xlabel('解码层（1–32）与归一化终点', labelpad=8)
    right.set_ylabel('层输出相对 L2 误差（%）', labelpad=9)
    right.set_title(f'(b) {count} 条实测传播曲线与各自终点', loc='left', fontsize=12.9, color=ink, pad=32)
    right.text(0, 1.035, '各自重算激活量化；菱形为末端归一化后', transform=right.transAxes,
               fontsize=10.4, color=gray)
    right.legend(loc='upper left', frameon=False, fontsize=8.8, labelspacing=.65,
                 handlelength=2.0, handletextpad=.65)
    right.grid(axis='y', color='#DDE4EB', linewidth=.7)
    right.set_axisbelow(True)
    fig.text(.077, .151, '相对 L2 误差 = 100 × ‖当前实现 − 参考‖ / ‖参考‖；参考保留中间精度，两路采用相同算子出口。',
             fontsize=10.8, color=ink)
    fig.text(.077, .101, f'统计单位为 {count} 篇独立源文档；同一文档的层、算子与token不算新增样本，不与旧批次重复文档累加。',
             fontsize=10.3, color=gray)
    zero_note = ' 零误差以底部三角形标明。' if len(positive) != len(values) else ''
    fig.text(.077, .052, '全部观测直接显示，不绘制置信区间；采用已接受输出，尚非总体统计或逐输出严格误差保证。' + zero_note,
             fontsize=10.3, color=gray)
    fig.savefig(output / 'numerical_overview.png', dpi=220, facecolor='white')
    fig.savefig(output / 'numerical_overview.pdf', facecolor='white')
    plt.close(fig)
    return dict(matplotlib=matplotlib.__version__, python=platform.python_version(),
                font=file_identity(font_path), font_family=font_name, png_dpi=220,
                size_inches=[14.3, 7.1], left_scale='logarithmic', right_scale='linear',
                displayed_document_points_per_category=count, displayed_propagation_curves=count,
                displayed_final_norm_endpoints=count, confidence_intervals=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Default: ATTEMPT/overview_v1 (must be empty)')
    args = parser.parse_args(argv)
    data = collect_data(args.attempt)
    output = args.output or args.attempt / 'overview_v1'
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError('overview output directory is not empty; existing evidence is preserved')
    data['plot_source'] = file_identity(__file__)
    data['render'] = draw(data, output)
    data['outputs'] = [file_identity(output / name) for name in ('numerical_overview.png', 'numerical_overview.pdf')]
    with (output / 'source_data.json').open('x') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(output=str(output.resolve()), measured_documents=data['measured_documents'],
                          documents=[dict(doc_id=doc['doc_id'], tokens=doc['tokens'],
                                          local_maxima_percent={row['node']: row['relative_l2_percent'] for row in doc['local_maxima']},
                                          layer32_percent=doc['propagation_curve'][-1]['relative_l2_percent'],
                                          final_normalization_percent=doc['final_normalization']['relative_l2_percent'])
                                     for doc in data['documents']]), ensure_ascii=False))


if __name__ == '__main__':
    main()
