# E003 R004：完整 implementation 的独立架构与物理审核

负责人：A007 `/root/m002_physical_architecture_review`。仅维护本记录；工程实现、运行及三摘要由 A006/主控负责。以下为只读评判，不启动 EDA、不修改 RTL/约束，不再分叉。

**当前政策（2026-10-15）：**用户后续明确要求“不要设置强行停止 只要进程还在正常继续”。[持续执行补充](../../../../../mission/M002_ddr_separation_and_timing_recovery/full_implementation_continuation_2026-10-15.md)已取消 E003 当前与后继阶段的固定时间终止；§1–2 的12小时/24小时预算、截止和驱动描述保留为启动时历史，实际接管及后继 route 规则以§3为准。原合同及原始证据未改写。

**最新事实：**AT001原place成功及POST失败均保留。AT002新的place POST与独立physopt/DCP/完整POST均已闭合，stage自然0退出；正式physopt时序仍FAIL（WNS−1.290/WHS−0.620ns）。后继R003/AT001 route于22:45:40 UTC自然Tcl1失败，监督/driver于22:45:51 UTC自然exit1结束，无原进程遗留或时间/资源强停。Phase9报告245279个重叠节点、248289条signals因拥塞失败；未生成route DCP、完整POST、route_status或正式routed时序。§8.4为终态最终审核，§4–8.3的历史阶段观察保留；完整implementation成功验收未达成，正式reset/CDC安全保持OPEN。

## 1. 新授权下的流程、预算与验收合同审核

依据主控真实任务消息及随后落盘的[本轮合同](../../../../../mission/M002_ddr_separation_and_timing_recovery/full_implementation_contract_2026-10-15.md)：用户最新要求“进行一次完整的 implementation”，本轮 SM007/E003 取代上轮不再 place 和两小时成本边界；原 E002 失败事实保持。A007 已有界核对合同正文，6237 bytes、SHA256=`8461a1ff702b33f95cd03100086d2c1bb58ae590430598adb59818ffa2c0794b`。它已纳入阶段/总累计余额、显式 E003 profile、历史政策分开及执行/时序独立验收，本节没有新增人工批准门。

**结论：所述恢复路线与完整流程没有实质架构缺陷。**从 E002 AT008 已完整关闭的 debug/pre-place 状态恢复，使用同一 DCP、综合源/工具/embedded 约束，重新取得有限的实际恢复检查，然后顺序执行 place→physopt→route→最终 DCP/报告，能够构成当前基线的一次完整 implementation。无需重跑没有改变的 synth、OPT 或 debug；E002 AT009 没有新 closed 物理点，不能把其部分布局内存进度当作本轮恢复源。

恢复源仍为[原 AT008 debug DCP](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_materialized.dcp)，397261751 bytes、已审 SHA256=`e58d89707d21be85a3059a9ba7096651b6a277c125e831a47ebc7ec4f98fc44e`，及其完整 pre-place/POST/父链；此处引用既有身份，不重复读取大 DCP 或结构图。既有证明与失败边界见 [E002 R005 最终审核](../../../../E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R005/architecture_review.md#533-at009-真实终态与本阶段最终有界评判)。新的执行命令、当前凭据和新报告必须与继承的 OPT/debug/POST 来源分开记录。

**预算判断：**place/physopt 含恢复、检查和 POST 共12小时，route 含恢复和 POST 共12小时；另有从 E003 第一条 EDA 实际启动起算的24小时总墙钟，包含期间修复和间隔。合同要求每个 AT 取所属阶段余额与总余额的较小值，不因重试重置预算。这是明确、可执行的本轮成本上限；现有数据不能保证在该上限内完成或收敛。维持8 CPU、单 EDA、nice5、RSS192GiB、可用内存48GiB持续30秒与磁盘30GiB底线。实际启动/状态应绑定原预算起点、已用阶段额度及实际截止，后续对工程冻结差异只核这些预算隔离和真实执行来源。

**执行适配须保持身份清楚：**初审时安装的 `run_managed_eda.py` 仍限定 E002 attempt 目录并使用旧 LIMITS，必须针对 E003 明确适配新输出位置、授权 profile 与实际12小时阶段上限。旧恢复记录中的 `single_bounded_restart` 是 E002 当时政策；新用户授权应另有记录和身份，不覆写旧事实，也不把旧政策文字静默当作 E003 的现授权。上述属于已授权的普通入口适配及受影响验证，不扩大算法/时钟/约束门，不产生新人工停点。实现冻结/安装身份和实际运行预算尚待工程证据，本初审不预填它们已完成。

**阶段与最终验收：**

- 恢复准入继续核精确父 DCP/源/约束身份、零黑盒、关键 clock/hub/端点关系、已有 reset/CDC 条件和原生 DRC。相同 DCP 已关闭的完整 POST 可明确继承；新的物理变换必须按各阶段取得实际证据，不能拿原 pre-place 结果充当 placed/physopt/route 结果。
- place/physopt/route 的执行完成分别需要真实 native 成功、关闭的对应 DCP 和完整 POST/凭据。后继 route 应使用实际合格的 physopt 父点及原报告身份；单纯文件存在、内部阶段 checksum 或日志中的嵌套 Physical Synthesis Task 均不足以替代成功命令。
- 负 setup/hold/PW 数值继续作为诊断结果报告，不把时序收敛设为 route 的前置条件。既有允许的诊断分类和正式安全 OPEN 保留；新的身份错误、结构/clock 覆盖缺失或原生硬阻塞仍按实际证据处理。
- “完整 implementation 已完成”至少应同时取得实际 route 成功、closed 最终 route DCP、完整报告与 `routable>0`、`fully_routed==routable`、unrouted/partially_routed/routing_errors 均0的实际 route_status。程序结束、报告生成与物理连线完整分别记录；WNS/TNS、hold、PW/Max Skew、资源/拥塞、CDC/复位与最终签核另给结论。时序仍 FAIL 的完整诊断实现不能表述为时序通过或可用 bitstream。

此前 USER_SLL_REG 放置意图未满足、DDR1 BUFCE_ROW delay 上限及10个 BUFG 候选跳过等事实继续作为待比较限制；既有 warning 本身不新增门。保持 Hadamard/ScaleCode/format05、接口、core100MHz/UI200+200MHz，不运行 bitstream/GPU/板卡/PPL/ACC。

execution：本轮尚处入口准备，A007 已完成本合同范围的只读审核；verdict：流程、预算和阶段验收无实质缺陷，预算为上限而非完成保证；applicability：上述精确合同身份、E003 范围与 AT008 恢复源；review：合同审核完成，结果通过真实消息送达主控/A006。工程依已获授权适配、受影响验证后直接启动，后续仅按冻结差异和有意义物理阶段补充审核，不等待整段 EDA 才报告，也不增加逐项审批。

## 2. R001/AT001 冻结适配与 R002/AT001 实际启动审核

**冻结、CPU与安装：**仅审核[最终冻结差异](../R001/attempts/AT001_full_implementation_profile_cpu/production_delta_frozen.patch)，涉及4份生产Python（含新增`m002_execution_profile.py`）及1份新测试。[candidate_frozen.sha256](../R001/attempts/AT001_full_implementation_profile_cpu/candidate_frozen.sha256)为1351 bytes、SHA256=`ca2a9ced8beb3453a1a9d1cedcadeb3d98be0a50293e2c6931f763c2249dba70`；A007独立复算5/5项一致，[完整archive](../R001/attempts/AT001_full_implementation_profile_cpu/archived_sources.sha256)另核20/20项一致，SHA256=`f42db41e5c25bf79ed83808b5242850dc04b9b2cdf1b777a44116637849e3fd7`。与AT009冻结源逐项比较的9份Tcl均相同。本轮[最终测试日志](../R001/attempts/AT001_full_implementation_profile_cpu/cpu_tests_final.log)实际129项、3.374秒、OK；[validation](../R001/attempts/AT001_full_implementation_profile_cpu/validation_result.json)分解为14项profile新测试+13恢复+6隔离+96原物理测试，均为本轮执行，A007未重跑。[installation](../R001/attempts/AT001_full_implementation_profile_cpu/installation.json)于12:21:22.374381 UTC安装，5项after均独立匹配实际安装及archive，3项既有生产文件before均匹配AT009原stage_sources。没有安装上轮missing-physical候选。

**新profile隔离与累计计时：**冻结代码将E003限制在明确profile、精确合同SHA和R002/place或R003/route attempt根；报告授权必须等于manager授权，manager命令另绑定授权文件身份，仅环境变量或单独report标记不能替代它。原E002 LIMITS保持place/route7200秒。持有单EDA锁后才核累计账本：所属阶段每个已结束AT按manager command开始至status结束计费，缺终态/未completed/有survivors拒绝继续；新AT不能重置同阶段已用时间。全局起点在Vivado实际Popen成功后形成，原first-launch anchor与最早实际启动receipt一致；首anchor先写、manager可见receipt最后发布。后续仍以该anchor+86400秒计算包含修复/间隔的总墙钟，并取阶段余额与总余额较小值。CPU负例覆盖缺失/改写anchor、预算耗尽、未闭合尝试/存活记录、跨阶段累计和仅标记授权等；这不是长期运行全部异常路径已实际发生的证据。

**历史父链未被改写：**[实际源资格](../R001/attempts/AT001_full_implementation_profile_cpu/actual_source_qualification.json)记录工程12:18:56.892835–12:19:17.392375 UTC重新核339输入/45 DCP及AT008完整点PASS；A007只独立核其9项小文件身份链接，未重扫339源、45 DCP或大图。[canonical原父链](../R001/attempts/AT001_full_implementation_profile_cpu/qualified_original_pre_place_parent.json)206204 bytes、SHA256=`cb71534a967e2ed472962cd1dc18c7bdcbeba463e059e13dafac140d3f0f3a8e`，与E002已审核父链相同；其原single_bounded_restart=true不改。未变化的完整POST回放明确复用E002 AT012已有结果，不冒称本轮重新生成POST。实际[E003 recovery_parent](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/recovery_parent.json)207212 bytes、SHA256=`31b6b6d3ccf32081801c0b12128eb0faeda982ba930bbbd5bc4ed72e65bf0be3`与canonical逐字段比较，仅`execution_authorization`、`restart_scope`、`single_bounded_restart`三项变化；DCP、完整证据及历史OPT/debug receipt原路径全部保留，新false政策准确来自本次授权，不表示AT009部分布局可恢复。

**route判据与顺序：**冻结finalize仅在真实E003授权下增加实际route counts检查：routable>0、fully_routed等于routable、unrouted/partially_routed/routing_errors全0，否则不写合格最终diagnostic_evidence。既有真实成功physopt父链、当前阶段DCP/POST与来源检查保留，未添加setup/hold/PW必须为正的route前置门。[本轮驱动](../R001/attempts/AT001_full_implementation_profile_cpu/run_full_implementation.py)顺序等待managed place/physopt成功终态再进入其合格父点的route；不并行两条EDA、不因本静态审核额外等待批准。route资格逻辑已核，实际route尚未执行，最终结果不能预填。

**实际启动及截止：**[R002/AT001 command](../R002/attempts/AT001_full_pre_place_restore_place_physopt/command.json)记录manager起点2026-10-15 12:21:48.608023 UTC、初始已用阶段0秒、timeout43200秒、CPU0–7/nice5。实际[EDA启动receipt](../R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_eda_started.json)为12:22:11.492419 UTC、PID3678158；attempt、report及全局anchor三份记录逐字节相同，双方授权记录亦相同。[effective_budget](../R002/attempts/AT001_full_pre_place_restore_place_physopt/effective_budget.json)正确记录place/physopt截止2026-10-16 00:21:48.608023 UTC、全局截止2026-10-16 12:22:11.492419 UTC。两起点相差约22.9秒：阶段从manager计费，全局从实际EDA启动计费，不能混成同一时间。A007本次核到原日志只有对精确AT008 debug DCP的`open_checkpoint`，没有新place/physopt/route完成证据；fresh guard仍待实际完成。

本阶段execution区分R001准备/验证已完成与R002真实EDA已启动；verdict为上述冻结profile、累计计时、历史来源及route判据未发现实质缺陷；applicability限本节manifest、安装身份和真实启动记录；review为A007有界审核完成。结果已通过真实消息通知主控/A006，既有授权运行继续，无新增启动停点；后续按实际guard与物理里程碑审核，正式安全及物理/时序签核仍OPEN。

## 3. 取消固定时间终止：实际监督移交与后继 route 审核

**用户决定与适用身份：**本节仅审核最新持续执行指令的实施，依据补充原文1987 bytes、SHA256=`17acf92465c4e0f3256a40ff78f953bc7398b1a9a68ed53da79ae23fb8db8363`。A007独立复算原合同仍为6237 bytes及§1原SHA；原`command.json`、`started.json`和`effective_budget.json`均与接管前绑定身份一致，生产脚本与本AT冻结`stage_sources`仍一致。取消时限不改变诊断验收、资源保护、源/工具/约束或算法。§2冻结适配审核仍适用于其源与证据；其固定时间政策已被本节替代。

**真实接管已生效：**工程的[冻结监督脚本](../R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/adopt_no_wall.py)为16161 bytes、SHA256=`c52c042f0e24667e165beac9d5d75b6e92265f5cc3accd260de10e426ead4aca`，与manifest、[validation](../R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/validation.json)及[adoption_ready](../R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/adoption_ready.json)绑定一致。[handoff_effective](../R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/handoff_effective.json)在2026-10-15 12:32:57.101255 UTC记录仅原监督PID3677862/start_ticks917946821进入T；worker3677864/start917946826、Vivado启动PID3678158/start917949115及PG3677864不变。report的[runtime_supervision_override](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/runtime_supervision_override.json)精确绑定该handoff，`supervision_profile=m002_no_wall_continuation`、`timeout_seconds=null`、`global_deadline_utc=null`。A007独立核脚本、补充、原start/command/budget和handoff共6项链接，没有仅凭文档声称生效。

A007于12:37:28.799117 UTC直接读取`/proc`：旧监督仍T且CPU ticks仍943；上述worker、Vivado启动器、下级启动器3678177/start917949119、native3678249/start917949130均为原身份和PG，native CPU ticks由接管时159658增至207606；新监督3687878/start918013654为S。六者均nice5/CPU0–7。[工程连续性记录](../R002/attempts/AT001_full_pre_place_restore_place_physopt/supervision_handoff/post_handoff_continuity.json)另记录12:34:06原native已增长17749 ticks。12:37:26实际资源样本RSS22083657728 bytes、MemAvailable427412832256 bytes、磁盘520961384448 bytes，未触发既有保护。原监督的计时循环实际暂停，冻结脚本没有恢复它的SIGCONT路径；它保留真实EDA flock直至原子树关闭。

**代码及隔离验证范围：**A007已读最终冻结脚本及两份实际CPU自检源/结果。监督循环没有elapsed/global/no-output终止分支，只保留RSS192GiB、MemAvailable48GiB持续30秒、磁盘30GiB保护及进程/真实错误处理。`ACTIVE`在单PID SIGSTOP前设置；主流程外层异常处理可对同一仍活跃子树继续resource-only监督，循环异常落盘重试，SIGTERM/INT显式记录并保持监督。此前指出的post-stop/pre-monitor主异常空窗已补。两项隔离自检分别实测仅停dummy监督时原dummy child仍推进、错误PID身份拒绝、终态wait码解码，以及worker真实退出7→确认无活动子树→旧dummy监督单PID退出−9→孤儿回收；A007未重复执行测试。隔离测试不代表生产终态交接已发生，也不证明所有操作系统/I/O异常已实测。

**终态与真实来源必须分开：**采用原worker在`/proc/stat`的真实zombie wait status（field52）判定worker退出；只有无活动owned后代才单PID SIGKILL旧暂停监督，避免其Python `finally`对原子树发送终止。随后取得真实flock、确认原owned身份回收，才写采用新监督的当前`status.json`。其中`native_exit_code`明确是physical worker退出；实际Vivado退出继续由`launcher_status.txt`记录，不能把worker0单独当作Vivado/native各阶段通过。旧manager的−9是监督替换的管理性退出，旧driver随之产生的非成功记录也不是物理失败或成功，分别保留。当前这些生产终态步骤尚未发生；若终态后回收等待出现异常，工程已通过真实消息承诺按proc/wait事实单独报告，不把等待当作EDA推进，不添加新的计时杀进程条件。

**后继 route 无固定时限且资格不放宽：**冻结监督在place worker正常关闭后直接启动未改的`run_m002_physical_stage.py route`，使用同一原执行源授权及另行绑定的持续执行补充；不会调用旧timed manager或`profile.budget()`，route命令timeout为null，仍由同一无wall监督循环读取实际Popen poll/wait。旧授权文件中的12小时/24小时字段是冻结来源凭据，不能再解释为当前执行上限。A007核过未改的`parent_recovered_place()`：仍要求当前place监督成功且无survivors、真实launcher/native成功、当前physopt DCP及完整POST/源/约束身份、place与独立physopt的真实命令成功；未取消最终完整routing counts验收，未新增正时序前置门。未来route路径目前仅完成静态审核，真实启动与结果留待对应证据。

**实际物理里程碑及边界：**[fresh pre-place证据](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/pre_place_evidence.json)与原生guard receipt显示12:34:04 UTC恢复检查完成、native Tcl0、blackboxes0、DRC blockers0、clock_groups_verified1，`diagnostic_eligible=true`。小型guard/command原文及当前日志已读，日志进入`place_design`/Placer Phase1；没有placed/physopt/route完成凭据。live内部no_clock/unconstrained/generated/multiple/loops均0，hub实际50MHz/530端点，300MHz元数据不匹配保持；正式reset/CDC安全OPEN。此处读取fresh摘要和小凭据，不冒称重新审核全部DRC/大图或重跑完整POST。

本节execution：无时限监督接管已实际生效，R002 place正在运行；verdict：本次最终冻结实现及实际接管未发现阻止正常持续执行的实质缺陷，先前主异常空窗已关闭；applicability：上述补充、冻结脚本及精确原进程身份；review：A007本轮有界审核完成，已真实消息通知主控/A006，无新增审批。生产terminal/reap、后继route及完整物理/时序验收仍待真实发生；本审核结束不表示后台持续监控或SM007全局完成。

## 4. Post Commit 拥塞告警与真实 place 命令成功（POST 尚待完成）

**首次告警边界：**A007于2026-10-15 14:35:17 UTC只读核到[当前原生日志](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/vivado.log)第924行`Place 46-14`：placer判定设计“highly congested and may have difficulty routing”，建议读congestion报告。它是实际布线风险告警，原文本身没有热点坐标、具体资源/模块或未布通数量，也没有native fatal；不能由此判定设计不可布通、归因某条DDR路径或作为新增停止条件。此次走到更晚placer阶段才观察到告警，不等于相对E002已经证明设计退化。

**过程时序及三类既有警告：**第909/915行的Post Placement Timing/Replication WNS均−1.858 ns，原文要求正式`report_timing`取得准确值；第880行−1.884/TNS−1349.388属较早内部估计，数值变化不单独构成正式时序改善。`Place 30-1229`记录USER_SLL_REG未满足，打印100次后被抑制，不能把100当全部受影响寄存器数；它表明SLL/Laguna放置意图未全部实现，实际跨SLR路径及延迟影响待报告。DDR1 `c0_riu_clk`和`u_bufg_divClk_0`的BUFCE_ROW delay capped4告警表示为PLL/RIU MAX_SKEW限制可用延迟范围，未单独证明skew违例。BUFG优化准确统计为10候选、插入0、driver复制0、因placement/routing conflicts跳过10、因timing/netlist编辑失败跳过均0；表示这条候选优化未应用，不能等同10条失败时序路径、10个缺失时钟buffer或拥塞根因。前述小型告警摘录与观测身份保存在[A007观察记录](../../../../../agent/A007/report_20261015_E003_post_commit_warning_observation.json)，不改写运行日志。

**随后到达的实际命令里程碑：**[place_command_result](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/place_command_result.txt)已真实记录`command=place_design`、start1792067666、end1792074961（14:36:01 UTC）、`native_tcl_code=0`，日志明确`place_design completed successfully`，报告337 Infos/143 Warnings/0 Critical Warnings/0 Errors。这关闭的是place命令，不代表完整place POST、独立physopt或route成功。14:37:06观察时正在写checkpoint，`place.dcp`、`place_result.txt`及正式timing/congestion/SLR报告尚未出现。

在命令结束前新打印的`Post-Placement Estimated Congestion`中，全局四向Global/Long/Short Region Size均64×64；SLR0各类四向同为64×64，SLR1/2存在16×16、32×32、64×64混合。该表进一步支持拥塞区域较广，不能将Region Size读作资源利用率百分比、违规计数或最终router结果，也不能仅凭尺寸直接定位控制广播或DDR接口根因。

**正式证据的核查顺序：**冻结`m002_post`按place native成功→写DCP→报告→完整结构/clock/CDC/reset等POST关闭执行，现有代码不需为这条告警更改。place阶段本来就会输出`timing_place.rpt`（min/max）、PW/bus_skew、`congestion_place.rpt`（等级≥3）、`utilization_slr_place.rpt`及`slr_crossing_place.rpt`（最多32条）；详细top32 setup/hold及worst_per_clock在physopt/route才输出。以这些实际报告对照资源和热点坐标、SLR分布/穿越、关键路径及DDR时钟检查，再判定三类警告的实测影响；有限top32集合不能证明其余路径不存在问题。最终可布通性仍依实际route_status全布通及完整POST，时序和正式安全分开评判。

阶段execution：真实place命令成功、POST正在产生；verdict：新告警确认拥塞/后继布线风险，尚不足以作根因或最终不可布结论；applicability：当前同源E003/R002/AT001截至上述观测；review：告警范围已独立审核并实发主控/A006，正式place POST及后续结果待证据。授权运行继续，无额外停点。

### 4.1 Closed place DCP 与首份正式利用率报告

随后工程交付[place_checkpoint_facts](../R002/attempts/AT001_full_pre_place_restore_place_physopt/place_checkpoint_facts.json)：native place实际7295秒，closed `place.dcp`579080094 bytes、SHA256=`37591435c8f95383a0910978b986c035a102c762b24b69b76e59b63d49e905f7`，全ZIP成员CRC、part/top/board/build身份及核验期间稳定性由A006实际核查。A007独立复算其中native command、冻结log snapshot和override三项小文件身份均一致，直接看日志checkpoint generated/write_checkpoint完成；不重复读取大DCP或冒称独立跑过CRC。此时place POST仍在进行。

[正式utilization_place](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/utilization_place.rpt)标注Vivado2025.2/6299465、正确device/top、2026-10-15 22:39:43本地时间及`Design State: Fully Placed`。当前证据支持以下事实：

| 指标 | 全局 | SLR0 / SLR1 / SLR2 |
| --- | --- | --- |
| 已占用CLB站点 | 146472/147780，99.11% | 99.86% / 99.09% / 98.39% |
| CLB LUT | 814911，68.93% | 76.15% / 68.10% / 62.54% |
| CLB寄存器 | 1019696，43.13% | 44.37% / 40.59% / 44.42% |
| Block RAM Tile | 941，43.56% | 57.01% / 22.29% / 51.39% |
| URAM | 752，78.33% | 70.00% / 80.00% / 85.00% |
| DSP | 5451，79.69% | 70.79% / 82.24% / 86.05% |

高CLB站点占用说明布局遍布接近全部CLB站点，不能解释为LUT/寄存器槽全部用尽；它与较广拥塞相容，但单表不能确定是哪类逻辑、控制集合或布线通道造成拥塞。SLR0 LUT负载较高，SLR2 URAM/DSP较高，需与实际拥塞区域和路径位置对应，不能只按全局平均剩余资源判断局部可布性。

同一报告实际SLL占用为SLR1↔SLR0 8812/17280（51.00%）、SLR2↔SLR1 9451/17280（54.69%），总18263；现证据不支持“全局SLL容量耗尽”，仍不能排除局部SLL列/端点约束问题。SLR2↔SLR1两方向的TX/RX_REG使用字段均0，SLR0→SLR1 RX-only1/Both518、反向RX-only449/Both244；这是当前实际放置统计，尚未逐cell映射USER_SLL_REG告警，不能把统计直接等同全部属性违例或功能失效。BUFGCE总量13/720（1.81%）也不能推翻10候选因placement/routing conflicts跳过的原生日志：全局buffer cell总数不等于特定位置/区域可用路由，报告自身提示该表不是完整global clocking资源可用性报告。

截至14:42:03 UTC，正式timing/congestion/SLR crossing与完整integrity仍未生成；上述是已产出报告的阶段审核，不预填POST、独立physopt或route完成。

### 4.2 正式 placed 时序及警告的首批实测影响

[timing_place.rpt](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/timing_place.rpt)已在2026-10-15 22:45:22本地时间由`report_timing_summary -delay_type min_max -report_unconstrained`实际生成，Design State为Fully Placed；后续日志已进入report_drc，报告调用已返回。A007独立复算2399253 bytes、SHA256=`34fad5c8ed75e5feb9a1fd6292f303c3c858d3a2b47fbc6e2cc4f9575aec68ef`，与工程[place_timing_facts](../R002/attempts/AT001_full_pre_place_restore_place_physopt/place_timing_facts.json)一致，并读取摘要、相关时钟表、最差setup/hold及DDR1 Max Skew条目。正式阶段结果为WNS−1.819/TNS−818.651 ns、setup失败1014/3209658端点；WHS−0.620/THS−2150.556 ns、hold失败33141/3208214；WPWS/TPWS均0、PW/skew失败0/1095362。**本placed点时序FAIL；不是native执行失败，也不新增诊断继续停点。**报告的互连延迟仍标注estimated，因此正式placed时序不等于最终routed时序。

**失败分布比单一WNS更能限定结论：**

| 时钟范围 | setup WNS / TNS（ns），失败端点 | hold WHS / THS（ns），失败端点 |
| --- | --- | --- |
| GTYE4_CHANNEL_TXOUTCLK[3]_1 → xdma_0_axi_aclk | −1.819 / −805.234，917 | −0.173 / −1.162，10 |
| xdma_0_axi_aclk → GTYE4_CHANNEL_TXOUTCLK[3]_1 | −0.285 / −2.403，31 | −0.620 / −114.871，297 |
| xdma_0_axi_aclk本时钟域 | −0.588 / −8.354，34 | −0.142 / −53.227，1863 |
| core100MHz本时钟域 | −0.317 / −1.677，28 | −0.331 / −1453.162，25144 |
| DDR0 UI200MHz本时钟域 | +0.312 / 0，0 | −0.164 / −42.630，1775 |
| DDR1 UI200MHz本时钟域 | −0.358 / −0.982，4 | −0.350 / −244.675，2449 |

当前全局最差setup在PCIe硬核到XDMA AXI域，不能将−1.819直接解释为core计算路径瓶颈。其报告第6607行起的具体路径终点为XDMA `RQ_FIFO/Head_reg[220]/CE`，数据延迟5.070ns，其中logic0.669ns/两级LUT、estimated route4.401ns，clock skew−0.261ns并有0.381ns Inter-SLR compensation；报告沿用既有MultiCycle约束。本审核未改变约束或将时钟关系判为可随意忽略。全局最差hold第6412行起位于XDMA `aa256_tdata_ff_reg[51]`→PCIe `SAXISCCTDATA[51]`，数据延迟0.168ns、skew+0.272ns；当前core域大批hold失败同样需要后继物理结果，不能因其setup较小而称core已通过。

**对旧警告已能增加的实测判断：**DDR1 PLL/RIU Max Skew显示正slack样例+1.450、+1.458、+1.432ns，且本报告全局PW/skew失败0；现证据不支持把BUFCE_ROW cap4警告等同为本placed点skew失败，也不证明该限制对其它时序没有代价。DDR1 `d1_mig_slice`的Laguna ready路径出现正式hold−0.350ns，实际源/目的落于LAGUNA_X20Y194/X20Y314；它证明存在已采用Laguna且仍有hold风险的路径，但没有逐cell对齐被抑制的USER_SLL_REG警告，不能直接宣称二者因果。BUFG十候选未应用的事实保持，尚无证据证明这些候选是当前全局最差路径或拥塞根因。

完整place POST、正式congestion/SLR crossing与后继独立physopt仍待实际证据；本节已通过真实消息将上述物理/时序分布及DDR1正skew结果通知主控/A006。

独立[脉宽报告](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/pulse_width_place.rpt)随后于22:57:39本地时间实际返回，`report_pulse_width -all_violators`产物1217 bytes仅表头，无违例项；[bus-skew报告](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/bus_skew_place.rpt)22:57:50实际返回，2108394 bytes、A007独立SHA256=`d52427d5e678cf3ecd58a6625b8cbb3cd9c6afde907fe41bf46ff9907db8ff6c`。有界解析其完整摘要94项，负slack0、最小+3.015ns（requirement4.000/actual0.985，Slow）。这使独立bus-skew在现有约束集合的placed报告中也获得正面证据；不将其扩展为全部CDC/reset安全已证明或最终routed结果。

### 4.3 正式拥塞窗口：风险已定位到区域，尚不能直接判定根因

[congestion_place.rpt](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/congestion_place.rpt)由冻结命令`report_design_analysis -congestion -min_congestion_level 3`实际产生，报告23:02:52本地时间/Fully Placed，日志随后显示调用已返回。A007独立核全部48行表及身份32582 bytes、SHA256=`5983689853fa2d667f03f260cb31e8c7a008651e1438a1a2370e2eda24cae971`。四向×Global/Long/Short共12个组合均有Level3、4、5、6窗口，最大报告Level6；这48行是不同方向/类别/等级的窗口，存在嵌套和重叠，不能当成48个独立失败或最终router未布通数量。

多个窗口集中在报告原始tile坐标Y约180–293，列出的Cell Names主要涉及MLP `shared_compute`/dot、weight与projection repack、`input_frontend/g_quant[1].u_quantizer`及DDR1 mem_intfc/addr_decode；South/Long Level6另有Y770–833的attention区域。以下示例按原报告保持坐标，不从坐标数字自行推定SLR归属：

| 方向/类别/等级 | 原始Window | 报告列出的局部资源与层级 |
| --- | --- | --- |
| North / Global / 6 | CLEL_R_X27Y183 → CLEM_X57Y246 | LUT70%、URAM100%；DDR1 addr_decode12%、mem_intfc11%、MLP branch0 dot7% |
| South / Global / 6 | CLEL_R_X27Y199 → CLEM_X57Y262 | LUT71%、URAM100%；MLP输入量化10%、DDR1 mem_intfc9%、addr_decode7% |
| East / Global / 5 | CLEL_R_X54Y234 → DSP_X69Y265 | RAMB100%、URAM100%、DSP69%；shared_compute15%、branch0 dot14%、weight_repack8% |
| South / Long / 6 | CLEL_R_X19Y770 → CLEL_R_X49Y833 | DSP90%、URAM87%；attention postprocess_store37%、projection right2 shard12%、center12 region10% |

表内另有较小窗口DSP100%或LUT90%的实际记录。由此可以确认部分局部专用资源已经占满，不能用全局LUT68.93%、SLL约51–55%等平均数排除局部拥塞。Cell Names百分比仅按工具所列窗口统计引用，不解释为拥塞因果贡献率；层级彼此可能嵌套，不能相加为归因比例。现有证据支持“多个计算/重排/存储及DDR相关区域的局部资源和互连压力需在后继route中检查”，不足以确认单一控制广播、USER_SLL_REG或十个BUFG候选就是根因，也不能直接把这些窗口等同当前PCIe→XDMA全局最差setup路径的原因。

独立[utilization_slr_place](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/utilization_slr_place.rpt)6932 bytes、SHA256=`b36ecdd61cd253a2cd819840f176168e7a048dcdb448f918117ddd6452597d53`已读，§4.1分SLR/跨边界统计均一致。SLR crossing路径报告及完整POST仍待实际生成；拥塞结论已实发主控/A006，未触发新的运行停止或代码/约束修改。

### 4.4 正式 SLR crossing 与四个跳过 BUFG 候选的实际交集

[slr_crossing_place.rpt](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/slr_crossing_place.rpt)206533 bytes、独立 SHA256=`19125f091af039ab94cefa69c1020d62f9e02ee0e5068455c7417b7bd9954773`。其 fanout 表有32行；timed crossing/logic-level 部分只有表头，不能据空表判断零跨SLR路径或时序通过。层级 TOP 列13856 cross nets，与 utilization 的18263 SLL 用量统计口径不同；括号指精确层级自身驱动，嵌套行不可相加。

十个跳过的 BUFG 候选中有四个精确名称出现于该有界 top32 表，当前仍为 LUT 驱动且跨 SLR0/1：

| 报告行 / MLP net | 驱动 | 总扇出 | SLR0 / SLR1 loads |
| --- | --- | --- | --- |
| 118 / down projection `out_payload_r[8191]_i_1_n_0` | LUT4 | 8201 | 4105 / 4096 |
| 122 / down projection `error_r_reg_0` | LUT6 | 6192 | 3119 / 3073 |
| 125 / gate projection `out_payload_r[0]` | LUT6 | 6145 | 3073 / 3072 |
| 126 / gate projection `input_fire` | LUT5 | 4652 | 2348 / 2304 |

四项驱动均位于SLR0。这是高扇出控制/重排信号局部性风险的实际证据，尚不构成它们导致全局最差时序或Level6拥塞的因果证明；其余六项没有出现在top32也不证明其无跨SLR风险。Hadamard valid_s1–s4 在该表也跨 SLR0→2，本审核不授权改变算法。USER_SLL_REG 警告打印在100项后受抑制，100不是全部受影响cell数。

本次6份物理报告身份、48个拥塞窗口/12种组合、32项fanout及四个精确交集的有界核查记录见 [A007物理证据](../../../../../agent/A007/report_20261015_E003_place_physical_bounded_review_evidence.json)。其15:09:24 UTC快照描述的是尚未获知完整POST终态的观察，原文件保留；当前终态见下节。

## 5. 实际 place POST 失败、CDC 代表源变化及无 wall 终态

### 5.1 执行终态与影响范围

[integrity_place.json](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/integrity_place.json)观察时间15:08:08.303566 UTC，唯一 gate issue 为 `critical_CDC: ValueError: new/unclassified critical CDC path`；`reset_structure.qualified`、`reset_fanout_observation.qualified` 均 true 且 issues 空，`cdc_classification=null`。[原place_result](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/place_result.txt)仍 completed0/diagnostic_eligible0，原失败不得改写。place native0/closed DCP/正式测量与完整POST失败分别成立；后继独立physopt、route均NOT_RUN。

[终态事实](../R002/attempts/AT001_full_pre_place_restore_place_physopt/terminal_facts.json)与原始回执显示：原worker于15:08:16.711485 UTC已Z，wait_status256解码exit1，active_owned空；此时旧监督仍T。随后只释放旧监督PID，15:08:16.816356记录旧监督消失、owned_after_release空；最终status为completed、native_worker1、stop_reason=null、owned_survivors空，launcher另记实际Vivado native1。此处completed表示监督已结算，不是实验成功。A007独核9份小记录身份全部一致，并在后续实际读取/proc时确认11个原PID/start_ticks身份全部不存在。

旧 `implementation_chain.json` 将manager调用标为stage=place、exit_code−9；这是已停止监督器被行政替换的返回值，发生于真实worker退出后，**不是 place_design 或 Vivado 原生退出码**。`terminal_facts.json`已明确分开该scope；原driver非成功阻止了旧route派发。此次失败没有触发墙钟或资源停止，既有无固定时限政策生效。峰值树RSS34706485248 bytes、最低可用内存415355936768 bytes、最低磁盘515519860736 bytes来自工程合并采样；本审核未重复扫描全资源日志。

### 5.2 实际 DDR1 AUX 双源 cone 的独立核查

[精确CDC增量](../R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_place_CDC_delta.json)仍有8条Critical，6条tuple不变；仅 DDR1 psr0 与 psr_aclk1 两条 CDC-10 从 `d1_gate/inst/u_ready_cdc/arststages_ff_reg[3]/C` 改报 `u_base_reset_cdc/arststages_ff_reg[3]/C`，来源/目标clock仍 `mmcm_clkout0_1`→core，目标仍各自 `syncstages_ff_reg[0]/D`。

A007流式读取原生 [reset_graph_place.tsv](../../../../hardware/vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt/reset_graph_place.tsv)，119919819 bytes、独立SHA256=`8eddbbdd7a6d90f51bc9497310fc59ba29e2c2a7d4747e45a773dd7381eac542`，仅提取18个相关CELL及85个PIN，排除巨大net alias字段。两目标D都由 `psr_aclk/.../ACT_LO_AUX_i_1` 的LUT1（INIT2'h1）驱动；该反相器的输入来自 `d1_gate/inst/aresetn_INST_0` 的LUT2（INIT4'h8），I0/I1分别为base/ready末级Q，即 `~(base_Q & ready_Q)`。两源末级C都实际连接DDR1 UI clock；两个目标链各4级FDRE，C均core、ASYNC_REG=1、CE=VCC、R=GND、INIT0且逐级D←Q连续。

四份相关真实primitive exports（place_5/6/9/10）尺寸/SHA与原完整资格中的身份逐一吻合，并独立读取全部16个实例：两个源链为FDCE/INIT1，base CLR inversion0、ready inversion1；两个AUX链为FDRE/INIT0。未显式覆盖的C/D极性沿用资格已绑定的Vivado UNISIM默认模型，不从空graph属性猜值。A007还直接对比旧AT008与本place的8个结构字段：AUX、7条async、3条HostSplit、gate sources、reported sources、launch C→Q、DDR输出与critical targets均完全相同。详细抽取、原文件身份与终态核查见 [A007 CDC/终态证据](../../../../../agent/A007/report_20261015_E003_CDC_terminal_bounded_evidence.json)；工程全14导出/模型检查见[结构比较](../R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_place_reset_proof_comparison.json)。

由上述实际结构可支持“同一双源复位cone选择了另一代表起点”的窄诊断解释。不能将此解释扩展为任意同名源白名单，也不证明异步复位、重汇合或事务安全；正式reset/CDC安全保持OPEN。

### 5.3 最小恢复边界与当前审核状态

工程在新R001 CPU尝试对原始完整place报告、实际结构图和14导出重放修正分类，验证规则而不改原AT001 integrity/result/status。新规则应只接受四个固定AUX目标各恰一条、准确UI→core clocks、本域base或ready末级/C；每个目标的实际双源Q、极性与四级链必须均被结构资格覆盖，另外四条tuple与Critical总数8严格不变。原OPT canonical参考身份继续冻结，另记本次实际代表源选择，不能让原参考或实际报告被改写成一致。

**主控15:20后实发的最终方案取代早期“CPU重标资格后继承整套POST”的准备方案：**从原place命令native0与同一closed DCP精确身份恢复，通过fresh live guard后，在新AT重新实际采集整个未通过的place POST，再直接独立physopt；不调用place、OPT或debug。原始place查询虽已产生，旧POST整体仍未通过，CPU分类重放仅为规则验证，不能冒充新原生POST完成。此方案保持失败关联清楚，避免引入复杂旧报告重标或通用递归恢复。后继route仍须真实成功physopt父链、完整POST与来源身份；取消墙钟停止与资源保护保持。

execution：AT001已自然失败闭合，A007继续审核窄修复/恢复冻结证据；verdict：本次原图支持代表源变化解释，所述最小恢复边界没有已知实质架构阻碍；applicability：仅上述exact place DCP、8条CDC集合与实际结构/导出身份；review：结论已真实通知主控/A006，分类候选与受影响验证尚待交付，无新增人工审批，工程独立工作继续。

### 5.4 冻结修复、受影响验证与实际恢复启动：本轮审核交付

工程 [R001 AT002](../R001/attempts/AT002_placed_CDC_recovery_cpu/installation.json)于15:34:51.788451 UTC在空闲EDA lane锁下完成安装：`m002_physical_evidence.py`、`run_m002_physical_stage.py`、`m002_resume_physical.tcl`、新增 `run_m002_no_wall.py` 与其测试共5项。A007逐项计算生产及冻结副本尺寸/SHA，5/5与安装记录相同；[validated_sources.sha256](../R001/attempts/AT002_placed_CDC_recovery_cpu/validated_sources.sha256)列出的50份冻结文件也逐项一致。修改限于诊断分类、恢复来源/阶段记录和无wall监督，未改变RTL、XDC、设计策略、算法或时钟目标。

**分类审核：**仅在place/physopt/route报告中允许四个固定AUX目标分别由本域base或ready末级/C代表；`normalized==canonical`、actual总数8及一对一归一化共同拒绝缺项、额外项和双代表。原生报告解析仍检查全部声明/明细数及重复；实际graph同目录/同阶段、两条Q、四级链/clock和qualified结构/14导出/fanout均须成立，canonical OPT SHA仍固定。新实际tuple另行记录，正式安全仍OPEN。

**恢复审核：**只准入本次自然POST1、无遗留进程、原place native0/closed DCP及仅两条DDR1代表源变化的精确失败；原源112份文件由closure manifest/completion绑定并独立验算，旧integrity/result/status保持失败。新 `recovery_parent.json` 明确 `physical_post_complete=false`。真实fresh guard后执行新的完整 `m002_post place`，随后独立physopt；Tcl分支不再调用place/OPT/debug。final和后继route父链仅接收新的physopt命令回执，OPT/debug/place原回执保存在historical scope，并验证新原生place POST确实先于physopt发生。

审核中两项会误拒合法恢复的问题已实发并修复：代表源列表改为稳定排序，避免不同Python进程的set顺序破坏父JSON相等；新stage manifest只绑定旧closure manifest及completion，旧归档另行逐path/hash核查，避免把旧同名脚本误当新执行代码。BRAM模型列表只按path排序后比较，全部身份及其他图字段保持严格相等。

[最终测试原日志](../R001/attempts/AT002_placed_CDC_recovery_cpu/cpu_tests_final.log)23936 bytes、SHA256=`9c2ed2eb73a32ec718d343ad755fd7f2ebf9e6f0582830cd22d2d0acd8e2400a`，150项/30.997秒/OK。A007独立数到150条ok，其中129项既有回归、21项本次受影响测试；没有另跑测试。新增验证覆盖精确CDC异常/错源错clock/缺链/重复条目，三种PYTHONHASHSEED真实子进程序列化，旧档篡改拒绝，新POST与回执作用域，Tcl恢复调用顺序及live guard拒绝。无wall监督的隔离真实子进程测试分别保留place exit7、route exit0；故意设置过去的旧wall anchor仍不触发停止。测试中的fixture/部分mock只证明相应解析、scope及控制逻辑，不等于原生EDA阶段通过。

[实际worker入口准备](../R001/attempts/AT002_placed_CDC_recovery_cpu/actual_worker_entry_preflight.json)验证197个准备输入与future archive、独立旧closure112项；未发EDA。A007核其parent、stage manifest、archive三份身份均一致。生产无wall入口绑定用户补充的精确SHA，timeout与global deadline均null，无wall/no-output停止分支；单EDA锁、8CPU/nice5、RSS192GiB及内存/磁盘保护保留。新的实际worker manifest另外纳入持续执行授权身份，不把旧固定预算恢复为停止条件。

**实际启动：**[R002 AT002](../R002/attempts/AT002_closed_place_POST_physopt/started.json)于15:34:59.997055 UTC启动manager3866162、worker3866163；[实际EDA回执](../R002/attempts/AT002_closed_place_POST_physopt/actual_eda_started.json)记录15:35:29.081055 UTC launcher3866502。A007直接读取/proc确认原生Vivado3866592/start_ticks919108889、PG3866163、CPU0–7、nice5，日志已执行 `open_checkpoint` 指向原place DCP SHA `37591435…f7`。当前处于真实恢复，未预填新POST/physopt/route完成。此次独立核查及精确安装/准备/进程身份见 [A007最终证据](../../../../../agent/A007/report_20261015_E003_placed_recovery_final_review_evidence.json)。

execution：本轮A007有界审核completed，工程AT002仍running；verdict：两项发现已修复并获得对应验证，冻结分类、恢复及无wall入口无剩余已知实质缺陷；applicability：上述5项安装、50份冻结源、原closed place父点与实际AT002身份；review：结果已真实送达主控/A006。后继依真实阶段消息再作有界审核，不新增运行审批，也不声称A007持续后台监控。正式reset/CDC/重汇合/事务安全OPEN，placed时序FAIL及最终routed/板级验收尚未闭合。

### 5.5 新原生 place POST 闭合及独立 physopt 实际启动

AT002 [place_result.txt](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/place_result.txt)现为completed1、diagnostic_eligible1、blackboxes0、COMPLETE_INTERNAL，physical_signoff=false且reset/CDC review仍OPEN。[integrity_place.json](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/integrity_place.json)于2026-10-15 16:19:46.149861 UTC形成，gate_issues为空，当前结构与fanout均qualified，classified8/new_critical0。此为本次实际原生POST完成，不是此前CPU重放或旧报告重标。

A007有界核[阶段facts](../R002/attempts/AT002_closed_place_POST_physopt/completed_place_POST_facts.json)及[64文件POST manifest](../R002/attempts/AT002_closed_place_POST_physopt/completed_place_POST.sha256)：13份关键回执、其中56份小POST文件、14份实际primitive exports/2个模型及4份当前执行archive的尺寸/SHA均与冻结记录一致。只读取当前CDC的clock标签和8条Critical明细，6条CDC-10/2条CDC-11与新观察记录逐tuple一致，两个DDR1 AUX仍报base末级/C；实际分类同时保留canonical ready末级/C及同双源Q。新旧place的8个有界结构字段全等，当前constraints的hashes/metadata与父点一致。未重读已覆盖的大时序/拥塞表或大结构图；当前graph/fanout/CDC的精确身份由新integrity与POST manifest共同绑定。

新的原生POST序列化了 [place.dcp](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/place.dcp)，579812151 bytes、SHA256=`f2ba76edc720739c5562a110c3f82056007e6c5bcb9942a8f7c01a0b517648b9`。A007核当前尺寸、manifest身份、生成日志和fresh admission关联；25个ZIP成员CRC、稳定性及器件/top/board/tool包信息沿用工程[原检查点facts](../R002/attempts/AT002_closed_place_POST_physopt/new_place_POST_checkpoint_facts.json)，未重复读取大DCP。新文件是恢复同一成功布局后的重新序列化，不能将其hash/尺寸变化解释为又执行了一次place。来源仍为原579080094-byte、`37591435…f7`检查点；原AT001的integrity/status SHA、completed0结果及native0 place命令回执均保持，原place仅在historical scope。`recovery_parent.physical_post_complete=false`描述恢复准入时的旧POST状态，当前完成依据是本次新的result/integrity，而非改写该历史父记录。

[冻结日志](../R002/attempts/AT002_closed_place_POST_physopt/place_POST_and_physopt_start_log_snapshot.txt)第59行打开原place DCP、第144行生成新place DCP、第185行 `M002_DIAGNOSTIC_STEP_COMPLETED place`，紧接第186行真实 `Command: phys_opt_design`，第194行进入Physical Synthesis Initialization；没有重新执行place/OPT/debug。当前仍无新place命令回执，也尚无physopt结束回执。A007直接读取原生PID3866592/start_ticks919108889，PG3866163、CPU0–7/nice5连续；冻结前缀仍与运行日志一致。故可以确认独立physopt已实际启动，不能提前声称physopt成功、route已运行或整体implementation完成。

本次[独立核查证据](../../../../../agent/A007/report_20261016_E003_native_place_POST_physopt_start_review.json)已送达主控/A006。execution：本次有界审核completed、工程physopt running；verdict：新原生place POST的执行/来源/窄分类与继承边界闭合；applicability：AT002新POST manifest、新DCP及当前执行归档；review：审核已交付，无新增停点。正式reset/CDC安全OPEN，既有placed负时序与最终物理/板级验收边界不变，后续仅按实际阶段消息再审。

## 6. 独立 physopt 完成及正式阶段报告审核

### 6.1 原生完成、closed DCP 与正式时序变化

[physopt_command_result.txt](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/physopt_command_result.txt)记真实独立 `phys_opt_design` native0，16:19:46→16:38:12 UTC，1106秒。A007独核104-byte回执SHA=`d30357291522922db59dc9e5706ffd7e15645dd327fe2a637379e38cee9ce381`，与工程native/closed两份facts一致；原生日志第624行命令成功、第637行保存新DCP。新 [physopt.dcp](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/physopt.dcp)568389035 bytes、SHA=`c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91`；尺寸与[工程检查点事实](../R002/attempts/AT002_closed_place_POST_physopt/physopt_checkpoint_facts.json)相同，25成员CRC/稳定性与器件/top/board/tool包验证沿用工程证据，未再次读取大DCP。此刻physopt_result仍completed0/eligible0，完整POST尚未闭合；命令/DCP成功不等于route父资格完成。

[正式timing_physopt](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/timing_physopt.rpt)2392045 bytes、独立SHA=`b23c8eede37f4d7692807f76fbb16137fc308b87b3164fef72c3ef0c642dd237`，Design State为Physopt postPlace，仍采用estimated interconnect。与同AT002 fresh place比较：全局WNS−1.819→−1.290（+0.529ns），TNS−818.651→−762.165（改善56.486ns），setup失败1014→980；WHS−0.620、THS−2150.556及33141个hold失败均不变，PW/MaxSkew失败仍0。setup/hold端点总数各增加6、PW总数增加2，统计口径与当前优化后网表绑定；不把阶段改进当routed收敛。

| 时钟范围 | place→physopt setup WNS/TNS（ns），失败端点 | physopt hold WHS/THS（ns），失败端点 |
| --- | --- | --- |
| core100MHz | −0.317/−1.677，28 → 0.000/0，0 | −0.331/−1453.162，25144；不变 |
| DDR1 UI200MHz | −0.358/−0.982，4 → +0.089/0，0 | −0.350/−244.675，2449；不变 |
| DDR0 UI200MHz | +0.312/0，0 → 同值 | −0.164/−42.630，1775；不变 |
| PCIe GT clock→XDMA AXI | −1.819/−805.234，917 → −1.290/−751.939，917 | −0.173/−1.162，10；不变 |
| XDMA AXI→PCIe GT clock | −0.285/−2.403，31 → −0.285/−1.872，29 | −0.620/−114.871，297；不变 |
| XDMA AXI域内 | −0.588/−8.354，34 → −0.588/−8.364，35 | −0.142/−53.227，1863；不变 |

core的setup失败清零仅表明本阶段报告精度下未负，0.000ns没有可宣称的正裕量，且其hold尚未收敛。当前全局setup压力仍集中于PCIe→XDMA：917个失败端点未减少，其他部分并非全部单调改善（XDMA域内新增1个setup失败、TNS略差0.010ns）。各clock group统计不作机械相加以替代全局端点统计。

**具体最差路径及逻辑/估计布线组成：**新PCIe→XDMA最差setup（第6554行起）仍由PCIe硬核CORECLK发出，但目的从原RQ_FIFO `Head_reg[220]/CE`变为`Head_reg[205]/CE`。当前数据延迟4.577ns＝logic0.688+estimated route3.889（84.968%），1级LUT4，clock skew−0.219、Inter-SLR compensation0.387ns；原最差代表为5.070＝0.669+4.401、2级LUT、skew−0.261。两者端点不同，只能比较各阶段的最差代表，不能把分项差值解释为同一条路径的优化因果。

core最差setup也已换路径：原为MLP gate scheduler `source_block_r_reg[8]`→`u_meta_sched/error_reg/D`，30级逻辑、9.388ns数据＝2.111+7.277；当前为core base-reset同步末级→attention accumulator `upper_head_guard_s42_r_reg[36]/CE`，11级LUT、9.682ns＝0.568+9.114（estimated route占94.133%）、skew+0.060ns。原路径已不再是本域最差，新余量边界涉及复位/使能逻辑及互连；不能从这两个不同路径的级数下降直接归因或据此放宽reset/CDC安全。DDR1最差仍为arready→stall vector CE族，但目的位1131→1064：当前4.376ns＝0.167+4.209（96.184%）、两级LUT4，setup+0.089；该族的当前正裕量仍很小。

最差全局hold仍为XDMA `aa256_tdata_ff_reg[51]`→PCIe `SAXISCCTDATA[51]`，−0.620ns、data0.168＝0.060+0.108、skew+0.272；core最差hold仍是d0_smc upsizer FF→FIFO BRAM写入，−0.331ns；DDR1 Laguna ready hold仍−0.350ns。上述未改善事实保留，不能以setup清零称core或DDR1整体时序通过。

正式utilization显示LUT814935（较place+24）、FF1019698（+2）；CLB占用146472/99.11%、BRAM941、URAM752、DSP5451不变。小幅净网表变化没有证明局部拥塞已缓解；正式congestion、SLR crossing/top32路径及优化后实际CDC/结构按后续实际产物再审，不以place图代替physopt图。

本节精确回执、同AT002时序表与八条有界最差路径头见[A007阶段证据](../../../../../agent/A007/report_20261016_E003_physopt_timing_review_evidence.json)。execution：独立physopt native completed，完整POST仍running；verdict：setup改善但整体时序FAIL、hold未改善；applicability：当前closed physopt DCP与正式estimated timing；review：已实发主控/A006，后继报告尚待实际生成，流水线无新增停点。
### 6.2 当前物理报告、脉宽／bus-skew 与 top32 路径

A007对新 [工程物理facts](../R002/attempts/AT002_closed_place_POST_physopt/physopt_physical_reports_facts.json)所列SLR utilization、congestion、SLR crossing逐份核size/SHA一致；PW、bus-skew及32条setup/hold报告身份、选定表格和路径头另存 [当前有界证据](../../../../../agent/A007/report_20261016_E003_physopt_physical_review_evidence.json)。当前报告均绑定AT002及Vivado2025.2/build6299465/指定top与器件，详细路径仍为estimated interconnect。

[congestion_physopt.rpt](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/congestion_physopt.rpt)共有48行，即4方向×3类型×Level3–6；全部12组合最高Level6。与同AT fresh place的48行比较，窗口、局部资源占用与层次贡献字段全等。必须保留原报告范围：其标题为 **Placer Final Level Congestion Reporting**、Design State为Fully Placed；这是新POST重报的placer-final表，未证明优化后重新估算的拥塞改善或恶化，更不是routed拥塞。窗口有重叠/嵌套，不能计作48个独立失败区域；坐标本身不足以指定SLR。既有MLP/DDR局部压力风险仍待实际route结果辨别。

[SLR utilization](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/utilization_slr_physopt.rpt)显示SLR2↔1为9471/17280（54.81%，place9451），SLR1↔0为8811/17280（50.99%，place8812），Total SLLs18282、净增19。SLR0/1/2已占CLB仍49193/48810/48469，即99.86/99.09/98.39%；LUT为300082/268405/246448、FF为349674/319883/350141。总SLL尚有余量与局部布线/CLB压力可以同时成立，不能由前者排除后者。

[SLR crossing](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/slr_crossing_physopt.rpt)的fanout表为32项；前阶段10个skipped-BUFG候选中的4个精确交集仍为down payload8201、down error6192、gate payload6145、gate input_fire4652，类型、driver SLR0与SLR0+1负载分布全部不变（完整层次名见证据）。这是持续存在的控制/广播局部性候选，不能定为唯一瓶颈。SLR逻辑级数时序表仍header-only，不能解释为没有跨SLR路径。

[setup top32](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/paths_setup_physopt.rpt)全部由PCIe硬核CORECLK到XDMA RQ_FIFO Head寄存器：30个CE、2个D，slack−1.290至−1.245ns；30条1级、2条2级LUT。数据延迟4.511–4.648ns，其中logic0.636–0.688、estimated route3.823–3.979ns（84.748–85.988%）；32条数据段均跨SLR1→2。29条最大数据net均为同一RQ_FIFO `m_axis_rq.tready`，fanout22、estimated增量3.396ns。这支持该PCIe→XDMA跨SLR控制族为当前setup尾部主要压力；数字仅涵盖top32，不能替代完整917个失败端点或据此直接改IP/约束。路径内另有clock crossing标记，统计时已与数据段区分。

[hold top32](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/paths_hold_physopt.rpt)全部XDMA→PCIe：31条CC数据、1条CQ ready；slack−0.620至−0.534ns、全部0级逻辑，数据延迟0.160–0.291＝logic0.058–0.061加estimated route0.100–0.230ns，数据段均无SLR crossing。它们表明hold短路径问题与上述setup跨SLR族不同，未形成时序收敛结论。

[pulse_width](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/pulse_width_physopt.rpt)为15行header-only、无all_violators条目。[bus_skew](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/bus_skew_physopt.rpt)独立解析summary94项，负slack0，最小+3.015ns（requirement4.000、actual0.985，line217），与place最小值相同。没有重读其长From/To表达式或将这些局部通过扩大为全局时序通过。

execution：本节物理报告审核完成，完整physopt POST/实际reset结构资格仍待工程产物；verdict：当前setup尾部由PCIe→XDMA跨SLR估计互连主导，hold仍失败，placer-final局部压力未取得新的route证据；applicability：上述精确本阶段报告，非routed签核；review：已真实通知主控/A006，工程按无wall政策继续，无新增停点，正式reset/CDC安全OPEN。

### 6.3 实际优化后结构、完整 POST 与成功父链：本轮审核交付

[完整physopt POST facts](../R002/attempts/AT002_closed_place_POST_physopt/completed_physopt_POST_facts.json)绑定 [55文件manifest](../R002/attempts/AT002_closed_place_POST_physopt/completed_physopt_POST.sha256)。[integrity_physopt.json](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/integrity_physopt.json)形成于2026-10-15 17:15:29.964475 UTC，gate_issues为空；[physopt_result](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/physopt_result.txt)为completed1、diagnostic_eligible1、blackboxes0、COMPLETE_INTERNAL，physical_signoff=false、reset_io/cdc review仍OPEN。原生冻结日志第674行出现 `M002_DIAGNOSTIC_STEP_COMPLETED physopt`。因此§6.1–6.2所记完整POST待续已由当前证据闭合。

本轮实际reset graph为119919564 bytes、SHA=`ca3d0c717f251619a2fa4b24217509ecbb77050e2528a2b67d4dcddc71bcd567`；当前结构qualified且issues空，并与integrity嵌入对象完全相同。A007有界对比新physopt与fresh place的9字段：4条AUX链、7条async链、3条HostSplit链、gate/reported起点、launch C→Q、DDR输出、critical目标及PCIe接收端均完全相同。14份当前primitive exports和4份FDCE/FDRE/BRAM模型逐size/SHA通过，14 scope的effective参数与place全等；未因文件存在就推定结构，也未重读约120MB大图。当前图来源身份由实际运行资格、integrity和POST manifest共同绑定。

当前fanout source5985273 bytes及BRAM clock source263752 bytes已独立核hash；qualified、issues空、XDMA UI两域5+6个接收端、688个BRAM时钟端点、aux coverage及消费者统计均与place相同。当前constraints的metadata/hashes亦全等。原生CDC报告只抽取clock标签与Critical明细：实际恰8条、6条CDC-10/2条CDC-11，逐tuple等于本阶段工程观察及fresh place；两个DDR1 AUX代表仍为base末级/C，实际双源Q与canonical ready末级/C分别保留。classified8/new_critical0支持当前诊断延续，不能关闭异步复位、重汇合或事务安全。

**来源核查范围：**完整POST facts中7份小身份均通过；55项manifest中47份小文件实际重新hash通过，6份大项复用此前A007独立hash或当前资格/工程DCP CRC绑定，另外control_sets与DRC大报告沿用工程manifest身份而未重扫。未将这55项描述为全部独立重新读取。各层核查方式、精确身份、9字段/14参数比较、CDC原行号和fanout事实见 [A007当前POST审核证据](../../../../../agent/A007/report_20261016_E003_physopt_POST_CDC_review_evidence.json)。

[终态facts](../R002/attempts/AT002_closed_place_POST_physopt/terminal_facts.json)与实际status/launcher显示本stage于17:16:53.390716 UTC自然结束，native/worker/supervisor均0、stop_reason=null、owned_survivors空。A007核5份终态小身份并直接检查13个原PID/start_ticks均已不存在，未重扫资源日志。[diagnostic_evidence](../../../../hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/diagnostic_evidence.json)为execution completed、diagnostic_eligible=true；新command_receipts仅physopt，OPT/debug/place明确留在historical scope，`new_place_POST_physopt__inherited_opt_debug_place`与当前新place POST/integrity/closed physopt DCP精确相连。A007另外核10份父点、准入、stage input/archive与约束等小来源身份均一致，内部缺时钟/未约束端点仍0。外部已分类reset IO与正式时序FAIL没有被改写。

工程实际父链验证已通过并自动派发[R003 AT001](../R003/attempts/AT001_full_route/started.json)；A007读取其no-wall/no-deadline、CPU0–7/nice5及[17:18:03 UTC EDA启动回执](../R003/attempts/AT001_full_route/actual_eda_started.json)。这证明后继route阶段进入实际恢复/执行入口，不提前宣称 `route_design` 已完成或获得最终route_status。

execution：A007本轮独立physopt时序、物理、实际CDC/POST及成功父链审核completed，工程后继route继续；verdict：本阶段完整执行与诊断准入成立，整体时序仍FAIL，正式reset/CDC安全OPEN；applicability：§6的当前AT002精确DCP/报告/结构/来源及真实终态；review：已通过实际消息交付主控/A006，无新增审核停点。本轮完成不代表SM007全局完成或A007后台持续监控，下一有意义route阶段由主控实发后再作有界审核。

## 7. 实际 route 启动与恢复检查边界

### 7.1 真实父点、运行身份与实际检查范围

R003/AT001 [启动记录](../R003/attempts/AT001_full_route/started.json)为17:17:27.705894 UTC，实际EDA launcher于17:18:03.079268 UTC启动。A007独立读取manager3964207、worker3964212、launcher3964561及native Vivado3964652的/proc；native start_ticks919724289、PG3964212、CPU0–7/nice5均与工程启动事实相符，CPU累计随阶段推进增长。实际no-wall入口的timeout/global_deadline均null、wall_clock_stop_disabled=true；冻结监督循环仅保留RSS192GiB、MemAvailable48GiB持续30秒和磁盘30GiB保护，没有固定wall或无输出超时分支。当前授权SHA仍为`17acf924…8363`，未恢复旧12/24小时限额。

[原生启动日志快照](../../../../../agent/A007/route_start_native_log_snapshot_20261016.txt)第59行打开R002/AT002的closed physopt DCP；第80行从binary archive恢复constraints，第121行open_checkpoint完成、elapsed9分11秒；第122行真实 `Command: route_design`，第127行Starting Routing Task，第128行最大8 CPUs，第130行Phase1 Build RT Design。这比“route进程已启动”更进一步，实际路由命令已经运行，但没有route完成回执、最终DCP/route_status。

A007逐项核当前16份stage archive与实际执行源码/生成probe的SHA一致；35项stage input中31份小文件独立hash通过，当前physopt DCP/CDC复用§6已核身份，另2份旧综合/OPT CDC保持历史来源不重扫。新command的synthesis与父diagnostic精确相同，XPR effective_build_identity亦等于339输入/45检查点的原综合身份。stage inputs实际绑定父`diagnostic_evidence.json` SHA=`66e3565a…12dc`、physopt DCP SHA=`c6944eee…ff91`和当前CDC SHA=`08b48827…7261`。冻结worker先经`parent_recovered_place`核成功launcher/supervisor、无survivor、new physopt与historical command作用域、新place POST、physopt完整integrity/结构/CDC和输入/约束身份，才设置当前恢复DCP并发EDA；未将原AT001失败或原XPR impl_1状态改为成功。

**本次确实有fresh对象检查，但范围必须精确。** `m002_resume_physical.tcl`第46–128行是place/route共用preflight，因本次命令使用`-notrace`，这些查询没有逐条显示在open_checkpoint与route_design之间。实际 [restored_preflight.tsv](../../../../hardware/vivado/reports/m002_E003_R003_AT001_full_route/restored_preflight.tsv)有器件/top/BD root、6个原综合canonical CDC目标唯一命中、3个reset端口方向、3个clock family及40条period、blackbox_count0、7条async与4条AUX各4级、DDR0/1 XPM各2、head-local计数4/2/1，最后PREFLIGHT_ISSUES为空。实际恢复project的IP cache由read write设为disable，threads=8；embedded constraints来自已识别DCP。

应区分实际观测与Tcl断言：器件/top/root、6目标、端口、各时钟根周期与存在目标generated周期、7+4条四级计数、XPM非空和cache禁用有检查；blackbox计数与head-local数量在此共用preflight只记录，本次实际分别为0及4/2/1。XPM条件是非空，并非强制2；四级数量不证明链连接、极性、ASYNC_REG或HostSplit链。三时钟族逐族检查不含cross-family断言，A007独立对本次3族集合比较无交集；不扩大为完整内部clock coverage。6个canonical目标不等于当前8条critical目标，后两条XDMA→DDR CLR的完整限定资格来自父physopt POST。`debug_proof_restore.txt`的verified0也不是新debug失败：该predicate只在恰一个已知dbg_hub黑盒且关联两DDR时为1，本次blackbox_count0时不适用其“单已知黑盒”断言。

**本次未重跑place专用完整live guard。** route分支第168–170行直接调用route_design并在完成后做route POST，未调用`m002_live_pre_place_restore`，当前不存在其新check_timing/report_drc/clock-groups guard及route实际reset图。完整physopt DRC、内部时钟覆盖、约束、reset/CDC图与fanout资格继承自§6已闭合且精确绑定的父点；最终route POST尚待真实执行。当前合同“恢复后live sanity、时钟/约束及原生DRC，再完整place”描述恢复到place的流程，route要求成功physopt父链/完整POST及来源；本次按这一范围具备诊断route依据，不新增逐阶段重跑完整guard的合同要求，也不声称本次已运行该guard。正式安全仍OPEN。

具体身份、源码断言行、实际preflight行、进程快照及来源核查方法见 [A007 route启动有界证据](../../../../../agent/A007/report_20261016_E003_route_start_bounded_review_evidence.json)。本段未改生产实现、未运行EDA/测试、未控制进程；工程正常route继续，无新增审核停点。

### 7.2 路由中的局部引脚压力观察

截至17:32:48.845443 UTC的[独立日志快照](../../../../../agent/A007/route_local_pin_warning_log_snapshot_20261016.txt)，第149行原生`Route 35-445`报告 **at least 97 CLBs**存在high pin utilization、可能影响运行时间和时序收敛；报告给出的连续范围为 `(188 325)→(188 329)`，对应 `CLEL_R_X30Y586→CLEL_R_X30Y582`。这是本次实际route过程的局部引脚压力观察，与§6.2复述的placer-final窗口表范围不同；不能把97当作完整最终失败CLB数，也不能从所列坐标单独给出架构归因或不可布结论。

同一快照已进入Phase2.4 Update Timing，Phase2.3的`Number of Nodes with overlaps = 0`只属于该阶段，不能替代最终全网route_status。此普通信息未阻塞流程；继续等待route原生命令、DCP、完整POST、正式时序/DRC与全部可布网络统计，不扩大诊断范围或人为停止。

### 7.3 本段交付

工程补充[route_native_started_facts](../R003/attempts/AT001_full_route/route_native_started_facts.json)及[route_restore_scope](../R003/attempts/AT001_full_route/route_restore_scope.json)与上述独立结论一致；A007对其中15份小身份逐size/SHA核对均通过（包括412KB debug观测文件，仅核身份，不重扫其内容）。精确native route起始epoch要等命令结束回执，本段仅报告已经观测到命令开始，不以launcher时间冒充route_design时间。

execution：本段有界启动/来源/恢复范围审核completed，工程route仍running；verdict：真实成功父链、实际共用preflight与no-wall身份支持本次既有授权诊断路由，无新增实质阻碍；当前97 CLB局部引脚压力待最终结果；applicability：本段精确源码/父DCP/实际preflight与17:32日志快照；review：已实发主控/A006，不新增停点。完整route、时序、DRC和route_status未预填通过，正式reset/CDC安全OPEN；后继有意义里程碑按主控实际消息再作有界审核，不声称后台监控。

### 7.4 全局路由初期 Estimated SLL Demand 风险

本段核[工程阶段facts](../R003/attempts/AT001_full_route/route_SLL_demand_facts.json)7551 bytes、SHA=`4992e1d5fe704d4fc1e8806bbd211b22e992a73df962b8a929ed8962cef4f1db`，以及[原生日志快照](../R003/attempts/AT001_full_route/route_SLL_demand_log_snapshot.txt)20539 bytes、SHA=`69308b18f98093398d43f32396608992cbc5bff783646ea149ca51910c67892c`。A007独立从原始四行解析全部12列、复算列和/容量/百分比并逐项与工程facts核对，均一致；证据见 [A007 SLL需求风险审核](../../../../../agent/A007/report_20261016_E003_route_SLL_demand_risk_review_evidence.json)。

**准确阶段与口径：**日志第210行进入Phase3 Global Routing，第211–215行为`Number SLLs per Column: 1440`、`Estimated SLL Demand Per Column`及Route35-3311；第217行Phase3.1 SLL Assignment再次打印相同两行估计及同一告警。12列×1440=每边界17280；四个原行是两边界的同表重印，不能计作两次独立运行或两次失败。该估计对应全局路由初期/SLL assignment，不是最终已分配SLL利用率。

| 相邻SLR边界 | 当前估计总需求 / 表内可用 | 总估计利用率 | 超1440需求的列数 | 最大列需求 / 1440 |
| --- | --- | --- | --- | --- |
| 1–2 | 14482 / 17280 | 83.81% | 4 / 12 | 2044 / 1440 = 141.944%（原表142%） |
| 0–1 | 21886 / 17280 | 126.66% | 9 / 12 | 2997 / 1440 = 208.125%（原表208%） |

SLR0–1在当前估算下总需求高于表内容量4606，同时存在广泛的列超额，属于显著布线可行性风险；SLR1–2总量低于边界容量2798，但局部4列仍超额，不能以总量83.81%排除局部拥塞。原表没有给出列序到物理列坐标的映射，不能用打印顺序擅自指定X列或归因到某一RTL/net集合。

**与此前统计的区别：**placed `report_utilization/report_slr_crossing` 的SLL Used为SLR1–2 9451/54.69%、SLR0–1 8812/51.00%；独立physopt后为9471/54.81%及8811/50.99%。这与当前router的Estimated SLL Demand是不同阶段、不同报告分子，即使都使用17280作边界容量，也不能把其差值当成已新增的实际SLL占用，或由此前总量余度反驳当前局部需求告警。原生日志没有展开需求估算内部算法，本段不虚构其是否重复计数、复制或绕行的具体机制。它也不同于§6.2重叠的placer-final Level6窗口、以及§7.2的至少97 CLB高pin利用率；三者均可提示压力，但不可合并为同一种“失败数”。

紧邻表之前的Phase2 Router Initialization第200–204行显示Failed Nets2032246＝Unrouted1822647＋Partially Routed209599、Node Overlaps0。这是在全局路由之前的进度统计，不能当最终失败网络数或最终全布通证据。Phase3.1随后正常结束，当前已继续到Phase3.2/3.2.1 Build GR Node Graph。工程17:42:10–12 UTC快照绑定原native PID/start身份连续及资源仍处正常范围；本段沿用该资源采样，不重复进程或资源日志扫描。

工具原话为“Router **might not** be able to find a suitable solution”，并建议SSI placer directives或减少局部SLL压力的location constraints。这是诊断建议，未构成当前设计不可布通的证明，也没有授权本轮热改策略/LOC；当前一次默认路线、设计/接口/约束身份保持，正常route无停点。最终判断仍需真实route命令返回、closed DCP/完整POST、fully routed/unrouted/partially routed/routing errors与正式时序/DRC。

execution：本段有界风险审核completed、工程route running；verdict：当前估计揭示SLR0–1总量及局部、SLR1–2局部的显著SLL需求压力，最终可布性尚未判定；applicability：上述Phase3/3.1原生估计与已审placed/physopt统计，非最终资源分配；review：已实发主控/A006，无新增停点。正式reset/CDC安全OPEN，未运行EDA/测试、未改生产或控制进程。

### 7.5 GR 清零、完成优先与 Initial Estimated Level7 拥塞

本段对应[GR至Initial进展](../R003/attempts/AT001_full_route/route_global_to_initial_facts.json)、[Route35-447完成优先](../R003/attempts/AT001_full_route/route_completion_priority_facts.json)、[Initial Estimated Level7](../R003/attempts/AT001_full_route/route_level7_estimated_congestion_facts.json)。A007逐size/SHA核三facts关联的8份小身份，所列原行号/文字全部与各自快照一致；前两份日志字节均是后一份29392-byte快照的完整前缀，确认同一实际route阶段连续记录。后者SHA=`c8697f29a88a16da4e77623a36e1200b72f67f7c69a9ca0c7e9f49cabd843f04`。独立提取、窗口计算及限定见 [A007本段证据](../../../../../agent/A007/report_20261016_E003_route_initial_congestion_review_evidence.json)。

**三个指标可以同时成立。** Phase3.2.2 Run Global Routing第236–241行在Global Iteration0中报告Total GR Congestion7076→0，Iteration1也为0，随后Phase3完整结束。这里只证明该global阶段标量清零；日志没有把它定义为最终逐net布通或所有局部拥塞清零。进入Phase4后，4.1 Initial Net Routing Pass与4.2 Update Timing均结束，第263行Route35-447明确报告拥塞正在阻碍所有nets完成，并声明router将优先成功完成所有nets、其次进行时序优化；随后继续执行4.3–4.10的四组Initial Net Routing/Update Timing，加上4.1–4.2共五组，Phase4于第304行结束。这是冻结默认route命令内部的处理优先级，未发生用户策略/seed/LOC/XDC修改，也不表示时钟目标被放宽、所有时序优化关闭或最终时序已变差。

Phase4结束后第308行标题为 **Initial Estimated Congestion**；第399行35-448报告Estimated Global/Short level7（128×128），第401行35-581另报Estimated Timing level7（128×128）。它们是当前router初始布线后的估计，不是最终route_status或routed签核。明细表实际范围如下；百分比仅保留原列名`% Tiles`，本段不擅自赋予其全器件分母、相加或换算独立失败面积：

| 方向 | Global Size / % Tiles | Long Size / % Tiles | Short Size / % Tiles |
| --- | --- | --- | --- |
| NORTH | 128×128 / 10.12 | 128×128 / 23.59 | 16×16 / 3.99 |
| SOUTH | 128×128 / 14.60 | 128×128 / 33.84 | 32×32 / 3.42 |
| EAST | 64×64 / 5.89 | 64×64 / 9.84 | 32×32 / 8.04 |
| WEST | 64×64 / 7.68 | 64×64 / 12.41 | 64×64 / 9.06 |

因此整体Global/Short Level7并不表示每一Short方向都是128×128；本表Short最大仅WEST64×64。Timing Level7是独立消息，此截取没有对应的单列Timing窗口表，不能将Long窗口直接改称Timing窗口。

**可以支持的具体重叠：**在当前同一INT坐标口径下，Global NORTH首框`INT_X32Y131→INT_X95Y290`（line325）、EAST首框`INT_X32Y235→INT_X95Y298`（line337）、WEST首框`INT_X32Y228→INT_X95Y291`（line343）的公共矩形为 **X32–95、Y235–290**。另一处SOUTH Global首框`INT_X6Y726→INT_X69Y853`（line331）完整位于SOUTH Long首框`INT_X0Y643→INT_X95Y866`（line356）内。由此可确认不同方向/类型的报告包络重叠或包含，不能将表中60条坐标框视作60个独立失败区，也不能推定其中每一个tile、同一net或同一RTL都拥塞。坐标没有附本轮可核SLR映射，亦不据此建立SLL0–1、97个CLB高pin或某模块的因果关系。

**风险如何更新：**先前为placer-final Level6、SLL初期需求超额及高pin警示；当前新增的是route内部明确“拥塞阻碍当前全布通”及其完成优先行为，并在Initial Routing后仍有高等级估计。这支持“全局阶段GR标量清零后，实际后续局部布线和时序仍有实质压力”，不能支持“问题已经解决”或“最终必然失败”。placer-final Level6与本次Initial Estimated Level7来自不同阶段/查询，不把数字之差写成同口径受控实验恶化一级；未取得新的SLL实际分配或最终计数，不能宣称旧需求告警已解决或一定是当前Level7根因。

execution：本段有界进展/风险审核completed，工程同一native route仍running；verdict：Phase3/4进展真实，当前局部布线与时序风险持续，最终布通与时序均待证据；applicability：上述相同原生日志的阶段指标和当前INT包络，非最终全网/根因证明；review：已实发主控/A006，无停点或策略热改。保持正常no-wall执行，后继仅依据真实命令、closed DCP/POST、最终route_status、DRC与正式时序评判，正式reset/CDC安全OPEN。

### 7.6 Phase5.2 中间时序与 overlap 进展的窄审核

[本次facts](../R003/attempts/AT001_full_route/route_iteration1_intermediate_timing_facts.json)2294 bytes、SHA=`fa85086da67a5ff5ac5819a34481e1751a4d149ed2afd2640242c5cc02b755ef`，绑定30126-byte[冻结日志](../R003/attempts/AT001_full_route/route_iteration1_intermediate_timing_log_snapshot.txt)、SHA=`810a9ef6790581e29e5dc4195353b8ca221158845ceea30d0d05247e21b6a91e`。A007独核本日志、prior overlap facts及prior日志3项身份通过，prior日志是本日志完整前缀，facts内三条中间时序原行均匹配。第403行是Phase5 Rip-up And Reroute，第415行Phase5.2 Global Iteration1；第416–418行Number of Nodes with overlaps依次1861520→988355→501530，第419行明确 **Intermediate Timing Summary：WNS−17.994ns、TNS−2261923.747ns、WHS=N/A、THS=N/A**。

节点指标从首值累计减少1359990（73.058%），较前次减少486825（49.256%），支持同一迭代中的实际进展；最后观测501530仍非零。这不是已完成路由百分比，也不是剩余未布网络数。中间负setup显示当前显著时序压力，可以与overlap下降同时存在；hold N/A只表示该条没有可用hold结论，不能填0或PASS。该行没有端点统计、路径或时钟域明细，不能据此归因core/DDR/SLL、推出失败端点数/频率/延迟，或与§6正式physopt结果相减写成同口径因果退化。

[独立窄审核证据](../../../../../agent/A007/report_20261016_E003_route_intermediate_timing_review_evidence.json)保留原行、独立复算及范围。execution：本段审核completed，工程同一native3964652仍running；verdict：重叠节点指标继续改善但当前中间setup风险严重，最终布通/时序尚不可判；applicability：21:10:59 UTC工程冻结观察，非正式最终timing、route_status、DCP或完整POST；review：已实发主控，正常no-wall route继续，无新增停点或策略更改。本段不读大图/DCP、不跑EDA/测试、不改生产、不控制进程，正式reset/CDC安全OPEN。

## 8. 原生 route 合法性失败及本轮最终审核

### 8.1 已确认验证失败，命令自然终态仍待取得

[失败阶段facts](../R003/attempts/AT001_full_route/route_native_verification_failure_facts.json)3037 bytes、SHA=`beea280bcb93b56ba0fb75513d469d4dea3f3a1e4058da9c6f7b29d16fe47810`绑定[49915-byte原生日志快照](../R003/attempts/AT001_full_route/route_native_verification_failure_log_snapshot.txt)、SHA=`580911f155c1dc6eaef51739d8a02ccd5db81dce8ea01b92560c072cbaf09283`。A007独核该快照和前Phase5 facts身份、所有引用原行均通过。第536行进入Phase9 Verifying routed nets，第537行Route35-162明确 **248289 signals因routing congestion失败**；第636行Verification failed，第640行ERROR Route35-2明确 **Design is not legally routed，245279 node overlaps**。这已是当前实际尝试的合法性失败证据，不再只是此前估计风险，也不证明所有布局策略或整个架构都不可能布通。

Phase8第477–481行同时有Failed Nets0、Unrouted0、Partially Routed0和Node Overlaps245279；原日志把Failed定义为unrouted＋partially routed且排除driverless/loadless nets。它未覆盖资源互斥/重叠合法性，故不能以这三个0称合法全布通，亦不能据此否定Phase9失败。248289 signals与245279 nodes是不同计数，不能互换或把二者当独立失败集合相加；该段没有routable/fully-routed总量，不拼成完整report_route_status。Phase6/7 Delay/Skew/Post Hold Fix内部阶段结束也不表示hold或正式时序通过。

第643行Phase10 Depositing Routes仍在推进；截至本段观察，route_command_result、launcher/status、route DCP、route_status、integrity和最终diagnostic证据均尚未出现。等待命令自然结束及A006实际冻结产物，不提前填退出码、停止原因或可用失败DCP。当前不会自动开启新物理尝试。

### 8.2 finalize 拥塞统计与此前容量/估计的区别

Phase8 GLOBAL Congestion明确使用utilization threshold **0.85**。四方向均为64×64区域，Max Cong依N/S/E/W分别 **85.471%、86.437%、86.551%、87.3848%**；20个原始INT坐标框全部落在X20–91、Y202–299的包络范围。随后hotspot文字为clusters found at Level5、effective congestion level6；North aspect ratio0.666667/sparse ratio1.25，其余三方向均1/1。这是本次finalize阶段统计，不因effective6小于前Initial Estimated7就推定问题解决；其紧后的合法性验证实际失败。

同段Global Vertical Routing Utilization50.5855%、Horizontal49.857%是路由资源的聚合数，不是placed CLB站点99.11%、各SLR CLB接近满载或早期SLL per-column demand。二方向百分比不能相加为“资源用满”，全局约50%也不能排除局部压力。§7.4 SLL0–1估计126.66%、§7.5 Initial Level7和§7.6中间WNS/TNS仅保留各自阶段的证据含义，未获得全量关系或受控实验，不将它们直接定为最终失败的唯一因果链。

### 8.3 十个冲突节点样例的有限线索

日志明确只列 **top10 physical nodes**，每节点最多给5个竞争signals。本次10条各报告3个overlapping nets，共30次打印、27个唯一net名字，全部位于Attention层次；涉及输入/输出buffer、projection lane/accumulator、context/postprocess store等。节点类型为3个PINBOUNCE、1个VSINGLE、2个HDOUBLE、2个HSINGLE、2个LONG_LOCAL，真实INT坐标范围X18–99、Y735–858。这支持Attention相关局部连接是后续诊断线索；样本经过工具选择且含重复net，不能外推245279全部节点或248289全部signals的模块占比、唯一根因或算法正确性。

同一INT坐标下，这10个示例均不在§8.2列出的20个finalize GLOBAL热点框内。这里只能说明“方向/Global区域热点框”与“top10冲突节点”是不同的有限选择，不能证明Attention区域没有局部拥塞或全局热点表错误，也不擅自给坐标赋SLR。详尽原样本、去重计数、矩形包含检查和事实边界见 [A007最终阶段证据](../../../../../agent/A007/report_20261016_E003_route_native_failure_review_evidence.json)。

execution：本轮原生验证已失败，route命令/监督自然收尾仍待实际终态，A007审核running；verdict：本次当前策略未取得合法布线路由，正式时序/安全签核没有成立；applicability：已冻结同一source/DCP/tool/默认route尝试和上述有限日志证据；review：已实发主控/A006，等实际回执/报告可得性后完成终态审核。不运行EDA、不读大DCP/图、不改RTL或策略，正式reset/CDC安全OPEN。

### 8.4 自然失败终态、产物缺口与最终结论

[终态facts](../R003/attempts/AT001_full_route/terminal_facts.json)为2745 bytes、SHA=`5cfb58e3907df821aa51f093dfbdae4c4ba9882d3d645663a7f8f701cec88c6e`；[完整终态及可得性facts](../R003/attempts/AT001_full_route/route_terminal_completion_facts.json)为12456 bytes、SHA=`cd0b00471cbf85c06b2e1f389e92148a1a097425ca175724b1a2931844a31956`。A007独核后者12项小文件身份及13条原日志行全部匹配；早先§8.1的49915-byte失败快照是最终51877-byte `vivado.log`/`implementation_run.log`的完整前缀。两份最终日志SHA均为`3f1d9c65cfb6b2769ad3d7317bb1f328c3a08e10b886b927c8cd170c960b51c4`。新增独立证据见[A007终态审核](../../../../../agent/A007/report_20261016_E003_route_terminal_review_evidence.json)，不覆盖此前运行中观察。

**真实时间与退出层次：**`route_command_result.txt`记录实际`route_design`从2026-10-15 17:27:55到22:45:40 UTC，19065秒（5小时17分45秒），`native_tcl_code=1`；与最终日志line676的elapsed一致。内部route task另报18814.9秒，不能拿它替代整个命令耗时，命令中包含失败后工具自动DRC。stage从17:17:27.705894到22:45:51.707572 UTC，19704.001678秒，包含恢复/启动等开销；launcher native/worker均1，chain记录manager/driver1并在22:45:51.717252结束。监督JSON的`execution_state=completed`只表示监督已结束，其`exit_code=1`和chain `failed`清楚表明本次实验失败，不能将completed单字段读成路由成功。

**自然结束及资源：**监督`stop_reason=null`、`owned_survivors=[]`，no-wall政策保留。A007实际读取`/proc`，原native3964652/start919724289、launcher3964561/919724273及3964580/919724277、worker3964212/919720736、manager3964207/919720731和driver3866160/919105949这6个原身份全部不存在。工程已取得真实session exit1及单EDA锁非阻塞独占后立即释放回执；A007没有操作该锁或控制进程。[主控独立资源核验](../../../../../results/reviews/SM007_route_terminal_check_20261016.json)已复算3882样本，与终态facts完全一致：峰值进程树RSS27882639360 bytes（25.968GiB），最低可用内存432796045312 bytes（403.073GiB），最低磁盘余量487714902016 bytes（454.220GiB）。A007复用该已核原始采样结果，并独核终态小文件绑定；没有重复读取资源日志。这支持原生工具自然失败，没有时间或资源保护终止。

**失败后自动DRC不构成反证：**最终日志line661–667显示Phase11后router仍报告errors；line669明确“Running DRC after route_design as it did not complete successfully”，line671是该工具内部跟随DRC的0 Errors。紧接line675/677仍为`route_design failed`/Common17-39。这一DRC0不能覆盖Phase9的245279 node overlaps，亦不是完整`drc_route.rpt`或正式物理签核。

**POST实际未执行，不能补造最终指标：**A007核对3份冻结controller/archive与安装源及manifest身份相同。`m002_resume_physical.tcl`第129–134行把route Tcl非零原样抛出，因此第169行命令失败后不执行第170行`m002_post route`；Python也在native非零检查时先失败，未到finalize，`evidence_error.txt`仅确认`native physical controller exited 1`。独立检查facts列明的13项当前POST产物均缺失，包括route DCP、route_status、timing、DRC、check_timing、clocks、CDC/reset graph、integrity、admission/route_result、最终diagnostic和checkpoint manifest。对本AT、report、Vivado工作根、当前impl_1及native_run_receipts五个已知位置的直接DCP文件检查也均无本次失败checkpoint；不声称对全盘作过穷尽搜索。最后可用的完整物理父点仍是§6已核的成功physopt DCP/POST，不能从已退出进程恢复其未保存的route内存状态。

因此，Phase8的unrouted/partial0和Phase9的245279 nodes/248289 signals各按原生口径保留；没有完整`report_route_status`，不能填最终全网总量或布通率。最新可得route时序仍只是§7.6中间WNS−17.994/TNS−2261923.747ns、hold N/A；没有正式routed时序/端点/路径报告，不拿它代替签核，也不与正式physopt指标作同口径归因。此前place和独立physopt成功及完整证据仍成立，route自然失败不追溯抹去这些已完成阶段。

**最终范围结论：**本轮一次冻结默认物理尝试已实际推进至route并自然失败；该尝试没有合法布线结果，未达到合同所需的成功route、最终DCP/完整POST，完整implementation成功验收未达成。此前CLB站点密度、SLL估计需求和拥塞/Attention有限冲突样例仍是后续诊断线索；单次失败不足以证明所有策略或架构不可布，更不能反驳Hadamard/ScaleCode/format05算法。没有自动重跑、新策略、RTL/XDC/时钟改动或bitstream/板卡执行。

execution：工程本次实验FAILED，A007最终只读审核completed；verdict：当前冻结尝试routing legality FAIL、完整物理成功未达成，架构普遍可布性仍inconclusive；applicability：本次已核source/tool/父DCP/默认策略和原生终态，不外推未试配置；review：独立审核已交付主控/A006，用户全局验收未代替。正式reset/CDC/事务安全继续OPEN，后续实验由主控结合现有授权另行界定，本轮不自动开启新物理尝试。
