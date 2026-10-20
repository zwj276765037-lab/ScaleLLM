# E012 R007：工程已真实完成，待Root最终审阅

execution_state: completed

verdict: inconclusive

applicability: 三种等位宽RNE候选dev4初筛及last1独立next32dev验证；未验证出联合全面改善，不推广生产；无全1024/ACC/PPL/RTL时序结论。

AT001全部36文档/4494真实位置完成，116次完整32层forward，输入与源SHA冻结并复核不变；所有动态编码每臂重新执行。GPU worker PID864316的外部pidfd于2026-10-20T00:57:01.272Z观测实际退出，捕获/proc exit_code0、随后/proc消失且GPU无该PID。原observer API失败保留，v2成功，未将基础设施失败解释为方法失败。

AT002 CPU独立复算、固定FP64head见证和Python PNG完成，两个CPU子进程真实native0且parent wait/reaped；图已目视检查。自有GPU/CPU实验与观察器均无活动后台进程。未超原GPU0/CPU1/RSS8GiB/GPU24GiB/2400s/512MiB预算。

主要结果：meanTV相对改善0.1173%，但finalhidden L2中位相对退步0.05937%、Top1错35→36/4096、TVP99上升。原生产源保留。实际agent模型/effort缺独立运行回执，保持未核实；期望gpt-6.1-sol/xhigh已登记，不混写为实际。

阻塞：无执行阻塞。Root最终方法/后续决策未记录；未追加GPU范围或其他候选搜索。

[GPU外部退出证据](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/external_lifecycle_receipt_v2.json) · [CPU收据](../experiment_results/runs/R007/attempts/AT002_cpu_postprocess/execution_receipt.json) · [独立复算](../experiment_results/runs/R007/attempts/AT002_cpu_postprocess/analysis/independent_checks.json) · [head见证](../experiment_results/runs/R007/attempts/AT002_cpu_postprocess/head_witness/independent_head_witness.json)


---
Published: 2026-10-20T01:01:05.795069+00:00
Publication: P5374ac080ed74293b7c514b78f31d8af
Execution state: completed
Research verdict: inconclusive
Applicability: R007 dev4三候选初筛与last1 next32dev验证完成；部分微小改善伴finalhidden/Top1/TVP99退步，未证明全面优化，不推广生产
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/result.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/external_lifecycle_receipt_v2.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT002_cpu_postprocess/analysis/report.md
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT002_cpu_postprocess/analysis/independent_checks.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT002_cpu_postprocess/head_witness/independent_head_witness.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT002_cpu_postprocess/execution_receipt.json
