# R007 — 等位宽舍入纠正开发验证

Execution state: running（2026-10-20 08:45:49 Asia/Shanghai实际启动）
Verdict: inconclusive，尚无优化后整网结果。

本次独立candidate将Linear组对齐和可选PV逐项算术右移由floor改为最近偶数舍入；既有guard/acc宽度、wrap、出口half-away及饱和保持。比较仅末层Linear、全层Linear、全层Linear+PV，始终对相同的原output-only高精度参考。开发前4篇筛选、另外32篇验证，ACC/PPL不重跑。

已完成CPU17059例，以及实际GPU511个向量、30个Linear输出（含guard/wrap负对照）、256个PV输出与独立CPU精确oracle一致。独立静态审查确认只改对应对齐块；49188个signed helper检查0 mismatch。整网baseline必须与原R006开发4篇逐值指标/隐藏SHA一致后才能继续使用。

[合同](optimization_contract.json) · [实际启动](attempts/AT001_rne_equalwidth_dev36/actual_launch.json) · [当前阶段](attempts/AT001_rne_equalwidth_dev36/status.json) · [GPU原语资格](attempts/AT001_rne_equalwidth_dev36/gpu_qualification.json) · [候选独审](independent_review/A015_candidate_key_review.json)

GPU0单一worker PID864316/PGID864316/startticks14675736；资源/2400秒上限按合同。该PID是启动快照，实时状态以status、stages及真实进程身份为准；worker自写终态与外部进程退出证据分别记录。

---

以下保留初始登记模板。

# R007 — E012

Recorded: 2026-10-20T00:39:21.188149+00:00

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
