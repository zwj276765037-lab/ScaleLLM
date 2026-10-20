# E009：SM013只读全量失败网归因来源

M003/SM013；基线为E008/R001/AT004失败DCP（765705446B/SHA51679d9a…）、已审终态与144生产输入。工程A006已真实登记R001/AT001并完成CPU准备；尚未启动原生EDA。Vivado2025.2/VCU118原图只读，不重新综合/实现，不改RTL/XDC/旧证据。

query_plan.json/targets.tcl冻结canonical别名闭包、driver模块归一及唯一主组、前20排序、固定parent/meta/80保护/top10与既有C01跨SLR种子；consumer/clock-region关联另表，覆盖按网ID union计算。固定对象耗尽结束，无递归全芯片时序扩展。完整字段/缺测与批量输出见[协议](protocol.md)。

[准备清单](prepared_manifest.json)绑定实际入口、查询计划及基线；本次预检144输入和失败DCP身份一致、前次PID/start消失、无EDA/编译、锁可获取且已释放。单EDA、CPU0–7/nice5/max8、树RSS192GiB/MemAvailable48GiB持续30s/disk30GiB，正常无墙钟/静默强停。实际模型无独立回执，不默换。


---
Published: 2026-10-18T00:36:50.907449+00:00
Publication: Pc630163bbcd94542af1e462c450fa76c
