# R003/AT001：本次route自然失败终态

execution_state: failed；verdict: inconclusive（方法普遍性）；本次route合法性：FAIL。

实际`route_design`于17:27:55–22:45:40 UTC执行19065秒并返回Tcl1；native/worker/manager/driver均1。Stage于22:45:51.707572 UTC自然结束，stop_reason=null，无时间/资源强停。Phase8 failed/unrouted/partial nets0与245279 node overlaps并存；Phase9原生明确非法布线、248289 signals因拥塞失败。自动失败DRC0 Errors未覆盖此失败。

本次没有route/失败DCP、独立route_status、正式routed timing或完整route POST，不能声称完整implementation达成或最终时序通过。最后完整恢复点仍为成功physopt；不重跑route/改策略。3882样本资源复算、4tracked+manager/driver六身份消失及真实EDA锁释放已闭合，当前无本轮活动EDA。详见[最终绑定facts](route_terminal_completion_facts.json)、[终态复算](terminal_facts.json)和[工程总报告](../../../../engineering_final_report_2026-10-16.md)。

## 以下为历史过程观察（不覆盖上述终态）

# R003/AT001：完整route

execution_state: running；verdict: unassessed。

成功父点为R002/AT002真实独立physopt0/closed DCP/完整POST，driver和worker均已重新通过父链/归档/约束资格，不把旧/新同名源混用。source physopt DCP为568389035B、SHA c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91。

manager实际起点2026-10-15T17:17:27.705894+00:00，PID3964207/worker3964212/PG3964212；Vivado controller实际起点2026-10-15T17:18:03.079268+00:00，launch3964561/native3964652（start919724289）。open_checkpoint真实成功（9m11s）后，已观察原生Command: route_design / Starting Routing Task，当前Phase2正常推进；route命令尚未返回，不声称route完成。精确native起始epoch须待成功/失败命令回执产生。

源与命令在[新report](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m002_E003_R003_AT001_full_route)；实际当前PID/资源见[started](started.json)、[resources](resources.jsonl)。timeout/global_deadline均null，wall_clock_stop_disabled=true，补充授权SHA17acf…；单EDA、CPU0–7/nice5、192GiB RSS/48GiB MemAvailable持续30s/30GiB disk不变。route完整POST及严格fully_routed/未布通/错误计数验证后才判执行完成；时序、reset/CDC和用户全局验收分开。

## 实际route启动与恢复检查范围

[启动事实](route_native_started_facts.json)及[冻结日志快照](route_native_started_log_snapshot.txt)证明native route已开始，同一native PID/start_ticks连续；[恢复范围](route_restore_scope.json)精确区分本次实时与继承资格。恢复后common preflight实际核器件/top/关键对象、各时钟族、reset/XPM链及runtime设置，PREFLIGHT_ISSUES为空、BLACKBOX_COUNT=0。完整准入继承刚闭合且hash-bound的physopt父点。

本次route前没有另跑place恢复式m002_live_pre_place_restore、fresh check_timing/report_drc、独立board clock family guard或Python full live admission；不补造这些回执。-notrace隐藏Tcl正文trace不等于未执行common preflight。debug_proof_restore的verified=0来自要求一个已知dbg_hub blackbox的旧窄谓词，与当前materialized blackbox0不一致；不能据此判新debug失败，也不宣称当前完整debug timing PASS。route完成后的全套POST尚待实际生成，正式reset/CDC安全OPEN。

## Global route SLL需求风险

实际Phase3/3.1报告Route35-3311：SLR0–1 estimated demand21886/available17280=126.66%，单列峰2997/1440≈208.125%；SLR1–2为14482/17280=83.81%，也有局部列超额。见[不可变阶段facts](route_SLL_demand_facts.json)和[原生日志快照](route_SLL_demand_log_snapshot.txt)。这是route阶段的estimated demand，不能混同placed/physopt已占用SLL或最终布通结论。当前正常原生route继续，策略/LOC/接口/时钟不改，最终以真实route_status与工具终态判断。

## Global routing正常推进

其后实际GR Congestion由7076降至0，Global Iteration1仍0，Phase3完成并进入Phase4.1 Initial Net Routing。见[不可变推进facts](route_global_to_initial_facts.json)及[日志快照](route_global_to_initial_log_snapshot.txt)。此前SLL估算风险与当前正常进展并列保留；GR0不能代替最终route_status/完整POST或时序结论，当前同一原生route继续。

## 原生router优先布通告警

实际Phase4.2后新增Route35-447：拥塞影响布线，原生router声明优先完成全部网络而非时序优化。见[阶段facts](route_completion_priority_facts.json)及[日志快照](route_completion_priority_log_snapshot.txt)。当前同一正常route继续，这是默认命令内部行为，未另改策略/seed/LOC/XDC；不能提前判最终布通失败或时序结果。

## 当前route估算拥塞level7

Phase4.10后原生Route35-448/35-581分别报告Estimated Global/Short routing congestion及Estimated Timing congestion均level7(128x128)。见[不可变事实](route_level7_estimated_congestion_facts.json)和[日志快照](route_level7_estimated_congestion_log_snapshot.txt)。这是当前route阶段估算，不能与此前placer-final level6混作同一指标，也不是最终routed拥塞或route_status签核；原生route正常继续，不改策略/LOC/XDC。

## Rip-up and reroute第1次迭代节点观察

原生Phase5/5.1后进入Phase5.2 Global Iteration1，并实际报告Number of Nodes with overlaps=1861520。见[不可变阶段facts](route_iteration1_overlap_facts.json)及[日志快照](route_iteration1_overlap_log_snapshot.txt)。这是中间布线节点计数，不能换算成失败/未布通net数、最终route_status或终态失败。原native持续计算，[1908Z活动范围](route_iteration1_activity_20261015T1908Z.json)另保留CPU与资源观察；当前未产生route命令回执/DCP/终态，后续变化另存。

## 当前iteration1重叠节点下降

其后原生同一Phase5.2/Global Iteration1实际报告overlap nodes由1861520降至988355，减少873165（约46.9%）。见[不可变推进facts](route_iteration1_overlap_reduction_facts.json)和[日志快照](route_iteration1_overlap_reduction_log_snapshot.txt)。这是实际中间进展，仍不能替代最终route_status/未布通net计数或时序结论；原route正常继续。

## 当前iteration1重叠节点进一步降至501530

原生同Phase5.2再次报告overlap nodes501530，序列1861520→988355→501530；较前观察减少486825（约49.26%），较初始减少1359990（约73.06%）。见[不可变facts](route_iteration1_overlap_501530_facts.json)及[日志快照](route_iteration1_overlap_501530_log_snapshot.txt)。这是中间nodes计数，原route继续；最终route_status/DCP/完整POST及时序仍待取得。

## 第1次迭代中间时序观察

同一未结束route的Phase5.2后原生Route35-416报告Intermediate Timing Summary：WNS−17.994ns、TNS−2261923.747ns，WHS/THS=N/A。见[不可变facts](route_iteration1_intermediate_timing_facts.json)及[原生日志快照](route_iteration1_intermediate_timing_log_snapshot.txt)。这是布线未完成时的中间风险观察，hold缺失不填0，不作最终routed时序或与正式physopt同口径差值/因果结论；当前route命令尚未返回，原进程继续。

## 第1次迭代完成、第2次实际开始

其后Phase5.2 Global Iteration1输出真实完成checksum，原生日志elapsed03:44:12，并进入Phase5.3 Global Iteration2。见[不可变facts](route_iteration2_started_facts.json)及[日志快照](route_iteration2_started_log_snapshot.txt)。这仅闭合内部迭代，不等于整个route命令成功或最终布通；先前节点和中间时序观察原样保留。当前同一原生route继续，未重启或改策略。

## 第2次迭代重叠节点2025963

实际Phase5.3 Global Iteration2报告Number of Nodes with overlaps=2025963；前轮最后观察为501530。见[不可变facts](route_iteration2_overlap_2025963_facts.json)和[日志快照](route_iteration2_overlap_2025963_log_snapshot.txt)，绑定当前资源及第2轮真实入口。跨迭代序列不是单调下降，不能把前轮73.058%局部降幅当完成百分比或声称单调收敛；该node口径不是final failed/unrouted net数，也未构成最终失败/根因结论。当前原route继续，完整route_status/DCP/POST及时序待取得。

## Rip-up and reroute内部阶段结束

实际Phase5.3 iteration2完成checksum1a1667ce5，随后Phase5 Rip-up And Reroute完成checksum230eea064，原生日志elapsed05:05:30。见[不可变facts](route_ripup_phase_completed_facts.json)及[快照](route_ripup_phase_completed_log_snapshot.txt)。这仅为内部phase完成；末次观察仍为iteration2 overlap2025963，未取得其后zero-overlap或最终net完整性证据。整个route命令回执、closed route DCP、最终route_status/完整POST尚待取得，原进程继续。

## Delay/Skew与Post Hold Fix继续推进

其后实际Phase6 Delay and Skew Optimization完成并进入Phase7 Post Hold Fix，已观察Hold Fix/Additional Hold Fix等子步骤。见[不可变facts](route_delay_skew_to_hold_facts.json)及[快照](route_delay_skew_to_hold_log_snapshot.txt)。这是原生内部route行为，不代表整个命令/布通/hold或最终时序通过；原route继续，最终报告待取得。

## 原生Phase9布线合法性核验失败

实际Phase9 Verifying routed nets显示Verification failed，随后ERROR Route35-2明确Design is not legally routed，245279 node overlaps。见[不可变失败facts](route_native_verification_failure_facts.json)和[原生日志快照](route_native_verification_failure_log_snapshot.txt)。这是当前原生合法性失败，不再只是中间估算风险；245279仍是重叠node数，不能冒充最终未布通net数。当前原native进入Phase10 Depositing Routes，整个命令回执/最终可得报告/自然终态待闭合；保全失败，不重跑route或改策略。
