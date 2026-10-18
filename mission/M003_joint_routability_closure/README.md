

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

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

- 前置：[M002 · ddr_separation_and_timing_recovery](../M002_ddr_separation_and_timing_recovery/README.md)

## 任务总结原文摘录

# M003：任务定义与当前状态

2026-10-18，依据用户“定义成完整详细的mission”，已建立[联合可布线改造与完整实现验收合同](contract.md)及[验证矩阵](verification_matrix.md)。

execution_state: planned  
verdict: unassessed  
applicability: 本次仅完成任务定义；没有M003生产改动、仿真、EDA或新E/R/AT结果。  
review: [独立文档审核](../../results/reviews/M003_definition_review_2026-10-18.md)已完成，两项歧义修订闭合，七个SM与主合同/矩阵一致；不能作为设计有效、布通成功或用户结果批准。

## 对goal的作用

承接M002的DDR分离架构及E008/AT004自然失败证据，先归因与冻结，集中交付RTL、正式物理约束、测试和入口，再新综合、完整实现。M002未成功目标保持，不以新编号抹去失败。依赖M002是证据承接，不要求其先成功布通。

## 已定义的子任务

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| [SM013](tasks/SM013.md) | 全量失败网分类和有限端点归因 | planned |
| [SM014](tasks/SM014.md) | 四表、候选纳入/排除与联合设计冻结 | planned |
| [SM015](tasks/SM015.md) | 选定RTL集中改造 | planned |
| [SM016](tasks/SM016.md) | 新overlay/入口、协议数值回归与集成 | planned |
| [SM017](tasks/SM017.md) | 新综合、结构资格和实现输入冻结 | planned |
| [SM018](tasks/SM018.md) | 固定版本完整place→physopt→route | planned |
| [SM019](tasks/SM019.md) | 验收矩阵、独立核查、总报告与交接 | planned |

## 关键约束与待定选择

MLP FIFO数据组织、Attention元数据地址、配套物理约束是重点评估对象；具体副本/银行/位置以及算术结构是否选入由SM013–014冻结，未预判有效。保持数值/ABI/DDR/100MHz与200MHz时钟、80保护和原时序目标；正常进程不设置墙钟/静默强停，单EDA及原资源保护不变。

合法路由、时序规则、原目标余量、DRC/CDC/reset/IO/bus-skew分别验收，任一必要项未达则整体未完成。不生成bitstream、不上板、不运行GPU/PPL/ACC。当前没有本mission的布通或

（摘录截断；完整记录见链接。）

## 相关决定、变更与讨论

- [README](../../results/README.md)
- [overview](../../results/overview.md)

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
