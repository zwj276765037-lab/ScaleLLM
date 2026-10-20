# E009：SM013只读全量失败网归因来源

M003/SM013；基线为E008/R001/AT004失败DCP（765705446B/SHA51679d9a…）、已审终态与144生产输入。工程A006已真实登记并于2026-10-18 00:40:06Z启动R001/AT001原生只读测量，A007预运行独立核查无实质阻断；prepared manifest SHA122178e26…、input_bindings SHA f0beb420…；00:49:28Z载图完成，原生路由状态/schema预检进行中。Vivado2025.2/VCU118原图只读，不重新综合/实现，不改RTL/XDC/旧证据。

query_plan.json/targets.tcl冻结canonical别名闭包、driver模块归一及唯一主组、前20排序、固定parent/meta/80保护/top10与既有C01跨SLR种子；consumer/clock-region关联另表，覆盖按网ID union计算。固定对象耗尽结束，无递归全芯片时序扩展。完整字段/缺测与批量输出见[协议](protocol.md)。

[准备清单](prepared_manifest.json)绑定实际入口、查询计划及基线；本次预检144输入和失败DCP身份一致、前次PID/start消失、无EDA/编译、锁可获取且已释放。单EDA、CPU0–7/nice5/max8、树RSS192GiB/MemAvailable48GiB持续30s/disk30GiB，正常无墙钟/静默强停。实际模型无独立回执，不默换。


---
Published: 2026-10-18T00:50:34.024569+00:00
Publication: Pa3a925812a6e4f3388e0e0a93e18113c
