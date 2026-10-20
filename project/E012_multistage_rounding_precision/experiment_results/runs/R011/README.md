

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E012 / R011 运行结果

[负责人维护的本批运行记录](run.md)

# R011 — E012

Recorded: 2026-10-20T02:22:35.588874+00:00

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


<!-- R011-authorized-diagnostic-terminal -->
## 本次授权诊断终态

Recorded: 2026-10-20T02:38Z

Execution state: completed
Verdict: supported within the three-case numerical diagnostic scope.

原始planned正文保留为创建时记录。本次仅decoder31/finalnorm，3篇299位置，12四轨迹forward+6条件后缀干预；AT002真实parent wait/reaped native0，GPU阶段75.5803秒。AT001观察器dtype资格失败完整保留；所有旧冻结源不改。当前无所属GPU/CPU进程。

跳升点是MLP分支合回残差：已有两路误差叠加、真实信号相消；FP32加法自身roundoff不是主要来源。OUTPUT_ONLY保留基础量化、ScaleCode、LUT/SwiGLU、共同出口和Host。独立A015限定审核通过；不作单算子唯一归因、1024干预、优化或任务质量结论。

[最终报告](attempts/AT003_cpu_causal_analysis/analysis/report.md) · [全部stage CSV](attempts/AT003_cpu_causal_analysis/analysis/stage_metrics.csv) · [四

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [branch_comparison](branch_comparison) | 未登记；查看原记录 | 未登记 | [report.md](branch_comparison/report.md) |
| [AT001_singleblock_fourway](attempts/AT001_singleblock_fourway) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT001_singleblock_fourway/manifest.json) |
| [AT002_singleblock_fourway_v2](attempts/AT002_singleblock_fourway_v2) | completed | 未登记 | [执行收据](attempts/AT002_singleblock_fourway_v2/result.json) · [manifest.json](attempts/AT002_singleblock_fourway_v2/manifest.json) |
| [AT003_cpu_causal_analysis](attempts/AT003_cpu_causal_analysis) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT003_cpu_causal_analysis/manifest.json) |
| [AT004_terminal_summary](attempts/AT004_terminal_summary) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
