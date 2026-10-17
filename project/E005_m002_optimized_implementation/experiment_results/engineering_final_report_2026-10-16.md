# SM009 / E005 工程最终报告

本轮优化、新综合、完整implementation及合同比较补证已执行至自然终态，当前无活动EDA。候选仍未合法布通：R004/AT004 Default route因拥塞和节点重叠自然失败；新place/physopt与完整POST父链保留，失败现场已取得，R006两批只读补采已完成并获独立复核。工程执行结束不代表时序收敛、正式安全或可用bitstream。

执行依据为[SM009合同](../../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)，合同SHA256为`0de96ef2e741f3fb18005af5d4fed2137b4a15a71915f2d490bbb6d7e1e529f6`。本报告由A006工程实验负责；A009负责RTL/功能解释，A007独占R005独立审核，主控负责全局三摘要/mission/results及最终判断。

## 实施与验证范围

本次实施Attention48个固定slot局部译码、MLP Gate/Down各16个同拍输出CE，采用新SSI_SpreadSLLs布局，独立physopt及router保持Default。算法Hadamard/ScaleCode、format05、位宽/舍入、HostABI、双DDR角色及core100/UI200+200MHz保持。旧工程只读，未运行bitstream、板卡、GPU、PPL或ACC。

局部Attention/Gate/Down差分、独立oracle、背压/中断及非法输入覆盖见[功能最终事实](runs/R001/rtl_functional_final_facts.json)。该验证范围不替代完整系统数值、DDR事务或板级验证。新综合网表80边界、342源/45DCP父链已经核实，见[综合独立审核](runs/R005/synthesis_stage_review_facts.json)。

原生OPT成功后POST准入失败、后续CDC来源适配失败均保持独立AT；当前窄恢复198项CPU回归、CDC适配219项回归、旧CPU终态schema窄修23项及新峰目标准备9项CPU检查分别保留，不相加为独立用例总数。成功综合、OPT、debug、place及physopt没有重跑，失败route没有重复。

## 完整implementation结果

R004/AT003的新place及独立Default physopt均自然原生0，完整POST与诊断父链通过。physopt明确setup非负、跳过setup优化且未改网表；不能将整个组合结果归因于这次physopt。

| 指标 | E005 physopt，布线前估计 | E005失败route诊断图 |
| --- | ---: | ---: |
| WNS / TNS (ns) | +0.103 / 0 | −13.528 / −1920757.000 |
| WHS / THS (ns) | −0.695 / −2145.408 | −0.258 / −468.768 |
| Hold failing endpoints | 30885 | 13151 |
| WPWS / TPWS (ns) | 0 / 0 | −0.537 / −3.018 |

新physopt资源为CLB LUTs801751、CLB Registers1017050、CLB143802/97.31%，SLR1 CLB99.85%、SLL18983，BRAM941/URAM752/DSP5451。CLB Registers不混称纯FF。布线前setup/PW通过但hold FAIL；失败route不合法，表中阶段不同，不据此推导route时序改善或routed签核。见[完整physopt父链](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/completed_physopt_POST_summary_facts.json)和[正式时序资源事实](runs/R004/attempts/AT003_current_CDC_bound_OPT_place_physopt/physopt_timing_utilization_report_facts.json)。

AT004原生Phase9明确1148579个重叠节点、758463个因拥塞未布通信号，二者单位不同。与旧E003同阶段的245279个节点、248289个信号相比均增加；四方向末期Max Cong均上升、有效峰6→7。两项RTL与布局指令同时改变，一次组合实验不能分离孤立因果或判定方法普遍性。比较复用[A007同阶段证据](runs/R005/AT004_phase9_failure_same_stage_review_evidence.json)，没有再次抽取旧基线。

失败route_status明确routable2031772、fully routed1273309、routing errors/resource conflicts各758463；未显式报告unrouted/partially routed，不补0。失败DRC含RTSTAT-13并说明RTSTAT-*未运行，report命令0不代表DRC通过。失败congestion文件仅含Placer Final24行和Router Initial21行，没有Router Final表；末期拥塞依据原生日志，不以文件生成时间改称最终拥塞。

AT004于2026-10-16T13:56:35.660913Z自然失败闭合，Tcl/Vivado/worker/监督均1，stop_reason=null，无时间或资源强停。checkpoint/status/timing/congestion/drc五项失败capture均原生0，原错误随后正确重抛。failed DCP779113008bytes、SHA256`6d1cf5ef3fea7b8ca0ab7ba27aaa61383ce487a640bcb63248cb6a9af7009590`，为diagnostic_failed_route，不进入成功route父链；成功route DCP/完整POST未取得。原6个PID/start均不在，锁释放，144生产输入保持。见[工程终态小事实](runs/R004/attempts/AT004_default_route/route_terminal_engineering_summary.json)。

原生内部total15510.3秒、route含自动DRC15782秒、外层Tcl含1449秒失败capture共17233秒、整AT17864.645122秒为不同时间范围，不直接混比，较短失败耗时不是布通性能收益。

## R006：实际控制位置、旧窗口与新峰区域

AT001在Vivado前因两条旧CPU记录缺state字段被拒，原失败保留。窄修仅绑定两条原始终态、双hash及PID/start，其他running/UNKNOWN/一般缺state仍拒。后续AT002和AT003均为新尝试，各自先后打开精确closed place与physopt DCP，只读查询，不写checkpoint或执行物理命令。

AT002于14:45:12.436500Z自然native/监督0结束，两phase各60项query均0。80边界、94net、97个逐SLR位置包络、14上游源、56原placed LOC实际device映射、48旧窗及三个精确目标层次齐全。原placed LOC使用同part实际device映射，没有替换成physopt驱动位置。physopt与placed的上述数据一致；56mapping仅phase标签不同。见[AT002终态](runs/R006/attempts/AT002_closed_place_physopt_readonly/readonly_terminal_summary.json)及[独立复核](runs/R005/R006_AT002_physopt_terminal_review_evidence.json)。

| 边界 | nets | CE leaf pins | 源相对跨SLR leaf pins |
| --- | ---: | ---: | ---: |
| Attention input | 48 | 12288 | 0 |
| Gate | 16 | 6144 | 1917 |
| Down | 16 | 8192 | 0 |

Gate rows2/4/6/7各384、row5为381个跨SLR叶引脚，driver在SLR1，对应负载在SLR0。14上游net共389个leaf pins，其中13个跨SLR。79组负载各在单一SLR，与75组源相对cross0为不同统计；不能用负载直方图代替driver-relative计算。Attention同SLR负载的Xspan59–68/Yspan186–192，不能据无跨SLR便认定局部紧凑。

| 精确目标层次 | Total LUTs | Logic LUTs | SRLs | FFs（原列） | RAMB36 / RAMB18 |
| --- | ---: | ---: | ---: | ---: | ---: |
| input | 6422 | 6422 | 0 | 12383 | 42 / 2 |
| Gate repack | 7024 | 4720 | 2304 | 6245 | 0 / 0 |
| Down repack | 5216 | 2141 | 3075 | 8282 | 0 / 0 |

三者LUTRAM/URAM/DSP均0。原生hierarchy重复root/parent行不相加；逐表说明见[placed独立审核](runs/R005/R006_AT002_place_supplement_review_evidence.json)。

**AT002空new_peak项为N/A。** 其terminal facts中的new_peak_source_reports为空字典，all(empty)=true只表示该尝试不适用该检查，不能作新峰已测证据。旧48窗aggregate与tile名称不足以推出新峰区域。原facts不改写，由AT003独立补齐原合同义务。

**AT003映射范围为12峰行/10区域子集。** 各phase保留新拥塞报告全部48行/45unique区域，仅映射12个方向/type峰Level6记录对应的NW001–NW010十个区域，其余36行未逐区测量。原行号/source index、端点和区域关联与[独立固定目标](runs/R005/R006_current_peak_window_targets.json)精确一致；没有重80/94net/层次或物理阶段。

AT003的place/physopt各15项query全0，原生phase分别752/758秒。各自实际DCP的10区域资源/连接/10个tile列表完全一致。所有区域site均在SLR1；SLICEL/M site容量为2944（7区）、3008（NW003）、3072（NW006/NW007），各区occupied同值。此为站点已有primitive占用，不代表所有LUT/FF/BEL容量100%，也不是唯一根因证明。各区primitive54671–56489、attached hierarchical net segments235599–323764。10个tile列表unique union20784，45对区域均重叠，不相加资源总数；附着segments不是边界crossings。见[新峰placed事实](runs/R006/attempts/AT003_new_peak_windows_readonly/place_readonly_closed_phase_summary.json)、[新峰physopt事实](runs/R006/attempts/AT003_new_peak_windows_readonly/physopt_readonly_closed_phase_summary.json)及[A007实际双phase复核](runs/R005/R006_AT003_physopt_new_peak_review_evidence.json)。

**固定窗口拥塞仍为UNAVAILABLE。** 新旧区域查询实际提供GRID/tile/site/SLR资源与连接分布，没有验证可用的固定窗口原生拥塞等级API。源报告峰Level6和新测occupancy属于不同量，不能以占用代替等级，窗口缺席不能记0或改善。

## 终态、身份及资源闭合

AT003于2026-10-16T15:11:38.117704Z自然native/监督0结束，stop=null，无cleanup/无survivors。21项工程核验全true：4个原PID/start无活体，实际FLOCK probe取得并立即释放；144生产输入、两原DCP、6份archived源、两原新报告、独立target、contract及原input绑定保持。全会话1521.569428秒。见[AT003终态小事实](runs/R006/attempts/AT003_new_peak_windows_readonly/readonly_terminal_summary.json)、[完整终态](runs/R006/attempts/AT003_new_peak_windows_readonly/readonly_terminal_facts.json)、[终态与覆盖独立审核](runs/R005/R006_AT003_terminal_coverage_review_evidence.json)。

| 尝试 | 资源样本 | 采样峰树RSS (GiB) | 最低MemAvailable (GiB) | 最低磁盘 (GiB) | 最大采样间隔 (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| R004/AT004 route | 3515 | 27.288212 | 385.292797 | 404.394199 | 6.013834 |
| R006/AT002只读 | 422 | 22.775665 | 375.224209 | 403.499451 | 5.146364 |
| R006/AT003新峰只读 | 300 | 22.821053 | 375.171288 | 401.564053 | 5.157572 |

全程单EDA、CPU0–7/max8/nice5，沿用192GiB树RSS、48GiB/30秒MemAvailable、30GiB磁盘保护，无墙钟/无输出强停；无资源保护触发。资源表为监督采样，不作不同阶段性能收益。

## 保留限制与工程交付边界

原综合监督UNKNOWN及2097.384826秒观测缺口保持，恢复父链资格不追溯改写原监督状态。raw debug verified0、hub声明300MHz/实际50MHz、vendor XPM例外、外部input1/output2缺delay及OPT辅助coverage_limited均保留。完整POST的BB0、内部时钟COMPLETE、8已分类Critical CDC/新增0仅为诊断准入；正式reset/CDC/release/transaction/外部IO安全仍OPEN。

本轮候选有局部功能、资源与布线前setup变化，但合法布通、完整routed时序及最终系统目标未达成。工程证据与收尾已交付；由主控汇总审核，不再自动开启新implementation或额外实验。模型期望gpt-6.1-sol/xhigh，实际配置仍未取得独立证明，不以登记值代替实际核验。
