# 当前闭合范围（2026-10-16）

本轮工程执行及证据收尾已结束：实际place0、独立physopt0/完整POST/父链通过；R003/AT001原生route19065秒后自然1，Phase9合法布通FAIL（245279 node overlaps/248289 signals拥塞失败），native/worker/manager/driver均1且无遗留进程，单EDA锁实查释放。未取得合法route DCP、独立route_status、正式routed timing/完整POST。目标未达成，方法普遍性inconclusive；不追加策略/新AT。[工程总报告](../experiment_results/engineering_final_report_2026-10-16.md)、[最终原始证据绑定](../experiment_results/runs/R003/attempts/AT001_full_route/route_terminal_completion_facts.json)。

当前无活动EDA。以下为实际执行协议及其保留历史：固定wall限制已由用户持续执行补充取消，原始旧段落不视为当前政策；所有失败与成功父点保持原身份。代码/源未在运行中热改。

## 已执行协议与历史补充

# 生效恢复方案（15:35:29Z已启动）

R001/AT002最终150项CPU PASS并安装5文件；R002/AT001原place命令成功/原POST自然1保留。新R002/AT002从closed place SHA375914…恢复，经fresh live guard后重新原生完整place POST，再独立physopt；不重跑place/OPT/debug。只允许四个实际AUX双源cone的base或ready最后级代表，精确8行和其他tuple/实际结构/原语/扇出约束不放宽；正式reset/CDC安全OPEN。112项原报告/source闭合manifest独立核验，新stage_inputs仅绑定manifest和completion，避免旧/新同名代码误归档；跨进程分类排序固定。

新实际启动器run_m002_no_wall.py明确验证用户持续执行补充SHA17acf…，stage/global timeout均null，不调用旧budget函数，不按无输出计时终止；原E002旧默认及E003启动历史不改。当前单EDA/CPU0–7/max8/nice5、RSS192GiB/MemAvailable48GiB持续30s/disk30GiB不变。新physopt父链成功后driver自动R003 route并沿用同无wall政策。以下原固定wall段落仅为保留启动历史，已被本段及持续执行补充覆盖。

> 当前优先指令（2026-10-15追加）：[持续执行补充](../../../mission/M002_ddr_separation_and_timing_recovery/full_implementation_continuation_2026-10-15.md)取消E003当前及后续固定时长强停。12:32:57Z实际接管生效：新watchdog3687878、旧supervisor3677862仅被暂停持锁，worker/Vivado原PID连续，资源保护保留。原12h/24h仅为保留启动历史，已非生效停止政策；未改冻结设计/生产脚本。详见R002/AT001/supervision_handoff实际回执。

# E003：完整implementation工程协议

当前授权：SM007，[完整implementation合同](../../../mission/M002_ddr_separation_and_timing_recovery/full_implementation_contract_2026-10-15.md)，SHA256 `8461a1ff702b33f95cd03100086d2c1bb58ae590430598adb59818ffa2c0794b`。用户指令：“进行一次完整的implementation”。工程A006唯一EDA执行；A007只读审核；主控拥有共享摘要/索引。E002全部失败保留。

## 输入、平台与控制变量

VCU118/xcvu9p-flga2104-2L-e，Vivado2025.2，top=scalellm_vcu118_f05_bd_wrapper。工程 `project/hardware/vivado/project/m002_E002_R001_AT001_fresh`；E002/R001/AT002正式综合339输入、45 DCP路径及原始source/constraint/IP哈希逐项验证，manifest SHA `1dc14fef9dbe62ba0a55a7eebef3a5c0a277574c674e2d3310d5d69e10f711d3`。

恢复E002/R003/AT008的完整debug/pre_place：`project/hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_materialized.dcp`，397261751B，SHA `e58d89707d21be85a3059a9ba7096651b6a277c125e831a47ebc7ec4f98fc44e`。原pre_place SHA `b6a1fc8785afa7e4963c79577e44a2c5a99d5ecdd3678a02c8e6f5f8588c1c5b`。原完整POST及终态闭包逐项校验；OPT/debug成功receipt保留原路径，绝不伪装为本次执行。AT009无closed place点，不能继承其部分布局。

本轮不改变RTL/XDC/IP、时钟、接口、数值合同或默认物理策略，不搜索seed。旧只静态审核missing-physical候选保持未安装。无bitstream、板卡、GPU/PPL/ACC。setup/hold/PW负值可进入诊断route，时序与执行分开。

## 批次与顺序

- R001/AT001：只做CPU入口/profile/预算/授权/全布通判据回归、真实339/45与AT008源资格验证、冻结源码并安装。原完整POST解析器与Tcl未变，引用E002/AT012实际完整hook replay；不重新生成原报告。
- R002/AT001：显式 `--execution-profile m002_full_implementation`；`run_managed_eda.py place` 加项目、合成report/attempt、AT008 `--pre-place-report`。真正open_checkpoint后live sanity、内部clock/constraint与原生DRC；完整place成功即保存place.dcp再POST，继续独立phys_opt_design，保存physopt.dcp再完整POST。原OPT/debug不重执行。
- R003/AT001：仅真实成功R002父链被独立检查通过后，以同一profile及 `--place-report` 自动route，保存route.dcp与完整POST。若报告失败已产生完整物理点，仅按真实缺口最小适配补阶段；不重新运行已成功命令。

## 预算及监督

显式profile固定合同SHA及指令并绑定manager command/attempt/report。E002默认7200s未变。本轮place+physopt+恢复+POST累计43200s，route+恢复+POST累计43200s；读取同阶段所有真实闭合attempt的command.started至status.ended累计。未闭合attempt或幸存进程不视为空闲额度；失败准备也消耗阶段额度。首成功Vivado Popen后的actual_eda_started绑定不可重置anchor，总86400s包含修复间隙。每次只获所属阶段余额与全局余额的较小值，真实监督同时执行阶段monotonic和全局UTC期限；effective_budget落盘。

唯一lane锁，CPU0–7，max8线程/nice5，进程树RSS≤192GiB，MemAvailable≥48GiB（持续30s低值停止），disk≥30GiB。只清理本人PID身份/子进程组，不影响他项。

## 验收、独立预期与采集

129个受影响CPU检查（14个E003新检查、13恢复、6隔离及96原物理回归），无EDA。校验预算重试不可重置、修复间隙计入全局、env/marker单独不可授权、变合同拒绝、旧默认不变、全布通严格判据。

实际执行保存命令/授权、工具与源archive/input manifests、UTC起止/退出、PID及资源样本、日志、原生命令receipt、闭合DCP、完整POST、来源链。最终route必须routable>0、fully_routed==routable，unrouted/partially_routed/routing_errors全部0；exit0和文件存在不足以声称完整完成。各阶段WNS/TNS/WHS/THS/WPWS/TPWS及端点、路径逻辑/布线/skew、SLR资源/拥塞与DRC按实际报告记录。新物理CDC/reset图按实际新证据评判；正式reset/CDC/事务安全保持OPEN。

重要启动/DCP/失败/终态实际消息通知主控；无未经配置的后台实时监控承诺。所有原始尝试不覆盖。
