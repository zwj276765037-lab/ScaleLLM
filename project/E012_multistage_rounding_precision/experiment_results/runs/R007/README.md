

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E012 / R007 运行结果

[负责人维护的本批运行记录](run.md)

# R007 — 等位宽舍入纠正开发验证

Execution state: completed（GPU实际0退出，CPU后处理真实0退出）

Verdict: inconclusive；本批没有验证出全面改善，不推广生产。Root最终审阅待记录。

实际完成dev4/398位置三候选初筛及last1的next32dev/4096位置验证。baseline/reference前4与R006双hidden哈希、L2、Top1、TV全等。next32 meanTV0.867630920→0.866613218%，第32层pre-norm L2中位1.940032317→1.939197037%；但finalhidden中位2.097337280→2.098582422%、Top1错35→36/4096、TVP99上升。全部不利文档与尾部保留，未作末端reference校准。

CPU17059例及GPU511向量/30Linear/256PV资格PASS；源码与位宽边界保持。36文档/116完整forward/80配对全部完成，source SHA复核不变。GPU阶段665.205s；峰值allocated14.197GiB/RSS1.763GiB，总证据约417MiB。PID864316于00:57:01.272Z被pidfd观测实际退出（Linux/proc exit_code0），随后回收且GPU无该PID；所有CPU子进程已wait/reaped。

80组NPZ独立hidden复算与18个固定CPU FP64head见证通过；Python PNG生成并目视检查。FP64head见证是选定位置数值核查，非全部位置bitwise证明。

[合同](optimization_contract.json) · [完整报告](attempts/AT002_cpu_postprocess/analysis/report.md) · [对比PNG](attempts/AT002_cpu_postprocess/analysis/rounding_comparison.png) · 原始结果（原文引用：`attempts/AT001_rne_equalwidth_dev36/result.json`；待核实） · [真实GPU退出](attempts/AT001_rne_equalwidth_dev36/external_lifecycle_receipt_v2.json) · [CPU后处理收据](attempts/AT002_cpu_postprocess/execution_receipt.json) · [固定head见证](attempts/AT002_cpu_postprocess/head_witness/independent_head_witness.json)

适

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_rne_equalwidth_dev36](attempts/AT001_rne_equalwidth_dev36) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT001_rne_equalwidth_dev36/manifest.json) |
| [AT002_cpu_postprocess](attempts/AT002_cpu_postprocess) | 未登记；查看原记录 | 未登记 | [manifest.json](attempts/AT002_cpu_postprocess/manifest.json) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
