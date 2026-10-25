# M006 功耗与速度集中审核（2026-10-25）

审核状态：**COMPLETE_BOUNDED**。执行：**HOST_INTERRUPTED**；测量结论：**PARTIAL_VALID_RESULTS，正式 benchmark 未完成**。可用结果限于少量已核正确命令的初测速度及明确 idle 窗口的七路功耗；负载功耗、增量功耗、稳态吞吐、duty 与 energy/job 均 **NOT_ESTABLISHED**。用户已要求实际测量；唯一设备 owner 为 `/root/board_host_prepare`，审核者只读核查并维护本文件，没有操作 Dell/FPGA/电源配置。依据为冻结的 [measurement 合同](../../../../../mission/M006_mlp_linear_only_hardware/power_performance_plan_2026-10-25.md)。本审核不另设执行批准门。

## 对象、数值与循环合法性

bit SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`；ABI SHA `318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a`。正式负载 `dense_active_128_v1` 的 manifest SHA `3e8074092cd9247f47d66743b0f83a285003e84505baf59c730c0fa9efcc1210`，gold SHA `8d67b8ddd9df84a1e5d72d77b466e1946f4e05d2839302f9680ec6cf8892f48d`。

审核者独立检查全部五份 binary 的大小/SHA，直接从 wire 解码并用独立 Python 整数运算重算 120 个输出坐标，覆盖两个矩阵、六行、两逻辑半区及尾列，每坐标均使用全部 128 组，全部一致。原 backend 的 [dense pair](attempts/AT_20261025T014143.332479Z_dense_original_backend_pair/receipt.json) 两份 1,376,256 B 原始输出亦独立逐字节与 gold 一致。作者另提供全 448 个周期、全非零 code/权重/activation、padding 与独立完整基周期复算证据。458,752 个 S24 输出全部非零，正负各半，范围 −3,935…3,942，无饱和。负载严格按合同构造；32 列周期诊断不能代表真实模型或最大翻转功耗。

已核原生 helper 的单 owner 驻留循环：首次原 backend 完成 stage、两 cohort 比对/ACK/release 后，新的持续 Windows 会话验证 active bank/generation/layer/bases；每完整 pair 释放后，以不同非零 epoch 绑定相同驻留数据，不重新 META LOAD/COMMIT，不重建 backend 丢弃 lease。每命令完整 C2H、逐字节 gold 比较、保存 DONE/身份/输出 hash 后才 ACK。首错停止新提交，保留 pending/DONE。相同输出按 SHA 去重保存，不省略每次 C2H 与比较。

正式 native source SHA `d0ebe952783607bcc8b470d8989cb708ab0134ae7019c68016d3da7d152b52d3`；Windows adapter SHA `ff64ca61a9bb1345d55fd805e4c43f67c13538de1f58db60580453e1a369fa91`；timed sampler SHA `11455992b1bc3e1716af21551039593963c7de4296bfff9a1e988053efeb34a5`。本地 helper/sampler 与冻结 stage identity 独立核对一致。native pilot 的四命令成功；其 `poll_s=0.0001` 有 Windows sleep 延迟，正式使用 `poll_s=0`，限制在八个逻辑 CPU，无系统 timer 修改。pilot 与正式不混合统计。

## 口径审核

- `0x354` 是 compute command 握手至 compute_done 窗口，包括供给/背压等待；`0x358` 是 LOAD phase；`0x35c` 是 store arm 至终态 drain 窗口；`0x360` 是接口 stall 的逐拍 OR。各项重叠，不相加，不从高 stall 比率推断 DDR 是唯一瓶颈。100 MHz 来自冻结 ABI、构建时钟与既有物理身份，不是频率计实测。无映射 total-cycle CSR，主机 START→首次 DONE 观测不可冒充精确硬件 START→DONE。
- 单 GU 为两矩阵 `2×16×4096×14336 = 1,879,048,192 MAC`；1 MAC=2 ops 时为 3,758,096,384 ops。compute-window dense-equivalent TOPS 与含 H2C/C2H、比较、记录、ACK 的驻留主机吞吐分列；weights/metadata 预驻留，不能当冷启动速度。
- 固定七路地址 `70/11/12/15/14/72/73`。官方 [AMD UG1224 v1.5](https://docs.amd.com/v/u/en-US/ug1224-vcu118-eval-bd) 图 3-27（印刷页 106，已实际看图）显示它们是并列 12 V 输入稳压器输出，表 3-34 对应独立器件/地址。因此可求“七路已监测稳压器输出功耗和”，未重复加入上游输入或同集合下游。该和不含其它 rail、转换损耗与其它板上负载，不是整板 12 V 输入或 FPGA die 总功耗。
- 三路 MAX20751 使用真实 `READ_POUT`，当前 2 W 步进对应每路约 ±1 W half-step、和约 ±3 W；load-minus-idle 保守约 ±6 W。该数只是量化项，非校准准确度或置信区间，均值不能消除系统量化。反馈节点 READ_VOUT 不作为 rail 电压，不乘 IOUT；P/I 只作诊断。四路 MAX15301 用测得 VOUT×IOUT，负小读数保留；非同时 V/I 及传感器误差仍存在。
- 同 Dell UTC 标记连接 native 阶段与 sampler；不直接相减不同进程的 perf_counter 和 Stopwatch ticks。仅完整、有效且全 sweep 位于阶段内的数据计稳态；跨阶段 sweep 排除。时间积分只在实际完整样本 midpoint 覆盖之间进行，端点/缺口不可冒称已测。低采样率只能给窗口平均。
- compute-window duty 按同一实际 load window 内完整成功命令的 `sum(0x354)/100MHz/window_s` 计算。它包含内部等待，不能叫 DSP 有效占空比、满载功耗或反推出瞬时 active 功率。energy/job 区分包含实际 I/O/主机空隙的窗口总能量与扣 idle 的增量。

## 正式数据审核

实际 attempt：[AT_20261025T014505.113183Z_native_formal](attempts/AT_20261025T014505.113183Z_native_formal/)。工程已启动 native 与 sampler；采集 SSH 随后返回 255 / server 127.0.0.1 timeout。[direct_recovery.stdout.txt](attempts/AT_20261025T014505.113183Z_native_formal/direct_recovery.stdout.txt) 显示主机 boot_time 为 `2026-10-25T01:47:48.5Z`，Windows Event 1001 记录 bugcheck `0x133`（参数 1），并有 Event 41/6008，原自有进程已不存在。因此执行存在明确 **HOST_INTERRUPTED**，本次正式测试不能判 PASS；此记录本身不证明 FPGA 数值失败，也不能确定根因为 poll0、驱动或其它组件。重启是观测到的系统事件，不是审核者/工程执行的恢复动作。

已取回并直接审核 [receipt](attempts/AT_20261025T014505.113183Z_native_formal/native_recovered/receipt.json)、[commands](attempts/AT_20261025T014505.113183Z_native_formal/native_recovered/commands.jsonl) 和 [telemetry](attempts/AT_20261025T014505.113183Z_native_formal/orchestration_recovered/telemetry.json)：

| 证据 | 实际终态/覆盖 |
| --- | --- |
| native receipt | 仍为 `running`；只含两 warmup command 20000/20001，epoch2000、request200、cohort0/1，均完整输出比较 PASS、身份/字节数/records/error 正确、ACK true |
| 持久化 commands | 恰好两组 before-ACK 与 ACK 记录；未出现任何 measured 命令完成记录，也没有持久化失败诊断 |
| 阶段 marker | 两 warmup 完成并 release 后进入 idle；`idle_before_begin=01:45:04.423105Z`，`load_begin=01:45:19.428938Z`；无 load_end、idle_after 或最终 CSR/owner 终态 |
| 正式有效 N | **0/要求至少20**。不能把 warmup 或其它 attempt 的 pilot 混入补足 |
| sampler | 85 次完整七 rail sweep，`pass=true`，约 55.07 s；采样器成功不证明 native 持续执行 |

receipt 的 `retained_lease=null/retained_pending=null` 是尚未更新的初始字段，不能作为中断后已释放的证明；仅 warmup pair 在 idle marker 前的 release 可由代码与成功记录确认。未知时段是否 START、DONE 或滞留不能由未写日志推断。审核者独立逐字节核对 recovered 与 pilot 保存的输出均等于 gold；去重文件只证明所存内容，逐次全量比较由命令记录与已审代码支持。

[WER metadata](attempts/AT_20261025T014505.113183Z_native_formal/dump_metadata.stdout.txt) 的本次及历史 bucket 都为 `0x133_ISR_XDMA!unknown_function`，本次 minidump 元数据约 9.95 MB；没有分析 dump 栈。此证据支持 XDMA ISR 路径关联，不能宣称已定位完整根因。时间线是 poll0 两 warmup 成功→句柄保持但 idle 15 s→load_begin 后无完成进展；idle/D-state 恢复与轮询/中断负担均是待区分假设，warmup 成功不能排除后者。本轮停止继续压测，不修改 driver、电源设置或系统 timer。

### 可用的初测速度（分组，不作正式分布）

下表每组仅 N=2；p5/p95 为 linear quantile 的描述值，不是统计置信界。pilot 总共四个正确命令，recovered 另有两 warmup；不把这些不同 poll/阶段合并。

| 组 | compute ms median [p5,p95] | compute min…max ms | dense-equivalent TOPS（median compute） | Host START→首次DONE median ms | Host 含I/O/compare/ACK median ms |
| --- | --- | --- | --- | --- | --- |
| [native pilot](attempts/AT_20261025T014420.840244Z_native_pilot/native/receipt.json) warmup，poll0.0001 | 7.350725 [7.347247,7.354204] | 7.346860…7.354590 | 0.511255 | 14.277800 | 18.633650 |
| 同 pilot，measured 标签两命令 | 7.353005 [7.350580,7.355431] | 7.350310…7.355700 | 0.511097 | 11.137850 | 14.833000 |
| 中断正式 attempt 的 warmup，poll0 | 7.349975 [7.348558,7.351393] | 7.348400…7.351550 | 0.511307 | 7.464500 | 11.938800 |

初测支持“本诊断生产形状 GU 的 compute 窗口约 **7.35 ms**，约 **0.511 dense-equivalent TOPS**”。它不支持稳定持续负载吞吐或真实模型速度承诺。正式 warmup 的 Host START→DONE 范围 7.4634…7.4656 ms，Host 端到端范围 11.5723…12.3053 ms；该 Host 时间不含预先 stage weights/metadata，且不能作为已完成正式 20 命令 benchmark 的结果。

### 可用的 idle 功耗

审核者对所有 85×7 rail 的原始 Linear11 或 VOUT×IOUT 重新转换，并重新核七路求和，均与记录一致。严格以同 Dell UTC、整 sweep 完全处于上述 idle_before 阶段筛选，仅 **index0…20，共21次**有效；无跨边界 sweep，剩余64次的 workload 未确认，全部不用于 load/idle-after 统计。

idle 阶段总长 15.005833 s；有效 sweep 外包络覆盖 13.092041 s，首末 sweep midpoint 覆盖 **12.930582 s**。以相邻 midpoint 梯形积分得到时间加权均值 **11.278003 W**；仅此已覆盖区间计入，不外推到整个15 s。实际 midpoint 间隔 median0.646091 s（requested sleep 为500 ms，另含顺序读取时间）。七路和样本 median11.277602 W、p5/p95=11.195610/11.370896 W、min/max=11.194162/11.397804 W；仍带约 **±3 W 的量化 half-step 项**及未校准误差。

| rail | idle 21样本算术均值 W（分项展示） |
| --- | ---: |
| VCCINT | 6.000000 |
| VCC1V8 | 2.306006 |
| VADJ1V8 | −0.048962 |
| VCCINTIO_BRAM | 0.377663 |
| VCC1V2 | 0.641161 |
| MGTAVCC | 0.000000 |
| MGTAVTT | 2.000000 |

分项表是算术均值，七路和的上述11.278003 W是时间加权值；两者口径有微小差别。MGTAVCC读0并不证明 rail 无功耗，负小 VADJ 读数不裁零。本轮没有确认的 load/idle-after 窗口，故不报告 delta、load功耗、满载功耗、TOPS/W 或 energy/job，也不以全部85样本的11.292484 W均值冒充负载功耗。

原始证据 SHA256：receipt `d99f728a15c5834ab7854e69d50886563848ec54039b802fd7ed0652289abaa0`；commands `5f78d9049ab0e23cbbaaa383470028bc43d94050b23799fbc9bbf8870a544f4f`；telemetry `06dbdc0551d4e451f9485f1d5d3d2f462a489c3da1b150f1f211e24b8ab4a43a`。

## 后继诊断建议（本轮不执行、不作为当前结果通过条件）

先只读对齐已安装 XDMA binary/version/hash 与现存 source 的 idle power policy、D0 entry/exit、ISR ack/mask/drain 路径，并保留 WER/事件时间线；源码相似不能假定与已装 binary 一致。若另开有界复现任务，应先为每次驱动调用增加持久化 before/after 标记，以定位 load_begin 后第一处停滞，再用少量完整 pair 区分短间隔与 idle15s 后首次访问，固定保守轮询、每次只改变一个变量。不能仅从 poll0 改善过初次延迟推断它适合持续运行，也不能直接靠改电源设置、驱动或重启掩盖现场。当前不继续任何新设备测试。

### IRQ 线索的只读核查

GU 构造源码和已生成 BD 确有下列链路：`hap_mlp_gu_axil_control.sv:148` 将 completion_valid 或 reset_required 作为 MLP irq；`hap_mlp_gu_job_control.sv:110–111` 仅在匹配命令 ACK 且排空/无fatal时清 completion_valid。`hap_attention_mlp_board_core_gu_only.sv:117–119,185–188` 声明 LEVEL_HIGH，并寄存 OR(Attention irq, MLP irq, integration_error)。`create_mlp_gu_board.tcl:616–621` 和 `m006_gu_AT006_constructor/.../synth/scalellm_vcu118_f05_bd.v:1426` 将该线接 XDMA `usr_irq_req[0]`，没有使用 `usr_irq_ack`。生成 XCI 设1路user IRQ、MSI能力1vector、MSI-X能力关闭；这只是能力配置，不代替运行时MSI/INTx状态。WindowsSession只开 `user/h2c_0/c2h_0`，未开读event0。

**上述事实支持核查 user IRQ 路径，但不证明 IRQ storm。** [PG195 user interrupt协议](https://docs.amd.com/r/en-US/pg195-pcie-dma/User-Interrupts) 本就要求 req 在 IP ack 后继续保持，直到软件清 source；[user enable语义](https://docs.amd.com/r/en-US/pg195-pcie-dma/IRQ-Block-User-Interrupt-Enable-Mask-0x04) 是源上升沿触发，源已高时重新enable亦触发。因此不能把“req持续高且未接usr_irq_ack”直接解释为不断产生MSI。driver若反复mask/re-enable、实际INTx模式或其它ISR问题属于另待证机制。`event_0`未打开也不等于kernel ISR不处理；当前没有与已装binary对应的Windows源码证据，不能宣称Windows/Linux行为差异已定位。

仅供后继任务审核的 user-only polling 方案如下，**本轮不执行这些写操作**。[PG195地址格式](https://docs.amd.com/r/en-US/pg195-pcie-dma/PCIe-to-DMA-Address-Format) 将 IRQ block 放在 XDMA内部DMA寄存器空间0x2000；[IRQ表](https://docs.amd.com/r/en-US/pg195-pcie-dma/IRQ-Block-Registers-0x2) 和 [user W1C定义](https://docs.amd.com/r/en-US/pg195-pcie-dma/IRQ-Block-User-Interrupt-Enable-Mask-0x0C) 给出：

| config/control空间offset | 用途 |
| --- | --- |
| 0x2000 | IRQ identifier；先只读核mapping，不借用应用user BAR地址 |
| 0x2004 / 0x2008 / 0x200c | user enable读/RW、W1S、W1C |
| 0x2010 / 0x2014 / 0x2018 | DMA channel enable读/RW、W1S、W1C；候选方案不写这些寄存器 |
| 0x2040 / 0x2048 | user request / pending只读；request含enable掩码，读0不一定说明源已低 |
| 0x3014 | 运行时 MSI bit0、MSI-X bit1（[PG195 Config MSI](https://docs.amd.com/r/en-US/pg195-pcie-dma/Config-Block-MSI-Enable-0x14)） |

在后继任务确认正确control映射、独占owner、无pending命令/IRQ源、driver不会并发改回mask之后，可评估只向 `0x200c` 写 `1` 清 user0 enable，并读回2004及2010证明仅user0改变、DMA channel enable保持；仍通过应用CSR轮询，完整C2H/gold后照常匹配ACK，mask不是ACK。若原user0已禁用，不能拿再写禁用作有区分力实验；若driver会自动重启用，直接BAR写也不是稳定方案。需要恢复时仅在source/pending已清、原位原本为1且所有权安全时用2008的bit0恢复；故障现场不重新enable。禁止全局关MSI、关DMA通道IRQ或把应用CSR 0x200c当作XDMA config地址。该方案尚未验证，也不是对本次0x133根因的结论；与idle/D-state、poll0负担假设分开。

详细 G5、Max-DPO、external reset 与真实模型适用性保持既有 OPEN 边界；本轮不将新增测点或未来性能优化列为当前通过条件。

## 追加：匹配已装驱动的源码与 IRQ 机制复核

本节依据后续取得的实际证据，更新上文“没有对应 Windows 源码”的时点判断；不改变原测量的 HOST_INTERRUPTED 及有效数值。工程取得 [24份源快照](attempts/AT_20261025T014505.113183Z_native_formal/installed_driver_source_snapshot/) 及 [来源/hash清单](attempts/AT_20261025T014505.113183Z_native_formal/current_driver_sources.json)，审核者独立核24份本地文件size/SHA均与远端清单一致。`C:\pcie_demo\hap_tools\xdma_driver_win_9018_src` 同目录 build 的 XDMA.sys 为32,256 B、SHA `1b50d26131c62edd9558d37a686968df5540ac67f38033373b7b99db063684f5`，与已安装 System32 驱动一致；这建立了 source/build 目录关联和二进制身份，并不等于已经可复现重编译。审核直接读取的 `libxdma/interrupt.c` SHA为 `6d82c3a9aed908f269918827f5bc55053a1ed6d169f555ebacd440325bd0852f`。

最小相关路径已核：

| 文件/行 | 行为及含义 |
| --- | --- |
| libxdma/interrupt.c:377–384 | shared MSI/INTx `EvtInterruptEnable` 无条件 W1S 开全部 channel 和 user IRQ；用户是否打开 event0 不影响此启用 |
| 同文件:399–439 | ISR 读 channel/user request，将非零位 OR 入软件 pending，并 W1C 暂时屏蔽，随后排 DPC |
| 同文件:442–489 | DPC 执行 engine/user callback，再在 interrupt lock 内恢复 channel 和 user pending 对应 enable；用户源清除只留 FIXME，实际没有等待条件 |
| sys/driver.c:335–336；sys/file_io.c:987–993 | 所有 user callback 都注册为 `HandleUserEvent`，它仅 `KePulseEvent`；不会清 FPGA completion_valid |
| sys/file_io.c:927–947 | event读取只清/等内核KEVENT；单独增加event0读者也不等于处理应用DONE或清硬件源 |
| libxdma/interrupt.c:537–585,688–695 | MSI-X user回调和导出UserIsrEnable也有独立W1S路径，后续policy不能漏过 |

由此形成有事实支撑的**候选机制**：GU DONE保持source高→ISR mask→DPC仅通知用户且立即reenable→按PG195“源已高时enable产生新中断”再次触发；用户态尚需完整C2H/比对后才能ACK清source。反复中断可能拖延C2H/用户态清源，形成反馈；这与WER的XDMA ISR关联相容。当前无崩溃时栈、ISR频率、DMA调用入口/出口或DONE现场，仍不能断言本次必由该机制导致。warmup成功只说明短次执行可完成，不排除长期或特定时序触发。保留应用先copy/compare后ACK合同；提前ACK不是修复。

**纠正“rawrequest未AND enable”的过度推论：**源码确实没有额外的软件AND，但PG195的0x2040寄存器本身定义为source AND enable，不能据此认定被屏蔽源仍会被任意后续DMA ISR读到并强制重开。要证明该变体，需要与文档不一致的实际寄存器语义或竞态证据。单次用户态mask仍不是耐久修复：已排队DPC可按旧软件pending重开，WDF重新调用EvtInterruptEnable以及导出UserIsrEnable也可重开，而且BAR写不持有driver的interrupt lock。上文mask方案因此降级为**未验证的条件性诊断候选**，不能作为随后压测安全性的保证；本轮不执行。

工程追加的 [control只读快照](attempts/AT_20261025T014505.113183Z_native_formal/control_irq_readonly_v2.json)（02:00:25 UTC）仅打开control、零写、句柄已关闭：IRQ/config identifier=`1fc20006/1fc30006`，userEN=1、channelEN=3，user/channel request及pending全0，0x3014=1（实际MSI）。它确认当前映射/模式及user0启用；重启后静态快照不能还原崩溃时状态，也未验证mask期间request行为。

S0 idle线索单独判断：审核对全部24份C/C++/H搜索 `WdfDeviceAssignS0IdleSettings`、`WdfDeviceStopIdle`、`IdleTimeout`、`EvtDeviceD0Entry/Exit` 均无匹配；sys/driver.c:197–207仅设置Prepare/Release并初始化空power-policy callback集合。**没有证据表明该驱动显式设置15秒S0 idle timeout。**15秒是本benchmark的用户态sleep，不能直接当作电源状态切换证据；平台/PCIe电源行为仍未测，未据此排除。

### 最小、可审核的后继准备边界

当前仅允许工程在独立副本准备可逆patch/编译产物，不安装、不更改driver/power settings、不重新压测。无需现在开发通用event ACK协议或更改RTL。若选择修复性候选，建议专用9018实验包使用独立固定user-IRQ policy（本GU polling场景禁用user0，保留其它允许位），而不是临时硬件enable值：

1. 在统一policy下覆盖全部五处user W1S（interrupt.c:383/482/542/584/694）；Enable callback明确清掉policy禁止位。shared/per-user ISR不认领或积累禁止位，DPC不派发/重新enable禁止位；导出Enable对禁用事件明确返回不支持，避免虚假成功。policy在enable/ISR/DPC三处一致，源禁止位不会通过旧pending或重新启用callback恢复。
2. 保持channel W1S/W1C、engine work、DMA描述符与超时逻辑、power policy完全不变；不使用全局MSI屏蔽。不要在DPC简单把pending AND当前硬件enable当作修复：ISR本已临时mask这些位，这样会误杀正常rearm。这里需要的是独立“允许哪些user IRQ”的策略，而非瞬时硬件mask。
3. 离线核所有user-enable写点、单MSI和MSI-X分支、禁用事件API及旧pending路径；用事件序列验证“source持续高不会重新启用user0，而DMA channel仍恢复”。在现有WDK构建配置下保存源码diff、完整构建日志、binary/INF/CAT身份与签名状态；编译通过只证明准备完成。安装前保留原oem113.inf对应包/原binary SHA及精确PnP实例，形成恢复到原包并核回SHA的步骤，不覆盖历史源码/原包。
4. **安装和再次设备测试属于尚未放行的新动作。**如果Root决定采用该候选，须先交付上述可审代码、验证与恢复方案，再向用户明确驱动替换及可能再次主机中断的影响，取得安装和有界再测同意。后续首先只能少量完整pair与明确idle后的首访问，持久化每次驱动调用前后标记、核user0维持禁用/channel enable不变；首错停止。不得直接恢复15秒持续压测，也不得以本节准备替代正式测量缺口。

当前结论是**源码级IRQ重复触发机制候选成立，具体蓝屏归因尚未闭合；mask-only不足以承诺耐久，是否需要安装新driver还未决定**。本审核没有编译、改动实现、安装或写设备，仍只维护本文件。
