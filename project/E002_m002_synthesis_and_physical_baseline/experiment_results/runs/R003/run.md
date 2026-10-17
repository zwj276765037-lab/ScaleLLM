# R003 — checkpoint physical diagnostic

Execution state: cost_stop; bounded physical stage ended
Verdict: PHYSICAL_NOT_COMPLETE; NO_NEW_CLOSED_PHYSICAL_CHECKPOINT

AT008完成完整debug_materialized/pre_place后，在place Area Swap按2h终止；AT009按明确单次恢复授权从同e58d8970...debug DCP重启place，复用完整POST，fresh live sanity/native DRC实际通过。AT009 stage→pre_place receipt748.398s，相比AT008同口径2629.541s，前置减少1881.143s（31m21.1），原partial placement内存未恢复。

AT009于2026-10-15T11:41:11.046467Z按原11:41:02.527929Z截止停止：managed124/native−15、stage_wall_timeout，owned_before_reap=[3528459]、survivors=[]。全部6个受管PID/start_ticks及实测supervisor身份均不在；峰值RSS32.278GiB。最后完整子阶段4.1.1.2 BUFG Replication，最后原生累计1h38m37s，停止于4.1.1.3 Post Placement Timing Optimization。无place/physopt成功receipt或DCP，无route父链。

原始终态/日志/身份：attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json。成本精度：同目录cost_time_anchors.json，基于managed start与receipt文件mtime，不是精确native place起点。100条SLR样本/抑制、两条DDR1 BUFCE_ROW cap4及10候选BUFG全部skip、中间WNS−1.884/TNS−1349.388原样保留，不能替代完整placed报告或归为route DRC失败。

不再重复place、不追加时长。私有续接候选已归档但未安装、未回归/真实资格验证/额外EDA；五live脚本未变。R004 route NOT_RUN；formal reset/CDC安全及最终时序保持OPEN/未签核。
