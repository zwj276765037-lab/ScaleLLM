# SM009 / E005 最终内部审核

execution：本轮A007审核及既定物理比较补证据completed；工程已执行功能、新综合、place／独立physopt和一次完整Default route，route自然失败，实验执行failed。verdict：局部功能保持、结构落实、资源及布线前setup改善有支持；本次组合未实现合法布通，末期物理结果较E003恶化，单项方法因果inconclusive。applicability：VCU118／xcvu9p-flga2104-2L-e／Vivado2025.2、当前冻结RTL／约束及实际父DCP。review：A007独立内部审核已完成并实际交付主控／A006；不是用户验收，M002全局目标未完成。

本轮同时改变Attention固定slot写入结构、Gate／Down同拍payload CE及SSI_SpreadSLLs布局。功能与结构收益成立，但“本轮方案足以使当前设计合法布通”的目标未达成；无法据单次组合结果分别判定某项RTL或SSI策略有效／无效，也不能推广成该架构永远不可布。

## 已支持的收益与实际代价

受影响局部功能测试采用冻结旧版逐周期差分及独立oracle。Attention通过1,265,488周期、1,263,504检查及192中断；Gate S24／M2与Down S32／M1分别通过4821／2477周期、98／49输出。原异步复位、clear、stall、同拍消费／补入、tail及错误用例保持，有限测试不等于全系统或形式证明。[功能审核§5–8](architecture_review.md)

新综合网表及place／physopt真实图保留48×256 FDCE/CE、16×384 FDRE/CE及16×512 FDRE/CE，80个driver的类型、INIT、保护属性与连接成立；不是仅在RTL里命名了80个边界。综合LUT841576→828763，减少12813。[综合事实](synthesis_stage_review_facts.json)

下表严格比较E003与E005各自的独立physopt阶段；新Default physopt实际仅25秒，并明确跳过setup优化、未修改网表，收益属于整个新组合。

| 指标 | E003 physopt | E005 physopt | 结论 |
| --- | ---: | ---: | --- |
| CLB LUTs | 814935 | 801751 | −13184 |
| CLB Registers | 1019698 | 1017050 | −2648 |
| CLB站点占用 | 146472／99.11% | 143802／97.31% | 减少2670站点，仍很满 |
| BRAM／URAM／DSP | 941／752／5451 | 941／752／5451 | 未减少 |
| SLLs Used | 18282 | 18983 | 增加701，非目标网跨SLR pin数 |
| WNS／TNS，ns | −1.290／−762.165 | +0.103／0 | 布线前setup通过 |
| WHS／THS，ns | −0.620／−2150.556 | −0.695／−2145.408 | hold仍失败，最坏值变差 |
| setup／hold失败端点 | 980／33141 | 0／30885 | 不能据setup通过宣称整体时序通过 |

新SLR0／1／2的CLB占用分别99.00%／99.85%／93.07%。SLL使用从SLR2↔1减少962，但SLR1↔0增加1663。新旧最坏setup端点也不同，+1.393ns不能描述成同一条路径的优化幅度。[完整physopt审核](AT003_completed_physopt_POST_parent_review_evidence.json)、[阶段解释§29–34](architecture_review.md)

## 完整route反证了本次成功目标

| 同阶段原生指标 | E003 | E005 |
| --- | ---: | ---: |
| Phase9重叠路由节点 | 245279 | 1148579 |
| 因拥塞失败的signals | 248289 | 758463 |
| 末期North／South Max Cong，% | 85.471／86.437 | 116.672／100.013 |
| 末期East／West Max Cong，% | 86.551／87.3848 | 102.451／112.353 |
| 四方向effective congestion level | 6 | 7 |

节点与signals是不同单位；末期Max Cong也不同于placed Level6或初始%Tiles。新route_status为routable2031772、fully_routed1273309、routing errors／conflicts各758463，原生明确not legally routed。Phase8连通统计零未布／部分布线不能推翻Phase9合法性失败。[同阶段证据](AT004_phase9_failure_same_stage_review_evidence.json)

失败图诊断WNS−13.528ns／TNS−1920757.000ns，WHS−0.258ns／THS−468.768ns，PW也失败；非法图上的“Routed”报告标题不是正式签核，且旧E003没有同类完整失败图报告可作delta。失败DRC的RTSTAT-13明确跳过部分路由状态检查。此次更早以失败结束，不是成功布线性能收益。[失败终态审核](AT004_natural_failure_terminal_review_evidence.json)

原错误、failed DCP及五项失败取证保存完整；成功POST和成功父链拒收成立。route与取证自然退出1，无墙钟、无输出或资源强停。144输入保持，进程／锁自然闭合已核；不能将结果归因为人为提前停止。[冻结与资源审核](AT004_terminal_facts_resources_freeze_crosscheck.json)

## 已定位的物理事实与尚未确定的原因

1. **站点接近填满，热点资源共存。** 总CLB仍97.31%，SLR1为99.85%；旧固定窗3／7／10中distinct occupied SLICE为3050/3051、3002/3003、682/684。这些是实际站点占用，不是LUT利用率，也不是拥塞数值。是否因控制兼容性、SRL／FF打包、硬核列布局或数据互联共同形成局部压力，现有证据尚未分离。AT003各自closed placed／physopt的新峰12行→10区域均已独立实测：全部site在SLR1，每区2944–3072个SLICEL/M site全occupied，RAMB36 site也各全occupied，DSP／URAM仍有部分容量。10区两两重叠，不可相加；occupied仅指site至少有一个primitive，不等于所有LUT／FF／BEL槽全满。该数据将局部密度风险定位到SLR1，但未证明唯一因果；physopt实际资源／连接／tile名单与placed一致，双phase与自然终态已核。见[新峰placed审核](R006_AT003_place_new_peak_review_evidence.json)、[physopt审核](R006_AT003_physopt_new_peak_review_evidence.json)。
2. **局部CE在逻辑上拆分，物理局部性仍不充分。** 各自closed place／physopt实际测得input跨SLR leaf pin0、Gate1917、Down0，上游13。Gate五行driver均在SLR1，row2／4／6／7各有384个负载在SLR0，row5有381个；79组负载单SLR只有75组源相对cross0。input即使全在SLR2，每net负载包络仍X跨度59–68、Y186–192。跨度不是实际线长／延迟，跨SLR pins不是SLL导线或拥塞失败数，也缺旧E003同口径数据，不能补造“跨SLR改善幅度”。
3. **全局数据互联与局部控制贡献未区分。** 失败top10节点覆盖MLP、Attention、tensor及DDR互联，只是工具选出的局部样本。旧capture_index名字消失不证明原瓶颈已解决，新两个write-enable名字出现也不证明它们是全局根因。48个新最坏行与旧参考位置不同；旧窗口未进入新最坏列表不等于改善或拥塞清零。
4. **布线前估计与实际路由存在明显落差，hold仍是独立问题。** 预布线setup+0.103ns余量很小，route失败图出现大量setup违例；这说明本次route未能实现布线前的setup估计，未证明某单网导致全局失败。Default physopt未实际修复hold，不能把它的成功退出当收敛。正式CDC/reset/release/transaction、外部IO与板级安全也继续OPEN。

上述控制、层次和旧48窗结果均来自各自DCP实际查询；AT002两phase各60query0且输出同值，4原进程及锁／冻结收尾已核。[placed审核](R006_AT002_place_supplement_review_evidence.json)、[physopt与终态审核](R006_AT002_physopt_terminal_review_evidence.json)。固定窗口congestion API全为UNAVAILABLE，不能用site资源占用代填。

## 后续可证伪方向（供下一合同选择，本轮不执行）

| 要区分的假设 | 最小有区分力的下一步 | 什么结果会削弱该假设 |
| --- | --- | --- |
| SSI分布策略是本次恶化的主要因素 | 固定本轮综合网表／约束／工具，先只改变place directive，保留统一资源与目标位置／跨SLR口径，再按既定验收检查真实route | 同网表改用对照布局仍出现相近失败，或目标局部性改善而全局冲突不减；不能凭placed WNS单判 |
| Gate源与负载跨SLR或input组内展宽是主要控制瓶颈 | 在精确目标组上提出单一、可测的局部性改动；同拍语义与资源约束保持，复测driver-relative cross及位置，再看完整失败信号／合法性 | 目标cross或跨度明显改善，整体路由仍无改善；则该局部机制不足以解释主瓶颈 |
| 高占用与打包／硬核列共存导致更广的资源压力 | 依据AT003真实新峰region选择一个资源贡献明确的模块，先核精确站点／SRL／FF／互联占用与相邻可用资源，提出仅改变一项资源形态的候选 | 可用站点或所选资源压力显著改善，最终拥塞仍不减；支持继续检查连接需求而非只看容量 |
| 一项RTL改动带来的放置副作用被另一项掩盖 | 在同一布局策略下对Attention48与MLP32做有顺序的单项对照，保留独立功能与网表身份，再决定是否值得完整route | 单项对照不能复现相应资源／局部性变化，或所有组合均无合法性改善 |

这些方向按观测决定下一步，不构成无界策略／seed扫描，也不在本次失败后原样重复route。任何新增流水、数值／接口或全局验收改变须进入相应设计合同；不能用移除复位、删断言或弱化安全资格来制造通过。

## 最终证据覆盖与保留边界

R006 AT002各自closed place／physopt的控制源、跨SLR leaf pin、位置、精确层次及旧48窗已独立测量和审核。AT003在各自DCP实际测量12个方向/type峰行对应NW001–NW010，完整48原始行与来源保留；仅峰值子集声明空间覆盖，36非峰行及route末期INT热点不作额外覆盖承诺。10区两两重叠，tile并集20784；全部site映射SLR1，SLICE site全部occupied，不是全部LUT／FF／BEL容量耗尽或唯一失败原因。当前fixed-window congestion统一UNAVAILABLE，原生Level6仅为选窗来源。

AT003两phase原生分别752／758秒、各15query0；原生15:11:32 UTC、监督15:11:38.117704 UTC自然退出0，整AT1521.569428秒，无stop、cleanup或残留。300资源样本独立重算峰RSS22.821053GiB／最低MemAvailable375.171288GiB／最低disk401.564053GiB。144冻结输入、2原DCP、6归档源、2source报告及独立target保持，4原PID-start消失，单EDA锁自然释放。A007核真实文本／hash／stat／进程身份，不读取大DCP、不重跑工具。[AT003终态与范围闭合](R006_AT003_terminal_coverage_review_evidence.json)、[最终事实与目标绑定](final_internal_review_facts.json)

原综合监督UNKNOWN和2097.384826秒资源观测缺口、早期编译／入口／OPT／CDC失败及R006 AT001 pre-EDA拒绝继续保留，后续成功收尾不追溯改写。成功place／physopt POST仅支持诊断准入，8已分类Critical CDC／新增0不代表正式安全通过；外部IO缺delay、debug实际与声明时钟差异、局部枚举coverage_limited等原边界仍在。无bitstream、板卡、GPU、PPL或ACC，局部功能测试不替代全系统数值或真实DDR事务验收。

所接受的补证据义务已经完成，未发现需补采才能解释本轮结论的剩余缺项。成功合法布通、完整routed时序及正式安全验收仍未完成；后续候选需由新的明确任务选择，本轮不追加implementation或策略扫描。
