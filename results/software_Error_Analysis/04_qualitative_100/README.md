# 低Margin翻转100例：固定随机抽样与两次评阅

从Margin<0.05的876个翻转中，以random.Random(20261020).sample抽100个不同位置，先按(doc_id,整数position)排序。样本名单在解码前冻结；100例来自93篇文档：web54、reviews33、news13。

- [最终定性报告](reconciled/report.md)、[可搜索完整HTML](reconciled/review.html)、[最终100行CSV](reconciled/annotated_samples.csv)、[16例分歧裁决](reconciled/adjudication.json)。两次独立AI初始标签84例一致，初始rubric/100条标签/summary分别保存在root_annotation与independent_annotation，未用裁决覆盖初标。
- [原评阅包](review_packet.md) 隐藏原文下一token；[完整样本JSONL](samples.jsonl) 和CSV保留全部已保存prefix、两候选单token repr与联合decode。logits位置t预测下一token，prefix严格为input_ids[:t+1]。只追加一个候选，无真实suffix拼接和自由生成。
- [固定抽样manifest](sample_manifest.json)、[protocol](protocol.json)、[独立抽样复现](root_annotation/sampling_reproduction.json) 和 [数据核验](validation.json) 保留。原文实际next token仅是辅助，不能当金标；本样本100例均能从已存artifact取得。`scope_clarification.json`记录不再额外重分词的授权变更。

这是局部定性AI审阅，不是独立人工标注或任务准确率；不能把未知后续归为无害，也不能认定候选差别等于回答错误。两位评阅最初探查均意外看到S001辅助next字段，最终报告保留此限制。来源/SHA见 [清单](../package_sources.json)。
