# v3 恢复入口增量独立审核

execution：完成；verdict：窄范围内容资格规则有证据支持；applicability：delivery baf56456、manifest 151e4f11；review：入口无阻断，G4 未放行。

45 源中 5 改、40 不变；5 份差异逐字重建、当前与保存源身份全核。工程 59 测试通过、49 原件/归档绑定匹配；A007 新增 2 项验证及实际 Tcl 分支的显式 mock 验证通过。普通 fresh guard 保持拒绝 stale；恢复分支保留实际 23 项状态，限定原生产者与消费图、输入、身份、恢复来源和运行回执；没有清 stale 或新综合。3 RTL/G2/池/预算/物理策略不变。

本次原产物内容核验归因于 A006，A007 仅核有限文本/源/回执且未读取或重哈希 DCP。新生产载图、actual apply、图结构、预算及严格 INIT→OPT→debug→preplace 仍须原生证据。

完整身份和证据：[JSON](R002_native_entry_fix_v3_review.json)。
