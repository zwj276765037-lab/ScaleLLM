# 阶段审核队列

每个 SM 可独立审核；执行、研究判断和审核状态分开。队列变更后由主控通过真实对话报告重要事件。

用户备注和跨任务决策可写在自动管理区外。

## 2026-10-15：M002 启动条件审核

- 事件：EV_M002_20261015_READINESS；类型：global_impact / blocker。
- [审核正文](reviews/M002_readiness_2026-10-15.md) / [Q001](../question/Q001_M002_synthesis_readiness/question.md)。
- 结论：当前 RTL 权重配对被切断、Host/地址布局及构建约束存在缺陷，不能按“设计完成”启动正式综合实现。主控建议 revise；缺陷未修复、未验证。
- 已在本轮用户对话报告。未取得工程执行新授权，未启动 EDA，不把此记录当作用户批准。

<!-- research-agent:stage-events:begin -->
## Stage review index

Active: 69. Resolved: 1. Newest events appear first. Full evidence and review history remain in the linked small-mission review pages.

### Pending / needs evidence / revise / paused

| Event | Small mission | Trigger | Review | Decision required | Summary |
|---|---|---|---|---|---|
| [EV_SM012_E008_AT001_schema_failure_AT002_resumed_20261017](reviews/SM012.md) | SM012 | anomaly | pending | false | AT001于05:12:22Z因布局前RLOC_ORIGIN schema入口错误自然exit1，未place；14项收尾通过。45bbc普通修复26例及独立审核接受，但Root来源绑定未及时接续；… |
| [EV_SM012_E008_R001_AT001_actual_native_started_20261017](reviews/SM012.md) | SM012 | milestone | pending | false | E006 R006 AT003完整候选比较自然0/0结束并独立接受，主控仅选择C01；E008 R001 AT001于2026-10-17T04:50:44.658893Z实际原生启动，35归档源/… |
| [EV_SM010_R005_AT002_python_environment_failure_20261017](reviews/SM010.md) | SM010 | anomaly | pending | false | R005 AT002真实owner导出通过，但Vivado派生Python缺少_tkinter导致资格adapter导入失败；01:45:04Z自然终态native/supervisor1，clas… |
| [EV_SM010_R005_owner_integration_failure_and_retry_20261017](reviews/SM010.md) | SM010 | anomaly | pending | false | R005 AT001因清理入口时遗漏owner辅助函数自然失败，原局部mock未覆盖完整readonly_resolve；根因和审核局限已独立订正，恢复原函数并补完整入口正负对照后AT002于09:… |
| [EV_SM010_R005_native_started_after_explicit_switch_20261017](reviews/SM010.md) | SM010 | milestone | pending | false | 用户明确批准当前R004诊断切换后，R004真实受控收尾并通过输入/PID/锁独立核查；R005新有向cut诊断于09:19:19真实原生启动。 |
| [SM010-E006-20261017-hotspots-revise-candidate-priority](reviews/SM010.md) | SM010 | milestone | pending | false | 真实热点与40失败样本已闭合：MLP占UNION约76.735%，旧输入candidate仅1.01%且仅23/657样本热点负载；原候选降为探索对照。 |
| [SM010-E006-20261017-user-authorized-readonly-switch](reviews/SM010.md) | SM010 | milestone | pending | false | 用户明确允许仅切换这一次只读诊断；A006已按实际PID/start发出受控停止并保存真实原终态。 |
| [EV_SM010_E006_first_native_owners_20261017](reviews/SM010.md) | SM010 | milestone | pending | false | 首批已关闭原生owner：SLR1 MLP为248355 LUT/288933 CLB Registers/361 BRAM tile，相比E003同根+55033/+42104/+259；Atte… |
| [EV_SM010_E006_readonly_started_20261016](reviews/SM010.md) | SM010 | milestone | pending | false | R001/AT001于2026-10-16 15:51:44.063950 UTC实际启动，监督942046、leader942061，原生已加载指定xcvu9p器件并打开E005当前physopt… |
| [EV_SM009_E005_final_failed_reviewed_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | E005一次优化implementation自然route失败；失败现场保全，R006两批只读补采与独立审核完成，最终交付已整合。1148579重叠节点、758463拥塞失败信号；合法布通目标未达成。 |
| [EV_SM009_E005_route_closed_R006_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | AT004完整route及失败取证自然native/监督1结束，无强停/残留、144输入保持；R006 AT002已实际启动双phase只读补采。 |
| [EV_SM009_E005_route_legality_failed_20261016](reviews/SM009.md) | SM009 | anomaly | pending | false | AT004原生Phase9合法布通检查FAIL：1148579重叠节点、758463拥塞失败信号；进程继续原生收尾与失败取证。 |
| [EV_SM009_E005_route_initial_level7_reroute_20261016](reviews/SM009.md) | SM009 | anomaly | pending | false | 实际route初始估计Global/Short及Timing拥塞均Level7（128×128），已进入Phase5拆线重布，进程正常。 |
| [EV_SM009_E005_native_route_congestion_priority_20261016](reviews/SM009.md) | SM009 | anomaly | pending | false | 实际route在Phase4.2后报告Route35-447：拥塞妨碍全部网络布通，工具转为优先完成连接，当前仍正常运行。 |
| [EV_SM009_E005_native_Default_route_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | AT004已实际调用route_design -directive Default并进入Phase1 Build RT Design，原生完整route运行中。 |
| [EV_SM009_E005_physopt_closed_route_entry_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | AT003完整place/physopt POST及最终父链通过，自然native/监督0且无残留；AT004完整Default route入口已实际启动，当前恢复本次physopt DCP。 |
| [EV_SM009_E005_place_closed_physopt_saved_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | AT003完整placed POST通过；独立Default physopt原生0/25秒，新physopt DCP保存，原生日志明确网表未修改，完整physopt POST继续。 |
| [EV_SM009_E005_place_native_succeeded_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | AT003真实SSI_SpreadSLLs布局命令自然返回0、0 Errors，耗时8387秒；正在写新place DCP并进入完整POST。 |
| [EV_SM009_E005_debug_closed_place_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | AT003完整debug POST及pre_place实际通过，新图复位与内部时钟检查通过；原生日志确认真实SSI_SpreadSLLs布局已启动。 |
| [EV_SM009_E005_CDC_report_identity_recovery_20261016](reviews/SM009.md) | SM009 | anomaly | pending | false | AT002在当前复位结构qualified=true后，因定向CDC报告的旧固定整文件hash不匹配而自然返回1；无强停/残留，布局未开始。 |
| [EV_SM009_E005_OPT_recovery_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | 物理恢复入口已安装，198项CPU通过且144输入冻结；R004/AT002于04:20:06 UTC从本轮新OPT检查点实际接续。 |
| [EV_SM009_E005_fresh_OPT_POST_recovery_20261016](reviews/SM009.md) | SM009 | anomaly | pending | false | 原生OPT成功并生成新opt.dcp；R004/AT001随后因缺少显式pre-place debug准入而POST自然失败，native/监督1、无强停或残留，布局未开始。 |
| [EV_SM009_E005_physical_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | 新综合恢复closure及342输入/45DCP已绑定，补充164项CPU通过；R004/AT001于02:46:43 UTC实际启动新物理实现。 |
| [EV_SM009_E005_synth_native_completed_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | 新综合及完整外层报告自然完成，原wrapper native/exit均0；80局部控制逐项通过，LUT较同阶段基线减少12813。 |
| [EV_SM009_E005_supervision_handover_20261016](reviews/SM009.md) | SM009 | anomaly | pending | false | 工程代理曾因登录凭据错误中断；恢复后实时发现原综合监督进程消失、原leader/Vivado仍存活，已为同PID树恢复资源guard与单EDA锁。 |
| [EV_SM009_E005_functional_pass_fresh_create_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | 首选3个RTL的Attention与生产Down/Gate局部功能验证完成；179项最终入口CPU通过，安装版SSI参数已核；141输入冻结后新工程create实际启动。 |
| [EV_SM009_E005_optimized_implementation_started_20261016](reviews/SM009.md) | SM009 | milestone | pending | false | 用户明确授权优化与新implementation，SM009/E005已实际启动A009 RTL/TB、A006构建/唯一EDA、A007独立审核。 |
| [EV_SM007_FULL_IMPLEMENTATION_NATURAL_FAILURE_FINAL](reviews/SM007.md) | SM007 | milestone | pending | false | 完整物理尝试自然结束：place/独立physopt成功，route命令19065秒后Tcl1，245279重叠节点/248289拥塞失败信号；无route DCP/完整POST。 |
| [EV_SM007_ROUTE_NATIVE_LEGALITY_FAILURE](reviews/SM007.md) | SM007 | milestone | pending | false | R003/AT001 Phase9原生Verification failed，Route35-2明确Design is not legally routed，245279 node overlaps… |
| [EV_SM007_ROUTE_INTERMEDIATE_SETUP_RISK](reviews/SM007.md) | SM007 | milestone | pending | false | 同一Phase5.2拆线重布输出新的中间时序：WNS−17.994/TNS−2261923.747ns，WHS/THS=N/A；此前重叠节点已下降至501530。 |
| [EV_SM007_ROUTE_LEVEL7_REROUTE](reviews/SM007.md) | SM007 | milestone | pending | false | 初始网络布线Phase4完成，当前进入Phase5拆线重布；初始详细路由Global/Short及Timing估计拥塞Level7。 |
| [EV_SM007_ROUTE_INITIAL_CONGESTION_PRIORITY](reviews/SM007.md) | SM007 | milestone | pending | false | 详细路由阶段Route35-447提示拥塞妨碍全布通，工具内部优先布通全部网络；后续正常推进至Phase4.6。 |
| [EV_SM007_ROUTE_GLOBAL_TO_INITIAL](reviews/SM007.md) | SM007 | milestone | pending | false | 全局布线真实完成：GR Congestion7076→0，下一迭代仍0，进入Phase4.1初始网络布线。 |
| [EV_SM007_ROUTE_SLL_DEMAND_RISK](reviews/SM007.md) | SM007 | milestone | pending | false | Route35-3311：SLR0–1估计SLL需求126.66%、列峰208.125%；SLR1–2总量83.81%、列峰141.944%，真实路由出现显著局部拥塞风险。 |
| [EV_SM007_ROUTE_NATIVE_STARTED](reviews/SM007.md) | SM007 | milestone | pending | false | 已真实进入route_design并推进全局时钟网络布线；同native PID/start连续，CPU0–7/nice5，无wall期限。 |
| [EV_SM007_ROUTE_RESTORE_STARTED](reviews/SM007.md) | SM007 | milestone | pending | false | 独立physopt完整POST及真实终态成功，13进程无遗留；R003/AT001布线阶段Vivado于17:18:03 UTC启动读取physopt检查点。 |
| [EV_SM007_PHYSOPT_POST_COMPLETED](reviews/SM007.md) | SM007 | milestone | pending | false | 完整physopt POST通过：result1/eligible1、BB0、内部覆盖完整、gate\[\]；55阶段文件封闭，实际结构/fanout合格，Critical8/new0。 |
| [EV_SM007_PHYSOPT_NATIVE_COMPLETED](reviews/SM007.md) | SM007 | milestone | pending | false | 独立physopt于16:38:12 UTC native0/18分26秒，closed DCP已保存；正式WNS−1.290ns，较place改善0.529ns，setup失败980，时序仍FAI… |
| [EV_SM007_PLACE_POST_COMPLETED_PHYSOPT_STARTED](reviews/SM007.md) | SM007 | milestone | pending | false | AT002新完整原生place POST于16:19:46 UTC通过，64文件封闭；真实日志随即进入独立phys_opt_design。 |
| [EV_SM007_CLOSED_PLACE_RECOVERY_STARTED](reviews/SM007.md) | SM007 | milestone | pending | false | 150项CPU及真实CDC/来源/worker准备/后继archive核验通过；5文件已安装，AT002 Vivado于15:35:29 UTC实际从closed place点启动恢复。 |
| [EV_SM007_PLACE_POST_CDC_REPAIR](reviews/SM007.md) | SM007 | anomaly | pending | false | place命令/DCP及正式物理报告已完成；15:08:08 UTC POST因2条DDR1 AUX CDC报告源变化未获分类而自然退出1，Critical总数仍8。 |
| [EV_SM007_PLACE_COMMAND_COMPLETED_CONGESTION](reviews/SM007.md) | SM007 | milestone | pending | false | 14:36:01 UTC place_design native0，耗时2小时1分35秒，随后DCP保存成功；完整POST仍在生成。新增高拥塞告警已独立核范围。 |
| [EV_SM007_ACTUAL_PLACE_STARTED](reviews/SM007.md) | SM007 | milestone | pending | false | E003本次live guard native0/174秒，零blackbox/DRC blockers、内部clock覆盖通过；已实际执行place_design，日志记录Phase1.1完成。 |
| [EV_SM007_NO_WALL_HANDOFF_EFFECTIVE](reviews/SM007.md) | SM007 | milestone | pending | false | 12:32:57 UTC无wall监督实际接管：仅暂停旧supervisor，worker/Vivado及计算进程身份连续；接管后native CPU实增17749 ticks，旧固定截止不再执行。 |
| [EV_SM007_NO_WALL_STOP_DIRECTIVE](reviews/SM007.md) | SM007 | milestone | pending | false | 用户追加“不要设置强行停止 只要进程还在正常继续”；取消E003固定12h/24h墙钟终止。原Vivado继续，工程正在安全调整监督，尚未据回执确认旧timer已失效。 |
| [EV_SM007_FULL_IMPLEMENTATION_STARTED](reviews/SM007.md) | SM007 | milestone | pending | false | 129项CPU和真实339/45/AT008来源验证通过，E003独立profile已安装；R002/AT001实际Vivado于12:22:11 UTC启动，正在恢复完整debug/pre_pla… |
| [EV_SM007_FULL_IMPLEMENTATION_AUTHORIZED](reviews/SM007.md) | SM007 | milestone | pending | false | 用户追加“进行一次完整的implementation”；SM007/E003新合同已建立并经A007流程初审，当前工程准备E003独立预算profile，尚未记录新EDA启动。 |
| [EV_SM006_AT009_TERMINAL_NO_PHYSICAL_POINT](reviews/SM006.md) | SM006 | blocker | pending | false | AT009于11:41:11 UTC按原两小时上限结束，124/native−15，无遗留；已到布局后时序优化，但无place/physopt成功回执或完整DCP。 |
| [EV_SM006_AT009_RESTORED_PLACE_STARTED](reviews/SM006.md) | SM006 | milestone | pending | false | AT009本次live恢复检查通过，已实际执行place_design。前置准备由AT008同口径2629.541秒降至748.398秒，实测减少31分21秒；入place时剩107分31.6秒。 |
| [EV_SM006_AT009_PRE_PLACE_RECOVERY_STARTED](reviews/SM006.md) | SM006 | milestone | pending | false | AT012新增13项恢复+6项隔离测试以及真实完整POST/父链核验PASS，入口已安装；AT009于09:41:02 UTC从已完成debug/pre_place实际启动恢复，单次截止11:41:… |
| [EV_SM006_AT008_PLACE_WALL_COST_STOP](reviews/SM006.md) | SM006 | blocker | pending | false | AT008于09:08:31 UTC按原2小时上限受控结束，124/native−15、无survivors。实际布局已到细化Phase3.3，但无place/physopt成功回执或完整DCP，r… |
| [EV_SM006_PLACE_USER_SLL_REG_IGNORED](reviews/SM006.md) | SM006 | anomaly | pending | false | AT008实际布局出现Place30-1229，SLR分区不能满足部分USER_SLL_REG并忽略属性继续；08:22:43 UTC处于Phase2.1.1.2。日志保留100条可见warning… |
| [EV_SM006_ACTUAL_PLACE_STARTED](reviews/SM006.md) | SM006 | milestone | pending | false | AT008实际OPT准入、显式debug与完整新阶段pre_place通过；已执行place_design，两次前置DRC0 Errors，07:55:15 UTC归档观察到Placer Phase… |
| [EV_SM006_COMPLETE_OPT_DIAGNOSTIC_GATE_QUALIFIED](reviews/SM006.md) | SM006 | milestone | pending | false | AT007取得全部688 BRAM写端口实际时钟，原失败1保留；修正辅助枚举上限分类后，AT011在完整真实OPT数据上组合gate_issues=\[\]，限定复位结构、完整fanout及精确8 Cr… |
| [EV_SM006_ACTUAL_RESET_STRUCTURES_QUALIFIED](reviews/SM006.md) | SM006 | milestone | pending | false | AT006原门失败终态保持；完整实际复位图和14份原语导出已保存。独立源语义核查与新解析器离线回归支持7 async、4 AUX、3 HostSplit限定结构；完整CDC诊断门尚待688 BRAM… |
| [EV_SM006_OPT_NEW_RESET_CDC11](reviews/SM006.md) | SM006 | anomaly | pending | false | AT005完整OPT CDC报告新增2条CDC-11 Critical：XDMA user_reset至DDR0/DDR1 base_reset首级CLR，同源同目的UI另有HostSplit复位同… |
| [EV_SM006_OPT_COMPLETED_CONTROLLED_STOP](reviews/SM006.md) | SM006 | milestone | pending | false | AT004真实OPT成功并保存DCP；黑盒/no_clock/内部未约束均0，未布局时序仍FAIL；在place前按既定guard受控终止，整体125/native-15，POST未完成。 |
| [EV_SM006_ACTUAL_INIT_COMPLETE_OPT_STARTED](reviews/SM006.md) | SM006 | milestone | pending | false | AT004统一预检与完整INIT POST实际完成，已进入真实opt_design；INIT诊断准入成立，blackbox=1/coverage仍PENDING工具debug物化。 |
| [EV_SM006_DEBUG_MATERIALIZATION_STAGE](reviews/SM006.md) | SM006 | anomaly | pending | false | 实际native implementation Tcl证明debug模块由place前独立implement_debug_core生成，新增恢复入口遗漏此步；此前OPT自动物化假设被否定。 |
| [EV_SM006_RECOVERY_IDENTITY_QUERY_FAILURE](reviews/SM006.md) | SM006 | anomaly | pending | false | AT003已真实打开project-init DCP并恢复时序/约束，但current_design NAME误作RTL top的检查导致exit1；未执行six-target或OPT。 |
| [EV_SM006_INIT_PROBE_QUERY_FAILURE](reviews/SM006.md) | SM006 | anomaly | pending | false | AT002真实project link与init DCP写出完成；INIT POST的指定CDC复位引脚查询失败，整体exit1、35.89分钟，无资源停止或遗留。 |
| [EV_SM006_FIRST_PHYSICAL_STARTED](reviews/SM006.md) | SM006 | milestone | pending | false | 新物理入口47项CPU验证通过，完整339源/45 DCP身份复核一致；首个R003 AT001于03:21:57 UTC真实启动project init/opt→place/phys_opt。 |
| [EV_SM005_FRESH_SYNTH_COMPLETED](reviews/SM005.md) | SM005 | milestone | pending | false | AT002正式综合及完整报告流程完成：exit0、114.28分钟、峰值进程树RSS约27.06GiB、owned_survivors=\[\]；新板级资源未超总容量，时序与覆盖未关闭。 |
| [EV_SM005_SYNTH_COVERAGE_GAPS](reviews/SM005.md) | SM005 | anomaly | pending | false | 完整board综合报告已产生：总容量未超，setup+0.904ns/hold-0.814ns及5脉宽违例；530无clock/554未约束端点集中于MIG调试链，唯一dbg_hub_CV占位；6条… |
| [EV_SM005_FRESH_CREATE_STARTED](reviews/SM005.md) | SM005 | milestone | pending | false | 用户追加授权的E002正式流程已真实启动fresh create，独立项目/报告目录并启用受管CPU/内存/磁盘/时间保护。 |
| [EV_M002_QUICK_VALIDATION_COMPLETE](reviews/SM004.md) | SM004 | milestone | pending | false | M002本轮修复与快速验证完成：Host106、构建CPU49、整数参考9、四套XSim及完整board展开通过；实际BD校验退出0，地址别名critical与历史reset告警保留并已限定解释。 |
| [EV_SM004_M002_BD_ADDRESS_WARNINGS](reviews/SM004.md) | SM004 | anomaly | pending | false | 真实BD validate退出0，但原始日志出现4条BD41-1354地址段重叠critical，不能等同于无告警签核。 |
| [EV_SM002_M002_GROUP_SCOREBOARD_DIAGNOSIS](reviews/SM002.md) | SM002 | anomaly | pending | false | 完整权重组/原生frontend首组比较失败；诊断发现native expected全X而DUT payload确定、metadata相等，正在修复测试台组合计算初始触发并保持独立期望算法。 |
| [EV_SM004_M002_DATA_AND_LAYOUT_PASS](reviews/SM004.md) | SM004 | milestone | pending | false | 生产复用的独立256bit数据router和M002只读布局CSR已通过真实XSim定向测试；构建CPU回归21/21通过。 |

### Recent resolved (up to 8)

| Event | Small mission | Trigger | Review | Decision required | Summary |
|---|---|---|---|---|---|
| [EV_SM008_E004_routability_analysis_complete_20261016](reviews/SM008.md) | SM008 | milestone | approved | false | 详细可布性分析完成：原生确认Attention双wave10根6170–6174扇出索引与MLP8201/6145跨SLR输出控制；形成input48局部边界+MLP32同拍CE、SSI_Sprea… |

Earlier resolved events omitted from this compact queue: 0. [Full per-mission review pages](reviews/).
<!-- research-agent:stage-events:end -->
