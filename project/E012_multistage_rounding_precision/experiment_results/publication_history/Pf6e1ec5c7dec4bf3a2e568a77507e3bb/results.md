# E012 多级舍入：当前结果

execution_state: running（B001完成，Root有限后台队列Q001已启动）
verdict: inconclusive
applicability: 单模型、≤128真实token前缀；正式16/1024文档的五类局部对照与32层连续传播
review: A014已独立核查B001有限范围，不等于整体精度命题通过

Q001启动时已核快照（非实时）：B001实际完成16篇（web8/news4/reviews4）、1645 tokens，耗时484.948567秒/native0；peak RSS1937338368B、own GPU15619588096B，worker245181已回收，22消费源不变。每篇32 hidden、384 local、每臂192 dynamic坐标和final norm覆盖齐；没有padding、retokenize或重新选样。[真实收据](../experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/gpu_receipt.json) · [逐文档结果](../experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/paired_result.json)

这16篇最终Host RMSNorm的current-vs-output-only相对L2为**1.17394662%–1.78056073%**；预定audit文档为1.50156580%。这是参考信号归一化的表示误差，不是任务准确率下降。当前小批不用于估完整1024尾部、调整阈值或宣布精度保持。逐层传播与局部同码差保持分开。[hidden统计](../experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/document_summary.json) · [局部统计](../experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/local_document_summary.json) · [最终norm](../experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/final_norm_document_summary.json)

A014独审CPU9.97秒：16篇冻结input IDs/mask/positions逐值核对、全部文档32/384/192覆盖通过；预定audit的全32 hidden、dynamic metadata/预定values与384见证全部核验。独立整数/Fraction复算72064展开输出（Linear3584、RoPE2048、QK512、Softmax65408、PV512），current/reference零不符；38376适用界零违例。Softmax31720 valid、33688 causal-masked必须分列；不能用72064当有效输出或独立样本数。Linear622592完整组点积重算；这些是预定audit子集验证，不能外推全量逐元素界。[独审原件](../experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/independent_audit/A014_audit_R004_B001_result.json)

首批成本：一次装配约316秒，单篇非audit整对6.17–9.50秒，audit52.90秒；证据约211.1MiB。Root已据成本冻结后续至多48篇/组、两个剩余全32 raw hidden audit所在组至多32篇，均≤1audit，不按误差调整。64是固定logical batches数，不要求装载模型64次。新queue 12项CPU测试（3.626秒）通过，含准入不launch、cost stop、source变化、失败/缺覆盖、登记失败、总deadline不启动、partial日志及SIGTERM/SIGINT只清自有CPU dummy；Q001已由Root启动，A016未单独启动任何进程。

正式目标仍1024篇、103700 tokens；**启动时快照完成16、剩余1008（非实时）**。Root于2026-10-19T05:00:09.660291Z实际启动[Q001](../experiment_results/runs/R004/queues/Q001/root_launch_receipt.json)，队列PID/PGID260261、starttime7561672。冻结计划24组/1008篇、总墙钟23400秒；GPU worker按组在登记与新资源准入后启动，不能用队列PID代替GPU worker身份。

最新进度须核[队列事件](../experiment_results/runs/R004/queues/Q001/queue_events.jsonl)、各组durable document_result与终态收据；启动时[queue_receipt.json](../experiment_results/runs/R004/queues/Q001/queue_receipt.json)尚未生成。此文件未出现不代表已完成，也不由本摘要估算新增完成数。全部覆盖后才运行25次generic独审、全1024聚合、图和可读报告；未来[analysis/Q001/report](../experiment_results/runs/R004/analysis/Q001/report)为计划输出目录，当前不能称报告已完成。剩余实际数只能由固定成员、逐文档coverage ledger与终态核实；全队列exit0也不自动成为总体精度通过。总体固定域配额经验分布描述性；域内分位CI仍依赖声明的iid假设，n256的P99上端无界不能以samplemax代替。

历史四开发文档final norm为2.2210%、1.6430%、1.7555%、2.1527%；32token单dev为2.3901%，均不混正式分母。[AT010](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/paired_result.json)只支持开发范围。当前局部五类见证未独立覆盖SwiGLU/Host共同出口损失，不支持超128 token、多模型或ACC/PPL结论。
