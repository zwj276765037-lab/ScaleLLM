

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E002 / R002 运行结果

[负责人维护的本批运行记录](run.md)

# R002 — physical diagnostic entry CPU verification

Execution state: completed AT012
Verdict: CPU_RECOVERY_AND_ACTUAL_POST_REPLAY_PASS; PHYSICAL_SIGNOFF_NOT_ASSESSED

AT012新增13项完成pre_place恢复/CLI/真实终态/新旧命令receipt/route-parent准入测试和managed隔离6项实际执行PASS；96未变legacy诊断测试复用AT011，不声称115项全部新跑。完整真实AT008 debug POST组合hook gate[]、7+4+3链/14exports/688实际BRAM端口/精确8CDC及最终实际父链PASS。

最终source_archive/archived_sources、status、actual_replay_status与installation均在attempts/AT012_post_debug_pre_place_recovery_cpu，五live脚本before与AT008冻结源一致，after与最终候选一致。v1失败replay driver逐字历史byte及旧hash解析映射另存，不改旧manifest/log；v2输入与最终checker独立闭合。

新EDA结果属于R003 AT009：本CPU批次不宣称新的live EDA通过或physical signoff，formal reset/CDC safety保持OPEN。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_preflight_build_cpu](attempts/AT001_preflight_build_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT002_supervisor_isolation_cpu](attempts/AT002_supervisor_isolation_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT003_physical_diagnostic_cpu](attempts/AT003_physical_diagnostic_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT004_physical_diagnostic_final_cpu](attempts/AT004_physical_diagnostic_final_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT005_checkpoint_recovery_cpu](attempts/AT005_checkpoint_recovery_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT006_recovery_identity_preflight_cpu](attempts/AT006_recovery_identity_preflight_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT007_debug_materialization_draft_cpu](attempts/AT007_debug_materialization_draft_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT008_opt_recovery_debug_final_cpu](attempts/AT008_opt_recovery_debug_final_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT009_cdc_reset_diagnostic_reuse_cpu](attempts/AT009_cdc_reset_diagnostic_reuse_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT010_actual_reset_graph_bram_clock_cpu](attempts/AT010_actual_reset_graph_bram_clock_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT011_auxiliary_cdc_full_gate_cpu](attempts/AT011_auxiliary_cdc_full_gate_cpu) | 未登记；查看原记录 | 未登记 |  |
| [AT012_post_debug_pre_place_recovery_cpu](attempts/AT012_post_debug_pre_place_recovery_cpu) | 未登记；查看原记录 | 未登记 | [report.md](attempts/AT012_post_debug_pre_place_recovery_cpu/report.md) |

## 本批问题与交付文件

- [worker_report.md](worker_report.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
