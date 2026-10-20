# E011当前实测结果

AT023完整80/80 clock端点、actual K1/12062网段，原生0/nullstop/树锁闭合，采集3755ms、含载图318.177695s。actualdirect alias1；完整segments/canonical/leaf/ports各1，direct80。旧首CLK四字段与新组逐字段相同。3.755s仅时钟采集，不是完整G4速度。

优化/v2已实际应用，48源manifest16f9523c；128 ordinary回归实际PASS，另精确8项group/stream CPU及独立审核已通过。原AT003 outer1、旧失败/停止与UNKNOWN退出码均保持原证据。

AT024当前实际22依赖读取/23元数据、open_run返回和两次overlay apply均已闭合；第二success240B/a4bfa8e9，事件02:30:42Z。open_run elapsed44:36含第一次overlay，与clock3755ms不可混比。两个apply只证明各次实际约束Tcl流，不替代快照/预算/restore/G4。

02:31Z新synth快照已开始，fresh design_1/token1/实际12602唯一clock网段、直接成员1，segments351ms、NAME/CLASS106+59ms；首个完整core_address行C_nets_group引用及CLR361token已保全，spool逐行增长。当前仅部分采集，不把首行/trace存在当全量snapshot/80memory/source或结构预算通过。48源冻结；当前无native终态/G4/place/route/时序成功，TOP01−2.896ns/22049仍OPEN。


---
Published: 2026-10-19T02:35:10.970812+00:00
Publication: P617abf78ae8e4674873ccb2f3ba7c56b
