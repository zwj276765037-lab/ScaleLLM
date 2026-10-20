# E012 R009：第32层两出口真实加位数，全部开发配对完成

同36开发文档/4494位置、六臂216forward。固定同一ref4主比较；L2为文档中位百分数，TV为概率质量百分数。

| 配置 | layer32 pre-norm L2% | finalhidden L2% | logit L2% | meanTV% | Top1不一致 |
|---|---:|---:|---:|---:|---:|
| baseline | 1.931924726 | 2.097039955 | 1.754972086 | 0.866875513 | 39/4494 |
| +2位 | 1.931482537 | 2.097150969 | 1.755059598 | 0.865514105 | 40/4494 |
| +4位 | 1.930945450 | 2.097175368 | 1.753638070 | 0.866748062 | 39/4494 |

+2/+4位meanTV相对下降0.157048%/0.014702%，但finalhidden中位均略退步，+2位Top1多错1个；+4位在原next32的meanTV反而略升。只说明该有界加位方案未取得一致改善，不推生产。全部不利尾部、同格式比较、参考漂移、各文档差值均保留。[完整报告](runs/R009/attempts/AT004_cpu_postprocess/analysis/report.md) · [Python对比PNG](runs/R009/attempts/AT004_cpu_postprocess/analysis/r009_precision_comparison.png)

所有prefix hash/动态编码/HostFP32恰好一次缩放/恢复及旧baseline/ref0全等检查通过。独立CPU复算252组finalhidden及54组可用pre-norm，固定63个FP64全词表head见证通过；没有声称其余pre-norm有全raw。独立实现窄审通过，Root最终整网审阅尚未记录。此前[R007等位宽RNE限定负结果](runs/R007/attempts/AT002_cpu_postprocess/analysis/report.md)保留。


---
Published: 2026-10-20T01:59:50.476253+00:00
Publication: P7e9133137795496d9d7404e57e4420b9
