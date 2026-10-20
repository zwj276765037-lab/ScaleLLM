"""Six-column comparison: five local document maxima and final hidden output.

Independent additional figure; no imports from frozen aggregate/plot/model
modules and no GPU work.  Every document is kept.  The sixth column uses the
aggregate's final-normalization constraint bound, while its original relative
ratio state is retained explicitly in source_data (including undefined0/0).
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

COLUMNS = ('linear','rope','qk','softmax','pv','final_hidden')
LABELS = ('线性层','旋转位置编码','注意力打分','概率归一化','注意力加权','整体输出误差')
POSITIONS = (0.,1.,2.,3.,4.,5.45)


def identity(path):
    path=Path(path).resolve();digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1<<20),b''):digest.update(block)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest.hexdigest())


def require(condition,message):
    if not condition:raise ValueError(message)


def _extended(row):
    if row['state']=='unbounded':return Decimal('Infinity')
    require(row['state']=='finite','unestimable values cannot enter a successful-subset quantile')
    value=Decimal(row['value_decimal'])
    require(value.is_finite() and value>=0,'invalid finite document value')
    return value


def verify_quantiles(points,statistics):
    require(statistics['document_count']==len(points),'quantile document denominator differs')
    invalid=sum(point['state']=='unestimable' for point in points)
    require(statistics['unestimable_documents']==invalid,'unestimable count differs')
    require(statistics['unbounded_documents']==sum(point['state']=='unbounded' for point in points),'unbounded count differs')
    if invalid:
        require(statistics['state']=='unestimable' and statistics['quantiles']=={},'invalid document silently dropped from quantiles')
        return
    ordered=sorted(_extended(point) for point in points)
    for name,p in (('p50',Decimal('.5')),('p95',Decimal('.95'))):
        location=p*(len(ordered)-1);left=int(location);fraction=location-left
        if not fraction:value=ordered[left]
        elif ordered[left].is_infinite() or ordered[left+1].is_infinite():value=Decimal('Infinity')
        else:value=ordered[left]+fraction*(ordered[left+1]-ordered[left])
        stored=statistics['quantiles'][name]
        require((stored['state']=='unbounded')==value.is_infinite(),'quantile infinity state differs')
        if value.is_finite():
            require(stored['state']=='finite' and Decimal(stored['value_decimal'])==value,'document quantile does not match preserved values')


def collect_data(path):
    path=Path(path).resolve();aggregate=json.loads(path.read_text())
    require(aggregate.get('schema')=='m005_formal_numerical_aggregate_v1' and aggregate.get('execution_state')=='completed','completed formal aggregate required')
    docs=aggregate['documents'];n=aggregate['completed_documents'];planned=aggregate['planned_documents']
    require(type(n) is int and 0<n<=planned and len(docs)==n,'invalid document accounting')
    require(len({doc['doc_id'] for doc in docs})==n and len({doc['duplicate_cluster'] for doc in docs})==n,'document/cluster duplicate')
    require(aggregate['missing_documents']==planned-n,'missing target accounting differs')
    require(aggregate['failed_supplied_attempts']==aggregate['invalid_supplied_attempts']==0,'failed/invalid supplied attempt cannot be plotted as completed')
    pool=aggregate['distributions']['fixed_quota_pool'];columns=[]
    for key,label in zip(COLUMNS,LABELS):
        records=[]
        for doc in docs:
            bound=(doc['final_normalization']['constraint_bound'] if key=='final_hidden' else doc['local_family_bounds'][key])
            require(bound['state'] in ('finite','unbounded','unestimable'),'unknown document bound state')
            records.append(dict(doc_id=doc['doc_id'],duplicate_cluster=doc['duplicate_cluster'],domain=doc['domain'],tokens=doc['tokens'],
                                bound=bound,original_relative_error=doc['final_normalization']['relative_error'] if key=='final_hidden' else None))
        statistics=pool['final_normalization_bound' if key=='final_hidden' else 'local_'+key]
        verify_quantiles([record['bound'] for record in records],statistics)
        require(all(point.get('interval') is None for point in statistics['quantiles'].values()),'fixed-quota pooled figure cannot imply CI')
        columns.append(dict(key=key,label=label,point_count=n,points=records,statistics=statistics,
                            definition=('same document, final normalization hidden vector; not LM-head/logits/ACC' if key=='final_hidden' else
                                        'within-document maximum over all32 layers and all sites of this local node family')))
    source=identity(path)
    return dict(schema='m005_numerical_six_columns_v1',aggregate_source=source,plot_source=identity(__file__),
                planned_documents=planned,completed_documents=n,missing_documents=planned-n,target_state=aggregate['target_state'],
                collection_complete=aggregate['collection_complete'],full_target_achieved=aggregate['full_target_achieved'],
                independent_unit='operational document source cluster; iid/semantic independence not verified',
                columns=columns,all_document_points=6*n,percentile_definition='linear interpolation over all document bounds, in extended nonnegative reals',
                statistics_scope='fixed-quota pooled descriptive only; no confidence intervals',
                zero_infinite_unestimable='retain original states; no document filtering, no epsilon; original final0/0 ratio remains null',
                metric_definition='100*||current-reference||_2/||reference||_2 when reference norm positive; frozen minimal nonnegative constraint bound otherwise',
                reference='retained intermediate precision with the same base quantization/approximation functions/common exits',
                domain_counts=aggregate['domain_counts_completed'],accepted_attempts=[row['path'] for row in aggregate['accepted_attempts']],
                input_evidence_identities=aggregate['evidence_files'])


def finite_value(row):
    if row['state']!='finite':return None
    value=row.get('value')
    require(type(value) in (int,float) and math.isfinite(value) and value>=0,
            'finite Decimal outside the representable plotting range; cannot silently omit it')
    return value


def text_value(row):
    if row is None:return '不可估'
    if row['state']=='unbounded':return '∞'
    value=finite_value(row)
    return f'{value:.3g}%' if value is not None else '不可估'


def draw(data,output):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager,pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    font_path=subprocess.check_output(['fc-match','-f','%{file}','Noto Sans CJK SC'],text=True).strip()
    require(font_path and 'NotoSansCJK' in Path(font_path).name,'Noto Sans CJK font required')
    font_manager.fontManager.addfont(font_path);font_name=font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams.update({'font.family':font_name,'font.size':11,'axes.unicode_minus':False,'pdf.fonttype':42,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#A6AFBC',
                         'axes.labelcolor':'#26364A','xtick.color':'#425369','ytick.color':'#425369'})
    blue,orange,gray,ink='#27659A','#C86E24','#8F9CAA','#152D45'
    points=[record['bound'] for column in data['columns'] for record in column['points']]
    positive=[finite_value(point) for point in points if point['state']=='finite' and finite_value(point)>0]
    lower=10**math.floor(math.log10(min(positive))-.20) if positive else 1e-6
    upper=max(positive)*3.1 if positive else 1.
    fig,axis=plt.subplots(figsize=(13.5,7.25))
    fig.subplots_adjust(left=.095,right=.975,top=.745,bottom=.25)
    fig.suptitle('局部算子与整体输出的相对数值误差',fontsize=17,fontweight='bold',color=ink,y=.966)
    status='全部采集' if data['collection_complete'] else '部分结果'
    fig.text(.535,.902,f"已测 {data['completed_documents']}/{data['planned_documents']} 篇文本 · {status}",ha='center',fontsize=12,color='#566779')
    axis.set_yscale('log');axis.set_ylim(lower,upper);axis.set_xlim(-.57,6.12)
    axis.axvspan(-.57,4.72,color='#F7F9FC',zorder=0)
    axis.axvspan(4.72,6.12,color='#FFF4E4',zorder=0)
    axis.axvline(4.72,color='#C9BDAA',linewidth=1.0,zorder=1)
    axis.text(2.,1.045,'五类局部算子',transform=axis.get_xaxis_transform(),ha='center',fontsize=12,color=ink,fontweight='bold')
    axis.text(5.45,1.045,'最终隐藏向量',transform=axis.get_xaxis_transform(),ha='center',fontsize=12,color=ink,fontweight='bold')
    handles=[Line2D([],[],color=gray,marker='o',linestyle='',markersize=5,label='每篇文本'),
             Line2D([],[],color=blue,marker='o',linestyle='',markersize=7,label='中位数（50%文本）'),
             Line2D([],[],color=orange,marker='D',linestyle='',markersize=7,label='95%文本分位值')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.535,.861),ncol=3,frameon=False,fontsize=10.8,columnspacing=2.7)
    gray_count=0;per_column=[];exceptions=False
    for x,column in zip(POSITIONS,data['columns']):
        xs=[];ys=[];zero=[];infinite=[];invalid=[]
        for record in column['points']:
            jitter=(int(hashlib.sha256(record['doc_id'].encode()).hexdigest()[:8],16)/0xffffffff-.5)*.44
            point=record['bound']
            if point['state']=='finite':
                value=finite_value(point)
                if value>0:xs.append(x+jitter);ys.append(value)
                else:zero.append(x+jitter)
            elif point['state']=='unbounded':infinite.append(x+jitter)
            else:invalid.append(x+jitter)
        artist=axis.scatter(xs,ys,s=23,color=gray,alpha=.59,edgecolors='none',zorder=2)
        plotted=len(artist.get_offsets())
        if zero:axis.scatter(zero,[lower*1.15]*len(zero),marker='v',s=22,color=gray,zorder=2)
        if infinite:axis.scatter(infinite,[upper/1.32]*len(infinite),marker='^',s=22,color=gray,zorder=2)
        if invalid:axis.scatter(invalid,[lower*1.15]*len(invalid),marker='x',s=22,color=gray,zorder=2)
        exceptions|=bool(zero or infinite or invalid)
        rendered=plotted+len(zero)+len(infinite)+len(invalid);gray_count+=rendered
        require(rendered==column['point_count'],'document point dropped during rendering')
        per_column.append(dict(key=column['key'],document_points=rendered,finite_positive_points=plotted,
                               zero_points=len(zero),unbounded_points=len(infinite),unestimable_points=len(invalid)))
        for name,offset,color,marker in (('p50',-.075,blue,'o'),('p95',.075,orange,'D')):
            point=column['statistics']['quantiles'].get(name)
            if point is None:continue
            if point['state']=='finite':value=finite_value(point);y=value if value>0 else lower*1.15
            elif point['state']=='unbounded':y=upper/1.32
            else:continue
            axis.scatter(x+offset,y,s=77,color=color,marker=marker,edgecolors='white',linewidths=.85,zorder=5)
            if name=='p95':
                axis.annotate(text_value(point),(x+offset,y),xytext=(0,14),textcoords='offset points',ha='center',
                              fontsize=11.2,color=orange,fontweight='bold')
        if column['statistics']['state']=='unestimable':axis.text(x,upper/1.6,'不可估',ha='center',color='#566779',fontsize=10.5)
    local_points=[record['bound'] for column in data['columns'][:5] for record in column['points']]
    if all(point['state']=='finite' for point in local_points):
        observed=max(finite_value(point) for point in local_points)
        axis.text(.017,.953,f'本批局部观测最大：{observed:.4g}%',transform=axis.transAxes,color='#566779',fontsize=10.2,va='top')
    else:observed=None
    axis.set_xticks(POSITIONS,LABELS,fontsize=11);axis.tick_params(axis='x',pad=11,length=0)
    axis.yaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'))
    axis.set_ylabel('相对数值误差（%，对数坐标）',labelpad=12)
    axis.grid(axis='y',which='major',color='#DDE4EB',linewidth=.75);axis.set_axisbelow(True)
    fig.text(.095,.143,'前五列：每篇文本在该类算子的全部32层及调用位置取最大误差；第六列：同篇文本最终归一化后的隐藏向量误差。',fontsize=10.1,color=ink)
    fig.text(.095,.094,'整体输出不指语言模型输出头、logits或准确率。相对误差 = 100 × ‖当前实现 − 参考‖ / ‖参考‖；参考保留中间精度并使用相同出口。',fontsize=9.7,color='#566779')
    note=f"当前仅测 {data['completed_documents']}/{data['planned_documents']} 篇；每篇文本是一个统计单位，分位数为描述值，不是置信区间。"
    if data['collection_complete']:note=f"已测 {data['completed_documents']}/{data['planned_documents']} 篇；每篇文本是一个统计单位，固定域配额合池仅作描述，不是置信区间。"
    if exceptions:note+=' 零值/∞/不可估分别在坐标底部或顶部标示，未删除、未加常数。'
    fig.text(.095,.046,note,fontsize=9.9,color='#566779')
    png=output/'numerical_six_columns.png';pdf=output/'numerical_six_columns.pdf'
    fig.savefig(png,dpi=230,facecolor='white');fig.savefig(pdf,facecolor='white');plt.close(fig)
    require(gray_count==data['all_document_points'],'wrong total document point count')
    return dict(matplotlib=matplotlib.__version__,python=platform.python_version(),font=identity(font_path),font_family=font_name,
                size_inches=[13.5,7.25],png_dpi=230,all_gray_document_points=gray_count,per_column_points=per_column,
                local_observed_max_percent=observed,confidence_intervals_drawn=False,percentiles=['p50','p95'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv);data=collect_data(args.aggregate)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    require(not any(args.output_dir.iterdir()),'new empty output directory required; prior figures are immutable')
    data['render']=draw(data,args.output_dir)
    data['outputs']=[identity(args.output_dir/name) for name in ('numerical_six_columns.png','numerical_six_columns.pdf')]
    with (args.output_dir/'source_data.json').open('x') as handle:json.dump(data,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps(dict(output=str(args.output_dir.resolve()),completed=data['completed_documents'],planned=data['planned_documents'],
                          point_count=data['render']['all_gray_document_points'],source_sha256=data['aggregate_source']['sha256']),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
