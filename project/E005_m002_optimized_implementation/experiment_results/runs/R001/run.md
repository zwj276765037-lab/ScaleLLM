# R001 — M002 / SM009 / E005 同周期RTL优化与功能验证

execution_state: completed（RTL实现与本批功能范围）；verdict: supported/PASS local functional scope；applicability: Attention functional_delivery_v1 / AT001，MLP functional_delivery_v2 / AT003；review: A007独立审核另记，非用户最终验收。

3生产RTL已实现并冻结：Attention双wave48固定slot标量LUT6，MLP Gate/Down32默认row标量LUT1，均无新周期，保持payload异步reset/clear hold或原resetless保持、metadata、历史SRL和控制优先级。80为计划边界数量，实际新综合网表落实/资源/fanout仍待A006核验。

- [最终小facts与3生产RTL SHA256](rtl_functional_final_facts.json)
- [Attention功能结果](attention_functional_results.md) / [小facts](attention_functional_facts.json)
- [MLP功能结果](mlp_functional_results.md) / [小facts](mlp_functional_facts.json)
- [执行清单与覆盖](functional_execution_list.md)
- [v1输入SHA256](functional_delivery_v1.json) / [v2输入SHA256](functional_delivery_v2.json)
- [修改前精确小文件](frozen_before/manifest.json) / [参考唯一派生](frozen_before/simulation_reference_derivation.json)
- [15项Python静态边界核验](rtl_static_checks.json)，仅静态证明
- [Attention diff](hap_tensor24_buffers.diff) / [Gate diff](hap_mlp_projection_repack12_to16_s24_history2.diff) / [Down diff](hap_mlp_projection_repack12_to16_s32_history2.diff)
- [模块实现说明](../../../../hardware/source/m002_routability_ce.md)

AT001 Attention实际native/监督0，无资源/墙钟停止、无survivors：1265488逐周期差分、1263504槽oracle，192中断/196epochs、4完整双wave128group、13591stall检查；末slot前/后各4、valid中断4、异步reset97和wave127边界中断2均真实命中。

AT002 MLP v1编译失败，保留[原TB](revisions/hap_mlp_repack_output_ce_tb_v1.sv)及原AT；只将变量声明前移后，AT003 v2实际native/监督0、无stop/survivors。Down2477周期/49oracle输出/replace2/stalls1368/errors16；Gate4821周期/98输出/replace5/stalls2754/errors17。两者reset_overlap=clear_overlap=1、tail4/8、高符号位和生产16row均命中。独立列FIFO oracle与冻结原版逐周期检查均通过，未改gold或删断言。

A006唯一EDA调度且维护原始AT。生产三RTL自首版到当前哈希未变，本次所有v2交付输入仍匹配；Attention与MLP实际运行身份、命令、工具、输入、日志、退出与资源均链接至原AT。后续新综合/place/route由A006维护，新网表48/32边界、扇出/负载、拥塞、合法route和时序均未由本批证明；完整数值、CDC/reset签核、板卡独立。禁止热改正式冻结RTL。
