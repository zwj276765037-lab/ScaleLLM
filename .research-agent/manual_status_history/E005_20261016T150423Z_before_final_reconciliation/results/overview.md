# ScaleLLM：审核总览

SM009/E005局部功能与179入口检查通过，新create及正式新综合原生自然完成。新网表80个局部控制逐项通过，LUT较同阶段E002减少12813至828763（70.10%）。原监督UNKNOWN及约34分57秒资源观测缺口保留，真实wrapper退出0；恢复closure及342输入/45DCP已绑定，补充164项CPU通过；新物理R004/AT001原生OPT成功、新opt.dcp已保存，04:15:48 UTC因显式debug入口缺失而POST自然失败；198项入口回归通过，当前CDC身份适配219项回归通过，AT003完整place/physopt POST已通过并自然退出0，最终父链合格；AT004已从新physopt DCP实际启动原生Default route，原生Phase9合法布通失败（1148579重叠节点、758463拥塞失败信号），已自然native/监督1退出、无强停/残留且144冻结输入保持，失败现场已保全；R006/AT002双phase只读补采已自然0结束，AT003已于14:46:16 UTC实际启动新峰窗口映射补齐，最终整合待完成；布线前setup/PW通过而hold失败，placed拥塞峰Level6；实际route初始Global/Short及Timing拥塞Level7，阶段不同不能直接比较。placed hold仍FAIL、正式CDC/reset安全OPEN，尚无route完成结果。详见[E005状态](../project/E005_m002_optimized_implementation/experiment_status/summary.md)。

SM008/E004详细优化分析已完成并通过内部独立审核；执行completed，候选收益inconclusive。已取得只读physopt原生证据并形成[优化方案](../project/E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)：Attention固定slot写入48个局部边界、MLP32个同拍输出CE及SSI_SpreadSLLs布局；失败取证和生产参数功能验证列下一阶段必做。唯一诊断自然exit0，原DCP未改，无活动EDA。本轮未实施优化或运行新综合/place/route；[审核范围](reviews/SM008.md)保留help、无效BEL直方图与负载细分缺口。以下为E003已结束基线。

前置基线为M002/SM007/E003完整implementation尝试。本轮完整implementation尝试已自然结束，执行FAILED；place/独立physopt命令、DCP和完整POST通过，R003/AT001 route实际19065秒后于22:45:40 UTC返回Tcl1。Phase9合法布通FAIL：245279重叠路由节点、248289拥塞失败信号（不同指标）。22:45:51 UTC监督/driver自然结束，stop_reason=null，无时间或资源终止，六个原进程退出且单EDA锁释放。没有生成route DCP/完整route_status/正式routed时序/POST；最后有效恢复点是AT002 physopt.dcp。原失败保留，无新EDA尝试，未改变算法/RTL/XDC/接口/时钟/默认策略。 用户的[持续执行补充](../mission/M002_ddr_separation_and_timing_recovery/full_implementation_continuation_2026-10-15.md)优先于原启动时限，算法/RTL/XDC/接口/时钟保持。

新完整POST的64文件封闭记录、actual reset结构/fanout、8条CDC限定分类、新未分类0及内部时钟覆盖已取得；主控核阶段facts六项小证据身份一致。正式physopt时序WNS−1.290/TNS−762.165ns、setup980；WHS−0.620/THS−2150.556ns、hold33141，仍FAIL。setup改善0.529ns/减少34个失败端点，互连仍为布线前估计；placed Level6拥塞风险和正式CDC/reset安全OPEN保留。本次完整physopt POST已通过并冻结55份阶段文件，主控核7项小证据身份一致；R003/AT001现已实际路由验证失败，完整routed产物未生成；不把诊断准入等同签核。[本次完整POST事实](../project/E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/completed_place_POST_facts.json)。

## E002 已结束阶段（E003启动前基线）

E002正式create/synth已完整完成，AT002 exit0、约114分钟、峰值进程树RSS27.06GiB。综合LUT71.18%、DSP79.69%、URAM78.33%，资源总量未超。随后OPT已将黑盒、内部缺时钟及未约束端点清零，LUT降至70.06%；未布局估计WNS+0.904ns、WHS−0.814ns，时序仍未通过。详见[E002结果](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/summary.md)。

AT008和唯一一次从完整pre_place恢复的AT009均达到各自两小时上限。AT009于11:41:11 UTC结束，124/native−15，无遗留进程；完成细化布局并进入布局后时序优化，但没有place/physopt成功回执或完整DCP，独立physopt/route未运行。原准备至回执实测由43分49.541秒降至12分28.398秒，节省31分21秒；仍不足以在该预算内完成布局。当时按E002合同停止重复place，该轮结束时无活动EDA，完整物理基线未取得。详见[终态事实](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)。

物理入口适配及完整pre_place已通过；AT011的102项CPU、AT012的19项本次测试和真实POST/父链验证均已有证据，AT012另外96项legacy仅复用。布局中间WNS−1.884ns/TNS−1349.388ns不是完成布局报告；USER_SLL_REG放置意图、BUFG插入10候选全部跳过、DDR1时钟延迟限制等已记录，完整影响待测。正式时序、reset/CDC安全及板级验收未签核。此次方法结论inconclusive，超时不等于架构被反驳。详见[E002状态](../project/E002_m002_synthesis_and_physical_baseline/experiment_status/summary.md)。

以下为E001已完成阶段证据：

[M002本轮修复与快速功能验证已完成](missions/M002_summary.md)。双逻辑权重完整保留并按引擎分离DDR，MLP数据口独立；Host地址、生命周期与layout ID检查已修复。

106项Host CPU、49项构建CPU、9项整数参考、四套定向XSim和完整board RTL展开通过；170个数值/软件文件hash保持。实际BD校验退出0，但4条地址别名critical及历史复位优先级warning保留并有范围明确的分析。

E001当时建议进入fresh synthesis，未运行正式综合/implementation/板卡；其后E002已完成上述新综合。真实互连事务、完整数值与板级验收仍有缺口，M002全局时序和部署目标未完成。[E001三摘要](../project/E001_m002_repair_quick_validation/experiment_status/summary.md)及[Q001答案](../question/Q001_M002_synthesis_readiness/answer.md)保留该阶段判断。

## 硬件事实与边界

以下是 2026-10-14 从旧工程 native025 终态文件重新读取的历史结果，不是本次重跑：

- 候选 C1-min + D0-terminal + P0 保存了 placed DCP；局部不变量及三个定向 DRC 规则通过。
- 未布线的全局 setup 从 -1.673 ns 退化到 -5.100 ns，hold 从 -0.686 ns 退化到 -3.122 ns。不能作为 routed signoff 或板级性能。
- DDR0 面向 MIG 的 AW 路径改善，但内部 FIFO/状态路径恶化；仅把末端移近 MIG 没有解决完整路径。
- 原始/监督退出码均为 1，required timing coverage incomplete；物理效果本身也未通过。27/27 CPU 测试通过仅覆盖局部脚本逻辑。
- 没有完成该候选的 implementation、route、bitstream 或上板。旧记录报告任务已停止；本轮未轮询旧进程，不把记录当新的进程存活检查。
- 完整 32 层、双 cohort、所有中间量的端到端精确验证仍有缺口，不能由有限 layer0 联合验证代替。

证据：`/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware/vivado/reports/mission0008_e2_diagnostic_native_025/worker_final_receipt.txt`、`exit.json`、`diagnostic_timing_deltas.tsv`。

## M001 历史整理结果

两路核心复制及主控静态复核已完成：software 42 个、hardware 239 个来源文件；269 个字节一致、12 个仅路径适配。所有281个源文件hash复核与初始复制快照一致。新工程约7.2 MiB磁盘占用，旧工程约60 GiB完整保留。详见 [整理结果](missions/M001_summary.md)。没有启动综合、仿真、GPU 或板卡任务。
用户最新要求取消此前绑定，只在ScaleLLM分区新建四个独立对话。已通过原生thread/start新建，核验无fork来源、无父会话、无项目/代理绑定，每个仅一轮就绪确认，普通分区列表可见。此前误建和fork入口已解除关联并归档，原有四个历史对话保留。当前入口见 [工作对话](../agent/work_chats.md)，证据见 [.research-agent/fresh_section_chats.json](../.research-agent/fresh_section_chats.json)。旧创建、修复和双向通信回执仅保留为历史证据；自动通信已停用，本次未启动硬件任务。

当前普通软件引用已切到新 software 目录，数值 golden 字节未变。大型输入和冻结历史证据仍外置；历史 bitgen 验收脚本未移植，具体原因及源路径已登记。新目录不是独立可发布的硬件包。

M001之后已转入上述M002本轮授权范围；不得恢复旧优化任务。

详细结果引用对应类别页、SM 审核和实验三份摘要。
