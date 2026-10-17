# E001：M002修复与快速验证依据

关联M002；SM004负责整合，SM002 RTL及SM003 Host为并行依赖。

问题：修复被禁用的权重半组、共享数据口、Host/API/地址重叠和无效构建约束后，专属DDR架构能否通过快速功能验证？

方法：保留双逻辑权重流及原数值模块，将其路由到各引擎专属物理DDR；分离MLP数据口；重建无相交地址布局和在飞保护；修正构建与约束。平台目标xcvu9p-flga2104-2L-e，core100/UI200，工具版本以实际尝试记录为准。

基线：2026-10-15静态审核发现缺陷的当前源，不能用native025作新候选基线。验收为Host合同回归、RTL完整elaboration、事务和数值的限定快速验证；不覆盖综合/时序/上板或完整32层模型。

权威来源：[执行合同](../../../mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md)、[审核](../../../results/reviews/M002_readiness_2026-10-15.md)、[完整协议](protocol.md)。
