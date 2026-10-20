# E012 多级舍入：当前来源与方法

execution_state: running（R005 S001；2026-10-19T07:35:34.627809+00:00已核271/1024篇durable、16/64组执行完成）
verdict: inconclusive

进度快照（UTC 2026-10-19T07:35:34.627809+00:00，一次有界只读核查）：已观察到271/1024篇独立文档的完整durable结果；16/64组已有completed执行片段回执，覆盖256篇，当前G017运行中。每篇durable结果核对32层hidden、384局部坐标、每臂192动态坐标、416 MLP坐标和全部真实T×128256词表位置；这些是执行覆盖，不是最终独审或精度成功。共享worker330520身份与pid/pgid/starttime/argv记录一致，global GPU终态、analysis_manifest与session终态尚未出现，完整1024独审/汇总/最终图仍待同一冻结pipeline自然完成。此数字是带时间戳的快照，不是实时计数；A016没有持续监控或启动新运行。

[本次进度核查记录](../../../agent/A016/r005_progress_snapshot_20261019T073534Z.json) · [组级进度](../experiment_results/runs/R005/session_S001/group_progress.json) · [逐文档运行日志](../experiment_results/runs/R005/session_S001/session_stdout.log)

applicability: 当前时间戳快照271/1024篇durable、组终态覆盖256篇；完整正式集合及最终独审尚未完成，精度inconclusive

用户要求的MLP/全词表补测正在R005执行，旧R004/Q001失败证据和冻结源码保持原样。R005沿用同1024冻结文档/token、同权重/模型/32层数值规则；全部1024均需新扩展测量，不把旧成功112或durable160计入扩展完成数。Top1为固定前缀预测一致性，不是有标签ACC；ACC/PPL不重跑。

[AT001成本资格](../experiment_results/runs/R005/attempts/AT001_cpu_summary_cost_qualification/evidence/original_tmp_execution/summary_cost.json)已真实完成并登记：CPU3.116538秒/native0；旧48篇footer触发约417万次bootstrap分位调用。完整48篇关闭批内bootstrap后0.745664秒，所有原点指标/计数精确一致。新入口只在批内计算点统计，完整集合置信推断留CPU统一处理。

[AT002真实GPUpilot](../experiment_results/runs/R005/attempts/AT002_extended_mlp_logits_pilot/gpu_receipt.json)于06:30:21.594150–06:37:59.324022Z completed/native0，457.664067秒；worker313807已回收、26消费源不变，peak RSS4328800256B、GPU15678308352B，证据约195.27MiB。4篇dev0..3实际tokens[128,14,128,128]；每篇32 hidden/384 local/每臂192 dynamic/416 MLP/全部T×128256 logits覆盖齐。载模41.316秒、attach319.157秒、head4.398秒；audit首篇58.769秒、普通128篇7.726/7.634秒、14token篇5.244秒。这些成本不承诺所有新长度相同。

[只读对照](../experiment_results/runs/R005/attempts/AT002_extended_mlp_logits_pilot/readonly_baseline_qualification.json)确认4篇旧hidden/local指标和全部动态字段SHA不变，预定auditdoc0的66个两臂raw数组逐字节一致，无第三整网前向。[A014独审](../experiment_results/runs/R005/independent_review/AT002_extended_audit_v1.json)6.720秒完成：head原BF16来源、3个全词表审计位置、产品/Host整数spot和旧节点见证已核。MLP完整分支仍是生产统计与有限配对spot，不声称全分支独立重执行；GPU FP32 head roundoff独立诊断，不混入额外中间舍入。

正式阶段采用新有限常驻GPUworker，一次装配顺序消费原64个逻辑16doc组；每组保留真实execution receipt，唯一global GPU launch/receipt，不伪造组独立GPU运行。Root已于2026-10-19T06:51:49.381852Z实际启动正式有限stage，supervisor330188；shared worker330520/PGID330520/starttime8235802于06:52:30.965543Z实际启动，启动时G001装配（当前进度见上方时间戳快照）；启动时扩展完成0/1024是静态快照，不是实时进度。新框架10项CPU资格、A014最终独审和全部64组/1024篇/103700tokens实际CPU计划核验均通过；总wall14400秒、global6144MiB、67条独审/汇总/绘图CPU收尾均已冻结。唯一真实GPU会话采用session_S001，组AT003..066只是同一worker的执行片段，不伪造组GPU launch。新source/plan/finalizer均保持冻结。CPU1/RSS8GiB/GPU24GiB/free保护不增加，单组900秒/256MiB不变；完整图只能据全部1024覆盖及独审重新生成。

[Root正式启动回执](../experiment_results/runs/R005/session_S001/root_launch.json) · [冻结计划与30源身份](../experiment_results/runs/R005/qualification/persistent_source_v1/source_ready.json) · [实际全计划CPU核验](../experiment_results/runs/R005/qualification/persistent_source_v1/final_plan_validation.json)。运行进度只看session_S001逐文档日志、group_progress和各组execution_receipt；session_gpu_receipt、analysis_manifest及最终session_receipt尚未生成前不视作完成。最终输出位置为R005/analysis/final_precision_png/png_v1，当前尚无正式1024最终图。

## R004/Q001停止快照与早期证据（历史）

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


---
Published: 2026-10-19T06:03:23.169985+00:00
Publication: P930e451df41941e3814119b8ff29b00a
