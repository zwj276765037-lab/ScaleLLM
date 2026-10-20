# E009：AT001自然失败于别名资格检查，G1未完成

2026-10-18 00:53:21.909734Z监督结束，native1/supervisor1，stop_reason=null、无cleanup/残留，post_integrity_error=null。00:49:28Z载图完成、00:53:05Z全量cell库存完成；随后第一个parent_head_r[0]的alias检查因`names ne seg`列表字符串比较触发异常。原异常未记录两侧配对，不能声称实际native元素已证明相等；将逐项资格比较并保留配对回执，同范围新AT续跑。

本次原生route report已重现logical7145555/routable2031733/fully1484185/conflict547548；所需schema字段与CONFLICTS枚举存在。canonical全量清单/分类/union覆盖和G1未建立。702396节点仍是独立历史指标。

工程终态复核：144输入、基线及13归档项无变化，4个已登记PID/start均不在，单EDA锁可获取；观察器session15611已真实exit0并排空。原始报告/失败保留。terminal_facts的route_status自动解析为空，原生计数以完整native_route_status.rpt和schema_and_route_status_observed.json为准，未伪写0。

[原异常](runs/R001/attempts/AT001_failed_route_full_attribution/evidence/native/native_error.tcllist) · [终态核验](runs/R001/attempts/AT001_failed_route_full_attribution/terminal_facts.json) · [原生计数](runs/R001/attempts/AT001_failed_route_full_attribution/evidence/native/native_route_status.rpt)。


---
Published: 2026-10-18T00:56:15.424466+00:00
Publication: P784b3889ca6743cc9d369a31740339b8
