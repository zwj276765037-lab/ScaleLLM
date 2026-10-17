# E005：完整route自然失败，失败现场已保全，待补充比较

AT004于2026-10-16 13:56:35.660913 UTC自然结束，native/监督退出码均1，stop_reason=null，全部登记原进程已退出、锁实测可释放，144冻结输入未变。失败checkpoint及route_status/timing/congestion/DRC共5项保存回执均code0，原route错误随后重抛；成功route DCP、成功完整POST与父链未取得。本次总监督墙钟4小时57分44.645秒，峰树RSS27.2882GiB；与原生内部route计时及包含取证的wrapper区间分开。R006只读补采尚待实际启动，整个交付仍在进行。[自然终态事实](runs/R004/attempts/AT004_default_route/route_terminal_observation_summary.json)。

以下为历史阶段截点；当前route已闭合，不再运行。

本次Default route的Phase9合法布通检查已失败：Route35-2报告1148579个节点重叠，Route35-162报告758463个因拥塞未布通的信号；两者单位不同。旧E003同阶段分别为245279/248289，本次均更多，当前组合未达到布通目标。该历史截点的失败取证现已完成，原生/监督1自然退出；不重试相同route。[原生失败证据](runs/R004/attempts/AT004_default_route/native_route_progress_captures/capture_009_facts.json)。

以下为先前阶段截点记录，当前状态以上述失败取证为准。

13:06 UTC主控观察到Phase5.3第二轮全局迭代与Phase5拆线重布完成，13:08 UTC封存原生日志407–412行及不可变前缀。原生累计elapsed分别03:56:27/03:56:28；不是该单阶段耗时。尚无新的重叠计数、中间时序或route/监督终态，当前原进程继续后续处理。[实际阶段完成证据](runs/R004/attempts/AT004_default_route/native_route_phase5_completed_observation.json)。

已完成E003与E005相同route阶段的独立比较：两次原生初始Global/Short及Timing均Level7；新12组方向/线型统计中10组%Tiles更高、8组报告size更大，各60窗有重叠嵌套，不能求和作独立失败数。第二轮首次重叠节点旧2025963→新2472092，过程指标不是终态失败信号数。第一轮新中间WNS/TNS较旧少负4.459/394937.140ns，但两次WHS/THS均N/A；不同迭代工作及布局不能据此宣称最终时序或性能改善。当前证据不支持拥塞改善已成立，route继续，无新停点。[同阶段独立审核](runs/R005/AT004_vs_E003_route_intermediate_comparison_review_evidence.json)。

12:01 UTC新增实际过程计数：Phase5.3 Global Iteration2的重叠节点2472092，比前轮2183923增加288169。两次观测未显示重叠下降，布通风险保持；尚无新的中间时序或命令终态，不提前判失败。[本轮计数证据](runs/R004/attempts/AT004_default_route/native_route_progress_captures/capture_002_facts.json)。

先前截点：实际route完成Phase5.2 Global Iteration1并进入Phase5.3 Global Iteration2。前轮中间计数为2183923个重叠节点，最新中间WNS−13.535ns/TNS−1866986.607ns，WHS/THS=N/A；均不是终态报告，N/A不可解释为hold通过。资源与CPU正常，继续原Default route。[本次过程证据](runs/R004/attempts/AT004_default_route/native_route_iteration1_intermediate_timing_observation.json)。

SSI_SpreadSLLs布局原生返回0，耗时8387秒；新place DCP已保存，SHA32b4af05f2ba43c8f63ec8ee44f7fcd40dbc1d6f5012638d404bb0cb6678bdf2。完整placed POST通过：completed=1、diagnostic_eligible=1、gate_issues=[]、黑盒0、内部时钟覆盖完整、reset结构/fanout合格、688 BRAM时钟端点、8条已分类Critical CDC且新增未分类0。正式CDC/reset及外部IO安全仍OPEN。[完整阶段事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/completed_place_POST_independent_physopt_command_facts.json)。

独立Default physopt原生命令返回0，耗时25秒。原生日志明确setup无违例，跳过setup优化且网表未修改；不能据此宣称hold修复。新physopt DCP已保存，579969232字节，SHA766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d。[检查点事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/physopt_checkpoint_saved_observation.json)、[原生处置](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/independent_physopt_native_disposition_observation.json)。完整physopt POST已通过：BB0、COMPLETE_INTERNAL、gate_issues=[]、当前8条CDC分类/新增未分类0，正式安全OPEN。AT003于08:57:32.868921 UTC自然结束，native/监督0、stop=null、无残留，144冻结输入保持；installed parent_place实际接受。[父链资格事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/completed_physopt_POST_parent_qualification_facts.json)。

R004/AT004_default_route已于08:58:51.015791 UTC实际启动，监督器611388、leader611402。检查点恢复后，原生日志122行已实际调用route_design -directive Default，131行进入Phase1 Build RT Design；当前原生route运行中，尚无终态或routed资格。[原生启动事实](runs/R004/attempts/AT004_default_route/native_route_started_observation.json)。[真实启动](runs/R004/attempts/AT004_default_route/started.json)。

正式Physopt postPlace资源、时序12summary、80边界/14上游完整行以及48行拥塞与本次placed分别相同；整体仍hold FAIL、各类拥塞峰Level6。该等同关系来自两阶段各自实际报告，不以physopt值代填placed缺项。[physopt实际事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/physopt_timing_utilization_report_facts.json)。

以下仅为E003 placed→E005 placed同阶段比较：

| 指标 | 旧placed | 本次placed |
| --- | ---: | ---: |
| LUT | 814911 | 801751 |
| CLB站点占用 | 146472 / 99.11% | 143802 / 97.31% |
| CLB Registers（非纯FF简称） | 1019696 | 1017050 |
| SLL Used | 18263 | 18983 |
| Setup WNS / TNS (ns) | -1.819 / -818.651 | +0.103 / 0 |
| Setup失败端点 | 1014 | 0 |
| Hold WHS / THS (ns) | -0.620 / -2150.556 | -0.695 / -2145.408 |
| Hold失败端点 | 33141 | 30885 |
| WPWS / TPWS (ns) | 0 / 0 | 0 / 0 |

[资源独立核验](runs/R005/AT003_place_resource_pre_POST_review_evidence.json)、[时序独立核验](runs/R005/AT003_place_timing_pre_POST_review_evidence.json)。新SLR0/1/2的CLB占用99.00%/99.85%/93.07%，SLR1局部仍极满；SLL Used不等于目标控制网跨SLR负载或router需求。setup/PW在placed阶段通过，整体仍hold FAIL，互连仍为布线前估计；新旧global最坏setup均在PCIe→XDMA但端点不同，不能单独归因某个RTL改动。

80个实际边界全部保持48input×256FDCE/CE、16Gate×384FDRE/CE、16Down×512FDRE/CE，共26624叶pin；原生issues=[]、LOC/BEL与DONT_TOUCH存在，A007逐行核同cell/INIT/REF。14个上游源负载数/类型保持。79组负载各在单SLR，Gate row5负载在SLR0/1为381/3；精确跨SLR量仍需driver映射。Attention各组虽均在SLR2，slice包络仍Xspan59–68/Yspan186–192，不能将同SLR等同紧凑。[80边界事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/place_80_boundary_graph_facts.json)。

实际拥塞报告48行相互重叠/嵌套，Global/Long/Short最高均Level6，四个Global方向峰均6。新热点位置变化，旧48个direction/type/window精确命中0；旧固定窗当前值NOT_MEASURED，不能填0或宣称改善。仍属Placer Final Level，非fresh routed估计。[实际拥塞](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/place_congestion_report_facts.json)。当前支持资源和setup的同阶段改善、80局部控制机制保留；拥塞改善及合法布通未确立。完整placed POST现已通过；后续补充比较证据仍须在最终交付前完成。

已完成的功能、综合及恢复证据：Attention AT001与生产Gate/Down AT003局部功能PASS；新create/综合自然成功，80局部控制逐项符合预期，Synthesized LUT841576→828763，342输入/45DCP父链已绑定。[功能事实](runs/R001/rtl_functional_final_facts.json)、[综合审核](runs/R005/synthesis_stage_review_facts.json)。原综合监督UNKNOWN及2097.384826秒观测缺口保留，原wrapper真实退出0单独有据。AT001显式debug准入缺失、AT002旧CDC报告hash适配失败保留；219项入口回归通过，AT003完整debug/pre_place已通过。[入口回归](runs/R002/attempts/AT010_current_CDC_recovery_cpu/completion_facts.json)。raw debug verified0、声明300MHz/实际50MHz、vendor异常约束及外部IO缺delay继续保留；OPT aux枚举coverage_limited不可由非OPT not_limited推断消除。

调度：完整physopt POST/父链/结构/资源/约束资格已闭合，当前AT004继续一次完整Default route，负hold或Level6本身不新增停点。固定旧窗口、目标层次利用率、driver及上游负载位置/精确跨SLR比较，允许在route自然终态后从本次精确closed placed/physopt DCP按单EDA顺序补齐；仍属最终交付义务，不声称已经完成，不重做物理阶段。[报告覆盖范围](runs/R005/AT003_frozen_physical_reporting_coverage.json)。合法布通、时序及正式CDC安全独立验收；无bitstream/板卡/GPU/PPL/ACC。


最新过程风险：原生route在Phase4.2后输出Route35-447，拥塞妨碍全部网络布通，工具将优先完成布线再考虑时序优化。当前仍正常运行、无终态；这是实际route风险，不是正式失败或routed验收。[原生告警证据](runs/R004/attempts/AT004_default_route/native_route_congestion_priority_observation.json)。


实际route初始拥塞估计进一步报告Global/Short Level7（128×128）和Timing Level7；已保全4方向×3类别的12组size/%Tiles、60个实际窗口，Long未原生标level则不推断，Timing未给窗口则不补造。该值属于route初始估计，不能与placed Level6直接作增减比较。10:06 UTC观察时进入Phase5 Rip-up And Reroute/5.1.1 Update Timing；该截点无终态结论。[原始估计及窗口](runs/R004/attempts/AT004_default_route/native_initial_estimated_congestion_facts.json)。


---
Published: 2026-10-16T14:01:13.923496+00:00
Publication: P1a4be15272b14b29929efbbaa7f649eb
