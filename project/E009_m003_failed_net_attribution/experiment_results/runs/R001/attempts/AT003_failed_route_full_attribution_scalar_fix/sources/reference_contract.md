# M003：联合可布线改造与完整实现验收

创建日期：2026-10-18（北京时间）。负责人：项目主控与架构评判。优先级：P0。

**用户要求：明确需要修改什么，尽量一次集中修改完毕，并“定义成完整详细的 mission”。** 本合同将此前[联合修改方案](../M002_ddr_separation_and_timing_recovery/joint_routability_change_plan_2026-10-18.md)升级为可执行、可分阶段审核的完整任务。M003承接M002的现有架构、生产代码和失败证据，不迁移代码，不将M002标记为成功。

当前 `execution_state: planned`，`verdict: unassessed`；合同已定义，具体设计尚未冻结，工程尚未启动。本轮直接交付是mission定义，登记不代表启动RTL修改、仿真、综合或implementation。此前优化和完整实现授权保持，后续按本合同依赖推进，不增加逐项用户批准门。导航依赖M002表示承接架构和E008已收尾证据，不要求M002先成功布通；否则会形成目标循环。

## 1. 目标、交付和“一次集中改完”

在VCU118 / xcvu9p-flga2104-2L-e、Vivado 2025.2、core 100 MHz、双DDR UI 200 MHz的现有设计上，完成一个**真实改变拥堵连接、保持功能与周期合同、可复现的RTL＋物理约束＋验证入口联合版本**，由新综合进入完整place→physopt→route，以最终合法路由、时序和安全覆盖分别验收。

交付物：

1. 完整失败网清单、可核对的模块×区域归因、选型需要的端点证据。
2. 四张设计冻结表、候选纳入/排除决定、具体文件差异及物理策略。
3. 同一版本的RTL、正式生效的物理overlay、保护/来源检查与配套测试。
4. 位精确和逐周期功能回归、新综合结构/资源报告、完整实现及验收材料。
5. 无论成功或失败都可追溯的输入身份、运行原证据、阶段结论和进程/锁收尾。

“一次集中改完”是**在下一轮完整implementation前完成选定改动的集成、功能修复、约束适配和新综合核验**。综合发现副本被合并、对象缺失等问题，在实现前修复并重新冻结，每次实际尝试保留证据。不在长实现中夹带热修改，不把不同版本结果拼成成功版本；不承诺第一轮route必过，也不因“一次”跳过验证或加入无依据改动。

## 2. 当前依据与证据边界

权威入口：[E008结果](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)、[E008状态](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)、[Q003解释](../../question/Q003_M002_route_overlap_remediation/answer.md)、[A007联合包审核v2](../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/joint_change_package_architecture_review_20261018_v2.md)。以下为已取得基线，不是M003新测量。

| 基线事实 | 结论和限制 |
| --- | --- |
| E008/R001/AT004：2026-10-18 03:09:25北京时间route失败，05:18:30.695127监督结束 | native1/supervisor1、stop_reason=null，自然失败；14项收尾已独立核验，无活动EDA |
| 最终702396重叠节点、547548有资源冲突的网络；2031733可路由，1484185完全路由 | 节点数与网数不同，不相加、不互作分母；未合法布通 |
| 原C01物理成员9491个均在SLR2 | 落区已实现，不证明全部拥堵来自或已由C01解决 |
| physopt occupied CLB：SLR0/1/2为94.95%/99.68%/99.92%；LUT槽54.79%/71.73%/76.31% | occupied site不等于槽位耗尽；SLR2不是默认空闲区，须核兼容打包及硬块周边空间 |
| 失败图WNS−12.413ns、WHS−0.125ns、WPWS−0.664ns | 仅作诊断，不是合法routed签核，不与其他阶段时序混比 |
| 日志top10含MLP分支DSP接入、parent FIFO、Attention元数据URAM地址及量化器等 | 只是样本，不能代表全部冲突网；同一网在多个重叠节点出现需去重 |

失败DCP在[AT004报告目录](../../project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation)，`route_failed.dcp`为765705446 B，工程已核SHA256：`51679d9a4f8dc35c5e5b167ebbecd72260b0862f85ad8168782646f0fc16da21`。SM013载图前从真实产物确认路径/身份，不以本文代替执行核验。place/physopt及E005同阶段报告用于区分阶段差异，原数据保持只读。

联合版本改变多个机制，属于整体方案验证；与E008的比较只能支持整体结果，不能把全部收益归给某一项。全量冲突归因、银行数/副本粒度及新物理位置尚未冻结。

## 3. 不变量与允许修改的文件

### 3.1 全局不变量

- 保持Hadamard、ScaleCode、format05、符号扩展、舍入、饱和/溢出规则及审计计数，保持S32/F16 Down输出等[goal数值合同](../../goal/goal.md)。不用近似除法、降低位宽或删计算换布通。
- 保持Attention→DDR0、MLP→DDR1、当前地址与lease生命周期、Host ABI、CSR、数据布局及外部ready/valid语义。生产软件算法不在本次改造范围。
- 保持器件、工具、core 100 MHz、双DDR UI 200 MHz及全部派生/IO时序要求。不暗中启用95 MHz fallback、无依据false path或放宽bus-skew。
- 保留E005的48个Attention输入边界、32个MLP输出CE边界及保护语义；80个边界在新图重新解析，不能以旧名字/数量代替新图证据。
- 保持所改模块的可观察延迟、吞吐/II、队列容量、事务顺序及reset/clear/abort语义。需要改变这些合同的方案交主控集中评判；触及用户冻结的全局数值/接口/时钟须用户明确授权，不能作为普通适配。

### 3.2 文件与责任边界

| 范围 | 生产入口或文件 | 允许变化 |
| --- | --- | --- |
| MLP数据组织 | `project/hardware/rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv` | FIFO字段分区、最少必要同拍副本、消费者连接，不删除隔离队列 |
| MLP上游 | `project/hardware/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv` | 选定组织所需连接/选择逻辑，保持调度协议 |
| Attention地址/存储 | `project/hardware/rtl/attention/hap_attention_board_cohort16_core.sv`、`hap_weight_meta_resident.sv` | 同拍地址分发；存储分银行仅经SM014选入 |
| 物理入口 | `project/hardware/vivado/scripts/m002_physical.tcl`、`build_vcu118_board.tcl`及相关检查；新建`project/hardware/vivado/constraints/m003_joint_locality.xdc`（计划名） | 正式构建链注册、来源与对象核验，不覆盖E008冻结包 |
| 验证 | `project/hardware/tb`、受影响仿真/结构检查、输入清单/报告入口 | 独立参考、协议、生产参数及实际网表检查 |
| 条件性算术结构 | 归因指向的DSP打包/量化器内部实现 | SM014有证据选入才改，保持精确数值及原吞吐/延迟，不顺手重写计算链 |

唯一生产入口仍为`project/hardware`和`project/software`，不复制一套生产RTL。旧`/home/user/EDA-202/zhuowenjun/ScaleLLM`及全部E005/E006/E008原始证据、归档源不删除、不移动、不改写。

## 4. SM013：有限范围、可交付的全量归因

复用失败DCP和报告，不为归因重复综合/route。先离线整理，再用单次只读载图补缺。查询预先声明输入、对象集合、字段、结束条件与checkpoint；缓冲写盘、分块统计，避免逐pin同步日志或无必要的全设计source×sink笛卡尔积。

必须交付：

1. 全部冲突网canonical ID/alias去重清单，与原生547548网对账；口径差异保存原计数、映射与原因，不强行凑数。702396重叠节点另作资源指标；不能导出的节点/字段写NOT_MEASURED，不把缺失当0。
2. 每网至少一条归属：驱动模块/类型、消费者模块集合、源/负载SLR及clock region、扇出、常量/时钟/控制/多driver/未知分类。网级、端点级、连接对级分表，未知保留。
3. 模块×区域全量统计。主排序键固定为`(归一driver模块, source SLR, 排序去重后的load SLR集合)`；多driver和未知各进显式桶，每个canonical网只入一个主组，按组内唯一网数降序、同数按键字典序，深查前20组（不足20取全部）。driver模块归一层级/规则在查询计划冻结；consumer归属与clock-region细分另作可重叠关联表，不与主组相加。前20组与补充深查集合取网ID的union计算覆盖率，分母是对账后的全量冲突网，不预设“90%已解释”。
4. MLP/URAM及可能算术热点的字段—源—消费者、位置/硬块、控制扇出、跨界cut及失败网交集，保留共享站点、macro、原生物理父及硬约束。
5. SLL初始估计仅作辅助；物理列/clock-region/SLR边界须由器件对象映射，不能把报告列顺序当X/LOC/BEL。

补充深查的种子在启动前冻结：拟改候选的literal roots、80保护对象的匹配规则、已知跨SLR热点边界；同时固定字段、查询终点和有界代表时序条数。全量轻量分类可以发现新类，但不在运行中递归扩大深查；新发现另列缺口，在当前批次自然结束后由主控决定是否新R补采。正常完成以预定对象/块清单耗尽为准，不用墙钟截断。

退出条件：全量网级清单可对账，拟改对象关键源/负载/状态/落区明确，主要未解释类有数量、影响和处置。关键未知可能推翻某候选时只阻塞该候选冻结；非关键未知经主控说明适用边界可保留，不无限追全芯片时序。诊断完成不等于唯一根因已证明。正常慢进程不因墙钟/静默强停，范围在启动前限定，下一批在自然结束后调整。

## 5. SM014：四表及联合设计冻结

| 冻结表 | 必须字段 |
| --- | --- |
| F1 字段—消费者 | 位宽、生产者、所有实际读者、捕获沿、跨区连接、共享字段、拟改变的D/Q连接；仅重命名不计收益 |
| F2 状态—采样 | 原/新next-state方程、push/pop/reset/clear/abort/launch优先级、URAM采样/返回拍、标签、stall保持、等价断言 |
| F3 资源—连接成本 | FF/LUT/mux/BRAM/URAM/DSP增减、CE/reset/clock负载、扇出、容量、吞吐/II/延迟；估算与实测分开 |
| F4 约束—对象 | 层次表达式、角色/数量推导、物理父/macro、硬块/时钟区、兼容容量/打包、原硬约束和overlay策略；新综合后实核 |

每个候选填写`selected / rejected / deferred`、证据、可证伪机制、文件、银行/副本粒度、布局策略、保护、测试、资源预算及失败判据。不能只列文件名，也不能把核心选择留到长实现期间。最终网表匹配/坐标依赖新综合的部分在SM017关闭，未关闭不得进入SM018。

C01整分支SLR2约束须明确保留、缩小、调整或替换及其依据。它是E008实验变量，不是M003算法不变量；不能偷偷取消，也不能以此绕过原硬约束与80保护。

### 5.1 MLP精确合同

现parent为非旁路、固定head、两entry FIFO。生产TILE_W=9的payload 6560 bit，head/tail共13120 bit。完整双消费者银行每支4144 bit：activation2304、acode64、ashift48、weights1536、wcode96、wshift72、mask12、mode/first/last/tile12。双支head/tail共16576 bit，**增加3456 FF**；这是估算，不是必须选择或已测物理代价。

保留中央occupancy、`parent_pop = parent_valid && ready0 && ready1`、空push→head、非空push→tail、满pop搬tail→head、占用1同时push/pop替换head和原reset/clear优先级。宽payload原无复位，不新增宽复位；下游两entry branch ingress保存不同在途事务，不能作为重复存储删除。

只复制真实远隔多消费者所需字段，同一捕获事件和输入语义，各consumer读对应银行。同步分析银行D端、CE/reset/clock及上游选择源，防止长线只迁到上游。必要保留属性精确限定对象，不广泛DONT_TOUCH。

### 5.2 Attention精确合同

`meta_read_addr_r`同时提供响应tile/group标签。本地副本须同沿执行原状态：异步reset、`system_clear`、`ST_LAUNCH && weight_command_ready`清零，`meta_rsp_fire`递增，保持赋值优先级；每个有效URAM采样沿`local_addr == original_addr`。`local_addr <= original_addr`额外一级不等价，含abort的`datapath_clear`不能替代所有地址事件。

保持response消费推进地址、原FSM、单pending/token、读enable/延迟、同址读写语义、响应stall及计数/格式检查。改为request接受推进需另定义标签/协议，不能藏在副本改造中。

81920×256存储可评估10×8192×256银行，但高位选银行、低13位地址、同沿银行/data捕获、256-bit响应选择路径、80-URAM实际映射均需核实；不是默认必改，不暗加输出流水。SM014在同拍副本、银行方案或维持原结构间明确选型。

### 5.3 算术候选

DSP已有输入/乘积/校正输出流水，MLP量化已有双divider lane，Attention量化有8个divider；E005 input48/CE32已实现。不重复当新优化，不仅因top10出现就重写。

若全量归因证实算术逻辑/控制集合/硬块接入为主要压力，可并入位精确结构调整，同时给资源成本、原吞吐/延迟与数值证明；否则写不选原因。近似数学、调度降速、外部周期变化超出本合同。

## 6. SM015–SM016：集中实施与配套验证

按冻结表集中交付RTL、约束和测试。接口冻结后MLP/Attention可按文件边界并行；集成、公共入口、同一测试或摘要各有唯一owner。剔除项也保留理由。

新`m003_joint_locality.xdc`经当前M002正式链注册/加载，输出真实来源、对象数量/属性。`m002_physical.tcl`与`build_vcu118_board.tcl`已拒绝的`mission0004_metadata_width_local.xdc`、`mission0005_coordinated_partition.xdc`继续是历史输入，修改它们不算有效优化。E008归档包不热改。

检查的完整覆盖目标包括空匹配/数量错误/未知资源、source/constraint身份、origin/物理父/macro、硬约束冲突、80保护、新银行和硬块区域、恢复DCP后的实际生效。G3b（SM016）只验检查实现/必要正负对照和联合功能回归已完成；G4（SM017）在新综合/恢复父图上原生实核；SM018再核布局后对象存活/复制/合并及真实位置。前一阶段不等待后一阶段产物，也不能提前将其原生结果记PASS。名字含local不证明本地化；避免对大leaf列表反复昂贵查询。

必须一次配齐的验证见[验收矩阵](verification_matrix.md)：

- MLP独立整数参考；生产TILE_W=9；全部合法占用/push-pop；非对称stall、原子接受、满空转换、持续反压、在途reset/clear、事务守恒；新旧逐周期ready/valid、有效payload、状态与接受/返回周期。
- 元数据直接专测：首/末/银行边界/越界、stall、读写碰撞、单pending/token、reset/system_clear/abort/launch、响应标签、计数/格式。valid/stall数据稳定；无效payload不作错误期望。
- 选入算术改动补独立位精确参考、合法范围或有证明的边界/随机覆盖、符号/舍入/溢出及吞吐/协议；数值测试不代替协议。
- 入口正负对照：漏overlay、空匹配、身份错误、保护丢失应被发现，不改预期值或弱化断言。
- 接口/Host/DDR/IP未改证据按身份/适用性复用；被影响项新验，不无依据重跑全项目或板级验证。

## 7. SM017：新综合、资格和实现输入冻结

RTL改变必须新综合。E005父DCP、旧144输入、E008的39归档源仅作基线，不能代表新设计。新源/参数/IP/XDC/Tcl/工具清单记录真实数量、SHA、差异与关联测试，不机械要求数量等于旧值。

核预期副本是否存在/被合并、实际D/Q和consumer、FIFO/存储容量、URAM映射、资源/控制集合、扇出及保护。结构未实现或超预算时，在完整实现前修复、重验、重新综合；估算与实测差异须解释，不以面积下降证明布通。

完成opt/debug/pre-place正式检查，在新图关闭F4，形成实现输入冻结：RTL/测试/overlay/入口身份、新综合网表及合法父DCP、确切策略、适用报告和风险。以E008 SSI_SpreadSLLs/Default/Default为参考，由SM014集中决定策略是否改变；关闭增量实现，不自动扫seed/策略。未冻结策略、身份不一致、关键对象未解析、物理约束非法不得进入SM018。

## 8. SM018：同一版本完整implementation

资格通过后连续place→physopt→route，逐阶段保存DCP、日志、完整报告和真实状态。常规工具/来源适配按既有授权修复并记录新AT，不逐项问用户；源/约束改变重建身份，结构/策略/范围变化另开R并重做受影响前置，不拼接版本。

place/physopt核实际银行/分支/硬块位置、C01策略、对象存活/复制/消失、兼容站点/SLR资源、跨区连接、固定热点与新最坏窗口、SLL/控制时钟接入、timing和DRC。固定窗不可得写UNAVAILABLE，不用另一窗口冒充同窗改善。

结构/约束合法但setup/hold/PW负，主控记录风险后可继续一次诊断route，沿用原授权；负时序不是正常进程自动停止条件，最终验收不降低。自然失败尽可能保存失败DCP、route状态、拥塞、时序、DRC及代表连接，保留原exit，诊断失败不覆盖原route错误。

物理目标是一版集中完成的设计和一次完整验证，不自动原样重跑或无限扫参。失败后依据新证据由主控集中定义下一实质版本及影响范围，不自行增设逐项批准。

## 9. 成功标准与结束判据

详见[验收矩阵](verification_matrix.md)。各层级单独记录，互不替代。

| 层级 | 通过条件 |
| --- | --- |
| 功能等价 | 位精确、逐周期协议、生产参数、reset/clear/abort、计数、吞吐/延迟全部通过；独立参考及适用身份完整 |
| 结构/约束 | 真实网表实现冻结连接/副本/存储，overlay生效，80保护和原硬约束保持，资源/消费者/落区符合设计 |
| 合法布通 | 原生route成功、可打开closed route DCP、完整POST；routable>0、fully_routed==routable；unrouted/partial/error/conflict和重叠节点均0 |
| 时序规则 | 完整合法routed图全部时钟WNS/WHS/WPWS≥0、TNS/THS/TPWS=0、失败端点0；完整覆盖，无无依据例外；bus-skew另核 |
| 原目标余量 | 保留goal和M002原100MHz setup/hold≥+0.5ns目标，单列实测；0ns规则通过不代表原余量达成，不自行降频/下调目标 |
| DRC/安全 | 完整DRC无未解决违例；告警逐项归属/处置；正式CDC/reset/IO和最终bus-skew源/端点覆盖关闭，旧OPEN不能算通过 |
| 交付/审核 | 输入与产物可复现、独立审核、差异/限制和终态收尾齐全；用户结果审核另列，不伪写批准 |

整体成功需要范围内上述功能、结构、合法路由、时序/原目标余量及安全达到合同，证据/审核齐全。仅布通但时序/安全FAIL或OPEN，写“布通通过，整体未完成”；冲突减少也不是成功。计划步骤自然完成但目标未达，可提交本轮失败/未完成总报告，执行结束与技术目标分开。

全项目部署/性能仍在范围外：不生成bitstream、不上板、不运行GPU/PPL/ACC，不把M003成功等同ScaleLLM系统目标完成。

## 10. 子任务、依赖和所有权

| SM | 交付 | 依赖 / 技术阶段门 | 责任 |
| --- | --- | --- | --- |
| [SM013](tasks/SM013.md) | 失败网分类、候选端点归因 | E008终态；G1口径/关键归因 | 工程取数，独立核口径 |
| [SM014](tasks/SM014.md) | F1–F4、选型和联合设计 | SM013；G2语义/成本/策略冻结 | 主控选型，工程设计，架构审核 |
| [SM015](tasks/SM015.md) | 选定RTL集中改造 | SM014；G3a实现及局部验证 | 工程按文件唯一owner |
| [SM016](tasks/SM016.md) | overlay/入口和完整回归 | SM014可准备，最终依赖SM015；G3b联合回归 | 工程集成，独立核查 |
| [SM017](tasks/SM017.md) | 新综合、结构/资源实核及输入冻结 | SM015＋SM016；G4新图和来源资格 | 唯一EDA，主控确认范围 |
| [SM018](tasks/SM018.md) | 完整place/physopt/route | SM017；G5真实物理/终态 | 唯一EDA，阶段独立审核 |
| [SM019](tasks/SM019.md) | 最终矩阵/总报告/交接 | SM018终态；G6全局证据整合 | 主控整合，独立审核 |

G1–G6是技术完成条件，不是新增用户审批。未满足依赖不假通过，独立文档/测试准备继续。SM均planned；工程在实际准备时登记E/R/AT，本合同不预造已运行实验。

主控独占goal/mission/results与共享导航；A006为现有工程协调/唯一EDA职责入口，A007为独立架构审核入口，后续实际派发/运行身份另记，本文不声称工程任务已启动。同一RTL/测试/摘要有唯一owner，保留他人改动。最多3活跃agent含Root、无后代；agent并行和重工具串行分别管理。[模型期望](../../agent/model_policy.md)与实际回执分开，不默换、不重绑旧外部会话。

## 11. 资源、停止和连续性

- 全项目重工具同时最多1条，含Vivado/XSim及编译；CPU0–7、max8线程、nice5，不按SM重复分配额度。
- 保留树RSS192GiB上限、MemAvailable低于48GiB持续30秒、磁盘低于30GiB的原保护。触发仅管理本任务经核验PID/start进程组，保全证据，不影响其他项目。
- 正常进程无墙钟/无输出强停，不继承默认300秒/12小时deadline。真实fatal、身份失效、资源异常或用户明确停止按事实处理；旧单次诊断停止例外不复用。
- PDU暂停已解除，旧记录不是重新等待恢复的条件；新运行仍核单EDA空闲和前次收尾。
- 实际启动/阶段改变/异常/结束更新三摘要，原生进程与监督状态分开。文档running不是心跳；代理/消息故障后先查真实状态，不盲目重跑。
- 未配置持续监控不声称后台监控，本任务定义不创建定时提醒。

## 12. 版本、证据与交接

E为实验主题，R为固定范围/协议批次，AT为具体尝试。新结构/策略/范围新R，同范围工具修复新AT及新来源绑定；原终态不覆盖。冻结后不热改消费源；SHA来自真实文件，命令、时间、环境和产物可追溯。

实际E目录至少交付协议/三摘要、F1–F4与选型、baseline/新manifest、文件差异、回归、synth/opt/place/physopt/route检查点及报告、最终矩阵、warning/CDC/reset/IO/bus-skew清单、成功签核或失败保全、输入未变和PID/start/锁/资源收尾。主控维护`results/missions/M003_summary.md`和SM审核，不能制造空报告当通过证据。

下一技术入口为SM013：补齐归因，为集中设计冻结提供数据。**本轮定义完成，不代表SM013已运行、RTL已改或新implementation已启动。**
