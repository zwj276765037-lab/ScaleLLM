# M003：任务定义与当前状态

**原生启动已核：E009/R001/AT001于北京时间08:40:06启动Vivado，只读载入E008失败图。** 固定包独立审核通过，唯一EDA锁、进程身份和资源限制已核；G1归因与G2选型尚未完成，生产RTL未改。[最新状态](../../project/E009_m003_failed_net_attribution/experiment_status/summary.md)。下方准备阶段描述为此前观测。

**2026-10-18执行启动：用户已明确“可以开始进行mission”，M003进入SM013工程准备。** A006执行和A007独立审核任务已真实送达；本条记录时尚无新原生EDA启动核验，具体状态以新实验回执为准。按已审合同连续推进技术依赖，常规步骤不新增用户批准。 [启动记录](../../mission/M003_joint_routability_closure/execution_start_2026-10-18.md)。下方“仅定义/未执行”为启动前历史。

2026-10-18，依据用户“定义成完整详细的mission”，已建立[联合可布线改造与完整实现验收合同](../../mission/M003_joint_routability_closure/contract.md)及[验证矩阵](../../mission/M003_joint_routability_closure/verification_matrix.md)。

execution_state: running  
verdict: unassessed  
applicability: SM013/E009准备与CPU协议对照已完成，待独立预运行审核；AT001已登记planned，无原生EDA归因结果、无生产改动。  
review: [独立文档审核](../reviews/M003_definition_review_2026-10-18.md)已完成，两项歧义修订闭合，七个SM与主合同/矩阵一致；不能作为设计有效、布通成功或用户结果批准。

## 对goal的作用

承接M002的DDR分离架构及E008/AT004自然失败证据，先归因与冻结，集中交付RTL、正式物理约束、测试和入口，再新综合、完整实现。M002未成功目标保持，不以新编号抹去失败。依赖M002是证据承接，不要求其先成功布通。

## 已定义的子任务

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| [SM013](../../mission/M003_joint_routability_closure/tasks/SM013.md) | 全量失败网分类和有限端点归因 | running：E009准备/待原生启动 |
| [SM014](../../mission/M003_joint_routability_closure/tasks/SM014.md) | 四表、候选纳入/排除与联合设计冻结 | planned |
| [SM015](../../mission/M003_joint_routability_closure/tasks/SM015.md) | 选定RTL集中改造 | planned |
| [SM016](../../mission/M003_joint_routability_closure/tasks/SM016.md) | 新overlay/入口、协议数值回归与集成 | planned |
| [SM017](../../mission/M003_joint_routability_closure/tasks/SM017.md) | 新综合、结构资格和实现输入冻结 | planned |
| [SM018](../../mission/M003_joint_routability_closure/tasks/SM018.md) | 固定版本完整place→physopt→route | planned |
| [SM019](../../mission/M003_joint_routability_closure/tasks/SM019.md) | 验收矩阵、独立核查、总报告与交接 | planned |

## 关键约束与待定选择

MLP FIFO数据组织、Attention元数据地址、配套物理约束是重点评估对象；具体副本/银行/位置以及算术结构是否选入由SM013–014冻结，未预判有效。保持数值/ABI/DDR/100MHz与200MHz时钟、80保护和原时序目标；正常进程不设置墙钟/静默强停，单EDA及原资源保护不变。

合法路由、时序规则、原目标余量、DRC/CDC/reset/IO/bus-skew分别验收，任一必要项未达则整体未完成。不生成bitstream、不上板、不运行GPU/PPL/ACC。当前没有本mission的布通或性能结论。

SM013已真实委派，E009已登记并完成准备/CPU对照。144输入、失败DCP、单EDA和资源预检通过；A007正在审核固定入口。[E009最新状态](../../project/E009_m003_failed_net_attribution/experiment_status/summary.md)。后续按G1–G6继续，未选择候选，原始E008证据/冻结包/旧工程保持。
