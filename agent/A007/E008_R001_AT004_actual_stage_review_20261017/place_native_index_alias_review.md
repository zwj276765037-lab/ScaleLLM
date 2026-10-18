# AT004 place 原生端口索引与缓冲别名审核

- execution：当前 AT004 归档验证器完整重放及闭合记录独立核对已完成。
- verdict：支持完整原生端口全集、逐端口邻接、别名闭包及全组双向互证；269 个端口、269 个组、2,772 个别名、2,170 次原生调用。IN 23 / OUT 70 / INOUT 176；断开、多组和未知方向均为 0。
- 167,160 条已闭合别名事件序号连续、时间不递减、BEGIN/END 操作与 detail 完整配对；正常最终 flush，mapping Tcl code 0。
- 实际 source、artifact、point、epoch 与父输入元数据绑定均通过；DCP 身份来自工程归档元数据，审核未读取或哈希 DCP。
- applicability：仅适用于 AT004 实际 place 图的索引与别名子步骤；epoch 的输入路径指原始恢复DCP，并非重新恢复或pre-place测量。未据此确认完整 cut、时序、combined候选phase或route；不推断迁移收益。
- review：本子步骤接受，无新增执行停点。原始证据与此前审核保持。

[完整审核与证据身份](place_native_index_alias_review.json)
