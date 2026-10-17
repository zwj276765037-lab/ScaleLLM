# E005：完整implementation失败，证据交付完成

**当前组合未合法布通。** R004/AT004于2026-10-16 13:56:35.660913 UTC自然结束，native/监督均1、stop_reason=null，无墙钟、无输出或资源强停。失败DCP及诊断已保存，成功route DCP、完整成功POST和成功父链未取得。R006/AT002与AT003只读补采均自然0/0完成；最后AT003于15:11:38.117704 UTC结束，实际结果和终态已通过独立审核。 实验执行记failed，方法判断inconclusive；内部复核完成不替代用户验收，M002全局目标仍未完成。

## 同阶段关键结果

| 指标与阶段 | E003 | E005 |
| --- | ---: | ---: |
| Phase9重叠路由节点 | 245279 | 1148579 |
| Route35-162拥塞失败信号 | 248289 | 758463 |
| 末期North/South最大拥塞 (%) | 85.471 / 86.437 | 116.672 / 100.013 |
| 末期East/West最大拥塞 (%) | 86.551 / 87.3848 | 102.451 / 112.353 |
| 末期四方向effective congestion level | 6 | 7 |
| physopt CLB LUTs | 814935 | 801751 |
| physopt CLB站点占用 | 146472 / 99.11% | 143802 / 97.31% |
| physopt SLLs Used | 18282 | 18983 |
| physopt setup WNS/TNS (ns) | −1.290 / −762.165 | +0.103 / 0 |
| physopt hold WHS/THS (ns) | −0.620 / −2150.556 | −0.695 / −2145.408 |

节点、信号、SLL使用和跨SLR叶pin是不同口径。两次末期拥塞threshold均0.85、窗口标签64×64，不能与placed Level6或初始%Tiles混比。新route_status为routable2031772、fully_routed1273309、errors/conflicts各758463；Phase8零未布/部分布线不能推翻Phase9合法性FAIL。[布线同阶段审核](runs/R005/AT004_phase9_failure_same_stage_review_evidence.json)、[physopt审核](runs/R005/AT003_completed_physopt_POST_parent_review_evidence.json)。

失败图WNS−13.528/TNS−1920757.000ns、WHS−0.258/THS−468.768ns、WPWS−0.537/TPWS−3.018ns仅作诊断，不是合法routed签核，也无旧E003同类完整失败图可比。失败DRC的RTSTAT-13明确指出路由不足、部分检查未运行；报告命令code0不是DRC通过。

## 功能和结构已验证到什么程度

Attention通过1265488周期差分、1263504独立slot检查、192中断/196epoch及4完整双wave映像；Gate/Down通过4821/2477周期、98/49输出及17/16非法用例。保留clear/reset、stall、尾mask、同拍消费/补入和错误语义。仅覆盖实际局部测试，不代表全系统数值、DDR事务或板级验收。[功能事实](runs/R001/rtl_functional_final_facts.json)。

新综合80局部边界落实，综合LUT841576→828763（−12813），342输入/45DCP来源绑定。place/physopt实际保持48×256 FDCE/CE、16×384 FDRE/CE、16×512 FDRE/CE，共26624目标叶pin，driver属性与连接通过。BRAM941/URAM752/DSP5451未变。新Default physopt因setup非负跳过setup优化且未改网表，不能把组合收益单独归因于该命令。[综合审核](runs/R005/synthesis_stage_review_facts.json)。

## 物理补采给出的定位

各自closed place/physopt DCP实际测得Attention/Gate/Down的driver-relative跨SLR叶pin分别0/1917/0；Gate第2/4/6/7行各384、第5行381，源均SLR1。14条上游net共389叶pin，其中跨SLR13。79组负载在单SLR，只有75组源相对跨SLR为0；不能把Gate row5负载381/3直方图误算为仅3跨区。Attention同SLR负载仍有Xspan59–68/Yspan186–192，属于大范围分布。没有旧E003同口径叶pin基线，不能声称跨区改善。

新SLR0/1/2的CLB占用为99.00%/99.85%/93.07%。旧48固定窗已实际映射设备GRID/tile/site/SLR；优先窗3/7/10/23的占用SLICE/容量为3050/3051、3002/3003、682/684、3009/3136。新峰在各自place/physopt报告中保留全部48原始行，仅12个方向/type峰行对应10个区域完成实际空间测量；两阶段结果一致，10区域全部SLR1，每区2944–3072个SLICE站点均有primitive占用。其余36非峰行和route末期INT热点不属于该空间测量范围。全部10区两两重叠；占用不代表所有LUT/FF/BEL槽满，也不证明唯一失败原因。 这些是站点占用，不能等同LUT容量或原生拥塞等级；重叠区域不相加，attached hierarchical net segments也不是穿越边界数。

精确input/Gate/Down层次Total LUT6422/7024/5216、SRL0/2304/3075、FF12383/6245/8282，仅适用于所查层次。固定窗口原生拥塞测量统一记UNAVAILABLE，未填零；56个既有LOC仅映射E005的placed driver，不是E003跨SLR基线。[AT002 placed审核](runs/R005/R006_AT002_place_supplement_review_evidence.json)、[physopt和终态审核](runs/R005/R006_AT002_physopt_terminal_review_evidence.json)。[新峰placed审核](runs/R005/R006_AT003_place_new_peak_review_evidence.json)、[physopt审核](runs/R005/R006_AT003_physopt_new_peak_review_evidence.json)、[终态和覆盖审核](runs/R005/R006_AT003_terminal_coverage_review_evidence.json)。

## 证据完整性与边界

失败checkpoint为[route_failed.dcp](../../hardware/vivado/reports/m002_E005_R004_AT004_default_route/route_failed.dcp)，779113008字节，SHA256 `6d1cf5ef3fea7b8ca0ab7ba27aaa61383ce487a640bcb63248cb6a9af7009590`。checkpoint/status/timing/congestion/DRC五项取证均code0，原route错误正确重抛，失败产物拒绝成功父链。144冻结输入未变、原PID-start均退出、结束锁探测已取得并释放。3515样本独立复算：峰RSS27.2882GiB、最低MemAvailable385.2928GiB、最低磁盘404.3942GiB。[布线终态](runs/R004/attempts/AT004_default_route/route_terminal_observation_summary.json)、[独立交叉核查](runs/R005/AT004_terminal_facts_resources_freeze_crosscheck.json)。

内部Routing Task15510.3秒、原生命令含失败DRC15782秒、外层含1449秒取证共17233秒、整AT17864.645秒分别记录；较短失败耗时不是布通性能收益。R006/AT002各60查询成功并自然0/0退出；AT003各15查询成功、21项工程终态检查通过，144输入、两个DCP、归档源、原报告及独立目标保持，原进程均退出且锁释放；300采样峰RSS22.8211GiB、最低MemAvailable375.1713GiB、最低磁盘401.5641GiB。 两次只读补采均不重放物理阶段或写checkpoint。[补采批次](runs/R006/run.md)。

原综合监督UNKNOWN及2097.384826秒观测缺口保留；原生和wrapper0由恢复链独立核实。早期功能/入口/OPT/CDC失败和R006/AT001 pre-EDA拒绝均独立保留；AT002空new_peak_source_reports仅不适用，不作为新峰测量证据。正式CDC/reset/release/transaction与外部IO安全仍OPEN；8已分类Critical CDC/新增0仅用于诊断准入。raw debug verified0、声明300MHz/实际50MHz、vendor XPM例外、外部input1/output2缺delay及OPT辅助coverage_limited保持。

本轮支持局部功能、结构和资源/setup收益，但实际拥塞与合法性结果恶化。单次组合不能区分RTL与SSI布局原因，top10失败节点也不能代表全局分布。下一次应优先用受控对照区分布局策略和热点资源/连接局部性，不能据本轮承诺布通或原样重复route。[工程最终报告](engineering_final_report_2026-10-16.md)、[最终独立内部审核](runs/R005/final_internal_review.md)、[主控审核](../../../results/reviews/SM009.md)。


---
Published: 2026-10-16T15:16:56.476634+00:00
Publication: Pc1f7cce8522f40539c3c16660e923a0e
