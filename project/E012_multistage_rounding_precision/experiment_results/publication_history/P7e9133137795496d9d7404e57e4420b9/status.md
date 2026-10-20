# E012 R009：真实六臂运行

execution_state: running

verdict: inconclusive

applicability: 首4篇初步结果，尚无全部36篇终态；无任务质量/RTL时序结论。

AT003 worker PID880983，唯一一次model load36.720s、attach286.431s已完成，六臂正式配对运行；最近持久完成12/36文档。全部动态编码、prefix hash、HostFP32缩放一次、attrs/functions/buffers恢复及旧baseline/ref0指标资格通过。

AT001/2原语失败保留，未装模型；AT003新v2 kernel修复legal_shift并实际GPU资格通过。源不热改，GPU0/CPU1/RSS8GiB/GPU24GiB/2400s/512MiB保持。AT004 CPU后处理源与固定doc0/4/35见证计划已在结果前冻结，等待GPU真实退出后运行。

下一步：完成所有36文档、固定/matched/reference-drift三口径，外部OS退出证据、独立CPU复算/PNG/终态三摘要。Root最终审核待取得结果。

[当前状态](../experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/status.json) · [固定CPU见证计划](../experiment_results/runs/R009/attempts/AT004_cpu_postprocess/manifest.json)


---
Published: 2026-10-20T01:42:18.417549+00:00
Publication: P73d87fd217834bc1975093744bd52f40
Execution state: running
Research verdict: inconclusive
Applicability: R009 first4dev/398positions completed, all36 six-arm comparison in progress; c4 tinyTV improvement with hidden regression, no optimization-success claim
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/gpu_qualification.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/actual_launch.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/lastlayer_precision_contract.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/first4_summary.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/r007_legacy_parity.json
