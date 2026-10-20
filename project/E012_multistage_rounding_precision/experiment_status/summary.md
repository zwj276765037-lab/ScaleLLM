# E012 R011：诊断完成

execution_state: completed

verdict: supported（仅支持所述3例末层位置、传播及条件干预诊断，不是唯一因果归因或优化）。

AT001观察器重建Hadamard遗漏int32→int64，在资格阶段自然失败，未进入真实样本，冻结源/失败收据保留。AT002新v2补原转换与CPU S35探针后，原生/观察器GPU输出逐值一致，正常/异常恢复通过；12次四轨迹单层forward+6次切点后缀全部完成，299位置。A/B逐值复现旧R006 hidden31/finalnorm与36份Prepared/KV文件。GPU阶段75.5803秒，加失败资格仍低于900秒；峰值allocated约0.414GiB、采样RSS约1.787GiB，证据约356.3MiB。

AT002真实父wait/reaped native0、/proc消失且无所属GPU进程；AT003 CPU4.672秒native0/reaped，独立核查决定性raw和能量恒等式。A015另独立复算129个保存stage指标对象、21组ABC分解、旧18hidden/final输入输出数组、36动态文件、全部6条件切点；限定审核通过。23项GPU/CPU消费来源终态SHA不变，全部所属进程退出。报告仅修正“保留比例/抵消比例”措辞，前版与SHA回执保留，不改冻结源或统计。

3篇是预声明诊断个例，不能外推1024干预或ACC/PPL效果；原1024既有stage趋势由Root/A015独立汇总。A/C是同层入口，层内动态量化输入可分化；B轨迹输出替换也移除继承输入差，修复比例是条件效果。没有继续GPU、优化、加位、生产修改或完整模型试验。

[实际退出](../experiment_results/runs/R011/attempts/AT002_singleblock_fourway_v2/external_wait_receipt.json) · [CPU证据](../experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/independent_raw_checks.json) · [终态释放/SHA](../experiment_results/runs/R011/attempts/AT004_terminal_summary/final_release_check.json)


---
Published: 2026-10-20T02:37:42.761565+00:00
Publication: P6e53624bbe884f24ae54fb7e565f3a4d
Execution state: completed
Research verdict: supported
Applicability: Only three predeclared diagnostic documents/299 positions, single decoder31 four-way trajectories and two conditional suffix cuts; supports residual-combination/propagation explanation, not unique/additive attribution, optimization or formal1024 intervention
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/causal_diagnostic_contract.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/attempts/AT002_singleblock_fourway_v2/result.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/attempts/AT002_singleblock_fourway_v2/external_wait_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/report.md
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/causal_summary.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/independent_raw_checks.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/independent_review/actual_singleblock_review.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R011/attempts/AT004_terminal_summary/final_release_check.json
