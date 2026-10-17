## 实现入口

| 目录 | 内容 | 当前边界 |
| --- | --- | --- |
| [software](software/README.md) | 正确算法、QDQ/整数 twin、评估入口、精选历史证据 | 本轮不改变数值权威 |
| [hardware](hardware/README.md) | RTL、Host、TB、小型向量、Vivado源脚本/约束 | E005优化后的完整implementation及补采已全部结束，合法布通失败：1148579重叠路由节点、758463拥塞失败信号，失败DCP和诊断已保存。局部功能通过，新综合及完整place/physopt流程完成；布线前setup改善，hold仍失败。R006两批只读补采均自然成功、独立复核完成，144冻结输入与原检查点保持。整体执行failed、方法判断inconclusive，用户结果审核未记录；M002全局目标未完成。 |

代码直接位于这两个目录，不另建一套 E 编号源码副本。未来新实验只登记实验协议和证据，引用这两个实现根。

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-17T04:53:47.983901+00:00。来源修订：`16fcfce055f5`。

# 实验与结果索引

| 实验 | 详情 | Mission / 子任务 | 最新发布的执行 / 研究状态 | 运行批次 |
| --- | --- | --- | --- | --- |
| E001 | [m002_repair_quick_validation](E001_m002_repair_quick_validation/README.md) | M002 / SM004 | completed / supported | [R001](E001_m002_repair_quick_validation/experiment_results/runs/R001/README.md) · [R002](E001_m002_repair_quick_validation/experiment_results/runs/R002/README.md) · [R003](E001_m002_repair_quick_validation/experiment_results/runs/R003/README.md) · [R004](E001_m002_repair_quick_validation/experiment_results/runs/R004/README.md) |
| E002 | [m002_synthesis_and_physical_baseline](E002_m002_synthesis_and_physical_baseline/README.md) | M002 / SM005 | failed / inconclusive | [R001](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/README.md) · [R002](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/README.md) · [R003](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/README.md) · [R004](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R004/README.md) · [R005](E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R005/README.md) |
| E003 | [m002_full_implementation](E003_m002_full_implementation/README.md) | M002 / SM007 | failed / inconclusive | [R001](E003_m002_full_implementation/experiment_results/runs/R001/README.md) · [R002](E003_m002_full_implementation/experiment_results/runs/R002/README.md) · [R003](E003_m002_full_implementation/experiment_results/runs/R003/README.md) · [R004](E003_m002_full_implementation/experiment_results/runs/R004/README.md) |
| E004 | [m002_routability_optimization_analysis](E004_m002_routability_optimization_analysis/README.md) | M002 / SM008 | completed / inconclusive | [R001](E004_m002_routability_optimization_analysis/experiment_results/runs/R001/README.md) · [R002](E004_m002_routability_optimization_analysis/experiment_results/runs/R002/README.md) · [R003](E004_m002_routability_optimization_analysis/experiment_results/runs/R003/README.md) |
| E005 | [m002_optimized_implementation](E005_m002_optimized_implementation/README.md) | M002 / SM009 | failed / inconclusive | [R001](E005_m002_optimized_implementation/experiment_results/runs/R001/README.md) · [R002](E005_m002_optimized_implementation/experiment_results/runs/R002/README.md) · [R003](E005_m002_optimized_implementation/experiment_results/runs/R003/README.md) · [R004](E005_m002_optimized_implementation/experiment_results/runs/R004/README.md) · [R005](E005_m002_optimized_implementation/experiment_results/runs/R005/README.md) · [R006](E005_m002_optimized_implementation/experiment_results/runs/R006/README.md) |
| E006 | [m002_slr1_congestion_attribution](E006_m002_slr1_congestion_attribution/README.md) | M002 / SM010 | completed / supported | [R001](E006_m002_slr1_congestion_attribution/experiment_results/runs/R001/README.md) · [R002](E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/README.md) · [R003](E006_m002_slr1_congestion_attribution/experiment_results/runs/R003/README.md) · [R004](E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/README.md) · [R005](E006_m002_slr1_congestion_attribution/experiment_results/runs/R005/README.md) · [R006](E006_m002_slr1_congestion_attribution/experiment_results/runs/R006/README.md) |
| E007 | [m002_slr2_input_locality_implementation](E007_m002_slr2_input_locality_implementation/README.md) | M002 / SM011 | planned / unassessed | [R001](E007_m002_slr2_input_locality_implementation/experiment_results/runs/R001/README.md) · [R002](E007_m002_slr2_input_locality_implementation/experiment_results/runs/R002/README.md) |
| E008 | [m002_exact_hotspot_offload_implementation](E008_m002_exact_hotspot_offload_implementation/README.md) | M002 / SM012 | running / unassessed | [R001](E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/README.md) |

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
