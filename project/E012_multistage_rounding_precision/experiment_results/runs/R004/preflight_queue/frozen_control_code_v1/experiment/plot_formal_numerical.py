"""Plot document-level formal numerical aggregates, preserving partial status.

The fixed-quota pool is descriptive.  P50/P95 bands are percentiles, not CIs.
P99 is reported separately rather than drawing a misleading small-N tail curve.
This tool writes only new PNG/PDF/source-data files and never loads a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

FAMILIES = ('linear', 'rope', 'qk', 'softmax', 'pv')
LABELS = ('线性层', '旋转位置编码', '注意力打分', '概率归一化', '注意力加权')
DOMAINS = {'web': '网页', 'news': '新闻', 'reviews': '影评'}


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def collect_data(path):
    path = Path(path)
    report = json.loads(path.read_text())
    if report.get('schema') != 'm005_formal_numerical_aggregate_v1':
        raise ValueError('expected strict formal numerical aggregate')
    count, target = report['completed_documents'], report['planned_documents']
    docs = report['documents']
    if count != len(docs) or count + report['missing_documents'] != target or target != 1024:
        raise ValueError('aggregate document accounting differs')
    if len({doc['doc_id'] for doc in docs}) != count or len({doc['duplicate_cluster'] for doc in docs}) != count:
        raise ValueError('duplicate plotted document/cluster')
    if report['failed_supplied_attempts'] or report['invalid_supplied_attempts']:
        raise ValueError('failed/invalid supplied attempts cannot become a successful plot')
    if not count:
        raise ValueError('no measured documents to plot')
    complete = report['collection_complete']
    if complete != (count == target):
        raise ValueError('completion flag differs from coverage')
    pool = report['distributions']['fixed_quota_pool']
    for distribution in pool.values():
        if any(point.get('interval') is not None for point in distribution['quantiles'].values()):
            raise ValueError('fixed-quota pooled curve cannot carry an inferential confidence interval')
    if not complete:
        for statistics in report['distributions'].values():
            if any(point.get('interval') is not None for distribution in statistics.values() for point in distribution['quantiles'].values()):
                raise ValueError('partial plot cannot contain full-target confidence intervals')
    local_points = [dict(doc_id=doc['doc_id'], domain=doc['domain'], tokens=doc['tokens'],
                         family_bounds={name: doc['local_family_bounds'][name] for name in FAMILIES}) for doc in docs]
    title = (f'数值精度统计：已测 {count}/{target} 篇（固定域配额）' if complete else
             f'数值精度检查：已测 {count}/{target} 篇，部分预览')
    if complete and not report['full_target_achieved']:
        title += '；含不可估项'
    return dict(schema='m005_formal_numerical_plot_v1', measured_documents=count, planned_documents=target,
                missing_documents=report['missing_documents'], collection_complete=complete,
                full_target_achieved=report['full_target_achieved'], target_state=report['target_state'],
                title=title,
                domain_counts=report['domain_counts_completed'], domain_targets=report['domain_counts_planned'],
                actual_token_range=[min(doc['tokens'] for doc in docs), max(doc['tokens'] for doc in docs)],
                local_document_points=local_points,
                pooled_local={name: pool['local_' + name] for name in FAMILIES},
                pooled_five_family_max=pool['local_five_family_bound'],
                propagation=[dict(layer=layer+1, statistics=pool[f'propagation_layer_{layer:02d}']) for layer in range(32)],
                final_normalization=pool['final_normalization_bound'], domain_statistics=report['distributions'],
                metric_definition='minimum M>=0 with ||error|| <= M/100*||reference|| at all required coordinates',
                ordinary_positive_signal_case='100*||current-reference||_2/||reference||_2; per-document max before quantiles',
                zero_signal='original0/0 ratios remain null; all-zero exact document constraint bound0 is explicitly counted',
                band_definition='descriptive P50-to-P95 percentiles, not confidence intervals',
                pooling='fixed domain quotas, descriptive only; no pooled iid inference',
                p99_note=('small-N descriptive order/interpolation only; no population-tail inference' if count < 1024 else
                          'descriptive pooled P99; conditional within-domain rank CIs are separate in source_data'),
                aggregate_source=identity(path), aggregate_consumed_source_files=report['evidence_files'],
                plot_source=identity(__file__))


def _point(statistics, quantile):
    return statistics.get('quantiles', {}).get(quantile)


def _finite(point):
    return point is not None and point.get('state') == 'finite' and point.get('value') is not None and math.isfinite(point['value'])


def _format(point):
    if point is None:
        return '不可估'
    if point.get('state') == 'unbounded':
        return '∞'
    return f"{point['value']:.3g}%" if _finite(point) else '不可估'


def render(data, output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager, pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    import numpy as np

    font_path = subprocess.check_output(['fc-match','-f','%{file}','Noto Sans CJK SC'], text=True).strip()
    if not font_path or 'NotoSansCJK' not in Path(font_path).name:
        raise ValueError('Noto Sans CJK is required')
    font_manager.fontManager.addfont(font_path)
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams.update({'font.family':font_name, 'font.size':11, 'pdf.fonttype':42,
                         'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
                         'axes.edgecolor':'#A6AFBC', 'axes.labelcolor':'#26364A',
                         'xtick.color':'#425369', 'ytick.color':'#425369'})
    blue, orange, ink, gray = '#27659A', '#C86E24', '#152D45', '#566779'
    fig,(left,right)=plt.subplots(1,2,figsize=(14.6,8.0),gridspec_kw={'width_ratios':[1.03,1.17]})
    fig.subplots_adjust(left=.077,right=.977,top=.745,bottom=.34,wspace=.30)
    fig.suptitle(data['title'],fontsize=17,fontweight='bold',color=ink,y=.968)
    quota='；'.join(f"{DOMAINS[key]} {data['domain_counts'].get(key,0)}/{data['domain_targets'][key]}篇" for key in DOMAINS)
    lengths=data['actual_token_range']
    fig.text(.5,.91,quota+f"；实际长度 {lengths[0]}–{lengths[1]} token",ha='center',fontsize=11.5,color=gray)
    handles=[Line2D([],[],color=blue,marker='o',linewidth=1.9,label='中位数（50%文本）'),
             Line2D([],[],color=orange,marker='D',linestyle='--',linewidth=1.9,label='95%文本分位值')]
    if data['measured_documents']<=64:
        handles.append(Line2D([],[],color='#A5B0BD',marker='o',linestyle='',markersize=4,label='每篇文本的观测值'))
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.867),ncol=len(handles),frameon=False,fontsize=10.3)

    finite_local=[point['value'] for stats in data['pooled_local'].values() for point in stats.get('quantiles',{}).values() if _finite(point) and point['value']>0]
    lower=10**math.floor(math.log10(min(finite_local))-.25) if finite_local else 1e-6
    upper=max(finite_local)*6 if finite_local else 1
    left.set_yscale('log');left.set_ylim(lower,upper)
    if data['measured_documents']<=64:
        for doc in data['local_document_points']:
            jitter=(int(hashlib.sha256(doc['doc_id'].encode()).hexdigest()[:8],16)/0xffffffff-.5)*.50
            for index,name in enumerate(FAMILIES):
                point=doc['family_bounds'][name]
                if _finite(point) and point['value']>0:
                    left.scatter(index+jitter,point['value'],s=18,color='#8F9CAA',alpha=.55,zorder=2,edgecolors='none')
    for index,name in enumerate(FAMILIES):
        stats=data['pooled_local'][name]
        for quantile,offset,color,marker in (('p50',-.095,blue,'o'),('p95',.095,orange,'D')):
            point=_point(stats,quantile)
            if _finite(point):
                value=point['value'];y=value if value>0 else lower*1.15
                left.scatter(index+offset,y,s=61,color=color,marker=marker,edgecolors='white',linewidths=.7,zorder=4)
                if value==0:left.annotate('0',(index+offset,y),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8,color=color)
            elif point and point.get('state')=='unbounded':
                left.scatter(index+offset,upper/1.3,marker='^',color=color,s=65)
                left.text(index+offset,upper/1.14,'∞',ha='center',color=color)
        p95=_point(stats,'p95')
        if _finite(p95) and p95['value']>0:
            left.annotate(_format(p95),(index+.095,p95['value']),xytext=(0,13),textcoords='offset points',ha='center',fontsize=10,color=orange,fontweight='bold')
        if stats['state']=='unestimable':left.text(index,upper/2,'不可估',ha='center',color=gray)
    left.set_xlim(-.55,4.55);left.set_xticks(range(5),LABELS,fontsize=10.2)
    left.tick_params(axis='x',length=0,pad=11)
    left.yaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'))
    left.set_ylabel('每篇文本最差位置的相对误差（%，对数刻度）',labelpad=9)
    left.set_title('(a) 单个算子：每篇文本跨32层取最大误差',loc='left',fontsize=12.2,color=ink,pad=18)
    left.grid(axis='y',color='#DDE4EB',linewidth=.7);left.set_axisbelow(True)

    statistics=[row['statistics'] for row in data['propagation']]+[data['final_normalization']]
    positions=list(range(1,33))+[35]
    p50=[_point(stats,'p50') for stats in statistics];p95=[_point(stats,'p95') for stats in statistics]
    y50=np.array([point['value'] if _finite(point) else np.nan for point in p50],dtype=float)
    y95=np.array([point['value'] if _finite(point) else np.nan for point in p95],dtype=float)
    right.fill_between(positions,y50,y95,color=blue,alpha=.13,linewidth=0)
    right.plot(positions[:32],y50[:32],color=blue,linewidth=2,marker='o',markersize=2.6)
    right.plot(positions[:32],y95[:32],color=orange,linewidth=1.9,linestyle='--',marker='o',markersize=2.5)
    right.plot(positions[31:],y50[31:],color=blue,linewidth=1.6,linestyle=':')
    right.plot(positions[31:],y95[31:],color=orange,linewidth=1.6,linestyle=':')
    for values,color in ((y50,blue),(y95,orange)):
        right.scatter(35,values[-1],color=color,marker='D',s=54,edgecolors='white',linewidths=.7,zorder=5)
    finite_propagation=[value for value in [*y50,*y95] if math.isfinite(value)]
    ceiling=max(finite_propagation)*1.30 if finite_propagation and max(finite_propagation)>0 else 1
    right.set_ylim(0,ceiling)
    for series,color in ((p50,blue),(p95,orange)):
        for x,point in zip(positions,series):
            if point and point.get('state')=='unbounded':right.scatter(x,ceiling*.94,color=color,marker='^',s=35)
    if any(point and point.get('state')=='unbounded' for point in p50+p95):
        right.text(.02,.96,'顶部三角形表示∞，并非有限上限',transform=right.transAxes,color=gray,fontsize=9)
    if any(stats['state']=='unestimable' for stats in statistics):
        right.text(.02,.91,'不可估位置留空，未补值或连线填补',transform=right.transAxes,color=gray,fontsize=9)
    for point,color,offset in ((p95[-1],orange,12),(p50[-1],blue,-18)):
        if _finite(point):right.annotate(_format(point),(35,point['value']),xytext=(-6,offset),textcoords='offset points',ha='right',color=color,fontweight='bold',fontsize=10.7)
    right.set_xlim(0,37.4);right.set_xticks([1,8,16,24,32,35],['1','8','16','24','32','末端\n归一化'])
    right.tick_params(axis='x',pad=8);right.set_xlabel('解码层（1–32）与归一化终点',labelpad=8)
    right.set_ylabel('隐藏向量的相对误差（%）',labelpad=9)
    right.set_title('(b) 误差累积：32层传播与最终归一化',loc='left',fontsize=12.2,color=ink,pad=18)
    right.grid(axis='y',color='#DDE4EB',linewidth=.7);right.set_axisbelow(True)

    p99local=_format(_point(data['pooled_five_family_max'],'p99'))
    p99final=_format(_point(data['final_normalization'],'p99'))
    if data['collection_complete']:
        for index,key in enumerate(DOMAINS):
            stats=data['domain_statistics'][key]
            text=f"{DOMAINS[key]} N={data['domain_counts'].get(key,0)}\n局部五类总最大 P95 {_format(_point(stats['local_five_family_bound'],'p95'))}；末端 P95 {_format(_point(stats['final_normalization_bound'],'p95'))}"
            fig.text(.077+index*.305,.222,text,fontsize=9.4,color=gray,linespacing=1.5)
        note=f'合池 P99（描述值）：局部五类总最大 {p99local}；末端 {p99final}。域内条件秩区间另存源数据，图中不混作合池置信区间。'
    else:
        note=f"P99 仅列描述值：局部五类总最大 {p99local}；末端 {p99final}。当前 N={data['measured_documents']}，不作总体尾部推断或完整目标置信区间。"
    fig.text(.077,.188,note,fontsize=10.0,color=gray)
    fig.text(.077,.137,'相对误差 = 100 × ‖当前实现 − 参考‖ / ‖参考‖；参考保留中间精度，两路使用相同算子出口。',fontsize=10.4,color=ink)
    fig.text(.077,.092,'每篇文本是一个统计单位；左图包含该文本内的全部层与调用位置。阴影为中位数到95%分位的描述带，不是置信区间。',fontsize=10.0,color=gray)
    exceptional = any(stats['unbounded_documents'] or stats['unestimable_documents'] or stats['all_zero_exact_documents']
                      for stats in data['domain_statistics']['fixed_quota_pool'].values())
    footnote = ('出现零参考、无穷或不可估情况；技术定义和计数详见源数据，相关文本未从分母中删除。' if exceptional else
                f"当前已测 {data['measured_documents']} 篇，目标 {data['planned_documents']} 篇；网页、新闻、影评按固定配额合并，仅作描述统计。")
    fig.text(.077,.047,footnote,fontsize=9.7,color=gray)
    fig.savefig(output/'formal_numerical_overview.png',dpi=220,facecolor='white')
    fig.savefig(output/'formal_numerical_overview.pdf',facecolor='white')
    plt.close(fig)
    return dict(matplotlib=matplotlib.__version__,python=platform.python_version(),font=identity(font_path),font_family=font_name,
                size_inches=[14.6,8.0],png_dpi=220,plotted_percentiles=['p50','p95'],p99_drawn_as_curve=False,
                band='descriptive P50–P95, not CI',partial=data['target_state']!='complete')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    data=collect_data(args.aggregate)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if any(args.output_dir.iterdir()):raise FileExistsError('use a new empty plot directory')
    data['render']=render(data,args.output_dir)
    data['outputs']=[identity(args.output_dir/name) for name in ('formal_numerical_overview.png','formal_numerical_overview.pdf')]
    with (args.output_dir/'source_data.json').open('x') as handle:
        json.dump(data,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps(dict(output=str(args.output_dir.resolve()),measured=data['measured_documents'],planned=data['planned_documents'],
                          partial=not data['collection_complete'],source_sha=data['aggregate_source']['sha256']),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
