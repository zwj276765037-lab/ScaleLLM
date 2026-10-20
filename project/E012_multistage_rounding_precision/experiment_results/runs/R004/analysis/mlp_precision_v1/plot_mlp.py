"""Additional B001 MLP projection figure; no model or frozen-source imports."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


def identity(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.summary.read_text())
    ops = ('gate_proj', 'up_proj', 'down_proj')
    labels = ('门投影（Gate）', '上投影（Up）', '下投影（Down）')
    points = [{**{k: doc[k] for k in ('doc_id', 'domain', 'duplicate_cluster')},
               'op': op, 'bound': doc['projections'][op]} for doc in data['documents'] for op in ops]
    if any(x['bound']['state'] != 'finite' or x['bound']['value'] <= 0 for x in points):
        raise ValueError('this B001-only figure requires finite positive data; source states must not be dropped or replaced')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in ('mlp_projection_precision.png', 'mlp_projection_precision.pdf', 'source_data.json'):
        if (args.output_dir / name).exists():
            raise ValueError('new figure output filenames required')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager, pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    font = subprocess.check_output(['fc-match', '-f', '%{file}', 'Noto Sans CJK SC'], text=True).strip()
    font_manager.fontManager.addfont(font)
    plt.rcParams.update({'font.family': font_manager.FontProperties(fname=font).get_name(),
                         'font.size': 11, 'axes.unicode_minus': False, 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#A6AFBC'})
    gray, blue, orange, ink = '#8F9CAA', '#27659A', '#C86E24', '#152D45'
    fig, ax = plt.subplots(figsize=(9.2, 6.4))
    fig.subplots_adjust(left=.135, right=.96, top=.75, bottom=.28)
    fig.suptitle('MLP三个投影：同输入局部舍入误差', fontsize=16, color=ink, fontweight='bold', y=.958)
    fig.text(.55, .892, f"已测 {data['completed_documents']}/{data['planned_documents']} 篇文本 · 部分结果", ha='center', color='#566779', fontsize=11.5)
    fig.legend(handles=[Line2D([], [], marker='o', color=gray, linestyle='', label='每篇文本'),
                        Line2D([], [], marker='o', color=blue, linestyle='', label='中位数（P50）'),
                        Line2D([], [], marker='D', color=orange, linestyle='', label='95%文本分位值（P95）')],
               loc='upper center', bbox_to_anchor=(.55, .856), ncol=3, frameon=False, fontsize=10)
    values = [x['bound']['value'] for x in points]
    ax.set_yscale('log')
    ax.set_ylim(min(values) / 1.9, max(values) * 2.0)
    ax.set_xlim(-.5, 2.5)
    ax.set_facecolor('#F7F9FC')
    counts = {}
    for i, op in enumerate(ops):
        selected = [x for x in points if x['op'] == op]
        xx = [i + (int(hashlib.sha256(x['doc_id'].encode()).hexdigest()[:8], 16) / 0xffffffff - .5) * .4 for x in selected]
        artist = ax.scatter(xx, [x['bound']['value'] for x in selected], s=29, color=gray, alpha=.7, edgecolors='none', zorder=3)
        counts[op] = len(artist.get_offsets())
        if counts[op] != data['completed_documents']:
            raise ValueError('document point dropped')
        for key, offset, color, marker in (('p50', -.065, blue, 'o'), ('p95', .065, orange, 'D')):
            value = data['projections'][op][key]['value']
            ax.scatter(i + offset, value, s=84, color=color, marker=marker, edgecolors='white', linewidths=.8, zorder=5)
            if key == 'p95':
                ax.annotate(f'{value:.4g}%', (i + offset, value), xytext=(0, 14), textcoords='offset points',
                            ha='center', color=color, fontsize=11, fontweight='bold')
    ax.set_xticks(range(3), labels)
    ax.tick_params(axis='x', length=0, pad=12)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
    ax.set_ylabel('相对数值误差（%，对数坐标）', labelpad=12)
    ax.grid(axis='y', which='major', color='#DDE4EB', linewidth=.8)
    ax.set_axisbelow(True)
    fig.text(.135, .178, '每个点：一篇文本在同一投影的32层中取最大误差；统计单位为文本，分位值不是置信区间。', fontsize=9.5, color=ink)
    fig.text(.135, .127, '相对误差 = 100 × ‖当前实现 − 高精度参考‖ / ‖高精度参考‖；两者使用同一输入和共同输出接口。', fontsize=9.1, color='#566779')
    fig.text(.135, .076, '仅覆盖三个投影；SiLU、门控逐元素乘法、整个MLP及其残差尚未独立测量。', fontsize=9.6, color='#566779')
    png = args.output_dir / 'mlp_projection_precision.png'
    pdf = args.output_dir / 'mlp_projection_precision.pdf'
    fig.savefig(png, dpi=230, facecolor='white')
    fig.savefig(pdf, facecolor='white')
    plt.close(fig)
    source = dict(schema='m005_b001_mlp_projection_figure_v1',
                  planned_documents=data['planned_documents'], completed_documents=data['completed_documents'],
                  missing_documents=data['missing_documents'], partial=True,
                  summary_source=identity(args.summary), plot_source=identity(__file__),
                  underlying_sources=data['sources'], all_document_points=points, projections=data['projections'],
                  render=dict(total_document_points=sum(counts.values()), per_projection_document_points=counts,
                              quantiles=['p50', 'p95'], confidence_intervals=False, font=identity(font),
                              size_inches=[9.2, 6.4], matplotlib_version=matplotlib.__version__),
                  outputs=[identity(png), identity(pdf)])
    with (args.output_dir / 'source_data.json').open('x') as stream:
        json.dump(source, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(source['render'], ensure_ascii=False))


if __name__ == '__main__':
    main()
