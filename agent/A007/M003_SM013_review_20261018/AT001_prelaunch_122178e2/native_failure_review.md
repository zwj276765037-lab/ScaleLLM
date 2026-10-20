# AT001 原生局部结果与自然失败独立审核

2026-10-18；A007。execution：本次只读诊断尝试自然失败，独立有界终态审核完成；verdict：原生 route 计数和必需 schema 已确认，canonical census / G1 未完成，优化方法仍未评估；applicability：E009/R001/AT001、122178e2 固定包和原失败图；review：内部审核，已实际报告 Root/A006，不是用户全局验收。

## 已闭合原生事实

- `OPEN_CHECKPOINT_COMPLETE` 为 00:49:28Z；本次原生 route report：logical 7145555、routable 2031733、fully routed 1484185、routing errors/resource conflicts 均547548，与 E008 基线口径一致。report 714 B / SHA256 `ac53eab23be7a99d351f58e54b64a36c4cc2a74da045437efd0f28e5a3546b28`。
- 原生 schema 的 net NAME/ROUTE_STATUS、pin NAME/DIRECTION/IS_LEAF/IS_CLOCK/REF_PIN_NAME、cell NAME/REF_NAME/LOC/BEL/IS_PRIMITIVE 均存在；route enum 含 CONFLICTS。schema 77915 B / `62b45def35e8806a475744f51edbf5ca16446c3dde5123b0ecbad945384032d5`，enum 138 B / `24f2cbf314d8a5ba14492148b9caaed40a057249ff3e109e0e94362834636561`。属性存在不代表其返回值/segment 集合已验收。
- CELL_INVENTORY_COMPLETE 为 00:53:05Z；随后第一次 parent_head_r[0] 补充网 alias 调用在 `native segment NAME/handle alignment` 检查失败。原生错误和调用栈保留在 native_error.tcllist，canonical 全量网清单及后续 deep 阶段未到达。
- Vivado 于 00:53:09Z 退出，监督终态 00:53:21.909734Z：native1/supervisor1，stop_reason=null，natural terminal=true，无 cleanup、无 owned survivors，post_integrity_error=null。独立重算资源样本的 RSS 峰值、最低内存余量和磁盘余量与 status 一致；核验时全部原 tracked PID/start 及 supervisor 身份不存在，旧监督器不持锁。见 `native_failure_review.json`。

本次未重新读取/hash DCP 或144输入；运行前后完整身份保持是 A006 监督器记录归因，沿用已审检查源码。A007只核本阶段闭合小报告、错误、资源记录和进程身份，不把部分 cell 库存当 G1 完成。

## 失败定位与最小修复依据

当前 alias 检查用 `$names ne $seg` 比较两个 Tcl 列表的字符串表示。独立最小反例使用同一 parent_head_r[0] 名称：raw NAME 字符串与 lsort/list 结果的 llength 均1、逐元素相等，但该字符串比较为真。反例代码与实际输出分别保存在 `list_representation_counterexample.tcl` / `.txt`，CPU exit0。

这证明检查存在表示层误拒绝的可能；原失败没有保存左右值，不能据此宣称具体 native pair 已证相等。建议保持长度/逐元素 NAME 身份检查，增加首个实际配对和异常配对的有界回执；不要删资格检查或放松 canonical/alias 闭包一致性。

按已有授权保留 AT001 后修复同范围新 AT，仅对改动及受影响语义增量审核。无需新用户批准；不复用旧停止例外、不扩大查询范围。G1 数据收集尚未完成，任何候选的选入/排除或物理收益结论都不从这次工具适配失败得出。
