# R001 — Host 修复与 CPU 验证

execution_state: completed；verdict: supported；review: 主控核查完成，非用户全局验收。

适用范围：AT104/sources.sha256 对应 Host 源；106 项 CPU 用例通过，退出码 0。完整命令、Python/NumPy 版本、UTC 起止时间、失败尝试及独立期望见 [worker_report.md](worker_report.md) 与 [AT104 回执](attempts/AT104/command.json)。主控复核当前 20 个输入 hash 一致。

验证 Host API、通道/偏移、地址区间、artifact、单层权重生命周期、旧布局拒绝。32 层用例是 mock，非实际推理；无 EDA、DDR/PCIe、板卡、PPL/ACC 或性能验证。AT101–AT103 原失败记录保留。
