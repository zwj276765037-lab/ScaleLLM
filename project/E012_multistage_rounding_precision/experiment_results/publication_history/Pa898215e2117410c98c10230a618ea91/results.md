# E012 R007：快速纠正候选试验完成，未验证出全面改善

execution_state: completed；verdict: inconclusive。前4初筛的Linear-last1在另一组32开发文档上只取得微小部分改善，finalhidden与Top1出现退步，当前不支持推广生产。Root最终审核待独立决定。

| next32dev指标（4096真实位置） | baseline | Linear-last1 RNE |
|---|---:|---:|
| 第32层pre-norm L2文档中位% | 1.940032317 | 1.939197037 |
| finalhidden L2文档中位% | 2.097337280 | 2.098582422 |
| 全词表logit L2文档中位% | 1.775272383 | 1.774625834 |
| meanTV% | 0.867630920 | 0.866613218 |
| TV位置P95% | 2.474970284 | 2.456746171 |
| TV位置P99% | 4.207869798 | 4.242743280 |
| TV位置最大% | 11.236764994 | 11.181976208 |
| Top1不一致 | 35/4096 | 36/4096 |

meanTV相对下降0.11730%，第32层L2中位相对下降0.04305%，logit L2中位相对下降0.03642%；finalhidden L2中位相对上升0.05937%，Top1多1个不一致，TVP99也上升。逐文档meanTV为19改善/13退步，finalhidden为17改善/15退步；全部不利数据与尾部保留。

前4（398位置）初筛中last1 meanTV0.869618→0.863230%、Top1错4→2。全层Linear和全层Linear+PV因finalhidden中位变差未合格；后者虽meanTV0.836278%更低，仍未绕过冻结规则。36文档/4494位置、116次完整forward、80组candidate/reference比较全部完成。

CPU独立复算80组NPZ hidden全通过，最大L2差1.151e-13。18个固定位置CPU FP64全词表head配对见证TV与原FP32head最大差5.882e-7，Top1 IDs全等；此为选定见证，不是全量bitwise证明。

所有candidate/baseline有限guard/acc overflow、格式错误及输出sat/overflow、KV clip均0；QK既有score clamp非0（next32两臂各542597），完整保留。GPU阶段665.205s，峰值allocated14.197GiB、RSS1.763GiB；总证据约417MiB。GPU实际0退出并被OS回收，设备无残留该PID。

[完整报告及所有指标](runs/R007/attempts/AT002_cpu_postprocess/analysis/report.md) · [Python对比PNG](runs/R007/attempts/AT002_cpu_postprocess/analysis/rounding_comparison.png) · [逐文档差值](runs/R007/attempts/AT002_cpu_postprocess/analysis/per_document_deltas.csv) · [逐位置指标](runs/R007/attempts/AT002_cpu_postprocess/analysis/per_position_metrics.csv) · [原始配对结果](runs/R007/attempts/AT001_rne_equalwidth_dev36/result.json)

此前[R006全1024结论](runs/R006/analysis/aggregate_v2/report.md)保留，未与本批混算。本批无任务ACC/PPL、RTL实现、时序或广泛无偏性结论。


---
Published: 2026-10-20T01:01:05.795069+00:00
Publication: P5374ac080ed74293b7c514b78f31d8af
