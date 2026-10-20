# ScaleLLM

**原生启动已核：E009/R001/AT001于北京时间08:40:06启动Vivado，只读载入E008失败图。** 固定包独立审核通过，唯一EDA锁、进程身份和资源限制已核；G1归因与G2选型尚未完成，生产RTL未改。[最新状态](project/E009_m003_failed_net_attribution/experiment_status/summary.md)。下方准备阶段描述为此前观测。

**当前M003已开始执行。** SM013 / E009已完成归因入口准备和CPU协议对照，A007正在独立预运行审核；原生EDA尚未启动，生产RTL未修改，候选未选定。

- [M003完整合同](mission/M003_joint_routability_closure/contract.md) · [执行启动授权](mission/M003_joint_routability_closure/execution_start_2026-10-18.md) · [当前任务](mission/current.md)
- [E009最新状态](project/E009_m003_failed_net_attribution/experiment_status/summary.md) · [验收矩阵](mission/M003_joint_routability_closure/verification_matrix.md) · [候选决定表](mission/M003_joint_routability_closure/candidate_decision_register.md)
- [软件](project/software/README.md) · [硬件](project/hardware/README.md) · [项目目标](goal/goal.md)
- [E008终态](project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)：AT004自然route失败，702396重叠节点/547548冲突网，收尾已核；M002目标未完成。
- [M003阶段记录](results/missions/M003_summary.md) · [项目对话入口](agent/work_chats.md)

先归因和集中设计冻结，再一次配齐RTL/约束/测试、新综合、完整实现。普通步骤按授权连续推进；保留全局不变量、单EDA、原资源保护及正常无墙钟/静默强停，旧工程与冻结证据只读。

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T02:10:14.644741+00:00。来源修订：`7ceee81686fc`。

# ScaleLLM 项目首页

项目根：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`

## 查看入口

| 记录 | 入口 |
| --- | --- |
| 目标与历史 | [打开](goal/goal.md) |
| 所有 mission | [打开](mission/index.md) |
| 实验与每次结果 | [打开](project/index.md) |
| agent 讨论与待办 | [打开](communication/index.md) |
| 用户技术问答 | [打开](question/index.md) |
| 四个职责会话 | [打开](agent/index.md) |
| 全项目报告与历史 | [打开](results/index.md) |

## 当前任务

[M003 · joint_routability_closure](mission/M003_joint_routability_closure/README.md)

合同：[原始任务定义](mission/M003_joint_routability_closure/contract.md)
前置任务：[M002 · ddr_separation_and_timing_recovery](mission/M002_ddr_separation_and_timing_recovery/README.md)
唯一实现入口：[工程代码](project)

## 最新执行报告

| 职责 | 当前任务 / 阶段 | 执行状态 | 上报时间 | 下一步 / 阻塞 |
| --- | --- | --- | --- | --- |
| 项目主控与架构评判 | 完成项目主控对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.081240+00:00 | 本轮整理交付后由用户决定下一步，不自动恢复硬件任务  |
| 工程实现与验证 | 完成工程实现对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.232249+00:00 | 迁移后不自动综合、仿真、实现或上板  |
| 研究探索与瓶颈分析 | 完成研究探索对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.365918+00:00 | 后续讨论算法贡献、系统瓶颈与可证伪候选，不继承旧优化授权  |
| m002_rtl_repair | SM006 AT005 OPT reset CDC精确增量只读核查 R005 §7完成：2条CDC11与2条CDC10 source变化已定位；HostSplit精确consumer/极性预期已交付 | completed | 2026-10-15T06:11:22.942903+00:00 | 等待父派发新AT实际pin/全链/consumer证据的有界复核；安全资格OPEN，不扩展扫描/EDA  |
| m002_host_repair | SM003 Host布局与生命周期修复 106项CPU回归及独立只读审核已交付 | completed | 2026-10-14T23:55:43.097917+00:00 | 由父主控整合R002/R003验证  |
| m002_build_verify | M003/SM013 E009 R001 AT003全量失败网只读归因 02:08:45Z固定28组×max/min=56命令code0完成；final aggregate268663活跃，native/supervisor未终态，G1未过 | running | 2026-10-18T02:10:04.198076+00:00 | final aggregate自然结束后collector v3/raw audit v3统一原始复算和完整G1审核；差22049保持OPEN  |
| m002_physical_architecture_review | M003 SM013诊断包与G1口径独立审核，SM014架构冻结准备 AT003初次分类小表已审，535331同SLR端点；固定deep/时序进行，raw audit v3已独立准备，G1/22049差额待闭合 | running | 2026-10-18T02:10:13.610862+00:00 | 自然终态后核v3实际raw复算、deep属性/时序、计数差额与候选关键缺口；保持固定范围  |
| m002_rtl_routability_explorer |   | 未登记 | 未登记 |   |
| m002_routability_rtl_implementation | SM009/E005/R001三RTL实现与两功能TB及原证据解释交付完成 Attention AT001和MLP AT003功能PASS；生产三RTL正式冻结 | completed | 2026-10-16T00:49:14.038166+00:00 | A006新综合实核48/32边界、fanout/负载与物理结果；A009按实际消息配合，不热改冻结源  |
| gsm8k_protocol |   | 未登记 | 未登记 |   |
| gsm8k_worker |   | 未登记 | 未登记 |   |

## 当前证据范围（来自负责人概览，截取）

# ScaleLLM：审核总览

**原生启动已核：E009/R001/AT001于北京时间08:40:06启动Vivado，只读载入E008失败图。** 固定包独立审核通过，唯一EDA锁、进程身份和资源限制已核；G1归因与G2选型尚未完成，生产RTL未改。[最新状态](project/E009_m003_failed_net_attribution/experiment_status/summary.md)。下方准备阶段描述为此前观测。

**M003执行running，当前SM013/E009为准备及独立审核阶段，尚无原生EDA归因结果。** 用户已明确开始执行；A006/A007已真实派发，E009/R001/AT001登记完成。固定查询包和CPU协议对照通过，144生产输入、失败DCP及资源/单EDA预检完成；A007正在审核。详见[E009状态](project/E009_m003_failed_net_attribution/experiment_status/summary.md)。

[M003合同](mission/M003_joint_routability_closure/contract.md)、[执行授权](mission/M003_joint_routability_closure/execution_start_2026-10-18.md)、[验收矩阵](mission/M003_joint_routability_closure/verification_matrix.md)和[候选决定表](mission/M003_joint_routability_closure/candidate_decision_register.md)为当前入口。任务定义已经独立审核；实际选型、RTL和G1归因未验收，不能将文档通过当方法有效。

先SM013归因、SM014四表/联合设计冻结，再RTL＋overlay＋测试集中交付、新综合与完整implementation。关键未知只阻塞相应候选，不扩成无界诊断；常规步骤连续推进，不新增逐项用户审批。

最近实际物理基线E008/AT004自然失败：702396重叠节点、547548冲突网，9491个C01成员全SLR2；完整place/physopt阶段通过但未合法布通。14项收尾与独立审核完成，原EDA结束。[E008证据](project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)。

功能、结构、合法route、时序规则/原余量、DRC/CDC/reset/IO/bus-skew分别验收。数值/ABI/双DDR/时钟/80保护不变；单EDA、原资源保护及正常无墙钟/静默强停；不重绑旧会话、不改旧工程/原始证据，无bitstream/板卡/GPU/PPL/ACC。

[项目目标](goal/goal.md) · [当前任务](mission/current.md) · [M003阶段记录](results/missions/M003_summary.md)

[完整概览及审核来源](results/overview.md)

## 最近讨论

- [C001 · M001 初始化通信核验，非工程实验任务。请确认你能读取新根目录及当前仅整理、不改旧工程、不运行 EDA/GPU/板卡的边界。](communication/C001_M001%20%E5%88%9D%E5%A7%8B%E5%8C%96%E9%80%9A%E4%BF%A1%E6%A0%B8%E9%AA%8C%EF%BC%8C%E9%9D%9E%E5%B7%A5%E7%A8%8B%E5%AE%9E%E9%AA%8C%E4%BB%BB%E5%8A%A1%E3%80%82%E8%AF%B7%E7%A1%AE%E8%AE%A4%E4%BD%A0%E8%83%BD%E8%AF%BB%E5%8F%96%E6%96%B0%E6%A0%B9%E7%9B%AE%E5%BD%95%E5%8F%8A%E5%BD%93%E5%89%8D%E4%BB%85%E6%95%B4%E7%90%86%E3%80%81%E4%B8%8D%E6%94%B9%E6%97%A7%E5%B7%A5%E7%A8%8B%E3%80%81%E4%B8%8D%E8%BF%90%E8%A1%8C%20EDA_GPU_%E6%9D%BF%E5%8D%A1%E7%9A%84/thread.md) — 已关闭

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
