# E001：阶段结果

Host 修复后的 106 项 CPU 测试通过；构建与静态合同 49 项通过；9 项整数参考通过，170 个数值/软件文件与 M001 冻结身份一致。完整 board RTL 展开通过：88 个 RTL 文件、无黑盒；该步骤不是正式综合。

data router 与只读 layout CSR 两项 XSim 已通过。权重组及原生 frontend 比较仍在复测：失败证据已保留，实际差异诊断发现测试台首组 expected 全 X、真实 payload 确定且 metadata 相等，正在修复初始组合计算触发，不修改独立字节期望。真实 BD validate-only 正在执行。

证据：[Host R001](runs/R001/worker_report.md)、[RTL R002](runs/R002/worker_report.md)、[构建 R003](runs/R003/worker_report.md)、[数值 R004](runs/R004/run.md)。无正式综合/实现、时序、板卡、32 层端到端或性能通过结论。


---
Published: 2026-10-14T23:57:06.163204+00:00
Publication: Pce3dbae6592446aabd6779488fbb9bc5
