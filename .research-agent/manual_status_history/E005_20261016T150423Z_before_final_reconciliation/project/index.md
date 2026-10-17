## 实现入口

| 目录 | 内容 | 当前边界 |
| --- | --- | --- |
| [software](software/README.md) | 正确算法、QDQ/整数 twin、评估入口、精选历史证据 | 本轮不改变数值权威 |
| [hardware](hardware/README.md) | RTL、Host、TB、小型向量、Vivado 源脚本/约束 | M002快速验证、正式综合及入口适配完成；E003 route自然失败；E004分析完成；E005局部功能/入口通过，新create成功，正式新综合自然完成、80局部控制已核，OPT成功/POST入口失败，198项入口回归通过，219项入口回归通过，AT003完整place/physopt POST已通过并自然退出0，最终父链合格；AT004已从新physopt DCP实际启动原生Default route，原生Phase9合法布通失败（1148579重叠节点、758463拥塞失败信号），已自然native/监督1退出、无强停/残留且144冻结输入保持，失败现场已保全；R006/AT002双phase只读补采已自然0结束，AT003已于14:46:16 UTC实际启动新峰窗口映射补齐，最终整合待完成；布线前setup/PW通过而hold失败，placed拥塞峰Level6；实际route初始Global/Short及Timing拥塞Level7，阶段不同不能直接比较 |

代码直接位于这两个目录，不另建一套 E 编号源码副本。未来新实验只登记实验协议和证据，引用这两个实现根。

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-16T14:50:41.501559+00:00。来源修订：`c9b5b8efc301`。

# 实验与结果索引

| 实验 | 详情 | Mission / 子任务 | 最新发布的执行 / 研究状态 | 运行批次 |
| --- | --- | --- | --- | --- |
| E001 | [m002_repair_quick_validation](E001_m002_repair_quick_validation/README.md) | M002 / SM004 | completed / supported | [R001](E001_m002_repair_quick_validation/experiment_results/runs/R001/README.md) · [R002](E001_m002_repair_quick_validation/experiment_results/runs/R002/README.md) · [R003](E001_m002_repair_quick_validation/experiment_results/runs/R003/README.md) · [R004](E001_m002_repair_quick_validation/experiment_results/runs/R004/README.md) |
| E002 | [m002_synthesis_and_physical_baseline](E002_m002_synthesis_and_physical_baseline/README.md) | M002 / SM005 | failed / inconclusive | [R001](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/README.md) · [R002](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/README.md) · [R003](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/README.md) · [R004](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R004/README.md) · [R005](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R005/README.md) |
| E003 | [m002_full_implementation](E003_m002_full_implementation/README.md) | M002 / SM007 | failed / inconclusive | [R001](E003_m002_full_implementation/experiment_results/runs/R001/README.md) · [R002](E003_m002_full_implementation/experiment_results/runs/R002/README.md) · [R003](E003_m002_full_implementation/experiment_results/runs/R003/README.md) · [R004](E003_m002_full_implementation/experiment_results/runs/R004/README.md) |
| E004 | [m002_routability_optimization_analysis](E004_m002_routability_optimization_analysis/README.md) | M002 / SM008 | completed / inconclusive | [R001](E004_m002_routability_optimization_analysis/experiment_results/runs/R001/README.md) · [R002](E004_m002_routability_optimization_analysis/experiment_results/runs/R002/README.md) · [R003](E004_m002_routability_optimization_analysis/experiment_results/runs/R003/README.md) |
| E005 | [m002_optimized_implementation](E005_m002_optimized_implementation/README.md) | M002 / SM009 | running / inconclusive | [R001](E005_m002_optimized_implementation/experiment_results/runs/R001/README.md) · [R002](E005_m002_optimized_implementation/experiment_results/runs/R002/README.md) · [R003](E005_m002_optimized_implementation/experiment_results/runs/R003/README.md) · [R004](E005_m002_optimized_implementation/experiment_results/runs/R004/README.md) · [R005](E005_m002_optimized_implementation/experiment_results/runs/R005/README.md) · [R006](E005_m002_optimized_implementation/experiment_results/runs/R006/README.md) |

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
