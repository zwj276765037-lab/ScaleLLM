#!/usr/bin/env python3
"""CPU-only figures/tables from audited package data; writes only this directory."""
from pathlib import Path
from collections import OrderedDict
import csv, hashlib, html, io, json, math, os, sys, time

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
from matplotlib.ticker import FuncFormatter
from PIL import Image

FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
font_manager.fontManager.addfont(str(FONT))
FAMILY = font_manager.FontProperties(fname=str(FONT)).get_name()
BLUE, ORANGE, GREEN, PURPLE = '#17689B', '#C75B19', '#24775B', '#7955A1'
INK, LIGHT, GREY = '#182B3A', '#E7EDF2', '#647585'
COLORS = [BLUE, GREEN, ORANGE]
plt.rcParams.update({'font.family': FAMILY, 'font.size': 10.5, 'text.color': INK,
    'axes.labelcolor': INK, 'axes.edgecolor': '#82909B', 'axes.titleweight': 'bold',
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.unicode_minus': False,
    'axes.axisbelow': True, 'grid.color': '#CDD6DE', 'grid.alpha': .55,
    'figure.facecolor': 'white', 'savefig.facecolor': 'white'})

def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}

def save_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def read_csv(name):
    with (PACKAGE / name).open(newline='') as f:
        return list(csv.DictReader(f))

def write_csv(name, rows):
    p = HERE / 'tables' / name
    p.parent.mkdir(exist_ok=True)
    with p.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def number(v, digits=6):
    return '未测' if v is None or v == '' else f'{float(v):.{digits}g}'

def panel_title(ax, title, subtitle=None):
    ax.set_title(title, loc='left', fontsize=14.5, pad=28 if subtitle else 15)
    if subtitle:
        ax.text(0, 1.018, subtitle, transform=ax.transAxes, fontsize=9.8, color=GREY, va='bottom')

def source_data():
    specs = OrderedDict([
        ('01_full1024/operator_error_summary.csv', '13项文档分布；前11项为跨site最大，后2项为完整轨迹'),
        ('01_full1024/layer_error_summary.csv', '32个块输出与final norm/logits文档分位数'),
        ('01_full1024/vocabulary_coverage.csv', '12个原始logit绝对差阈值；全部score覆盖'),
        ('01_full1024/TV_summary.csv', '文档/位置两种权重TV分布及分位数'),
        ('01_full1024/per_position_tv.csv', '103700真实位置TV；用于完整ECDF，不截尾'),
        ('01_full1024/top1_summary.json', '103700位置Top1一致与翻转；非任务准确率'),
        ('03_top1_margin/buckets.csv', '8个预先固定Margin桶的计数/桶内率'),
        ('02_attention_mlp_layer32/pure_branch_AB.csv', '仅3篇299位置，残差前两个纯分支，当前/参考轨迹'),
        ('06_metric_definition_audit/summary.json', '全1024同N能量合池的残差机制三阶段；不是纯Attention'),
    ])
    sources = [{'relative_path': name, 'role': role, **identity(PACKAGE / name)} for name, role in specs.items()]
    operators = read_csv('01_full1024/operator_error_summary.csv')
    layers = read_csv('01_full1024/layer_error_summary.csv')
    coverage = read_csv('01_full1024/vocabulary_coverage.csv')
    tv_summary = read_csv('01_full1024/TV_summary.csv')
    buckets = read_csv('03_top1_margin/buckets.csv')
    pure = read_csv('02_attention_mlp_layer32/pure_branch_AB.csv')
    top1 = json.loads((PACKAGE / '01_full1024/top1_summary.json').read_text())
    residual = json.loads((PACKAGE / '06_metric_definition_audit/summary.json').read_text())
    values, keys = [], set()
    for row in read_csv('01_full1024/per_position_tv.csv'):
        key = (row['doc_id'], int(row['position']))
        assert key not in keys
        keys.add(key)
        value = float(row['tv_percent'])
        assert math.isfinite(value) and 0 <= value <= 100
        assert math.isclose(value, 100 * float(row['tv']), abs_tol=1e-12)
        values.append(value)
    values = np.sort(np.asarray(values, dtype=np.float64))
    assert len(values) == 103700 and len({k[0] for k in keys}) == 1024
    assert len(operators) == 13 and len(layers) == 34 and len(coverage) == 12
    assert len(buckets) == 8 and sum(int(r['positions']) for r in buckets) == 103700
    assert sum(int(r['flips']) for r in buckets) == top1['token_weighted_flip_count'] == 1053
    assert sum(int(r['flips']) for r in buckets[:2]) == 876
    assert sum(int(r['flips']) for r in buckets[:3]) == 975
    assert all(int(r['score_total_count']) == 13300147200 for r in coverage)
    assert all(r['scalar_count'] == 424755200 for r in residual['rows'])
    assert all(int(r['count']) == 1224704 for r in pure)
    summary = next(r for r in tv_summary if r['pool'] == 'fixed_quota_pool' and r['metric'] == 'position_weighted_tv')
    for q, name in [(.5, 'p50'), (.95, 'p95'), (.99, 'p99')]:
        assert math.isclose(float(np.quantile(values, q)), float(summary[name + '_percent']), abs_tol=1e-11)
    assert values[-1] == float(summary['max_percent'])
    data = {'scope': {'full_documents': 1024, 'positions': 103700, 'layers': 32, 'vocabulary': 128256,
                     'diagnostic_pure_branch_documents': 3, 'diagnostic_pure_branch_positions': 299,
                     'reference': 'Reference retains basic quantization, ScaleCode, LUT/SwiGLU, common exits and Host'},
            'operators': operators, 'layers': layers[:32], 'cumulative_outputs': layers[32:],
            'coverage': coverage, 'tv_summary': tv_summary, 'top1': top1, 'margin_buckets': buckets,
            'pure_branches_3docs': pure, 'residual_mechanism_1024': residual,
            'position_tv_ecdf': {'unit': 'percent of probability mass', 'n': len(values),
                                 'sorted_percent_all_positions': values.tolist(),
                                 'cumulative_fraction_rule': '(one-based sorted index)/103700; no positions omitted'},
            'missing_data_policy': 'No full1024 token-wise hidden/cosine is available; not inferred or plotted. Pooled-only metrics have no measured document quantiles.'}
    return data, sources

LOCAL_LABELS = ['Attention 线性投影', 'RoPE', 'QK', 'Attention Softmax', 'PV',
                'MLP Gate', 'MLP Up', 'MLP Down', '门控乘积＋共同出口', '整个 MLP（固定入口）', 'MLP＋固定残差']
RESIDUAL_LABELS = ['Attention\n残差后', 'MLP\n分支', '两者\n相加']

def local_panel(ax, data):
    rows = data['operators'][:11]
    positions = np.arange(11)
    for lo, hi, color in [(-.5, 4.5, BLUE), (4.5, 7.5, GREEN), (7.5, 8.5, ORANGE), (8.5, 10.5, PURPLE)]:
        ax.axhspan(lo, hi, color=color, alpha=.045, zorder=0)
    for cut in [4.5, 7.5, 8.5]:
        ax.axhline(cut, color='#B9C6CE', linewidth=.7)
    p50 = [float(r['P50_percent']) for r in rows]
    p95 = [float(r['P95_percent']) for r in rows]
    ax.hlines(positions, p50, p95, color='#9BAAB5', linewidth=2)
    ax.scatter(p50, positions, color=BLUE, marker='o', s=34, label='文档 P50', zorder=3)
    ax.scatter(p95, positions, color=ORANGE, marker='D', s=30, label='文档 P95', zorder=4)
    for y, value in zip(positions, p95):
        ax.annotate(number(value) + '%', (value, y), xytext=(7, 0), textcoords='offset points', va='center', fontsize=9.5)
    ax.set_yticks(positions, LOCAL_LABELS, fontsize=10)
    ax.set_ylim(10.6, -.6)
    ax.set_xscale('log')
    ax.set_xlim(.00025, .58)
    ax.set_xlabel('张量相对 L2（%）；对数坐标')
    ax.grid(axis='x', which='major')
    panel_title(ax, 'A  局部计算误差', 'Attention 5项 / MLP投影 3项 / 共同出口 1项 / MLP组合 2项')
    ax.legend(loc='upper left', bbox_to_anchor=(.47, 1.13), ncol=2, frameon=False, fontsize=9.5, handletextpad=.4, columnspacing=1)
    ax.text(0, -.23, '每篇跨层/节点取最大，再统计1024篇；\n共同出口项包含其舍入损失。', transform=ax.transAxes, fontsize=9.5, color=GREY, va='top')

def layer_panel(ax, data):
    x = np.arange(1, 33)
    p50 = np.array([float(r['P50_percent']) for r in data['layers']])
    p95 = np.array([float(r['P95_percent']) for r in data['layers']])
    ax.fill_between(x, p50, p95, color=BLUE, alpha=.10)
    ax.plot(x, p50, color=BLUE, linewidth=2.2, label='文档中位数 P50')
    ax.plot(x, p95, color=ORANGE, linewidth=2.1, linestyle='--', label='文档 P95')
    ax.scatter([31, 32], p50[-2:], color=BLUE, s=22, zorder=5)
    ax.scatter([31, 32], p95[-2:], color=ORANGE, s=22, zorder=5)
    for layer, value, offset, color in [(31, p50[-2], (-116, -25), BLUE), (32, p50[-1], (-111, -3), BLUE),
                                        (31, p95[-2], (-126, 10), ORANGE), (32, p95[-1], (-130, 4), ORANGE)]:
        ax.annotate(f'{layer}层 {value:.5f}%', (layer, value), xytext=offset, textcoords='offset points',
                    fontsize=9.5, color=color, arrowprops={'arrowstyle': '-', 'color': color, 'linewidth': .7})
    ax.set_xlim(.5, 33.1)
    ax.set_ylim(0, 2.85)
    ax.set_xticks([1, 4, 8, 12, 16, 20, 24, 28, 31, 32])
    ax.set_xlabel('Decoder 块序号（1—32；最终 RMSNorm 之前）')
    ax.set_ylabel('文档张量相对 L2（%）')
    ax.grid(axis='y')
    panel_title(ax, 'B  误差随32层传播', '1024篇文档等权；仅画块输出，不把最终归一化/词表当新层')
    outputs = data['cumulative_outputs']
    table = ax.table(cellText=[['最终 RMSNorm 后', f"{float(outputs[0]['P50_percent']):.5f}%", f"{float(outputs[0]['P95_percent']):.5f}%"],
                              ['词表 logits', f"{float(outputs[1]['P50_percent']):.5f}%", f"{float(outputs[1]['P95_percent']):.5f}%"]],
                     colLabels=['累计输出', 'P50', 'P95'], cellLoc='center', bbox=[.045, .65, .65, .31], colWidths=[.48, .26, .26])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#CED8E0')
        cell.set_linewidth(.6)
        cell.set_facecolor('#EDF3F7' if row == 0 else 'white')
    ax.legend(loc='center left', bbox_to_anchor=(.025, .47), frameon=False, fontsize=10)
    ax.text(0, -.23, '浅色带为 P50—P95 描述分位区间，不是置信区间。', transform=ax.transAxes, fontsize=9.5, color=GREY, va='top')

def residual_axes(fig, spec, data, compact=True):
    rows = data['residual_mechanism_1024']['rows']
    sub = spec.subgridspec(1, 3, wspace=.54 if compact else .38)
    axes = [fig.add_subplot(sub[i]) for i in range(3)]
    for ax, key, title, ylabel in zip(axes, ['absolute_RMSE', 'reference_RMS', 'pooled_relative_L2_percent'],
                                     ['绝对误差 RMSE', '参考信号 RMS', '相对 L2'],
                                     ['原数值单位', '原数值单位', '%（能量合池）']):
        values = [r[key] for r in rows]
        bars = ax.bar(range(3), values, width=.62, color=COLORS)
        ax.set_xticks(range(3), RESIDUAL_LABELS, fontsize=9.2 if compact else 12)
        ax.set_title(title, fontsize=11.5 if compact else 15, pad=13)
        ax.set_ylabel(ylabel, fontsize=9.5 if compact else 12)
        ax.set_ylim(0, max(values) * 1.27)
        ax.grid(axis='y')
        ax.tick_params(axis='y', labelsize=9 if compact else 11)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, value + max(values)*.035,
                    f'{value:.5g}', ha='center', va='bottom', fontsize=9.4 if compact else 12.5)
    return axes

def coverage_panel(ax, data):
    rows = data['coverage']
    x = np.array([float(r['epsilon']) for r in rows])
    y = np.array([float(r['score_coverage_percent']) for r in rows])
    ax.plot(x, y, color=BLUE, marker='o', markersize=4.3, linewidth=2.1)
    for epsilon in [.1, .2, .5]:
        index = list(x).index(epsilon)
        ax.scatter([x[index]], [y[index]], s=65, facecolors='white', edgecolors=ORANGE, linewidths=1.7, zorder=4)
    ax.set_xscale('log')
    ax.set_xlim(.0008, 6.5)
    ax.set_ylim(0, 105)
    ax.set_xticks(x, [f'{v:g}' for v in x], fontsize=9.1)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel('全词表 score 覆盖率（%）')
    ax.set_xlabel('绝对 logit 差阈值 ε（原始 logit 单位；对数坐标）')
    ax.grid(axis='y')
    panel_title(ax, 'D  全词表 logit 绝对差覆盖', '分母 13,300,147,200 个 logit 对；条件 |当前 − 参考| ≤ ε')
    card = '\n'.join(f'{eps:g} → {float(next(r for r in rows if float(r["epsilon"]) == eps)["score_coverage_percent"]):.5f}%' for eps in [.1, .2, .5])
    ax.text(.52, .10, '重点阈值\n' + card, transform=ax.transAxes, fontsize=11, linespacing=1.55,
            bbox={'boxstyle': 'round,pad=.6', 'facecolor': '#FFF7F0', 'edgecolor': '#E6CBB7'}, va='bottom')
    ax.text(0, -.23, '只画全 score 覆盖；ε 不是概率差，也不是相对误差百分比。', transform=ax.transAxes, fontsize=9.5, color=GREY, va='top')

def tv_panel(ax, data):
    x = np.asarray(data['position_tv_ecdf']['sorted_percent_all_positions'])
    y = np.arange(1, len(x)+1) / len(x)
    ax.plot(x, y, color=BLUE, linewidth=1.9)
    summary = next(r for r in data['tv_summary'] if r['pool'] == 'fixed_quota_pool' and r['metric'] == 'position_weighted_tv')
    for key, quantile in [('p50', .5), ('p95', .95), ('p99', .99), ('max', 1.)]:
        ax.scatter([float(summary[key + '_percent'])], [quantile], s=22, color=ORANGE, zorder=4)
    ax.set_xscale('symlog', linthresh=.1, linscale=.65)
    ax.set_xlim(0, 34)
    ax.set_ylim(0, 1.025)
    ax.set_xticks([0, .05, .1, .5, 1, 5, 10, 30], ['0', '0.05', '0.1', '0.5', '1', '5', '10', '30'])
    ax.set_yticks([0, .25, .5, .75, 1], ['0%', '25%', '50%', '75%', '100%'])
    ax.set_xlabel('TV（概率质量百分数；近零线性，其余对数）')
    ax.set_ylabel('累计位置比例')
    ax.grid(axis='y')
    panel_title(ax, 'E  逐位置 TV：完整经验累积分布', '103700个真实位置；包含全部尾部，最大值 29.72007%')
    top1 = data['top1']
    ax.text(.03, .075, f"Top-1 一致\n{top1['token_weighted_agreement_percent']:.5f}%\n（102647 / 103700）\n翻转 1053", transform=ax.transAxes,
            fontsize=10.6, linespacing=1.4, bbox={'boxstyle': 'round,pad=.6', 'facecolor': '#F1F6FA', 'edgecolor': '#CBD9E3'}, va='bottom')
    card = '\n'.join(f'{label}  {float(summary[key + "_percent"]):.5f}%' for label, key in [('P50', 'p50'), ('P95', 'p95'), ('P99', 'p99'), ('最大', 'max')])
    ax.text(.56, .075, card, transform=ax.transAxes, fontsize=10.6, linespacing=1.65,
            bbox={'boxstyle': 'round,pad=.6', 'facecolor': 'white', 'edgecolor': '#D7DEE5'}, va='bottom')
    ax.text(0, -.23, 'TV = ½Σ词表 |概率差|（温度1）；Top-1卡片是独立指标，非曲线上一点。', transform=ax.transAxes, fontsize=9.5, color=GREY, va='top')

def margin_panel(ax, data):
    rows = data['margin_buckets']
    rates = [float(r['within_bucket_flip_rate_percent']) if r['within_bucket_flip_rate_percent'] else None for r in rows]
    for i, rate in enumerate(rates):
        color = ORANGE if i < 2 else BLUE
        if rate is None:
            ax.text(i, .002, '未测', ha='center', fontsize=9)
        else:
            ax.bar(i, rate, color=color, width=.64)
            if rate == 0:
                ax.scatter([i], [0], marker='o', color=BLUE, s=25, zorder=4)
            ax.annotate(f'{rate:.4g}%' if rate else '0%', (i, rate), xytext=(0, 6), textcoords='offset points', ha='center', fontsize=9.5)
    ax.set_yscale('symlog', linthresh=.03, linscale=.75)
    ax.set_ylim(-.002, 105)
    ax.set_yticks([0, .01, .1, 1, 10, 50], ['0', '0.01', '0.1', '1', '10', '50'])
    ticks = [r['margin_bucket'].replace('0.01', '.01').replace('0.05', '.05').replace('0.1', '.1').replace('0.2', '.2').replace('0.5', '.5')
             + '\n' + r['flips'] + '/' + r['positions'] for r in rows]
    ax.set_xticks(range(8), ticks, fontsize=8.7)
    ax.set_xlabel('参考 Logit Margin 桶；下行为 翻转数 / 桶内位置数', labelpad=11)
    ax.set_ylabel('桶内翻转率（%；近零线性，其余对数）')
    ax.grid(axis='y')
    panel_title(ax, 'F  Top-1 翻转集中在低 Margin', '876/1053 次翻转的 Margin < 0.05；975/1053 次 < 0.1')
    ax.text(0, -.29, 'Margin = 参考最高 logit − 第二高 logit（原始 logit 单位，非概率差）。\n8个预定桶全部保留；右侧两个非空桶翻转率确为0%。', transform=ax.transAxes, fontsize=9.5, color=GREY, va='top')

def save_figure(fig, name, dimensions):
    fig.savefig(HERE / name, dpi=240)
    plt.close(fig)
    with Image.open(HERE / name) as im:
        assert im.size == dimensions
    return {'file': name, 'pixels': dimensions, 'dpi': 240}

def figures(data):
    fig = plt.figure(figsize=(20, 16))
    grid = fig.add_gridspec(3, 2, left=.105, right=.975, top=.895, bottom=.085,
                           wspace=.28, hspace=.68, height_ratios=[1.15, 1, 1.05])
    fig.suptitle('ScaleLLM数值误差：局部计算、累计传播与输出影响', fontsize=23, y=.975, fontweight='bold')
    fig.text(.5, .944, '1024篇文档 / 103700个真实位置 / 32层 / 128256词表', ha='center', fontsize=13)
    fig.text(.5, .922, '当前版本与数值参考比较；参考仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口与Host', ha='center', fontsize=11, color=GREY)
    local_panel(fig.add_subplot(grid[0, 0]), data)
    layer_panel(fig.add_subplot(grid[0, 1]), data)
    axes = residual_axes(fig, grid[1, 0], data, compact=True)
    box = grid[1, 0].get_position(fig)
    fig.text(box.x0, box.y1 + .034, 'C  第32层残差机制：全1024篇能量合池', fontsize=14.5, fontweight='bold')
    fig.text(box.x0, box.y1 + .017, '每阶段 N=424,755,200；Attention残差后不是纯Attention分支', fontsize=9.8, color=GREY)
    fig.text(box.x0, box.y0 - .066, '相加后（相对Attention残差后）：绝对RMSE +41.8%；参考RMS −1.57%。\n此处是全量能量合池，不是按文档的分位数。', fontsize=9.5, color=GREY, va='top')
    coverage_panel(fig.add_subplot(grid[1, 1]), data)
    tv_panel(fig.add_subplot(grid[2, 0]), data)
    margin_panel(fig.add_subplot(grid[2, 1]), data)
    fig.text(.5, .019, '相对L2、TV、logit绝对差和Top-1一致率是不同指标；固定配额数据的描述性统计，不是任务准确率或完整生成质量。', ha='center', fontsize=10.3, color=GREY)
    inventory = [save_figure(fig, 'main_overview.png', (4800, 3840))]
    with Image.open(HERE / 'main_overview.png') as im:
        im.resize((2400, 1920), Image.Resampling.LANCZOS).save(HERE / 'main_overview_preview.png', dpi=(120, 120))
    inventory.append({'file': 'main_overview_preview.png', 'pixels': [2400, 1920], 'description': '同一主图缩小预览；未重新计算或改变布局'})

    fig = plt.figure(figsize=(15, 6.8))
    spec = fig.add_gridspec(1, 1, left=.075, right=.98, bottom=.25, top=.71)
    residual_axes(fig, spec[0], data, compact=False)
    fig.suptitle('第32层残差合并：实际误差与参考信号的变化', fontsize=21, fontweight='bold', y=.96)
    fig.text(.5, .885, '全1024篇 / 103700位置 × 4096通道；每阶段424,755,200个数值，按能量合池', ha='center', fontsize=12)
    fig.text(.5, .825, 'Attention残差后是MLP的残差基底；MLP分支在第二次残差相加前测量', ha='center', fontsize=12, color=GREY)
    factors = data['residual_mechanism_1024']['final_vs_attention_residual']
    fig.text(.5, .11, f"相对Attention残差后：绝对RMSE +{100*(factors['absolute_RMSE_factor']-1):.2f}%    参考RMS {100*(factors['reference_RMS_factor']-1):.2f}%    相对L2 +{100*(factors['relative_L2_factor']-1):.2f}%", ha='center', fontsize=13)
    fig.text(.5, .045, '两路参考信号相消，而误差近乎不相消；不等于FP32加法自身舍入大，也不把能量抵消比例当成幅度下降。', ha='center', fontsize=11, color=GREY)
    inventory.append(save_figure(fig, 'layer32_residual_detail.png', (3600, 1632)))

    fig, axes = plt.subplots(1, 3, figsize=(15, 6.8))
    fig.subplots_adjust(left=.075, right=.98, bottom=.22, top=.70, wspace=.35)
    pure = data['pure_branches_3docs']
    for ax, key, title, unit in zip(axes, ['absolute_rmse', 'reference_rms', 'relative_l2_percent'],
                                   ['绝对误差 RMSE', '参考信号 RMS', '相对 L2'], ['原数值单位', '原数值单位', '%']):
        values = [float(r[key]) for r in pure]
        bars = ax.bar([0, 1], values, color=[BLUE, GREEN], width=.56)
        ax.set_xticks([0, 1], ['Attention\n纯分支输出', 'MLP\n纯分支输出'], fontsize=12)
        ax.set_title(title, fontsize=16, pad=15)
        ax.set_ylabel(unit, fontsize=12)
        ax.set_ylim(0, max(values)*1.25)
        ax.grid(axis='y')
        for bar, value in zip(bars, values):
            ax.text(bar.get_x()+bar.get_width()/2, value+max(values)*.04, f'{value:.7g}', ha='center', fontsize=13)
    fig.suptitle('第32层纯分支：Attention 与 MLP', fontsize=22, fontweight='bold', y=.96)
    fig.text(.5, .88, '仅3篇诊断文档 / 299位置；两个分支均在残差相加前测量；每分支1,224,704个数值', ha='center', fontsize=12)
    fig.text(.5, .82, '当前与参考轨迹比较；这不是全1024篇同口径纯分支统计', ha='center', fontsize=12, color=GREY)
    fig.text(.5, .09, 'MLP的绝对误差更大，同时参考幅度更大；这3篇中的相对L2反而较低。', ha='center', fontsize=13)
    fig.text(.5, .035, '尺度差异是观测关系，不能据此唯一归因某个舍入算子；完整全量残差机制见独立大图。', ha='center', fontsize=11, color=GREY)
    inventory.append(save_figure(fig, 'pure_attention_mlp_3docs.png', (3600, 1632)))
    return inventory

def html_table(rows, columns):
    lines = ['<div class="table-wrap"><table><thead><tr>']
    lines += ['<th>' + html.escape(title) + '</th>' for key, title in columns]
    lines += ['</tr></thead><tbody>']
    for row in rows:
        lines.append('<tr>')
        for key, title in columns:
            value = row.get(key)
            exact = '未测' if value is None or value == '' else str(value)
            numeric = False
            if exact != '未测':
                try:
                    value_float = float(value)
                    numeric = True
                    if key in ['positions', 'flips', 'cumulative_flips', 'count', 'scalar_count', 'score_within_count', 'score_total_count', 'document_within_count', 'document_total_count', '统计单位数', '文档数', '每文档site数', '层号从1开始', 'sample_count', 'matches', 'total']:
                        display = f'{int(value_float):,}'
                    else:
                        display = f'{value_float:.7g}'
                except (ValueError, TypeError):
                    display = exact
            else:
                display = exact
            lines.append(f'<td class="{"num" if numeric else "text"}" title="{html.escape(exact, quote=True)}">{html.escape(display)}</td>')
        lines.append('</tr>')
    lines.append('</tbody></table></div>')
    return ''.join(lines)

def tables(data):
    local = data['operators'][:11]
    layers = data['layers']
    outputs = data['cumulative_outputs']
    residual = data['residual_mechanism_1024']['rows']
    pure = data['pure_branches_3docs']
    all_tv = data['tv_summary']
    top1 = data['top1']
    top1_rows = [
        {'metric': '位置等权Top-1一致', 'matches': 102647, 'total': 103700, 'percent': top1['token_weighted_agreement_percent'], 'definition': '每个真实位置的两个Top1 ID是否一致；翻转1053'},
        {'metric': '文档等权平均位置一致率', 'matches': None, 'total': 1024, 'percent': top1['document_equal_weight_mean_agreement_percent'], 'definition': '先逐文档算一致率，再对1024文档等权平均'},
        {'metric': '全位置均一致的文档', 'matches': 397, 'total': 1024, 'percent': 100 * top1['all_positions_match_document_fraction'], 'definition': '一篇的全部保存位置Top1都一致才计为一致文档'},
    ]
    csv_specs = [
        ('local_computation_1024.csv', local), ('layer_outputs_1024.csv', layers),
        ('cumulative_outputs_1024.csv', outputs), ('layer32_residual_1024.csv', residual),
        ('vocabulary_coverage_1024.csv', data['coverage']), ('TV_1024.csv', all_tv),
        ('top1_1024.csv', top1_rows), ('margin_stratification_1024.csv', data['margin_buckets']),
        ('pure_branches_3docs.csv', pure)]
    for name, rows in csv_specs:
        write_csv(name, rows)
    quantile_cols = [('P50_percent', 'P50（%）'), ('P95_percent', 'P95（%）'), ('P99_percent', 'P99（%）'), ('max_percent', '最大（%）')]
    chapters = []
    def chapter(key, title, note, content):
        chapters.append((key, title, f'<section id="{key}"><h2>{title}</h2><p class="note">{note}</p>{content}</section>'))
    chapter('local', '1. 全量局部计算误差', '1024篇文档等权；每篇先跨层/预定义节点取最大tensor相对L2，再统计文档分位数。共同出口、组合计算与单算子口径有区别。单位为relative L2百分数，不是逐scalar相对误差占比。',
            html_table(local, [('名称', '测量项'), ('每文档site数', '每篇节点数')] + quantile_cols + [('口径', '固定输入与参考口径')]))
    chapter('layers', '2. 32个块输出的累计传播', '仅最终RMSNorm之前的32个decoder块输出，每行1024篇；文档张量relative L2百分数。P50—P95是描述分位区间，不是置信区间。',
            html_table(layers, [('层号从1开始', '块序号'), ('文档数', '文档数')] + quantile_cols))
    chapter('outputs', '3. 最终归一化与词表累计输出', '同一文本前缀下两条完整轨迹的文档张量relative L2；不是第33/34层。每行1024篇，全词表logits使用128256词表的共同FP32输出头。',
            html_table(outputs, [('stage', '输出位置'), ('文档数', '文档数')] + quantile_cols))
    chapter('residual', '4. 第32层全量残差机制', '全1024篇、103700位置×4096通道，每阶段424755200个数值；按总误差能量/总参考能量合池。Attention残差后不是纯Attention分支。此处仅有合池指标，P50/P95/P99与逐值最大误差未测，不填0。RMSE/RMS为原数值单位，相对L2为百分数。',
            html_table(residual, [('stage', '阶段'), ('scalar_count', '数值数'), ('absolute_RMSE', '绝对RMSE'), ('reference_RMS', '参考RMS'), ('pooled_relative_L2_percent', '合池相对L2（%）'), ('error_energy', '误差能量'), ('reference_energy', '参考能量')]))
    coverage_html = html_table(data['coverage'], [('epsilon', 'ε：原始logit单位'), ('score_within_count', '阈值内score数'), ('score_total_count', 'score总数'), ('score_coverage_percent', 'score覆盖（%）'), ('document_within_count', '全部score达标文档'), ('document_total_count', '文档总数'), ('document_all_scores_within_percent', '文档覆盖（%）')])
    tv_html = html_table(all_tv, [('pool', '集合'), ('metric', '测量项'), ('统计单位数', '统计单位数'), ('权重', '权重'), ('mean_percent', '均值TV（%）'), ('p50_percent', 'P50 TV（%）'), ('p95_percent', 'P95 TV（%）'), ('p99_percent', 'P99 TV（%）'), ('max_percent', '最大TV（%）')])
    top_html = html_table(top1_rows, [('metric', 'Top-1测量项'), ('matches', '一致数'), ('total', '分母'), ('percent', '一致率（%）'), ('definition', '定义')])
    chapter('distribution', '5. 全词表覆盖、TV与Top-1', '三个指标单位不同。logit覆盖是|当前−参考|≤ε，ε是原始logit单位；score分母13300147200。TV=0.5×全词表概率差绝对值之和，表内显示100×TV概率质量；位置/文档权重分开。Top-1数值一致率不是任务准确率；阈值覆盖与Top-1计数不是分位数统计，未测的分位数不以0代替。',
            '<h3>5.1 全词表绝对logit差覆盖</h3>' + coverage_html + '<h3>5.2 TV描述分布</h3>' + tv_html + '<h3>5.3 Top-1一致</h3>' + top_html)
    chapter('margin', '6. 参考Logit Margin与翻转', '1024篇、103700位置、1053翻转；Margin=参考top1 logit−top2 logit，非概率差。左闭右开固定8桶，表内所有计数保留。桶内翻转率=翻转数/该桶位置数；非空零翻转桶为0%，空桶为未测/NA。',
            html_table(data['margin_buckets'], [('margin_bucket', 'Margin桶'), ('positions', '位置数'), ('flips', '翻转数'), ('within_bucket_flip_rate_percent', '桶内翻转率（%）'), ('share_of_all_flips_percent', '占1053翻转（%）'), ('cumulative_share_of_all_flips_percent', '累计翻转占比（%）')]))
    chapter('pure', '7. 三篇诊断的纯Attention/MLP分支', '仅3篇、299位置；两个分支均在残差相加前测量，每分支1224704数值。这不是1024篇同口径纯分支比较。仅有合池RMSE/参考RMS/relative L2与实测绝对最大差，文档P50/P95/P99未测。',
            html_table(pure, [('branch', '纯分支'), ('count', '数值数'), ('absolute_rmse', '绝对RMSE'), ('reference_rms', '参考RMS'), ('relative_l2_percent', '相对L2（%）'), ('max_absolute_error', '绝对最大差')]))
    nav = ''.join(f'<a href="#{key}">{title}</a>' for key, title, body in chapters)
    links = ''.join(f'<li><a href="tables/{name}">{name}</a></li>' for name, rows in csv_specs)
    text = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ScaleLLM数值误差：完整表格</title><style>
:root{color-scheme:light}body{margin:0;background:#f3f6f9;color:#182b3a;font:16px/1.6 system-ui,"Noto Sans CJK SC",sans-serif}
main{max-width:1600px;margin:0 auto;padding:35px 30px 60px}h1{font-size:30px;line-height:1.35}h2{font-size:24px;margin-top:0}h3{margin-top:28px}
section{background:white;border:1px solid #d7e0e7;border-radius:12px;padding:25px;margin-top:24px}.note{border-left:4px solid #17689b;padding:10px 15px;background:#eef5fa}
nav{display:flex;gap:10px;flex-wrap:wrap}a{color:#17689b}nav a{background:white;border:1px solid #ccd9e3;border-radius:8px;padding:6px 12px;text-decoration:none}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #dce3e9;padding:10px 12px;vertical-align:top}th{background:#edf3f7;text-align:left;white-space:nowrap;position:sticky;top:0}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.text{min-width:100px}tr:nth-child(even){background:#f8fafc}tr:hover{background:#fff6e9}.small{font-size:14px;color:#566877}
@media print{body{background:white}main{padding:0}section{break-inside:avoid}nav{display:none}}
</style><main><h1>ScaleLLM数值误差：完整表格</h1>
<p>1024篇文档 / 103700个真实位置 / 32层；参考仍保留基础量化、ScaleCode、LUT/SwiGLU、共同出口与Host。仅复用已核数据，没有新模型实验。</p>
<p class="small">HTML精简显示7位有效数字；鼠标停留可见原值。下方CSV保留全部保存精度。缺失统计写“未测”，不写0。各章分母与聚合方式单独注明。</p>'''
    text += '<nav>' + nav + '</nav>' + ''.join(body for key, title, body in chapters)
    text += '<section><h2>完整精度CSV与来源</h2><ul>' + links + '</ul><p><a href="source_manifest.json">源SHA与口径</a> · <a href="plot_data.json">完整绘图数据</a> · <a href="index.html">图表查看入口</a></p></section></main></html>'
    (HERE / 'tables.html').write_text(text)
    return [str((Path('tables') / name)) for name, rows in csv_specs]

def main():
    started = time.monotonic()
    data, sources = source_data()
    save_json('plot_data.json', data)
    save_json('source_manifest.json', {'schema': 'redesigned_numerical_figures_v1',
        'scope': 'Existing full1024 statistics plus separately marked3-document pure-branch diagnosis; CPU presentation only',
        'source_files': sources, 'font': identity(FONT), 'plotter': identity(__file__),
        'desired_model': 'gpt-6.1-sol', 'desired_effort': 'xhigh', 'actual_model': 'unverified',
        'write_boundary': 'Only07_redesigned_figures_v1; original figures/data/reports/manifests unchanged',
        'independent_files': 'Root owns index.html; independent reviewer owns audit JSON; neither generated by this script',
        'unit_policy': 'relativeL2 percent; TV percent of probability mass; epsilon and margin in raw logit units; separate position/document/pooled denominators',
        'not_available': ['Full1024 token-wise hidden errors', 'Full1024 token-wise cosine', 'Full1024 same-definition pureAttention branch data'],
        'new_experiment': False})
    pngs = figures(data)
    print(json.dumps({'stage': 'PNGs_ready', 'images': pngs}, ensure_ascii=False), flush=True)
    csvs = tables(data)
    for src in sources:
        assert identity(src['path'])['sha256'] == src['sha256'], src['path']
    outputs = [p['file'] for p in pngs] + ['tables.html', 'plot_data.json', 'source_manifest.json'] + csvs
    save_json('output_manifest.json', {'execution_state': 'completed', 'new_experiment': False,
        'source_files_unchanged': True, 'outputs': [identity(HERE / name) for name in outputs],
        'images': pngs, 'pid': os.getpid(), 'wall_seconds': time.monotonic()-started,
        'versions': {'python': sys.version, 'numpy': np.__version__, 'matplotlib': matplotlib.__version__},
        'CPU_affinity': sorted(os.sched_getaffinity(0)), 'GPU_or_model_used': False,
        'preview': 'main_overview_preview.png is the same main image resized to50%, explicitly identified in its metadata and Root viewer',
        'Root_index_and_independent_review_excluded': True})
    print(json.dumps({'execution_state': 'completed', 'png_count': len(pngs), 'csv_count': len(csvs),
                      'wall_seconds': time.monotonic()-started, 'source_files_unchanged': True}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
