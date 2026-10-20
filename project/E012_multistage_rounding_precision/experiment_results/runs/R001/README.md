

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E012 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — E012

Recorded: 2026-10-19T02:25:20.119728+00:00

Execution state: planned
Verdict: unassessed

- Exact command and working directory:
- Host, tool and platform versions:
- Code identity (commit/hash), external constraints and IP identity:
- Input/data identity and reproducibility inputs:
- Start/end times:
- Exit status and infrastructure errors:
- Independent oracle, expected values and acceptance criteria:
- Evidence paths and qualified scope:
- Observations and limitations:

A run record alone does not establish PASS or a method verdict.

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_cpu_local_rounding_pilot](attempts/AT001_cpu_local_rounding_pilot) | completed | CPU合成局部Linear恢复pilot v1；291条中252条理论有效。非真实激活、非全模型；v2修正资格字段后须新AT。 | [执行收据](attempts/AT001_cpu_local_rounding_pilot/run.json) · [report.md](attempts/AT001_cpu_local_rounding_pilot/report.md) · [manifest.json](attempts/AT001_cpu_local_rounding_pilot/manifest.json) |
| [AT002_cpu_local_rounding_v2](attempts/AT002_cpu_local_rounding_v2) | completed | CPU合成局部Linear恢复v2；303条中264条理论有效，含128/448组累积舍入见证。真实模型输入和全链均未测。 | [执行收据](attempts/AT002_cpu_local_rounding_v2/run.json) · [report.md](attempts/AT002_cpu_local_rounding_v2/report.md) · [manifest.json](attempts/AT002_cpu_local_rounding_v2/manifest.json) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
