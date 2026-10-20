# E011 当前来源与方法

原冻结核心48源manifest42dafce3及全部3RTL保持。实际新AT029另明确消费4份实验适配源（native_init_recovery.py、recover_init.tcl、launch.py及已有离线pblock checker），共52runtime源；199 current/archive绑定全匹配。它们全部写入本次stage_inputs/source_archive与owned源归档，不隐藏外部依赖或拼接成旧48源。

AT028 native INIT生成的225813781B init.dcp/a6dedfc5及原INIT报告作为已发生事实继承，不重综合、不重新执行INIT。恢复前照常使用原m003::require_project严核原XPR的0/1/global/LATE/TCL，再绑定原driver、actual source/apply及DCP embedded SRC_FILE_INFO；恢复后禁止overlay重应用，实际导出embedded registry和有效成员/资源资格。

新适配只精确替换原m002_post的一处hook调用，保留全部原结构/时钟/资源/DRC/CDC/reset/IO/probe/admission守卫；约束链改为明确的embedded继承来源，并保留逐源hash、原candidate metadata、限定debug新增和deltaapply0。新增实际PBLOCKS排除检查；不改变冻结架构、预算、资源池或验收。

7项受影响正负回归与零EDA预检通过；未重复已过功能仿真或综合。实际G4包仍由A007独审后才允许固定place SSI_SpreadSLLs/physopt Default/route Default。


---
Published: 2026-10-19T12:54:01.373475+00:00
Publication: P472ad7be88c240c5b850c1f06502fbc2
