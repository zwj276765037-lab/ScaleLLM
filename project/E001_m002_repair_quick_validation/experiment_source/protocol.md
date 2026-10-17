# E001：修复与快速验证协议

执行边界和接口以[本轮合同](../../../mission/M002_ddr_separation_and_timing_recovery/repair_contract_2026-10-15.md)为准。所有实现留在project/hardware，不在实验目录复制一套可编辑实现。

R001：Host/API、布局与加载生命周期CPU验证，A005负责。
R002：专属DDR权重/data路径快速RTL功能验证，A004提供实现/TB，A006串行执行EDA。
R003：构建、BD映射、约束、完整层级elaboration，A006负责。
R004（如登记）：主控独立整数数值基线回归，不替代RTL端到端。

AT终态必须记录command/cwd、输入/代码SHA256、工具版本、started_at/finished_at、exit_status、scope和原始日志路径。失败重试新AT，范围变更新R；不覆盖原始终态。

独立期望：固定字节/地址scoreboard、原数值golden/整数模型、真实artifact大小和对区域区间逐一相交检查。覆盖AR/R背压、返回归属、双逻辑半组完整性、引擎独立并行、reset/maintenance及在飞权重保护。

通过只支持其覆盖范围；工具失败不反驳架构。单文件syntax不算elaboration，elaboration不算仿真，mock/缩小向量不算32层模型。发现全局影响立刻消息主控；其余独立工作继续。
