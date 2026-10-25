# AT028后控制边界修订的证据复用

AT028是真实生产层次、N128/64和完整K128/448的全部序列PASS。
其冻结源码在attempt/source_snapshot，之后两处生产RTL控制修订为
job_control和production_core；kernel/cache/parser/metadata/DMA数据与
ready/valid状态机均未改变。输入identity逐attempt记录，不能把SHA变化
直接忽略为所有控制行为均已验证。

| 范围 | 差异论证 | 采用证据 |
|---|---|---|
| GU/Down整数与物理W4/metadata/cache映射 | 未修改任何数值、调度、数据RAM或数据握手；production只增加全局故障诊断guard | AT021全部整数；AT028真实全层次全部byte |
| 正常成功、末B与自然排空 | 健康时paired/data fault为0，新owner在合法admission置1；selected_error在无故障/超时/abort/维护时恒0，正常phase/arm/fire/store_seen及数量断言不变 | AT028四个同epoch任务及最后B屏障；AT030同一4job公共接口与inclusive计数回归 |
| 原mid-compute ABORT和BRESP维护 | 原AT028实际外部事件→drain/维护/保留DONE链为PASS；新首错选择在这些非同时事件时给相同首码，owner为1，不引入控制反馈 | AT028真实ABORT及BRESP；不据此自动继承所有新优先级 |
| 同拍DRAIN+ABORT、新path+ABORT、先ABORT后LOAD错 | 新统一组合选择消除NBA旧值/覆盖，按已有首错→本拍paths→watchdog→ABORT→维护 | AT030单位：公开事件同拍注入，断言终态码/身份/计数；不以mock声称实际transport恢复 |
| 已有recoverable错后停流/超时 | active命令watchdog继续工作，超时升级严重性并保留旧码与已commit前缀 | AT030短timeout80，prefix4032B保持，FAULT后改变live输入不改变DONE |
| late fatal与匹配ACK同拍 | 跨phase严重性升级，ACK本拍fatal保护，未ACK DONE不重写 | AT030原成功DONE后同拍fatal/ACK拒绝及安全clear后ACK |
| idle fatal、过往身份与hard_clear | active_owned区分真实accepted owner与busy/global fault；无owner不造DONE，有owner未完成才补失败快照 | AT030保留旧descriptor后idle fault/clear无假DONE，active clear补2202，fatal+START同拍仍有1007响应 |
| 真实全局physical framing | paired/data全局fault进入job fatal和非quiet；不AND所有Attention的paired quiet，保持SHARED正常独立职责；global维护屏障不变 | AT031 focused真实DDR1早RLAST→global_freeze拒软清→core reset→GU完整gold重试，真实PASS，30529 checks/23820cycles/245760 metadataB，原始result保存 |

flow_stall与compute/store inclusive修订此前已包含在AT028，且AT027、AT030
以公开fire/done独立边沿计数。所有observer只进入计数，不反馈数据或控制。
Attention44源SHA不变，只能证明字节保持；没有并发Attention、生产全N
整数、综合或物理的额外结论。
