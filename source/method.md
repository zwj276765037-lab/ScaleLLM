# 方法与实现边界

研究目标是 Hadamard + ScaleCode 的真实 FPGA 系统验证，算法贡献不与某一种阵列规模、物理分区或历史候选绑定。软件实现见 `project/software`，RTL/Host/构建入口见 `project/hardware`。

当前数值合同见 [项目目标](../goal/goal.md)。本轮只复制已存在实现，不重新设计量化器或计算核；无源预裁剪与最终定点饱和不是同一概念，不能因“无 clip”删除合法的最终输出饱和。

新架构假设须区分计算、权重搬运和 Host 等待，使用可比输入、计时范围和真实数据，不从 DSP 数量直接推导系统 token/s。当前没有新增实验结论。

| 方法 ID / 名称 | 要解决的问题 | 机制与来源定位 | 最小区分实验 | M/SM/E | 当前判断与证据 |
| --- | --- | --- | --- | --- | --- |
| 多次位宽舍入的数值保真验证 | 隔离额外中间舍入的局部损失及传播累积 | [数值合同](../project/software/0_Software/rounding_precision/source/numerical_fidelity_contract_v3.md)：固定基础量化、权重、LUT及共同出口，精确整数参考；[独审入口](../project/software/0_Software/rounding_precision/experiment/audit_formal_numerical.py) | 同输入五类节点对照、32层双路径传播、冻结真实文档与预定原始算术见证 | M005 / E012 | [独审记录](../project/software/0_Software/rounding_precision/source/numerical_fidelity_review_v3.md)限定核验实现与证据；正式进度见[E012](../project/E012_multistage_rounding_precision/experiment_status/summary.md)，执行完成不等于总体精度保持。当前范围≤128 token、单模型prefill；不重复ACC。 |

重要论文 PDF 放在 papers/ 并记录 DOI/版本/页码；复杂方法可在 methods/ 单列详情。候选不是验证结论。
