## 核心工程

- [软件：算法、整数参考、评估入口](project/software/README.md)
- [硬件：RTL、Host、测试与构建入口](project/hardware/README.md)
- [真实项目对话](agent/work_chats.md)
- [当前目标](goal/goal.md) / [整理结果](results/missions/M001_summary.md)

旧工程 `/home/user/EDA-202/zhuowenjun/ScaleLLM` 完整只读保留。M002快速验证、新工程正式综合及物理入口适配已完成。E003完整implementation自然结束，因拥塞和节点重叠未合法布通；[E004详细优化分析](project/E004_m002_routability_optimization_analysis/README.md)现已完成并通过内部独立审核，见[方案](project/E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)。用户现已授权[E005优化与新implementation](project/E005_m002_optimized_implementation/README.md)，按[当前合同](mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)完成局部功能与入口验证，新create成功，正式新综合自然完成、80局部控制已核，恢复父链已绑定，原生OPT成功、POST入口自然失败，198项入口回归通过，当前CDC身份适配219项回归通过，AT003完整place/physopt POST已通过并自然退出0，最终父链合格；AT004已从新physopt DCP实际启动原生Default route，原生Phase9合法布通失败（1148579重叠节点、758463拥塞失败信号），已自然native/监督1退出、无强停/残留且144冻结输入保持，失败现场已保全；R006/AT002双phase只读补采已自然0结束，AT003已于14:46:16 UTC实际启动新峰窗口映射补齐，最终整合待完成；布线前setup/PW通过而hold失败，placed拥塞峰Level6；实际route初始Global/Short及Timing拥塞Level7，阶段不同不能直接比较；布通与时序目标待新结果。

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-16T14:50:41.501559+00:00。来源修订：`c9b5b8efc301`。

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
| m002_build_verify | SM009/E005 R006新最坏区域只读映射 AT002双phase自然0/0及20核验通过；AT003已实际原生打开closed place DCP | running | 2026-10-16T14:48:27.574563+00:00 | 仅提取每phase12峰行对应10NW区域；完整自然终态/144freeze/DCP/资源/进程锁核验后提交工程总报告  |
| m002_physical_architecture_review | SM009/E005 R006 AT002双phase与自然终态独立审核 §46完成：physopt与placed实际同值、自然0/0、144freeze/2DCP/资源/原进程及锁闭合；AT003新峰映射待实际结果 | completed | 2026-10-16T14:50:41.152729+00:00 | 按AT003实际phase/terminal消息复用本A007续审，关闭12峰行/10区域覆盖后最终总交付  |
| m002_rtl_routability_explorer |   | 未登记 | 未登记 |   |
| m002_routability_rtl_implementation | SM009/E005/R001三RTL实现与两功能TB及原证据解释交付完成 Attention AT001和MLP AT003功能PASS；生产三RTL正式冻结 | completed | 2026-10-16T00:49:14.038166+00:00 | A006新综合实核48/32边界、fanout/负载与物理结果；A009按实际消息配合，不热改冻结源  |

## 当前证据范围（来自负责人概览，截取）

# ScaleLLM：审核总览

SM009/E005局部功能与179入口检查通过，新create及正式新综合原生自然完成。新网表80个局部控制逐项通过，LUT较同阶段E002减少12813至828763（70.10%）。原监督UNKNOWN及约34分57秒资源观测缺口保留，真实wrapper退出0；恢复closure及342输入/45DCP已绑定，补充164项CPU通过；新物理R004/AT001原生OPT成功、新opt.dcp已保存，04:15:48 UTC因显式debug入口缺失而POST自然失败；198项入口回归通过，当前CDC身份适配219项回归通过，AT003完整place/physopt POST已通过并自然退出0，最终父链合格；AT004已从新physopt DCP实际启动原生Default route，原生Phase9合法布通失败（1148579重叠节点、758463拥塞失败信号），已自然native/监督1退出、无强停/残留且144冻结输入保持，失败现场已保全；R006/AT002双phase只读补采已自然0结束，AT003已于14:46:16 UTC实际启动新峰窗口映射补齐，最终整合待完成；布线前setup/PW通过而hold失败，placed拥塞峰Level6；实际route初始Global/Short及Timing拥塞Level7，阶段不同不能直接比较。placed hold仍FAIL、正式CDC/reset安全OPEN，尚无route完成结果。详见[E005状态](project/E005_m002_optimized_implementation/experiment_status/summary.md)。

SM008/E004详细优化分析已完成并通过内部独立审核；执行completed，候选收益inconclusive。已取得只读physopt原生证据并形成[优化方案](project/E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)：Attention固定slot写入48个局部边界、MLP32个同拍输出CE及SSI_SpreadSLLs布局；失败取证和生产参数功能验证列下一阶段必做。唯一诊断自然exit0，原DCP未改，无活动EDA。本轮未实施优化或运行新综合/place/route；[审核范围](results/reviews/SM008.md)保留help、无效BEL直方图与负载细分缺口。以下为E003已结束基线。

前置基线为M002/SM007/E003完整implementation尝试。本轮完整implementation尝试已自然结束，执行FAILED；place/独立physopt命令、DCP和完整POST通过，R003/AT001 route实际19065秒后于22:45:40 UTC返回Tcl1。Phase9合法布通FAIL：245279重叠路由节点、248289拥塞失败信号（不同指标）。22:45:51 UTC监督/driver自然结束，stop_reason=null，无时间或资源终止，六个原进程退出且单EDA锁释放。没有生成route DCP/完整route_status/正式routed时序/POST；最后有效恢复点是AT002 physopt.dcp。原失败保留，无新EDA尝试，未改变算法/RTL/XDC/接口/时钟/默认策略。 用户的[持续执行补充](mission/M002_ddr_separation_and_timing_recovery/full_implementation_continuation_2026-10-15.md)优先于原启动时限，算法/RTL/XDC/接口/时钟保持。

新完整POST的64文件封闭记录、actual reset结构/fanout、8条CDC限定分类、新未分类0及内部时钟覆盖已取得；主控核阶段facts六项小证据身份一致。正式physopt时序WNS−1.290/TNS−762.165ns、setup980；WHS−0.620/THS−2150.556ns、hold33141，仍FAIL。setup改善0.

（摘录截断；完整记录见链接。）

[完整概览及审核来源](results/overview.md)

## 最近讨论

- [C001 · M001 初始化通信核验，非工程实验任务。请确认你能读取新根目录及当前仅整理、不改旧工程、不运行 EDA/GPU/板卡的边界。](communication/C001_M001%20%E5%88%9D%E5%A7%8B%E5%8C%96%E9%80%9A%E4%BF%A1%E6%A0%B8%E9%AA%8C%EF%BC%8C%E9%9D%9E%E5%B7%A5%E7%A8%8B%E5%AE%9E%E9%AA%8C%E4%BB%BB%E5%8A%A1%E3%80%82%E8%AF%B7%E7%A1%AE%E8%AE%A4%E4%BD%A0%E8%83%BD%E8%AF%BB%E5%8F%96%E6%96%B0%E6%A0%B9%E7%9B%AE%E5%BD%95%E5%8F%8A%E5%BD%93%E5%89%8D%E4%BB%85%E6%95%B4%E7%90%86%E3%80%81%E4%B8%8D%E6%94%B9%E6%97%A7%E5%B7%A5%E7%A8%8B%E3%80%81%E4%B8%8D%E8%BF%90%E8%A1%8C%20EDA_GPU_%E6%9D%BF%E5%8D%A1%E7%9A%84/thread.md) — 已关闭

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
