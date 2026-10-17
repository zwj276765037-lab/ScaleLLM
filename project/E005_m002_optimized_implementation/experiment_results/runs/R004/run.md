# R004 — E005 新布局、独立physopt与完整route

Execution state: failed
Verdict: legal routing FAIL; diagnostic timing setup/hold/PW FAIL

本批已于2026-10-16T13:56:35.660913Z自然失败闭合。AT003完整place/physopt POST及父链已通过；AT004一次完整Default route在Phase9确认不合法布通：1,148,579个重叠节点、758,463个因拥塞未布通信号。五项失败现场保存全部原生code0，随后重抛原route错误，Tcl/Vivado/worker/监督均1，stop_reason=null，无时间或资源强停。144生产输入未变，原6个PID/start身份均不在、单EDA锁已释放。

见[工程终态小事实](attempts/AT004_default_route/route_terminal_engineering_summary.json)、[完整工程事实](attempts/AT004_default_route/route_terminal_engineering_facts.json)。失败DCP仅为diagnostic_failed_route，不进入成功route父链；失败时序不是合法routed签核。R006已新开只读补采，不重复综合、OPT、debug、place、physopt或该失败route。以下保留实际阶段历史。

- 原AT001 fresh_place_physopt于2026-10-16T02:46:43Z真实启动；[started](attempts/AT001_fresh_place_physopt/started.json)、[独立监督启动/锁身份](attempts/AT001_fresh_place_physopt/detached_launch_handoff.json)。
- 使用同一新工程m002_E005_R002_AT006_fresh、R003/AT001独立恢复资格的342源/23+22/45DCP父链；旧原监督UNKNOWN/观测缺口仍保留，不当作持续监督成功。
- 安装的Python subprocess start_new_session与独立stdio实际分离supervisor265616/start923136210；nativeleader265627/start923136332。02:47:30Z监督PPID1/独立pgrp、CPU0–7/nice5，内核FLOCK WRITE265616持单EDA锁inode169247080。非绝对持久保证；原失联根因未证明。
- 命令：run_m002_optimized.py place --attempt <R004/AT001_fresh_place_physopt> --report <m002_E005_R004_AT001_fresh_place_physopt> --project <新工程> --synth-report <R003报告> --synth-attempt <R003/AT001>；精确argv由started/command记录。
- INIT→OPT/debug→SSI_SpreadSLLs place→Default独立physopt。当前142生产输入冻结；8CPU/max8/nice5，RSS192GiB、MemAvailable48GiB持续30s、disk30GiB，无wall/no-output期限。仅一条EDA lane。
- 后继按新真实clock/reset/CDC和80边界/负载/位置/SLR图检查；负setup/hold不自动阻止诊断完整route。结构/资源/约束非法先按合同修，阶段成功/异常实际通知主控。
- route尚未启动；无bitstream/板卡/GPU/PPL/ACC。尚无placed/physopt/route通过结论。

## 实际阶段变化

03:17 UTC前INIT完整POST已真实完成：coverage=PENDING_TOOL_DEBUG_MATERIALIZATION、blackboxes=1，正式安全OPEN。原生opt_design开始，预条件DRC0 Errors，进入Phase1.1.1 Generate And Synthesize MIG Cores。当前正常运行/源142冻结。已有project-mode OPT POST严格guard可能导致自然非零；仅在真实终态后保全新OPT和原失败，按本轮来源最小适配显式debug恢复，不重综合/INIT/OPT。非生产draft位于agent/A006/pending_project_opt_recovery，尚未安装。

03:56 UTC前原生`opt_design completed successfully`，0Errors，elapsed39:03、CPU1:47:28；原始OPT POST继续，03:59已生成本轮`opt.dcp`并开始报告。仅为OPT内部命令成功，不代表完整POST、布局或时序通过。实际里程碑前缀证据见[OPT观察](attempts/AT001_fresh_place_physopt/native_OPT_completed_observation.json)。MIG和hub均为本次真实新生成；hub23文件/884009bytes和5条worker XDC读路径保全，existing generated_debug_parent通过；PHY produced/result两对一致，disable配置与native2条Added-cache消息并存，指定repo该次观察无文件，均原样保留。所有142生产输入03:42:50复核未改；恢复草稿/32定向CPU通过尚未安装，不当作真实parent资格。

## AT001真实终态与AT002接续

- 原AT001于04:15:48.372Z以native/supervisor1结束，stop=null、无owned残留；精确错误为`native project mode has no qualified explicit pre-place debug admission`。原`opt_result.txt`仍completed0，`integrity_opt.json`和原生`opt_command_result.txt`保持不存在。1053资源样本、40 tracked原身份加supervisor均核为不在，峰值为采样树32.6805GiB；见[终态facts](attempts/AT001_fresh_place_physopt/native_OPT_POST_terminal_facts.json)。
- 原生OPT成功与checkpoint不重跑。新OPT DCP SHA `af634c358eecf869c83cb45c0755d0164b39d5a9f5aed316bcaa52cd3c02919e`，218327530bytes，part/top/board/tool一致；[独立log-derived来源证明](attempts/AT001_fresh_place_physopt/native_project_opt_execution_proof.json) SHA `458a75098c185500684514bd68c8341f1bdc30ebe55e3a0979ec72f12fb240d1`，明确不是虚构的原生命令回执或原POST成功。
- 原142输入安装前全部匹配，5份旧工程脚本已保全；窄fresh-project/disabled-cache规则、独立proof、actual CDC probe、显式恢复directive和精确归档传播安装后，[R002/AT009](../R002/attempts/AT009_project_OPT_recovery_cpu/completion_facts.json)198项CPU通过，native/supervisor0、无残留；当前144输入前后不变，342源/45DCP父链再资格通过。旧legacy来源/timeout契约不扩展。
- AT002使用原AT001 `--opt-report`恢复，实际模式`checkpoint_restored_commands`，`HAP_RECOVERY_OPT_LOG_DERIVED=1`，原OPT POST未完成标志保持0。新阶段只实际执行未完成POST、显式debug与当前图pre-place，然后`place_design -directive SSI_SpreadSLLs`、独立`phys_opt_design -directive Default`；后继完整route仍待合法physopt父链。
- [AT002实际分离启动/CPU/锁观测](attempts/AT002_native_OPT_POST_recovery_place_physopt/detached_launch_handoff.json)。正常推进无wall/no-output强停；144生产输入冻结，不热改；bitstream/板卡/GPU/PPL/ACC仍不运行。

## AT002原失败与AT003实际物理结果（08:36 UTC仍在运行）

- AT002仅辅助CDC报告绑定仍要求旧hash而自然失败。完整Critical tuple及同OPT/DCP/约束、真实归档producer和命令/clock pair联合绑定已按当前E005来源窄修；保留旧严格分支和四个raw UNKNOWN枚举cap的coverage_limited。R002/AT010实际219项CPU回归通过，144生产输入不变；AT002原失败/原integrity不覆盖。
- AT003恢复原OPT，显式debug命令原生0，native说明cores already implemented；新的debug DCP及完整pre-place合格，但raw debug_proof verified=0、hub声明300MHz与实际50MHz关系和正式安全OPEN保留。
- SSI布局原生命令成功，8387秒；新place DCP SHA `32b4af05f2ba43c8f63ec8ee44f7fcd40dbc1d6f5012638d404bb0cb6678bdf2`。完整place POST completed1/diagnostic eligible1，BB0/internal clocks COMPLETE、gate issues0、当前Critical8/new0、真实reset/fanout/688 BRAM验证通过。
- placed资源：LUT801751、CLB Registers1017050、CLB143802（97.31%），SLR1 CLB99.85%；SLL Used18983。80局部边界和26624 CE leaf pins逐项通过。新48行Placer Final拥塞Global/Long/Short峰均Level6；旧48固定窗未被选中，当前值NOT_MEASURED，不能记0或改善。
- 完整place POST之后实际独立`phys_opt_design -directive Default`原生0、25秒。native因WNS非负跳过setup优化，明确netlist未改；新physopt DCP SHA `766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d`。
- [正式physopt时序/资源事实](attempts/AT003_current_CDC_bound_OPT_place_physopt/physopt_timing_utilization_report_facts.json)十二summary字段与placed相同：WNS+0.103ns/TNS0；WHS−0.695ns/THS−2145.408ns/hold30885；PW0。overall hold FAIL，均为布线前估计。内部+0.255不构成正式改善。
- 完整physopt POST正在正常运行；当前父链尚未闭合，不能宣称route已开始或时序已收敛。实际闭合后直接一次完整Default route；合同比较缺项在route自然终态后单EDA只读各自closed place/physopt DCP补齐，不重复物理命令或增设审批。

## AT003真实终态及AT004接续

AT003于08:57:32.868921Z自然结束，native/supervisor0、stop=null、无owned残留，全部tracked PID/start身份已不在，原单EDA锁已释放。完整physopt hook completed1/diagnostic eligible1、BB0/internal COMPLETE、gate issues空、current Critical8/new0、reset/fanout qualified/688 BRAM；144生产输入未变，安装版`parent_place`实际验收通过。见[4440字节小事实](attempts/AT003_current_CDC_bound_OPT_place_physopt/completed_physopt_POST_summary_facts.json)及其中绑定的完整证明。正式时序仍overall hold FAIL，formal reset/CDC/外部IO仍OPEN；本次诊断资格不代表签核。

AT004随即在08:58:49.935Z实际启动，单EDA锁由611388持有，leader611402/start925369067、native611607/start925370167，实际CPU0–7/nice5；见[实际进程与锁观察](attempts/AT004_default_route/detached_launch_handoff.json)。恢复原AT003 physopt DCP后，09:10 UTC已实际观察line122精确`route_design -directive Default`及line131 Phase1 Build RT Design；原log前缀另存，不替代继续增长的完整log。正常推进无墙钟/无输出强停。route自然终态后按R006范围单EDA只读补采；不重复已成功物理命令、不无依据重试同route，不把启动当作布通或时序通过。

09:30 UTC，Phase4.2 Update Timing之后原生log245出现Route35-447：拥塞正在阻碍全部nets完成连接，router将优先完成连接而非timing优化。[告警事实与不可变log前缀](attempts/AT004_default_route/native_route_congestion_priority_observation.json)已保全；当时进程及资源正常、没有真实终态。这是进行中风险，不提前判自然失败；继续唯一Default route，不热改策略或强停。原生intermediate时序仅为过程数据，不替代正式routed报告。

10:05 UTC，Phase4 Initial Routing已完成（native累计elapsed00:55:52），Initial Estimated Congestion原生Global/Short及Timing分别明确Level7（128×128）。[初始路由拥塞事实](attempts/AT004_default_route/native_initial_estimated_congestion_facts.json)保存四方向×Global/Long/Short的size和%Tiles及全部60个原生INT/物理tile窗口；Long只给size/%Tiles，不擅推level，Timing只给标量、未提供窗口。%Tiles峰Global20.09 North、Long30.52 North、Short19.03 West，重叠窗口不相加。这与placed/physopt的Placer Final Level6属于不同报告；旧E003仅在最终按相同route阶段比较，不做跨阶段改善或自然失败结论。10:06:45Z进程已进入Phase5.1.1 Update Timing，资源正常、无终态，仍继续同一次Default route。

11:22 UTC观察：同一次Default route已从Phase5.2 Global Iteration1推进到Phase5.3 Global Iteration2，仍无终态且CPU/资源正常。log398重叠nodes2183923及log399原生中间WNS−13.535ns、TNS−1866986.607ns、WHS/THS N/A已按原phase、原文行号及不可变log前缀保全，见[小事实](attempts/AT004_default_route/native_route_iteration1_intermediate_timing_observation.json)；统一phase/count/intermediate ledger保存在同AT的native_route_progress.jsonl，producer原字节另存。中间值不替代最终routed报告，N/A不代表hold通过；不改变策略、不新增停点，继续至真实自然终态。

12:01 UTC观察：Phase5.3 Global Iteration2的原生log406新报告2472092重叠nodes，见[统一progress capture002](attempts/AT004_default_route/native_route_progress_captures/capture_002_facts.json)及原count ledger同步的不可变前缀。暂无新中间时序或终态；该数仅为原phase过程计数，不推导最终合法布通结论或跨阶段delta。当前supervisor身份/CPU增长与资源正常，继续唯一Default route，无新gate/策略/停点。已实际消息通知Root。

13:08 UTC保全：原生log407确认Phase5.3 Global Iteration2完成（checksum1f804179b，累计elapsed03:56:27/CPU15:14:40）；log410确认Phase5 Rip-up And Reroute完成（同checksum，累计elapsed03:56:28/CPU15:14:48）。见[小事实](attempts/AT004_default_route/native_route_phase5_completed_observation.json)。只读observer v3新增checksum完成行和累计用时的统一记录，v1/v2原字节保留；capture004同时回填之前阶段的原完成/时间行，不代表那些阶段在本次新执行。没有新计数/中间时序或route/supervisor终态；继续同一Default，不设新门或改变策略。

13:25 UTC原生推进：Phase6 Delay and Skew Optimization已完成（累计elapsed04:15:39），随后Phase7.1 Hold Fix Iter完成（04:15:43）、Phase7.2 Additional Hold Fix完成（04:16:08），并进入Phase7.3 Non Free Resource Hold Fix Iter。见[小事实](attempts/AT004_default_route/native_route_phase6_completed_holdfix_started_observation.json)及统一capture005–007的不可变前缀。没有原生返回initial route文字，不推断；hold修复阶段不代表正式hold PASS，尚无route终态。继续同一Default，终态封存后再R006。

13:26 UTC重大原生结果：Phase9 Verifying routed nets的log520 Route35-162报告758463个因拥塞未布通信号；log630 Route35-2明确Design is not legally routed，1148579个节点重叠。见[合法布通失败小事实](attempts/AT004_default_route/native_route_phase9_legality_failure_observation.json)及capture009不可变原文。signals与nodes为不同指标，不互换。合法布通检查FAIL已确定，但log633进入Phase10 Depositing Routes，原命令和supervisor尚未终态；继续原生自动DRC、失败DCP/诊断保存与原错误重抛，不中断，不把进行中取证记为已终结。终态后核native/supervisor/144freeze/进程与锁，再按R006顺序只读补采。Root和A007已实际获知。

失败checkpoint真实保存：原生checkpoint capture项code0，started_epoch1792157531→ended_epoch1792157720（189秒）。route_failed.dcp为779113008bytes、SHA6d1cf5ef3fea7b8ca0ab7ba27aaa61383ce487a640bcb63248cb6a9af7009590，已读核写入前后size/mtime不变，见[保存观察](attempts/AT004_default_route/failed_checkpoint_saved_observation.json)及其不可变原错误、receipt/log前缀和producer。该DCP严格为diagnostic_failed_route，不可作为成功route父链。观察时其余失败诊断/外层route回执/supervisor未终态；Root与A007已实际通知。

## AT004自然失败终态与工程解释

原route在完成Phase10/11及自动DRC后，以原错误进入五项失败取证；checkpoint、route_status、timing、congestion、drc分别原生0，合计1449秒，随后外层Tcl receipt17233秒原错误code1。原生route含自动DRC04:23:02、内部total15510.3秒、整AT17864.645122秒属不同时间范围，不混比。

失败route_status明确routable2,031,772、fully routed1,273,309、routing errors/resource conflicts758,463；unrouted/partially routed未显式报告，不能补0。失败诊断时序WNS−13.528ns/TNS−1,920,757ns、setup failing546167，WHS−0.258ns/THS−468.768ns、hold failing13151，WPWS−0.537ns/TPWS−3.018ns、PW failing10，三项均FAIL且不作为合法routed签核。DRC含RTSTAT-13并声明RTSTAT-*未运行，不能称全绿。失败congestion文件仅含Placer Final24行、Router Initial21行，无Router Final表；最终Phase8拥塞使用原生日志和A007同阶段证据。

3515个资源采样中树RSS峰27.288212GiB、MemAvailable最低385.292797GiB、磁盘最低404.394199GiB，最大间隔6.013834秒；无保护触发。独立审核复用R005的同阶段、中间、Phase9及自然终态记录，不重复抽取E003基线。formal reset/CDC/外部IO仍OPEN，本轮未获得可用route或bitstream。
