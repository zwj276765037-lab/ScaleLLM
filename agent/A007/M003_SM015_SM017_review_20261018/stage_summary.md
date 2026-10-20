# A007：SM015–SM017 有界阶段摘要

2026-10-18，当前独立审核 execution=running；G3a局部功能集成与G3b v3固定入口现已独立接受并实际送达Root/A006；G4尚未通过。本文件是可更新导航，各具体审核原件保持。

Root 已正式冻结 M2+A3+C-P1，G2 原件 SHA `4424c426859b6b1e64be2f52a008ff6c03e1a6854f71570970cbba4941fff709`；[一致性审核](G2_root_freeze_fidelity_review.json)接受。SM014 最终审核见[封存结论](../M003_SM014_review_20261018/G2_consolidated_design_review.md)，工程 manifest `6d74e85d…`。

| 独立审核子项 | 实际结论 | 适用边界 |
| --- | --- | --- |
| [首 RTL 源码](initial_RTL_source_review.json) | 3 原件与冻结基线相同，3 diff 重建；实际 42/39 CE 映射共 13,120 bit 全等，实际 CE/D 表达式 1,024 组合等于旧 case；非改动区保持。 | 静态/方程审查，不代替 native。 |
| [AT002 A3 helper](AT002_A3_helper_native_review.json) | 44 inputs；实际 UNISIM LUT2/3、131,072 进位回绕、8 个 S/L/R 组合及异步 reset；整链 0，无 stop/survivor。 | helper，不是存储/core 集成。 |
| [AT002 M2 parent 差分](AT002_M2_parent_native_review.json) | 44 inputs；旧/current parent 抽取除 module 名逐字相同，3,000 随机周期+边界队列/整 head-tail/原子接受/清空；UNISIM LUT1，整链 0。 | branch 是明确可控 ready stub；另用下一项验真实分支。 |
| [AT002 M2 真实生产位宽 dispatch](AT002_M2_production_dispatch_review.json) | 131 inputs；真实 branch/kernel，独立整数参考只改测试名字/位宽/参数；两 phase 各 2,048 事务双 branch 守恒，II=1/1/1，2,304 lane、42 stall 检查；整链 0。 | TILE_W=9，DOWN_TILES=4、DOWN_GROUPS=448；不冒充 342-tile 全规模测试或时序证据。 |
| [AT002 A3 全容量 resident](AT002_A3_resident_native_review.json) | 45 inputs、53 预运行归档（2,282,247 B）逐项匹配；原参考仅 rename，实际 mode1/default0；81,920 地址外口读写、old-word、stall、S/L/R、abort、81920/131071 拒绝、X 侧带 legacy，整链 0。 | 原生日志未打印碰撞精确值，按实际断言记≥100；不将推算 318 冒作日志实测。实际 core 标签/连接集成另验；URAM 级联/RDW/40+40 推断留 G4。 |

[AT002 M2兼容参数原生审核](AT002_M2_legacy_dispatch_review.json)：旧独立整数bench SHA bf897659保持，DOWN_TILES4/DOWN_GROUPS448/default TILE_W2实际走兼容CE路径；131输入及137预执行归档匹配，两phase各2048事务/双支守恒，II1/1/1，2304lane/42stall，42110ns、整链0，无stop/survivor。审核chunk a98896 exit0；其后actual cohort已完成，详见G3a合并审核。

三个当前生产 RTL 身份：MLP `5829f33f…`、resident `55f3e8ef…`、cohort core `672d37c9…`，完整 SHA 见各审核。所有已审 native 子项 source unchanged、无资源/时间停止、无 owned survivor；A007未启动 EDA、未读取 DCP 或操作进程/锁。

已关闭的普通问题：M2 TB 原子断言括号和同 negedge 驱动竞争在实跑版修正；AT001 helper native PASS 后相对 `$0` 校验失败保持整次 failed，AT002 改绝对入口且不改 RTL/期望；supervisor leader 先退出后须继续资源监控至归属树空的修复已查。旧 `97db…` 与 `0de59…` supervisor 已按旧 command 精确哈希分别归档，原件恢复方式明确，后续 job 启动前归档全部实际输入。

当前剩余：选定版联合回归、正式 overlay/角色/来源/保护/restore 检查实现及正负例；实际 cohort core 集成和 MLP 兼容参数已完成（见下方合并审核）。G3b 齐备且独立无阻断后按 Root 已授连续流程进入 SM017；G4 再核实际新图、预算、消费者、约束/资源兼容性及 80 保护。TOP01 −2.896 ns 未直接处理、旧报告差 22,049 OPEN、SLR2 拥堵及新增 control set 风险均保留。

[E005同阶段综合基线](E005_same_stage_synthesis_baseline_review.md)已独立核验：u_meta347LUT/11FF/80URAM，shared389067LUT/479315FF/192RAMB36/3072DSP；144冻结身份全等，111实际综合公共输入全SHA一致，7小文件锚定通过。用于同stage同metric对比；LUT合并/FF报告与primitive计数差异及旧supervision间隔保留，新G4仍待。

[G3a合并审核](G3a_consolidated_review.md)已交付：源码与六项实际native证据无局部功能阻断；新增core集成86输入/93预归档一致，302消费/303请求/300stall/4clear，真实0无stop/survivor。AT002 marker失败与AT003仅display修复保留。G3b联合回归/正式检查和G4新图/物理仍待，不新增批准门。

[AT003生产top smoke](AT003_selected_production_smoke_review.json)接受：131输入/137预归档一致，无force，真实A3mode1/M2TILE9；6次AXIL read各3cycle稳定，public core_clear后health0，1790ns整链0无stop/survivor。DDR时钟200MHz且相差1.25ns，但未发DDR数据/完整A或MLP命令。G3b整体仍待正式入口/检查包及影响回归映射。

[G3b v3正式合并审核](G3b_consolidated_review_v3.md)无阻断：manifest62d55f/41源，288最终回归原log/69归档核验，42资格/probe独立重放0；v1/v2原件保持，v3补全来源闭包/逐phaseprobe。工程可直接新R create/synth，G4新图/preplace及物理未通过。

[R002/AT001新建工程自然失败](R002_AT001_create_failure_review.md)：实际Vivado→系统Python环境污染，尚未新综合；187归档/41入口身份接受，5个已跟踪PID/start均不再存活。已实发A006/Root，合同内环境适配新AT连续推进，G4待实测。

[R002/AT002环境修复独立无阻断](AT002_python_environment_fix_review.md)：42源manifest d1f90456，5 Tcl调用+1净化helper，36旧源不变；工程191/46和独立46资格成功，实际constructor前缀污染环境核通过（原生API前stub停止）。已实发A006/Root，立即新AT重试，G4待实际包。

[AT002构建成功/AT003新综合真实启动](AT002_create_AT003_synth_handoff_review.md)：04:29:01Z create completed0；04:29:31Z fresh_synth启动。188归档/42固定源/379实际输入、原生overlay注册及6已跟踪进程环境已核，无旧根/DCP输入。G4与物理仍待。

[Constructor原告警归属](AT002_constructor_warning_attribution_review.md)已独立核：6原件/旧board-evidence回指、27条完整多重集与241配置全等，告警RETAINED而非清零；G4仍须新图关闭范围。

[AT003两条memory属性告警](AT003_ingress_memory_warning_review.json)：当前原生973/975与旧344/346源码逐行同一，旧/新源码/旧log SHA及7行窗口一致；仅原ingress数组归属，不代表新85LUT/34FF或原80保护通过。正常core OOC继续。

[AT003早期core原生资源](AT003_early_core_resource_review.md)独立接受：报告LUT+111（raw primitive和+112）、FF+34全FDCE、CARRY8+4；URAM/BRAM/DSP不变。仅同core局部合计，非各新增锥或新图/G4；顶层报告/23产22用仍待。

[AT003后报告自然失败](AT003_postreport_failure_review.md)：23实际synth end/0error，但新M003 XDC两次共12个unsupported命令告警且无apply成功回执；collector误纳parent_count，外层06:12:18Z native1。271记录PID身份已结束。工程普通入口修复新AT；Root允许按消费语义复用本次23产物，须双尝试来源严格绑定，旧失败保持，G4未过。

[AT003同stage资源报告子项](AT003_same_stage_resource_review.md)：独立实际checker0，顶层+111LUT/+34FF/+4CARRY8，meta+40/+34，shared+76/0，硬资源不变；只接受报告预算，不替代新图/精确锥/G4，原AT003failed1保持。

[AT006 原生 TCL/INIT 边界](AT006_native_tcl_mechanism_failure_review.md)：TCL 类型支持已核，但 info script 相对路径失效且错误降为 critical warning；toy opt 完成不证明约束应用。12 归档/23 PID 身份收尾闭合，实际 INIT-only/apply/restore 待 AT007，不放行 G4。

[AT007 INIT-only 原生机制](AT007_native_init_mechanism_review.md)：TCL 实际 apply1、149 行完整 INIT 前缀、无 OPT、checkpoint restore 无重施；13 归档/16 PID 收尾和 CPU11 负例已核。仅接受机制，正式修复/同源复用及 G4 继续。

[正式入口修复v1](R002_native_entry_fix_v1_review.md)：manifest8c9fb38e/45源，32不变+10入口修复+3helper，13 diff重建；工程201和独立56通过，真实identity文本1正5负通过。source/recovery-entry无阻断，可新AT008，G4仍待native严格包。

[AT008注册检查失败](AT008_registration_failure_review.md)：自然native1、4PID结束、45冻结源和8继承报告核实；在open_run/apply前被严格policy拒绝，具体属性待native dump。普通修复继续，不放行G4。

[v2注册policy恢复](R002_native_entry_fix_v2_review.md)：manifeste90400dc/45源，仅1 Tcl改、44不变；实际保存XPR已证TCL转换后UsedIn含synthesis，原policy重申和前后metadata不放宽guard。工程57/独立新增1通过，可AT009，G4待。

[AT009 policy/stale](AT009_policy_and_stale_review.md)：实际policy恢复、identity仅XDC→TCL；synth原已Out-of-date/100%/refresh1，旧fresh guard在载图前拒绝，自然1/4PID结束。恢复专用内容资格增量待审，G4未过。


v3 内容恢复入口已独立接受：manifest 151e4f11 / delivery baf56456，45 源 5 改 40 不变、5 diff 重建、工程 59/A007 新增 2 测试及 Tcl mock 通过。真实 stale 保留，普通 fresh guard 不变；生产图和 G4 尚待。见 [审核](R002_native_entry_fix_v3_review.md)。


AT011 机制已独立核：实际 stale/100%/refresh1 下 open_run 和完整 INIT 成功，apply1/2；旧绝对计数断言导致 native1，restore 未到、G4 未放行。13 归档/6 组机制绑定、独立 prefix 重放与 16 PID 结束已核。见 [审核](AT011_native_stale_mechanism_review.md)。


AT012 于07:01:01.860503Z真实启动已独立核：45 当前接受源归档匹配；23 run 原生元数据全部 Complete/100%/refresh0，三个 policy dump 一致，stale=[] 如实。监督/leader/native 的 PID/start、nice5/CPU0–7已核；正在新图加载，actual apply/预算/G4仍待。[启动证据](AT012_content_recovery_start_review.json)。


AT012 于07:16:51.410992Z自然native1：当前直接child payload查询不完整，自动/显式2次apply均无成功，selected snapshot/G4未到；6 PID/start结束。恢复内容资格和22实际依赖读取仍成立，真实名字待同次fresh core OOC有界诊断。见[审核](AT012_payload_query_failure_review.md)。


用户服务器重启暂停：Root 实际转达“立即中断M003”，A007已实发收到并停止后继派发，仅核A006受控停止、PID/start、锁/观察器、部分输出和恢复起点；execution_state=paused，禁止自动恢复，等用户新的继续指令。


用户重启暂停最终审核完成：[AT013收尾](AT013_user_server_restart_pause_review.md)。07:44:47.297092Z native−15，监督/4PID已结束、锁无持有，工程observer0/sessiondrain，45源身份与3RTL及4组报告保全，原core仅stat/元数据核、不重读DCP。0B部分TSV、完整族数未得、G4未过；A007 paused，禁止自动恢复，等用户明确继续。


08:19用户明确“可以继续了”，A007独立审核恢复并已实发Root/A006。等待工程重启后来源有界回执和改进新诊断包；AT013部分0B表不作数据。恢复授权审阅见server_restart_resume_authority_review_20261018T0819.json。


重启后preflight已独立核：45源身份与151e4f11完全一致、3RTL/G2/小来源回执hash通过，新boot匹配；原core177165461B仅stat/原AT003元数据核，DCP内容与23/22/379重算归因A006。资源/锁预检无阻断，新诊断包仍待审核，G4未过。见server_restart_resume_preflight_review.json。
