# E012 R007：真实运行状态

execution_state: running

verdict: inconclusive

applicability: 等位宽RNE隔离软件候选；dev4初筛完成，next32开发验证尚未完成。

A019 worker PID/PGID864316，UTC2026-10-20T00:45:49.857真实启动；CPU/GPU原语均PASS；单模型装配和前4文档完成。Linear-last1为provisional候选，next32已自动启动，最近持久结果显示完成8/32验证文档。所有动态编码每臂独立执行192坐标，生产buffer签名不变。

无已知阻塞，未扩大候选/全1024/GPU范围。原生命周期observer因Python缺少pidfd API失败已保留；v2 Linux syscall observer PID865543已真实打开目标pidfd，最终OS退出/回收/GPU释放证据待进程结束。实际模型/effort未核实时保留未核实。

下一步：完成全部next32，核真实退出、CPU原始hidden/JSON独立复算、Python对比PNG及终态摘要，Root最终审阅尚未发生。

[实际启动](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/actual_launch.json) · [实时持久状态](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/status.json) · [原始指标](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/metrics.jsonl)


---
Published: 2026-10-20T00:54:20.722145+00:00
Publication: P4d963b8e981e47eb8477e22492a3454a
Execution state: running
Research verdict: inconclusive
Applicability: R007 dev4/398positions筛选完成，Linear-last1 provisional，next32dev验证进行中；无全1024/ACC/PPL/RTL时序结论
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/selection_summary.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/selection_decision.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/r006_baseline_parity.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/actual_launch.json
