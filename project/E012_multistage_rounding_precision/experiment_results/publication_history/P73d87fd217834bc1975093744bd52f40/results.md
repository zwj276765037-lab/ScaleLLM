# E012 R009：资格通过，模型装配中

尚无R009整网改善结论。CPU2781整数/Fraction及4个Host缩放恢复情景通过，补充432个宽度wrap/sat检查保留。AT001/AT002在模型加载前由GPU资格发现legal_shift反推漏加b，原始失败不改写；新core_v2在AT003修复，GPU b0 raw/counter parity、宽Attention正码、Down超int32、独立Fraction reference全部通过。

本批将测全部36开发文档和不利尾部，不以新高精度参考漂移冒充算法改善。此前R007已被Root接纳为限定负结果，未采用RNE；其结果保留于[R007报告](runs/R007/attempts/AT002_cpu_postprocess/analysis/report.md)。

[GPU资格](runs/R009/attempts/AT003_true_exit_precision_dev36/gpu_qualification.json) · [两次失败原始证据](runs/R009/attempts/AT002_true_exit_precision_dev36/execution_receipt.json)


---
Published: 2026-10-20T01:35:40.356168+00:00
Publication: Pa898215e2117410c98c10230a618ea91
