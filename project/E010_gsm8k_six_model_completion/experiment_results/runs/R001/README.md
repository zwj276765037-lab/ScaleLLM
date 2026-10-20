

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E010 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — E010

Recorded: 2026-10-18T01:57:33.858528+00:00

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
| [AT001_dual_gpu_gsm8k_pipeline](attempts/AT001_dual_gpu_gsm8k_pipeline) | failed | BF16 smoke complete; a8w8_fp32 and a8w4_fp32 failed unchanged logits-allclose gate; active workers naturally drained, no pilot/formal started. Ordinary diagnosis continues. | [执行收据](attempts/AT001_dual_gpu_gsm8k_pipeline/run.json) · [report.md](attempts/AT001_dual_gpu_gsm8k_pipeline/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
