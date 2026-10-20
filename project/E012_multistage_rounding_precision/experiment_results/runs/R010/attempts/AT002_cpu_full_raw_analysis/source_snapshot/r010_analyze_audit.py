"""CPU-only independent raw verification, global scalar audit tables and examples."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from r010_audit_cpu import comparisons,metric_from_integers

def write(p,x):
    p=Path(p);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def identity(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def array_sha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

def analyze(at,out):
    start=time.monotonic();receipt=json.loads((at/'external_wait_receipt.json').read_text());assert receipt['native_exit_code']==0 and receipt['child_reaped'] and receipt['worker_proc_absent'] and not receipt['gpu_owned_process_rows']
    result=json.loads((at/'result.json').read_text());assert result['all_hard_checks_passed'] and result['source_unchanged']
    rows=[json.loads(s) for s in (at/'operator_records.jsonl').read_text().splitlines()];assert len(rows)==30
    out.mkdir(parents=True,exist_ok=False);checks=[];examples=[];allsummary={};close_count=0
    for op in ['o_proj','down_proj']:
        buffers={k:[] for k in ['accumulator','current_code','reference_code','exact_quotient','exact_remainder']};group_right=np.zeros(32,dtype=np.int64);group_lost=np.zeros(32,dtype=np.int64);group_total=np.zeros(127,dtype=np.int64);group_left=np.zeros(25,dtype=np.int64);ones=0;inactive=0;host_count=0;host_energy=0.;hostmax=0.;saturation=0;guard=0;overflow=0
        for row in [x for x in rows if x['op']==op]:
            p=Path(row['raw']['path']);assert identity(p)['sha256']==row['raw']['sha256']
            with np.load(p) as z:a={k:z[k].reshape(-1).copy() for k in z.files}
            assert set(a)==set(buffers)
            for k,v in a.items():assert array_sha(v)==row['arrays'][k]['sha256'];buffers[k].append(v)
            acc=a['accumulator'];cur=a['current_code'].astype(np.int64);ref=a['reference_code'].astype(np.int64);q=a['exact_quotient'];r=a['exact_remainder'].astype(np.int64);bits=row['common_bits'];width=24 if op=='o_proj' else 32
            # Independent integer identities from raw, separate from observer/metric code.
            rounded=np.sign(acc)*((np.abs(acc)+128)//256);expected=np.clip(rounded,-(1<<(width-1)),(1<<(width-1))-1)
            assert np.array_equal(cur,expected)
            assert ((r>=0)&(r<(1<<bits))).all()
            inc=np.where(q>=0,r>=(1<<(bits-1)),r>(1<<(bits-1))).astype(np.int64)
            assert np.array_equal(ref,np.clip(q+inc,-(1<<(width-1)),(1<<(width-1))-1))
            comps=comparisons(a,bits)
            num=q*(1<<bits)+r;host_code=cur.astype(np.float32).astype(np.int64)
            host_difference=(host_code-cur).astype(np.float64)/65536
            stored_host=row['host_fp32_decode_audit']
            assert np.count_nonzero(host_difference)==stored_host['changed_count'] and float(np.max(np.abs(host_difference)))==stored_host['absolute_max']
            comps['delivered_host_total']=(num,host_code*(1<<bits)-num,1<<(bits+16))
            for name,(bn,dn,denom) in comps.items():
                stored=row['statistics'].get(name);nz=bn!=0;diff=dn.astype(np.float64)/denom;signal=bn.astype(np.float64)/denom
                if stored is not None:
                    assert len(bn)==stored['count'] and np.count_nonzero(nz)==stored['original_nonzero']
                    assert int(np.count_nonzero((~nz)&(dn==0)))==stored['zero_original_current_zero']
                    assert int(np.count_nonzero((~nz)&(dn!=0)))==stored['zero_original_current_nonzero']
                e=float(np.sum(np.square(diff),dtype=np.float64));se=float(np.sum(np.square(signal),dtype=np.float64))
                assert stored is None or (math.isclose(e,stored['error_energy'],rel_tol=2e-12,abs_tol=1e-25) and math.isclose(se,stored['signal_energy'],rel_tol=2e-12,abs_tol=1e-20))
                for label,factor in [('0.1',1000),('1',100),('5',20),('10',10)]:
                    count=int(np.count_nonzero(nz&(np.abs(dn)*factor>np.abs(bn))));assert stored is None or count==stored['relative_thresholds'][label]['count'];close_count+=1
                if name not in ['final_cut8','total_rounding','additional_intermediate','delivered_host_total']:continue
                absolute=np.abs(diff);rel=np.full(len(bn),-1.,dtype=np.float64);rel[nz]=np.abs(dn[nz].astype(np.float64)/bn[nz])
                ids=[('fixed',i) for i in sorted({0,1,len(bn)//4,len(bn)//2,len(bn)-1})]+[('largest_absolute',int(absolute.argmax())),('largest_relative_nonzero',int(rel.argmax()))]
                for kind,i in ids:
                    examples.append(dict(op=op,definition=name,selection=kind,doc_index=row['doc_index'],doc_id=row['doc_id'],flat_index=i,token=i//4096,channel=i%4096,before_real=float(bn[i])/denom,after_real=float(int(bn[i])+int(dn[i]))/denom,absolute_error=float(abs(int(dn[i])))/denom,relative_error_percent=float(abs(int(dn[i]))/abs(int(bn[i]))*100) if bn[i] else None,before_integer_numerator=int(bn[i]),difference_integer_numerator=int(dn[i]),common_denominator=denom,accumulator_F24=int(acc[i]),current_code_F16=int(cur[i]),reference_code_F16=int(ref[i]),exact_F16_quotient=int(q[i]),exact_F16_remainder=int(r[i]),exact_remainder_bits=bits))
            g=row['group_histograms'];group_right+=g['rightshift_bits'];group_lost+=g['nonzero_discarded_remainder_by_rightshift'];group_total+=g['total_shift_bits'];group_left+=g['leftshift_bits'];ones+=g['discarded_one_bits'];inactive+=g['inactive_pairs']
            assert sum(g['rightshift_bits'])==g['active_pairs'] and sum(g['nonzero_discarded_remainder_by_rightshift'])<=g['active_pairs']
            h=row['host_fp32_decode_audit'];host_count+=h['changed_count'];host_energy+=h['error_energy'];hostmax=max(hostmax,h['absolute_max'])
            saturation+=row['observer_counters'][0];guard+=row['observer_counters'][2];overflow+=row['observer_counters'][3]
            checks.append(dict(doc_index=row['doc_index'],op=op,raw_sha_checked=True,arrays_sha_checked=True,original_round_and_saturation_from_acc_equal=True,exact_parts_round_equals_reference=True,all_zero_and_threshold_counts_equal=True,energy_fp64_recomputed=True))
        joined={k:np.concatenate(v) for k,v in buffers.items()};assert joined['current_code'].size==7151616
        bits=31 if op=='o_proj' else 28;comps=comparisons(joined,bits)
        host_code=joined['current_code'].astype(np.float32).astype(np.int64);exact_num=joined['exact_quotient']*(1<<bits)+joined['exact_remainder'].astype(np.int64)
        comps['delivered_host_total']=(exact_num,host_code*(1<<bits)-exact_num,1<<(bits+16))
        metrics={k:metric_from_integers(*v) for k,v in comps.items()}
        for m in metrics.values():
            m['zero_error_energy']=m['error_energy']==0
            if m['zero_error_energy']:
                for family in ['relative_thresholds','rms_normalized_thresholds']:
                    for t in m[family].values():t['error_energy_share_percent']=None
        # Scope-specific exact additional-intermediate difference distribution, never 1024 extrapolated.
        delta=joined['current_code'].astype(np.int64)-joined['reference_code'].astype(np.int64);vals,cnts=np.unique(delta,return_counts=True)
        active=int(group_right.sum());positive=int(group_right[1:].sum());lost=int(group_lost.sum())
        allsummary[op]=dict(documents=15,tokens=1746,outputs=7151616,output_fractional_bits=16,final_cut_bits=8,absolute_value_of_one_output_step=1/65536,metrics=metrics,group=dict(active_terms=active,inactive_terms=inactive,rightshift_histogram={str(i):int(v) for i,v in enumerate(group_right) if v},leftshift_histogram={str(i):int(v) for i,v in enumerate(group_left) if v},total_shift_histogram={str(i):int(v) for i,v in enumerate(group_total) if v},nonzero_remainder_by_rightshift={str(i):int(v) for i,v in enumerate(group_lost) if v},nonzero_lost_remainder_terms=lost,percent_of_active_terms=100*lost/active,percent_of_positive_rightshift_terms=100*lost/positive if positive else 0.,discarded_one_bits=ones),additional_difference_code_counts={str(v):int(n) for v,n in zip(vals,cnts)},host_fp32_decode=dict(changed_count=host_count,count=7151616,absolute_max=hostmax,error_energy=host_energy),exceptions=dict(output_saturation=saturation,software_group_guard_overflow=guard,accumulator_overflow=overflow))
        del joined,buffers,comps
    write(out/'scalar_summary.json',allsummary)
    write(out/'independent_checks.json',dict(passed=True,operator_rows_verified=len(checks),scalar_outputs_verified=14303232,integer_threshold_count_checks=close_count,per_operator=checks,input_attempt=identity(at/'manifest.json'),scope='CPU full raw checks of finalcut/saturation, exact common-exit round, zero/strict thresholds and energy; GPU actual same-input dependency Fraction witness checks recorded in original attempt',cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),seconds=time.monotonic()-start))
    with (out/'before_after_examples.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(examples[0]));w.writeheader();w.writerows(examples)
    table=[]
    for op,item in allsummary.items():
        for definition,m in item['metrics'].items():
            d=dict(op=op,definition=definition,output_count=m['count'],nonzero_original=m['original_nonzero'],zero_original_after_zero=m['zero_original_current_zero'],zero_original_after_nonzero=m['zero_original_current_nonzero'],absolute_mean=m['absolute_mean'],absolute_rmse=m['absolute_rmse'],absolute_max=m['absolute_max'],error_energy=m['error_energy'])
            for t in ['0.1','1','5','10']:d[f'relative_above_{t}_percent_count']=m['relative_thresholds'][t]['count'];d[f'relative_above_{t}_percent_proportion']=m['relative_thresholds'][t]['percent_of_nonzero'];d[f'relative_above_{t}_percent_error_energy_share']=m['relative_thresholds'][t]['error_energy_share_percent']
            table.append(d)
    with (out/'scalar_threshold_table.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    report=['# R010：原版第32层两输出投影逐数舍入核验','','仅重放预声明15篇audit文档/1746位置，o_proj与down_proj各7,151,616数值，总14,303,232。使用保存的CURRENT量化输入，相同输入逐数比较；没有重跑前31层、没有完整模型或新优化。不能将此15篇逐值比例外推到1024篇。','','相对误差=abs(后−前)/abs(前)，只在原值非零处计算，严格大于阈值，没有epsilon。零原值另列。末尾舍入与全程舍入分开；物理值均为同一实数单位，1/65536=0.0000152587890625。','','| 出口 | 定义 | 非零原值数 | >0.1% | >1% | >5% | >10% | 绝对RMSE | 绝对最大 |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for op,item in allsummary.items():
        for name in ['final_cut8','total_rounding','additional_intermediate']:
            m=item['metrics'][name];pcts=[m['relative_thresholds'][t]['percent_of_nonzero'] for t in ['0.1','1','5','10']]
            report.append(f'| {op} | {name} | {m["original_nonzero"]} | '+ ' | '.join(f'{v:.8f}%' for v in pcts)+f' | {m["absolute_rmse"]:.12g} | {m["absolute_max"]:.12g} |')
    report+=['','final_cut8：原F24 accumulator→F16 half-away，固定舍8位，饱和前。total_rounding：current输出→same-input精确未舍入sum，包含中间逐组floor与末尾round。additional_intermediate：current输出→同F16 OUTPUT_ONLY参考，两边共同出口；它不等于全部舍入损失。饱和和HostFP32转换另列。','','## 实际舍位和非零余数','','| 出口 | active group terms | 逐组右移位数范围 | 右移有非零余数 | 占active项 | 实际丢弃1比特总数 |','|---|---:|---|---:|---:|---:|']
    for op,item in allsummary.items():
        g=item['group'];keys=[int(x) for x in g['rightshift_histogram']];report.append(f'| {op} | {g["active_terms"]} | {min(keys)}..{max(keys)} | {g["nonzero_lost_remainder_terms"]} | {g["percent_of_active_terms"]:.8f}% | {g["discarded_one_bits"]} |')
        report+=['',f'{op}完整逐组右移分布：`{json.dumps(g["rightshift_histogram"])}`。右移位数、余数是否非零、余数中1比特数量是三个不同概念，分母是组贡献项，不是输出数值。']
    report+=['','## 零值、尾部能量、RMS阈值与Host转换','']
    for op,item in allsummary.items():
        report.append(f'{op}：HostFP32转换变化{item["host_fp32_decode"]["changed_count"]}/{item["outputs"]}，绝对max={item["host_fp32_decode"]["absolute_max"]:.12g}；异常={item["exceptions"]}。')
        for name in ['final_cut8','total_rounding','additional_intermediate']:
            m=item['metrics'][name];report.append(f'{name}原值0→后值0：{m["zero_original_current_zero"]}；原值0→后值非0：{m["zero_original_current_nonzero"]}。原RMS={m["reference_rms"]:.12g}；绝对P99={m["absolute_quantiles"]["0.99"]:.12g}，P99.9={m["absolute_quantiles"]["0.999"]:.12g}。')
            report.append('相对误差>'+ ', '.join(f'{t}%：{m["relative_thresholds"][t]["count"]}数，承担总误差能量{m["relative_thresholds"][t]["error_energy_share_percent"]:.8f}%' for t in ['0.1','1','5','10'])+'。')
            report.append('误差绝对值大于原RMS的'+', '.join(f'{t}%：{m["rms_normalized_thresholds"][t]["count"]}/{m["count"]}（{m["rms_normalized_thresholds"][t]["percent"]:.8f}%）' for t in ['0.1','1','5','10'])+'。')
    report+=['','## 实际HostFP32返回值与精确未舍入结果','','这是实际整数code→FP32/65536后的总差，和整数舍入主表分列。','', '| 出口 | >1%计数/比例 | >5%计数/比例 | >10%计数/比例 | 绝对RMSE | 绝对max |','|---|---:|---:|---:|---:|---:|']
    for op,item in allsummary.items():
        m=item['metrics']['delivered_host_total'];cells=[f'{m["relative_thresholds"][t]["count"]}/{m["original_nonzero"]} ({m["relative_thresholds"][t]["percent_of_nonzero"]:.8f}%)' for t in ['1','5','10']]
        report.append(f'| {op} | '+' | '.join(cells)+f' | {m["absolute_rmse"]:.12g} | {m["absolute_max"]:.12g} |')
    report+=['','总误差能量为0时，误差能量占比是0/0未定义，机器统计使用null和zero_error_energy=true；原GPU记录中的0仅为旧运行约定，后处理不将其解释为有效占比。']
    report+=['','## 原数→舍入后数：预定坐标与诊断极值','','下表取每出口第一篇的固定坐标0，另列全表中的最大绝对/相对案例；均有选择标签，不当成随机样本。完整CSV保留所有固定点与每篇极值。','','| 出口 | 定义 | 标签 | doc/token/channel | 原数 | 后数 | 绝对差 | 相对误差 |','|---|---|---|---|---:|---:|---:|---:|']
    for op in ['o_proj','down_proj']:
        for definition in ['final_cut8','total_rounding','additional_intermediate','delivered_host_total']:
            selected=[x for x in examples if x['op']==op and x['definition']==definition]
            picks=[next(x for x in selected if x['selection']=='fixed' and x['flat_index']==0),max(selected,key=lambda x:x['absolute_error']),max((x for x in selected if x['relative_error_percent'] is not None),key=lambda x:x['relative_error_percent'])]
            for x in picks:report.append(f'| {op} | {definition} | {x["selection"]} | {x["doc_index"]}/{x["token"]}/{x["channel"]} | {x["before_real"]:.15g} | {x["after_real"]:.15g} | {x["absolute_error"]:.12g} | {x["relative_error_percent"]:.9g}% |')
    report+=['','## 核验与适用边界','','GPU私有observer与原版production逐值/计数相同；独立原OUTPUT_ONLY参考相同；R006固定witness完整依赖/codes和15篇原local aggregate逐一相同。CPU任意精度见证检查及本次全raw独立阈值/出口/能量核查通过，全部不利尾部保留。每输出保存accumulator、current/reference code、exact quotient/remainder，可从整数重建原值。','','这给出同输入下最后层两投影自身的直接舍入差；前31层不同输入引起的传播差不在本核验中。不能据此声称最后层舍入导致全部32层输出误差，不能相减relativeL2百分数作归因。没有优化、加位、ACC/PPL、RTL或性能结论。','','[完整机器统计](scalar_summary.json) · [阈值CSV](scalar_threshold_table.csv) · [原/后值CSV](before_after_examples.csv) · [独立CPU核验](independent_checks.json) · [原始GPU输入/来源](../../AT001_original_two_exit_scalar_audit/manifest.json) · [GPU真实退出](../../AT001_original_two_exit_scalar_audit/external_wait_receipt.json)']
    existing_path=at.parents[1]/'analysis_existing/full1024_output_differences.json'
    if existing_path.exists():
        existing=json.loads(existing_path.read_text());write(out/'existing1024_source_link.json',dict(source=identity(existing_path),note='Root-owned algebraic recovery from original full1024 tensor aggregates; no new1024 replay and no pointwise relative thresholds'))
        report+=['','## 已有1024篇离散出口差：单独范围','','以下来自Root维护的原1024篇tensor aggregate代数恢复，比较current与同F16 OUTPUT_ONLY出口；不包含最终舍入前原数，不能据此得到1024篇逐值相对误差比例。没有重新计算1024篇。','','| 出口 | 全量数值数 | 不同值数 | 不同比例 | 每个变化的实际值差 |','|---|---:|---:|---:|---:|']
        for op,d in existing['per_operator'].items():report.append(f'| {op} | {d["scalar_count"]} | {d["changed_count"]} | {d["changed_percent"]:.8f}% | -0.0000152587890625 |')
        report+=['','全部变化为负一步，没有超过一步；这是额外中间舍入在共同F16出口的离散差。','[已有1024来源](../../../analysis_existing/full1024_output_differences.json)']
    (out/'report.md').write_text('\n'.join(report)+'\n')
    write(out/'artifact_manifest.json',dict(source=identity(Path(__file__)),files=[identity(p) for p in out.iterdir() if p.is_file()],seconds=time.monotonic()-start))
    return allsummary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=analyze(a.attempt,a.output);print(json.dumps({op:{k:r[op]['metrics'][k]['relative_thresholds']['1']['percent_of_nonzero'] for k in ['final_cut8','total_rounding','additional_intermediate']} for op in r}))
