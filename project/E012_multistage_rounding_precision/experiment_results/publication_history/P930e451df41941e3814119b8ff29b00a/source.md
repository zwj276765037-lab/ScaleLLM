# E012 多级舍入：当前来源与方法

execution_state: cost_stop（触发组G003；Q001终态stopped）
verdict: inconclusive
applicability: 本次队列未完成全1024；完整成功attempt112篇、独审16篇、terminal durable160篇须分开

Q001已于2026-10-19T05:45:16.832621Z停止。G003/AT005在单组900秒合同下运行896.240821秒后cost_stop：`assigned wall budget reached`，exit124/native−15；不是总deadline、256MiB、RSS或显存限制。worker284748已回收、source unchanged；旧证据与失败终态保留。

完成数快照：B00116篇成功且独审；G001/G002各48篇完整成功但队列后置独审未运行，所以成功attempt合计112篇、独审仅16篇。G003另48篇两臂逐文档32/384/192覆盖已durable落盘，但缺组末paired_result与local/final汇总，不能填成功/验收。Q001 terminal ledger的160=112+48，后续864篇未完成；全1024未完成，不作总体精度保持判定。

G003第48篇于05:41:44.504147Z完成，随后211.562秒收尾仍未完成；G001/G002最后文档后的收尾各约254秒。这定位到前向结束后的汇总/落盘区间，不凭时间戳指定具体慢函数或因果。六列依赖任务已于05:45:20.899357Z停止，render_result=null；全1024六列最终图未生成，现存16篇预览仍仅预览。后继MLP/logit扩展及新续跑计划尚未启动。

[只读停止报告](../experiment_results/runs/R004/analysis/Q001_stop_diagnosis_v1/stop_diagnosis.md) · [完整ID/证据SHA与续跑提案](../experiment_results/runs/R004/analysis/Q001_stop_diagnosis_v1/stop_diagnosis.json) · [队列终态回执](../experiment_results/runs/R004/queues/Q001/queue_receipt.json) · [六列依赖停止回执](../experiment_results/runs/R004/analysis/six_columns_after_queue/control/receipt.json)

以下保留Q001启动时的方法、结果与历史状态；其中“运行/16篇启动快照”不代表当前仍在运行。Root另行登记、publish与维护共享索引。

## Q001启动记录与既有证据（历史）

按[v3数值协议](../../../mission/M005_multistage_rounding_precision/numerical_fidelity_protocol_v3.md)比较“当前实现”与“仅输出舍入”。只补数值精度，不重跑ACC/PPL。共享生产整数权重、基础量化、ScaleCode、LUT与共同出口；局部固定同一整数输入，连续两臂各自重算动态码。精确整数/Fraction参考只用于预定节点见证，不把BF16/QDQ轨迹冒充参考。

正式目标为固定1024文档簇（web512/news256/reviews256），train/dev各64互斥Wikipedia文章；文本/URL去重不证明语义iid或历史未曝光。原first64/128只作smoke。真实≤128 token前缀已在[AT009](../experiment_results/runs/R003/attempts/AT009_frozen_eval_token_stream_fix/frozen_document_stream.json)冻结：总103700 tokens，416篇不足128而未padding，1024前缀无相同token序列。[R004计划](../experiment_results/runs/R004/attempts/AT001_frozen_formal_input_plan/formal_batch_plan.json)保留原域内顺序，固定2web:1news:1reviews交织，64个logical batches。正式入口只核SHA读取原NPZ，不重新选样、retokenize或截短。

**Q001启动时快照：正式完成16/1024篇、1645真实tokens（非实时进度）**：B001为web8/news4/reviews4。每文档全32层hidden、384 local坐标、每臂192 dynamic准备坐标与final norm统计，完成前有唯一坐标覆盖断言。局部五类为7个Linear site、query/key RoPE、QK、Softmax、PV。QK含causal未来score，Softmax只统计valid keys；分母不可合并。GPUobserver只给common-exit局部比较与聚合audit，不能称全量strict/exact逐输出界。

活动唯一代码根project/software/0_Software/rounding_precision，B001实际消费22源已由Root按运行hash保存。逐tensor加载、同一V5实例、HF5兼容桥与生产row-chunk128量化，Attention03/MLP05、Down S32/shift12/S45/S54；LMhead不加载或调用。每组CPU1/RSS8GiB/GPU24GiB、900秒、整AT256MiB，GPU0仅Root准入/监督。具体合并连续logical batches用于复用一次装配，不改变文档、审计身份或统计单位。

预定15审计文档的storage addendum绑定原计划：每域第一个audit保留全32 raw hidden，其余12保留层0/15/31与final norm；所有audit的dynamic metadata、节点见证覆盖全32层，dynamic values只层0/15/31。每坐标预选16点并保存完整依赖（Linear全128/448组、RoPE pair、Softmax整行），witness64MiB/doc与96MiB/AT不代替整AT256MiB。B001预定audit c4:6896全32 hidden及384见证均保存并已独审。

统计单位为文档簇：先合并能量E/S、signed sum/count再算relativeL2%=100sqrt(E/S)、normalized signed bias%、RMSE/max及signalRMS。零信号比值null，0/0匹配与正误差/零信号分开，不加epsilon或结果后通过阈值。每文档跨32层/site最大与五类总最大按[数值合同](../../software/0_Software/rounding_precision/source/numerical_fidelity_contract_v3.md)处理。总体固定域配额只描述性，域内iid为条件模型；P99有限上界与joint family按[不确定性合同](../../software/0_Software/rounding_precision/source/numerical_quantile_uncertainty.md)报告。

Root已于2026-10-19T05:00:09.660291Z启动有限后台队列Q001，PID/PGID260261、starttime7561672；[启动回执](../experiment_results/runs/R004/queues/Q001/root_launch_receipt.json)绑定冻结queue_plan_v2（SHA102ed26d592574cfa20bd0bd39ff6b51bdb93d97c74044a9eb11badd2d757031）。剩余1008篇固定为24组，总墙钟23400秒；每组≤48篇、至多1audit，剩余两个全32 raw hidden audit所在组≤32篇。新queue串行调用既有bounded_gpu_run，核precompleted B001与逐文档覆盖；每组重新准入，任一失败/身份变化/成本停止即停，不重试或扩预算。队列启动不代表每组GPU worker已启动。

实时证据位置为[queue_events.jsonl](../experiment_results/runs/R004/queues/Q001/queue_events.jsonl)及各预定attempt的durable document_result/终态回执；[queue_receipt.json](../experiment_results/runs/R004/queues/Q001/queue_receipt.json)只在队列终态生成，此启动快照时尚未出现，不可当成已完成。只有全部固定成员与coverage齐全，才依序执行冻结的25次generic独审、完整聚合、图和可读报告。未来输出位置为[analysis/Q001](../experiment_results/runs/R004/analysis/Q001)，其中report/为计划报告目录，目前不构成已产出报告。执行完成仍不等于精度保持；独立SwiGLU/Host损失、超过128 token和其他模型泛化均不在当前已证范围。

历史：R003四dev与先前32token成本资格独立保留；R001/R002只支持合成/BF16局部，失败attempt不覆盖。[AT010开发证据](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/paired_result.json)不计入正式16篇。


---
Published: 2026-10-19T05:02:49.754908+00:00
Publication: Pf6e1ec5c7dec4bf3a2e568a77507e3bb
