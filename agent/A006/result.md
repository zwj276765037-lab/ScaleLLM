# SM010 / E006 当前工程执行

用户已新授权SLR1资源/热点/连接归因。AT001于15:51:44.063950Z原生启动，一次读取E005闭合physopt DCP；原physopt恢复及2,204,250 unique primitive导出已闭合，global与首4owner原生query0。首批[batch001事实](../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution/closed_owner_batch001_summary.json)已实发主控/A007：MLP BRAM36K当量126/361/0、Attention0/57/296、MLP metadata URAM280/280/112；60项实际primitive/site与原生资源互核一致。core_other继续，随后关闭其他owner/detail及10NW/UNION实际cell归属，再继续40失败样本与热点相关canonical连接。原E005工程终态保持历史，整stage/热点/连接/本次终态尚未完成。

[当前R001](../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/run.md) · [真实启动证据](../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/attempts/AT001_physopt_attribution/native_started_observation.json) · [持久接续](resume_E006.json)

主控追加的后继CPU准备已交付[原OPT/pre-place、约束和SSI入口身份](followon_placement_parent_cpu_preparation_2026-10-16.md)：原DCP重hash及包身份已核，162现存XDC+13明确映射snapshot共175来源匹配；没有新EDA、DCP复制或生产修改，目标selector在实际OPT/pre-place命中仍待新合同验证。E006继续现有原生会话，未切换实验。

## 已结束的E005及以前交付（历史）

# SM009 / E005 工程最终交付

工程执行和取证收尾已完成，当前无活动EDA。完整Default route合法布通FAIL：1148579重叠节点、758463拥塞失败信号；原生/监督自然1、五项失败capture均0，原错误重抛，失败DCP不进入成功父链。新place/physopt完整POST父链保持；正式hold及失败route时序仍FAIL，formal reset/CDC/外部IO安全OPEN。

R006/AT002和AT003各自双phase自然0/0闭合。80边界/94net/旧48窗与新12峰行→10NW区域测量已完成，Gate精确跨SLR1917 leaf pins/upstream13；新10区域site均SLR1且CLB sites全部occupied，但不等于LUT/BEL容量100%或拥塞等级。AT002空new_peak项为N/A；新峰只映射48保留行中的12峰/10unique子集；fixed congestion仍UNAVAILABLE。

144输入、2原DCP、实际archived源和来源绑定、全部原PID-start退出、锁释放、资源复算均已核，A007独立复核完成。详见[工程最终报告](../../project/E005_m002_optimized_implementation/experiment_results/engineering_final_report_2026-10-16.md)、[AT003终态小事实](../../project/E005_m002_optimized_implementation/experiment_results/runs/R006/attempts/AT003_new_peak_windows_readonly/readonly_terminal_summary.json)、[当前R006](../../project/E005_m002_optimized_implementation/experiment_results/runs/R006/run.md)。

原综合监督UNKNOWN/观测缺口、debug raw verified0与300MHz/50MHz问题及正式安全OPEN保持，无bitstream/板卡/GPU/PPL/ACC。由主控整合三摘要/mission/results及审核；本工程不再自动开启implementation、EDA或测试。

# SM008 / E004 历史交付

物理分析及唯一一次只读 AT001 已自然完成，native/监督0、stop null，原DCP后hash不变，五受管身份和supervisor均退出，EDA锁释放。35/48 query code0，13help失败；BEL槽hist INVALID，native资源/SRL槽/site与52net定向查询有效；27个日志唯一样例全部找到。优化候选未实施，收益未验证，当前无活动EDA。

[最终物理报告](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R001/physical_routability_analysis.md)、[小汇总与证据身份](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R001/engineering_delivery_facts_2026-10-16.json)。首选input48slot译码与MLP32output CE的分项验证；S32-only浅history为条件次选。具体组合/策略及全局验收由主控/A007最终审核。所有生产实现不改。

# SM007 / E003工程最终交付（历史）

工程执行与证据收尾已结束；本次合法布通FAIL，方法普遍性inconclusive，当前无活动EDA。实际place0、独立physopt0/closed DCP/完整POST及成功父链保留；route19065秒后native1，Phase9明确245279 node overlaps/248289 signals拥塞失败。自然终态native/worker/manager/driver均1、stop null，3882样本资源复算、六原PID/start退出和EDA锁释放已闭合。

本次无route/失败DCP、独立route_status、正式routed timing或完整POST，不自动重试/改策略。冻结默认策略、算法/数值/接口/时钟不变，bitstream/板卡/GPU/PPL/ACC未运行；正式reset/CDC/事务安全OPEN。交主控集中评判后续。

[工程总报告](../../project/E003_m002_full_implementation/experiment_results/engineering_final_report_2026-10-16.md)、[route最终facts](../../project/E003_m002_full_implementation/experiment_results/runs/R003/attempts/AT001_full_route/route_terminal_completion_facts.json)、[资源/终态复算](../../project/E003_m002_full_implementation/experiment_results/runs/R003/attempts/AT001_full_route/terminal_facts.json)、[完整physopt父点](../../project/E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/terminal_facts.json)。

## E002及更早历史（保留）

# A006：工程交付记录

## E001历史交付（SM004快速验证范围）

SM004 / E001 / R003 已完成。[worker报告](../../project/E001_m002_repair_quick_validation/experiment_results/runs/R003/worker_report.md)；[主控审核](../../results/reviews/SM004.md)。

构建CPU、完整展开、真实BD及告警分析已交付。原始成功/失败attempt保留，当前输入身份已核查。结论只适用于快速验证；未执行正式综合/实现/板卡，不作完整模型或告警豁免声明。全局限制和下一阶段见 [M002报告](../../results/missions/M002_summary.md)。


## E002本轮有界阶段交付（SM005/SM006）

新正式综合、OPT/debug及严格pre_place诊断已完成；AT009唯一一次完成pre_place恢复后仍在固定2h上限结束，124/native−15、无survivors，全部6个受管身份及独立supervisor均不在。没有place/physopt成功receipt或完整DCP，没有route父链，R004 NOT_RUN；不再重复place，无活动EDA。

[工程总报告](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/engineering_final_report_2026-10-15.md)、[AT009原终态](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)、[R004未运行原因](../../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R004/not_run_reason.json)。本次前置实测减少31m21.1s；CPU/真实父链与live guard通过不替代物理结果。私有后继候选已持久留存，未安装、未回归/真实资格或额外EDA。

执行阶段已结束，M002物理/最终时序与正式reset/CDC/release/事务安全未达成或OPEN；数值与接口/100MHz合同未改，旧工程只读，bitstream/板卡/GPU/PPL/ACC未运行。由主控据总报告集中评判后续，不自动恢复。
