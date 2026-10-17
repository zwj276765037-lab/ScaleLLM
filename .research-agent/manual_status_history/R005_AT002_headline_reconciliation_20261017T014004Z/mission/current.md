# 当前大 mission

SM010/E006当前R005已于北京时间2026-10-17 09:19:19真实启动，同图比较SwiGLU独立8-row分支C01与Down权重重排C02的有向边界和有界时序。原R004两候选成员/资源已闭合，并按此次明确用户例外受控收尾；其完整cut/时序/UNION未完成。热点归属/40失败样本/9份exact资源保留，旧输入候选降为未实施探索对照。下一implementation已获授权但尚未启动。[当前事实](../project/E006_m002_slr1_congestion_attribution/experiment_results/summary.md)。

用户追加授权：归因清楚后针对性优化 SLR1，可由其他 SLR 分担；当前先完成 E006，依据实测建立后续卸载与物理验证合同。原数值/接口/时钟及单 EDA 资源边界保持。

用户最新要求定向优化后开启下一轮implementation；原SM011/E007输入局部性入口保留为探索对照，未实施。当前依据R004已闭合资源和R005新有向cut范围选定下一实现范围，不把源码准备当作候选适用性已通过。

后继[SM012/E008合同](M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md)已建立，工程同步准备无默认候选的共通物理入口；当前未选择C01/C02、无实际R/AT或implementation。选定真实支持的一个候选并完成单EDA收尾后连续完整实现。

为减少与候选无关的外部时钟负载导出，已集中核对[候选有向cut范围修订](M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)，R005及E008各阶段采用同一明确口径，正式物理验收保持。R004实际收尾和R005真实启动已独立核查；当前R005恢复检查点。E008新9f267入口源码包正在独立核查。旧UNION全端点补采不计为已完成，后续正常进程仍无墙钟/静默强停。

下文保留E005已结束基线。

当前 M002 目标仍为双DDR分离系统的正确实现与时序恢复。[SM009执行合同](M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)已完成一次优化后的全流程尝试；route自然失败，不自动重复相同实现。

E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。

| ID | 工作与结果 | 状态 |
| --- | --- | --- |
| SM009 / E005 | 首选RTL优化、功能验证、新综合和完整implementation；route自然失败，补采、独立复核及总交付完成 | failed / inconclusive；用户尚未审核结果 |
| SM008 / E004 | 已完成旧失败分析并提出本轮首选组合 | completed / inconclusive；收益判断由E005实际结果更新 |
| SM007 / E003 | 旧完整implementation自然失败，245279重叠节点、248289拥塞失败信号 | failed / inconclusive；原始证据保留 |

E001快速验证及E002正式综合与物理入口适配为前置历史。最新执行状态见[E005摘要](../project/E005_m002_optimized_implementation/experiment_status/summary.md)，内部审核见[SM009](../results/reviews/SM009.md)。正常进程无墙钟/无输出强停；无bitstream、板卡、GPU、PPL/ACC，不恢复旧工程或旧会话绑定。

<!-- research-agent:identity-index:begin -->
## Registered identities

This index records identity and links only. Execution, conclusions and user decisions remain in the linked records.

| Mission | Title | Contract | Summary |
|---|---|---|---|
| M001 | clean_project_migration | [contract](../mission/M001_clean_project_migration/contract.md) | [summary](../results/missions/M001_summary.md) |
| M002 | ddr_separation_and_timing_recovery | [contract](../mission/M002_ddr_separation_and_timing_recovery/contract.md) | [summary](../results/missions/M002_summary.md) |
<!-- research-agent:identity-index:end -->
