# M003：验证流程提速与连续执行决定

2026-10-19，北京时间。主控负责；本决定落实用户“优化验证流程 太久了 这个速度没法接收”。适用于 SM017/E011 的诊断与综合后验证入口，不修改冻结 G2 原件、生产 RTL、物理策略、资源预算或最终验收。

## 已核实的问题

AT020 的 `read_state_sources.tcl` 对 80 个 URAM CLK 逐个执行完整 `get_nets -segments`、leaf-driver、primary-port 查询及完整名称导出。已审首条含 12,062 个唯一网段、1,755,346 B；AT019 的完整 80 项有同一 alias 集合。实际 80 个端点须覆盖，重复展开同一个连通组没有必要。源码冗余已证实，具体 API 时间占比尚未实测，不以静默推断挂起。

AT019 已独审完整地址/级联与有效读写模式，AT020 已独审闭合的 34 项 helper D 及首个 CLK 来源。此前 effective_memory v2 修复候选已通过独立 CPU 审核，尚未应用生产。这些依赖未变的证据复用并保留原运行身份，不冒称本轮重新测量，也不将旧 AT020 改为 80 项完成。

依据：
- [当前工程实态](../../project/E011_m003_joint_routability_implementation/experiment_status/summary.md)
- [AT019 全量独审](../../agent/A007/M003_SM015_SM017_review_20261018/AT019_terminal_and_complete_address_review.json)
- [AT020 首项时钟独审](../../agent/A007/M003_SM015_SM017_review_20261018/AT020_first_clock_source_review.json)
- [合并语义修复 v2](../../agent/A007/M003_SM015_SM017_review_20261018/effective_memory_snapshot_v2_candidate_review.json)

## 必须实现的有界优化

1. 实际枚举全部 80 个 CLK 端点，保留精确 cell/pin 与直接 net 身份，拒收缺项、重复、断接和未知对象。
2. 在当前打开设计内按实际连通性归组。对已知组使用直接 net 在完整 segments 集合中的成员证明；不可仅凭同名时钟、旧 hash 或抽样归组。
3. 每个不同连通组只查询一次完整 segments、实际 leaf drivers 与 primary ports；核来源唯一性、方向和目标时钟。80 个端点全部引用可核查的组证据。可保留旧字段，也可规范化为组表与引用，必须证明语义等价，不减验收字段。
4. 缓存仅存在于一次采集调用及同一打开设计/阶段。open/close、OPT、restore、源/图改变后重建，禁止跨阶段复用对象句柄或结论。先完成时钟关键路径优化，不扩展成无边界重构。
5. 同机制进入后续生产 snapshot，合并已有 effective_memory v2 的原生语义修复；按行/组流式写出，避免同时保留全量行和整包编码。保留原始 API 语义、失败栈、未知/缺失拒收，不以改名或常量填充迎合断言。
6. 增加实际查询次数与按类别的开始/结束计时，记录输入规模与完成范围。采用少量阶段/每组日志，避免逐 pin 同步刷盘。任何成本预测只作调度依据，不新增墙钟强停。

算法成本目标：端点核对为 N=80；完整连通组/来源查询随实际不同组数 K 增长，而不是 N。K=1 仅为当前同 core 的有证据预测，新入口须原生实测。A007 已从本机 2025.2 手册核到 top-net API；可在每组完整 segments 之外单独查询 canonical top net，验证其实际对象属于该组，再仅对该对象查询 primary ports。完整 segments 与 canonical 查询分别计数（可为 K+K），不得把二者混写为总共 K 次，也不得预报墙钟提速倍数。新 proof 查询保留 API 错误，避免 quiet 吞错；leaf driver 范围仍以每组完整集合为依据。

## 验证与执行流程

- A006 持续拥有 project、生产入口、实验三摘要和唯一 EDA，其他人不得并行修改这些文件；保留 M004/E010 等他人工作。A007 写自身独立审核与反例，不运行第二 EDA。主控维护本决定与目标/结果导航。最多三活跃、无后代，复用现有角色，不绑定其他会话。
- 先离线实现最小可切换入口，使用模拟 API 调用计数和正负例证明 N 个端点/K 个连通组、覆盖完整、错网/断网/双来源拒收、缓存失效以及输出语义等价；已有依赖未变测试引用原回执，只跑受影响范围。
- 同阶段普通修复按 research-agent/hardware-agent 当前阶段连续规则执行，A007 同步独审，集中交付阶段结论；不把每次源码变动、编译、启动再拆成独立人工放行门。实质覆盖/接口/架构变化仍回主控判断。真实 G4 结构、约束、预算、保护及 INIT/OPT/restore 要求不省略。
- 准备可直接启动的优化诊断和后继恢复入口，原生对照首先验证 direct-net 到连通组关系及来源，并给实际 API 次数/耗时；成功后连续完成生产修复、受影响回归、新图资格、严格 G4 及固定完整 place/physopt/route，不因普通修复再次等用户逐项批准。
- 旧运行源、输出、失败及新旧来源分别保全；原 AT003 外层失败、AT018 失败及 AT020 原监督退出码未知均不改写为成功。
- 旧 45 源是旧版冻结清单的事实，不是新验证工具的文件数上限。新共享库或启动 helper 可进入新清单，但必须登记全部实际消费依赖及受影响身份检查，保留旧清单，不能隐藏依赖或拼接版本。

## 当前运行与切换边界

原 AT020 尚正常计算；接管 guard 已恢复原资源阈值及唯一锁，历史监督证据缺口保留。当前不热改它正在消费的输入，不另开 EDA。用户此前明确“不要设置强行停止 只要进程还在正常继续”；本次要求优化没有明确给出结束 AT020 的单次例外。所有离线实现/等价验证/入口准备立即进行，不等旧 80 条完成。若准备完成时旧运行仍在，先给出具体可审结果，再确认本次受控切换例外；用户批准前不停止正常运行。不得反复询问已经批准的同一次动作。

CPU0–7/max8/nice5、树 RSS192GiB、MemAvailable48GiB持续30s、磁盘30GiB保护保持；无 GPU/bitstream/板卡/PPL/ACC。新监督与观察器实际身份见工程三摘要，不将文档 running 当作心跳。

## 本轮交付状态

已实际向 A006 委派实施、A007 委派并行独审。当前状态为 implementing，原生提速尚未测量，G4 与布局布线尚未开始；后续在本文件集中追加实际结果与切换决定。

## 实施与本次切换授权（2026-10-19 追加）

最小共享 collector、80CLK 原生入口、规范化证据检查器和启动器已实际实现。CPU spy 已验证 80 个实际别名端点、12,062 个组成员时：direct=80，完整 segments=1、canonical=1、leaf=1、ports=1；覆盖 19 个模拟原生拒收场景与 7 个序列化负例，6 个测试函数通过。该数据是离线 API 模拟计数，不是实际 Vivado 速度；最终候选与测试身份由工程回执保存，独审发现的常规边界修复持续更新同一工作集。

用户已明确答复 **“允许结束本次 AT020，切换优化版（推荐）”**。本次停止例外仅限当前 AT020，取代上节该次“待确认”状态，不扩展到未来正常运行。Root 已通过实际消息通知唯一 owner A006保全数据、核准归属进程后受控停止、核退出/锁并切换优化原生入口；A007独立只读核验。原监督丢失造成的退出码 UNKNOWN 继续保留，不把受控切换写作自然成功。

[本次明确授权](../../.research-agent/decision_inputs/M003_AT020_optimized_switch_authorized_20261019.json)。新运行必须有真实启动回执与进程身份后才记 running；原生性能、完整结构/预算和 G4 仍待验证。

### 已执行切换与真实启动

AT020 于 2026-10-19 00:40:19Z（北京时间08:40:19）按本次明确授权受控结束，4 个登记 PID/start 均退出，锁释放；保全 21/80 条完整 CLK、36,862,302 B、无残缺尾行。原 native 退出码 UNKNOWN 保持。

AT021 于 00:42:45Z（北京时间08:42:45）实际启动：supervisor152171/start6017183、native152267/start6017293，唯一 EDA 锁与原资源限制已核。最小诊断工程 CPU 6 函数通过，独立规范化10项及API-spy7项通过；当前仅新运行已启动，原生全80结果与耗时尚待。

[AT020受控收尾](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT020_fresh_core_state_source_semantics/evidence/user_authorized_switch_20261019/controlled_switch_stop_receipt.json) · [AT021真实启动](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT021_fresh_core_grouped_clock/evidence/actual_native_activation.json)。新诊断6源已冻结，production集成只在独立候选进行，不热改消费源。

### 原生兼容修复进展

AT021 载图后在 context 属性查询处自然失败；本机手册确认 current_design 返回名字，须先取得实际设计对象。AT022 已越过该处，但原生日志 Common17-736 证实 12,062 元素 collection 在字符串化排序时默认截成 500，随后触发成员守卫。原失败分别保留，未减弱成员证明。修复为先限界计数，再原生 foreach 逐对象生成普通列表，完整物化后去重并核精确成员；增加分条件失败详情。

AT023 于北京时间08:59实际启动同一完整80时钟诊断，新包与共享库均冻结；其真实覆盖/性能仍待。生产独立候选已补34个helper/C的共享查询，8项受影响测试通过，准备完整新来源清单和独立增量审核。原生运行源不热改，功能/时序/物理验收保持。

### 原生提速已验证：AT023

2026-10-19 01:04:53Z（北京时间09:04:53）AT023 自然 native0、监督完成、stop=null、无归属残留。独立审核核实80/80精确端点、1个连通组、12,062个唯一网段、canonical core_clk、唯一primary core_clk/IN、leaf为空，所有direct成员证明通过。实际 distinct direct net=1；此前CPU压力样例的80个不同direct aliases仅为离线覆盖，不冒充原生数据。

采集 call_begin 至 call_complete 为 **3,755 ms**，完整原生作业 **318.178 s（5分18秒）**；open_checkpoint日志单列 **4分49秒**。API实际计数/累计时间：direct 80/4ms，完整segments 1/219ms，NAME+CLASS 2/149ms，leaf 1/474ms，canonical 1/198ms，ports 1/113ms。完整segments和canonical各一次，不能混报为所有含segments选项的调用总共一次。

- [原生计数](../../project/hardware/vivado/reports/m003_E011_R002_AT023_fresh_core_grouped_clock_native_collection/api_counts.json)
- [原生阶段计时](../../project/hardware/vivado/reports/m003_E011_R002_AT023_fresh_core_grouped_clock_native_collection/api_trace.jsonl)
- [全80资格结果](../../project/hardware/vivado/reports/m003_E011_R002_AT023_fresh_core_grouped_clock_native_collection/grouped_clock_qualification.json)

该结果仅证明完整时钟取证的正确覆盖与效率；不冒称整个综合后验证、G4或布局布线只需3.755秒。生产候选已覆盖13120 payload/C、17 core/C、34 address/C及其34 helper/C复用、80 URAM/CLK与selected boundary的全部时钟调用点，8项受影响测试通过，独立13项decoder及48源闭包无实质阻断，工程正连续实际应用与验证。


### 正式入口已应用并继续执行：AT024

2026-10-19 01:06:27Z（北京时间09:06:27），工程实际应用共享连通组查询、effective_memory v2与流式snapshot。新48源manifest为`16f9523c2e4968a34abdce8d8e5c126476f206ce8c0f93ceec146799c0d9cf75`；共享库`01919f5e…`与AT023原生成功版本相同。原45源清单、6项被替换旧文件及原失败保全，G2和3份RTL未改。独立审核逐项核实48源与已审候选一致。

应用后实际受影响回归95项/38.021秒与33项/7.737秒全部通过；精确相同源码的8项group/stream测试（9.726秒）引用已完成回执，不冒称重测。测试fixture适配已独核，原非时钟失败守卫和其余测试语义保持。普通修复、编译、验证持续推进，不添加逐项批准。

AT024于01:10:47.982557Z（北京时间09:10:47）真实启动`recover-synth`，由独立会话的监督157933/start6185410管理；原生158026/start6185635，实际环境指向新入口与原新综合工程，194个归档来源中全部48个runtime身份已核。唯一EDA锁由157933持有，原CPU/内存/磁盘保护和正常无墙钟/静默强停保持。本次未重新综合；原AT003外层native1仍保留。

当前仅确认优化已进入正式运行，完整新图/snapshot/预算和G4未终验，布局布线未开始。后续沿原合同完成综合后恢复→严格INIT/OPT/restore→G4→固定完整place/physopt/route。AT020单次停止例外已经使用，不适用于AT024或后续正常进程。

- [实际生产应用](../../project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/grouped_connectivity_v1/production_candidate/application_evidence/application_receipt.json)
- [实际受影响回归](../../project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/grouped_connectivity_v1/production_candidate/application_evidence/applied_affected_regression_receipt.json)
- [应用身份独审](../../agent/A007/M003_SM015_SM017_review_20261018/actual_grouped_production48_source_application_increment.json)
- [回归与fixture独审](../../agent/A007/M003_SM015_SM017_review_20261018/actual_production_grouped_regression_and_fixture_review.json)
- [AT024实际启动与资源回执](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT024_grouped_stream_postreport_recovery/evidence/actual_native_activation.json)


### AT024自然失败与续接纠正（2026-10-19北京时间13:06核实）

原生`status.json`记录AT024于02:52:17.707235Z（北京时间10:52:17）自然native1结束，stop_reason=null、owned_survivors空、maxRSS21,741,862,912 B，3RTL未改；不存在正常进程强停。此后工程摘要仍为02:35的running，工程agent已结束、审核agent容量错误，修复未及时衔接。Root在本次用户进度查询中核对原始终态后纠正状态，并通过实际followup分别续接唯一owner A006和独立审核A007；A007已实际确认恢复，未替换模型或扩大额度。

失败栈为`M003 selected metadata boundary S count/duplicate mismatch: 0, expected 1`：snapshot_body在预期metadata层级查询addr_system_clear引脚为空。22项依赖读取与两次overlay实际应用已经完成，部分快照保留；该事实尚不能判断RTL设计有缺陷，也不能直接放宽端口资格断言。工程先根据实际图、选择器及冻结设计定位，普通入口修复与受影响回归按原授权连续执行。完整新图、资源预算、INIT/OPT/restore/G4和布局布线仍未完成；新尝试未启动前不记running。

补充证据保全边界：A007已指出正式入口测试适配时，最初3个fixture失败原输出被后续重定向覆盖，工程已将旧fixture重放标为LATER REPLAY；这是原始失败日志的归档缺口，不能声称该输出完整保全或将重放冒充原输出。已完成的最终128项PASS与实际源身份核验不因此改写。后续日志必须使用独立路径，避免覆盖。

- [AT024真实终态](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT024_grouped_stream_postreport_recovery/evidence/jobs/native_postreport/status.json)
- [AT024原生失败栈](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT024_grouped_stream_postreport_recovery/evidence/jobs/native_postreport/launcher.log)
- [测试失败输出来源澄清](../../project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/grouped_connectivity_v1/production_candidate/application_evidence/fixture_failure_log_provenance.json)


### AT025运行实态（2026-10-19北京时间13:37）

七个边界的独立实际源锚选择修复已应用，受影响7函数通过，未改RTL、未重综合。AT025于05:17:40.326247Z实际启动，48源manifest为dab87062fdb295c0c0dd4639cb8144b9fc05c58a5caae78b8c6bdfcbbbfd173c；194输入绑定和实际启动经A007独审。05:37:13Z资源记录中的原生274532/start7666943仍在，RSS约21.7GB，无status终态；最新日志正在全板open_run的约束处理，尚未抵达修复后的完整快照验收。离线新增NAME完整性防御未热改冻结源，本次真实导出须由已审checker核对全部源数量/方向/clock证据，不将离线通过作为原生通过。

A007现有只读观察处于活跃轮次，工程A006等待阶段事件以实际followup续接；不把文件状态当作持续运行保证。剩余依赖为完整snapshot/预算→冻结恢复综合产物→严格INIT/OPT/restore→实际G4→固定完整物理。

- [AT025实际启动](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT025_boundary_sources_postreport_recovery/evidence/actual_native_activation.json)
- [AT025启动独审](../../agent/A007/M003_SM015_SM017_review_20261018/AT025_actual_start_independent_review.json)


### AT025已越过原选择器失败点（北京时间14:50）

第二次overlay成功回执于06:37:08Z生成，两次实际应用均已成功。六个非clock源锚实际选中，原生segments计数S17/L9/R3/reset807/read1/write3，已独审；这些计数不代替最终NAME列表完整性。06:50:53Z新鲜资源采样仍有原生274532/start7666943，无终态；cells与endpoints流式部分产物于06:50:54持续写入。完整snapshot/源向量和clock证据/预算/G4待核，布局布线未开始。

- [工程阶段证据](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT025_boundary_sources_postreport_recovery/evidence/AT025_second_apply_and_six_source_selection_stage.json)
- [独立阶段审核](../../agent/A007/M003_SM015_SM017_review_20261018/AT025_second_apply_and_six_control_sources_independent_review.json)


### 复位语义修复与AT027（北京时间16:02核实）

AT025于07:13:04Z自然native1/nullstop/无残留结束，完整68,611,759B快照已生成。六源最终NAME向量、独立clock来源/12602组及调用成本已通过真实checker；唯一结构资格错误是34个helper CLR的alias集合不等于17个原core CLR。预算未执行，失败保持。

AT026于07:23:13Z启动限定freshcore 51 CLR及有界驱动锥查询，07:28:49Z自然native0结束并独审。实际三组LUT1 INIT1都接同一独立core_rst_n，51个端点全FDCE/INIT0、CLR pin_IS_INVERTED0；cell空属性保留。361/1/1 CLR和51端点与AT025逐相对映射通过，core root804与fulltop807的对应关系有原生证据。根因是独立复制反相器导致网络不同，原检查器的纯alias相等代理无法表示所要求的同复位行为。

Root接受在原合同内修正检查器为严格实际来源、函数、初值和引脚极性证明；这是已有数值/时钟复位合同下的验证实现修复，不放宽复位行为或验收覆盖。AT027必须在本次完整图中重新采到51项来源并通过同函数/独立根源检查，AT026仅提供修复依据，不能代替G4。

候选与受影响回归已独审；AT027于07:49:43.780807Z实际启动，48源manifest42dafce33f4727734dcf169b285a3decfcfa18d78d10f9a36463b4bea7c904d5，194绑定/源归档/进程身份/原资源保护通过，未修改RTL、未重新综合。08:02:29Z新鲜采样证明原生378139/start8579293仍在，尚无终态，日志处于整板网表/XDC载入。完整修正版snapshot/预算/G4及物理结果待。

- [复位补采及映射独审](../../agent/A007/M003_SM015_SM017_review_20261018/AT026_terminal_reset_semantics_and_mapping_independent_review.json)
- [AT027实际启动](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT027_reset_semantics_postreport_recovery/evidence/actual_native_activation.json)
- [AT027启动与最终应用独审](../../agent/A007/M003_SM015_SM017_review_20261018/AT027_actual_start_and_final_application_independent_review.json)


### 用户调整为每小时一次分析

用户明确要求停止持续盯项目进程，以降低token消耗，仅每小时分析一次。此要求取代前述持续agent轮询/每阶段立即followup机制，已有EDA作业与自动资源保护保持。A007已核准自身observer379620/start8592315后仅结束该只读观察器，session19318退出143、原进程身份消失；EDA和监督未触及。A006已收到同样的低频工作方式调整，只做一次管理收尾，随后结束活动轮次。

每次分析限定为最新摘要、实际终态/最新资源记录、新阶段或错误证据的一次有界检查；输出简短变化、原因和下一依赖后结束。不保持等待轮询，不反复读大表，不自动增加EDA、改运行源或检查范围。原mission未暂停，既有架构/资源/正常无墙钟强停规则保持。

已检索当前工具，未提供本地或当前会话的automation_update/等效定时入口；现有Page-controller自动化不适用于本地工程。因此小时频率作为执行规则已保存，自动唤醒尚未配置，不能承诺无人触发也会准时检查。官方入口是应用Scheduled中的本地项目定时任务，规则为每小时一次、Asia/Shanghai、使用本项目目录；不以常驻agent或额外CLI轮询替代。

[用户频率决定](../../.research-agent/decision_inputs/M003_hourly_analysis_policy_20261019.json) · [观察器退出回执](../../agent/A007/M003_SM015_SM017_review_20261018/AT027_hourly_analysis_observer_stop_closure.json)


### AT027工具侧成功（北京时间18:43一次性分析）

用户本次询问触发一次有界读取，未恢复观察器/唤醒工程/启动新EDA。原status记录AT027于09:49:43.849307Z自然completed/native0/nullstop/survivors空，core RTL unchanged。原生日志给出M003_POSTREPORT_QUALIFICATION_COMPLETED；m003_qualification_synth.json实际passed=true/errors=[]，same_stage_budget也passed=true/errors=[]，两次实际overlay通过。资源增量LUT111/FF34/CARRY8 4，BRAM/URAM/DSP不增。

这是原生综合后验证工具侧通过，不代替尚未完成的全量结果独审、来源/进程最终收尾、恢复综合产物冻结、严格INIT/OPT/restore与G4。布局布线未开始，原AT003/AT025失败事实不改写。

- [原生终态](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT027_reset_semantics_postreport_recovery/evidence/jobs/native_postreport/status.json)
- [结构资格](../../project/hardware/vivado/reports/m003_E011_R002_AT027_reset_semantics_postreport_recovery/m003_qualification_synth.json)
- [资源预算](../../project/hardware/vivado/reports/m003_E011_R002_AT027_reset_semantics_postreport_recovery/m003_same_stage_budget.json)
- [完成回执](../../project/hardware/vivado/reports/m003_E011_R002_AT027_reset_semantics_postreport_recovery/M003_postreport_qualification_complete.json)


### 用户指定新6.1-sol工程代理实际执行

用户明确“创建6.1-sol快速去进行验证 有问题再告知”。Root实际spawn `/root/m003_sol61_verification`，显式请求gpt-6.1-sol/xhigh（xhigh沿用已有工程策略）；工具返回该真实task，运行配置未另行独核。原A006已收到只读交接消息，新代理成为本轮project和唯一EDA owner，A007通过实际followup接续一次AT027最终独审。最多3活跃含Root，无后代，无长期会话重新绑定。

工作从AT027真实native0、结构及预算PASS接续：限定终态/来源/结果复核→冻结恢复综合产物→新原生INIT/OPT/debug及preplace资格→实际包独立G4→按原合同恢复和完整物理依赖。普通修复/受影响回归无需逐项用户批准；真实阶段依赖不能省略。该指令明确恢复实际执行，取代此前当轮分析-only限制；不恢复高频模型轮询或observer。工程原生作业及机器资源保护可持续，正常进程仍无墙钟/静默强停。仅实质问题或最终结果向用户报告，Root不保持常驻轮询。当前工具无自动小时唤醒能力的限制不变。

[新代理实际创建与执行记录](../../.research-agent/decision_inputs/M003_sol61_verification_execution_20261019.json)


### AT028初始化后属性检查失败（北京时间20:39一次性实查）

AT028于11:56:29.726006Z自然native1/nullstop/owned_survivors空结束，3RTL未改。原生link_design成功，init.dcp及初始化后的utilization/timing/DRC/CDC等报告已生成；在m002_post init的m003::snapshot内，require_project报“M003 overlay must be global implementation-only LATE TCL”。显式OPT未开始，G4/布局布线未到。

该失败不推翻已完成AT027综合资格/预算/独审/冻结，也不能在未核实际属性前认定只是误报。Root已实际followup A018唯一owner：保全终态与源/树锁，查原source project和native INIT工程上下文中overlay的FILE_TYPE/PROCESSING_ORDER/USED_IN/SCOPE等实际差异，保留guard意义，优先利用现有DCP/导出/driver证据；常规修复和受影响回归后新尝试连续推进。若复用INIT检查点必须如实标记继承且证明来源/有效约束，不伪称重跑。仍单EDA/原保护、正常无墙钟静默强停，不启观察器或模型常驻等待。

- [AT028原生终态](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT028_native_init_opt_preplace/evidence/jobs/native_pre_place/status.json)
- [失败原始日志](../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT028_native_init_opt_preplace/evidence/jobs/native_pre_place/launcher.log)


### 持续执行替代“启动交付即结束”

用户明确要求高效长运行而不再反复追问。Root实际followup A018保持连续工程任务，AT029及后续原生作业由机器等待终态事件，模型仅在结果到达/需要修复/阶段独审时工作；Root保持本轮任务接收必要结果并调度A007实际G4独审。普通错误按原授权修复、受影响回归、重试，合格后衔接恢复检查和固定完整place/physopt/route。禁止重复启动AT029、正常强停、伪造G4或以恢复检查代替物理验收。

该机制不等于外部定时任务已配置；现有工具仍无可用本地小时调度入口。执行期间采用事件等待和按小时有界分析，不每15秒模型轮询、不反复读大表、不以agent“启动交付completed”留下无人续接。当前等待启动回执由A018提供后再记实际生效。有实质阻塞、合同决策或最终结果才通知用户。


### 实际G4通过并衔接R003（2026-10-20）

A007集中独审对真实AT035 package94e3f335给no_blocker=true，Root实际读原审计/门并核hash，接受当前包作为已授权固定完整物理的入场证据。实际debug命令Tcl0、完整POST/preplace合格；整次AT035在完成包后重复close_project造成outer1，原失败保留，不伪写整体native0。现有pre_place_evidence严格要求实际命令/POST/约束/覆盖/来源/DCP身份而非外层统一0，独立审核限定此包适用，无需原样重跑已完成整阶段。

Root已将真实A007-owned门及review身份传A018：原门不改字节安装，实际过原package/source_review检查，独立新report完成全准备后新R003单EDA执行restore→固定place→physopt→route，终态事件自动续接，不再等待用户追问或新增批准。物理v2 package0e6866cf冻结。正式reset/CDC/IO、最终route/全时钟/原余量和mission均未因G4关闭；G2既有合法结构/约束下负时序诊断route授权沿用。

[Root精确包入场决定](../../.research-agent/decision_inputs/M003_G4_accept_physical_start_20261020.json) · [实际独审](../../agent/A007/M003_SM015_SM017_review_20261018/AT035_actual_G4_consolidated_independent_review_20261020.json)
