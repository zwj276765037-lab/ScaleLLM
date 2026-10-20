# E012 多级舍入：当前状态

execution_state: cost_stop（触发组G003；Q001终态stopped）
verdict: inconclusive
applicability: 本次队列未完成全1024；完整成功attempt112篇、独审16篇、terminal durable160篇须分开

Q001已于2026-10-19T05:45:16.832621Z停止。G003/AT005在单组900秒合同下运行896.240821秒后cost_stop：`assigned wall budget reached`，exit124/native−15；不是总deadline、256MiB、RSS或显存限制。worker284748已回收、source unchanged；旧证据与失败终态保留。

完成数快照：B00116篇成功且独审；G001/G002各48篇完整成功但队列后置独审未运行，所以成功attempt合计112篇、独审仅16篇。G003另48篇两臂逐文档32/384/192覆盖已durable落盘，但缺组末paired_result与local/final汇总，不能填成功/验收。Q001 terminal ledger的160=112+48，后续864篇未完成；全1024未完成，不作总体精度保持判定。

G003第48篇于05:41:44.504147Z完成，随后211.562秒收尾仍未完成；G001/G002最后文档后的收尾各约254秒。这定位到前向结束后的汇总/落盘区间，不凭时间戳指定具体慢函数或因果。六列依赖任务已于05:45:20.899357Z停止，render_result=null；全1024六列最终图未生成，现存16篇预览仍仅预览。后继MLP/logit扩展及新续跑计划尚未启动。

[只读停止报告](../experiment_results/runs/R004/analysis/Q001_stop_diagnosis_v1/stop_diagnosis.md) · [完整ID/证据SHA与续跑提案](../experiment_results/runs/R004/analysis/Q001_stop_diagnosis_v1/stop_diagnosis.json) · [队列终态回执](../experiment_results/runs/R004/queues/Q001/queue_receipt.json) · [六列依赖停止回执](../experiment_results/runs/R004/analysis/six_columns_after_queue/control/receipt.json)

以下保留Q001启动时的方法、结果与历史状态；其中“运行/16篇启动快照”不代表当前仍在运行。Root另行登记、publish与维护共享索引。

## Q001启动记录与既有证据（历史）

execution_state: running
verdict: inconclusive
applicability: 启动时快照正式16/1024篇已完成；Root已启动剩余1008篇有限队列，新增数须核durable证据
review: B001限定范围独审接受，无总体精度保持判定

B001已于484.948567秒/native0真实终态，worker245181回收，22消费源不变；正式16篇/1645真实tokens覆盖齐。最终norm相对L2范围1.17395%–1.78056%，不能填成精度通过。Root已登记completed并保存22源码版本；A014独立CPU核验原始tokens、全覆盖、audit384见证及适用界均无不符/违例。Q001已由Root实际启动，A016未自行启动/停止任何进程。

新run_formal_numerical_queue.py只新增独立入口与tests，既有22数值消费源未改。12项CPU资格通过（3.626秒），包含真实CPU dummy SIGTERM/SIGINT受控停止和无遗留；历史失败日志保留。入口要求Root明确冻结group_count/total_wall_seconds/precompleted B001和剩余全固定成员，逐组核身份/调用原bounded supervisor，每组结束且覆盖完整后才下一组。任何失败、准入不足、身份变化、成本停止或登记失败即停止并保全未完成IDs，不自动重试/扩预算。可选冻结后处理失败独立标analysis_failed。

Root已按冻结计划于2026-10-19T05:00:09.660291Z启动后台有限队列Q001：PID/PGID260261、starttime7561672；[真实启动回执](../experiment_results/runs/R004/queues/Q001/root_launch_receipt.json)。计划SHA102ed26d592574cfa20bd0bd39ff6b51bdb93d97c74044a9eb11badd2d757031，固定24组/剩余1008篇、单组≤48篇（剩余两全32 raw hidden audit组≤32）、≤1audit，总墙钟23400秒。启动时已完成16/1024仅是静态快照，不是实时数；当前活动GPU worker及新增完成数只看组启动和durable记录。每组仍CPU1/RSS8GiB/GPU24GiB/900秒/整AT256MiB，GPU0固定UUID，launch free≥30GiB/runtime free≥8GiB；外部进程不干预。固定64 logical batches可连续合并复用一次装配，不是64次固定模型加载。

统计与证据限制保持：正式1024只是目标，16个文档才是当前分母，不用scalar数量替代N。局部common-exit比较与连续传播分开；Host/SwiGLU独立节点损失、全量exact/strict逐输出界、超128 token及多模型均未证明。总体固定域配额不套iid合池CI；零信号与缺失不填0，失败样本不静默删除。ACC/PPL/任务非劣效、M003/M004、GPU1与EDA不在本轮范围。

最新证据入口：[queue_events.jsonl](../experiment_results/runs/R004/queues/Q001/queue_events.jsonl)逐组/逐文档事件，配合各attempt的document_result与gpu_receipt核对；[queue_receipt.json](../experiment_results/runs/R004/queues/Q001/queue_receipt.json)是未来终态回执，启动快照时尚未出现，不能先写成completed。后处理已冻结25次generic独审、完整聚合、图和可读报告，只有所有预定成员覆盖齐才执行；未来输出[analysis/Q001/report](../experiment_results/runs/R004/analysis/Q001/report)当前只是一条计划路径。分析失败与模型执行完成分开，不填精度通过。

三摘要由A016维护启动快照与证据入口，Root统一publish/登记/共享索引。历史开发、synthetic/BF16及失败attempt原件均保留。M005总体未完成。

Root实际启动复核（2026-10-19T05:02:47.610730+00:00）：G001已登记running，GPU工作进程260523的PID/启动身份由队列核实，首组源文档为B002–B004共48篇；原始资源与加载日志持续写入。模型权重290/290加载完成。此时尚无该组完成回执，正式已完成数仍保持16；不能将加载或运行中事件算成完成样本。


---
Published: 2026-10-19T05:02:49.754908+00:00
Publication: Pf6e1ec5c7dec4bf3a2e568a77507e3bb
Execution state: running
Research verdict: inconclusive
Applicability: Formal16/1024 startup snapshot verified; finite24-group queue for remaining1008 genuinely running on GPU0; five additional intermediate rounding nodes and32layer prefill,max128tokens,single model; no task metrics or numerical acceptance verdict.
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/gpu_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/paired_result.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/independent_audit/generic_v2.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/overview_v2/source_data.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/report_v2/report_manifest.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/preflight_queue/actual_plan_validation.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/preflight_queue/final_control_qualification.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/queues/Q001/root_launch_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/queues/Q001/queue_manifest.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/queues/Q001/G001/owned_worker.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT003_formal_group_g001_b002_b004/gpu_launch_manifest.json
