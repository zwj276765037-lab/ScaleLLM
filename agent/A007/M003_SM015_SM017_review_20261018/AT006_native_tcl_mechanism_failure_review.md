# A007：AT006 原生 TCL 机制与 INIT 边界审核

execution=completed（本独立子审核）；verdict=部分机制确认，正式入口仍待修复；applicability=AT006 toy；review=不放行 G4。

12 份源归档的原件/副本身份均匹配，23 个记录 PID/start 均已结束。AT006 于 06:21:21.389168Z 自然 native1，无 stop/survivor；3 RTL/G2 保持。原生确认 FILE_TYPE TCL 转为 Sourcing Tcl File，但 info script 指向生成驱动，使 helper 相对路径错误；两条 Common17-1548 被降为告警，toy 仍实际完成 opt。外层 Complete! 断言失败，实际 apply/restore 未通过。

生成驱动的完整 INIT 结束于第 149 行，下一行进入 Opt phase；完整前缀包含初始化/错误处理/end_step，不含 opt，也不写 init DCP。前缀原生重放仍待 AT007，正式流程须脚本仅生成、实际完成 INIT 后严格核 apply/已存约束再显式 opt；明确写 init checkpoint，不猜旧产物。绝对 helper 根必须绑定冻结源，restore 在载图前设 guard 并以 attempt counter 防止约束错误被吞为告警。

[机器可核证据](AT006_native_tcl_mechanism_failure_review.json)。A007 未运行 EDA、读取或哈希 DCP；未改生产。该失败不反驳 M2/A3 方法。
