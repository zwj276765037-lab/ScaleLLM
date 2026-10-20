# E012 R007：dev4初筛完成，next32验证运行

前4开发文档/398真实位置全部纳入，baseline/reference的双finalhidden哈希、layer32/logitL2、逐位置Top1/TV与R006完全一致。

| 配置 | layer32 L2中位% | finalhidden L2中位% | logit L2中位% | pooled meanTV% | Top1错数/398 | 初筛资格 |
|---|---:|---:|---:|---:|---:|---|
| baseline | 1.764028 | 1.954097 | 1.636305 | 0.869618 | 4 | baseline |
| linear_last1 | 1.763251 | 1.953842 | 1.635691 | 0.863230 | 2 | 合格provisional |
| linear_all32 | 1.809176 | 2.000419 | 1.594277 | 0.897987 | 1 | finalhidden中位变差，不合格 |
| linear_pv_all32 | 1.756805 | 1.997781 | 1.600403 | 0.836278 | 3 | finalhidden中位变差，不合格 |

Linear-last1初筛meanTV相对降低约0.735%，幅度有限；尚不能据此判验证成功。Linear+PV的meanTV更低，但finalhidden中位退步，未绕开冻结规则选中。全部尾部、逐文档/逐位置结果保留在原始comparison JSON/metrics JSONL中。

[初筛全指标](runs/R007/attempts/AT001_rne_equalwidth_dev36/selection_summary.json) · [筛选决定](runs/R007/attempts/AT001_rne_equalwidth_dev36/selection_decision.json) · [R006逐项复核](runs/R007/attempts/AT001_rne_equalwidth_dev36/r006_baseline_parity.json)

本节仅R007开发初筛；此前R006全1024结论保留于[历史R006分析](runs/R006/analysis/aggregate_v2/report.md)，两批数值不合并。


---
Published: 2026-10-20T00:54:20.722145+00:00
Publication: P4d963b8e981e47eb8477e22492a3454a
