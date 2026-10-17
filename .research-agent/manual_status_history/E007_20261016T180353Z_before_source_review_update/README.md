> 当前任务：用户已授权定向优化后开启下一轮完整implementation，SM011/E007正在准备将输入前端成组迁往SLR2的工程入口；实际新EDA尚未启动。[执行合同](mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)、[E007状态](project/E007_m002_slr2_input_locality_implementation/experiment_status/summary.md)。前置SM010/E006只读诊断仍运行，已核模块资源与候选规模，热点/连接及真实收尾尚未完成；单EDA和正常进程不强停要求保持。[E006状态](project/E006_m002_slr1_congestion_attribution/experiment_status/summary.md)。E005原失败证据保留。

## 核心工程

- [软件：算法、整数参考、评估入口](project/software/README.md)
- [硬件：RTL、Host、测试与构建入口](project/hardware/README.md)
- [真实项目对话](agent/work_chats.md)
- [当前目标](goal/goal.md) / [整理结果](results/missions/M001_summary.md)

旧工程 `/home/user/EDA-202/zhuowenjun/ScaleLLM` 完整只读保留。E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。[当前合同](mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)、[E005结果](project/E005_m002_optimized_implementation/experiment_results/summary.md)、[主控审核](results/reviews/SM009.md)。

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-16T18:03:21.595393+00:00。来源修订：`e54ce1e20466`。

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

[M002 · ddr_separation_and_timing_recovery](mission/M002_ddr_separation_and_timing_recovery/README.md)

合同：[原始任务定义](mission/M002_ddr_separation_and_timing_recovery/contract.md)
前置任务：[M001 · clean_project_migration](mission/M001_clean_project_migration/README.md)
唯一实现入口：[工程代码](project)

## 最新执行报告

| 职责 | 当前任务 / 阶段 | 执行状态 | 上报时间 | 下一步 / 阻塞 |
| --- | --- | --- | --- | --- |
| 项目主控与架构评判 | 完成项目主控对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.081240+00:00 | 本轮整理交付后由用户决定下一步，不自动恢复硬件任务  |
| 工程实现与验证 | 完成工程实现对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.232249+00:00 | 迁移后不自动综合、仿真、实现或上板  |
| 研究探索与瓶颈分析 | 完成研究探索对话的只读初始化与绑定 初始化完成，等待用户后续任务 | completed | 2026-10-14T11:36:54.365918+00:00 | 后续讨论算法贡献、系统瓶颈与可证伪候选，不继承旧优化授权  |
| m002_rtl_repair | SM006 AT005 OPT reset CDC精确增量只读核查 R005 §7完成：2条CDC11与2条CDC10 source变化已定位；HostSplit精确consumer/极性预期已交付 | completed | 2026-10-15T06:11:22.942903+00:00 | 等待父派发新AT实际pin/全链/consumer证据的有界复核；安全资格OPEN，不扩展扫描/EDA  |
| m002_host_repair | SM003 Host布局与生命周期修复 106项CPU回归及独立只读审核已交付 | completed | 2026-10-14T23:55:43.097917+00:00 | 由父主控整合R002/R003验证  |
| m002_build_verify | SM010/E006归因与SM011/E007后继实现入口 E007源准备与独立集中审通过；E006原core_other查询继续 | running | 2026-10-16T18:03:21.244670+00:00 | 保持E006；真实热点/端点归因与终态收尾、锁释放后串行E007同会话原生资格及完整实现  |
| m002_physical_architecture_review | SM011/E007 集中入口修复独立复核 F01–F06/N01–N02 源码准备审核通过；最终 manifest 236718ab，原生资格与物理结果仍 NOT_RUN | completed | 2026-10-16T18:03:20.733417+00:00 | 按原合同等待真实 E006 归因/收尾与单 EDA 资源释放；实际阶段证据到达后复用 A007 有界审核  |
| m002_rtl_routability_explorer |   | 未登记 | 未登记 |   |
| m002_routability_rtl_implementation | SM009/E005/R001三RTL实现与两功能TB及原证据解释交付完成 Attention AT001和MLP AT003功能PASS；生产三RTL正式冻结 | completed | 2026-10-16T00:49:14.038166+00:00 | A006新综合实核48/32边界、fanout/负载与物理结果；A009按实际消息配合，不热改冻结源  |

## 当前证据范围（来自负责人概览，截取）

# ScaleLLM：审核总览

SM011/E007已获用户“进行针对性优化后开启下一轮implementation”授权，正在准备输入bank与MLP capture/Hadamard/四量化器成组迁往SLR2的工程入口，实际EDA尚未启动。[执行合同](mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)、[E007状态](project/E007_m002_slr2_input_locality_implementation/experiment_status/summary.md)。前置SM010/E006只读诊断继续，已核当前MLP为SLR1主要贡献者、候选规模与职责；热点/连接及真实收尾待完成，单EDA资源未释放。[E006状态](project/E006_m002_slr1_congestion_attribution/experiment_status/summary.md)。

以下为已结束的E005基线及其验收限制。

E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。

当前基线为VCU118 / xcvu9p-flga2104-2L-e、Vivado2025.2、core100MHz与双DDR UI200MHz；Attention→DDR0、MLP→DDR1。Hadamard、ScaleCode、format05、数值与Host ABI保持。唯一实现入口是project/hardware与project/software。

| 已核事实 | 判断 |
| --- | --- |
| Attention与Gate/Down定向差分及独立oracle通过；80局部控制在实际网表落实 | 只覆盖已执行局部测试，不代表全系统或板级功能验收 |
| 同physopt阶段LUT814935→801751、CLB站点99.11%→97.31%、setup WNS−1.290→+0.103ns | 资源和布线前setup改善；hold WHS−0.695ns仍失败 |
| 同route Phase9重叠节点245279→1148579，拥塞失败信号248289→758463 | 本次组合未合法布通，关键失败指标恶化；两种计数单位不同 |
| 新SLR0/1/2 CLB99.00%/99.85%/93.07%；Gate1917跨SLR叶pin，Attention同SLR仍大跨度 | 局部拥挤和连接跨度仍是实际风险；尚不能分离RTL与SSI布局的因果贡献 |

详细数值与原报告见[E005结果](project/E005_m002_optimized_implementation/experiment_results/summary.md)，阶段内部审核见[SM009](results/reviews/SM009.md)。R006旧48窗映射已测，固定窗口原生拥塞为UNAVAILABLE；实际资源占用不能替代拥塞等级。新最坏12峰行→10区域已在各自place/physopt实际测量，全部SLR1且SLICE站点均有primitive占用；不等于LUT/FF/BEL槽全部满。原48行保留，其他36非峰行未逐区测量，10区重叠不累加。

当前合法routed时序、正式CDC/reset/release/transaction与外部IO安全、端到端数值和板级验收均未完成。失败图时序不作签核；用户结果审核尚未记录。无bitstream、板卡、GPU、PPL/ACC。

前置历史见[M002阶段报告](results/missions/M002_summary.md)和[M001整理报告](missions/M001_

（摘录截断；完整记录见链接。）

[完整概览及审核来源](results/overview.md)

## 最近讨论

- [C001 · M001 初始化通信核验，非工程实验任务。请确认你能读取新根目录及当前仅整理、不改旧工程、不运行 EDA/GPU/板卡的边界。](communication/C001_M001%20%E5%88%9D%E5%A7%8B%E5%8C%96%E9%80%9A%E4%BF%A1%E6%A0%B8%E9%AA%8C%EF%BC%8C%E9%9D%9E%E5%B7%A5%E7%A8%8B%E5%AE%9E%E9%AA%8C%E4%BB%BB%E5%8A%A1%E3%80%82%E8%AF%B7%E7%A1%AE%E8%AE%A4%E4%BD%A0%E8%83%BD%E8%AF%BB%E5%8F%96%E6%96%B0%E6%A0%B9%E7%9B%AE%E5%BD%95%E5%8F%8A%E5%BD%93%E5%89%8D%E4%BB%85%E6%95%B4%E7%90%86%E3%80%81%E4%B8%8D%E6%94%B9%E6%97%A7%E5%B7%A5%E7%A8%8B%E3%80%81%E4%B8%8D%E8%BF%90%E8%A1%8C%20EDA_GPU_%E6%9D%BF%E5%8D%A1%E7%9A%84/thread.md) — 已关闭

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
