# E003：阶段结果

129项CPU入口验证及实际339综合输入/45 DCP来源检查通过，5份生产/测试文件安装身份已核。复用原完整AT008 debug/pre_place，RTL/XDC/算法/时钟未改。当前及后继阶段按用户补充取消固定墙钟强停。

本轮实际Vivado于12:22:11 UTC启动，fresh恢复检查通过；place_design于14:36:01 UTC真实完成，native Tcl0、耗时7295秒（2小时1分35秒）。closed place.dcp为579080094 bytes，SHA256 `37591435c8f95383a0910978b986c035a102c762b24b69b76e59b63d49e905f7`；工程全包CRC/身份及稳定性通过，主控独立核3项小证据链接。[布局事实](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_checkpoint_facts.json)。

正式placed时序仍FAIL：WNS−1.819ns/TNS−818.651ns，1014个setup失败端点；WHS−0.620ns/THS−2150.556ns，33141个hold失败端点；WPWS/TPWS均0、该栏失败0。A007核最差setup在PCIe→XDMA；core100MHz本域WNS−0.317ns、28个setup失败端点。独立bus-skew摘要94项均非负，最小+3.015ns；不关闭正式reset/CDC安全。[正式时序事实](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_timing_facts.json)、[原报告身份](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_physical_reports_facts.json)、[独立审核§4](runs/R004/architecture_review.md)。

正式资源LUT68.93%、CLB站点占用99.11%，不能混同两种指标。拥塞12个方向/类别组合均报告至Level6，多个热点局部URAM/RAMB或DSP100%；48行窗口有嵌套/重叠，不是48个独立失败。top32跨SLR高扇出网中4条与BUFG优化跳过名单精确重合，实际为SLR0驱动、SLR0/1两侧大量负载，涉及MLP控制；这提供布局/高扇出风险线索，尚未证明全局最差时序或最终路由根因。

15:08:08 UTC place POST实际因 `critical_CDC: new/unclassified critical CDC path` 退出1。Critical总数仍8；精确差异仅DDR1两个AUX目标的报告源由ready末级改为base_reset末级，clock pair/目标及其余6项不变。当前reset_structure和fanout均qualified，唯一gate问题为新CDC tuple未获分类；仍需核实际组合锥，不能只按数量相同豁免。[实际CDC差异](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_place_CDC_delta.json)。

无固定时限或资源终止：新监督真实取得worker1，确认子树终态后才结束暂停的旧supervisor；旧manager管理性−9与Vivado/worker1分开。15:08:16状态无survivors；主控15:10:49独立复算两资源源132+1837样本，峰值34706485248 bytes及内存/磁盘低值与status一致，全部9个tracked身份和两supervisor均无对应PID/start_ticks幸存。[真实终态](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/status.json)。

AT001原失败和完整布局点/正式报告保留，独立physopt/route未运行。工程按既有授权做窄CDC核查、受影响验证与合法placed恢复，继续补POST→独立physopt→route；不重跑成功place，不热改或放宽算法/接口/时钟/安全验收。

后继修复已实际验证并启动：R001/AT002最终150项CPU PASS（129既有+21新增），真实原CDC/结构重放及worker准备/后继archive预检通过；跨进程代表源排序和新旧同名脚本身份问题已修复并验证。5份生产/测试文件15:34:51 UTC在空闲lane锁下安装，主控独立核安装/验证版5/5一致。[测试](runs/R001/attempts/AT002_placed_CDC_recovery_cpu/cpu_tests_final.log)、[安装](runs/R001/attempts/AT002_placed_CDC_recovery_cpu/installation.json)、[真实入口预检](runs/R001/attempts/AT002_placed_CDC_recovery_cpu/actual_worker_entry_preflight.json)。

R002/AT002实际Vivado于15:35:29.081055 UTC启动，launch PID3866502，manager3866162/worker3866163，当前从原closed place DCP恢复。先fresh live guard，再新原生完整place POST、独立physopt及成功父链后自动route；无place/OPT/debug重执行。启动时尚未取得本次fresh guard/完整POST/独立physopt成功。新无wall监管从启动即timeout/global_deadline=null，原资源保护保持。[实际启动](runs/R002/attempts/AT002_closed_place_POST_physopt/actual_eda_started.json)、[真实命令与监管](runs/R002/attempts/AT002_closed_place_POST_physopt/command.json)。

16:19:46 UTC，本次完整原生place POST已真实通过：completed1/diagnostic_eligible1、blackboxes0、COMPLETE_INTERNAL、gate_issues=[]；实际reset结构/fanout合格，8条既有CDC按真实新图分类、新未分类0，正式安全OPEN。新DCP为579812151 bytes、SHA `f2ba76edc720739c5562a110c3f82056007e6c5bcb9942a8f7c01a0b517648b9`，属于恢复原完成布局后的本次序列化；原place命令明确为历史继承，没有重跑place/OPT/debug。工程冻结64个完整POST文件，主控核阶段facts所引6项小证据身份一致。[完整POST事实](runs/R002/attempts/AT002_closed_place_POST_physopt/completed_place_POST_facts.json)。

原生日志在POST成功marker后实际执行独立phys_opt_design，当时物理优化刚开始，其后续结果见下。本次fresh正式placed时序与原值完全相同，FAIL保留；完整实现和时序/安全签核仍按后继真实结果判断。

独立phys_opt_design已于16:38:12 UTC实际native0完成，耗时1106秒（18分26秒）。closed physopt.dcp为568389035 bytes、SHA `c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91`，工程全25 ZIP member CRC/平台身份通过。正式优化后时序WNS−1.290/TNS−762.165ns，980个setup失败；较placed分别改善0.529ns/56.486ns、少34个失败端点。WHS−0.620/THS−2150.556ns及33141个hold失败不变，PW/skew栏目0。时序仍FAIL，互连延迟仍为pre-route估计。当前完整physopt POST尚在执行，route未运行。[原生命令](runs/R002/attempts/AT002_closed_place_POST_physopt/physopt_native_command_facts.json)、[完整DCP](runs/R002/attempts/AT002_closed_place_POST_physopt/physopt_checkpoint_facts.json)、[正式时序](runs/R002/attempts/AT002_closed_place_POST_physopt/physopt_timing_facts.json)。

17:16:53 UTC工程冻结完整physopt POST事实：completed1/diagnostic_eligible1、BB0、COMPLETE_INTERNAL、gate_issues=[]；当前实际reset结构/fanout合格，14份primitive exports/models身份核实，8条Critical CDC限定分类、新未分类0。55份阶段文件形成封闭清单；主控独立核命令、结果、integrity、manifest、DCP CRC事实、冻结日志及fresh place父点共7项小证据身份一致。原生日志严格place POST→独立physopt→physopt POST，时序FAIL和正式安全OPEN保留。此时worker/supervisor终态及route父链封闭尚在进行，未宣称route已启动。[完整physopt POST](runs/R002/attempts/AT002_closed_place_POST_physopt/completed_physopt_POST_facts.json)。

A007进一步核得core100MHz WNS−0.317→0.000ns、setup28→0（仅报告精度下零裕量），DDR1 UI−0.358→+0.089ns、setup4→0。PCIe→XDMA仍主导，top32 setup均落该方向，估计布线延迟占约84.7–86.0%。physopt中重报的placer-final拥塞窗口与fresh place相同，12方向/类别组合仍至Level6；这是布局拥塞报告，非新路由测量。独立bus-skew94项均非负，最小+3.015ns；PW无违例条目。当前完整布线和正式安全签核仍待实际结果。[独立审核§6](runs/R004/architecture_review.md)。


---
Published: 2026-10-15T17:18:14.236082+00:00
Publication: Pa37c637ba11c44c68c87d827d07b11d7
