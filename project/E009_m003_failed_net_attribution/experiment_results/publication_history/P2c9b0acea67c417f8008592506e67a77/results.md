# E009：AT002单元库存完成，别名/冲突全集枚举中

AT002于01:00:02Z真实启动、01:09:18Z完成载图、01:12:53Z完成全量cell库存（cells.tsv 445140901B）。本次原生report再次核得logical7145555/routable2031733/fully1484185/conflict547548，当前正按固定种子和全部CONFLICTS网作别名闭包；已越过AT001首次异常点，尚无native_error或终态。

别名记录已有缓冲输出；前8真实配对样本依冻结包在canonical阶段关闭后落盘，当前不能提前验收配对、全量分类、union覆盖或G1。未因日志缓冲插入新EDA查询或热改包。manifest47d12c26…、input_bindings d221f94e…/5669B，CPU0–7/nice5和单EDA/资源保护保持。

AT001自然失败和终态原件完整保留，144输入/来源/进程/锁收尾通过；观察器15611已真实exit0，当前独立新观察器85343只记录AT002阶段。生产RTL/约束及候选未改，工具修复和当前阶段不证明优化有效。

[AT002本次原生计数](runs/R001/attempts/AT002_failed_route_full_attribution_alias_fix/schema_and_route_status_observed.json) · [实际阶段](runs/R001/attempts/AT002_failed_route_full_attribution_alias_fix/observer_events.jsonl) · [启动与来源](runs/R001/attempts/AT002_failed_route_full_attribution_alias_fix/native_start_observed.json)。


---
Published: 2026-10-18T01:14:33.348009+00:00
Publication: P77d9126f45904cd6a938efaa3ece58f3
