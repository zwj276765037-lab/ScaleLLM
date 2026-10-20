

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# M003 · joint_routability_closure

[任务合同](contract.md) · [任务总结](../../results/missions/M003_summary.md)

## 执行子任务与主控审核

| 子任务 | 定义 | 完整审核历史 |
| --- | --- | --- |
| SM013 · failed_net_attribution | [定义](tasks/SM013.md) | [审核](../../results/reviews/SM013.md) |
| SM014 · joint_design_freeze | [定义](tasks/SM014.md) | [审核](../../results/reviews/SM014.md) |
| SM015 · joint_rtl_locality_implementation | [定义](tasks/SM015.md) | [审核](../../results/reviews/SM015.md) |
| SM016 · physical_entry_and_functional_regression | [定义](tasks/SM016.md) | [审核](../../results/reviews/SM016.md) |
| SM017 · fresh_synthesis_and_structural_admission | [定义](tasks/SM017.md) | [审核](../../results/reviews/SM017.md) |
| SM018 · fixed_version_full_implementation | [定义](tasks/SM018.md) | [审核](../../results/reviews/SM018.md) |
| SM019 · integrated_acceptance_and_handoff | [定义](tasks/SM019.md) | [审核](../../results/reviews/SM019.md) |

## 关联实验

- [E009 · m003_failed_net_attribution](../../project/E009_m003_failed_net_attribution/README.md) — completed
- [E011 · m003_joint_routability_implementation](../../project/E011_m003_joint_routability_implementation/README.md) — running
- 前置：[M002 · ddr_separation_and_timing_recovery](../M002_ddr_separation_and_timing_recovery/README.md)

## 任务总结原文摘录

# M003：联合可布线任务与当前状态

**2026-10-20最新：AT006已自然布线失败，原生Route35-2确认797175个重叠节点，最终route_status确认615840条资源冲突网。** 原尝试07:07:38Z监督结束native1/stop=null/owned_survivors空，route_failed.dcp及status/timing/congestion/DRC已保存；正式route POST未执行。完整place/physopt及其结构资格通过不代表可合法布通。现有证据显示局部跨SLR列需求0–1最高124%、1–2最高112%（对应总需求仅63.17%/62.30%），physopt占用CLB站点SLR0/1/2为96.71%/99.33%/99.90%，支持严重局部互连/打包压力；不将占用站点等同LUT槽耗尽，不将告警或top样本当唯一根因。用户随后明确要求“详细定位到底哪个地方无法布线成功”：A018已获派发，先现成报告离线归因，必要时新批次有界只读载入失败DCP，交付区域→模块→具体信号通路及覆盖/未知；不改RTL/XDC、不启动新implementation。单EDA、原资源保护及正常无墙钟/静默强停保持。M003整体未完成。

[验证提速与执行决定](validation_efficiency_2026-10-19.md)

[重启后恢复合同](server_restart_resume_2026-10-18.md) · [工程状态](../../project/E011_m003_joint_routability_implementation/experiment_status/summary.md)。

execution_state: running  
verdict: inconclusive  
applicability: SM013固定查询及代表路径的适用范围已独立接受；报告精确对账仍OPEN。SM014设计与独立审核完成，G2已正式冻结；SM015/SM016限定功能/入口通过，SM017新综合后报告进行中，G4 OPEN。  
review: Root限定接受现有证据用于设计及候选判断，不冒充用户技术结果批准。

## 对goal的作用

承接M002的DDR分离架构及E008/AT004自然失败证据，先归因与冻结，集中交付RTL、正式物理约束、测试和入口，再新综合、完整实现。M002未成功目标保持，不以新编号抹去失败。依赖M002是证据承接，不要求其先成功布通。

## 已定义的子任务

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| [SM013](tasks/SM013.md) | 全量失败网分类和有限端点归因 | completed：固定查询证据限定接受；报告精确对账OPEN |
| [SM014](tasks/SM014.md) | 四表、候选纳入/排除与联合设计冻结 | completed：G2设计冻结，M2+A3+C-P1 selected |
| [SM015](tasks/SM015.md) | 选定RTL集中改造 | completed：G3a限定功能集成独立通过 |
| [S

（摘录截断；完整记录见链接。）

## 相关决定、变更与讨论

- [README](../../results/README.md)
- [hardware_metrics](../../results/hardware_metrics.md)
- [overview](../../results/overview.md)
- [review_queue](../../results/review_queue.md)

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
