# R005 — E006

Recorded: 2026-10-17T00:55:23.163257+00:00

Execution state: running
Verdict: unassessed

- Scope: 按新的有向候选边界协议比较 C01/C02；该范围不同于 R004 的整网全部端点采集。AT001 已真实原生启动，当前恢复检查点。
- Contract: [范围修订](../../../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)，源码已完成独立核查；实际对象/schema/cut/时序资格仍未完成。
- Platform/input: 实际复用 R004 的 Vivado2025.2、同一 E005 physopt DCP、144 冻结生产输入和已闭合资源/热点/失败样本；[实际绑定](attempts/AT001_candidate_directed_cut/input_bindings.json)。
- Source: [新 manifest](../../../../../agent/A006/directed_candidate_cut/prepared_source_manifest.json)，9705 B / SHA256 `558c46fe4aaf5e14c3a8f548b02a1fd00891588d2054f5fc9c3e5fcf1d921161`；14 份源、5 项 CPU 证据、10 个外部身份。[独立最终审核](../../../../../agent/A007/directed_source_review_20261017/final_source_admission_review.md)已通过；R004 和 E008 b59 原源码保持。
- Start/end, command, exit: 于2026-10-17T01:19:19.287839Z启动，尚无终态；[实际启动与命令](attempts/AT001_candidate_directed_cut/started.json)、[原生核验](attempts/AT001_candidate_directed_cut/native_start_verified.json)。
- Dependency: 用户已明确答复“允许切换本次 R004 诊断（推荐）”，[实际决定](../../../../../.research-agent/decision_inputs/E006_R004_user_allowed_directed_switch_20261017.json)和[执行绑定](../../../../../.research-agent/decision_inputs/E006_R004_controlled_stop_for_R005_20261017.json)已归档。R004已受控结束，真实PID/锁/输入闭合独立通过；本次许可不扩展到后续正常进程。
- Acceptance: 原生证明完整候选有向 cut 和方向时序覆盖；显式保留 unknown/INOUT/多 driver 回退；不把未枚举外部 peer load 当零或整网完整。
- Limitation: 旧 UNION 全端点补采仍未完成；本批次不声称完成该旧覆盖。不预判候选迁移收益或完整布线结果。

独立核心检查已覆盖 17 种 collector 情形、14 个闭合 cut/scoped timing 场景与 28 次 adapter CLI；9 类错误计数/覆盖/单 alias 查询/类型不一致反例被拒绝。这些是 CPU 与模拟原生 API 的检查，实际 Vivado schema、对象覆盖和时序未执行。

A run record alone does not establish PASS or a method verdict.
