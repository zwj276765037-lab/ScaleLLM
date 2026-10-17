> 当前E003工程终态（2026-10-16）：place/独立physopt及新完整POST/成功父链成立；本次实际route17:27:55–22:45:40 UTC、19065秒/Tcl1，22:45:51.707572 UTC自然终态，native/worker/manager/driver1、stop null、六原身份退出且单EDA锁释放。Phase8连通摘要0失败不覆盖Phase9非法布线：245279 node overlaps/248289 signals拥塞失败。无合法route/失败DCP、独立route_status、正式routed timing/完整POST；最后完整父点仍physopt（正式pre-route WNS−1.290/WHS−.620ns，FAIL）。当前无EDA，不新增策略/尝试，正式安全OPEN。[总报告](../../E003_m002_full_implementation/experiment_results/engineering_final_report_2026-10-16.md)、[最终绑定facts](../../E003_m002_full_implementation/experiment_results/runs/R003/attempts/AT001_full_route/route_terminal_completion_facts.json)。以下均为此前过程/历史。

> 当前物理交接（17:20Z）：R002/AT002完整新place POST、独立physopt0/closed DCP/完整POST及真实成功父链全部闭合，worker/native/supervisor0、无13原身份；[terminal_facts](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/terminal_facts.json)。R003/AT001已实际启动controller并恢复源physopt点，route_design尚未开始；[实际新监督](../../E003_m002_full_implementation/experiment_results/runs/R003/attempts/AT001_full_route/startup_no_wall_facts.json)。无wall/资源保护继续。WNS−1.290/WHS−.620ns，timing仍FAIL；正式安全OPEN。下列未闭合状态为此前过程。

> 最新独立physopt命令（16:38:12Z）：native0，实际16:19:46Z开始、1106s；closed physopt.dcp已保存，568389035B，SHA c6944eee…，全25 ZIP成员CRC/平台身份PASS。见[原生命令事实](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/physopt_native_command_facts.json)、[完整DCP事实](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/physopt_checkpoint_facts.json)。正式physopt时序已生成：WNS−1.290/TNS−762.165/setup失败980（place为−1.819/−818.651/1014）；WHS−.620/THS−2150.556/hold失败33141不变；WPWS/TPWS/相关失败0。见[正式时序事实](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/physopt_timing_facts.json)，均为pre-route估计互连，仍FAIL。完整physopt POST尚在采集、route父链尚未成立；无wall/资源保护继续。以下为此前过程。

> 当前（E003/AT002，16:20Z观测）：完整新原生place POST已通过（place_result1/eligible1、gate[]、current结构/fanout/14原语/8CDC窄分类，新未知0），日志已实际进入独立phys_opt_design。新place序列化DCP SHA f2ba76…、579812151B，全25 member CRC/平台身份PASS；新正式时序仍WNS−1.819/WHS−.620ns、FAIL。独立physopt未完成，route父链尚未成立。原place/OPT/debug不重跑，原失败保留；无wall/资源保护继续，正式reset/CDC安全OPEN。[阶段事实/64文件闭合](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt/completed_place_POST_facts.json)。以下均为此前过程或历史。

> 当前（E003新AT002，15:35:29Z）：窄CDC分类/合法closed-place恢复/no-wall启动器已通过150项CPU与真实worker入口核验，5文件安装。manager3866162/worker3866163、Vivado launch3866502/原生3866592已实际启动。新AT先fresh guard，再完整原生place POST和独立physopt；原place成功不重跑，原POST失败保留。当前尚未取得新POST/physopt结果，后继同无wall route已配置，资源保护保留。[核验与安装](../../E003_m002_full_implementation/experiment_results/runs/R001/attempts/AT002_placed_CDC_recovery_cpu/report.md)。以下无EDA与旧进行中状态是历史。

> 最新终态（E003/AT001，15:08:08Z）：place native0/closed DCP保留，POST因两个DDR1 AUX代表源选择差异而native1，physopt/route尚未执行。真实新/旧8组有界结构完全相同，新14原语export/模型及当前结构/fanout资格通过。当前无EDA，工程按授权准备窄分类修复和从closed place点补缺阶段；不重跑place，不恢复wall停止。[终态/双资源流](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/terminal_facts.json)。此前进行中状态为历史。

> 最新实际物理点（E003，2026-10-15T14:40Z核）：place native0，7295s；closed place.dcp 579080094B，SHA `37591435c8f95383a0910978b986c035a102c762b24b69b76e59b63d49e905f7`，全ZIP CRC/平台身份通过。完整POST尚在进行，独立physopt/route未开始；过程WNS−1.858与高拥塞46-14风险不替代正式时序/可布通结果。见[E003 place事实](../../E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_checkpoint_facts.json)。

> 当前优先指令（2026-10-15追加）：[持续执行补充](../../../mission/M002_ddr_separation_and_timing_recovery/full_implementation_continuation_2026-10-15.md)取消E003当前及后续固定时长强停。12:32:57Z实际接管生效：新watchdog3687878、旧supervisor3677862仅被暂停持锁，worker/Vivado原PID连续，资源保护保留。原12h/24h仅为保留启动历史，已非生效停止政策；未改冻结设计/生产脚本。详见R002/AT001/supervision_handoff实际回执。

# E003 / SM007 当前完整implementation

2026-10-15：新授权已按合同落实。R001/AT001的129项CPU回归、真实339输入/45 DCP及AT008完整pre_place源资格PASS；5文件已验证安装，RTL/XDC/Tcl/策略不变。R002/AT001 manager已实际启动，恢复AT008后执行完整place/独立physopt，成功父链后自动route。实际Vivado起算及期限以actual_eda_started/effective_budget为准；当前未获得新物理完成结果。

证据：[E003协议](../../../project/E003_m002_full_implementation/experiment_source/protocol.md)、[R001报告](../../../project/E003_m002_full_implementation/experiment_results/runs/R001/attempts/AT001_full_implementation_profile_cpu/report.md)。E002原失败为历史保留；不代表本轮停止边界。

## 以下为E002及更早历史

# 当前硬件分阶段结果

适用平台：VCU118 xcvu9p-flga2104-2L-e，Vivado2025.2。目标core100MHz、DDR UI200/200MHz；不是已达成频率或性能。输入与数值权威见同目录design.md、m002_dedicated_ddr.md。

| 阶段 | 真实状态与范围 | 证据 |
| --- | --- | --- |
| E001功能/接口 | 四套定向XSim及完整board RTL展开通过；完整32层数值未覆盖 | E001/R002、R003 |
| E001 BD | validate退出0；4条地址别名critical及既存reset warning保留 | E001/R003/AT007 |
| E002 fresh create | execution completed，exit0，无遗留进程 | E002/R001/AT001 |
| E002正式综合 | execution completed，2026-10-15 02:44:24 UTC结束；native/overall exit0，114.279分钟，峰值受管RSS27.06GiB，无遗留进程。timing FAIL、coverage OPEN | [R001原终态](../../E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/synthesis_stage_facts.json) |
| E002物理入口CPU | AT011历史102项通过；AT012新增13恢复+6managed实际通过，96legacy复用。完整真实debug POST/AT008父链PASS；CPU通过不替代物理结果 | [R002 AT012](../../E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/attempts/AT012_post_debug_pre_place_recovery_cpu/status.json) |
| E002布局/布线 | AT008完整debug/pre_place后两小时中止；AT009同DCP恢复fresh guard通过、前置实减31m21.1s，11:41:11Z再次按原2h上限124/native−15停止、无survivors。无place/physopt成功receipt/DCP；不再重复place，R004 route NOT_RUN，无活动EDA | [工程总报告](../../E002_m002_synthesis_and_physical_baseline/experiment_results/engineering_final_report_2026-10-15.md) |
| bitstream/板卡 | NOT_RUN，本轮未授权 | implementation_contract_2026-10-15.md |

完整board正式综合资源：LUT841576（71.18%）、FF1029313（43.53%）、DSP5451（79.69%）、BRAM945 tiles（43.75%）、URAM752（78.33%）。这是全板linked report，资源总量未超不代表可布局。原报告：[utilization](../vivado/reports/m002_E002_R001_AT002_fresh_synth/utilization_post_synth.rpt)。

未布局时序估计：WNS+0.904ns、TNS0、setup失败0；WHS−0.814ns、THS−49355.641ns、hold失败1000183；WPWS−0.012ns、TPWS−0.037ns、PW/skew失败5。最差PW类为PCIe Max Skew；最终判定FAIL。原报告：[timing](../vivado/reports/m002_E002_R001_AT002_fresh_synth/timing_post_synth.rpt)。

530缺时钟和554未约束内部端点均在两MIG调试域；唯一dbg_hub_CV占位需由project implementation物化。CDC-10 Critical6、CDC-15 Warning6198、DRC Warning15927、29条生产RTL reset告警、两条vendor XPM端点查询告警和XDC puts critical保留，未因来源相同而豁免。真实INIT/OPT将记录有界网表结构、时钟、约束元数据与端点，真实OPT之后须显式implement_debug_core，再由独立debug_materialized/pre_place全设计检查通过才继续place。

没有本次拥塞、placement/route完成率或板级指标；不以历史native025或目标数填充。CPU脚本测试和综合生成完成均不替代物理/功能签核。

AT004真实OPT资源：LUT828255（70.06%）、FF1021363（43.20%）、BRAM941（43.56%）、URAM752（78.33%）、DSP5451（79.69%）。[实际命令/身份与限制](../../E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/opt_command_facts.json)。OPT自动实现debug，额外显式调用按原生顺序保留；未布局时序不作签核。

AT005同OPT重取timing/utilization与AT004完全一致：WNS+0.904/TNS0/setup0；WHS−0.814/THS−48989.652/hold992151；WPWS−0.012/TPWS−0.037/PW-skew5，timing FAIL。新CDC总Critical8（CDC10×6、CDC11×2），相对综合严格身份变化4；不能用计数相同代替来源相同。AT006限定诊断分类不关闭reset/CDC/release/事务安全。


AT012恢复入口CPU：新增13恢复+6managed重新执行PASS，96legacy复用AT011；真实AT008完整debug POST组合门及恢复父链PASS。五脚本安装见[R002 AT012](../../E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/attempts/AT012_post_debug_pre_place_recovery_cpu/report.md)。AT009只继承完整原POST，新的live guard/DRC已实际通过；AT009原2h终态124，无完整物理点，place链已停止，未取得物理成功或时序收敛。

AT009阶段终态：资源记录6个PID/start_ticks及独立supervisor共7身份均不在；五live脚本与运行冻结源一致。最后原生完成4.1.1.2 BUFG Replication，停于4.1.1.3；中间Estimated WNS−1.884/TNS−1349.388不是完整placed/route报告。Place30-1229仅100可见样本/抑制；两DDR1 BUFCE_ROW cap4无单位；BUFG10候选全因placement/routing conflicts跳过，不是route DRC失败。原始身份见[AT009终态](../../E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)。未执行的续接候选仅留档，未安装、未回归或启用；本轮无后续EDA。
