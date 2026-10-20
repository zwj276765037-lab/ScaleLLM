# M003：联合可布线任务与当前状态

**2026-10-18 G2设计已正式冻结，SM015/SM016已真实派发。** 选定C-M2（81个区域CE缓冲）+C-A3（两128位/各40 URAM地址切片）+C-P1（保留C01 hard-SLR2及原物理策略）。SM014独立审核已通过设计适用性，开始集中RTL、overlay与功能验证；新综合/implementation尚未启动。G1计数差22049及TOP01 −2.896ns剩余风险保持，未宣称布通。

[G2正式冻结与连续执行](../../mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md) · [独立设计审核](../../agent/A007/M003_SM014_review_20261018/G2_consolidated_design_review.md)。

execution_state: running  
verdict: inconclusive  
applicability: SM013固定查询及代表路径的适用范围已独立接受；报告精确对账仍OPEN。SM014工程与独立审核已重新实际派发，G2未冻结。  
review: Root限定接受现有证据用于设计及候选判断，不冒充用户技术结果批准。

## 对goal的作用

承接M002的DDR分离架构及E008/AT004自然失败证据，先归因与冻结，集中交付RTL、正式物理约束、测试和入口，再新综合、完整实现。M002未成功目标保持，不以新编号抹去失败。依赖M002是证据承接，不要求其先成功布通。

## 已定义的子任务

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| [SM013](../../mission/M003_joint_routability_closure/tasks/SM013.md) | 全量失败网分类和有限端点归因 | completed：固定查询证据限定接受；报告精确对账OPEN |
| [SM014](../../mission/M003_joint_routability_closure/tasks/SM014.md) | 四表、候选纳入/排除与联合设计冻结 | running：A006设计/A007审核已真实派发 |
| [SM015](../../mission/M003_joint_routability_closure/tasks/SM015.md) | 选定RTL集中改造 | planned |
| [SM016](../../mission/M003_joint_routability_closure/tasks/SM016.md) | 新overlay/入口、协议数值回归与集成 | planned |
| [SM017](../../mission/M003_joint_routability_closure/tasks/SM017.md) | 新综合、结构资格和实现输入冻结 | planned |
| [SM018](../../mission/M003_joint_routability_closure/tasks/SM018.md) | 固定版本完整place→physopt→route | planned |
| [SM019](../../mission/M003_joint_routability_closure/tasks/SM019.md) | 验收矩阵、独立核查、总报告与交接 | planned |

## 关键约束与待定选择

MLP FIFO数据组织、Attention元数据地址、配套物理约束是重点评估对象；具体副本/银行/位置以及算术结构是否选入由SM013–014冻结，未预判有效。保持数值/ABI/DDR/100MHz与200MHz时钟、80保护和原时序目标；正常进程不设置墙钟/静默强停，单EDA及原资源保护不变。

合法路由、时序规则、原目标余量、DRC/CDC/reset/IO/bus-skew分别验收，任一必要项未达则整体未完成。不生成bitstream、不上板、不运行GPU/PPL/ACC。当前没有本mission的布通或性能结论。

AT001/AT002解析适配问题已修复；AT003自然完成，工程与独立复算已交付。当前衔接SM014，535331同已知SLR端点不构成唯一因果，字段/控制/物理总成本由现有实际数据支持。[E009最新状态](../../project/E009_m003_failed_net_attribution/experiment_status/summary.md)。后续按G1–G6继续，未选择候选，原始E008证据/冻结包/旧工程保持。
