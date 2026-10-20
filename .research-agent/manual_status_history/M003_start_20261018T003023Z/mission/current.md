# 当前大mission：M003 联合可布线改造与完整实现验收

2026-10-18用户要求“定义成完整详细的mission”。[主合同](M003_joint_routability_closure/contract.md)与[验收矩阵](M003_joint_routability_closure/verification_matrix.md)已定义，execution_state=planned、verdict=unassessed。当前仅任务定义完成，未启动M003生产改动、仿真、综合或implementation，也未创建新E/R/AT。

执行顺序：SM013失败网归因 → SM014四表/候选冻结 → SM015 RTL与SM016入口/回归集中交付 → SM017新综合/结构资格 → SM018完整实现 → SM019全局验收。各SM定义与审核入口见[M003任务页](M003_joint_routability_closure/README.md)。技术阶段门不增加用户逐项审批。

前置是M002现有架构和E008/AT004已保存终态，不要求M002先成功。E008自然失败：702396重叠节点、547548冲突网；9491个C01对象实际在SLR2；14项收尾已独立核验，无活动EDA。[E008结果](../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)。PDU暂停已解除，原暂停/恢复记录保留。

MLP字段银行、Attention元数据地址、实际物理约束和测试是一版联合方案；副本粒度、银行数/位置、C01约束取舍及算术是否改动尚待SM013–014冻结。不把样本当全部根因，不按原配置盲目重跑，不保证一次布通。

全局数值/ABI/双DDR/core100MHz/DDR UI200MHz、80保护和时序目标保持；单EDA及原资源保护，正常无墙钟/静默强停；最多3活跃agent含Root、无后代。不重绑旧会话、不改旧工程/冻结证据，不运行bitstream/板卡/GPU/PPL/ACC。

主控负责goal/mission/results与导航；工程/独立审核实际任务派发另记，登记不代表已运行。下一技术入口：[SM013](M003_joint_routability_closure/tasks/SM013.md)。

<!-- research-agent:identity-index:begin -->
## Registered identities

This index records identity and links only. Execution, conclusions and user decisions remain in the linked records.

| Mission | Title | Contract | Summary |
|---|---|---|---|
| M001 | clean_project_migration | [contract](../mission/M001_clean_project_migration/contract.md) | [summary](../results/missions/M001_summary.md) |
| M002 | ddr_separation_and_timing_recovery | [contract](../mission/M002_ddr_separation_and_timing_recovery/contract.md) | [summary](../results/missions/M002_summary.md) |
| M003 | joint_routability_closure | [contract](../mission/M003_joint_routability_closure/contract.md) | [summary](../results/missions/M003_summary.md) |
<!-- research-agent:identity-index:end -->
