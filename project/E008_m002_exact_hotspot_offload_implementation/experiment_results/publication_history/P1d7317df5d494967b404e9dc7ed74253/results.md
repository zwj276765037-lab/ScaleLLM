# E008：AT004全局place POST闭合，候选locality运行中

截至12:51Z，实际place全局POST已闭合：completed1/diagnostic_eligible1、blackboxes0、内部时钟COMPLETE_INTERNAL，integrity gate_issues为空、reset structure/fanout资格通过；[本轮global POST事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_global_POST_closed_facts.json)。A007复用已接受timing/fresh80/congestion对其余global门做增量审核，无新停点。当前literal成员RAW9514/S9507/P9491闭合，正在候选locality；原生origin对应关系、实际全部P落SLR2、cut/有界timing及combined候选收据仍待，完整place phase尚未qualified，外层physopt/route未到。

用户明确“可以继续了”后，AT004于2026-10-17T09:23:05.136988Z真实启动。39归档源/b9dc、144生产/父8451、supervisor14547/start69484/native14680/start70786、CPU0–7/nice5及单EDA核实。[启动事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)。

12:17:58Z实际place_design SSI_SpreadSLLs自然native0，用时7858秒；仅命令成功，完整POST/locality尚未闭合。[命令事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_command_zero_POST_pending_facts_20261017.json)。实际place.dcp已生成并核身份580662986B/SHA4ce14ed66767dc099c8c3c24e18524a7305bef0e29fcb796ee538132f6784894，[本轮检查点记录](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_checkpoint_saved_identity.json)。

本轮完整place时序报告已实际产出，12:38Z读取：WNS+0.147ns/TNS0/setup违例0；WHS−0.562ns/THS−1879.853ns/hold违例34042，setup/hold总端点3209762/3208318；WPWS/TPWS0、PW-skew表头违例0。当前正式报告timing FAIL。旧E005同阶段为WNS+0.103ns、WHS−0.695ns、THS−2145.408ns、hold30885；最差值变好但hold端点增加3157，记录混合变化，不判整体改善或C01因果。此为布线前结果，非routed签核。 [时序原报告事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_full_timing_report_available_facts.json)；[采集文字时间澄清](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_full_timing_report_observation_clarification.json)保留原fact，只澄清其DRC now running沿用12:27观察，实际12:38已到pulse_width/bus_skew/结构输出，timing身份/数字不变。A007已独立接受实际timing及fresh80结构子步骤，无新门。

12:38Z已见bus_skew结束及fresh结构48/16/16边界图完成的原生信息，但fresh80结构已独立接受；global POST/integrity、成员reconciliation、实际全部P落SLR2与本阶段cut/timing仍待最终收据；不能凭部分表或消息宣称完整place资格。外层physopt/route未到。

本轮完整restored preplace已独立接受：[原生全门事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json)。RAW9514/S9507/P9491、16内部DSP→2父；30区X0Y10:X5Y14、hard/nonexclusive/non-routing-contained三policy0、9491成员/78266 sites；9525对象/17schema原策略前后一致。端口269/组269/aliases2772/calls2170与167160事件闭合。有向cut14307 nets、21479边界对，四组未布局through LOAD各16：入setup/hold+6.158/−0.074ns，出+6.859/+0.081ns；均非迁移收益/fullcutTNS/正式安全。

当前Place46-14高度拥塞/可能难布线风险保留。早期SLL10865/17280为全设计SLR1→2估计，不与旧SLR0→1相减；USER_SLL_REG可见100DDR对象后抑制，总数未知，9525候选策略快照不覆盖这些DDR属性，原字节保持不等于placer兑现。DDR delay cap3无日志单位，非skew值；自动BUFG提示实际INFO，11候选均跳过插入，非必需时钟缺失证据，不能与旧不同候选集合判因果。以上[独立告警审核](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/congestion_provisional_timing_review.md)保留边界，无新停点；原全局timing/DRC/CDC/reset/IO、fresh80与合法route验收不变。DRC15914旧preplace警告及debug实际50MHz/声明300MHz差异保留。

AT001/AT002入口自然失败、AT003用户PDU停机与14项真实收尾原证据保留；不作C01方法否定。当前execution running/verdict unassessed；正式reset/CDC/IO OPEN，暂无候选完整物理效果/合法route/时序收敛结论。


[本轮timing/fresh80/congestion独立子步骤闭合事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_timing_fresh80_congestion_substeps_reviewed_facts.json)：80结构为input48/gate16/down16、DONT_TOUCH全1，REF/INIT/CE宽256/384/512及全部driver LOC/BEL/load SLR范围有实际值，14 control-source原始行已核。完整timing原生表/分组及相同timer settings/clock表复核，内部no_clock/constant/PW-clock/unconstrained0；外部input1/output2无delay、6 unconstrained clock groups及report_methodology未运行仍保留。拥塞报告Fully Placed/min level3，当前/旧各48行且最高level6，所有同键窗口坐标不同，不作固定区域百分比delta。C01在每行所列top3贡献者当前0次/旧24次，仅名单变化，非零拥塞/全P落区/离开热点或因果证明。报告无SLR列、不猜tileY，未列及NA不当0，原固定窗UNAVAILABLE。完整POST/locality仍待。

---
Published: 2026-10-17T12:51:06.886771+00:00
Publication: P9e5d7a764cf34cd1a18a5fe26290b1a5
