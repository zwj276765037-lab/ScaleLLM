

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E012 / R003 运行结果

[负责人维护的本批运行记录](run.md)

# R003 — 纯数值保真实现与资格

本批次按用户最新范围只验证多次位宽舍入的数值误差，ScaleCode方法ACC保持已有结果。

状态：输入及节点参考资格已完成；单开发文档完整32层数值资格已完成并独立复算，4开发文档的范围与吞吐检查也已完成并独立审核。正式1024文档已冻结token输入，数值测量仍为0。结论inconclusive，不能写总体精度保持。

- AT001：真实来源去重与冻结，eval1024、train/dev各64；只准备输入。
- AT002：旧BF16数组包装成功，首重放因JSON序列化错误自然失败，原件保留。
- AT003：实际GPU六项精确参考测试通过，三Linear格式、RoPE、QK、Softmax、PV及上下文恢复。
- AT004：修复数组序列化后168旧真实输出全部合法，两组理论界无违例；独立Fraction及指标复算一致。仅1旧工程文档，formal0。
- AT005：300秒成本pilot于295.227秒停止，只完成17/32层量化装配，无前向结果。原进程已回收。
- AT006：三真实完整权重矩阵×三分块规格，q/code/shift哈希全部与原生产量化相同；chunk128提速约1.4–1.54倍。
- AT007：按实测成本另立900秒上限，实际315.132秒正常完成；CPU1、RSS峰值1.855GiB、GPU峰值14.602GiB，进程已回收且运行源不变。单开发文档32tokens、384局部算子单元与全32层hidden；局部同输入相对L2最大0.085331%，末层输出2.178868%，最终归一化后2.390086%。存在真实传播累积，不能据此宣称无损或总体数值精度保持。32层hidden原始数组、动态编码及文件身份已独立复算；局部全量统计尚不等于独立逐码复算。
- AT008：正式1024文档CPU token准备因产物命名碰撞失败；原始证据保留，未做数值推理。
- AT009：修复命名后1024文档token输入冻结成功；网页512、新闻256、评论256，共103700真实token，每文档最多128，短文保留实际长度。这里只准备输入，正式数值测量为0。
- AT010：四开发文档检查已于2026-10-19 04:18:47Z正常完成，374.403秒、native0、源码与共享权重不变、worker已回收。独立文档4，真实长度128/14/128/128，共398tokens；1536局部单元与128个逐层hidden完整。局部相对L2最高0.095073%，四篇最终归一化输出分别2.221033%、1.642960%、1.755511%、2.152683%。预定doc0的32层原始hidden、动态元数据和384份节点见证已独立复算；五类展开71936个标量，其中3895

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_clean_document_manifest](attempts/AT001_clean_document_manifest) | completed | 1024 eval documents plus disjoint train/dev64 each; source/text/URL clustering only, no numerical inference yet; near-duplicate independence and all-history exposure not certified | [执行收据](attempts/AT001_clean_document_manifest/run.json) · [report.md](attempts/AT001_clean_document_manifest/report.md) |
| [AT002_legacy_array_pipeline_qualification](attempts/AT002_legacy_array_pipeline_qualification) | failed | engineering-only pipeline: pack succeeded; replay naturally failed diagnostic ndarray JSON serialization. No formal evaluation, no scientific method rejection. | [执行收据](attempts/AT002_legacy_array_pipeline_qualification/run.json) · [report.md](attempts/AT002_legacy_array_pipeline_qualification/report.md) |
| [AT003_gpu_reference_qualification](attempts/AT003_gpu_reference_qualification) | completed | 6 actual CUDA tests passed; 969 Linear outputs, 9 independent Fraction spots; not a model fidelity or statistical evidence result | [执行收据](attempts/AT003_gpu_reference_qualification/run.json) · [report.md](attempts/AT003_gpu_reference_qualification/report.md) |
| [AT004_array_replay_serialization_fix](attempts/AT004_array_replay_serialization_fix) | completed | CPU array pipeline qualification only: 1 legacy BF16 prompt,21 tensors,168 outputs valid,bounds applicable168/violations0; formal eval documents0 | [执行收据](attempts/AT004_array_replay_serialization_fix/run.json) · [report.md](attempts/AT004_array_replay_serialization_fix/report.md) |
| [AT005_paired_32layer_numerical_pilot](attempts/AT005_paired_32layer_numerical_pilot) | cost_stop | 17/32 layers attached; no forward, hidden output, or numerical fidelity conclusion; bounded preparation cost stop | [执行收据](attempts/AT005_paired_32layer_numerical_pilot/run.json) · [report.md](attempts/AT005_paired_32layer_numerical_pilot/report.md) |
| [AT006_row_chunk_quantization_qualification](attempts/AT006_row_chunk_quantization_qualification) | completed | CPU three actual full weight matrices, 9 chunk configurations, q/code/shift SHA all identical; loading optimization qualification only | [执行收据](attempts/AT006_row_chunk_quantization_qualification/run.json) · [report.md](attempts/AT006_row_chunk_quantization_qualification/report.md) |
| [AT007_complete_paired_numerical_qualification](attempts/AT007_complete_paired_numerical_qualification) | completed | 1 development doc32tokens/full32layers:384 local common-exit cells and paired4096-channel hidden; last layer2.1788677%,final host RMSNorm2.3900856%; no formal evaluation, no generic precision pass | [执行收据](attempts/AT007_complete_paired_numerical_qualification/run.json) · [report.md](attempts/AT007_complete_paired_numerical_qualification/report.md) |
| [AT008_frozen_eval_token_stream](attempts/AT008_frozen_eval_token_stream) | failed | CPU token preparation wrote1024 arrays but payload name collided with supervisor manifest; no numerical inference | [执行收据](attempts/AT008_frozen_eval_token_stream/run.json) · [report.md](attempts/AT008_frozen_eval_token_stream/report.md) |
| [AT009_frozen_eval_token_stream_fix](attempts/AT009_frozen_eval_token_stream_fix) | completed | CPU frozen1024 eval document token arrays; true unpadded prefix lengths<=128; numerical measured documents0 | [执行收据](attempts/AT009_frozen_eval_token_stream_fix/run.json) · [report.md](attempts/AT009_frozen_eval_token_stream_fix/report.md) |
| [AT010_four_document_numerical_development](attempts/AT010_four_document_numerical_development) | completed | 4 development documents,all32 layers,384 local common-exit cells/doc; finalnorm relativeL2 2.2210/1.6430/1.7555/2.1527%; formal measured0;384 node witness coordinates independently audited | [执行收据](attempts/AT010_four_document_numerical_development/run.json) · [report.md](attempts/AT010_four_document_numerical_development/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
