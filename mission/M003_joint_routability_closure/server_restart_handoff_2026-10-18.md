# M003：服务器重启暂停交接

用户明确要求“需要先中断了 因为服务器需要重启”。本次暂停优先于所有旧连续执行/重试授权；必须等待新的继续指令。

当前状态：暂停收尾已核验完成，M003已具备服务器重启条件。A006唯一控制当前归属进程，A007独立只读审核，Root维护暂停入口。GPU不属本次范围。

已完成：G2冻结M2+A3+C-P1；SM015/SM016限定功能/入口回归和独立审核；本版23综合任务产生网表。当前SM017/G4未过，SM018布局布线未开始。

当前AT013为同版本fresh core只读角色/命名导出，原图已载入，完整族数尚未取得。AT012正式TCL加载已执行，但head payload选择不足导致apply失败；需要实际NAME/层级证据修正选择器，不能放宽13120位完整覆盖或改RTL/资源池。AT003及AT008–012的失败/机制适用范围均保留。

恢复入口：用户明确继续后先读E011三摘要与A007 stage_summary，核本交接最终收尾/暂停状态，复核45源manifest151e4f11、三RTL、G2和本版23产生/22消费网表身份，再定义有限后继诊断/修复AT。不得自动重跑旧长统计，不得把部分导出或旧DCP当新资格成功。

[暂停状态](../../.research-agent/project_pause.json) · [E011状态](../../project/E011_m003_joint_routability_implementation/experiment_status/summary.md) · [独立审核摘要](../../agent/A007/M003_SM015_SM017_review_20261018/stage_summary.md)。

本次停止07:44:47.297092Z（北京时间15:44:47），原native−15/explicit supervisor signal15保留；这是用户中断，非方法失败。监督和4个归属子进程均已结束，EDA锁已实际非阻塞取得并立即释放，session50467已排空，无常驻观察器/残留。

45源manifest151e4f113dfcbf377a2548280ba6112e26fdfa4b4b381509778f369b0180ab73与3RTL逐SHA不变；原fresh core DCP为177165461B，SHA e51adf501ead6402490a4a982bd7c74064f6e858eec7ff76fbc0bc69940975a1。原23/22综合网表来源链保持。

保全4份实际报告/来源记录及副本；parent_scope_candidates.tsv为0B，完整head/tail族数未取得，没有新中途DCP。恢复不能从该空表续算，需新AT有限诊断；已有每对象重复7次属性枚举开销的静态发现可用于缩减查询，待新授权后实施。

[工程收尾回执](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT013_fresh_core_native_role_attribution/evidence/server_restart_pause/pause_closure.json) SHA f6e78a1f880b499bf9138545fda27aaf2da38e900cc0cea547a2593665372216 · [工程交接](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT013_fresh_core_native_role_attribution/evidence/server_restart_pause/engineering_restart_handoff.md)。Root已核小型回执及真实进程终态；A007最终只读收尾审核已通过，见[独立审核](../../agent/A007/M003_SM015_SM017_review_20261018/AT013_user_server_restart_pause_review.json)，SHA 6a364df8c3f5e00686cecca035f6b889e8f5a0aa407ba71e003bfee4928e5a01。双方均paused；没有剩余进程控制或续跑任务。
