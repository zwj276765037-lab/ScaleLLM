# A005：结果交付

SM003 / E001 / R001 已交付。[工程报告](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R001/worker_report.md)；[主控审核](../../results/reviews/SM003.md)。

Host 地址/API、单层 MLP lease、未退役状态保护及布局版本拒绝已修复；AT104 的 106 项 CPU 回归通过，20 个输入文件当前 hash 一致。失败 AT101–AT103 保留。没有真实板卡、模型或性能结论。

另向父主控交付新权重 scheduler 的独立只读审核；仿真与最终整合仍由 SM002/SM004 和父主控负责。A005 本轮执行已完成，无长期对话绑定或后台监控。

后续又完成真实生成BD地址别名的独立只读审核；核对Host分支、每SI译码和31bit出口，结论及限制已纳入R003和M002报告。未运行EDA或修改源码。
