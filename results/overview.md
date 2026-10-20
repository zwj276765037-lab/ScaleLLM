# ScaleLLM：审核总览

**2026-10-20最新：AT006已自然布线失败，原生Route35-2确认797175个重叠节点，最终route_status确认615840条资源冲突网。** 原尝试07:07:38Z监督结束native1/stop=null/owned_survivors空，route_failed.dcp及status/timing/congestion/DRC已保存；正式route POST未执行。完整place/physopt及其结构资格通过不代表可合法布通。现有证据显示局部跨SLR列需求0–1最高124%、1–2最高112%（对应总需求仅63.17%/62.30%），physopt占用CLB站点SLR0/1/2为96.71%/99.33%/99.90%，支持严重局部互连/打包压力；不将占用站点等同LUT槽耗尽，不将告警或top样本当唯一根因。用户随后明确要求“详细定位到底哪个地方无法布线成功”：A018已获派发，先现成报告离线归因，必要时新批次有界只读载入失败DCP，交付区域→模块→具体信号通路及覆盖/未知；不改RTL/XDC、不启动新implementation。单EDA、原资源保护及正常无墙钟/静默强停保持。M003整体未完成。

[验证提速与执行决定](../mission/M003_joint_routability_closure/validation_efficiency_2026-10-19.md)

[重启后恢复合同](../mission/M003_joint_routability_closure/server_restart_resume_2026-10-18.md) · [工程状态](../project/E011_m003_joint_routability_implementation/experiment_status/summary.md)。

[M003合同](../mission/M003_joint_routability_closure/contract.md)、[执行授权](../mission/M003_joint_routability_closure/execution_start_2026-10-18.md)、[验收矩阵](../mission/M003_joint_routability_closure/verification_matrix.md)和[候选决定表](../mission/M003_joint_routability_closure/candidate_decision_register.md)为当前入口。G2设计冻结及独立审核完成；SM015/SM016限定功能与入口已通过，SM017新综合后资格检查及流程提速进行中；完整物理尚未开始，G1完整对账保持OPEN。

先SM013归因、SM014四表/联合设计冻结，再RTL＋overlay＋测试集中交付、新综合与完整implementation。关键未知只阻塞相应候选，不扩成无界诊断；常规步骤连续推进，不新增逐项用户审批。

最近实际物理基线E008/AT004自然失败：702396重叠节点、547548冲突网，9491个C01成员全SLR2；完整place/physopt阶段通过但未合法布通。14项收尾与独立审核完成，原EDA结束。[E008证据](../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)。

功能、结构、合法route、时序规则/原余量、DRC/CDC/reset/IO/bus-skew分别验收。数值/ABI/双DDR/时钟/80保护不变；单EDA、原资源保护及正常无墙钟/静默强停；不重绑旧会话、不改旧工程/原始证据，无bitstream/板卡/GPU/PPL/ACC。

[项目目标](../goal/goal.md) · [当前任务](../mission/current.md) · [M003阶段记录](missions/M003_summary.md)
