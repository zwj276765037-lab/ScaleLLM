

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E001 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — Host 修复与 CPU 验证

execution_state: completed；verdict: supported；review: 主控核查完成，非用户全局验收。

适用范围：AT104/sources.sha256 对应 Host 源；106 项 CPU 用例通过，退出码 0。完整命令、Python/NumPy 版本、UTC 起止时间、失败尝试及独立期望见 [worker_report.md](worker_report.md) 与 [AT104 回执](attempts/AT104/command.json)。主控复核当前 20 个输入 hash 一致。

验证 Host API、通道/偏移、地址区间、artifact、单层权重生命周期、旧布局拒绝。32 层用例是 mock，非实际推理；无 EDA、DDR/PCIe、板卡、PPL/ACC 或性能验证。AT101–AT103 原失败记录保留。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT101](attempts/AT101) | 未登记；查看原记录 | 未登记 |  |
| [AT102](attempts/AT102) | 未登记；查看原记录 | 未登记 |  |
| [AT103](attempts/AT103) | 未登记；查看原记录 | 未登记 |  |
| [AT104](attempts/AT104) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件

- [worker_report.md](worker_report.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
