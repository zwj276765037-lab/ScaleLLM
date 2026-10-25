

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E012 · multistage_rounding_precision

关联：M005 / SM021

## 原始管理记录

- [实验协议](experiment_source/protocol.md)
- [来源摘要](experiment_source/summary.md)
- [结果摘要](experiment_results/summary.md)
- [状态摘要](experiment_status/summary.md)

## 当前结果摘录

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

[完整报告](experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/report.md) · [全部stage CSV](experiment_results/runs/R011/attempts/AT003_cpu_causal_analysis/analysis/stage_metrics.csv) · [完整统计](runs/R011/attem

（摘录截断；完整记录见链接。）

## 每个运行批次

| 批次 | 详情 | 具体尝试数量 |
| --- | --- | --- |
| R001 | [本批结果与证据](experiment_results/runs/R001/README.md) | 2 |
| R002 | [本批结果与证据](experiment_results/runs/R002/README.md) | 5 |
| R003 | [本批结果与证据](experiment_results/runs/R003/README.md) | 10 |
| R004 | [本批结果与证据](experiment_results/runs/R004/README.md) | 5 |
| R005 | [本批结果与证据](experiment_results/runs/R005/README.md) | 66 |
| R006 | [本批结果与证据](experiment_results/runs/R006/README.md) | 68 |
| R007 | [本批结果与证据](experiment_results/runs/R007/README.md) | 2 |
| R008 | [本批结果与证据](experiment_results/runs/R008/README.md) | 1 |
| R009 | [本批结果与证据](experiment_results/runs/R009/README.md) | 5 |
| R010 | [本批结果与证据](experiment_results/runs/R010/README.md) | 3 |
| R011 | [本批结果与证据](experiment_results/runs/R011/README.md) | 5 |
| R012 | [本批结果与证据](experiment_results/runs/R012/README.md) | 0 |

## 原工程历史结果


本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
