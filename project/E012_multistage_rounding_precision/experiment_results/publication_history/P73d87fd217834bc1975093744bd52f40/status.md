# E012 R009：实际运行

execution_state: running

verdict: inconclusive

applicability: R009新实验格式overlay资格已通过，尚无整网结论。

GPU0 AT003 worker PID880983于UTC01:33:45真实启动；01:33:56 GPU资格通过后开始唯一一次模型装配。AT001/2仅原语失败均已退出回收，模型加载0；未热改消费源。CPU1/RSS8GiB/GPU24GiB/2400s/512MiB和原free保护保持。observer880984使用已修Linux pidfd机制。

下一步：六臂所有36docs/216forward，首4篇阶段回传，终态真实退出/独立CPU复算/图/摘要。Root最终审阅待实际结果。

[实际启动](../experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/actual_launch.json) · [当前状态](../experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/status.json)


---
Published: 2026-10-20T01:35:40.356168+00:00
Publication: Pa898215e2117410c98c10230a618ea91
Execution state: running
Research verdict: inconclusive
Applicability: R009 onlylayer31 trueF18/F20 output overlay; CPU/GPU qualification pass, one model assembling, no full-model result yet
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/gpu_qualification.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/actual_launch.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/lastlayer_precision_contract.json
