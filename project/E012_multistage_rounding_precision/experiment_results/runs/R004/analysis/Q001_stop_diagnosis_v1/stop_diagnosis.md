# Q001 停止原因：只读终态核查

核查时间2026-10-19T06:01:26.877717+00:00。不启停进程、不改源码/计划、不重跑模型。

## 精确停止原因

G003/AT005触发单组900秒预算，监督器在895秒预留退出后实际896.240821秒收尾，exit124/native−15，stop_reason=`assigned wall budget reached`。这是单组cost_stop；Q001因此stopped。队列总墙钟2707.120秒远小于23400秒，不是总deadline。

AT005证据69322263B（约66.11MiB）小于256MiB；peakRSS2008743936B小于8GiB，peakGPU15619588096B小于24GiB，最小GPU free35266756608B高于8GiB。source_unchanged=true/worker_reaped=true；worker284748、supervisor284742、queue260261核查时均无/proc记录。

## 完成数严格分开

|范围|文档数|资格|
|---|---:|---|
|B001|16|成功且A014独审|
|G001/AT003|48|完整成功；队列后置独审未运行|
|G002/AT004|48|完整成功；队列后置独审未运行|
|G003/AT005|48|durable两臂文档完整，但整组cost_stop|
|未完成剩余|864|后续组未启动|

因此完整成功attempt共112；terminal durable ledger160包含失败attempt的48篇，不等于160验收。完整ID列表见stop_diagnosis.json的completed_durable_document_ids/not_completed_document_ids/failed_attempt_durable_document_ids。

## 为什么48篇前向都结束仍触限

|组|加载/装配秒|文档前向区间秒|最后文档到终态秒|组耗时秒|
|---|---:|---:|---:|---:|
|G001|304.702|335.396|254.846|894.878|
|G002|315.311|296.403|254.260|865.908|
|G003|321.433|363.307|211.562|896.241|

G003最后文档在05:41:44.504147Z完成，停止在05:45:16.066341Z，之间211.562秒。hidden document_summary已生成，local_document_summary/final_norm_document_summary/paired_result未生成，末尾无completed stage。G001/G002同一收尾区间约254秒。事实定位到前向之后的汇总/落盘收尾；未做CPU profiler，不能仅凭时间戳断言具体函数或系统争用原因。

## 六列依赖任务

依赖任务于05:45:20.899357Z停止：`original numerical queue did not complete successfully`；render_result=null、gpu_started=false，PID273406核查时已不存在。未生成figure_six_columns_final；已有16篇预览图不能冒充全1024最终图。Q001 analysis_results为空，25次后置独审/全量聚合/正式图/报告未运行。

## 最小可行延续建议（仅提案，不启动）

保持旧Q001与AT005原始终态。新计划可承认成功前缀B001–B007的112篇（先补G001/G002独审），从B008起按原57个16篇logical batch独立分组：剩余912篇包含G00348篇重测，成员/顺序/审计不变，每次900秒/CPU1/RSS8GiB/GPU24GiB/整AT256MiB。16篇B001实测484.949秒、收尾2.133秒，具更多成本余量；估算单组约500–600秒，实际受新MLP覆盖和资源负载影响，不能保证。57组阶段墙钟cap合计51300秒是上限而非预计耗时，新全局有限预算需Root重新冻结。

32篇选项应先仅CPU核收尾成本再确定；现存48篇已接近/撞上900秒，不能直接沿用。若以后从AT005原始48篇仅CPU恢复汇总，必须新派生证据与明确资格合同，旧cost_stop不得改为成功或伪造成功收据。本报告不做恢复、不写新runner。

具体freeze-ready logical batch/ID列表、来源SHA及各组原始证据路径见JSON。
