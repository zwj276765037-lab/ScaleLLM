
历史原文已保留：[整理前原文](../../.research-agent/navigation_history/43642138164c68fb18de818a22c63061bbd76e9617e50dedb14217cf4fd08892.md)

当前执行依据：[2026-10-15 正式综合及布局布线实验合同](implementation_contract_2026-10-15.md)。[修复与快速功能验证合同](repair_contract_2026-10-15.md)对应已完成的E001前置阶段。旧方案/验收模板见上方历史原文，不能作为当前通过证据。

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# M002 · ddr_separation_and_timing_recovery

[任务合同](contract.md) · [任务总结](../../results/missions/M002_summary.md)

## 执行子任务与主控审核

| 子任务 | 定义 | 完整审核历史 |
| --- | --- | --- |
| SM002 · preserve_weight_streams_and_route_ddr | [定义](tasks/SM002.md) | [审核](../../results/reviews/SM002.md) |
| SM003 · repair_host_layout_and_loading | [定义](tasks/SM003.md) | [审核](../../results/reviews/SM003.md) |
| SM004 · repair_build_and_quick_verification | [定义](tasks/SM004.md) | [审核](../../results/reviews/SM004.md) |
| SM005 · m002_fresh_synthesis | [定义](tasks/SM005.md) | [审核](../../results/reviews/SM005.md) |
| SM006 · m002_physical_flow_and_experiments | [定义](tasks/SM006.md) | [审核](../../results/reviews/SM006.md) |
| SM007 · m002_full_implementation | [定义](tasks/SM007.md) | [审核](../../results/reviews/SM007.md) |
| SM008 · m002_routability_optimization_analysis | [定义](tasks/SM008.md) | [审核](../../results/reviews/SM008.md) |
| SM009 · m002_routability_optimization_and_implementation | [定义](tasks/SM009.md) | [审核](../../results/reviews/SM009.md) |
| SM010 · m002_slr1_congestion_attribution | [定义](tasks/SM010.md) | [审核](../../results/reviews/SM010.md) |
| SM011 · m002_slr1_offload_and_implementation | [定义](tasks/SM011.md) | [审核](../../results/reviews/SM011.md) |
| SM012 · m002_exact_hotspot_offload_implementation | [定义](tasks/SM012.md) | [审核](../../results/reviews/SM012.md) |

## 关联实验

- [E001 · m002_repair_quick_validation](../../project/E001_m002_repair_quick_validation/README.md) — completed
- [E002 · m002_synthesis_and_physical_baseline](../../project/E002_m002_synthesis_and_physical_baseline/README.md) — failed
- [E003 · m002_full_implementation](../../project/E003_m002_full_implementation/README.md) — failed
- [E004 · m002_routability_optimization_analysis](../../project/E004_m002_routability_optimization_analysis/README.md) — completed
- [E005 · m002_optimized_implementation](../../project/E005_m002_optimized_implementation/README.md) — failed
- [E006 · m002_slr1_congestion_attribution](../../project/E006_m002_slr1_congestion_attribution/README.md) — completed
- [E007 · m002_slr2_input_locality_implementation](../../project/E007_m002_slr2_input_locality_implementation/README.md) — planned
- [E008 · m002_exact_hotspot_offload_implementation](../../project/E008_m002_exact_hotspot_offload_implementation/README.md) — failed
- 前置：[M001 · clean_project_migration](../M001_clean_project_migration/README.md)

## 任务总结原文摘录

# M002：阶段报告

> 最新进度：**最新实态：E008/AT004布线因拥塞自然失败；2026-10-18北京时间05:18:30监督器结束，native1/supervisor1、stop_reason=null，无强停。最终702396重叠节点、547548拥塞失败信号；相对E005终态分别减少38.85%和27.81%，仍未合法布通。完整place/physopt已独立审核，C01的9491物理对象已落SLR2；失败图仍保持该落区。place/physopt/route_failed三个检查点及诊断已保存。此前running摘要因工程代理容量错误未及时更新，现按原始终态纠正；工程与独立审核正完成最终收尾，当前未启动新尝试。** [续接记录](pdu_shutdown_handoff_2026-10-17.md)。

下文保留E005已结束基线及更早阶段记录。

> 当前进度：E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。[E005结果](../../project/E005_m002_optimized_implementation/experiment_results/summary.md)、[主控审核](../../results/reviews/SM009.md)。

## E004、E003及更早阶段历史

下文为各阶段当时的判断，不覆盖E005当前结果。

> 最新进度：SM008/E004详细优化分析已完成，主控整合及独立审核完成。首选Attention固定slot写入48个局部边界、MLP32个同拍输出CE及SSI_SpreadSLLs布局；验证、后备与严格route判据见[优化方案](../../project/E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)及[主控审核](../../results/reviews/SM008.md)。只读诊断自然完成、原DCP未改，无活动EDA。候选尚未实施，布通收益inconclusive；本轮未改生产设计或运行新综合/place/route。

> E003已结束基线：本轮完整implementation尝试已自然结束，执行FAILED；place/独立physopt命令、DCP和完整POST通过，R003/AT001 route实际19065秒后于22:45:40 UTC返回Tcl1。Phase9合法布通FAIL：245279重叠路由节点、248289拥塞失败信号（不同指标）。22:45:51 UTC监督/driver自然结束，stop_reason=null，无时间或资源终止，六个原进程退出且单EDA锁释放。没有生成route DCP/完整route_status/正式routed时序/POST；最后有效恢复点是AT002 physopt.dcp。原失败保留，无新EDA尝试，未改变算法/RTL/XDC/接口/时钟/默认策略。 下文E002/E001为前置历史，不能当作本轮最终结果。

150项CPU/实际图与来源验证后，新原生place POST已真正完成；此前两条DDR1 AUX代表源适配问题已在真实新图

（摘录截断；完整记录见链接。）

## 相关决定、变更与讨论

- [README](../../results/README.md)
- [hardware_metrics](../../results/hardware_metrics.md)
- [hardware_progress](../../results/hardware_progress.md)
- [review_queue](../../results/review_queue.md)

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
