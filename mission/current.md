# 当前大mission：M003 联合可布线改造与完整实现验收

**最新用户要求：高效长运行，不再依赖用户反复追问。** A018已被实际followup为持续工程执行：正常工具等待交给机器终态事件，结束即分析/普通修复/续跑；Root保持本轮任务以衔接必要独立G4审核。取消此前“只完成启动便结束代理轮次”的交付方式，不恢复高频读日志或逐阶段播报，按小时有界分析、有实质问题及最终结果再报告。现有AT029正常运行与原资源保护保持，不能重复启动或强停。[持续执行决定](../.research-agent/decision_inputs/M003_continuous_event_execution_20261019.json)。

**最新用户执行指令：创建6.1-sol快速进行验证，有问题再告知。** Root已实际创建`/root/m003_sol61_verification`（请求gpt-6.1-sol/xhigh），接替原A006承担本轮project/唯一EDA；原A006只读、A007单次独审。立即复核AT027终态并冻结综合产物、实际启动后续资格验证，常规修复连续。低token要求仍有效：不恢复高频观察器/模型驻留等待，Root按小时有界分析，仅实质问题或最终结果通知；此前当轮“只读不启动”已由本次执行授权取代。[实际委派与所有权](../.research-agent/decision_inputs/M003_sol61_verification_execution_20261019.json)。

**最新用户运行方式：仅每小时一次有界分析，停止持续盯进程及按阶段高频唤醒。** A007只读观察器已核身份退出；已有EDA和自动资源保护继续。每次只查看最新状态/新增证据，给出简短分析后结束，不用等待循环模拟定时。当前会话无本地定时唤醒工具，自动排程尚未建立；不冒称会自行按时唤醒。见[频率与执行记录](../.research-agent/decision_inputs/M003_hourly_analysis_policy_20261019.json)。

**2026-10-20最新：AT006已自然布线失败，原生Route35-2确认797175个重叠节点，最终route_status确认615840条资源冲突网。** 原尝试07:07:38Z监督结束native1/stop=null/owned_survivors空，route_failed.dcp及status/timing/congestion/DRC已保存；正式route POST未执行。完整place/physopt及其结构资格通过不代表可合法布通。现有证据显示局部跨SLR列需求0–1最高124%、1–2最高112%（对应总需求仅63.17%/62.30%），physopt占用CLB站点SLR0/1/2为96.71%/99.33%/99.90%，支持严重局部互连/打包压力；不将占用站点等同LUT槽耗尽，不将告警或top样本当唯一根因。用户随后明确要求“详细定位到底哪个地方无法布线成功”：A018已获派发，先现成报告离线归因，必要时新批次有界只读载入失败DCP，交付区域→模块→具体信号通路及覆盖/未知；不改RTL/XDC、不启动新implementation。单EDA、原资源保护及正常无墙钟/静默强停保持。M003整体未完成。

[验证提速与执行决定](M003_joint_routability_closure/validation_efficiency_2026-10-19.md)

[重启后恢复合同](../mission/M003_joint_routability_closure/server_restart_resume_2026-10-18.md) · [工程状态](../project/E011_m003_joint_routability_implementation/experiment_status/summary.md)。

[主合同](M003_joint_routability_closure/contract.md) · [启动授权](M003_joint_routability_closure/execution_start_2026-10-18.md) · [E009三摘要入口](../project/E009_m003_failed_net_attribution/README.md) · [候选决定表](M003_joint_routability_closure/candidate_decision_register.md)。

顺序：SM013归因 → SM014四表/集中选型 → SM015 RTL＋SM016入口/回归 → SM017新综合/结构资格 → SM018完整实现 → SM019全局验收。按技术依赖连续推进，常规修复不新增用户逐项批准。G2已选定M2+A3+C-P1；工程于11:17:41实际开始E011/AT001，常规阶段按已授权连续执行。

E008/AT004仍为最近实际物理基线：自然route失败，702396重叠节点/547548冲突网，9491个C01对象全SLR2；14项收尾已独立核验。M002未成功，依赖是架构/证据承接，不要求其先布通。PDU暂停已解除。

数值/ABI/双DDR/core100MHz/DDR UI200MHz、80保护和验收保持；单EDA、原资源保护、正常无墙钟/静默强停；最多3活跃含Root、无后代，不重绑旧会话，不改旧工程/冻结证据，无bitstream/板卡/GPU/PPL/ACC。

<!-- research-agent:identity-index:begin -->
## Registered identities

This index records identity and links only. Execution, conclusions and user decisions remain in the linked records.

| Mission | Title | Contract | Summary |
|---|---|---|---|
| M001 | clean_project_migration | [contract](../mission/M001_clean_project_migration/contract.md) | [summary](../results/missions/M001_summary.md) |
| M002 | ddr_separation_and_timing_recovery | [contract](../mission/M002_ddr_separation_and_timing_recovery/contract.md) | [summary](../results/missions/M002_summary.md) |
| M003 | joint_routability_closure | [contract](../mission/M003_joint_routability_closure/contract.md) | [summary](../results/missions/M003_summary.md) |
| M004 | gsm8k_accuracy_completion | [contract](../mission/M004_gsm8k_accuracy_completion/contract.md) | [summary](../results/missions/M004_summary.md) |
| M005 | multistage_rounding_precision | [contract](../mission/M005_multistage_rounding_precision/contract.md) | [summary](../results/missions/M005_summary.md) |
<!-- research-agent:identity-index:end -->
