"""Build evidence-backed terminal R009 report from completed GPU/CPU artifacts."""
import argparse,json,hashlib,math
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--gpu',type=Path,required=True);p.add_argument('--post',type=Path,required=True);a=p.parse_args();result=json.loads((a.gpu/'result.json').read_text());checks=json.loads((a.post/'analysis/independent_checks.json').read_text());witness=json.loads((a.post/'head_witness/head_witness.json').read_text());postreceipt=json.loads((a.post/'execution_receipt.json').read_text());assert postreceipt['execution_state']=='completed' and checks['passed'] and witness['passed'];summary=json.loads((a.post/'analysis/independent_summary.json').read_text());deltas=json.loads((a.post/'analysis/comparison_deltas.json').read_text());resources=[json.loads(x) for x in (a.gpu/'resources.jsonl').read_text().splitlines()];mainreceipt=json.loads((a.gpu/'execution_receipt.json').read_text());exitproof=json.loads((a.gpu/'external_lifecycle_receipt_v2.json').read_text());assert exitproof['proc_entry_absent'] and not exitproof['gpu_owned_process_present']
 text='''# R009：第32层真实出口F18/F20六臂开发试验\n\n工程执行完成。只在index31 o_proj/down_proj增加真实输出小数位，保留前31层和其他第32层节点；两档与所有参考在全部36开发文档上完成。Root最终结果审核尚未记录。全局数值改善依据下表报告，未据微小波动采用生产版本。\n\n## 固定ref4主比较（36文档/4494真实位置）\n\n所有主比较共享同一F20 OUTPUT_ONLY参考；L2为文档中位百分数，TV为概率质量百分数。\n\n| 配置 | 第32层pre-norm L2% | finalhidden L2% | 全词表logit L2% | pooled meanTV% | Top1不一致 |\n|---|---:|---:|---:|---:|---:|\n'''
 def table(rows):
  out=''
  for arm,x in rows.items():out+=f"| {arm} | {x['layer32_pre_norm']['document_median_percent']:.9f} | {x['final_hidden']['document_median_percent']:.9f} | {x['logits']['document_median_percent']:.9f} | {100*x['tv']['pooled_mean']:.9f} | {x['top1_errors']}/{x['positions']} |\n"
  return out
 text+=table(summary['common_fixed'])+'\n'
 for d in deltas['deltas']:
  text+=f"{d['arm']} 相对baseline的meanTV降低 {d['mean_tv_relative_reduction_percent']:+.6f}%；L32/finalhidden/logit L2中位相对降低 {d['l32_median_relative_reduction_percent']:+.6f}/{d['finalhidden_median_relative_reduction_percent']:+.6f}/{d['logit_median_relative_reduction_percent']:+.6f}%；Top1错数变化 {d['top1_error_change']:+d}。这里降低为负即退步。\n\n"
 text+='''## 全部L2统计与尾部\n\n差异小不代表普遍无损。保留文档中位/均值/P95/最大及合并能量、位置TV所有尾部。\n\n| 指标% | baseline | +2位 | +4位 |\n|---|---:|---:|---:|\n'''
 arms=['baseline_b0','candidate_b2','candidate_b4'];common=summary['common_fixed']
 for key,name in [('layer32_pre_norm','L32 pre-norm'),('final_hidden','finalhidden'),('logits','fullvocab logit')]:
  for stat,label in [('document_median_percent','文档中位'),('document_mean_percent','文档均值'),('document_p95_percent','文档P95'),('document_max_percent','文档最大'),('pooled_relative_l2_percent','合并能量')]:text+='| '+name+' '+label+' | '+' | '.join(f'{common[arm][key][stat]:.9f}' for arm in arms)+' |\n'
 for stat,label in [('pooled_mean','TV pooled mean'),('position_median','TV位置中位'),('position_p95','TV位置P95'),('position_p99','TV位置P99'),('position_max','TV位置最大')]:text+='| '+label+' | '+' | '.join(f"{100*common[arm]['tv'][stat]:.9f}" for arm in arms)+' |\n'
 text+='\n| TV尾部位置计数 | baseline | +2位 | +4位 |\n|---|---:|---:|---:|\n'
 for stat,label in [('positions_above_1pct','>1%'),('positions_above_5pct','>5%'),('positions_above_10pct','>10%')]:text+='| '+label+' | '+' | '.join(str(common[arm]['tv'][stat]) for arm in arms)+' |\n'
 text+='\n逐文档方向（improved/worse/equal）全部保留：\n\n'
 for d in deltas['deltas']:
  text+=d['arm']+'：'+', '.join(f"{k}={v['improved']}/{v['worse']}/{v['equal']}" for k,v in d['directions'].items())+'。\n\n'
 text+='''## 同格式配对与参考漂移\n\n同格式比较消除出口格式差异，仍包含前31层CURRENT与OUTPUT_ONLY轨迹的差异，不能称为仅第32层纯局部舍入误差。ref0/ref2至ref4的变化单列，不能把移动参考带来的变化作为候选成果。\n\n| 同格式配置 | L32 L2中位% | finalhidden L2中位% | logit L2中位% | meanTV% | Top1不一致 |\n|---|---:|---:|---:|---:|---:|\n'''+table(summary['matched_format'])+'''\n| 参考漂移至ref4 | L32 L2中位% | finalhidden L2中位% | logit L2中位% | meanTV% | Top1不一致 |\n|---|---:|---:|---:|---:|---:|\n'''+table(summary['reference_drift'])
 for name,label in [('first4','原前4篇/398位置'),('next32','原next32篇/4096位置')]:text+='\n## '+label+'固定ref4分组\n\n| 配置 | L32 L2中位% | finalhidden L2中位% | logit L2中位% | meanTV% | Top1不一致 |\n|---|---:|---:|---:|---:|---:|\n'+table(result[name]['common_fixed'])
 text+='''\n## 实现与边界\n\n仅index31 o_proj与down_proj：b2/b4的中间F24+b、guard/acc原宽度+b，保持floor组对齐，最终half-away drop8；o_proj输出S26/F18或S28/F20，down_proj输出S34/F18或S36/F20，真实int64存储。临时effective output_width避开旧S24符号重解释；原shift合法性从delta+24+b重建。输出进入HF残差前以FP32只缩放一次，合成除2^(16+b)，Attention辅助概率不改。HostFP32有限24位有效精度仍可能丢弃大幅值低位；新增定点LSB并不保证Host保留每一位。\n\n独立wide参考与candidate分开：exact quotient/remainder、k=total_shift−(16+b)、common_bits=shift_max−(16+b)，expanded clamp/int64；其余OUTPUT_ONLY原算法保持。生产format05/ABI及所有旧冻结源不变，新增格式只属于实验overlay。\n\n## 资格、一致性与独立复核\n\nCPU2781 integer/Fraction及4 Host缩放/正常异常恢复情景通过；另432宽度modulo/sat检查保留。GPU实际b0原生产raw/counter相同，宽Attention正码超过旧S24、Down正码超过int32均正确，独立Fraction参考通过。AT001/2在模型加载前检出legal_shift漏加b并自然失败，未修改期待值；新core_v2修复后AT003资格通过，原失败版本完整保留。\n\n'''
 text+=f"全部216forward覆盖192个动态编码坐标/臂。前31层组内hash的{checks['prefix_layer_hash_comparisons']}次独立逐层比较通过，{checks['host_scale_once_events_verified']}个Host缩放事件均为FP32且每出口恰好一次，原attrs/functions/buffers恢复通过。baseline/ref0全部raw哈希与R007和旧指标全等。\n\n"
 text+=f"独立CPU复算{checks['final_hidden_npz_pairs_recomputed']}组finalhidden NPZ、{checks['pre_norm_npz_pairs_recomputed']}组可用pre-norm raw，最大L2绝对差{checks['max_hidden_l2_abs_difference']:.4g}；其余pre-norm按合同仅保留能量/hash，不虚称全raw独立复算。Top1 IDs重算、TV质量/范围/聚合核查通过。固定doc0/4/35与位置0/T//2/T−1的{witness['witness_count']}个CPU FP64 fullvocab head见证TV差最大{witness['max_tv_abs_difference']:.4g}，Top1 IDs全等={witness['all_top1_ids_equal']}，质量误差最大{witness['max_probability_mass_defect']:.4g}。此见证不是全部位置的bitwise FP32证明。\n\n"
 # Real finite-width counters and expected clipping are separated.
 text+='| common-ref4 current臂审计 | format错误 | guard/acc overflow | output sat/overflow及KV clip | QK score clamp |\n|---|---:|---:|---:|---:|\n'
 for arm in arms:
  c=result['common_fixed'][arm]['counters'];fmt=c['activation_scale_format_error']+c['linear_total_shift_format_error'];overflow=sum(c[k] for k in ['linear_group_guard_overflow_s37','linear_software_group_guard_overflow','linear_accumulator_overflow','linear_software_accumulator_overflow']);sat=sum(c[k] for k in ['fp_to_fixed_saturation','hadamard_saturation','linear_output_saturation','rope_output_saturation','kv12_clip','pv_output_saturation','swiglu_output_overflow']);text+=f"| {arm} | {fmt} | {overflow} | {sat} | {c['qk_score_clip']} |\n"
 text+='\n所有参考有限guard/acc计数为null，不当成0。QK原有clamp是实际计数，未隐藏。\n\n## 资源、命令和退出\n\n'
 gpu_total=0.;attempts=[]
 for at in sorted((a.run/'attempts').glob('AT00[123]*')):
  rp=at/'execution_receipt.json'
  if rp.exists():x=json.loads(rp.read_text());gpu_total+=x['gpu_wall_seconds'];attempts.append(dict(attempt=at.name,wall_seconds=x['gpu_wall_seconds'],state=x['execution_state']))
 peakrss=max(x['rss_bytes'] for x in resources);minfree=min(x['gpu_free_bytes'] for x in resources)
 text+=f"AT003 GPU wall {mainreceipt['gpu_wall_seconds']:.6f}s；含两次未装模型资格失败的累计GPU阶段{gpu_total:.6f}s，低于2400s。模型只装配一次。峰值allocated{result['peak_gpu_allocated_bytes']/(1<<30):.4f}GiB，采样RSS{peakrss/(1<<30):.4f}GiB、freeGPU最低{minfree/(1<<30):.4f}GiB，均在合同内。外部pidfd观测退出于{exitproof['pidfd_exit_observed_at']}，/proc消失={exitproof['proc_entry_absent']}、GPU残留该PID={exitproof['gpu_owned_process_present']}；Linux/proc退出状态={exitproof['proc_stat_at_exit']}。worker自写收据与外部证据分开。\n\n"
 text+='| 36篇合计runtime（秒） | baseline | +2位 | +4位 |\n|---|---:|---:|---:|\n'
 for key,label in [('forward_seconds','forward'),('measurement_seconds','common-ref4 head测量')]:text+='| '+label+' | '+' | '.join(f"{result['common_fixed'][arm][key]:.6f}" for arm in arms)+' |\n'
 text+='''\n这些是单次软件GPU实测，含调度/编译等因素，不作RTL资源、频率或稳定加速结论。实际命令、源/输入SHA、checkpoint消费身份见AT003 manifest/stream_loader_validation；全部消费源结束复核不变。CPU审计子进程native0且parent wait/reaped，GPU结束后运行。\n\n## 图、明细和适用范围\n\n![R009完整对比](r009_precision_comparison.png)\n\n[逐文档全部差值](per_document_deltas.csv) · [全部位置TV/Top1](per_position_metrics.csv) · [独立复核](independent_checks.json) · [独立汇总](independent_summary.json) · [原始GPU结果](../../AT003_true_exit_precision_dev36/result.json) · [FP64head见证](../head_witness/head_witness.json)\n\n同一组已用开发数据的重复验证，不是新的heldout或正式1024；两档均全测，未按结果筛除文档。前31层累计误差仍保留，最后两出口加位数不能消除既有所有差异。没有任务ACC/PPL、RTL实现/综合/时序、板级测量或普遍无损证明；没有修改生产源或自动启动后继GPU阶段。\n'''
 (a.post/'analysis/report.md').write_text(text)
 meta=dict(gpu_total_seconds=gpu_total,gpu_attempts=attempts,max_sampled_rss_bytes=peakrss,min_sampled_gpu_free_bytes=minfree,peak_gpu_allocated_bytes=result['peak_gpu_allocated_bytes'],source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),report_sha256=hashlib.sha256(text.encode()).hexdigest(),scope=result['scope']);(a.post/'final_report_manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))

if __name__=='__main__':main()
