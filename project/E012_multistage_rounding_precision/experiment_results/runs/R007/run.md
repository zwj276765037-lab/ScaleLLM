# R007 — 等位宽舍入纠正开发验证

Execution state: completed（GPU实际0退出，CPU后处理真实0退出）

Verdict: inconclusive；本批没有验证出全面改善，不推广生产。Root最终审阅待记录。

实际完成dev4/398位置三候选初筛及last1的next32dev/4096位置验证。baseline/reference前4与R006双hidden哈希、L2、Top1、TV全等。next32 meanTV0.867630920→0.866613218%，第32层pre-norm L2中位1.940032317→1.939197037%；但finalhidden中位2.097337280→2.098582422%、Top1错35→36/4096、TVP99上升。全部不利文档与尾部保留，未作末端reference校准。

CPU17059例及GPU511向量/30Linear/256PV资格PASS；源码与位宽边界保持。36文档/116完整forward/80配对全部完成，source SHA复核不变。GPU阶段665.205s；峰值allocated14.197GiB/RSS1.763GiB，总证据约417MiB。PID864316于00:57:01.272Z被pidfd观测实际退出（Linux/proc exit_code0），随后回收且GPU无该PID；所有CPU子进程已wait/reaped。

80组NPZ独立hidden复算与18个固定CPU FP64head见证通过；Python PNG生成并目视检查。FP64head见证是选定位置数值核查，非全部位置bitwise证明。

[合同](optimization_contract.json) · [完整报告](attempts/AT002_cpu_postprocess/analysis/report.md) · [对比PNG](attempts/AT002_cpu_postprocess/analysis/rounding_comparison.png) · [原始结果](attempts/AT001_rne_equalwidth_dev36/result.json) · [真实GPU退出](attempts/AT001_rne_equalwidth_dev36/external_lifecycle_receipt_v2.json) · [CPU后处理收据](attempts/AT002_cpu_postprocess/execution_receipt.json) · [固定head见证](attempts/AT002_cpu_postprocess/head_witness/independent_head_witness.json)

适用范围仅开发选择与另一组开发验证；无heldout正式1024、任务ACC/PPL、RTL实现或时序结论。原生产v5与R001–R006冻结源保留。初始/运行中管理记录见[终态前run快照](attempts/AT002_cpu_postprocess/previous_run_record.md)。
