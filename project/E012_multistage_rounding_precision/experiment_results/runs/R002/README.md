

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E012 / R002 运行结果

[负责人维护的本批运行记录](run.md)

# R002 — E012

Recorded: 2026-10-19T02:39:39.231508+00:00

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
| [AT001_bf16_real_input_32token_pilot](attempts/AT001_bf16_real_input_32token_pilot) | cost_stop | 32-token BF16真实输入采集pilot在模型加载阶段因CPU RSS超过8GiB预算受控停止，未进行前向、没有真实整数回放输入；不判定数值方法有效/无效。 | [执行收据](attempts/AT001_bf16_real_input_32token_pilot/run.json) · [report.md](attempts/AT001_bf16_real_input_32token_pilot/report.md) |
| [AT002_bf16_streamed_32token_pilot](attempts/AT002_bf16_streamed_32token_pilot) | completed | 真实BF16 32-token单prompt/三层/七算子/两token/四通道局部输入采集；168输出、29184组；不是V5生产轨迹或任务指标。 | [执行收据](attempts/AT002_bf16_streamed_32token_pilot/run.json) · [report.md](attempts/AT002_bf16_streamed_32token_pilot/report.md) |
| [AT003_cpu_replay_bf16_32token](attempts/AT003_cpu_replay_bf16_32token) | completed | 32-token真实BF16轨迹局部同码Linear恢复；168条合法/无理论界违例；117同码/51低1LSB。 | [执行收据](attempts/AT003_cpu_replay_bf16_32token/run.json) · [report.md](attempts/AT003_cpu_replay_bf16_32token/report.md) · [manifest.json](attempts/AT003_cpu_replay_bf16_32token/manifest.json) |
| [AT004_bf16_streamed_128token](attempts/AT004_bf16_streamed_128token) | completed | 独立128-token真实BF16轨迹局部输入采集；168输出、29184组；不与32-token合并。 | [执行收据](attempts/AT004_bf16_streamed_128token/run.json) · [report.md](attempts/AT004_bf16_streamed_128token/report.md) |
| [AT005_cpu_replay_bf16_128token](attempts/AT005_cpu_replay_bf16_128token) | completed | 128-token真实BF16轨迹局部同码Linear恢复；168合法/无理论界违例；115同码/53低1LSB；无全模型精度结论。 | [执行收据](attempts/AT005_cpu_replay_bf16_128token/run.json) · [report.md](attempts/AT005_cpu_replay_bf16_128token/report.md) · [manifest.json](attempts/AT005_cpu_replay_bf16_128token/manifest.json) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
