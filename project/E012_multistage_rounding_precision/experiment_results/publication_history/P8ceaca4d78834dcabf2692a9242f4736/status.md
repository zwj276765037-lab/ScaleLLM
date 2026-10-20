# R007：实现与独立审核进行中

execution_state: running
verdict: inconclusive
applicability: 开发4篇初筛与另外32篇验证的候选工程阶段；尚未GPU整网运行

真实工程agent rounding_optimization_runner使用gpt-6.1-sol/xhigh；rounding_reference_implementation独立审阅关键整数规则。GPU0有界单驻留阶段上限2400秒，CPU1/RSS8GiB/GPU24GiB。原冻结源码及证据保留。

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

# E012 多级舍入：当前状态

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


---
Published: 2026-10-19T06:03:23.169985+00:00
Publication: P930e451df41941e3814119b8ff29b00a
Execution state: failed
Research verdict: inconclusive
Applicability: Q001 collection cost-stopped during G003 CPU summary;112 documents in successful attempts,16 independently audited;160 durable includes48 in failed attempt;1024 target incomplete. MLP three projections split for audited16; additional MLP nodes/logits/top1 agreement are required but not newly measured.
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/queues/Q001/queue_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/analysis/Q001_stop_diagnosis_v1/stop_diagnosis.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/analysis/mlp_precision_v1/mlp_projection_summary.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R004/run.md

---
Published: 2026-10-19T10:47:27.458208+00:00
Publication: P4f772d6620aa48eba8d73ffab22f04fa
Execution state: completed
Research verdict: inconclusive
Applicability: 1024 frozen documents,103700 real prefix positions,32 layers,max128tokens;all64groups audited within explicit raw-witness scope;13-column Python PNG complete;no universal fidelity,taskACC,decode or post-softmax TV claim
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R005/session_S001/session_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R005/session_S001/session_gpu_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/aggregate_v1/final_aggregate.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/png_v2/output_manifest.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R005/analysis/final_precision_png/png_v2/layout_validation.json


---
Published: 2026-10-19T14:38:23.712340+00:00
Publication: P068f821c64a7488d967cabf37f4c18d4
Execution state: completed
Research verdict: inconclusive
Applicability: R006 full1024 frozen documents,103700 real prefix positions,max128tokens,32layers,temperature1;all128 group audits complete;45 raw full-vocabulary rows independently recomputed;single integrated Python PNGv3;no universal fidelity/taskACC/free-generation claim
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R006/session_S001/session_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R006/session_S001/background_driver_receipt.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/aggregate_v2/tv_aggregate.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/png_v3/output_manifest.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R006/analysis/png_v3/layout_validation.json
- project/E012_multistage_rounding_precision/experiment_results/runs/R006/independent_review/root_final_review.json


---
Published: 2026-10-20T00:42:54.110100+00:00
Publication: Pe744793cad264a90b3bc0bfc4eef11e5
Execution state: running
Research verdict: inconclusive
Applicability: R007 independent development candidate; no optimized model result yet
Evidence:
- project/E012_multistage_rounding_precision/experiment_results/runs/R007/optimization_contract.json
