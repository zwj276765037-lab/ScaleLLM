# ScaleLLM_MLP_fix

当前工作：[M006 MLP线性投影硬件工程](mission/M006_mlp_linear_only_hardware/contract.md)。优先实现和验证新的FPGA GU/DOWN引擎及双DDR集成，Host执行MLP预处理与非线性。

[设计规范](PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Design.md) · [实现计划](PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Implementation_Plan.md) · [工程状态](project/E013_mlp_linear_only_hardware/experiment_status/summary.md)

以下原README正文为克隆基线介绍；新任务的状态以M006/E013为准。

---


历史原文已保留：[整理前原文](.research-agent/navigation_history/c62e4d7ad0df396e0306d8dc44f540374af04589164b7e73dee79cd13a782e1b.md)

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# ScaleLLM_MLP_fix 项目首页

项目根：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`

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

[M006 · mlp_linear_only_hardware](mission/M006_mlp_linear_only_hardware/README.md)

合同：[原始任务定义](mission/M006_mlp_linear_only_hardware/contract.md)
唯一实现入口：[工程代码](project/hardware)

## 最新执行报告

| 职责 | 当前任务 / 阶段 | 执行状态 | 上报时间 | 下一步 / 阻塞 |
| --- | --- | --- | --- | --- |
| 项目主控与架构评判 | 完成项目主控对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.081240+00:00 | 本轮整理交付后由用户决定下一步，不自动恢复硬件任务  |
| 工程实现与验证 | 完成工程实现对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.232249+00:00 | 迁移后不自动综合、仿真、实现或上板  |
| 研究探索与瓶颈分析 | 完成研究探索对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.365918+00:00 | 后续讨论算法贡献、系统瓶颈与可证伪候选，不继承旧优化授权  |
| m002_rtl_repair | SM006 AT005 OPT reset CDC精确增量只读核查 R005 §7完成：2条CDC11与2条CDC10 source变化已定位；HostSplit精确consumer/极性预期已交付 | completed | 2026-10-15T06:11:22.942903+00:00 | 等待父派发新AT实际pin/全链/consumer证据的有界复核；安全资格OPEN，不扩展扫描/EDA  |
| m002_host_repair | SM003 Host布局与生命周期修复 106项CPU回归及独立只读审核已交付 | completed | 2026-10-14T23:55:43.097917+00:00 | 由父主控整合R002/R003验证  |
| m002_build_verify | 仅每小时有界分析的管理交接已完成 本轮结束；取消持续观察/驻留等待/阶段唤醒，保留AT027资源监督 | completed | 2026-10-19T08:12:13.106224+00:00 | Root每小时有界检查调度；本轮不再分析/新EDA/重试  |
| m002_physical_architecture_review | R004 AT001 v2 bounded independent entry review completed Missing mapping counterexample fixed; no substantive entry blocker | completed | 2026-10-20T08:26:57.028433+00:00 | Root/A018 install exact A007 gate and perform authorized read-only diagnosis; A007 has no observer or live polling  |
| m002_rtl_routability_explorer |   | 未登记 | 未登记 |   |
| m002_routability_rtl_implementation | SM009/E005/R001三RTL实现与两功能TB及原证据解释交付完成 Attention AT001和MLP AT003功能PASS；生产三RTL正式冻结 | completed | 2026-10-16T00:49:14.038166+00:00 | A006新综合实核48/32边界、fanout/负载与物理结果；A009按实际消息配合，不热改冻结源  |
| gsm8k_protocol | GPU0速度修复BF16/QDQ独立原始复核及readiness补强交付完成 两模型raw parity/15phase/16源审计及120/120最终CPU通过 | completed | 2026-10-18T11:43:20.233830+00:00 | ACC继续暂停；用户恢复后必须新R和全30组资格；本轮无GPU任务  |
| gsm8k_worker | M004/SM020全模型静态内容完整性修复与受控GPU0训练验证交付 CPU82稳定及A01089通过；BF16/QDQ各4题、原v2与完整性15阶段通过且独立接受；GPU0已释放hold | completed | 2026-10-18T04:55:13.699669+00:00 | 保持GPU0空闲，父负责GPU1维护交接及R003冻结/全新资格；不自动启动GPU/matrix/formal  |
| gpu1_repair | GPU1三轮诊断与限定管理员维护helper已交付 本子任务证据交付完成；GPU1实际维护/修复未完成 | completed | 2026-10-18T05:08:00.190361+00:00 | 管理员认证和外部GPU0资源交接后，实际GPU1维护及新AT复测；不宣称repair已成功  |
| gpu0_integrity_performance_repair | GPU0逐题完整性速度修复已生产接入并完成CPU验证 88/88 CPU、合成GPU14.461倍及parent guard10/10独审交付 | completed | 2026-10-18T11:22:00.504839+00:00 | 父负责正在运行的8B训练共享速度诊断；不自动恢复ACC  |
| rounding_design_and_review | R004/B001独审、generic冻结与有限队列静审已交付；整体精度inconclusive M005 / E012 / R004 B001 限定角色交付完成 | completed | 2026-10-19T05:05:59.876091+00:00 | Root Q001有限后台队列仍执行；A014不监控，完整正式数值结论待终态证据与汇总。  |
| rounding_reference_implementation | R012 response-quality CPU preparation delivered; generation and judging are not performed by this agent official885-question roster, lengths, blinded-pack/statistics/plot source v1 qualified | completed | 2026-10-20T08:15:45.611392+00:00 | Root runs the admitted generation stage; consume actual responses and frozen blind scores later. No continuous monitoring.  |
| rounding_data_and_experiment_runner | 一次有界状态核查完成：UTC 2026-10-19T07:35:34.627809+00:00 observed durable271/1024、组16/64；实验仍运行，非精度成功 R005 quarter-progress bookkeeping completed; experiment still running | completed | 2026-10-19T07:35:34.685237+00:00 | Root按既有supervisor继续监督完整冻结pipeline；A016不持续监控  |
| softmax_tv_measurement | M005/SM021+SM023/E012/R006标准输出Softmax TV补测 R006 full1024 TV, independent checks, CSV/JSON and integrated PNG complete | completed | 2026-10-19T14:15:46.200884+00:00 | Root终态独立审核与最终PNG目视检查；不宣称普遍精度保持  |
| m003_sol61_verification | R004/AT001本版失败DCP只读全量actual-driver/SLR归因 actual native read-only checkpoint load | running | 2026-10-20T08:29:36.293028+00:00 | 冻结全量light census耗尽→有界route样本→自然终态/源树锁收尾→离线对账及独审  |
| rounding_optimization_runner | All36dev baseline/c2/c4/ref0/ref2/ref4 with fixed/matched/dift metrics; no candidate omitted Six-arm repeated-development comparison running; first4 completed | running | 2026-10-20T01:42:19.175312+00:00 | Complete36, verify exit/release, independently recompute finalhidden and fixed FP64head witnesses, plot all results  |
| response_quality_generation | Background one-shot GPU0qualification/cost queue; source/input frozen; no answer generation yet AT005freeze complete; real bounded GPU0waiting phase active | running | 2026-10-20T08:32:54.429452+00:00 | Queue runs one1800spilot only after three empty observations and all frozen SHA/resource admission; final receipts automatic. Local handoff complete; no continuous manual6hwatch GPU0externalcompute occupancy; GPU1failedbyteintegr… |
| mlp_linear_architecture |   | 未登记 | 未登记 |   |
| mlp_linear_engineering |   | 未登记 | 未登记 |   |
| mlp_linear_host_reference |   | 未登记 | 未登记 |   |

## 当前证据范围（来自负责人概览，截取）

# ScaleLLM：审核总览

**2026-10-20最新：AT006已自然布线失败，原生Route35-2确认797175个重叠节点，最终route_status确认615840条资源冲突网。** 原尝试07:07:38Z监督结束native1/stop=null/owned_survivors空，route_failed.dcp及status/timing/congestion/DRC已保存；正式route POST未执行。完整place/physopt及其结构资格通过不代表可合法布通。现有证据显示局部跨SLR列需求0–1最高124%、1–2最高112%（对应总需求仅63.17%/62.30%），physopt占用CLB站点SLR0/1/2为96.71%/99.33%/99.90%，支持严重局部互连/打包压力；不将占用站点等同LUT槽耗尽，不将告警或top样本当唯一根因。用户随后明确要求“详细定位到底哪个地方无法布线成功”：A018已获派发，先现成报告离线归因，必要时新批次有界只读载入失败DCP，交付区域→模块→具体信号通路及覆盖/未知；不改RTL/XDC、不启动新implementation。单EDA、原资源保护及正常无墙钟/静默强停保持。M003整体未完成。

[验证提速与执行决定](mission/M003_joint_routability_closure/validation_efficiency_2026-10-19.md)

[重启后恢复合同](mission/M003_joint_routability_closure/server_restart_resume_2026-10-18.md) · [工程状态](project/E011_m003_joint_routability_implementation/experiment_status/summary.md)。

[M003合同](mission/M003_joint_routability_closure/contract.md)、[执行授权](mission/M003_joint_routability_closure/execution_start_2026-10-18.md)、[验收矩阵](mission/M003_joint_routability_closure/verification_matrix.md)和[候选决定表](mission/M003_joint_routability_closure/candidate_decision_register.md)为当前入口。G2设计冻结及独立审核完成；SM015/SM016限定功能与入口已通过，SM017新综合后资格检查及流程提速进行中；完整物理尚未开始，G1完整对账保持OPEN。

先SM013归因、SM014四表/联合设计冻结，再RTL＋overlay＋测试集中交付、新综合与完整implementation。关键未知只阻塞相应候选，不扩成无界诊断；常规步骤连续推进，不新增逐项用户审批。

最近实际物理基线E008/AT004自然失败：702396重叠节点、547548冲突网，9491个C01成员全SLR2；完整place/physopt阶段通过但未合法布通。14项收尾与独立审核完成，原EDA结束。[E008证据](project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)。

功能、结构、合法route、时序规则/原余量、DRC/CDC/reset/IO/bus-skew分别验收。数值/ABI/双DDR/时钟/80保护不变；单EDA、原资源保护及正常无墙钟/静默强停；不重绑旧会话、不改旧工程/原始证据，无bitstream/板卡/GPU/PPL/ACC。

[项目目标](goal/goal.md) · [当前任务](mission/current.md) · [M003阶段记录](results/missions/M003_summary.md)

[完整概览及审核来源](results/overview.md)

## 最近讨论

- [C001 · M001 初始化通信核验，非工程实验任务。请确认你能读取新根目录及当前仅整理、不改旧工程、不运行 EDA/GPU/板卡的边界。](communication/C001_M001%20%E5%88%9D%E5%A7%8B%E5%8C%96%E9%80%9A%E4%BF%A1%E6%A0%B8%E9%AA%8C%EF%BC%8C%E9%9D%9E%E5%B7%A5%E7%A8%8B%E5%AE%9E%E9%AA%8C%E4%BB%BB%E5%8A%A1%E3%80%82%E8%AF%B7%E7%A1%AE%E8%AE%A4%E4%BD%A0%E8%83%BD%E8%AF%BB%E5%8F%96%E6%96%B0%E6%A0%B9%E7%9B%AE%E5%BD%95%E5%8F%8A%E5%BD%93%E5%89%8D%E4%BB%85%E6%95%B4%E7%90%86%E3%80%81%E4%B8%8D%E6%94%B9%E6%97%A7%E5%B7%A5%E7%A8%8B%E3%80%81%E4%B8%8D%E8%BF%90%E8%A1%8C%20EDA_GPU_%E6%9D%BF%E5%8D%A1%E7%9A%84/thread.md) — 已关闭

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
