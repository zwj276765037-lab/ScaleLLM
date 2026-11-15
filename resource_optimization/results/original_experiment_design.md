# MLP ScaleCode DSP 整板候选：阶段合同

合同日期：2026-11-14；资源授权修订：同日用户明确要求“请最大化使用服务器的资源”，本修订替代原单重EDA/4核4线程限制。用户已授权立即启动新一轮完整板级 implementation 与 bitstream。架构、合同与阶段验收由 Astra xhigh 负责；工程由 Sol 按本合同连续准备、仿真、综合、布局、布线、普通修复及生成 bitstream，无逐次源码/运行审批门。两份阶段文档由架构负责人维护，工程在本实验其余目录保存实际映射、运行索引与结果，并向架构负责人同步事实。

## 1. 目标、边界与权威来源

在生产 Decode16 的独立构建副本中比较恢复叶 `dsp_raw_only` 与 `dsp_all`，取得两者完整板级综合与布局资源；选出一个候选完成布线、严格物理签核及合法 bitstream。仅改变 MLP ScaleCode 恢复叶的 DSP 映射属性，保持生产接口、数值、流水、所有板级 IP、80/200/200 MHz 时钟与六份 XDC。Down 继续由 CPU 完成，本阶段不移植 Down，不包含上板烧写。

| 来源与已核查位置 | 本阶段采用的事实 |
|---|---|
| [生产架构](../../../../docs/HARDWARE_ARCHITECTURE.md:3)，3–7、33–39、56–61、99–114 行 | VCU118 `xcvu9p-flga2104-2L-e`，top `scalellm_final_decode16_bd_wrapper`；core 80 MHz，两个 DDR UI 200 MHz；固定 ABI 与 CPU Down 边界 |
| [实际生产叶](../../../../project/hardware/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv:3)，3–86 行 | 双列精确恢复、四处 `use_dsp=no`、原三级弹性流水和同步 reset/clear |
| [构建入口说明](../../../../docs/BUILD_HARDWARE.md:31)，31–98 行 | 使用现有 prepare/create/synth/impl/bitstream 入口，在新目录构建；原生默认策略、无旧 incremental checkpoint；逐阶段保存 DCP 与完整报告 |
| [物理闭合规范](../../../../docs/PHYSICAL_CLOSURE.md:109)，109–163 行 | 显式 hold-sll/hold；每次选定输入 DCP，禁止隐藏重试；bit 阶段复核路由、时序与 DRC |
| [已验收单叶合同](../../mlp_scalecode_dsp_probe/source/design.md:19)，19–67 行；[结果](../../mlp_scalecode_dsp_probe/source/results.md:25)，25–54 行 | raw-only 与 all-DSP 只改变指定属性，已有独立整数 gold、协议及数域覆盖；单叶物理结果不是本次整板结果 |
| [已验收 bank192 合同](../../mlp_scalecode_dsp_bank192/source/design.md:7)，7–18 行；[结果](../../mlp_scalecode_dsp_bank192/source/results.md:22)，22–35 行 | all-DSP 96 叶 bank 的 OOC 结果可作映射背景；未包含完整 PE/guard/累加或板级上下文 |

以上仓库相对链接均以本文件所在 source 目录为起点；生产文件的权威绝对根为 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM`。已核查生产叶 SHA-256 为 `18a2bad1a3b7df345abfaf3428a8a5bec245d9580dc3b336e6153736a23a9f6a`，发布 `deploy/final/hardware_source_manifest.json` 为 `10795824a738727afadaf55941d7c51dc4e36ff3e1819df2ab0ab9b23160f3c9`，当前 `deploy/final/build_hardware.py` 为 `6ff679071bd5c64657d02e60c81679332d2c185bf963b2767b4d87eb5609b4f1`。工程执行前重验这些身份；新候选不得继续冒用原发布 bitstream 身份。

## 2. 候选与允许的实现变化

| 候选 | `s0_code_product0/1_u16_r` | `s1_raw0/1_s33_r` | 结构预期，待整板核查 |
|---|---|---|---|
| `dsp_raw_only` | `use_dsp=no` | `use_dsp=yes` | 每双列叶 2 DSP，96 叶共新增约 192 DSP |
| `dsp_all` | `use_dsp=yes` | `use_dsp=yes` | 每双列叶 4 DSP，96 叶共新增约 384 DSP |

在候选源闭包中保留原模块名 `hap_a8w4_scalecode_recover2_lut`，使现有实例连接不变。唯一允许的生产 RTL 文本差异为上述属性值；模块名中的 lut 是原生产名字，不再用作候选映射结论。不得改变算术表达式、位宽、符号、有效握手、寄存级、复位、clear、shift/guard、跨组累加、SiLU 或 DMA。不得用独立 bank 顶层替代原整板恢复层级。

先严格验证发布闭包，再从该闭包生成两个独立候选副本及各自 manifest，记录父 manifest、允许 overlay、每个输入文件 SHA-256 和候选身份。候选校验器必须仍对实际文件逐项校验：仅生产恢复叶可不同，其余 RTL/ROM/ABI/XDC 均与发布闭包相同。不得删除哈希检查、把失败改成 warning、改写原发布 manifest 或原工程来让候选通过。可在本实验内适配现有 Python/Tcl 入口的路径、候选 manifest 选择、分阶段 checkpoint 和报告输出；这些适配自身也记录哈希与差异。

两候选使用同一 Vivado 2025.2、part、board 文件、IP 版本/参数、synthesis/opt/place/phys_opt/route 默认策略、分阶段线程策略、时钟与约束。保持 incremental checkpoint 为空，不借用原生产布局或候选 A 的实现结果作为候选 B 的 incremental reference。相同身份的未改动 IP 结果允许只读复用，但必须核对源码/XCI、工具及生成配置的 manifest，且两候选按同一规则使用；不复用恢复叶综合结果代替整板实际综合。

最新授权允许在候选本地Python/Tcl驱动、create/thread hook及候选manifest内记录并修改4线程/4CPU/单jobs硬编码检查，引入独立的native线程数、IP jobs、CPU affinity与全任务资源守护参数。它们属于构建基础设施overlay，必须逐文件保存修改前后哈希、允许差异及实际生效参数；生产RTL overlay仍严格只含指定2/4处属性，全部数值/ABI/ROM/XDC和签核门槛不变，原发布文件不改。线程上限校验改为本机实测的1..32，不能直接删除范围检查。已经启动的raw-only create按其旧4线程配置完成，不中断或追改其运行manifest；后续阶段使用新版配置，两候选实际create并行参数差异单列，不能伪称已有运行已采用新预算。

## 3. 数值和协议合同

每列 `gold = signed(dot_s17) * unsigned(activation_code_u8) * unsigned(weight_code_u8)`，采用独立至少 64-bit 有符号整数计算。S17 全域为 [-65536,65535]，两个 U8 码为 [0,255]；输出 S33 精确整数，无新增舍入、饱和或截断，容差 0 bit。W4A8 生产 dot 范围 ±65280，完整 S17 极值作为接口诊断分别登记。

保留 s0、s1、out 三组 valid；满速 II=1。输入 e0 接受、e2 沿后输出可见、e3 接受，握手到握手延迟 3 周期。`rst_n` 为低有效同步复位；clear 同步取消在途事务，且复位优先。正常背压时 ready/valid、输出保持、顺序及容量与原叶相同；取消后无旧事务泄漏。生产 GU 的 S37/F24、S44/F24、S24/F16及 SiLU×Up S32/F16 边界不变。

## 4. 功能验证、证据复用与映射检查

1. 复用单叶通过运行 `mlp_sc_sim_20261113T081037Z_5219957a` 的独立整数 gold 和协议证据，前提是核验原运行 manifest、TB、三份叶文件及允许归一化差异。该运行覆盖 567 定向、两列各 131072 个 S17 编码、4096 固定种子随机事务，每路接受 135747、输出 135741、取消 6；复用明确标注为旧结果，不写成本次新仿真。
2. 对本次实际候选源各做新的叶级 post-synthesis functional netlist 验证：复用上述 gold/事务队列和覆盖，不用 DUT 内部信号或原输出生成期望。至少覆盖同样的边界/全S17扫描/随机/满速/背压/reset/clear，检查接受=输出+取消+在途，终态在途为0。工具模型使用 Vivado 2025.2，对全局启动/同步复位按真实模型采样，不能掩盖有效事务失败。允许复用同一 TB 的小型适配和小型叶综合入口；这只是映射功能验证，不是整板物理资源结果。
3. 用候选实际闭包完成native elaboration/compile-order校验，确认全部96个恢复叶来自唯一候选版本，未混入旧叶/另一候选/额外影子模块。工程发现portable独立`synth_design -rtl`入口未加载OOC IP、raw-only报`Synth 8-439`缺clk_core模块；保留此失败，后续由完整native project synthesis先完成IP依赖并执行真实顶层elaboration，再以完整闭包/96叶映射/第4.1节分阶段blackbox规则验收。不要求重复无效独立入口，不放行功能黑盒或将失败追认为PASS。新仿真必须退出0、零 ERROR/FATAL、全部断言通过且最后打印 `HARDWARE_AGENT_SIM_PASS` 或既有等价通过标记。
4. 在完整整板 synth 及 placed DCP 中导出恢复叶路径、DSP48E2 原语及乘法/寄存归属；核对实际 96 叶及 raw-only/all-DSP 差异，按第4.1节核查blackbox、确认无意外裁剪。实际数量不同先查明映射原因，不把属性意图当实测数量；普通脚本/路径修复连续完成。
5. 原发布全命令/板测结果仅作为未改动系统的历史背景。当前只有属性改变且归一化源码一致，可通过上述局部独立验证、全闭包核验及实际映射证明本阶段改动；不强制启动多小时完整模型仿真，也不把历史板测改称新候选板测。若发现属性以外 RTL 变化、接口差异或数值失败，停止物理推进并修复本阶段允许差异。

### 4.1 综合后调试占位与优化后零黑盒（2026-11-14限定修订）

已直接核查历史生产[linked_blackboxes.tsv](../../../../artifacts/verified_80mhz/hardware_agent/evidence/physical/final_decode16_011/reader_001/source_snapshot/project/hardware/vivado/reports/final_decode16_011_synth/linked_blackboxes.tsv:2)：唯一记录为`dbg_hub / dbg_hub_CV / OPEN_DEBUG_PLACEHOLDER`；同一历史[implementation日志](../../../../artifacts/verified_80mhz/hardware_agent/evidence/physical/final_decode16_011/reader_001/impl/vivado.log:424)的`opt_design`阶段明确执行`Generate And Synthesize Debug Cores`，为`dbg_hub`处理`xilinx.com:ip:xsdbm:3.0`。这支持将该精确占位身份与缺失功能IP区分；历史核展开不代表本轮已经展开成功。

- **仅完整native synth完成并链接全部功能IP后的检查**允许0或1个`IS_BLACKBOX == 1`单元；有1个时必须同时满足精确`NAME == dbg_hub`、`REF_NAME == dbg_hub_CV`、非primitive，并确认属于Vivado调试核对象。新报告必须保存实际NAME、REF_NAME、IS_BLACKBOX、IS_PRIMITIVE及调试核关联；不能只从旧报告推定当前REF_NAME。其余功能闭包/IP身份仍按原合同核对。任何其他名称/类型、额外黑盒、属性查询失败或无法确认调试核身份均FAIL；不得采用`*dbg*`等通配白名单、仅按名字豁免、关闭黑盒查询或降低DRC等级。
- **`opt_design`完成后、开始place前**必须导出并检查全部`IS_BLACKBOX == 1`单元，数量严格为0，保存post-opt DCP与结果；原`dbg_hub`也不再例外。保留本轮调试核生成/链接日志。若核生成失败或仍有黑盒，停止该候选物理推进。post-place、post-physopt、route、必要hold修复后的最终DCP及bitstream输入复核同样要求零黑盒；第5、7节选型与最终签核门槛不变。
- 本轮raw-only初次synth的原始`returncode=1`、日志、DCP及报告保持FAIL证据，不能改写为PASS。可对已完成且输入身份未变的本轮native synth/checkpoint重新执行报告及限定门槛，另存修复后的收据，绑定原DCP SHA-256及原失败收据，记录为报告/门槛复核；不重做无必要综合，不使用历史生产DCP代替本轮结果。复核通过后可继续已授权的opt/place流程，post-opt零黑盒检查是进入place的必要条件。
- 恢复叶路径含`gen_row[0]`等方括号，统计DSP后代必须使用字面层级前缀或等价准确对象关系；不能把完整路径直接作为Tcl glob。原始错误表保留，修复后的映射与独立DSP清单、分层报告交叉核对96叶及每叶实际2/4个DSP。报告修复不改变RTL、数值合同或原始综合网表。

## 5. 独立候选并行比较与一次首选 route

工程按依赖执行：预检/保存原身份 → 建立候选与功能检查 → 两个独立候选各自完成 synth、opt、place、phys_opt及报告，可按第6节并行推进 → 等两者比较所需报告齐备后选择 → 从所选自身post-physopt DCP继续route → 必要的显式hold修复 → bitstream。每个候选内部的设计依赖不并行；相互独立的IP OOC综合可按jobs预算并行。只为有效工作提高并发，不复制相同实现运行凑CPU占用。

为避免无必要的双重 route，可在现有 implementation Tcl 的本地副本把 `opt_design; place_design; phys_opt_design; route_design` 拆成 placement 与 route 两次受守护调用；命令和默认策略不变，前半段必须保存 placed、post-physopt DCP，后半段仅打开该候选自己的 post-physopt DCP 续跑 route。同候选两个调用共用 implementation 8小时预算，checkpoint加载/报告时间计入。没有完成的步骤必须如实记 NOT_RUN，不能把打开旧DCP写成新布局。

比较表同时列出两候选的全板 LUT、CLB Registers/严格FF、occupied CLB、BRAM36/URAM/DSP，总量和逐 SLR LUT/CLB/DSP 的使用量、可用量及百分比，以及实际 congestion/高扇出/跨SLR问题、post-place/post-physopt WNS/TNS/WHS/失败端点。LUT低于100%不意味着CLB/某SLR有足够空间；不得机械相加重叠层级。恢复层级和整板总量分别报告。

自动选择规则按下列顺序执行并把输入指标和结果写入现有运行索引，无新增审批门：

1. 排除未完成合法 placement、全板或任何SLR的CLB/DSP等资源超容量、未解析blackbox、身份/约束错误、未解决功能失败或工具报告无法完成后续路由的硬性布局错误者；若只有一项可行，选该项。LUT总量较低不能覆盖SLR资源超容量。
2. 两项可行时，先选post-physopt setup通过者（WNS≥0、TNS=0且setup失败端点0）；setup同级时，选hold通过者（WHS≥0、THS=0且hold失败端点0）。这是选型优先级，尚非route签核。
3. 两者setup/hold均通过时，默认选raw-only，以保留DSP余量；完整LUT、occupiedCLB、逐SLR CLB/DSP和拥塞差额照实交付，不以all-DSP节省少量LUT自动消耗额外DSP。若工具已明确报告raw-only存在步骤1的硬性布局问题，则按步骤1选all-DSP。
4. 两项处于同一未闭合类别时，按以下字典序选择：更大setup WNS → 更小setup失败端点数 → 更小abs(TNS) → 更大hold WHS → 更小hold失败端点数 → 更低最大SLR CLB使用率 → 更低最大SLR DSP使用率 → 更少全板LUT → raw-only。保留全部负值，记录将由route/适用hold修复检验的路径类别，不允许把负布局余量改写为通过；没有可执行的新物理假设则登记阻塞。

首选候选只完成一次正常 route。失败时按真实报告诊断：setup clean 且 cross-SLR hold 失败可用一次 `hold-sll`，剩余适用 hold 失败可用一次 `hold`；不盲目轮换 directive、随机 seed 或重复同命令。若首选仍不能闭合，另一个已布局候选仅在其报告支持不同瓶颈/映射假设时可作为合同内备选 route；保留失败者和选择原因，不为补齐比较表强制路由两者。两个候选均无新可验证原因时停止无效重试，报告具体阻塞。

## 6. 服务器资源和停止条件

2026-11-14（工具日志本地时间08:50）预检：2×Xeon Gold6248R，48物理核/96逻辑CPU；NUMA0为CPU0–23及48–71，NUMA1为CPU24–47及72–95。同次快照MemAvailable为495539781632B（约461.5GiB）、可用磁盘333233315840B（约310.35GiB），load为2.03/1.71/1.14。快照不是后续资源保证，每阶段及运行中仍须采样。

空Vivado2025.2进程实测 `set_param general.maxThreads`：8、16、32均接受且get_param读回同值；64和96拒绝，报`[Common 17-154] Value should be >= 1 and <= 32`，探针退出0。该实测配置上限32优先于安装手册摘要中的1..8；配置值不保证任何算法实际使用32线程。安装手册描述synth_design有效最多4线程，故IP综合按每进程4线程预算；place/phys_opt/route等采用maxThreads32并记录实测CPU使用，不能声称全程使用96核。

| 执行配置 | raw-only | all-DSP / 后续单选候选 |
|---|---|---|
| 两候选CPU affinity | 0–23,48–71（NUMA0，24物理/48逻辑） | 24–47,72–95（NUMA1，24物理/48逻辑） |
| 同时活跃候选树 | 最多2棵，互不共享CPU集合 | 祖先/子进程按唯一PID统计，不能重复计入全任务RSS |
| IP及top synth进程native线程 | 每进程4，所有实际子run hook均核查 | 相同规则 |
| 每候选IP OOC jobs | 初始6，充分使用24物理核；可增至12以使用SMT/隐藏I/O等待 | 相同上限和内存准入规则；无需重新审批 |
| create/elaborate及物理步骤native线程 | 后续新阶段maxThreads32；当前create保留旧配置 | maxThreads32；记录实际算法并行度 |
| 双候选时单树RSS | ≤192GiB，包含其所有IP子run | ≤192GiB |
| 全任务RSS | 同时所有本任务树的唯一PID RSS和≤384GiB | 相同硬上限，包括辅助仿真/探针 |
| 选择后独占route/hold/bit RSS | 预先授权≤384GiB，受全任务上限及MemAvailable约束 | 无第二候选重树时适用；不是失败后临时加限额 |
| 进程优先级/系统保留 | nice增量10；MemAvailable≥64GiB；目标盘free≥30GiB | 不改变其他项目进程 |

IP jobs的12是并行run数量上限，不是每进程线程数。初始6×4线程/候选可使用全部物理核；当实际CPU仍有空闲、I/O等待或单IP串行阶段占主导且内存/磁盘准入满足时，工程可把后续IP派发扩到最多12，不要求重启已运行IP。发新run前按已观测IP峰值和剩余树预算预约内存；无样本时采用每IP16GiB的启动预约（不是强制IP终止上限）。满足单树剩余额度、全任务剩余额度及系统64GiB保留才增加jobs；预算不足自动减少或暂缓新派发，不增大上限。launch_runs固定jobs入口可采用批次/受控独立run派发；先核对工具依赖，避免同时启动依赖未完成的top synth。记录有效jobs及调整原因。

选择后只保留所选候选重树，route/hold/bit独占模式明确允许CPU0–95全部96逻辑CPU affinity，`general.maxThreads=32`，全任务RSS≤384GiB、MemAvailable≥64GiB不变。候选本地runner在双候选模式每树仍限对应48逻辑CPU；独占模式应允许96，不能残留`len(cpus)<=48`限制。这样32个原生线程可调度到超过单socket24个物理核心；当前没有实测证据支持为NUMA局部性继续限制单socket，不预设跨NUMA一定加速，记录实际CPU使用和运行时间即可。不为使用闲置核启动第二次无必要route。新启动树应保留到各自RSS上限的内存余量；若机器当前可用内存不足，应缩减有效并发/单次声明额度或延后启动。已有raw-only create正常结束，不因本修订终止。其他项目长期Vivado PID2446209/2446304不是本任务，禁止修改其affinity、优先级或终止它们；PID仅作识别背景。

| 阶段 | 墙钟上限 | RSS上限与说明 |
|---|---:|---|
| validate/create/elaborate，各次 | 1800s | 32GiB，沿现有入口 |
| 每候选完整 synth | 10800s | 192GiB；包含父进程与并行子任务，墙钟按最早本阶段启动至阶段完成计算，不将并行子run时长相加 |
| 每候选 implementation | 28800s累计 | placement并行时每树192GiB；选定后独占route可384GiB；opt/place/phys_opt与后续route/加载/报告合计，拆阶段不重置额度 |
| 选定候选显式 hold 修复 | 7200s累计 | 独占时≤384GiB；hold-sll与hold共享预算，可依据剩余量缩短各次调用 |
| 最终 bitstream | 2400s | 独占时≤384GiB |
| 新叶级功能/综合网表验证，各次 | 1800s | 16GiB；先估成本，完整全域扫描已有短运行参考 |

墙钟上限保持原值，提高并发不是自动延长预算的理由；所有上限可因当前资源收紧。守护须监测单树和全任务RSS、MemAvailable、free disk及每候选阶段累计墙钟。达到预警余量时停止新IP/候选派发；硬限触发则终止造成单树违规的自有树，或按最新启动候选优先终止以恢复全任务/系统门槛，保存日志、退出码与停止原因，不影响其他项目。不得仅增大资源/时间额度原样重跑。普通可证实的RTL overlay/脚本/报告解析/测试台适配错误可在合同内修复并重跑受影响项；失败尝试保留，各次时间及阶段累计时间均记录。时钟、数值、接口、物理门槛和本次修订后资源限额的实质改变交回架构负责人。无许可/工具/board文件、空间或内存不足时先登记预检阻塞，不空跑重工具。

## 7. bitstream 合法性与交付

最终所选 DCP 必须同时满足：正确工具/器件/top与80/200/200MHz身份；使用候选真实闭包及未改六份XDC；无未解析blackbox；全部可路由网络已路由且routing errors=0；全局setup WNS、hold WHS、pulse WPWS均≥0，TNS/THS及相应失败端点为0；无被隐藏的关键时钟/内部未约束端点；正常bit-generation DRC无Error/Critical Warning。普通Warning逐类保留说明，不能降severity、增加false path/multicycle、去掉端点或取消DRC门槛来生成合格结果。

bit阶段必须显式绑定新候选已通过的 routed/hold-repaired DCP SHA-256，重新运行现有identity、timing、route、DRC guards；成功退出后记录生成bit的大小、SHA-256、精确DCP、源码/工具/IP/XDC、命令与日志。只在本实验候选输出目录交付，不替换 `bitstream/ScaleLLM_Final_Decode16_80MHz.bit` 或发布manifest，不烧写板卡。即使生成bit，也只标记构建/物理通过，上板为NOT_RUN。

机器证据保留每次manifest、父子checkpoint哈希、全量日志、退出码、原始分层/全板/逐SLR资源、时序、约束检查、route status、DRC、峰值RSS/CPU/墙钟/磁盘最低值及候选选择理由。工程在本实验维护一个运行索引，架构负责人依据实际结果集中更新本文件和 `results.md`，不为每次普通修复建立新正式审核文档。

## 8. 阶段验收状态

合同已建立，并于2026-11-14增加第4.1节精确调试占位的综合后分类及post-opt零黑盒门槛。两候选新叶网表功能验证已通过；raw-only已完成native顶层综合并生成DCP，但初次报告门槛FAIL保留，修复后复核待证据。各候选实时阶段状态及证据见results.md；全板布局/路由、物理签核及bitstream尚未验收，不得从旧OOC PASS填写为本轮PASS。阶段结束后在本节集中登记通过范围、未完成项、失败/资源保护记录和交付物身份。
