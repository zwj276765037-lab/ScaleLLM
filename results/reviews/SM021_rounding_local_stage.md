# SM021 局部舍入实验阶段核查

2026-10-19，Root依据A014独立审阅及实际运行收据作工程范围核查；不是用户整体科研结论批准。

已形成三个明确分工的子智能体：A014数值合同与独立审核，A015精确参考/生产公式回放，A016数据与实际运行。唯一代码入口为 `project/software/0_Software/rounding_precision/`；原始证据在E012。

首轮R001/AT001保留。补强后R001/AT002共303个合成测试，264个理论合法、36个合同外、3个坏输入；合法域四类误差界均无违例。当前实现相对仅输出舍入：255同码、8个低1输出LSB、1个低2输出LSB；LSB=2^-16。最大差2^-15约3.05e-5，属于构造长链截断偏差，不是代表性真实输入统计。不能写完全无损、所有误差<=1 LSB或已证明全模型精度不变。

A014不导入工程实现独立复算：297条精确oracle、291条当前输出、1728组lane点积、288条适用的精确截断恒等式全部一致；264有效样本D收紧界无违例。37项联合测试通过，早期失败日志保留。两次尝试均exit0且消费期间源码/输入未变，原始证据不覆盖。

阶段判断：接受有限合成输入下的局部CPU数值工具与界验证；继续SM022真实BF16输入局部回放。真实采样不足、V5生产轨迹传播、GPU/RTL逐位一致、NLL/PPL/ACC仍未验证。新实验不修改M003/M004状态或旧结果。

证据：[独立审阅](../../project/software/0_Software/rounding_precision/source/review.md)、[AT002汇总](../../project/E012_multistage_rounding_precision/experiment_results/runs/R001/attempts/AT002_cpu_local_rounding_v2/summary.json)、[真实运行收据](../../project/E012_multistage_rounding_precision/experiment_results/runs/R001/attempts/AT002_cpu_local_rounding_v2/execution_receipt.json)。
