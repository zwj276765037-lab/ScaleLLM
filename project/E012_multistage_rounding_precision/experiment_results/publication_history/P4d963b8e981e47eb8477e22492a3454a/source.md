# R007：重复舍入纠正候选

用户2026-10-20授权针对第32层输出快速优化。候选保留现有位宽/出口规则，将Linear组对齐及可选PV逐项右移改为最近偶数舍入；仅末层和全层分别比较。参考仍为原独立output-only中间高精度实现。开发前4篇初筛、其后32篇验证；不使用正式1024作候选选择。

[候选与验证合同](../experiment_results/runs/R007/optimization_contract.json) · [R007运行入口](../experiment_results/runs/R007/run.md)

---

以下保留R006及更早原算法基线历史。

# E012 R006 Softmax后TV：实际终态

execution_state: completed
verdict: inconclusive（无预设保真阈值，不作普遍精度保持断言）
applicability: 单模型、32层prefill、最多128真实token、固定配额1024文本、相同输入前缀

1024/1024篇、64/64组、103700真实位置×128256词表、温度1已实际测量。全部1024篇原head数值/数组及final-hidden SHA与R005精确相等；64核心+64扩展独审完成；15篇45行完整词表独立TV重算完成。每篇平均TV（概率质量%）：中位0.740003203，P95 1.17752086，P99 1.93750587，最大2.81020541。每篇最大TV的P95 8.62700373%，观测最大29.7200736%。两路概率质量最大缺陷3.20854454e-14。

[真实终态](../experiment_results/runs/R006/session_S001/session_receipt.json) · [后台驱动回执](../experiment_results/runs/R006/session_S001/background_driver_receipt.json) · [TV汇总](../experiment_results/runs/R006/analysis/aggregate_v2/tv_aggregate.json) · [最终PNG](../experiment_results/runs/R006/analysis/png_v3/final_precision.png)

TV百分比表示100×概率质量变化，与相对L2%不同。文档为统计单位；全位置统计另列为长度加权描述，固定配额合池仅描述；无ACC/PPL或自由生成结论。

Root终态审核与PNGv3目视已完成；128份独审报告/66个收尾回执/CSV坐标与分位/输出身份通过核查。v3仅修文字重叠，数据和曲线不变；不宣称普遍精度保持。


全103700位置TV（长度加权描述）：中位0.671020911%、P951.83018313%、P993.68184448%、最大29.7200736%。Top1一致102647/103700=98.9845709%。TV>5%为485位置，占0.467695%；>10%为65位置，占0.0626808%。文档等权曲线与位置分布口径分列。

---

以下为R005及更早已发布历史，不能覆盖R006当前状态。

# E012 多级舍入：当前来源与方法

execution_state: completed（R005 S001采集、64组独审、聚合与Python PNG绘图完成）
verdict: inconclusive（不作所有输出误差可忽略或普遍精度保持的结论）

2026-10-19 17:38:17（Asia/Shanghai）完整流水线结束，实际墙钟9946.915秒；GPU采集17:30:26结束，native0、worker已回收、冻结源未改变。1024/1024文档、64/64组、103700真实位置、13300147200对全词表分数；web512/news256/reviews256，无缺失文档。64核心与64扩展审查均已完成，15篇预选原始见证与其余文档统计/来源检查的范围分开陈述；不是所有完整张量独立重算。

全量结果：逐位置Top1一致102647/103700=98.984571%；文档等权98.994439%；整篇全部位置一致397/1024=38.769531%。全词表绝对差≤0.1的分数覆盖率98.130653%，≤0.2为99.844413%，≤0.5为99.991921%。末端隐藏向量相对L2中位数1.570580%、P95 2.847756%；最终词表分数相对L2中位数1.228031%、P95 2.207453%。这些不是任务ACC或自由生成一致性。

MLP每篇跨32层最大局部误差的P95（%）：Gate0.00709539、Up0.00918906、Down0.07167732、门控共同出口损失0.04570844、整个MLP分支0.16322653、同残差相加后0.09299327。门控项对同LUT精确乘积，其他局部项对共同出口的高精度中间参考。SiLU同表语义核验不表示解析函数近似误差为零。

PNG v2只修正底部说明重叠与两个分区标题；13×1024个点、分位值、整数计数和全部来源与v1一致。最终图已目视检查，原v1与冻结renderer保留。刚讨论的Softmax后完整概率分布TV尚未测得，不能标为本轮已完成指标。范围仅单模型、最多128个真实token、32层prefill；固定配额合池描述，分域区间依赖未验证iid假设。

[全局终态](../experiment_results/runs/R005/session_S001/session_receipt.json) · [最终PNG](../experiment_results/runs/R005/analysis/final_precision_png/png_v2/final_precision.png) · [汇总与源链](../experiment_results/runs/R005/analysis/final_precision_png/aggregate_v1/final_aggregate.json) · [数据表](../experiment_results/runs/R005/analysis/final_precision_png/aggregate_v1/quantiles.csv) · [版式一致性核查](../experiment_results/runs/R005/analysis/final_precision_png/png_v2/layout_validation.json)

## R005早期执行快照及更早实验（历史，以下不代表当前状态）


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

---
Published: 2026-10-19T10:47:27.458208+00:00
Publication: P4f772d6620aa48eba8d73ffab22f04fa


---
Published: 2026-10-19T14:38:23.712340+00:00
Publication: P068f821c64a7488d967cabf37f4c18d4


---
Published: 2026-10-20T00:47:19.270864+00:00
Publication: P8ceaca4d78834dcabf2692a9242f4736
