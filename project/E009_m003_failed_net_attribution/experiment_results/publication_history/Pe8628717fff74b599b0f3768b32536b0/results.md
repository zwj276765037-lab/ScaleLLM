# E009：AT001自然失败保全，AT002修复对照通过

AT001于00:53:21.909734Z自然结束：native1/supervisor1、stop_reason=null、无cleanup/残留，144输入/基线及13归档项不变、4登记PID/start均不在、单EDA锁空闲；原观察器session15611真实exit0并排空。00:53:05Z cell库存已完成，首次parent_head别名资格检查的列表字符串比较触发异常；实际两侧元素未记录，不能提前断言其具体配对相等。

本次原生route report为logical7145555/routable2031733/fully1484185/conflict547548，schema所需字段存在；终态独立CPU解析见AT001/terminal_facts_v2.json，原v1解析空记录保持。canonical全量清单/归因/G1未建，source/工具失败不作为RTL方法否定。

AT002对实际alias函数的CPU反例证明：表示差异接受，真实NAME及数量差异拒绝。固定query_plan、aggregate/supervise/launch均与AT001字节一致；新manifest47d12c26…、144/DCP/前次收尾/资源核验通过。尚无AT002原生结果。

[AT001终态](runs/R001/attempts/AT001_failed_route_full_attribution/terminal_facts_v2.json) · [原异常](runs/R001/attempts/AT001_failed_route_full_attribution/evidence/native/native_error.tcllist) · [AT002实际delta与CPU对照](runs/R001/attempts/AT002_failed_route_full_attribution_alias_fix/delta_and_cpu_checks.json)。


---
Published: 2026-10-18T00:59:12.465747+00:00
Publication: P40a9f49956a04b2c89a23d46aabbffed
