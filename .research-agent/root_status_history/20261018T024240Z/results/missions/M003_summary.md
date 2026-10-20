# M003：联合可布线任务与当前状态

**2026-10-18北京时间10:10核验：M003/SM013正在E009/R001/AT003的最终汇总阶段。** 全量轻量网/端点导出和固定56项代表时序查询已完成，尚待自然终态、原始数据独立复算及G1审核；候选未选、生产RTL未改，新综合/implementation未开始。

初次分类得到569597个canonical网、848个互斥主组；其中535331个网的驱动与全部可见负载位于同一个已知SLR，不能据此认定实际路由范围或唯一根因。原生report为547548，差22049待对账解释。77.8389%是前20整组与补充集合的分类覆盖，不是深查或mission完成率。

[当前工程状态](../../project/E009_m003_failed_net_attribution/experiment_status/summary.md) · [初次独立审核](../../agent/A007/M003_SM013_review_20261018/AT003_prelaunch_f0ac0b91/first_aggregate_review.md)。

execution_state: running  
verdict: inconclusive  
applicability: AT003初次网级分类和固定查询完成，最终聚合、独立原始复算与G1未完成；无候选选定或生产修改。  
review: 初次小表算术及alias资格已独立接受，未作为G1/G2或用户技术结果批准。

## 对goal的作用

承接M002的DDR分离架构及E008/AT004自然失败证据，先归因与冻结，集中交付RTL、正式物理约束、测试和入口，再新综合、完整实现。M002未成功目标保持，不以新编号抹去失败。依赖M002是证据承接，不要求其先成功布通。

## 已定义的子任务

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| [SM013](../../mission/M003_joint_routability_closure/tasks/SM013.md) | 全量失败网分类和有限端点归因 | running：E009/AT003最终汇总及G1审核待完成 |
| [SM014](../../mission/M003_joint_routability_closure/tasks/SM014.md) | 四表、候选纳入/排除与联合设计冻结 | planned |
| [SM015](../../mission/M003_joint_routability_closure/tasks/SM015.md) | 选定RTL集中改造 | planned |
| [SM016](../../mission/M003_joint_routability_closure/tasks/SM016.md) | 新overlay/入口、协议数值回归与集成 | planned |
| [SM017](../../mission/M003_joint_routability_closure/tasks/SM017.md) | 新综合、结构资格和实现输入冻结 | planned |
| [SM018](../../mission/M003_joint_routability_closure/tasks/SM018.md) | 固定版本完整place→physopt→route | planned |
| [SM019](../../mission/M003_joint_routability_closure/tasks/SM019.md) | 验收矩阵、独立核查、总报告与交接 | planned |

## 关键约束与待定选择

MLP FIFO数据组织、Attention元数据地址、配套物理约束是重点评估对象；具体副本/银行/位置以及算术结构是否选入由SM013–014冻结，未预判有效。保持数值/ABI/DDR/100MHz与200MHz时钟、80保护和原时序目标；正常进程不设置墙钟/静默强停，单EDA及原资源保护不变。

合法路由、时序规则、原目标余量、DRC/CDC/reset/IO/bus-skew分别验收，任一必要项未达则整体未完成。不生成bitstream、不上板、不运行GPU/PPL/ACC。当前没有本mission的布通或性能结论。

AT001/AT002均因取数脚本名称解析适配问题自然失败并完成收尾；修复经独立增量审核，AT003已完成全量导出与固定代表时序，继续最终汇总/独立复算。[E009最新状态](../../project/E009_m003_failed_net_attribution/experiment_status/summary.md)。后续按G1–G6继续，未选择候选，原始E008证据/冻结包/旧工程保持。
