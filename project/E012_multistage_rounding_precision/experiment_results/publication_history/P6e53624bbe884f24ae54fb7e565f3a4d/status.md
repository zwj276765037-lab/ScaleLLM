# E012 R010：核验完成

execution_state: completed

verdict: supported（仅支持同输入两个出口的数值核验结论，不是优化成果或整体误差因果归因）。

AT001实际worker897395于02:09:48Z启动，GPU阶段72.2835秒，15篇/30投影全部完成；父supervisor真实wait/reaped native0，GPU无所属进程。CPU4863整数/Fraction、GPU102合成标量/完整直方图、540真实标量任意精度核验、全部真实输出/计数、旧reference/witness/aggregate一致性通过。独立A015核验全部14303232值并另作60个完整依赖Fraction见证，通过。

AT002 CPU全raw后处理41.121秒，native0/wait/reaped，验证全部出口round/sat、exact common-exit round、零值/阈值计数和能量；Host delivered结果另算。总能量0时energy share标null和zero_error_energy，未把0/0作0%解释。12项GPU/CPU消费来源终态SHA不变，所属进程全部退出；证据约216MiB，小于512MiB。

直接同输入局部舍入差与前31层输入变化的传播差必须区分；这次核验没有重跑前31层，不能据此把整体32层输出误差归因于末层，不能相减relativeL2百分数。15篇逐值结果不外推1024，无优化/ACC/PPL/RTL/加速结论。最新授权范围已完成，无后继GPU。

[真实GPU退出](../experiment_results/runs/R010/attempts/AT001_original_two_exit_scalar_audit/external_wait_receipt.json) · [CPU终态](../experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/execution_receipt.json) · [全raw核验](../experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/independent_checks.json) · [A015独立核验](../experiment_results/runs/R010/independent_review/scalar_audit_review.json) · [释放/SHA](../experiment_results/runs/R010/attempts/AT003_terminal_evidence/final_release_check.json)


---
Published: 2026-10-20T02:16:56.874698+00:00
Publication: Pc02186b680df4808ba1f3ff23b45cc37
Execution state: completed
Research verdict: supported
Applicability: Only numerical-fidelity observations of original same-input layer31 o_proj/down_proj across15predeclared audit documents/1746positions/14303232scalars; not whole32layer causal attribution or all1024 pointwise relative ratios
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/lastlayer_rounding_audit_contract.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/attempts/AT001_original_two_exit_scalar_audit/result.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/attempts/AT001_original_two_exit_scalar_audit/external_wait_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/scalar_summary.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/report.md
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/independent_checks.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/independent_review/scalar_audit_review.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R010/attempts/AT003_terminal_evidence/final_release_check.json
