# E012 R009：执行完成，停止后续优化

execution_state: completed

verdict: inconclusive

适用范围：同一组已用36开发文档的限定数值试验，非新heldout、非1024正式结论；没有ACC/PPL、RTL资源/频率或普遍无损证明。两档均全测，没有按结果丢弃文档。

AT003自然native0，外部pidfd观测Linux退出状态0、/proc消失；所有所属GPU/CPU进程已退出。含两次模型加载前资格失败的GPU阶段855.183秒，小于2400秒；只装模型一次。独立CPU分析/见证均native0且parent wait/reaped。全部消费源30项终态SHA无变化，R009证据约401MiB小于512MiB。

用户最新范围仅核验末层逐数舍入before/after、dropbits和大误差比例；当前仅盘点已有证据，没有后继GPU/候选搜索。R006的1024×12site仅tensor aggregate；15audit文档有完整量化输入可补取逐数统计，但尚未启动补测。直接同输入局部误差与前31层输入传播差必须分别报告。

[实际退出](../experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/external_lifecycle_receipt_v2.json) · [独立复核](../experiment_results/runs/R009/attempts/AT004_cpu_postprocess/analysis/independent_checks.json) · [完整结果](../experiment_results/runs/R009/attempts/AT004_cpu_postprocess/analysis/report.md)


---
Published: 2026-10-20T01:59:50.476253+00:00
Publication: P7e9133137795496d9d7404e57e4420b9
Execution state: completed
Research verdict: inconclusive
Applicability: R009 six-arm repeated development36/4494 positions; tiny mixed improvements, no production adoption or global-method refutation; latest work is read-only lastlayer evidence inventory
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/lastlayer_precision_contract.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/result.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/external_lifecycle_receipt_v2.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT004_cpu_postprocess/analysis/report.md
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT004_cpu_postprocess/analysis/independent_checks.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT004_cpu_postprocess/head_witness/head_witness.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R009/independent_review/A015_implementation_review.md
