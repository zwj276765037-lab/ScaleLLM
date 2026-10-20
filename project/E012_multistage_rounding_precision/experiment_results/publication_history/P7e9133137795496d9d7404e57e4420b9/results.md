# E012 R009：首4篇已完成，全部36篇继续运行

主比较固定使用ref4，前4开发文档/398真实位置：

| 配置 | 第32层pre-norm L2中位% | finalhidden L2中位% | logit L2中位% | meanTV% | Top1不一致 |
|---|---:|---:|---:|---:|---:|
| baseline_b0 | 1.763582187 | 1.953769311 | 1.635095559 | 0.868463193 | 4/398 |
| candidate_b2 | 1.763760073 | 1.954201777 | 1.634997939 | 0.868672782 | 4/398 |
| candidate_b4 | 1.763525271 | 1.954007072 | 1.634998504 | 0.866707868 | 4/398 |

+4位meanTV略降，但finalhidden中位略升；+2位meanTV略升，暂不宣称优化成功。baseline/ref0所有raw哈希和旧R007指标全等；候选前31层与baseline相同，三参考前31层相同；attrs/functions逐臂恢复检查通过。

ref0→ref4自身meanTV漂移0.076799%、finalhiddenL2中位0.190052%，已另报而未当成候选改善。同格式配对和所有不利尾部见[完整首4篇摘要](runs/R009/attempts/AT003_true_exit_precision_dev36/first4_summary.json)。后续32篇仍对两档全测，无筛选省略。

[原始配对指标](runs/R009/attempts/AT003_true_exit_precision_dev36/metrics.jsonl) · [旧口径复核](runs/R009/attempts/AT003_true_exit_precision_dev36/r007_legacy_parity.json) · [历史R007限定负结果](runs/R007/attempts/AT002_cpu_postprocess/analysis/report.md)


---
Published: 2026-10-20T01:42:18.417549+00:00
Publication: P73d87fd217834bc1975093744bd52f40
