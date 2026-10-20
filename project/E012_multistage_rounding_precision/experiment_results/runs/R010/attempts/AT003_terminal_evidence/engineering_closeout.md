# E012 R010：15篇、14303232个数值的舍入核验完成

相同输入，精确未舍入原数→原版整数出口的全程舍入差；比例分母是非零原数，每出口7151616个。值均为真实数值单位。

| 输出投影 | 相对误差>1% | >5% | >10% | 绝对最大误差 |
|---|---:|---:|---:|---:|
| Attention o_proj | 0.25230661% | 0.05102343% | 0.02582633% | 0.00001229093323 |
| MLP down_proj | 0.14925298% | 0.03052457% | 0.01539512% | 0.00002098723780 |

末尾两出口均F24→F16舍8位，单看末尾最大绝对差均0.00000762939453125；末尾>1%比例分别0.20219212%/0.04860441%（非零原数各7151614，另2个0→0）。此前逐组实际右移o为5..16位、down为0..11位；这使用组项分母，不能和输出数值占比混用。

预定doc0/token0/channel0原→后：o −0.0240407324927→−0.0240478515625，down 0.661529435543→0.661514282227。近零极端down −0.000000020954757929→−0.0000152587890625，绝对差0.00001523783430而相对72717.78%，已标为诊断最大相对案例。

HostFP32转换另列：o0个变化，down45/7151616变化，转换最大绝对差0.0000152587890625；actual Host返回值相对exact总误差的down最大升至0.00003245554399，>1/5/10%计数保持不变。不是整数舍入统计的一部分。

>1%相对误差集合承担本出口全程误差能量仅o0.44323065%/down0.18664254%；所有输出绝对误差都小于本出口原数RMS的0.1%。完整0.1/1/5/10%计数、能量份额、尾部、零值、实际shift分布和物理原/后值见[完整报告](runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/report.md)、[阈值CSV](runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/scalar_threshold_table.csv)、[原/后值CSV](runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/before_after_examples.csv)。

另有Root从原1024篇aggregate恢复的同F16出口离散差：每出口424755200值，o24.82014935%/down76.62977993%变化，变化均为−0.0000152587890625；这不等于1024篇逐值相对误差比例，范围独立保留。[1024既有证据](runs/R010/analysis_existing/full1024_output_differences.json)

# E012 R010：核验完成

execution_state: completed

verdict: supported（仅支持同输入两个出口的数值核验结论，不是优化成果或整体误差因果归因）。

AT001实际worker897395于02:09:48Z启动，GPU阶段72.2835秒，15篇/30投影全部完成；父supervisor真实wait/reaped native0，GPU无所属进程。CPU4863整数/Fraction、GPU102合成标量/完整直方图、540真实标量任意精度核验、全部真实输出/计数、旧reference/witness/aggregate一致性通过。独立A015核验全部14303232值并另作60个完整依赖Fraction见证，通过。

AT002 CPU全raw后处理41.121秒，native0/wait/reaped，验证全部出口round/sat、exact common-exit round、零值/阈值计数和能量；Host delivered结果另算。总能量0时energy share标null和zero_error_energy，未把0/0作0%解释。12项GPU/CPU消费来源终态SHA不变，所属进程全部退出；证据约216MiB，小于512MiB。

直接同输入局部舍入差与前31层输入变化的传播差必须区分；这次核验没有重跑前31层，不能据此把整体32层输出误差归因于末层，不能相减relativeL2百分数。15篇逐值结果不外推1024，无优化/ACC/PPL/RTL/加速结论。最新授权范围已完成，无后继GPU。

[真实GPU退出](../experiment_results/runs/R010/attempts/AT001_original_two_exit_scalar_audit/external_wait_receipt.json) · [CPU终态](../experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/execution_receipt.json) · [全raw核验](../experiment_results/runs/R010/attempts/AT002_cpu_full_raw_analysis/analysis/independent_checks.json) · [A015独立核验](../experiment_results/runs/R010/independent_review/scalar_audit_review.json) · [释放/SHA](../experiment_results/runs/R010/attempts/AT003_terminal_evidence/final_release_check.json)
