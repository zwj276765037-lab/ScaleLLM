#!/usr/bin/env python3
"""Paper PNGs: all11 local clouds plus fixed-prefix decoding evidence; CPU only."""
from pathlib import Path
import csv, hashlib, json, math, os, sys, time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
os.environ['MPLCONFIGDIR'] = str(HERE / '.mpl_cache')
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from PIL import Image

ZH_FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
font_manager.fontManager.addfont(str(ZH_FONT))
ZH_FAMILY = font_manager.FontProperties(fname=str(ZH_FONT)).get_name()
BLUE, ORANGE, GREY = '#2166AC', '#D36B19', '#8C9298'
STABLE_OTHER, FLIP = '#9BBAD1', '#B64036'
INK = '#17212B'
plt.rcParams.update({'font.size': 14, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.axisbelow': True, 'axes.linewidth': .8, 'axes.unicode_minus': False,
                     'axes.labelsize': 14, 'xtick.labelsize': 14, 'ytick.labelsize': 14,
                     'text.color': INK, 'axes.labelcolor': INK, 'grid.alpha': .4,
                     'grid.color': '#CCD3D9', 'figure.facecolor': 'white', 'savefig.facecolor': 'white'})

def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}

def save_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def csvrows(name):
    with (PACKAGE / name).open(newline='') as f:
        return list(csv.DictReader(f))

def load_data():
    specs = [
        ('01_full1024/integrated_aggregate.json', 'All1024 per-document local maxima, retaining every point/tail'),
        ('01_full1024/operator_error_summary.csv', 'Stored P50/P95 and definitions; first11 local columns only'),
        ('01_full1024/vocabulary_coverage.csv', 'All12 absolute-logit thresholds, full-score denominator'),
        ('01_full1024/per_position_tv.csv', 'All103700 positions for exact post-step ECDF'),
        ('01_full1024/TV_summary.csv', 'Position-weighted TV quantile cross-check'),
        ('03_top1_margin/positions.csv', 'Recompute margin>2*max_abs_logit_delta, validate flags and flips'),
        ('03_top1_margin/buckets.csv', 'All8 fixed margin buckets, including two nonempty zero-flip buckets'),
        ('01_full1024/top1_summary.json', 'Observed greedy argmax agreement, not task accuracy'),
    ]
    sources = [{**identity(PACKAGE / name), 'package_relative_path': name, 'role': role} for name, role in specs]
    aggregate = json.loads((PACKAGE / specs[0][0]).read_text())
    rows = csvrows(specs[1][0])[:11]
    assert len(aggregate['documents']) == 1024 and len(rows) == 11
    locals_ = []
    for row in rows:
        values = [d['columns'][row['metric']]['value'] for d in aggregate['documents']]
        assert len(values) == 1024 and all(math.isfinite(v) and v > 0 for v in values)
        for q, field in [(.5, 'P50_percent'), (.95, 'P95_percent')]:
            assert math.isclose(float(np.quantile(values, q)), float(row[field]), abs_tol=1e-12)
        locals_.append({'metric': row['metric'], 'definition': row['口径'], 'sites_per_document': int(row['每文档site数']),
                        'all1024_values_percent': values, 'P50_percent': float(row['P50_percent']),
                        'P95_percent': float(row['P95_percent']), 'max_percent': max(values)})
    totals = {'positions': 0, 'certified_unchanged': 0, 'other_observed_unchanged': 0, 'flipped': 0}
    keys, docs = set(), set()
    with (PACKAGE / specs[5][0]).open(newline='') as f:
        for row in csv.DictReader(f):
            key = (row['doc_id'], int(row['position']))
            assert key not in keys
            keys.add(key)
            docs.add(row['doc_id'])
            margin, epsilon = float(row['reference_top1_margin']), float(row['max_abs_logit_delta'])
            assert math.isfinite(margin) and math.isfinite(epsilon) and margin >= 0 and epsilon >= 0
            certificate = margin > 2 * epsilon
            flipped = bool(int(row['top1_flip']))
            assert certificate == bool(int(row['margin_certified']))
            assert flipped == (int(row['current_top1_id']) != int(row['reference_top1_id']))
            assert not (certificate and flipped)
            totals['positions'] += 1
            totals['certified_unchanged'] += certificate
            totals['other_observed_unchanged'] += not certificate and not flipped
            totals['flipped'] += flipped
    assert totals == {'positions': 103700, 'certified_unchanged': 82728, 'other_observed_unchanged': 19919, 'flipped': 1053}
    assert len(docs) == 1024
    assert sum(totals[k] for k in ['certified_unchanged', 'other_observed_unchanged', 'flipped']) == totals['positions']
    totals['unchanged'] = totals['certified_unchanged'] + totals['other_observed_unchanged']
    totals['unchanged_percent'] = 100 * totals['unchanged'] / totals['positions']
    totals['percentages'] = {k: 100 * totals[k] / totals['positions'] for k in ['certified_unchanged', 'other_observed_unchanged', 'flipped']}
    totals['definition'] = 'Margin is reference top1 logit minus reference top2 logit; epsilon is max absolute current/reference logit difference at that same fixed prefix. The strict inequality is sufficient, not necessary.'
    totals['all103700_flags_recomputed_and_equal'] = True
    totals['all_certified_positions_observed_unchanged'] = True
    top1 = json.loads((PACKAGE / specs[7][0]).read_text())
    assert top1['token_weighted_match_count'] == totals['unchanged'] == 102647
    coverage = csvrows(specs[2][0])
    assert len(coverage) == 12 and all(int(r['score_total_count']) == 13300147200 for r in coverage)
    buckets = csvrows(specs[6][0])
    assert len(buckets) == 8 and sum(int(r['positions']) for r in buckets) == 103700 and sum(int(r['flips']) for r in buckets) == 1053
    tv_rows = csvrows(specs[3][0])
    assert len(tv_rows) == 103700 and {(r['doc_id'], int(r['position'])) for r in tv_rows} == keys
    tv = np.sort(np.asarray([float(r['tv_percent']) for r in tv_rows], dtype=np.float64))
    summary = next(r for r in csvrows(specs[4][0]) if r['pool'] == 'fixed_quota_pool' and r['metric'] == 'position_weighted_tv')
    for q, name in [(.5, 'p50'), (.95, 'p95'), (.99, 'p99')]:
        assert math.isclose(float(np.quantile(tv, q)), float(summary[name + '_percent']), abs_tol=1e-11)
    assert tv[-1] == float(summary['max_percent'])
    data = {'scope': {'documents': 1024, 'positions': 103700, 'layers': 32, 'vocabulary': 128256,
                      'logit_pairs': 13300147200, 'fixed_prefix_greedy_argmax_only': True,
                      'reference_retains': 'Basic quantization, ScaleCode, LUT/SwiGLU, common exits and Host'},
            'local_operators': locals_, 'cloud_document_order': [d['doc_id'] for d in aggregate['documents']],
            'grey_points': 11264, 'grey_points_omitted': 0,
            'certificate_and_observed_partition': totals, 'coverage': coverage, 'margin_buckets': buckets,
            'TV': {'sorted_all103700_percent': tv.tolist(), 'summary': summary,
                   'ECDF': "step([0]+x, [0]+arange(1,N+1)/N, where='post'); full tail retained"},
            'figure_policy': {'main_inches': [14, 10], 'dpi': 600, 'minimum_font_pt': 14,
                              'font_at7_2inch_width_pt': 7.2, 'jitter_seed': 20261020,
                              'jitter_is_visual_only': True, 'no_cumulative_hidden_or_logit_relative_L2_columns': True}}
    return data, sources

EN = {
    'title': 'Local numerical fidelity and fixed-prefix decoding agreement',
    'subtitle': '1,024 documents · 103,700 positions · 32 layers · 128,256 vocabulary entries',
    'local_title': 'A  Local computation error',
    'labels': ['Attention\nlinears', 'RoPE', 'QK', 'Softmax', 'PV', 'Gate\nprojection', 'Up\nprojection', 'Down\nprojection',
               'Gated\nproduct†', 'MLP\nbranch‡', 'Residual\nmerge‡'],
    'groups': ['Attention', 'MLP projections', 'Common exit', 'MLP combinations'],
    'ylabel': 'Relative L2 error (%)',
    'legend': ['All 1,024 documents', 'Document P50', 'Document P95'],
    'note1': 'Each document contributes its maximum across predefined layers/sites; all points and tails are retained.',
    'note2': '† Includes the shared product exit; ‡ MLP branch uses fixed input, residual merge uses a fixed base.',
    'decode_title': 'B  Greedy next-token agreement',
    'cert': 'Certified unchanged', 'other': 'Also unchanged',
    'flips': 'Flipped', 'fixed': 'Identical fixed prefixes, greedy argmax: 102,647 / 103,700 unchanged (98.985%).',
    'certificate_note': 'Post-hoc certificate from measured logits: m > 2ε (sufficient, not necessary).',
    'coverage_title': 'C  Full-vocabulary coverage', 'coverage_x': 'Absolute logit threshold τ', 'coverage_y': 'Score coverage (%)',
    'coverage_note': '13,300,147,200 logit pairs',
    'margin_title': 'D  Flips by reference margin', 'margin_x': 'Reference margin m (raw logit units)',
    'margin_y': 'Flip rate within bin (%)', 'margin_note': '975 / 1,053 flips have m < 0.1',
    'tv_title': 'E  Output-distribution TV', 'tv_x': 'TV (% of probability mass)', 'tv_y': 'Cumulative positions (%)',
    'tv_max': 'Max', 'scale_note': 'Symlog: linear near zero',
}
ZH = {
    'title': '局部数值精度与固定前缀解码一致性',
    'subtitle': '1024篇文档 · 103700个位置 · 32层 · 128256词表',
    'local_title': 'A  局部计算误差',
    'labels': ['Attention\n线性投影', 'RoPE', 'QK', 'Softmax', 'PV', 'Gate\n投影', 'Up\n投影', 'Down\n投影',
               '门控\n乘积†', 'MLP\n分支‡', '残差\n合并‡'],
    'groups': ['Attention', 'MLP投影', '共同出口', 'MLP组合'],
    'ylabel': '相对 L2 误差（%）', 'legend': ['全部1024篇文档', '文档 P50', '文档 P95'],
    'note1': '每篇先跨预定义层/节点取最大值，再统计文档分位数；全部散点及尾部均保留。',
    'note2': '† 包含共同乘积出口的舍入损失；‡ MLP分支固定同一入口，残差合并固定同一残差基底，二者为组合比较。',
    'decode_title': 'B  贪心下一 token 一致性', 'cert': '充分条件满足且不变',
    'other': '其余观测不变', 'flips': '改变',
    'fixed': '完全相同的固定前缀、贪心argmax：102647 / 103700 相同（98.985%）。',
    'certificate_note': '证书为已测logit上的事后充分条件：m > 2ε；不满足不代表发生翻转。',
    'coverage_title': 'C  全词表 score 覆盖', 'coverage_x': '绝对 logit 差阈值 τ', 'coverage_y': 'score 覆盖率（%）',
    'coverage_note': '分母：13,300,147,200 logit 对',
    'margin_title': 'D  参考 Margin 分层翻转', 'margin_x': '参考 Margin m（原始logit单位）',
    'margin_y': '桶内翻转率（%）', 'margin_note': '975/1053次翻转的 Margin < 0.1',
    'tv_title': 'E  概率分布 TV', 'tv_x': 'TV（概率质量百分数）', 'tv_y': '累计位置比例（%）',
    'tv_max': '最大', 'scale_note': 'Symlog：近零线性',
}

def local_plot(ax, data, text):
    local = data['local_operators']
    for lo, hi, color in [(-.5, 4.5, '#DDEAF4'), (4.5, 7.5, '#E2EEE6'), (7.5, 8.5, '#F4E9DB'), (8.5, 10.5, '#ECE6F3')]:
        ax.axvspan(lo, hi, color=color, alpha=.56, zorder=0)
    for x in [4.5, 7.5, 8.5]:
        ax.axvline(x, color='#B6C2CB', linewidth=.8)
    rng = np.random.default_rng(20261020)
    for i, row in enumerate(local):
        x = i + rng.uniform(-.17, .17, 1024)
        ax.scatter(x, row['all1024_values_percent'], s=2.1, color=GREY, alpha=.24, edgecolors='none', zorder=2)
        ax.scatter([i], [row['P50_percent']], marker='o', s=57, color=BLUE, edgecolors='white', linewidths=.65, zorder=5)
        ax.scatter([i], [row['P95_percent']], marker='D', s=52, color=ORANGE, edgecolors='white', linewidths=.65, zorder=6)
        ax.annotate(f"{row['P95_percent']:.4g}%", (i, row['P95_percent']), xytext=(0, 11), textcoords='offset points',
                    ha='center', fontsize=14, color='#713B18', bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .83, 'pad': 1.})
    for x, name in zip([2, 6, 8, 9.5], text['groups']):
        ax.text(x, 1.017, name, transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=14)
    ax.set_yscale('log')
    ax.set_ylim(.00026, .4)
    ax.set_xlim(-.5, 10.5)
    ax.set_xticks(range(11), text['labels'], fontsize=14)
    ax.set_ylabel(text['ylabel'], fontsize=15)
    ax.grid(axis='y', which='major', linewidth=.6)
    ax.tick_params(axis='x', length=0, pad=7)

def legend_handles():
    return [Line2D([], [], linestyle='', marker='o', color=GREY, markersize=4, alpha=.6),
            Line2D([], [], linestyle='', marker='o', color=BLUE, markersize=7),
            Line2D([], [], linestyle='', marker='D', color=ORANGE, markersize=6.5)]

def decode_bar(ax, data, text):
    part = data['certificate_and_observed_partition']
    cert, other, flip = [part['percentages'][key] for key in ['certified_unchanged', 'other_observed_unchanged', 'flipped']]
    left = 0
    for width, color in [(cert, BLUE), (other, STABLE_OTHER), (flip, FLIP)]:
        ax.barh([.5], [width], left=left, height=.96, color=color, edgecolor='white', linewidth=.8)
        left += width
    ax.text(cert/2, .5, text['cert'] + '\n82,728 (79.776%)', ha='center', va='center', fontsize=14, color='white', linespacing=1.2)
    ax.text(cert+other/2, .5, text['other'] + '\n19,919 (19.208%)', ha='center', va='center', fontsize=14, linespacing=1.2)
    ax.annotate(text['flips'] + ': 1,053 (1.015%)', (100-flip/2, .5), xytext=(100, 1.31),
                ha='right', va='bottom', fontsize=14, color=FLIP,
                arrowprops={'arrowstyle': '-', 'color': FLIP, 'linewidth': 1.}, annotation_clip=False)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.axis('off')

def coverage_plot(ax, data, text):
    rows = data['coverage']
    x = [float(r['epsilon']) for r in rows]
    y = [float(r['score_coverage_percent']) for r in rows]
    ax.plot(x, y, color=BLUE, marker='o', markersize=4, linewidth=1.6)
    for value in [.1, .2, .5]:
        i = x.index(value)
        ax.scatter([x[i]], [y[i]], s=42, facecolors='white', edgecolors=ORANGE, linewidths=1.3, zorder=3)
    ax.set_xscale('log')
    ax.set_xlim(.0008, 7)
    ax.set_ylim(0, 106)
    ax.set_xticks([.001, .01, .1, 1, 5], ['.001', '.01', '.1', '1', '5'])
    ax.set_yticks([0, 50, 100])
    ax.set_xlabel(text['coverage_x'], fontsize=14)
    ax.set_ylabel(text['coverage_y'], fontsize=14)
    ax.grid(axis='y', linewidth=.6)
    card = '\n'.join(f"{eps:g}: {float(next(r for r in rows if float(r['epsilon']) == eps)['score_coverage_percent']):.5f}%" for eps in [.1, .2, .5])
    ax.text(.49, .055, card, transform=ax.transAxes, fontsize=14, linespacing=1.25,
            bbox={'boxstyle': 'round,pad=.35', 'facecolor': 'white', 'edgecolor': '#D1D8DE'}, va='bottom')

def margin_plot(ax, data, text):
    rows = data['margin_buckets']
    rates = [float(r['within_bucket_flip_rate_percent']) for r in rows]
    x = range(8)
    ax.bar(x, rates, color=[ORANGE]*2 + [BLUE]*6, width=.62)
    for i, r in enumerate(rows):
        if rates[i] == 0:
            ax.scatter([i], [0], s=28, color=BLUE, zorder=3)
        ax.annotate(f'{rates[i]:.3g}', (i, rates[i]), xytext=(0, 5), textcoords='offset points', ha='center', fontsize=14)
    ax.set_yscale('symlog', linthresh=.03, linscale=.7)
    ax.set_ylim(-.003, 100)
    ax.set_yticks([0, .1, 1, 10], ['0', '0.1', '1', '10'])
    labels = [r['margin_bucket'].replace('0.01', '.01').replace('0.05', '.05').replace('0.1', '.1').replace('0.2', '.2').replace('0.5', '.5') for r in rows]
    ax.set_xticks(x, labels, rotation=55, ha='right', fontsize=14)
    ax.set_xlabel(text['margin_x'], fontsize=14)
    ax.set_ylabel(text['margin_y'], fontsize=14)
    ax.text(.97, .88, 'symlog', transform=ax.transAxes, fontsize=14, ha='right', color='#596570')
    ax.grid(axis='y', linewidth=.6)

def tv_plot(ax, data, text):
    x = np.asarray(data['TV']['sorted_all103700_percent'])
    y = np.arange(1, len(x)+1)/len(x)
    ax.step(np.r_[0., x], np.r_[0., y], where='post', color=BLUE, linewidth=1.6)
    summary = data['TV']['summary']
    for name, q in [('p50', .5), ('p95', .95), ('p99', .99), ('max', 1.)]:
        ax.scatter([float(summary[name + '_percent'])], [q], s=20, color=ORANGE, zorder=3)
    ax.set_xscale('symlog', linthresh=.1, linscale=.65)
    ax.set_xlim(0, 34)
    ax.set_ylim(0, 1.035)
    ax.set_xticks([0, .1, 1, 10, 30], ['0', '.1', '1', '10', '30'])
    ax.set_yticks([0, .5, 1], ['0', '50', '100'])
    ax.set_xlabel(text['tv_x'], fontsize=14)
    ax.set_ylabel(text['tv_y'], fontsize=14)
    ax.grid(axis='y', linewidth=.6)
    ax.text(.035, .79, 'symlog x', transform=ax.transAxes, fontsize=14, color='#596570')

def save_png(fig, name):
    fig.savefig(HERE / name, dpi=600)
    plt.close(fig)
    with Image.open(HERE / name) as im:
        size = im.size
        preview = (2400, round(size[1]*2400/size[0]))
        im.resize(preview, Image.Resampling.LANCZOS).save(HERE / name.replace('.png', '_preview.png'))
    return {'file': name, 'pixels': list(size), 'dpi': 600,
            'preview': name.replace('.png', '_preview.png'), 'preview_pixels': list(preview)}

def render(data, language):
    text = EN if language == 'en' else ZH
    plt.rcParams['font.family'] = 'DejaVu Sans' if language == 'en' else ZH_FAMILY
    fig = plt.figure(figsize=(14, 10))
    fig.text(.5, .977, text['subtitle'], ha='center', fontsize=14)
    ax = fig.add_axes([.075, .625, .90, .235])
    local_plot(ax, data, text)
    fig.text(.075, .935, text['local_title'], fontsize=16, fontweight='bold')
    fig.legend(legend_handles(), text['legend'], loc='upper right', bbox_to_anchor=(.975, .955),
               ncol=3, frameon=False, fontsize=14, columnspacing=1., handletextpad=.35)
    fig.text(.075, .550, text['note1'], fontsize=14)
    fig.text(.075, .528, text['note2'], fontsize=14)
    fig.text(.075, .485, text['decode_title'], fontsize=16, fontweight='bold')
    decode_bar(fig.add_axes([.075, .418, .90, .052]), data, text)
    fig.text(.075, .392, text['fixed'], fontsize=14)
    fig.text(.075, .366, text['certificate_note'], fontsize=14)
    # Small-multiple titles/count rows sit outside the compact plotting areas.
    xs = [.075, .375, .745]
    widths = [.245, .320, .230]
    axes = [fig.add_axes([x, .140, w, .140]) for x, w in zip(xs, widths)]
    coverage_plot(axes[0], data, text)
    margin_plot(axes[1], data, text)
    tv_plot(axes[2], data, text)
    for x, name in zip(xs, [text['coverage_title'], text['margin_title'], text['tv_title']]):
        fig.text(x, .325, name, fontsize=16, fontweight='bold')
    fig.text(xs[0], .298, text['coverage_note'], fontsize=14)
    fig.text(xs[1], .298, text['margin_note'], fontsize=14)
    # Quantiles outside the axes keep the complete ECDF visible.
    summary = data['TV']['summary']
    fig.text(xs[2], .054, f"P50 {float(summary['p50_percent']):.5f}%   P95 {float(summary['p95_percent']):.5f}%", fontsize=14)
    fig.text(xs[2], .030, f"P99 {float(summary['p99_percent']):.5f}%   {text['tv_max']} {float(summary['max_percent']):.5f}%", fontsize=14)
    main = save_png(fig, f'paper_fidelity_decoding_{language}.png')
    print(json.dumps({'stage': 'paper_png_ready', 'language': language, **main}, ensure_ascii=False), flush=True)

    fig = plt.figure(figsize=(14, 5.5))
    ax = fig.add_axes([.075, .26, .90, .52])
    local_plot(ax, data, text)
    fig.suptitle('Local computation error' if language == 'en' else '局部计算误差', fontsize=20, y=.98, fontweight='semibold')
    fig.legend(legend_handles(), text['legend'], loc='upper center', bbox_to_anchor=(.53, .91), ncol=3,
               frameon=False, fontsize=14, columnspacing=1.4)
    fig.text(.075, .100, text['note1'], fontsize=14)
    fig.text(.075, .055, text['note2'], fontsize=14)
    local = save_png(fig, f'local_operators_{language}.png')
    return [main, local]

def main():
    started = time.monotonic()
    data, sources = load_data()
    save_json('plot_data.json', data)
    save_json('source_manifest.json', {'schema': 'paper_fidelity_decoding_v1', 'sources': sources,
        'plotter': identity(__file__), 'fonts': [identity(ZH_FONT), identity(font_manager.findfont('DejaVu Sans'))],
        'scope': data['scope'], 'reference_and_units': '11 local document-max tensor relativeL2% only; decoding fixed-prefix greedy agreement; coverage raw-logit epsilon; margin raw-logit difference; TV probability mass percent',
        'certificate': 'Strictly recomputed m>2ε at each of103700 positions, compared against stored flags; certified unchanged and other observed unchanged are distinct',
        'format': 'Python/matplotlib PNG only;600dpi; no SVG/PDF', 'minimum_font_size_pt': 14,
        'publication_scale': 'At7.2inch width,14pt source font becomes7.2pt',
        'write_boundary': 'Only08_paper_fidelity_decoding_v1; Root report/provenance and all old artifacts remain untouched',
        'new_experiment': False, 'GPU_or_model_used': False})
    images = []
    for language in ['en', 'zh']:
        images += render(data, language)
    for source in sources:
        assert identity(source['path'])['sha256'] == source['sha256']
    names = [n for image in images for n in [image['file'], image['preview']]] + ['plot_data.json', 'source_manifest.json']
    save_json('output_manifest.json', {'execution_state': 'completed', 'source_files_unchanged': True,
        'images': images, 'outputs': [identity(HERE / n) for n in names],
        'plotter': identity(__file__), 'actual_pid': os.getpid(), 'wall_seconds': time.monotonic()-started,
        'versions': {'python': sys.version, 'numpy': np.__version__, 'matplotlib': matplotlib.__version__},
        'reference_or_statistics_changed': False, 'new_experiment': False, 'GPU_or_model_used': False,
        'certificate_validation': data['certificate_and_observed_partition'], 'all11264_local_points_retained': True})
    print(json.dumps({'execution_state': 'completed', 'wall_seconds': time.monotonic()-started,
                      'official_images': len(images), 'previews': len(images), 'certificate': data['certificate_and_observed_partition']}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
