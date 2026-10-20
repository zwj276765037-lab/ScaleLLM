# AT011 stale 原生机制独立审核

execution：06:56:43.063915Z 自然 native1，stop=null、无残留，16 个记录 PID/start 实际均结束；review：机制无阻断，G4 未放行。

原 metadata 实为 Out-of-date / 100% / NEEDS_REFRESH1。真实 open_run 成功、TCL apply attempts1；随后 scripts_only 生成并执行完整 150 行 INIT，link_design 成功、apply attempts2、init end 存在，OPT 未开始。13 源归档及 6 组原件/保存机制证据匹配；独立重放 extractor 得到相同前缀，Tcl info complete=1。

末尾旧组合断言要求绝对 attempts1，实际 2 已足以触发原失败；本审核不把未单独导出的最终 pblock/member 数量判为通过。restore 未到，原 native1 不改；AT007 的独立 restore delta0 仍限其原范围。正式 check_apply 没有绝对 1 限制。无需为已实测 stale/载图/INIT 机制重跑小图；新生产图、结构/预算与严格 G4 仍待。

[完整证据](AT011_native_stale_mechanism_review.json)。
