# Mission

验证 production 硬件在 Hadamard 前使用定点激活是否会破坏归档软件算法的精度：常规 Host ingress 为 FP32→S24 Q8.16；MLP Down 则消费 FPGA 内部 `SiLU(Gate)×Up` 生成的 S32 Q16.16，而不是另一条 Host FP→S32 传输。

本实验不修改 RTL。任务被拆成三个独立问题：

1. `FP -> S24 Q8.16 -> ideal H32` 是否放大量化误差；
2. production 的 `11585` 系数、16 个小数位的末级舍入和整数 A8 相比软件实现增加多少误差；
3. 把实际激活前端替换进完整模型后，PPL 和 token accuracy 是否出现不可接受的变化。

“证明”分为严格命题和经验命题。Hadamard 的 L2 不放大性可以严格证明；A8 阈值变化和端到端模型质量不能从线性代数推出，只能用固定数据与完整 A/B 报告，并明确模型外推边界。
