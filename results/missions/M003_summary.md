# M003：联合可布线任务与当前状态

**2026-10-20最新：AT006已自然布线失败，原生Route35-2确认797175个重叠节点，最终route_status确认615840条资源冲突网。** 原尝试07:07:38Z监督结束native1/stop=null/owned_survivors空，route_failed.dcp及status/timing/congestion/DRC已保存；正式route POST未执行。完整place/physopt及其结构资格通过不代表可合法布通。现有证据显示局部跨SLR列需求0–1最高124%、1–2最高112%（对应总需求仅63.17%/62.30%），physopt占用CLB站点SLR0/1/2为96.71%/99.33%/99.90%，支持严重局部互连/打包压力；不将占用站点等同LUT槽耗尽，不将告警或top样本当唯一根因。用户随后明确要求“详细定位到底哪个地方无法布线成功”：A018已获派发，先现成报告离线归因，必要时新批次有界只读载入失败DCP，交付区域→模块→具体信号通路及覆盖/未知；不改RTL/XDC、不启动新implementation。单EDA、原资源保护及正常无墙钟/静默强停保持。M003整体未完成。

[验证提速与执行决定](../../mission/M003_joint_routability_closure/validation_efficiency_2026-10-19.md)

[重启后恢复合同](../../mission/M003_joint_routability_closure/server_restart_resume_2026-10-18.md) · [工程状态](../../project/E011_m003_joint_routability_implementation/experiment_status/summary.md)。

execution_state: running  
verdict: inconclusive  
applicability: SM013固定查询及代表路径的适用范围已独立接受；报告精确对账仍OPEN。SM014设计与独立审核完成，G2已正式冻结；SM015/SM016限定功能/入口通过，SM017新综合后报告进行中，G4 OPEN。  
review: Root限定接受现有证据用于设计及候选判断，不冒充用户技术结果批准。

## 对goal的作用

承接M002的DDR分离架构及E008/AT004自然失败证据，先归因与冻结，集中交付RTL、正式物理约束、测试和入口，再新综合、完整实现。M002未成功目标保持，不以新编号抹去失败。依赖M002是证据承接，不要求其先成功布通。

## 已定义的子任务

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| [SM013](../../mission/M003_joint_routability_closure/tasks/SM013.md) | 全量失败网分类和有限端点归因 | completed：固定查询证据限定接受；报告精确对账OPEN |
| [SM014](../../mission/M003_joint_routability_closure/tasks/SM014.md) | 四表、候选纳入/排除与联合设计冻结 | completed：G2设计冻结，M2+A3+C-P1 selected |
| [SM015](../../mission/M003_joint_routability_closure/tasks/SM015.md) | 选定RTL集中改造 | completed：G3a限定功能集成独立通过 |
| [SM016](../../mission/M003_joint_routability_closure/tasks/SM016.md) | 新overlay/入口、协议数值回归与集成 | completed：G3b v3与288项回归独立通过 |
| [SM017](../../mission/M003_joint_routability_closure/tasks/SM017.md) | 新综合、结构资格和实现输入冻结 | running：查询去重/入口修复进行中；完整新图资格与G4待验 |
| [SM018](../../mission/M003_joint_routability_closure/tasks/SM018.md) | 固定版本完整place→physopt→route | planned |
| [SM019](../../mission/M003_joint_routability_closure/tasks/SM019.md) | 验收矩阵、独立核查、总报告与交接 | planned |

## 关键约束与待定选择

MLP FIFO数据组织、Attention元数据地址、配套物理约束是重点评估对象；具体副本/银行/位置以及算术结构是否选入由SM013–014冻结，未预判有效。保持数值/ABI/DDR/100MHz与200MHz时钟、80保护和原时序目标；正常进程不设置墙钟/静默强停，单EDA及原资源保护不变。

合法路由、时序规则、原目标余量、DRC/CDC/reset/IO/bus-skew分别验收，任一必要项未达则整体未完成。不生成bitstream、不上板、不运行GPU/PPL/ACC。当前没有本mission的布通或性能结论。

AT001/AT002解析适配问题已修复；AT003自然完成，工程与独立复算已交付。SM013历史：535331同已知SLR端点不构成唯一因果，字段/控制/物理总成本由现有实际数据支持。[E009最新状态](../../project/E009_m003_failed_net_attribution/experiment_status/summary.md)。后续按G3–G6继续，已冻结选型，原始E008证据/冻结包/旧工程保持。
