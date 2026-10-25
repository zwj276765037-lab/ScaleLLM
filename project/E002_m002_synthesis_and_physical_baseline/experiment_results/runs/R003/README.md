

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E002 / R003 运行结果

[负责人维护的本批运行记录](run.md)

# R003 — checkpoint physical diagnostic

Execution state: cost_stop; bounded physical stage ended
Verdict: PHYSICAL_NOT_COMPLETE; NO_NEW_CLOSED_PHYSICAL_CHECKPOINT

AT008完成完整debug_materialized/pre_place后，在place Area Swap按2h终止；AT009按明确单次恢复授权从同e58d8970...debug DCP重启place，复用完整POST，fresh live sanity/native DRC实际通过。AT009 stage→pre_place receipt748.398s，相比AT008同口径2629.541s，前置减少1881.143s（31m21.1），原partial placement内存未恢复。

AT009于2026-10-15T11:41:11.046467Z按原11:41:02.527929Z截止停止：managed124/native−15、stage_wall_timeout，owned_before_reap=[3528459]、survivors=[]。全部6个受管PID/start_ticks及实测supervisor身份均不在；峰值RSS32.278GiB。最后完整子阶段4.1.1.2 BUFG Replication，最后原生累计1h38m37s，停止于4.1.1.3 Post Placement Timing Optimization。无place/physopt成功receipt或DCP，无route父链。

原始终态/日志/身份：attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json。成本精度：同目录cost_time_anchors.json，基于managed start与receipt文件mtime，不是精确native place起点。100条SLR样本/抑制、两条DDR1 BUFCE_ROW cap4及10候选BUFG全部skip、中间WNS−1.884/TNS−1349.388原样保留，不能替代完整placed报告或归为route DRC失败。

不再重复place、不追加时长。私有续接候选已归档但未安装、未回归/真实资格验证/额外EDA；五live脚本未变。R004 route NOT_RUN；formal reset/CDC安全及最终时序保持OPEN/未签核。

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_project_init_opt_place_physopt](attempts/AT001_project_init_opt_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT002_project_init_opt_place_physopt](attempts/AT002_project_init_opt_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT003_checkpoint_recovery_opt_place_physopt](attempts/AT003_checkpoint_recovery_opt_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT004_complete_recovery_preflight_opt_place_physopt](attempts/AT004_complete_recovery_preflight_opt_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT005_opt_recovery_debug_materialized_place_physopt](attempts/AT005_opt_recovery_debug_materialized_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT006_cdc_reset_proof_debug_place_physopt](attempts/AT006_cdc_reset_proof_debug_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT007_bram_port_clock_debug_place_physopt](attempts/AT007_bram_port_clock_debug_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT008_complete_opt_gate_debug_place_physopt](attempts/AT008_complete_opt_gate_debug_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT009_completed_pre_place_recovery_place_physopt](attempts/AT009_completed_pre_place_recovery_place_physopt) | 未登记；查看原记录 | 未登记 | [report.md](attempts/AT009_completed_pre_place_recovery_place_physopt/report.md) |

## 本批问题与交付文件

- [worker_report.md](worker_report.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
