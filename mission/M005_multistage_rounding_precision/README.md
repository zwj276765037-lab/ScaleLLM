

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# M005 · multistage_rounding_precision

[任务合同](contract.md) · [任务总结](../../results/missions/M005_summary.md)

## 执行子任务与主控审核

| 子任务 | 定义 | 完整审核历史 |
| --- | --- | --- |
| SM021 · rounding_reference_and_local_validation | [定义](tasks/SM021.md) | [审核](../../results/reviews/SM021.md) |
| SM022 · real_activation_rounding_replay | [定义](tasks/SM022.md) | [审核](../../results/reviews/SM022.md) |
| SM023 · rounding_propagation_and_task_quality | [定义](tasks/SM023.md) | [审核](../../results/reviews/SM023.md) |
| SM024 · paired_response_quality | [定义](tasks/SM024.md) | [审核](../../results/reviews/SM024.md) |

## 关联实验

- [E012 · multistage_rounding_precision](../../project/E012_multistage_rounding_precision/README.md) — completed

## 任务总结原文摘录

# M005 R007：正在纠正累计舍入偏差

2026-10-20用户要求快速优化第32层输出。已建立独立R007，工程实现与独立算术核查并行；候选为中间右移最近偶数舍入，保留现有位宽和出口规则。当前尚无优化后模型结果。

[候选与验证合同](../../project/E012_multistage_rounding_precision/experiment_results/runs/R007/optimization_contract.json) · [运行入口](../../project/E012_multistage_rounding_precision/experiment_results/runs/R007/run.md)

下方R006为已完成的原算法数值基线，不能作为新候选的验证结果。

## 相关决定、变更与讨论

- [hardware_progress](../../results/hardware_progress.md)
- [review_queue](../../results/review_queue.md)

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
