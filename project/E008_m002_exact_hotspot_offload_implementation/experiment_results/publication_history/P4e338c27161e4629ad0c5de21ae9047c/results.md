# E008：完整physopt原生闭合，Default布线真实运行

截至15:20Z，本轮完整physopt原生POST/locality均0、candidate compliance true，于15:18:14Z真实闭合；9491实际P仍全原对象存活/all SLR2，无missing/replacement。完整有向cut14307nets/58361retained endpoints/21479boundary pairs；四组through LOAD各16，入setup/hold+0.603/−0.221ns、出+0.603/+0.057ns。当前已原生执行route_design Default并获取Implementation/xcvu9p许可、出现Starting Routing Task，实际布线运行中；尚无route结果。physopt剩余cut/timing/combined独立审核继续，无新增执行等待门。 [完整阶段与route启动观察](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/physopt_closed_route_started_observed_facts.json)。完整physopt stage facts3634705B/SHA7118bf3e，native0不代表hold或正式安全通过；完整时序WNS+0.147/TNS0，WHS−0.562/THS−1879.853/hold34042仍FAIL，高拥塞、固定窗UNAVAILABLE和正式reset/CDC/IO OPEN保留。

截至14:10Z，fresh physopt全局POST诊断资格、当前成员/native-origin对应关系/9491实际P全SLR2及完整native端口索引均已独立接受。global completed1/diag1/integrity gate空；9491P全原对象存活、无缺失/替换、LOC/BEL/区域及policy保持；索引269ports/269groups/2772alias/2170calls、167160alias事件全配对/unknown0。当前有向cut正常导出，限定timing/combined合规仍待，完整physopt phase尚未闭合，route未到。 [本轮global/member/index独立接受事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/physopt_global_membership_index_reviewed_facts.json)。12类本轮global报告去指定页眉后与place正文相同；current reset/CDC/BRAM/14exports及39源/144生产/175约束/162registry均重放核对。当前RTSTAT-13 CW1/15917 Warning、holdFAIL及正式reset/CDC/IO OPEN、高拥塞与固定窗/自适应窗口限制保持。

截至13:48Z，本轮fresh physopt完整时序与80保护结构已独立接受：时序报告仅Date/Command/Design State等页眉变化，正文与本轮place完全一致，WNS+0.147/TNS0/setup0、WHS−0.562/THS−1879.853/hold34042，timing FAIL；80为input48/gate16/down16、DONT_TOUCH全1、CE256/384/512及REF/INIT/实际位置与14控制源均核。当前phase专属collector/独立regular文件/inode/真实闭合marker证明是本次新采集，不能因网表未改而冒用place结果。完整physopt global POST/locality及当前9491P/连接/限定timing资格仍待。 [本轮独立子步骤事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/physopt_timing_fresh80_reviewed_substeps_facts.json)。

本轮完整place已于13:23:46Z真实闭合：native POST/locality均0、candidate compliance true，9491实际P全SLR2/原对象存活，global POST/fresh80/成员/index已独立接受；[完整place阶段事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_closed_stage_facts.json)3634643B/1f7fec13。当前完整place组合独立审核已接受：复用8份子审核，四组限定timing、compliance纯重放和combined收据均核实，无新门。外层phys_opt_design Default于13:26:15Z自然native0（149秒），native明确setup WNS>=0故未改网表；[实际physopt命令事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/physopt_command_zero_POST_pending_facts.json)。physopt.dcp580691314B/SHAf721fbbb28d313de94708bb97ca918d181046259780650540be33596890e5ec6已实际保存；当前完整physopt POST/locality继续，route尚未到。

Place cut为14307nets/55605候选leafpins/1276disconnected/58361保留端点/44054相关逻辑pairs/21479边界pairs，入3087/出55；四组through LOAD各16，入setup/hold+0.603/−0.221ns、出+0.603/+0.057ns，非完整cutTNS、不保证跨cut路径或签核。已知逻辑跨SLR127对不等于SLL；8014无SLR位置对经独立逐端点核对，driver均为RAW内但S/P排除的7个GND/VCC常量，非P缺项；clock1429/reset6156为整网分类、其余constant429。979 touched sites中801共享，不等于释放容量。

用户明确“可以继续了”后，AT004于2026-10-17T09:23:05.136988Z真实启动。39归档源/b9dc、144生产/父8451、supervisor14547/start69484/native14680/start70786、CPU0–7/nice5及单EDA核实。[启动事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)。

12:17:58Z实际place_design SSI_SpreadSLLs自然native0，用时7858秒；仅命令成功，完整POST/locality尚未闭合。[命令事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_command_zero_POST_pending_facts_20261017.json)。实际place.dcp已生成并核身份580662986B/SHA4ce14ed66767dc099c8c3c24e18524a7305bef0e29fcb796ee538132f6784894，[本轮检查点记录](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_checkpoint_saved_identity.json)。

本轮完整place时序报告已实际产出，12:38Z读取：WNS+0.147ns/TNS0/setup违例0；WHS−0.562ns/THS−1879.853ns/hold违例34042，setup/hold总端点3209762/3208318；WPWS/TPWS0、PW-skew表头违例0。当前正式报告timing FAIL。旧E005同阶段为WNS+0.103ns、WHS−0.695ns、THS−2145.408ns、hold30885；最差值变好但hold端点增加3157，记录混合变化，不判整体改善或C01因果。此为布线前结果，非routed签核。 [时序原报告事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_full_timing_report_available_facts.json)；[采集文字时间澄清](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_full_timing_report_observation_clarification.json)保留原fact，只澄清其DRC now running沿用12:27观察，实际12:38已到pulse_width/bus_skew/结构输出，timing身份/数字不变。A007已独立接受实际timing及fresh80结构子步骤，无新门。

12:38Z已见bus_skew结束及fresh结构48/16/16边界图完成的原生信息，但fresh80结构已独立接受；global POST/integrity、成员reconciliation、实际全部P落SLR2与本阶段cut/timing仍待最终收据；不能凭部分表或消息宣称完整place资格。外层physopt/route未到。

本轮完整restored preplace已独立接受：[原生全门事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json)。RAW9514/S9507/P9491、16内部DSP→2父；30区X0Y10:X5Y14、hard/nonexclusive/non-routing-contained三policy0、9491成员/78266 sites；9525对象/17schema原策略前后一致。端口269/组269/aliases2772/calls2170与167160事件闭合。有向cut14307 nets、21479边界对，四组未布局through LOAD各16：入setup/hold+6.158/−0.074ns，出+6.859/+0.081ns；均非迁移收益/fullcutTNS/正式安全。

当前Place46-14高度拥塞/可能难布线风险保留。早期SLL10865/17280为全设计SLR1→2估计，不与旧SLR0→1相减；USER_SLL_REG可见100DDR对象后抑制，总数未知，9525候选策略快照不覆盖这些DDR属性，原字节保持不等于placer兑现。DDR delay cap3无日志单位，非skew值；自动BUFG提示实际INFO，11候选均跳过插入，非必需时钟缺失证据，不能与旧不同候选集合判因果。以上[独立告警审核](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/congestion_provisional_timing_review.md)保留边界，无新停点；原全局timing/DRC/CDC/reset/IO、fresh80与合法route验收不变。DRC15914旧preplace警告及debug实际50MHz/声明300MHz差异保留。

AT001/AT002入口自然失败、AT003用户PDU停机与14项真实收尾原证据保留；不作C01方法否定。当前execution running/verdict unassessed；正式reset/CDC/IO OPEN，暂无候选完整物理效果/合法route/时序收敛结论。


[本轮timing/fresh80/congestion独立子步骤闭合事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_timing_fresh80_congestion_substeps_reviewed_facts.json)：80结构为input48/gate16/down16、DONT_TOUCH全1，REF/INIT/CE宽256/384/512及全部driver LOC/BEL/load SLR范围有实际值，14 control-source原始行已核。完整timing原生表/分组及相同timer settings/clock表复核，内部no_clock/constant/PW-clock/unconstrained0；外部input1/output2无delay、6 unconstrained clock groups及report_methodology未运行仍保留。拥塞报告Fully Placed/min level3，当前/旧各48行且最高level6，所有同键窗口坐标不同，不作固定区域百分比delta。C01在每行所列top3贡献者当前0次/旧24次，仅名单变化，非零拥塞/全P落区/离开热点或因果证明。报告无SLR列、不猜tileY，未列及NA不当0，原固定窗UNAVAILABLE。完整POST/locality仍待。

[完整place组合独立接受事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_combined_independent_review_accepted_facts.json)绑定A007实际组合/限定timing审核：四组原生64行返回值匹配，但ingress/egress setup的16条起终点/时钟签名全重合，不能当独立32条或保证每条跨cut。site16772 primitive行中9505 selected primitive经DSP父映射覆盖9491P，979touched/801shared；资源只用5个唯一顶层SLR行，重复subrow覆盖限制保留。完整place诊断资格不代替hold通过/压力改善/合法route或正式安全。

---
Published: 2026-10-17T15:20:28.858290+00:00
Publication: Pb0b125e7afb24965a0d5d850c4722e12
