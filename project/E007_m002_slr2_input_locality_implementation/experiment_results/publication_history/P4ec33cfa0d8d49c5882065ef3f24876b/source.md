# E007：SLR1定向卸载与完整implementation依据

用户明确要求“进行针对性优化后开启下一轮implementation 我希望下一次就能成功”。执行[SM011合同](../../../mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)，以E005已资格debug_materialized图为共同起点，将tensor输入bank与MLP capture/Hadamard/四量化器成组硬约束到SLR2。其余RTL/IP/数值/接口/时钟与物理directive保持。前期CPU资源与边界分析来自[E006候选](../../E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/input_frontend_locality_candidate.md)，不是迁移效果证据。


---
Published: 2026-10-16T23:10:32.789942+00:00
Publication: P4e7eda58aa9f4556af444c3b2daae3a9
