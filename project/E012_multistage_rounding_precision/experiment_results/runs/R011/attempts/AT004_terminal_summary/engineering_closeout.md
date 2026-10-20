# E012 R011：定位到MLP分支合回残差的位置

三篇诊断合池：Attention残差后的相对L2为1.00515987%，Down/MLP分支为0.93974511%，合回最终残差后升至1.43496316%。下表为三篇合池数值，不是1024篇P95。

| 阶段 | A/B相对L2% | 绝对RMSE | 参考RMS | A/C同层入口L2% | C/B继承输入L2% |
|---|---:|---:|---:|---:|---:|
| MLP入口norm | 1.72830918 | 0.006913571 | 0.400019319 | 0.03203299 | 1.72829651 |
| gate | 0.68185167 | 0.008865315 | 1.300182378 | 0.07728231 | 0.68173570 |
| up | 0.78734850 | 0.007266341 | 0.922887496 | 0.08973216 | 0.78676456 |
| SiLU | 0.45419124 | 0.004987621 | 1.098132458 | 0.08261964 | 0.45411314 |
| gated product | 1.33382373 | 0.007550937 | 0.566112056 | 0.17894192 | 1.33290457 |
| Down整数输出 | 0.93974515 | 0.011900250 | 1.266327372 | 0.25336882 | 0.93896352 |
| 最终残差合并 | 1.43496316 | 0.016859001 | 1.174873434 | 0.27368202 | 1.43441239 |

MLP残差误差能量=skip173.69806+branch173.43761+cross0.956943→348.09261；而真实信号两路合并后仅保留45.8985%（抵消54.1015%）。FP32加法本身的roundoff差能量仅5.6954e−13。因此跳变来自两路已有误差叠加与真实信号相消，不能把它归咎于最终加法舍入，或硬指Down末尾cut8为唯一根因。

将本层受policy控制的舍入移除，C/B最终L2仍1.43441239%，接近A/B1.43496316%；精确向量分解能量为12.66973+347.82545−12.40257=348.09261，交互项明确保留，不能解释为互斥因果份额。替换参考gated_product/Down输出并重算后缀，final误差能量条件降低50.09762%/50.10004%，三篇一致；两切点几乎同效，说明主要差异已沿MLP上游传播。Down切点结果逐位等于“当前skip+参考MLP输出”的FP32求和。

[完整报告](runs/R011/attempts/AT003_cpu_causal_analysis/analysis/report.md) · [全部stage CSV](runs/R011/attempts/AT003_cpu_causal_analysis/analysis/stage_metrics.csv) · [完整统计](runs/R011/attempts/AT003_cpu_causal_analysis/analysis/causal_summary.json) · [A015实际证据独审](runs/R011/independent_review/actual_singleblock_review.json) · [Root既有1024阶段图](runs/R011/root_analysis/layer32_error_location.png)

# E012 R011：诊断完成

execution_state: completed

verdict: supported（仅支持所述3例末层位置、传播及条件干预诊断，不是唯一因果归因或优化）。

AT001观察器重建Hadamard遗漏int32→int64，在资格阶段自然失败，未进入真实样本，冻结源/失败收据保留。AT002新v2补原转换与CPU S35探针后，原生/观察器GPU输出逐值一致，正常/异常恢复通过；12次四轨迹单层forward+6次切点后缀全部完成，299位置。A/B逐值复现旧R006 hidden31/finalnorm与36份Prepared/KV文件。GPU阶段75.5803秒，加失败资格仍低于900秒；峰值allocated约0.414GiB、采样RSS约1.787GiB，证据约356.3MiB。

AT002真实父wait/reaped native0、/proc消失且无所属GPU进程；AT003 CPU4.672秒native0/reaped，独立核查决定性raw和能量恒等式。A015另独立复算129个保存stage指标对象、21组ABC分解、旧18hidden/final输入输出数组、36动态文件、全部6条件切点；限定审核通过。23项GPU/CPU消费来源终态SHA不变，全部所属进程退出。报告仅修正“保留比例/抵消比例”措辞，前版与SHA回执保留，不改冻结源或统计。

3篇是预声明诊断个例，不能外推1024干预或ACC/PPL效果；原1024既有stage趋势由Root/A015独立汇总。A/C是同层入口，层内动态量化输入可分化；B轨迹输出替换也移除继承输入差，修复比例是条件效果。没有继续GPU、优化、加位、生产修改或完整模型试验。

[实际退出](../experiment_results/runs/R011/attempts/AT002_singleblock_fourway_v2/external_wait_receipt.json) · [CPU证据](../experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/independent_raw_checks.json) · [终态释放/SHA](../experiment_results/runs/R011/attempts/AT004_terminal_summary/final_release_check.json)
