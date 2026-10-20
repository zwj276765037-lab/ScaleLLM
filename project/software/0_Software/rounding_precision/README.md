# 多级舍入精度实验

用户主对照：**ScaleCode高精度参考** 与 **当前实现**。局部参考保留相同节点出口规则，精确节点值另作总数值误差诊断。

- `source/`：数值合同与独立审阅。
- `experiment/`：精确参考、生产对照、数据加载与运行工具。
- `tests/`：数值边界与独立一致性验证。
- `figures/`：由实测结果生成的图表，不保存虚构实验数据。

任务：[M005](../../../../mission/M005_multistage_rounding_precision/contract.md)。原始运行与三摘要：[E012](../../../E012_multistage_rounding_precision/README.md)。旧工程与生产算法只读；不在这里复制模型权重或历史大目录。

## 当前论文验证协议

用户要求清晰的数值精度证据，ScaleCode方法ACC已有结果。当前主入口：[数值保真协议v3](../../../../mission/M005_multistage_rounding_precision/numerical_fidelity_protocol_v3.md)，包括数学界、相对信号误差、32层数值传播和独立文档采样。v2的任务非劣效部分已撤销，本补测不跑ACC/PPL。旧单文本pilot只作为实现调试证据，不作为论文整体精度结论。R003实际实现和输入冻结进行中，正式大样本及32层数值传播尚未完成。

## 首轮实测入口

2026-10-19已完成合成边界实验和32/128-token真实BF16输入的局部回放，并独立复核。详见[阶段报告](../../../../results/reviews/SM022_real_input_local_stage.md)与[最新实验摘要](../../../E012_multistage_rounding_precision/experiment_results/summary.md)。图表使用「仅输出舍入」「当前实现」，不使用R1/R2/R3。全模型精度尚未测得。
