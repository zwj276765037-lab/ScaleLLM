# 当前终态：AT004自然布线失败

19:09:25Z原生route失败，702396 node overlaps/547548 congestion failed signals；21:18:30.695127Z native/supervisor1自然结束。14项收尾全true、两observer exit0、无活动EDA/新AT。[终态事实](attempts/AT004_C01_PDU_resume_full_implementation/terminal_facts.json)；[当前压缩结果](../../summary.md)；[详细失败包](attempts/AT004_C01_PDU_resume_full_implementation/failed_route_terminal_summary.json)；[独立审核/最终工程交付](attempts/AT004_C01_PDU_resume_full_implementation/terminal_engineering_delivery_facts.json)。

以下为保留的逐阶段历史，早期running状态不代表当前实态。

# E008 / R001：C01向SLR2卸载与完整implementation

execution_state: running（用户已明确恢复，AT004实际启动）；verdict: unassessed。

历史AT002_C01_native_policy_fix_full_implementation于2026-10-17T07:14:16.993406Z实际启动，37归档源/45bbc、144输入、原生与本项目唯一EDA已核。[启动事实](attempts/AT002_C01_native_policy_fix_full_implementation/native_start_verified.json)。当时恢复父网表，随后自然失败，见下文真实终态；不能据此读取当前运行。

AT001于05:12:22Z因入口要求不受支持的RLOC_ORIGIN而自然exit1，14项收尾全通过。[原终态](attempts/AT001_C01_slr2_offload_full_implementation/terminal_summary.json)。最小兼容修复26例和独立审核通过；旧3cae、AT001全部证据保留。新实际绑定包含失败终态/修复身份，保持C01及原合同，并将后续同C01常规修复的真实来源登记与重试委派给工程，避免idle Root阻塞。

唯一主动变量为C01 exact branch[1]的SLR2 hard非排他且不限制走线Pblock。恢复E005 debug_materialized DCP，SSI_SpreadSLLs place→Default physopt→Default route；不重复综合/OPT/debug或无关功能测试。实际成员、约束、80保护、全部P落区及完整物理验收保持。正常无墙钟/无输出强停，无bitstream/GPU/板卡/PPL/ACC。


## AT002实际成员子步骤（07:25Z）

父网表恢复完成，实际RAW9514/S9507/P9491成员闭合；16个DSP内部primitive归一到2个实际DSP48E2父，P全UNPLACED。[独立增量核查](../../../../../agent/A007/E008_R001_AT002_actual_stage_review_20261017/pre_place_membership_incremental_review.json)接受10份账本及本次实际artifact身份。仅成员资格成立，resource/native policy/Pblock/完整pre-place和place/physopt/route尚待实际结果；没有停止或新审核等待门。


## AT002真实终态（07:36:55Z）

自然native1/supervisor1：write_xdc -constraints physical被2025.2拒绝。资源/before policy已闭合，9525对象unsupported RLOC_ORIGIN全native0/空；区域成员/站点回读已写，但after/全pre-place/place/physopt/route未执行。[终态审计](attempts/AT002_C01_native_policy_fix_full_implementation/terminal_summary.json)14项全通过、原进程退出/144保持/lane释放。工程建立一行API兼容修复与独立delta审核后直接新AT，不覆盖AT002，不新增审批门。


## 当前AT003真实启动（07:43:04Z）

[实际启动事实](attempts/AT003_C01_physical_xdc_fix_full_implementation/native_start_verified.json)：39归档源/b9dc、144输入、supervisor1560167/native1560384的PID/start与唯一项目EDA已核。07:42:53先发起launcher，07:43:04才真正native启动。仅一行write_xdc -type physical修复经9例/115身份独立delta接受，工程按a024委派直接绑定c8c3来源后续跑，无新审批门。当前恢复父图；完整export/after/preplace及place/physopt/route待实际结果。11 fresh scope对象正确构成为10 root/ancestor+1 u_silu内部层级，总scope9525。


AT00307:52Z实际父图恢复与成员子步骤闭合，10份账本已独立增量接受；RAW9514/S9507/P9491、16DSP内部→2父、P全未布局。07:53Z新原生资源资格执行中；export/after/fullpreplace与物理阶段均未完成。


AT00308:05Z真实硬SLR2 Pblock与物理XDC导出闭合，08:08Z[独立接受](../../../../../agent/A007/E008_R001_AT003_actual_stage_review_20261017/actual_before_pblock_export_review.json)：30区全覆盖X0Y10:X5Y14、三policy0、P9491/site78266；XDC1598546B/9491名字与P全等。after新鲜逐对象schema/策略一致性仍进行，无preservation/完整pre-place/place/physopt/route结论。


AT00308:18Z原策略保留闭合并独立接受：9525fresh after/17schema、前后policy文件字节同、原Pblock0→仅指定新区域。08:19Z完整原生端口索引闭合并独立接受，269ports/269groups/2772aliases/2170calls、167160buffered alias事件完整；[索引捕获](attempts/AT003_C01_physical_xdc_fix_full_implementation/candidate_pre_place_native_port_index_closed_facts.json)。08:23Z有向cut仍正常导出，timing/global完整preplace/物理阶段未完成。


## AT003真实进入place（08:33Z前，08:35Z观测）

[完整restored preplace阶段事实](attempts/AT003_C01_physical_xdc_fix_full_implementation/pre_place_closed_stage_facts.json)记录原策略/cut/四组timing/restore全门，原源与144保持，restore guard native0、blackbox0/DRCblocker0/clockgroups1。实际日志已调用place_design SSI_SpreadSLLs并进入Phase1.3；全独立复核继续，无新等待门。当前未place完成/未physopt/未route。有界未布局入setup/hold+6.158/-0.074、出+6.859/+0.081ns，不做跨阶段改善或签核结论。


## 历史PDU停止状态（08:44:09Z，现用户已恢复）

按用户明确关机要求向精确supervisor发SIGTERM，原生-15/监督125受控结束，14项真实收尾通过、PID退出/lane释放/144与39源保持，两个observer均exit0。完整preplace已独立接受，place Phase1.3中断，没有当前E008 DCP，不是方法失败或完成。[真实暂停总证据](attempts/AT003_C01_physical_xdc_fix_full_implementation/user_PDU_stop_closeout_20261017.json)、[续接边界](attempts/AT003_C01_physical_xdc_fix_full_implementation/PDU_resume_readme.md)。AT登记使用helper允许的cost_stop终止类别，正文明确USER_REQUESTED_PDU_PAUSE；不表示预算或方案失败。等待用户恢复通知，不新开AT、不重启、不生成新checkpoint。


## 当前AT004真实恢复（09:23:05Z）

用户“可以继续了”已由Root归档，环境/版本/许可诊断、144生产、39消费源/b9dc、父8451/396068466B、全部旧owner和唯一lane预检通过。新ec12f2来源绑定保持原C01/E006支持/合同。AT004于09:23:05.136988Z真实native启动，[启动事实](attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)核supervisor14547/start69484/native14680/start70786、CPU0–7/nice5、39archives/144。当前恢复正式父图，完整preplace/place/physopt/route未完成，原AT003不改。


AT00409:32Z父图恢复与实际成员闭合，10份账本已独立增量接受：RAW9514/S9507/P9491，16内部DSP→2父，全P未布局。当前09:33Z原生resource资格检查，完整policy/Pblock/preplace和物理阶段待实际结果。


AT00409:44Z新资源/before/真实Pblock-XDC闭合并独立接受：30区X0Y10:X5Y14、三policy0、P9491/site78266、conflicts空；9525policy范围与AT003同。真实XDC1598540B，仅输出目录注释差异、可执行内容同。当前after逐对象fresh schema/策略一致性运行，无preservation/fullpreplace/物理阶段结论。


AT00409:56Z原策略保留闭合并独立接受，9525全fresh after/17schema与before及AT003同；只新指定hard区。09:56:49Z完整native port index/alias闭合并独立接受：269ports/269groups/2772aliases/2170calls、167160事件完整；[本轮捕获](attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json)。当前10:02Z有向cut逐网导出正常，fullcut/timing/globalpreplace/物理阶段待实际结果。


## AT004实际进入place（10:07Z前置门闭合，10:08Z观测）

[完整preplace及实际Placer入口事实](attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json)11341B/c7149c2c：当前39/144/原策略/cut/timing/restore全门通过，live内部clock/PW/unconstrained0，restore native0/blackbox0/DRC0/clockgroups1。native明确许可Implementation/xcvu9p通过且Started Placer；10:08Z Phase1.2。独立timing/global delta继续，不新增门；place/physopt/route未完成。未布局through LOAD入+6.158/-0.074、出+6.859/+0.081ns，各16，非fullcutTNS/跨cut路径保证/迁移收益或签核。


AT00410:11Z完整restored preplace/真实place入口独立增量接受（A007 global review284784B/2b5963a1）：144/39/175约束/162metadata/overlay/current live guard-clock-DRC/reset/debug通过诊断资格；15914 Warning及声明频率差异保留，80表明确旧证据继承，本轮POST待fresh。实际place Phase1.3正常运行，无place完成/physopt/route或正式签核。


## AT004实际PBP与告警范围（10:40Z观测）

当前10:40Z实际place已自然推进到Phase2.1.1.1 PBP（Partition Driven Placement），RSS28.78GiB/MemAvailable465.44GiB/disk391.0GiB，PID/start保持且CPU持续增长；尚无place命令完成/POST/locality/physopt/route结果。 本轮PBP告警经[A007只读独立审核](../../../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/place_warning_contract_impact_review.md)核查：全设计SLR1→SLR2当前需10865/17280 SLL（62.88%），仅阶段估计，不是候选专属代价、最终用量、合法route或timing；旧10594对应SLR0→1不可同边界相减。USER_SLL_REG忽略提示可见100个DDR/MIG对象，随后抑制、真实总量未知；旧轮亦存在且曾非致命，不证明本轮无害。9525原策略快照不含这些DDR对象/该属性，原字节保持不等于placer实际兑现，也不能由warning反推工程删除或软化。无新增停点，原流程/完整验收保持。 [本轮观察事实](attempts/AT004_C01_PDU_resume_full_implementation/place_PBP_warning_observed_facts_20261017.json)。


## AT004实际place后段

截至12:10Z，实际place已推进到Phase4.1.1.3 Post Placement Timing Optimization；RSS32.76GiB/MemAvailable461.43GiB/disk390.86GiB、CPU持续增长。全局放置和详细布局已在命令内部输出结束记录，当前仍是place_design内部优化；完整place命令/POST/locality尚未完成，未到外层phys_opt_design或route。 [新增clock/BUFG提示独立审核](../../../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/clock_bufg_message_contract_impact_review.md)：DDR0两网delay当前cap3/3、旧同阶段亦3/3，日志无单位，不推导skew/slack。BUFG提示实际为INFO：当前11候选/0插入/0复制/11冲突跳过，旧22/0/0/22但集合不同、精确交集9，不能判改善或C01因果。当前11均非字面C01，跳过自动插入不直接等于必需时钟缺失或未布通。无新增停点，保持原fresh POST/locality/80保护、全局clocks-DRC-timing-PW及适用skew、route验收。 [当前观察事实](attempts/AT004_C01_PDU_resume_full_implementation/place_postcommit_clock_BUFG_observed_facts_20261017.json)。


## AT004实际place命令自然成功，完整POST仍待闭合

12:17:58Z实际place_design SSI_SpreadSLLs自然native0、耗时7858秒，native明确completed successfully，已[独立核实](../../../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/congestion_provisional_timing_review.md)。当前12:20Z仍在保存布局检查点/完整POST过程中；完整POST、80保护边界、成员reconciliation、全部实际P落SLR2、cut和时序尚未闭合，外层physopt/route未到。 Place46-14明确设计highly congested/may have difficulty routing，需保留布线困难风险；与旧同阶段原文相同，不提供候选效果、SLR1定量压力变化或已失败证据。内部30-746/46-19临时WNS+0.147（旧+0.103）均要求更准确report_timing，不能推导改善、setup/hold/PW/TNS或routed收敛。完整congestion报告在原POST中正常采集，不增设门或强停。 [本轮实际命令事实](attempts/AT004_C01_PDU_resume_full_implementation/place_command_zero_POST_pending_facts_20261017.json)。


## AT004完整place时序报告已产出（12:38Z读取）

本轮完整place时序报告已实际产出，12:38Z读取：WNS+0.147ns/TNS0/setup违例0；WHS−0.562ns/THS−1879.853ns/hold违例34042，setup/hold总端点3209762/3208318；WPWS/TPWS0、PW-skew表头违例0。当前正式报告timing FAIL。旧E005同阶段为WNS+0.103ns、WHS−0.695ns、THS−2145.408ns、hold30885；最差值变好但hold端点增加3157，记录混合变化，不判整体改善或C01因果。此为布线前结果，非routed签核。 完整POST/locality尚未闭合，外层physopt/route未到，独立增量核查继续，无新门。[实际时序事实](attempts/AT004_C01_PDU_resume_full_implementation/place_full_timing_report_available_facts.json)、[观察时间文字澄清](attempts/AT004_C01_PDU_resume_full_implementation/place_full_timing_report_observation_clarification.json)。


## AT004时序/fresh80/congestion子步骤独立接受（12:46Z）

完整timing复核仍hold FAIL；本轮fresh80 input48/gate16/down16结构/属性/CE及实际位置独立接受。拥塞最高level6、48自适应窗口坐标均变，C01 listed top3贡献者0/旧24仅说明所列名单变化，固定窗UNAVAILABLE，未完成global POST/locality/全P落区/physopt/route。[子步骤证据](attempts/AT004_C01_PDU_resume_full_implementation/place_timing_fresh80_congestion_substeps_reviewed_facts.json)。


## AT004全局place POST真实闭合，候选locality待

截至12:51Z，实际place全局POST已闭合：completed1/diagnostic_eligible1、blackboxes0、内部时钟COMPLETE_INTERNAL，integrity gate_issues为空、reset structure/fanout资格通过；[本轮global POST事实](attempts/AT004_C01_PDU_resume_full_implementation/place_global_POST_closed_facts.json)。A007复用已接受timing/fresh80/congestion对其余global门做增量审核，无新停点。当前literal成员RAW9514/S9507/P9491闭合，正在候选locality；原生origin对应关系、实际全部P落SLR2、cut/有界timing及combined候选收据仍待，完整place phase尚未qualified，外层physopt/route未到。


## AT004全局POST、9491实际P落SLR2及完整index独立接受

截至13:03Z，全局place POST诊断资格已独立接受；当前actual RAW9514/S9507/P9491与完整native-origin对应关系已独立接受，9491 actual P全ORIGINAL_SURVIVING、无替换/缺失、LOC/BEL均非空且全SLR2/实际clock-region在hard范围内。有效Pblock仍三policy0、9491成员。实际269ports/269groups/2772aliases/2170calls及167160 alias事件配对已独立接受。当前有向cut正常采集，完整cut/限定timing/combined合规收据仍待，外层physopt/route未到。 [本轮global/成员/端口独立闭合事实](attempts/AT004_C01_PDU_resume_full_implementation/place_global_membership_index_reviewed_facts.json)。当前place原生IS_LOC_FIXED/IS_BEL_FIXED各9491项从preplace空→0，另5策略字段一致，保留raw delta，不写7字段全等。全局POST已核39源/144输入/175约束/162registry与50时钟，94bus-skew均MET、最差3.262ns；当前DRC为1 RTSTAT-13 Critical Warning+15917 Warning（尚未route），584exceptions中22零endpoint/384覆盖不足行保留；正式安全仍OPEN。


## AT004完整place原生闭合，外层physopt命令实际0

本轮完整place已于13:23:46Z真实闭合：native POST/locality均0、candidate compliance true，9491实际P全SLR2/原对象存活，global POST/fresh80/成员/index已独立接受；[完整place阶段事实](attempts/AT004_C01_PDU_resume_full_implementation/place_closed_stage_facts.json)3634643B/1f7fec13。当前cut已独立重放，四组限定timing与combined回执增量审核继续，无新门。外层phys_opt_design Default于13:26:15Z自然native0（149秒），native明确setup WNS>=0故未改网表；[实际physopt命令事实](attempts/AT004_C01_PDU_resume_full_implementation/physopt_command_zero_POST_pending_facts.json)。当前正在保存physopt检查点/完整POST，完整physopt phase及route尚未完成。

Place cut为14307nets/55605候选leafpins/1276disconnected/58361保留端点/44054相关逻辑pairs/21479边界pairs，入3087/出55；四组through LOAD各16，入setup/hold+0.603/−0.221ns、出+0.603/+0.057ns，非完整cutTNS、不保证跨cut路径或签核。已知逻辑跨SLR127对不等于SLL；8014无SLR位置对经独立逐端点核对，driver均为RAW内但S/P排除的7个GND/VCC常量，非P缺项；clock1429/reset6156为整网分类、其余constant429。979 touched sites中801共享，不等于释放容量。


## AT004完整place组合独立接受，physopt DCP保存

完整place native POST/locality0及compliance、四组timing和组合审核已独立接受；ingress/egress setup16条签名重合，非独立32或保证跨cut。physopt Default149s native0/未改网表，新DCP580691314B/f721fbbb已保存，当前全physopt POST/locality继续、route未到。holdFAIL/高拥塞/正式安全OPEN保持。[组合接受事实](attempts/AT004_C01_PDU_resume_full_implementation/place_combined_independent_review_accepted_facts.json)。


## AT004 physopt当前timing/fresh80独立接受

截至13:48Z，本轮fresh physopt完整时序与80保护结构已独立接受：时序报告仅Date/Command/Design State等页眉变化，正文与本轮place完全一致，WNS+0.147/TNS0/setup0、WHS−0.562/THS−1879.853/hold34042，timing FAIL；80为input48/gate16/down16、DONT_TOUCH全1、CE256/384/512及REF/INIT/实际位置与14控制源均核。当前phase专属collector/独立regular文件/inode/真实闭合marker证明是本次新采集，不能因网表未改而冒用place结果。完整physopt global POST/locality及当前9491P/连接/限定timing资格仍待。 [本轮子步骤证据](attempts/AT004_C01_PDU_resume_full_implementation/physopt_timing_fresh80_reviewed_substeps_facts.json)。


## AT004当前physopt globalPOST及成员原生闭合

截至14:05Z，本轮fresh physopt全局POST已真实completed1/diagnostic_eligible1、blackboxes0/COMPLETE_INTERNAL，integrity gate_issues为空且reset structure/fanout资格通过。[全局POST事实](attempts/AT004_C01_PDU_resume_full_implementation/physopt_global_POST_closed_facts.json)。当前literal RAW9514/S9507/P9491与原生origin对应关系闭合，9491实际P全SLR2、原对象存活、0缺项/替换，hard Pblock范围和三policy0保持；[本轮成员事实](attempts/AT004_C01_PDU_resume_full_implementation/physopt_membership_reconciliation_closed_facts.json)。A007对其余global/current成员增量审核继续，无新增门。本阶段native端口索引仍待原生闭合；完整有向cut/限定timing/combined合规仍待，完整physopt phase尚未qualified，route未到。


## AT004 physopt global/member/index独立接受

截至14:10Z，fresh physopt全局POST诊断资格、当前成员/native-origin对应关系/9491实际P全SLR2及完整native端口索引均已独立接受。global completed1/diag1/integrity gate空；9491P全原对象存活、无缺失/替换、LOC/BEL/区域及policy保持；索引269ports/269groups/2772alias/2170calls、167160alias事件全配对/unknown0。当前有向cut正常导出，限定timing/combined合规仍待，完整physopt phase尚未闭合，route未到。 [本轮global/member/index独立接受事实](attempts/AT004_C01_PDU_resume_full_implementation/physopt_global_membership_index_reviewed_facts.json)。12类本轮global报告去指定页眉后与place正文相同；current reset/CDC/BRAM/14exports及39源/144生产/175约束/162registry均重放核对。当前RTSTAT-13 CW1/15917 Warning、holdFAIL及正式reset/CDC/IO OPEN、高拥塞与固定窗/自适应窗口限制保持。


## AT004完整physopt闭合，原生Default route启动

截至15:20Z，本轮完整physopt原生POST/locality均0、candidate compliance true，于15:18:14Z真实闭合；9491实际P仍全原对象存活/all SLR2，无missing/replacement。完整有向cut14307nets/58361retained endpoints/21479boundary pairs；四组through LOAD各16，入setup/hold+0.603/−0.221ns、出+0.603/+0.057ns。当前已原生执行route_design Default并获取Implementation/xcvu9p许可、出现Starting Routing Task，实际布线运行中；尚无route结果。physopt剩余cut/timing/combined独立审核继续，无新增执行等待门。 [完整阶段与route启动观察](attempts/AT004_C01_PDU_resume_full_implementation/physopt_closed_route_started_observed_facts.json)。完整physopt stage facts3634705B/SHA7118bf3e，native0不代表hold或正式安全通过；完整时序WNS+0.147/TNS0，WHS−0.562/THS−1879.853/hold34042仍FAIL，高拥塞、固定窗UNAVAILABLE和正式reset/CDC/IO OPEN保留。


## AT004完整physopt组合独立接受，route持续

截至15:26Z，完整physopt阶段已独立组合接受：复用7份本轮子审核，剩余完整cut、四组bounded timing、compliance纯函数重放与combined回执均核实；9491原始P全SLR2、无缺失/替换，POST/locality均0于15:18:14Z闭合。当前route Default真实运行中，暂无route结果。 [完整physopt组合接受事实](attempts/AT004_C01_PDU_resume_full_implementation/physopt_combined_independent_review_accepted_facts.json)绑定A00733724B/SHA205b56d1审核。全局holdFAIL、高拥塞、正式reset/CDC/IO OPEN及原覆盖限制保持；四组through LOAD各16（入+0.603/−0.221ns、出+0.603/+0.057ns），两方向setup16条签名全重合，非独立32条/full-cutTNS或跨cut保证。SLR1同physopt LUT336107→282659、register435367→352889是全局重排观测，不能归因C01或转成释放容量；只用唯一顶层SLR行，重复O5/O6子行解析限制保留。


## AT004 route初始/全局原生警告保全

截至15:37Z，AT004原生route已从GlobalRouting/SLLAssignment继续到InitialRouting后的Phase4.2 UpdateTiming，进程正常、尚无route终态。当前[布线初始化/全局路由警告事实](attempts/AT004_C01_PDU_resume_full_implementation/route_initial_global_warnings_observed_facts.json)保留：Route35-3311局部SLL需求高，原生估计每列1440，SLR1→2总11721/17280、列最高1748(121%)；SLR0→1总12180/17280、列最高2296(159%)。这是列顺序估计，不是实际最终SLL使用或C01逻辑cut；总量低于容量不排除列热点。Route35-445至少135CLBs高pin；35-462 grp84/85/86各2path未populate，35-470共享driver导致一bus-skew group ignored（ID未印）。A007正做同阶段/覆盖影响增量核查，原完整验收不放宽。初始化failed2031260/unrouted1827047/partial204213及overlap0均非终态，不能判布线失败或成功；中间WNS+0.181/WHS−0.562/THS−1486.701非正式routed时序。高拥塞与正式reset/CDC/IO OPEN保持，继续自然route，无新停点。


## AT004 route局部SLL/bus-skew警告独立核查

截至15:38Z，本轮route中途SLL/bus-skew警告已独立有界审核，当前route仍正常、尚无终态。SLR1–2为2列超1440（1445虽显示100%仍超5、1748超308），SLR0–1为4列超额/峰2296；两次表相同不相加，旧同阶段无SLL表/该警告，不能做跨轮SLL改善比较。旧grp85/86四个missing目的pin与MLPcommand0 shared-driver ignored警告同本次，attentioncommand1旧整组ignored/本次2path未populate也不能判修复。当前physopt对应报告ID85/86/87/88先前10ns要求且均MET仍是该阶段事实，不能代替route全覆盖或推算有效组数。现有最终验证需逐对象核对这6个目的pin与shared source实际覆盖，保留ignored/unpopulated差异，不放宽约束，正式安全OPEN保持。[独立审核接受事实](attempts/AT004_C01_PDU_resume_full_implementation/route_initial_global_warnings_reviewed_facts.json)。35-445高pinCLB下界旧804/本次135仅该类别减少669，位置变化/全局重排不支持固定热点改善、C01因果或已可布通。


## AT004 route35-447中途拥塞警告，正常继续

截至15:40Z，原生route推进到Phase4.3 InitialNetRoutingPass，正常运行且无终态。此前Phase4.2后新增[Route35-447拥塞警告事实](attempts/AT004_C01_PDU_resume_full_implementation/route_congestion_prioritization_warning_observed_facts.json)：拥塞阻碍当前全部网络布通，工具将优先尝试完成全部连接再考虑时序优化。此为运行中警告，不等于已布通或自然失败；不改变原最终route/timing/DRC及bus-skew精确覆盖/正式安全验收。局部SLL超额、hold风险与正式reset/CDC/IO OPEN继续保留。


## AT004原生InitialRouting闭合，拥塞估计level7

截至16:09Z，本轮route的Phase4 InitialRouting已原生闭合；之后Route35-448与35-581均报告estimated congestion level7（128×128），分别为global/short routing及timing拥塞。原生拥塞窗口完整保留在[当前初始布线/拥塞观察](attempts/AT004_C01_PDU_resume_full_implementation/route_initial_routing_closed_congestion_observed_facts.json)。当前进程正常且尚无route终态；level7是本阶段自适应估计，不是固定原热点改善、C01因果、最终合法布通或已自然失败证据。既有35-447优先布通策略、局部SLL列超额、bus-skew精确覆盖与正式安全OPEN限制保持，继续原全门/真正terminal核验。


## AT004全局重布中间重叠观测与资源检查

截至16:30Z（北京时间00:30），AT004 actual Default route仍正常，当前Phase5.2 GlobalIteration1拆线重布中，首次报告1976955重叠nodes；这是运行中观测，不作终态或与旧final1148579的同阶段比较。[原生中间重叠事实](attempts/AT004_C01_PDU_resume_full_implementation/route_global_iteration1_overlap_observed_facts.json)及[本次资源观察](attempts/AT004_C01_PDU_resume_full_implementation/route_running_resource_checkpoint_20261017T1630.json)。当前RSS32.32GiB/MemAvailable461.98GiB/disk388.44GiB，从启动5080资源样本无既有保护触发。完整place/physopt已独立接受；initial-routing后adaptive global/short及timing congestion level7、Route35-447、局部SLL与bus-skew精确覆盖风险均保留，正式安全OPEN。继续本次自然route和完整fresh门/真正terminal审计。
