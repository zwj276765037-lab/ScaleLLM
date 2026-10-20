# M005 R007：正在纠正累计舍入偏差

2026-10-20用户要求快速优化第32层输出。已建立独立R007，工程实现与独立算术核查并行；候选为中间右移最近偶数舍入，保留现有位宽和出口规则。当前尚无优化后模型结果。

[候选与验证合同](../../project/E012_multistage_rounding_precision/experiment_results/runs/R007/optimization_contract.json) · [运行入口](../../project/E012_multistage_rounding_precision/experiment_results/runs/R007/run.md)

下方R006为已完成的原算法数值基线，不能作为新候选的验证结果。

---

# M005 R006最终交付：Softmax后TV与整合PNG

执行completed；数值普遍保真命题inconclusive。1024篇/103700位置、64组、128份独审和66个自动收尾完成；22:08采集结束，22:15自动流水线结束。Root终态核查与版式v3目视已完成。

全位置TV中位0.671021%、P951.830183%、P993.681844%、最大29.720074%；Top1一致98.984571%。TV>5%占0.467695%，少量尾部保留。文档等权平均TV中位0.740003%、P951.177521%。

[最终整合PNG](../../project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/png_v3/final_precision.png) · [全量TV与来源](../../project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/aggregate_v2/tv_aggregate.json) · [Root审核](../../project/E012_multistage_rounding_precision/experiment_results/runs/R006/independent_review/root_final_review.json)

以下保留此前阶段历史。

---

# M005：最终汇总

任务：multistage_rounding_precision。R005数值采集及图表交付完成；普遍精度保持命题尚未确证。

## 对目标的实际进展

待关联 goal 与真实验收证据。

## 小任务、关键数据与阶段决定

链接 SM 审核记录；保留阶段事件及其处理结果。

## 整合验证、限制和未完成项

待核查当前基线的整合依赖与全局验收，不能以 agent 全部返回代替通过。

## 下一步

待依据已审核证据确定。


## R005全量数值结果（2026-10-19）

execution_state: completed（R005 S001采集、64组独审、聚合与Python PNG绘图完成）
verdict: inconclusive（不作所有输出误差可忽略或普遍精度保持的结论）

2026-10-19 17:38:17（Asia/Shanghai）完整流水线结束，实际墙钟9946.915秒；GPU采集17:30:26结束，native0、worker已回收、冻结源未改变。1024/1024文档、64/64组、103700真实位置、13300147200对全词表分数；web512/news256/reviews256，无缺失文档。64核心与64扩展审查均已完成，15篇预选原始见证与其余文档统计/来源检查的范围分开陈述；不是所有完整张量独立重算。

全量结果：逐位置Top1一致102647/103700=98.984571%；文档等权98.994439%；整篇全部位置一致397/1024=38.769531%。全词表绝对差≤0.1的分数覆盖率98.130653%，≤0.2为99.844413%，≤0.5为99.991921%。末端隐藏向量相对L2中位数1.570580%、P95 2.847756%；最终词表分数相对L2中位数1.228031%、P95 2.207453%。这些不是任务ACC或自由生成一致性。

MLP每篇跨32层最大局部误差的P95（%）：Gate0.00709539、Up0.00918906、Down0.07167732、门控共同出口损失0.04570844、整个MLP分支0.16322653、同残差相加后0.09299327。门控项对同LUT精确乘积，其他局部项对共同出口的高精度中间参考。SiLU同表语义核验不表示解析函数近似误差为零。

PNG v2只修正底部说明重叠与两个分区标题；13×1024个点、分位值、整数计数和全部来源与v1一致。最终图已目视检查，原v1与冻结renderer保留。刚讨论的Softmax后完整概率分布TV尚未测得，不能标为本轮已完成指标。范围仅单模型、最多128个真实token、32层prefill；固定配额合池描述，分域区间依赖未验证iid假设。

最终证据：`project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/aggregate_v1/final_aggregate.json`；最终PNG：`project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/png_v2/final_precision.png`。
