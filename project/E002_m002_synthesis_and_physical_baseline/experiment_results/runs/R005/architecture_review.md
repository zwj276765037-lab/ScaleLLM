# A007：M002 物理策略与阶段审核

日期：2026-10-15。角色：架构、物理策略与独立阶段审核；runtime `/root/m002_physical_architecture_review`，不是历史长期对话。请求模型/强度为 `gpt-6-astra/xhigh`；[A007 配置](../../../../../agent/A007/config.md)记录实际 launch 已接受请求，本审核者没有独立运行时模型/强度证据，不把配置文件当作实际模型证明。

- execution：入口及恢复路线已审核；正式综合与CPU证据已核实；R003 AT004真实恢复预检已完成、issues为空，前两次查询/身份假设失败已有实证解释；发现并修正遗漏implement_debug_core的阶段设计，尚无实际place准入。
- verdict：当前旧物理检查与新 M002 基线不相容；以下最小诊断方案符合当前合同。
- applicability：E001 最终专属 DDR 源，VCU118 / xcvu9p-flga2104-2L-e / Vivado 2025.2 / core100、DDR UI200；本文件不证明综合、时序或上板通过。
- review：内部策略建议，交父主控整合；没有新增用户逐次批准门，没有用户最终验收。

权威：[当前执行合同](../../../../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md)、[E001 R003 工程报告](../../../../E001_m002_repair_quick_validation/experiment_results/runs/R003/worker_report.md)。本次只读 E001 三摘要、M002 阶段报告及当前物理入口的相关部分，不扫描旧工程或恢复旧任务；未执行 EDA，未改 RTL、脚本或 XDC。

## 1. 已核实的入口冲突

| 入口 | 当前行为 | M002 处置 |
| --- | --- | --- |
| `build_vcu118_board.tcl` 开头 | place/route 显式拒绝尚未适配的 M002 检查 | 由 A006 在新综合网表后接入当前检查；此技术拒绝不代表器件不可布局 |
| `mission0005_require_partition` | 要求旧 Pblock、USER_SLR_ASSIGNMENT、固定 SLR 与 1632/272/1536 DSP 分区，以及分区内所有叶子不跨 SLR | 不作为新基线验收；保留历史原件，不加载旧分区 XDC |
| `mission0004_require_metadata` | 要求 16 width、672 metadata / 752 board URAM、旧地址寄存器数及固定软 Pblock 成员 | 真实实例和资源重新报告；旧精确数目只能作待核对线索，不能未经新网表核验当要求 |
| place 后报告 | metadata 报告调用旧 floorplan 检查；evidence emitter 要求这些旧报告存在 | 改为当前层级/资源/时钟/拥塞/路径报告；不能制造空旧报告让 emitter 通过 |
| route 入口 | 同输入 marker 加 `s3_screen.txt decision=PASS` | 用明确 M002 diagnostic admission 语义；既有 S3 生产签核含义保持，不写伪 PASS |
| route 终态 | setup/hold 为负时，在独立 `routed.dcp` 写出前报错 | 先保存工具完成产生的 DCP、完整报告及负 slack，再分别判执行、可诊断性和最终时序 |
| 输入身份 | `source_files` 将 build/run/emitter 与 RTL/XDC/BD/XCI/ROM 等共存同一个 manifest | 保留旧 manifest 全体证据；后续物理脚本 provenance 与综合设计身份须有明确 lineage，不能笼统忽略脚本差异 |

对应源码：[builder](../../../../hardware/vivado/scripts/build_vcu118_board.tcl)、[launcher](../../../../hardware/vivado/scripts/run_vcu118_board.sh)、[emitter](../../../../hardware/vivado/scripts/emit_current_board_evidence.py)、[旧分区检查](../../../../hardware/vivado/scripts/mission0005_coordinated_physical.tcl)、[旧 metadata 检查](../../../../hardware/vivado/scripts/mission0004_metadata_physical.tcl)。历史 1929 terminal 和 native025 ECO 图签名同样不进入新 M002 基线。

## 2. 最小诊断链和不可删除的检查

1. **fresh synth 完成**：实际 run 完成且非 stale、原退出码和完整日志、顶层/核心/子 IP synth 全部有效；保存实际综合 DCP hash、原 inputs/identity/marker 和所用工具身份。仅 marker 文件存在不够证明所用 DCP。
2. **设计与板级连接**：保留 part/board/top/defines、所选 RTL、两 ROM pin/hash、有效 XDC、BD/XCI 和 IP cache 策略核查；保留专属 DATA/WEIGHT 与 Host 到 DDR0/DDR1 的实际连接、两个 core100→UI200 的 CDC 时钟及地址空间核查。无 blackbox、无未解析模块、实际资源不超过器件可用量。LUT/FF/DSP/BRAM/URAM 以当前报告为准，不硬编码旧分区数量。
3. **真实时钟与覆盖**：保留 PCIe 10 ns 主时钟及 core 10 ns 生成时钟、两个 DDR 4 ns 输入及 UI 5 ns 生成时钟、三组实际 clock-family 非空且互斥、LATE CDC XDC 顺序。保存 `check_timing -verbose`、时钟和交互、exceptions coverage、CDC 报告；缺必需时钟、关键路径无时钟、未解释的约束缺失不得显示检查 PASS。合法 IP 例外必须有对象/来源，不能按名字宽泛加入 false path/multicycle。
4. **opt → place → phys_opt**：首次使用工具自主布局，保持现有 100 MHz 目标和合法板级/IP 物理约束；没有证据不加用户 LOC/Pblock/SLR ownership。保存每一阶段 checkpoint、运行设置、DRC、时序和资源。物理 primitive 置于合法 site 的判断服从实际网表原语/工具 DRC；不能以所有层级 cell 都有 LOC 的错误规则误判。
5. **诊断 route**：只从当前同源、同约束、同器件的真实 completed phys_opt checkpoint 延续。负 setup/hold 允许带 FAIL 值进入本次诊断 route；输入变化、stale/空 checkpoint、缺时钟、容量不可实现、黑盒或真实 DRC error 不允许靠 diagnostic 标签跳过。已有 pre-route RTSTAT-13 仅在其含义确为尚未布线时保留为阶段预期，route 后必须按真实路由状态再判断，不能作永久 waiver。
6. **最终报告**：保存 WNS/TNS、WHS/THS、setup/hold 违例端点数、每时钟组最差路径的起止点/clock/逻辑与 net delay、LUT/FF/DSP/BRAM/URAM、SLR 使用和跨越、拥塞、路由完成率、DRC/CDC/约束覆盖。时序报告已有字段直接提取；不存在的字段写未取得，不推算成测量。post-route DCP 和 hash 在数值 verdict 之前保存。

不要求为了第一次诊断重复全套 E001 功能验证。输入/语义未变时引用 E001 各 AT 和 hash；RTL、时钟/接口或数值合同如发生变化，明确重验受影响范围。BD 的四条地址别名 critical 和 reset 告警始终保留。已生成的 SmartConnect 译码支持 Host `0x80000000+local` 与 core local 的解释，但不是事务验证或正式豁免。CDC 的未知/unsafe 交叉须列对象和处理结论，不能用异步 clock groups 或报告存在冒充安全；未完成的功能补证保持最终验收 HOLD，可按合同与诊断物理工作并行。

## 3. 建议的最小身份接口

**主控已采纳的实现策略**：原 create/build/run/emitter 综合入口保持字节不变，新增 M002 physical runner/Tcl/evidence helper。物理阶段逐行验证原 `inputs.sha256`（包含原脚本），原 `build_identity.txt` 与综合完成标记不变；新物理脚本另存 `stage_inputs.sha256`，再绑定实际综合 DCP hash。这能遵守先综合后适配的顺序，又不需要降低原身份检查。父主控已通过实际消息确认并通知 A006；这是合同内工程选择，不冒充新增用户决定。

如果工程确需原位修改旧脚本：先保存旧脚本和 diff，最多把 `build_vcu118_board.tcl`、`run_vcu118_board.sh`、`emit_current_board_evidence.py` 三个明确路径的物理运行变化归 stage provenance。`create_vcu118_board.tcl` 继续全 hash 匹配；RTL、源清单、有效 XDC、BD/XCI、ROM、board XML/pins/preset、top/defines/part/clock 均保持完整一致。对改动的 builder/launcher 还必须证明综合分支、源选择、ROM/cache 和综合参数没有语义变化，可保留未改综合代码片段 hash/diff，并核对实际 synth FLOW、STRATEGY、STEPS.SYNTH_DESIGN.ARGS 和有效 fileset 属性。不能按扩展名排除所有 Tcl/Python。原 manifest 不重写；任何非物理 runner 的有效设计/综合设置变化仍须重综合。

建议 completion/admission 记录至少包含：

```text
schema = m002_physical_diagnostic_v1
mode = diagnostic
stage = physopt | route
execution_state = completed | failed | resource_stopped
diagnostic_eligible = true | false
timing_verdict = PASS | FAIL | NOT_EVALUABLE
physical_signoff = false
project, part, tool_version
synth_manifest_sha256, synth_identity_sha256, synth_checkpoint_sha256
stage_inputs_sha256, effective_implementation_settings_sha256
parent_completion_sha256, checkpoint_sha256
clock_coverage, drc_disposition, cdc_review_status
wns, tns, whs, ths, setup_failing_endpoints, hold_failing_endpoints
```

字段可用 Tcl dict 或 JSON，不强制具体新文件名。launcher 原 exit、工具原 exit、资源中止原因独立保存；`execution_state=completed` 与 `timing_verdict=FAIL` 合法共存。diagnostic marker 不能替换 S3、routed signoff 或用户验收凭据。

## 4. 首次实验和集中审核判断

首次实验只检验当前网表在既定器件/时钟上能否合法放置、路由及暴露主要瓶颈，不承诺正 slack。不要同时修改 DDR 拓扑、流水或随机尝试许多 directive/seed，使失败失去可解释性。先复用工具默认或已明确记录的单一 directive；资源/时间遵守合同：单路 EDA、进程树总 8 logical CPU、nice 5、RSS 192 GiB、MemAvailable 48 GiB/30 s、磁盘 30 GiB，create 30 min、synth 3 h、place/phys_opt 2 h、route 2 h。

| 证据 | 可作的结论 | 不能作的结论 |
| --- | --- | --- |
| fresh synth 网表和资源/告警完整 | 当前设计可综合，资源/时钟/告警获得实证 | 功能/CDC/时序/上板已通过 |
| 当前合法 placed DCP，身份/时钟/DRC 合格，slack 为负 | 诊断 route 可继续；负值原样保留 | S3 PASS、最终时序通过 |
| route 工具完成且 DCP 可核验，路由/DRC 完整 | 已取得首次物理基线；可分类关键路径 | 只凭 exit 0 判全局签核 |
| routed setup/hold 非负 | 指定约束下该时序项目通过 | 忽略覆盖、pulse width、CDC、DRC、未决告警或全局 +0.5 ns 余量目标 |

最终 +0.5 ns margin 的长期目标和本轮首次诊断相区分；即使非负，仍应报告距长期目标的差额。日常路径/解析/构建错误由 A006 连续修复；实质架构/时钟/数值变化或不可在合同内解决的阻塞才升级父主控。

## 5. 实际阶段验收

初次策略交付时 fresh create/synth 由 A006 准备/执行，尚无新结果。以下按真实阶段追加；先前待核验状态不覆盖后续证据，亦不预填最终 PASS。

A004 已通过实际消息给出 reset 源级初结：29 条历史展开 warning 来自 payload/tag 在含 async reset+clear 的 always 中无 reset 赋值而仅 enable 更新；valid/count 具有 reset > clear > enable。源级未发现同优先级 set/reset 或多驱动，但存在不能一概用 valid 屏蔽解释的例外：accumulator lower/upper `head_wave` 会影响 `ready`，而 `lockstep_error` 对 ready 不等无条件采样。虽然首 enqueue 后同源/同 CE 可支持两者一致，power-up/空队列阶段仍需 fresh netlist 的 INIT、合并和 CE 证据。此为待判风险，不是已证实实现错误；详见 A004 的独立 `reset_warning_review.md`。没有因源 hash 未变而宣告安全，也没有修改冻结源。

沟通：本文件主要策略、身份方案和异常已通过 collaboration 实际消息发送父 `/root` 与 A006；文件写入本身不是通知。共享摘要、索引和最终 M002 结论由父维护。

### 5.1 AT002：子综合完成，主流程仍在 link/report

2026-10-15，父/A006 已报告 22 个 OOC 加 top 共 23 个 synth run 完成，AT002 控制进程仍在 `open_run`、link 和生成报告。审核读取的 [AT002 日志](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/vivado.log) 796–802 行记录 top DCP 已写出、top synth 结束并准备打开设计。这只证明子阶段，不能将完整 AT002 标为 completed 或签核。

已独立核对 [core utilization 原报告](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.runs/scalellm_vcu118_f05_bd_core_0_synth_1/scalellm_vcu118_f05_bd_core_0_utilization_synth.rpt)：

| 核心资源 | 使用 / 器件总可用 | 比例 |
| --- | --- | --- |
| CLB LUT | 755296 / 1182240 | 63.89% |
| CLB FF | 892881 / 2364480 | 37.76% |
| DSP48E2 | 5445 / 6840 | 79.61% |
| Block RAM tile | 844 / 2160 | 39.07% |
| URAM | 752 / 960 | 78.33% |

该表是 **core OOC**，不能替代完整板级 linked utilization。报告另有 19094 unique control sets 和 0 latch；仅从总量看未发现 core 超容量，但 DSP/URAM 的余量与真实 SLR 分布、时钟/控制/拥塞仍需完整板级报告和物理实证。不能据此断言可布局或时序可收敛。

**Designutils 20-1307 告警判读**：实际位置为 [ddr_timing_recovery.xdc 第9行](../../../../hardware/vivado/constraints/ddr_timing_recovery.xdc)。1–8 行全是注释，第9行只有打印 clock-policy 的 `puts`，文件没有 `create_clock`、`set_*` 或其他有效约束。AT002 日志 588–595 行明确显示拒绝 puts 后 `Finished Parsing XDC File`，继续读取 `dont_touch.xdc` 和 `board_clock_domains.xdc`，随后 `Completed Processing XDC Constraints`。因此当前证据支持“无约束效果的打印命令在 XDC 中被拒绝”，没有该文件的实际时钟/时序/位置约束丢失，也没有此处中止后续 XDC 的迹象。

此 critical 原样保留，不降低 severity，不把综合称为无 critical 签核。当前不修改冻结 XDC、不覆盖339输入manifest，也不为去掉该打印而重综合；未来新基线可将提示移至普通 Tcl 或改成注释。本次 physical flow 若再次报告同一条，应继续明确分类。该结论只覆盖这条 puts 告警，不豁免其他 XDC 解析错误、对象空匹配或时钟缺失。

**综合与物理约束边界**：AT002 日志 584–587 行显示 board DDR pins 的 implementation-specific 约束会在综合中忽略、implementation 使用，相关项记录在 `*_propImpl.xdc`。冻结 [build_identity](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/build_identity.txt) 第583行还明确登记 PCIe `ip_pcie4_uscale_plus_impl_x1y2.xdc` 为 `USED_IN_SYNTHESIS=0`、`USED_IN_IMPLEMENTATION=1`。实际 XPR 的 `impl_1` 关联 `synth_1`、`constrs_1`，board_clock_domains 的 PROCESSING_ORDER=LATE。以上是后续必须走 project implementation init/link 流程的具体依据；裸打开综合快照不能声称实现专用约束已经应用。

物理准入需补充且保留：原339项输入逐行验证；全部23 run DCP与 `.gen` 实际消费 DCP 的路径/hash对应；另存 linked-synth DCP作快照；有效implementation XDC的路径/hash、完整 USED_IN（不只两个布尔值）、PROCESSING_ORDER、SCOPED_TO_REF/SCOPED_TO_CELLS、启用属性和实际读取顺序。文件 registry 是候选清单，不能单凭文件名或 USED_IN 布尔值认定当前作用域已加载，尤其 OOC 约束。新物理脚本和 settings 单独绑定此 lineage。由 A006 通过 project impl flow 完成 init/link/opt 后再检查实际时钟/CDC/DRC，不以 linked-synth 快照冒充已完成的 implementation 初始化。

当前集中准入状态：**待完整 AT002 终态、linked资源/clock/CDC/DRC、DCP/约束身份及 A004 head-wave 网表 probe**。以上待证据不新增逐次审批；A006 可连续完成合同内报告、probe和物理入口适配，任何实际结构/时钟/DRC阻塞再单独报告。place/route 未有本审核可验收结果。

### 5.2 已有完整板级报告：诊断 init/opt 与 place 分开判定

本次只读复核时 AT002 controller 尚未交付原始退出/完整终态；下列是真实已生成报告，不能把报告存在等同整个 AT002 完成。

[完整板级 utilization](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/utilization_post_synth.rpt) 为 LUT 841576（71.18%）、FF 1029313（43.53%）、DSP 5451（79.69%）、BRAM tile 945（43.75%）、URAM 752（78.33%）。整体资源未超总容量，但报告的 Black Boxes 节明确列 **dbg_hub_CV × 1**，所以当前不能写“0黑盒”。[AT002 日志](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/vivado.log) 832–833 行有两 MIG debug core UUID，836–837 行确实已在当前 `open_run/link` 读取 PCIe `impl_x1y2.xdc` 并给出实际 scope；这比 §5.1 的 registry 证据更强，但后续 implementation 仍需记录实际读取和作用域，不能仅凭此一份文件推定全部约束加载完备。

[时序报告](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/timing_post_synth.rpt) 为未布局估计：WNS +0.904 ns、TNS 0、setup failing 0；WHS −0.814 ns、THS −49355.641 ns、hold failing 1000183；WPWS −0.012 ns、TPWS −0.037 ns、PW failing 5。工具明确写 `Timing constraints are not met`。最差 WPWS 在报告2501行是 **Max Skew**：`GTYE4_CHANNEL_TXOUTCLK[3]_1` 下固定 `PCIE40E4_X1Y2` 的 `CORECLKMIREPLAYRAM0` 相对 `CORECLK`，required 0.436 ns、actual 0.448 ns；不是已经证明五条均为 high/low pulse 不足。需补全 pulse-width/skew violators 类型。以上负数允许保留进入有界物理诊断，不能作最终时序 PASS，不能靠改100 MHz目标或覆盖vendor约束消除。

[check_timing](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/check_timing_post_synth.rpt) 的逐对象有界分组结果：

| 项目 | 真实对象范围 | 当前结论 |
| --- | --- | --- |
| no_clock 530 | 两个 `dbg_hub/sl_iport*_o[1]` 根，各265；其中 U_XSDB_SLAVE 共426、u_xsdb_arbiter 共104 | 与工具 debug hub 待物化存在结构关联；未证明已被合法时钟覆盖 |
| unconstrained internal endpoints 554 | U_XSDB_SLAVE 共466、u_xsdb_arbiter 共88，全属两MIG这些层级 | 两个统计集合对象/引脚不同，554−530不能理解成24个额外核心数据端点；层级名称不能替代实际连接证明 |
| no_input_delay 1 | `pcie_perstn` | 外部复位候选，需核查实际接收链和有效异步复位合同，不能盲补0 delay |
| no_output_delay 2 | `ddr4_sdram_c1_reset_n`、`ddr4_sdram_c2_reset_n` | MIG外部复位候选，需核查实际驱动和适用reset时序依据，不能按名字豁免 |
| multiple/generated clock、loop | 报告均0 | 仅对应检查通过，不推出全部时钟/约束覆盖通过 |

[默认 DRC](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/drc_pre_impl.rpt) 合计15927条，全为 Warning：DPIP-2 7275、DPOP-3 5192、DPOP-4 325、DPREG-7 3072、REQP-1858 22、REQP-1877 9、REQP-1935 32；此 ruledeck 无 Error/Critical。保持 warning 原文；DSP流水提示和BRAM碰撞建议分别属于性能/访问语义，不能把“无DRC blocker”改写成无告警或功能全绿。

**准入结论**：支持在现合同内进行 **诊断性 project init/opt**，以真实工具对象身份确认并物化唯一 debug hub 占位，再取得覆盖证据；该结论不允许未解析黑盒直接进入 place。INIT probe 至少绑定唯一黑盒的实际cell/ref、`get_debug_cores/get_debug_ports`对象和属性、hub clock连接/root与MIG XSDB关联及工具插入来源。满足此有界来源核验时，记录 `diagnostic_opt_eligible=true`、`blackbox/clock_coverage=PENDING`；不将其写为黑盒检查 PASS，也不使用仅按名字匹配的宽泛allowlist。

OPT POST 为自动的 place 前技术检查点：先保存DCP/报告，再全设计重查未解析blackbox、no_clock、unconstrained internal、真实时钟/作用域、DRC。仍存在未知黑盒、未解释的缺钟或真实DRC blocker则停在place前保留证据；如果工具占位已完成解析且覆盖得到证明，可依合同连续推进，不增加人工逐次放行。明确识别的外部reset IO仍须逐对象记录适用时序/同步方式，不能藏入一个“debug已解决”总标志。A006 已实际消息确认采用同一project流程中的 INIT probe → OPT自动检查 → place/phys_opt hooks，避免多次开大网表；每阶段DCP先于数值判定。

**CDC及局部约束最小查询清单**（A006唯一执行，A007只读审核）：

| 范围 | 需要补的最小实际证据 | 判读边界 |
| --- | --- | --- |
| CDC-10的两个core ready路径 | 每DDR `calib && !ui_reset` 的实际组合cone/源时钟；core_gate两个XPM全部4级的C、CLR、D、ASYNC_REG、INIT、输出扇出及同步释放 | 源码的4级 `xpm_cdc_async_rst` 是意图；源端组合复位、无glitch/稳定性假设和实际同步释放必须分开。不以XPM名称自动豁免，也不需把整个核心重做CDC扫描 |
| CDC-10的四个SmartConnect AUX路径 | d0/d1 gate的组合AND输入、psr0/psr_aclk1 AUX极性与实际同步链/目的clock；确认无同步释放旁路 | 六条全部是reset交叉，不是直接证明6条功能data CDC错误；未核验仍保持Critical/开放 |
| CDC-15共6198 | 先按目的family分桶：native FIFO368、d0_smc1383、d1_smc1383、host_split2920、xdma144；各结构族确认FIFO/CE或counter采样协议、同步控制及适用bus-skew约束 | 不逐bit重复扫描，不将全部6198称为已安全；特别区分异步FIFO数据和PCIe频率counter |
| Constraints18-401两条 | 仅d0/d1_smc S00 W request FIFO对应scope，重现原NAME查询的完整目标集合、primitive/IS_SEQUENTIAL、真实DFF端点/时钟与有效max-delay覆盖 | `xpm_memory_xdc.tcl:59`查询同时匹配非端点的 `doutb_reg[0]_i_1`；须证明合法端点仍获有效约束，不能仅因vendor脚本来源忽略 |
| PW/skew与bus-skew | 全部PW失败的类型/端点、实际clock source/waveform与专用bus-skew报告 | 最差已知为PCIe Max Skew；本阶段数字原样保存，route后重新判定 |
| A004 head-wave例外 | actual INIT、合并或同D/CE及ready→lockstep cone | 沿用 §5.1 / A004有界检查，不因本轮clock问题把该项关闭 |

上述 CDC-10 六行原证据见 [AT002 摘录](../R001/attempts/AT002_fresh_synth/cdc_critical_rows.json) 和 [CDC原报告](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/cdc_post_synth.rpt)。源码已核实 core ready 两路各自同步后相与，`make_ready`构造calib与反相ui_reset；此结构有意异步assert、同步release，源端组合逻辑触发CDC-10仍有明确核查价值。实际连接/控制稳定性未核验前，不对“6条可全部关闭”作结论。诊断init/opt可用于获取这些对象证据；进入place前应完成有界分类，真实不安全的控制/时钟结构不得靠报告标签放行。

这些判断和最小查询已通过实际消息给父及A006。当前仍是 **物理诊断准备/取证可继续，place准入待OPT与局部probe结果，最终签核HOLD**。

### 5.3 AT002 真实终态与物理入口草稿首次语义审核

已读 [synthesis_stage_facts](../R001/synthesis_stage_facts.json)、[受管原status](../R001/attempts/AT002_fresh_synth/status.json)、[原launcher退出](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/launcher_status.txt) 和 [综合完成marker](../../../../hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/fresh_synth_complete.txt)：AT002 从2026-10-15 00:50:07.610325 UTC运行至02:44:24.353986 UTC，共114.279分钟，native/overall exit均0，stop_reason为空，owned_survivors=[]。因此 **正式综合生成与报告流程 execution=completed**；带前述warning、debug占位和时序FAIL，不能称综合后物理/功能签核通过。该终态更新取代 §5.1–5.2 写作时的controller进行中状态，不删除当时观察。

独立重算facts所指六个身份记录文件的SHA256（源manifest、build identity、marker、DCP manifest、DCP bindings JSON、managed status）均与facts一致；源manifest确为339行，checkpoint manifest确为45行，原marker的project/inputs/identity与实际对应。本次仅重算身份记录文件，未声称重新读取/验证全部45份大型DCP内容；逐DCP检查由工程入口完成。

新物理代码由A006单一编写，本次有界只读对象为 `run_m002_physical_stage.py`、`m002_physical_evidence.py`、`m002_diagnostic_common.tcl`，以及本轮期间补出的 `m002_physical.tcl` 和各POST hooks。读取时属于草稿，未启动新EDA，不以未完成代码预填PASS。已支持的实现方向是：冻结旧综合入口/339输入，新stage脚本另存snapshot与manifest；每hook先写真实DCP再做检查；工具运行状态与timing verdict分开；`physical_signoff=false`；沿同一project impl run推进。负slack不再触发伪S3门。

首次集中审核给出的具体修正项如下，均已实际消息通知A006和父；A006已接受连续修复。表中保留最初发现的问题，最终静态处置已更新；CPU验证与实际工具边界见 §5.4，不新增逐次批准门。

| ID | 草稿读取时的具体问题 | 必要修正 / 最终复核点 | review |
| --- | --- | --- | --- |
| C1 | `synth_lineage`核验manifest已有行及23/22记录长度，但未要求339/45全集，未把所有consumed-IP路径及project/status严格关联 | 原339源及45 DCP完整集合；23 run与22 consumed唯一并集与DCP manifest完全相等；对应project、原status、marker和receipt一致，缺失/重复/串项目均拒绝 | 静态修正已核；验证范围见 §5.4 |
| C2 | INIT例外只看黑盒ref与部分debug扇出；缺钟parser可跳过不匹配行并对空集合返回true，其他clock异常也可能随debug例外继续 | 实际blackbox cell与debug core/ports关联，完整端点计数且每个端点归属已证实hub扇出，未知/遗漏拒绝；INIT的multiple/generated clock、loops等独立为0；OPT继续要求已解析黑盒和实际覆盖 | 静态修正已核；验证范围见 §5.4 |
| C3 | OPT→place只核内部coverage/DRC；CDC/reset IO硬写OPEN而没有未知Critical或新IO对象门 | 完成已识别6条reset CDC与3个IO的有界probe/结构分类，实际Critical集合须精确核对；新未知CDC/IO/控制问题停止在place前。OPEN可描述最终功能签核仍开放，不能代替技术准入条件 | 静态修正已核；验证范围见 §5.4 |
| C4 | route parent仅核数据文件及checkpoint hash，尚缺当前impl run非stale、真实physopt receipt/无error和原退出一致性 | route只续同run、同源、实际完成physopt原生DCP；核parent launcher真实exit0、当前run/step状态与receipt及稳定implementation settings，归档源码内容与manifest相符 | 静态修正已核；验证范围见 §5.4 |
| C5 | registry XDC只逐阶段保存hash，339输入不涵盖所有generated/IP XDC；后续阶段和route未必验证这些有效约束继续不变 | INIT已记录约束的字节与USED_IN/scope/order/启用状态跨阶段绑定；OPT合法新增tool-debug约束单列来源，不泛化允许差异；route验证parent最终约束manifest与当前project metadata；实际读取日志保留 | 静态修正已核；验证范围见 §5.4 |
| C6 | timing verdict仅按WNS/WHS/WPWS>=0，可误认显示−0.000但失败端点非0的报告；route只验证status报告存在 | timing PASS同时要求所有失败数为0、总违例/最差值非负且数值有限；路由完成/未布线/error数量单独提取。execution完成可与timing FAIL或诊断route不完整并存，不能仅凭文件存在写route complete | 静态修正已核；验证范围见 §5.4 |

C4中的历史stage provenance应验证不可变归档和旧manifest文件身份；不能重新要求旧manifest所指的所有live物理脚本仍是旧字节，从而无故阻止合法的route-only普通脚本修复。新route代码另存身份/差异，旧实际执行代码snapshot仍可复核。相反，综合设计/339输入和有效约束不能借此规则改变。当前未修改任何实现或运行EDA；完成草稿修复与CPU负例后再对最终差异集中补验。


### 5.4 物理入口最终差异审核与 R002 AT004 CPU 证据

集中复核仅针对 §5.3 C1–C6 及最后四处差异，没有重新展开功能签核或逐bit CDC调查，没有执行EDA、改实现或XDC。A006交付 [AT003 status](../R002/attempts/AT003_physical_diagnostic_cpu/status.json) / [44项原日志](../R002/attempts/AT003_physical_diagnostic_cpu/tests.log)，随后保留该次证据，另存 [AT004 status](../R002/attempts/AT004_physical_diagnostic_final_cpu/status.json) / [最终47项日志](../R002/attempts/AT004_physical_diagnostic_final_cpu/tests.log)。AT004从2026-10-15 03:20:11.825542 UTC至03:20:13.743566 UTC，exit0；测试日志明确为 `Ran 47 tests ... OK`。

独立重算 [AT004当前输入manifest](../R002/attempts/AT004_physical_diagnostic_final_cpu/inputs.sha256) 的15项脚本/测试及 [归档manifest](../R002/attempts/AT004_physical_diagnostic_final_cpu/archived_sources.sha256) 的15项文件hash，均与manifest一致；原执行字节保存在 `source_archive/`。A006的 [实际综合身份复核](../R002/attempts/AT004_physical_diagnostic_final_cpu/frozen_synthesis_verified.json) 记录339项源及45条DCP路径核验完成；本审核没有重复读取全部大型DCP，也不将“记录存在”替代A006执行所得检查。

C1–C6的最终静态处置为：C1要求339/45全集、23/22唯一且对应的DCP并集及原project/status/marker；C2限定INIT实际工具debug对象/端口及完整端点扇出，OPT不继承缺钟/黑盒例外；C3核未知Critical/IO及7条四级异步reset链、4条AUX链的真实primitive/连接/极性；C4核parent原launcher/supervisor、原生physopt DCP、完成receipt、非stale run和归档代码；C5跨阶段核约束字节及USED_IN/scope/order/enabled；C6核有限时序数值、所有失败计数和实际路由数量。相应正负例已纳入AT004；这些是入口实现和CPU验证结论，不是对真实目标网表的结构PASS。

最后差异的明确复核结果：

- reset IO分类使用当前实际构造层级 `rst_core/rst_ddr0/rst_ddr1`、`xdma_0`，已纠正旧的 `rst_d0/rst_d1` 与 `xdma` 字面值；结构fixture覆盖当前命名，INIT反向、AUX极性错误、断链及未知PCIe接收者均拒绝。
- CDC不仅要求真实report header，还逐类核对summary `(ID, severity)`计数与detail计数、Critical唯一性及已知六条集合。此前“在首条Info summary截断即返回零Critical”的具体漏洞已修复，含该截断负例和真实zero-critical正例；这只是报告完整性解析，没有把6198条Warning逐bit结构重审或宣告安全。
- route恢复physopt checkpoint时允许本轮actual XDC reads为空，明确写 `checkpoint_inherited` 并绑定父checkpoint、约束manifest和实际读取证据；不伪造本轮Parsing行。父证据hash变化会拒绝，INIT仍要求真实XDC读取。新正例/篡改负例已通过。
- place重试可接受同项目、具有前次M002归档provenance的自有hooks，仍拒绝foreign hooks；`reset_run`保留hook不再无故阻断普通修复后的新AT。

专用 `pulse_width` / `bus_skew` 报告均为必需产物。时序summary的WNS/WHS/WPWS、总违例及setup/hold/PW类别失败计数共同判断，显示−0.000但失败数非零不能PASS。即使summary为PASS，总 `timing_verdict` 仍为 `NOT_EVALUABLE`，`bus_skew_review=OPEN`、`physical_signoff=false`；已有负值则总判定FAIL。专用bus-skew或PW/Max-Skew的未知/失败不能被摘要PASS覆盖，后续实际报告仍须独立判读。

**阶段处置**：在AT004所绑定代码上，集中审核未见剩余明确的诊断INIT/OPT入口阻断或不安全放行项，支持A006沿已有合同启动R003，不新增用户批准门。真实Vivado命令语义、对象/层级匹配、debug物化、OPT零黑盒/零内部覆盖缺口、reset有界结构、实际约束和DRC仍须由运行证据证明；任何未知保持未知，普通入口错误另存尝试连续修复。进入place仍以真实OPT自动检查为必要条件。head-wave、Constraints18-401合法端点覆盖、CDC-15结构族、PW/Max-Skew和bus-skew审核保持原有范围和开放状态，不能用本次CPU通过关闭。

沟通：以上差异与无剩余静态入口阻断结论，已通过实际collaboration消息通知父 `/root` 和A006；父整合阶段记录及用户说明。本文件不替代真实INIT/OPT/place/route验收或用户最终验收。


### 5.5 R003 AT002：实际 INIT 中间证据与限定 debug 例外

本节为运行中的阶段观察，证据根 [R003 AT002报告目录](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt)。读取时 `init.dcp` 已生成（225530517 bytes），`init_result.txt` 仍为 `completed=0`、`diagnostic_eligible=0`、`blackboxes=1`；reset/head-wave/XPM等探针仍生成中。文件存在不能代表INIT hook、整个AT或物理阶段已完成。

独立核读 [blackboxes_init.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/blackboxes_init.tsv)、[debug_init.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/debug_init.tsv) 和 [check_timing_init.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/check_timing_init.rpt)：唯一cell为`dbg_hub`/`dbg_hub_CV`，live `get_debug_cores`含该hub及两个具有独立UUID的MIG core，`get_debug_ports`含实际`dbg_hub/clk`。两个`sl_iport0_o[1]`/`sl_iport1_o[1]`各有265个实际clock fanout，总530；完整530个no_clock对象与该fanout集合一致、没有范围外对象。554个unconstrained internal端点所属cell均在同一fanout cell集合；没有用554−530推导额外功能端点。`debug_proof_init.txt verified=1`与这些原对象记录一致，本次有界证据支持工具debug占位的限定诊断OPT例外，不支持把黑盒/覆盖记PASS。

[clocks_init.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/clocks_init.rpt) 实际core周期10ns、两DDR UI各5ns；multiple/generated-clock/loop/pulse_width_clock检查均0。hub输入为DDR1 MMCM `CLKOUT5`生成的`mmcm_clkout5_1`，周期20ns（50MHz）。同时debug属性`C_CLK_INPUT_FREQ_HZ=300000000`、`C_ENABLE_CLK_DIVIDER=false`；记录此属性/真实时钟差异，不能按属性声称hub输入300MHz。尚未证明该属性在禁用divider时有实际物理影响；不据此修改冻结约束或中止有界物化，OPT后保留真实hub时钟/属性/DRC再判。两方已收到此观察。

[vivado.log](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/vivado.log) 135–136行有PCIe `impl_x1y2.xdc`的实际读取及`xdma_0/inst/pcie4_ip_i/inst` scope；338–339行有`board_clock_domains.xdc`实际读取。原`ddr_timing_recovery.xdc` puts Critical仍在318行原样保留。project与init的162项XDC registry字节相同；独立重算`constraints_project.json`中162项文件hash全部一致。INIT阶段hash/actual-read正式产物尚待hook完成，registry一致本身不代替有效约束及后续跨阶段检查。

[INIT timing](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/timing_init.rpt) 与综合报告一致：WNS+0.904/TNS0/setup failing0，WHS−0.814/THS−49355.641/hold failing1000183，WPWS−0.012/TPWS−0.037/PW类别failing5。实际INIT默认DRC仍为15927条Warning（七类数量同§5.2），无Error/Critical DRC；不把XDC Critical或功能warning随此关闭。全板资源仍为LUT841576、FF1029313、DSP5451、BRAM945、URAM752。

当前判定：**限定debug来源和缺口归属已得到INIT实证，支持继续诊断OPT；INIT完整准入、OPT黑盒解析与内部clock coverage、reset CDC/IO结构及XPM/PW/bus-skew仍待完整产物。place未获实际准入证据。** 未添加人工批准门、未运行EDA或修改实现；实质观察已实际消息通知父和A006。


### 5.6 R003 AT002 失败终态与真实 project-init DCP 恢复边界

[AT002受管status](../R003/attempts/AT002_project_init_opt_place_physopt/status.json) 已终结：2026-10-15 03:23:12.371486 UTC至03:59:05.832424 UTC，native/overall exit均1，stop_reason为空、owned_survivors=[]。原 [child log](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/implementation_run.log) 03:58:53 UTC在INIT POST报 `CDC probe target missing: ...core_gate/inst/u_ready0_cdc/arststages_ff_reg[0]/CLR`，未执行OPT。失败发生在对象查询；尚未证明目标设计缺失或reset结构错误，CPU glob字符串测试不能代替实际Vivado查询语义。旧init_result保持0，旧impl_1/AT002失败不改写。

独立重算实际`init.dcp` SHA256为 `3a8e4ab2b407cc9796d24bc39ada8be48897da270e4757856262a34bfbd17d46`。它是完整project link并应用implementation约束后、INIT POST开头写出的真实状态，不是原top synth DCP；其生成日志在失败前明确成功。已完整关闭的register探针有27类、492459 bytes，SHA256为 `bcba4640edb748e24011900a091ea96bcacc70637ae6bde68bee73fda940a47b`。A004 [reset专项报告第5节](reset_warning_review.md)确认这27类对应29条消息去重后的类名；对指定center12/region2 accumulator，INIT0 FDRE的同一head Q实际驱动两侧ready，排除了该实例独立head初值01/10反例。D/CE选择、tail→head与完整lockstep cone仍NOT_RUN，不能关闭全部reset告警。

**恢复建议与决定来源：**A007推荐在新AT修复对象查询并从该真实project-init DCP自管恢复，主控已通过实际消息采纳并写入 [当前合同物理判断段](../../../../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md)。这是现授权内技术实现选择，未声称用户另作批准；资源/时间上限、设计与时钟语义不变。不必因后置查询失败重综合或无条件重复整个project init，但以下证据必须成立：

1. 绑定原failed launcher/managed status/child log、原执行代码归档及manifest、DCP生成日志/阶段/path/hash；原失败run不补造成功receipt。六个综合anchors、339源和45 DCP继续验证，新helper另存代码身份。
2. 从原child log补出真实Parsing XDC顺序和scope，绑定162项原registry完整元数据和字节hash；原`actual_xdc_reads_project.json`为空候选阶段记录，不能代替真实加载日志。恢复前原来源不变。
3. 实际打开checkpoint后核tool/design/part/top、blackbox/live debug对象、clock及缺口归属、有效exceptions；标记`embedded_checkpoint_inherited`。原project候选registry、checkpoint内有效约束、本轮真实读取分别记录，不重放vendor XDC来伪造相同效果。若加载改变实际对象/时钟/约束或丢失debug元数据，应先修正或回到真实project流程，不凭旧marker绕过。
4. 新AT补齐尚未执行的actual CDC、reset IO/结构及局部head-wave、XPM合法端点/例外覆盖；旧INIT结果不覆盖。实际OPT先保存DCP，再检查零黑盒、零内部缺钟/未约束、实际clock/DRC、已知CDC/IO和限定reset结构，满足后才进入place。
5. 新`execution_mode`明确为自管checkpoint恢复；由真实命令exit、阶段完成记录和DCP定义其physopt及后续route父链。不能把新自管成功冒充旧impl_1原生成功；route入口按实际模式核验归档、状态和约束，不伪造native receipt。

**可复用和裁剪的取证：**完整27类寄存器表可按同一DCP身份继承，后续不重复全层级warning扫描；只补A004指定head/tail FF、三个直接driver LUT及2/3级、32/64 cell上限的控制cone，以及两处XPM scope。恢复INIT的timing/check_timing/DRC/util可按同DCP、同phase/hash引用原报告，加载后先确认实际clock/debug/constraint身份且尚未变换。缺失的actual CDC和有效exceptions必须补；7条reset+4条AUX完整结构在真实OPT的place前技术门执行，后续只在变换影响既有证明时重验局部。place/physopt/route仍保存独立DCP和全设计coverage/DRC/CDC未知对象/时序；专用PW/bus-skew至少取得OPT与最终route真实报告，INIT未产出保持未知，不生成最终PASS。有限代表不能变成全量功能安全结论。

上述恢复lineage与取证边界已实际发送父及A006。当前execution为原尝试失败、恢复入口修复中；verdict只支持有条件复用实际INIT证据，尚无恢复工具运行、OPT/place或最终时序通过结论。


### 5.7 恢复入口差异审核与 R002 AT005 CPU 证据

只读集中核查新增`m002_resume_physical.tcl`以及parent/constraint/driver/POST hook的恢复差异，未重审无变化的339源设计。当前新路线先打开原XPR核build identity及候选约束元数据，关闭后打开已绑定INIT DCP；首步六个CDC target使用精确cell `NAME ==`和pin `REF_PIN_NAME`查找，再运行实际coverage/clocks/debug/CDC/exceptions及局部probe。自管`opt_design/place_design/phys_opt_design`使用实际命令结果记录，原project run不补写成功receipt。恢复INIT继承原timing/util/DRC文件并额外执行live DRC，reset完整结构延至真实OPT技术门，未删除place前检查。

[AT005 status](../R002/attempts/AT005_checkpoint_recovery_cpu/status.json) 与 [tests.log](../R002/attempts/AT005_checkpoint_recovery_cpu/tests.log) 记录2026-10-15 04:08:32.868700 UTC至04:08:35.444942 UTC、53项测试、exit0；含failed POST checkpoint复用、错误phase/后续OPT拒绝、原XDC篡改、缺真实reads、旧归档/新helper边界的回归。独立重算 [16项归档manifest](../R002/attempts/AT005_checkpoint_recovery_cpu/archived_sources.sha256) 全部一致。[recovery_parent.json](../R002/attempts/AT005_checkpoint_recovery_cpu/recovery_parent.json) 的INIT DCP hash与§5.6独立核值一致，含162项metadata/hash与52条实际XDC读取顺序/scope。另独立解析原child log，52次读取对应52个不同source，全部在162项pre-link冻结hash registry内，没有实际读取来源缺少该历史hash的情况。

测试后的三处差异已经逐行对照AT005归档核查：Tcl写candidate-project-settings作用域文本、finalize增加相同scope字段、command.json增加实际HAP环境记录。它们没有改变技术门或EDA命令，AT005原证据保持，不声称测试覆盖后加记录字段。A006已实际通知R003 AT003启动，并将最终执行字节独立存入该AT的stage_sources/manifest，启动后没有继续改源。

本次静态结论：未见恢复入口明确不安全放行或INIT/OPT静态阻断；支持已授权的新AT恢复。真实Vivado精确查询语义、checkpoint加载状态及后续OPT结构尚待运行验证，53项CPU测试与新模式标记不能替代这些结果。候选project settings不是自管有效命令设置，实际行为由归档脚本及真实command receipts证明。


### 5.8 R003 AT003：检查点恢复成功，身份预检失败

独立核读 [AT003 status](../R003/attempts/AT003_checkpoint_recovery_opt_place_physopt/status.json)：2026-10-15 04:09:35.150328 UTC至04:19:04.505924 UTC，native/overall exit均1，stop_reason为空、owned_survivors=[]。运行开始后的14项执行归档和36项stage inputs均经本审核独立hash核验一致，没有把AT005后补字段混称为原测试字节。

[AT003工具日志](../../../../hardware/vivado/reports/m002_E002_R003_AT003_checkpoint_recovery_opt_place_physopt/vivado.log) 明确记录binary timing及binary constraint restore完成，`open_checkpoint`成功，耗时9:00，原checkpoint工具build为2025.2/6299465。随后`m002_resume_physical.tcl`第25行的 `current_design PART/NAME` 复合条件报 `Restored design part/top mismatch`；完整properties dump放在该条件后，因此文件未产生，六target和INIT准入均未执行。当前不能仅凭复合错误直接声称已观察到某个NAME值，也不能据此称DCP网表/约束损坏；A006已报告DCP包中的Top/Part/BoardPart/tool正确。

修复集中原则已实际通知父与A006：`current_design NAME`是内存设计对象标识，不能假设等于RTL top。下一次加载后先无条件记录design/project/所有fileset可见properties，再按DCP包身份/hash、所有可得actual PART/TOP及唯一BD根cell/ref、预期顶层ports/方向综合核验。属性不支持或空值明确记录，不将NAME强作TOP。六target的精确cell/pin查询、3 reset IO、3 primary clock family/core/UI周期、live debug对象/扇出、7+4链关键计数、两XPM scope和A004局部计数分别catch并保存全部可得结果，最后统一汇总；任一未知/错误仍不得OPT，但不因首个属性错误丢掉其余独立证据。OPT后才出现的生成debug IP及相关API仍需真实阶段验证。

此处为查询/预检API假设修复，原AT003仍FAIL，未放松设计身份、clock coverage或place技术门，未追加用户审批或扩大预算。


AT003后续修复的独立差异复核：新入口已先保存design/project/全部fileset属性，DCP包身份与actual project PART、可得fileset TOP、唯一BD根cell/ref分开核验；六target与clock/IO/debug异常汇总，7+4 chain、XPM与局部对象计数收齐后才判preflight。未见新增明确不安全准入或INIT静态阻断，计数预检不替代OPT完整结构/coverage门。[R002 AT006 status](../R002/attempts/AT006_recovery_identity_preflight_cpu/status.json) / [tests.log](../R002/attempts/AT006_recovery_identity_preflight_cpu/tests.log) 为2026-10-15 04:23:46.381824 UTC至04:23:48.960648 UTC、55项、exit0；独立重算其16项当前输入和16项归档hash均一致。DCP包记录Part/Top/BoardPart/Product/build符合冻结目标，`dcp.xml` SHA256为`89767b285a4bfa15df61c21efc6fe96baa8c53d9a31a40da9723cc341b0a627c`。A006已通知R003 AT004开始真实恢复，实际属性、查询和OPT结果仍待证据，不用CPU通过预填工具成功。


### 5.9 原生流程核查发现缺失的 debug 实现步骤，修正准入阶段

按主控提出的具体恢复语义问题，只读核对 [AT002原生生成Tcl](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/native_run_receipts/scalellm_vcu118_f05_bd_wrapper.tcl)：第203–219行OPT PRE仅加载线程限制；220–226行OPT前后额外约束段为空，223行仅`opt_design`。**第287–290行在PLACE阶段、`place_design`之前显式执行 `if {[llength [get_debug_cores -quiet]] > 0} { implement_debug_core }`**。当前自管入口仅`opt_design → m002_post opt → place_design`，确实遗漏这一原生显式步骤。

这否定此前“只调用同名opt_design就可按原流程期待hub物化完成”的充分性假设；§5.2–5.8将OPT POST直接作为零黑盒检查点的阶段选择需要修正。并未观察到本设计真实OPT终态，不能反过来宣称opt_design必然不会做任何debug工作；可以确认的是原工具脚本仍要求随后显式implement_debug_core，恢复入口必须保留该步骤和实际证据。先前未见静态阻断的结论现由这一具体遗漏更新，原记录保留，不追写为“早已验证”。

A007已立即实际消息通知父和A006，主控已采纳如下同合同内技术修正，并通知不热改AT004运行中字节：

1. `opt_design`实际完成后先保存原始OPT DCP和报告。若仍有唯一已核工具hub、且所有缺钟/内部未约束缺口均与实际hub扇出对应，可标`PENDING_TOOL_DEBUG_MATERIALIZATION`，只允许进入已知工具debug实现；不得写OPT零黑盒PASS或place eligible。未知黑盒、范围外缺口和真实DRC/控制问题照常阻断。
2. 依原生条件显式运行`implement_debug_core`并保存真实command receipt；随后先写`debug_materialized.dcp`，建立独立`debug_materialized/pre_place`技术检查点。零黑盒、零内部缺钟/未约束、实际clock、DRC、已知CDC/IO和reset结构全部满足后才允许`place_design`，PW/bus-skew真实报告继续保留。
3. 约束继承链明确为OPT→debug_materialized→place；只在真实工具物化阶段接受有实际debug IP来源的新XDC，并继续记录字节、scope/USED_IN/order/enabled和真实读取。不用旧OPT未知值补成PASS。最终physopt/route父链补绑定debug命令receipt和pre_place检查/DCP/约束，不补造旧project-run成功receipt。
4. 完整reset/局部结构可在真正materialized门实测一次；若复用OPT中已取证的原对象，明确其身份和未受debug新增影响的范围，不再全warning扫描。AT004可得的独立预检数据保留；需要变更实际执行链时新开AT，资源预算不扩大。

修正的是工具执行顺序及检查点名称，不是放松“布局前不得有未解析黑盒或未知内部覆盖缺口”的要求。当前仍无真实OPT、debug物化或place准入通过结果。


### 5.10 R003 AT004：完整恢复预检已有实证

独立核读 [restored_preflight.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/restored_preflight.tsv)、[实际properties](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/restored_design_properties.tsv) 和 [debug_restore.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/debug_restore.tsv)。完整preflight以空`PREFLIGHT_ISSUES`结束；此为恢复对象/身份预检完成，不是INIT hook、OPT或place完成。

实际design `NAME=checkpoint_init`、`TOP=scalellm_vcu118_f05_bd_wrapper`、PART正确；project名`project_init`、PART/BOARD_PART均正确；`sources_1 TOP`确为空，唯一BD根cell/ref分别为`scalellm_vcu118_f05_bd_i`/`scalellm_vcu118_f05_bd`。这直接证明§5.8的NAME==RTL top假设错误，不能将DCP或设计判坏。六个原CDC target通过精确cell NAME与pin REF_PIN_NAME全部唯一匹配，支持AT002原missing为查询匹配问题，而非这些对象实际不存在。

3个reset IO均唯一、方向符合；7条async reset chain和4条AUX chain各有4个sequential cell。三个实际clock family分别21/14/14成员、两两交集为0，core周期10ns、两DDR UI各5ns。live debug仍为3个core、唯一hub和1个debug clock port，两输出各265个fanout，与原530范围保持一致。以上计数和对象身份不等于INIT/CLR/CE/D逻辑证明，完整结构及place前覆盖门仍必要。

两处SmartConnect S00 W request FIFO的vendor原查询各返回**恰好1个LUT4非时序对象和1个FDRE时序对象**：`doutb_reg[0]_i_1`的`IS_SEQUENTIAL=0`，`doutb_reg_reg[0]`为1。实际数据支持“宽匹配含非法LUT，同时存在合法FF目标”；合法FF是否获得正确max-delay/exception覆盖尚待后续有效exceptions/clock证据，不能据此关闭Constraints18-401。A004指定局部head/tail/lockstep查询分别3/2/1对象，完整控制cone尚待生成。

这些实证已实际消息发父与A006。当前AT004仍使用缺少显式implement_debug_core的冻结入口，主控/A006已确认其不直接推进place；按§5.9保留可得独立证据，后续修正工具顺序使用新AT，未热改运行中字节。


AT004随后已完成 [live CDC报告](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/cdc_init.rpt) 与 [live check_timing](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/check_timing_init.rpt)。独立按summary/detail完整计数核对：CDC-3 Info434、CDC-9 Info19、CDC-10 Critical6、CDC-15 Warning6198；6 Critical与原综合集合精确相等，new_critical=0。内部缺口仍530 no_clock/554 unconstrained，均通过本轮实际debug fanout归属核对；multiple/generated-clock/loop/pulse_width_clock等仍0。读取时INIT仍在report_exceptions，init_result=0，不能将这些已完成子报告合称INIT/OPT完成或CDC安全签核。


### 5.11 AT004 INIT完成后的有界结论与后续取证修正

随后独立读取 [init_result.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/init_result.txt)，实际为`completed=1 / diagnostic_eligible=1 / blackboxes=1 / clock_coverage=PENDING_TOOL_DEBUG_MATERIALIZATION / physical_signoff=false`。真实工具日志已进入`opt_design`的MIG core generation阶段；当前尚无OPT终态，不将INIT准入混称物理签核。

两处 [XPM局部probe](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/xpm_invalid_endpoint_probe_init.tsv) 中，非法匹配均为`doutb_reg[0]_i_1` LUT4、INIT=`16'h00E2`；合法匹配均为`doutb_reg_reg[0]` FDRE、INIT0、CE1、R0，D由该LUT驱动，C分别为`mmcm_clkout0`/`mmcm_clkout0_1`（对应UI200）。但 [exceptions_init.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/exceptions_init.rpt) 的616行仅为聚合coverage表，没有这两个对象名称或完整约束映射，不能由行位置/对象数量推断合法FF已获正确max-delay约束，18-401仍OPEN。

本机2025.2 `Vivado/doc/eng/man/report_exceptions`确认支持`-to`、`-ignored`、`-scope_override`、`-write_valid_exceptions`，且明确过滤须与原例外采用同类选项、相同cell/pin/port对象。原vendor XPM的`-to`为cell，故有限补证应使用实际FDRE cell，而不是仅查其D pin。A007已实际通知A006，后者临时草稿已加入每处cell的四类报告和真实命令记录；空结果或聚合百分比不自动判安全，也不凭LATE异步clock groups直接断言该max-delay已被覆盖。

A004的 [reset专项报告第6节](reset_warning_review.md) 已对同一INIT checkpoint的指定center12/region2实例核对真实head/tail、ready和lockstep LUT：合法count且replica一致条件下768组合更新相符，reset/clear下head/tail CE各48组合恒0，两侧ready各1024组合相符。该实例“独立head初值01/10”反例可限定关闭；完整replica next-state、CLR上游、其他29条消息覆盖和变换后图仍不在这一结论内。此处承接A004专项审核，不把局部结论扩成全局reset/CDC安全。

集中复核A006的临时草稿`/tmp/m002_debug_stage.GpbSzW`：限定post-OPT父状态、成功OPT命令/DCP/失败终态关联、显式debug命令、独立materialized门、debug XDC来源与字节归档、physopt/route父链总体符合§5.9。审核指出后续place/physopt/route无条件继承物化前reset qualified的适用性缺口，A006已改为每阶段只对7+4链及已知IO采实际snapshot、本阶段重判；不追加全warning扫描。

原INIT probe的cell `IS_C_INVERTED/IS_CLR_INVERTED/IS_R_INVERTED`为空，不能假定为0。草稿已保存限定FDCE/FDRE完整cell/pin属性，C/D/CLR(R)只接受显式、彼此一致的实际极性值。另已通知本机`write_verilog`文档支持`-cell <小block> -mode funcsim -write_all_overrides true`，可对11个四FF小block导出实际含默认值的参数作为有界补证；这只是可用工具路径，尚未取得实际导出结果。A006报告草稿69项CPU通过，尚未作为已归档执行字节独立验收，不能用合成fixture代替真实Vivado属性语义。


### 5.12 恢复project的实际IP cache策略差异

独立读 [restored_design_properties.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/restored_design_properties.tsv) 第145/147行：恢复后的临时`project_init`实际`IP_CACHE_PERMISSIONS=read write`、`IP_OUTPUT_REPO=./.cache/ip`。现有`require_disabled_ip_cache`只在打开原XPR时检查，`close_project → open_checkpoint`后没有再次恢复/核验该策略。因此原XPR的disable身份不能代表本次恢复后effective策略。

[AT004工具日志](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/vivado.log) 第164–165行确有两处MIG PHY `Added synthesis output to IP cache`，ID分别为`e05abd969537e9e8`与`ea5dcc7f77a211af`。截至本次读取，日志只有这两条IP cache写入消息；`Read Netlist Cache`/`Read Device Cache`属于checkpoint内部数据库restore，不能混称外部IP缓存命中。当前尚未证明发生旧IP cache读重用，也未证明网表损坏。

该实际配置异常已立即实际消息通知主控与A006：保留AT004冻结字节及证据；核查实际cache位置、已有/生成来源和是否读命中；新恢复入口应对实际临时project恢复并记录disable策略，候选XPR身份与effective恢复配置分别记录。OPT父链复用需保留这一来源判断，不能将后继关闭cache追写为AT004全程已禁用。该项为既有授权内配置/证据修复，未提出新增用户批准或扩大预算。

**随后来源核验：**A006保存了 [generated_phy_evidence.json](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/generated_phy_evidence.json) 和 [121项snapshot manifest](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/generated_phy_snapshot.sha256)。A007独立逐项复算121个归档文件、65,898,981 bytes及121项manifest全部一致；evidence/manifest SHA256分别为`e68105043da8e4771a543ad43f280964d9d8cccd1ce3595583d7b59c499e1b37`、`f77f30962f1ff2aeb0d86fa4309c38a2b244d612386ef550c60389c86cd6a5b9`。实际repo位于worker的`.Xil/Vivado-3161918-user/3161918/.cache/ip`。归档 [worker日志](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/generated_phy_snapshot/vivado.log) 第75/1209行分别`no cache hit, so run synth`，1183/2125行synth成功，1193/2135行随后写cache；这支持两处本次PHY综合未重用旧IP cache输入，不撤销恢复project实际read/write差异。

同一worker日志第1166/2107行实际读取两份生成`u_mig_ddr4_phy_phy.xdc`，均已逐字节归档，SHA256分别为`1d9d08daba1ad8953c35362841b27a696e042a6346e3fa62fe65d13c9b8c47c5`（DDR1）、`11c2669d29a57a8a0e7373f7b4193a967eedc4d90e6112544a4aab3e9f35773f`（DDR0）。已实际通知A006在OPT父链中绑定这些worker OOC读取及生成DCP来源，区分它们与主设计effective imported约束、后续debug新增来源；原INIT的52条读取不能扩称整个OPT的全部读取。这一核验不允许任意新XDC，也不构成OPT完成或place准入结论。


### 5.13 实际OPT进入debug生成，进一步收紧阶段假设

AT004真实工具日志随后完成`Phase 1.1.1 Generate And Synthesize MIG Cores`（该phase elapsed 11:17），并进入`Phase 1.1.2 Generate And Synthesize Debug Cores`，记录`Generating Script for core instance : dbg_hub`和`Processing IP xilinx.com:ip:xsdbm:3.0 for cell dbg_hub_CV`。这直接证明OPT自身至少开始了debug生成；§5.9的原生显式`implement_debug_core`证据只证明自管入口缺少该步骤，不能证明OPT绝不生成或绝不物化hub。是否已完成物化、零黑盒和全部时钟覆盖仍待真实OPT后报告；仍保留与原生一致的显式动作及独立pre_place检查。

已实际通知父与A006两个具体后果：其一，AT004必须通过真实可核停点止于place前，不能仅依赖“旧OPT门必因hub未物化而失败”的预测；任何监督终止保留实际exit/stop_reason，并由后继限定父类型审查，不能改写成原生exit1。其二，临时草稿目前仅按IPDEF `*:dbg_hub:*`识别新增来源，而实际工具生成IP为`xsdbm:3.0`；必须由真实worker/IP元数据与已知`dbg_hub`/`dbg_hub_CV`关联证明来源，不能将任意xsdbm泛化列白。若实际新debug约束已在OPT内部加载，应按真实OPT生成步骤绑定其字节/作用域/读取，再由显式物化后的门复核，不能伪记为下一阶段才生成。当前尚未观察到对应新约束终态；以上是由实际生成日志触发的取证/入口修正，布局准入要求未降低。

A006随后部署独立 [stop_guard.py](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/stop_guard.py)，没有热改已冻结Vivado脚本。A007只读核查其绑定当前supervisor/leader的PID、start_ticks和父子关系；仅在真实OPT receipt0、opt.dcp生成日志、BB0和clock报告可得后，先保存controlled_stop_request再SIGTERM该supervisor。BB1仍由旧门自然失败。该保护支持本AT的place前停点；终态须保留实际exit/stop_reason，终止时未完整关闭的报告由下一同OPT DCP恢复阶段重取，不能继承为完整。


### 5.14 生成debug派生产物、临时源缺口与诊断适用范围

按主控要求对 [generated_debug_evidence.json](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/generated_debug_evidence.json) 作独立有界核验：23个归档文件、867,221 bytes和23项 [manifest](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/generated_debug_snapshot.sha256) 均逐项hash一致。evidence/manifest SHA256分别为`8277c6a17011d7fb69ff9e0ba177cdfde45e46a8a9abf73672b80a68a99bfe71`、`9d98402ae32d45783706ca8a8c85c5b1dc7ab90b8685968ce2abbcaf3525b902`。生成`result.dcp` SHA256为`90e85b707d6a1168c12a4502e6d328eb8aa5dcfcb12d291dc198e6ef80b3d4e9`；包内Top=`dbg_hub`、part/board符合目标、Vivado2025.2 build6299465，OOC标志为1。包内`dcp.xml`、EDIF和`dbg_hub_in_context.xdc`与外部归档对应文件逐字节相同。

实际worker日志有`-top dbg_hub ... -mode out_of_context`综合命令及完成记录；已保存生成脚本、XCI与参数，绑定`xilinx.com:ip:xsdbm:3.0`、2个slave、`C_CLK_INPUT_FREQ_HZ=300000000`、divider=false。因此这个具体工具生成DCP已有身份与生成来源，可作为诊断用派生产物。五条worker实际XDC读取的路径/scope日志已留存，但原临时工程被工具清理、原文件字节/hash未取得；此缺口明确保留，不能补写不存在的原hash，也不能单凭临时源缺失就机械否定实际DCP或要求无条件重跑EDA。

四份out XDC的字节归档证明它们是生成输出，**尚不证明四份都在主设计中生效**。`dbg_hub_ooc_early.xdc`显式说明仅供OOC、定义`XSDB_CLK`周期3.333ns；DCP内`dbg_hub_in_context.xdc`也含两`sl_iport*_o[1]`输出的3.333ns create_clock及OOC target属性。它们不能覆盖已观察到的主设计hub输入50MHz，也不能仅凭文件名判定最终有效scope/顺序。现有主日志尚未逐文件列出这四份out XDC的实际main加载身份，故main effective约束完整性仍待OPT后实测。

已实际回传主控/A006：最小后续补证放入既定同OPT DCP恢复/pre_place阶段，显式核hub输入、两输出和相应fanout C端点的实际clock PERIOD/MASTER_CLOCK/SOURCE_PINS，核checkpoint内有效约束/例外及来源作用域；零no_clock计数本身不足以排除OOC假定残留。保留原临时五文件hash缺口，并将后续结论限定到该OPT/debug DCP身份及真实effective约束；无需为这项来源缺口单独启动另一EDA或假定debug功能通过。最终时序、全局CDC和硬件签核继续OPEN。


### 5.15 R002 AT007集中草稿审核：执行证据成立，hub准入语义须补

[AT007 status](../R002/attempts/AT007_debug_materialization_draft_cpu/status.json) 与 [tests.log](../R002/attempts/AT007_debug_materialization_draft_cpu/tests.log) 记录05:06:11.993667–05:06:14.662401 UTC、76项CPU、exit0；A007独立重算17项`inputs.sha256`及17项归档manifest全部一致。此为临时草稿的稳定字节，不是AT004执行中字节；339源/45原综合DCP及PHY121/debug23派生来源核验分别记录。没有将CPU通过写为实际OPT父资格、Vivado导出语法或place通过。

集中复核新增：特定guard125/真实SIGTERM终态父类型；缺失OPT POST时从同OPT DCP重新取报告、继承真实旧OPT命令而不重跑；恢复后临时project实际cache禁用/前后值记录；生成PHY与debug的13个可核XDC候选同worker实际读取分记；仅实际关联dbg_hub的xsdbm识别；11个四FF小scope的显式parameter导出fallback；每阶段局部reset结构重新判断；两合法XPM cell的有效/ignored/scope_override/valid例外和有限路径。上述主体符合当前有界恢复路线，真实工具API仍需执行后验证。

**当前明确准入缺口：**`debug_clock_facts`只要求hub输入/输出/fanout clock非空、属性存在、周期为正；输出即使仍为与实际连通不符的OOC独立3.333ns，也仅写`review=OPEN`而让`pre_place_evidence`继续自动place。主控随后明确的判断与A007发现一致：输入50MHz与参数300MHz的差异可以保留待解释；实际下游时钟若与无divider连通不一致，必须定位并修复，不能由零no_clock或泛称OPEN放行。已实际通知A006修正为有实际来源依据的限定准入或证据收齐后的技术停点，物化入口的最终静态验收暂不关闭此项。

本机`write_xdc`文档另确认可用`-cell dbg_hub -type timing -constraints ALL -write_id`生成有界当前timing约束快照，按design中加入/执行顺序写出；已给A006作为辅助scope补证路径。该局部导出不覆盖祖先scope施加约束，仍须结合实际master/source与全局clock报告，不能替代实际时钟关系判断。

**后续集中delta复核：**A006报告修正草稿79项通过。A007只读核对其实际新增判断：保存hub pin分段net、leaf driver/startpoint、有界source cone、clock master祖先及局部effective XDC；每个output须由实际input/master链或同net且同period/waveform关系支持，无divider时输出周期须与实际input一致，fanout观察须与output一致。错误独立3.333ns或未知来源不再仅OPEN后放行；多个CDC/reset/IO/clock问题先写完整integrity、再统一阻断，`pre_place_evidence`再次核`relationship_qualified`、probe及scope导出hash。参数300MHz与实际输入50MHz的metadata差异单独保留，不自动当作时钟关系失败。此项明确缺口在当前草稿静态上已修，未见新不安全准入；已实际通知主控/A006支持原AT真实终态后按已有授权安装、正式CPU归档和新AT执行。79项尚待正式档案及真实工具结果，不预填其Vivado API、时钟或物理阶段PASS。


### 5.16 假设性hub时钟修复预案：本机原生依据与最小选择

主控在等待OPT终态期间明确要求准备此有界预案。本节**没有认定当前主设计存在错误OOC时钟，没有运行EDA、修改配置/XDC或改变合同**；只有新AT的实际clock/master/source与网表连通证明错误后才选择修复。

原生依据来自当前2025.2安装：

- [implement_debug_core说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/implement_debug_core:19) 明确debug实现可在`opt_design`中自动发生，也允许指定core单独实现；不保证“对已实施core改属性后再次调用必强制重生成”，没有已文档化的`-force`参数。
- [xsdbm组件定义](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/ip/xilinx/xsdbm_v3_0/component.xml) 将`C_CLK_INPUT_FREQ_HZ`定义为25,000,000–650,000,000 Hz用户参数，默认300,000,000；divider默认false。[xgui参数更新](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/ip/xilinx/xsdbm_v3_0/xgui/xsdbm_v3_0.tcl:726) 将频率和divider传入model；547–642行频率还参与`C_XSDB_PERIOD_INT/FRC`等派生。因此不能预先把频率参数改动称为纯注释修改。当前归档XCI的model period为10/0、divider0，不能由该数字代替实际主设计clock观测。TTCL及实现主体受工具保护，未尝试解密或推断未见实现。
- [create_clock说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/create_clock:24) 明确在派生位置使用独立primary clock会丢失源时钟插入延时/jitter，导致错误计算。[create_generated_clock说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/create_generated_clock:47) 支持实际`-source/-master_clock`、`-divide_by 1`与有条件的`-combinational`；[reset_timing说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/reset_timing:3) 会清除全设计时序约束且不自动重载，不适合作为这一局部修复。

**选择A：修正生成配置并重新生成hub。**适用于实际clock错误确由生成配置、分频/参数或生成产物不一致引起，或现有网表不足以证明仅约束问题。将实际debug core的频率属性设为测得的50,000,000 Hz、保持已确认false divider，保存前后属性与实际命令。可靠起点是已有未物化hub的真实INIT DCP，由工具重新生成该hub并进行所需OPT/显式debug动作；若尝试复用已OPT的DCP，必须先确认属性可写及工具确实重生成，取得新DCP/XCI/生成参数/命令证据，不能仅凭`set_property`成功宣称实现更新。本选择不天然要求再次综合全部用户RTL，但会改变派生debug产物身份，旧OPT/物理报告不能无条件继承。

**选择B：限定有效约束修正。**仅适用于实际网表证明hub输入到两输出无分频/反相差异、source cone正确，而错误局限于OOC独立primary clock残留。先确认坏clock的source pins恰为所列hub输出、无其他设计范围共享，再用独立小repair XDC按实际input source/master定义对应divide-by-1关系，精确处理原坏clock对象/名称，避免`-add`留下并存假时钟；是否用`-combinational`由真实cone决定。不能在输出简单补`create_clock -period 20`替代source关系，不能全局reset时序，也不能靠异步分组/false path隐藏错误。若物理来源或旧clock范围不唯一，本选择不适用，应回到选择A或先补局部证明。

任一实际修复均保留旧尝试和DCP，记录新派生产物/约束链并复核hub实际输入/两输出/fanout clock、board core100/UI200、全设计coverage/DRC/CDC及受影响例外；再次到达pre_place门后才继续。若新AT已证明实际输出关系正确、只有300MHz元数据与50MHz输入不一致，则继续保留该差异的限定解释，不为这项假设自行修改时钟或重生成。

本机来源身份：`implement_debug_core` SHA256=`2efb5b8f73f98f55e0df40879f3c51935470a589106d410efa7345498ef3cef4`；xsdbm `component.xml`=`5b2fc44dd7d0d9ae4b12983aeb96dcb1193c5eaded4667ab83a830c43a26d0d0`；`xgui/xsdbm_v3_0.tcl`=`90a8a878ac551957b74500e0b6d1f578c399c805af6a7ea79cedec2c01255206`。预案已实际消息通知主控/A006，未作为当前实际故障或修复完成记录。


### 5.17 AT004 真实 OPT 命令完成，POST 与受控终态仍待确认

独立核对 [opt_command_result.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/opt_command_result.txt)：`command=opt_design / native_tcl_code=0`，epoch `1792039412 → 1792041664`，实际 elapsed 37分32秒。主日志第354–355行确认 OPT 成功，第367行写 checkpoint；[opt.dcp](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/opt.dcp) 实际为218,404,246 bytes，SHA256=`1b557cd956e364e38948a8a86d410ff1599261284edea1473d7c5df4c677d42b`。包内 `dcp.xml` SHA256=`0316cf24371990318d62534caa6ece3b805329a26e587e2c3614f17097938266`；Vivado2025.2/build6299465、part `xcvu9p-flga2104-2L-e`、board `xilinx.com:vcu118:part0:2.0`、top `scalellm_vcu118_f05_bd_wrapper`、OutOfContext0 均匹配。

同次读取 [opt_result.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/opt_result.txt) 为 `completed=0 / diagnostic_eligible=0 / blackboxes=0 / physical_signoff=false`；AT目录尚无 `status.json` 或 `controlled_stop_request.json`，report目录无place/physopt/route产物。因此已确认的是实际OPT命令成功及其新DCP，尚不能判完整POST或尝试成功，亦未获得布局准入或物理签核。BB0进一步印证OPT自身已生成/物化原hub；保留后继原生显式debug步骤及独立pre_place审核，不把缺失显式命令当作当前未物化的证据。

此里程碑已用实际消息通知主控与A006。继续核对既有stop guard的真实终态、父进程身份与place前停止证据；不改写正在执行的入口或原始结果，不将尚未关闭的报告继承为完整。

同一OPT的 [utilization_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/utilization_opt.rpt) 已完成：LUT828,255（70.06%，第38行）、FF1,021,363（43.20%，第43行）、BRAM tile941（43.56%，第84行）、URAM752（78.33%，第89行）、DSP5,451（79.69%，第100行）。这些全器件汇总未超总容量；不等于局部放置、连通或布线可实现，DSP/URAM高占用仍须真实物理证据。读取时`check_timing_opt.rpt`与`clocks_opt.rpt`尚不存在，不以资源报告替代时钟或时序检查。


### 5.18 OPT 内嵌约束与实际受控终态

独立核对 [opt_checkpoint_embedded_xdc.json](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/opt_checkpoint_embedded_xdc.json)（SHA256=`6fd6483d8849c271e67ffc23aff6693888808a24a6ebbd67bb60e7d2751683cf`）：四份归档文本XDC的bytes/hash及与OPT DCP对应原成员均逐字节一致，合计2,359,622 bytes；`dcp.xml`与§5.17身份一致。四份全文未见`sl_iport`、`XSDB_CLK`或`create_clock ... 3.333`。主wrapper XDC第555–557行为`current_instance dbg_hub/inst`及BSCAN `INTERNAL_TCK`的50ns `create_clock`；该TCK不同于已观察到的hub数据时钟20ns，不能混为同一个时钟。

上述主DCP内嵌文本不支持“已将OOC输出3.333ns时钟直接带入主设计”的猜测，但还不能独立证明实际hub输入/输出/source/master关系；保留新AT live探针门。提取DCP中的文本并非重新`read_xdc`，也不替代实际例外有效性报告。

[timing_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/timing_opt.rpt) 第68/140–142行实际为no_clock0、WNS+0.904ns、TNS0、WHS−0.814ns、THS−48,989.652ns、992,151个hold失败端点；WPWS−0.012ns、TPWS−0.037ns、5个PW类失败端点。OPT时序仍FAIL；无缺时钟并不等于关系正确、时序收敛或物理签核。

随后实际 [status.json](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/status.json) 记录05:30:21.947361 UTC结束，native exit−15、managed exit125，`stop_reason=supervisor_exception:KeyboardInterrupt:signal 15`；原始SHA256=`f30674f982b633d0a0a480a08a36b96d2867d191439c48b6551690dbe1d88e72`。[controlled_stop_request.json](../R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/controlled_stop_request.json) 在05:30:16.109429 UTC保存，绑定supervisor3161783/start_ticks915082417和leader3161784/start_ticks915082423及父子关系；SHA256=`606ade1a28a04801b3b82c7e7062b39292679a9a72697d7e08716424ad28df59`。A007独立重算其中五项OPT proof的bytes/hash全部匹配。原status瞬间记录`owned_survivors=[3161784]`；随后只读`/proc`核验supervisor/leader均不存在、该PGID无成员，这一后续观察不改写原记录。

主日志未出现实际`Command: place_design`或完成记录，也没有place/physopt/route产物；`opt_result`仍为completed0。受控停止保全了成功OPT和已完成子报告，POST整体未完成，不能将退出125改写成原生exit1/0或将全部POST称为完整。后继可按已审限定父类型从此同OPT DCP补取报告并执行显式debug/pre_place门；不需要再次OPT，也不能伪造父POST成功。受控终态、无活动受管进程及上述适用范围已实际通知主控/A006。

对已完成子报告补核：[check_timing_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/check_timing_opt.rpt) 的no_clock、unconstrained_internal_endpoints、multiple_clock、generated_clocks、loops均0，保留已知no_input_delay1/no_output_delay2；[clocks_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/clocks_opt.rpt) 第51/152–157行确认`mmcm_clkout5_1`周期20ns、DDR1 MMCM CLKOUT5来源、master为`default_250mhz_clk2_clk_p`，但没有逐个hub输出绑定证据；[drc_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/drc_opt.rpt) summary第27–37行仅6类Warning、总计15,914（DPIP-2:7,275；DPOP-3:5,192；DPOP-4:325；DPREG-7:3,072；REQP-1858:22；REQP-1935:28），无Error或Critical。以上仅为这些已完成子报告的限定读数，不关闭后继hub关系、CDC、reset或XPM证据要求。


### 5.19 R002 AT008 正式安装归档与实际 OPT 父链集中审核

[AT008 status](../R002/attempts/AT008_opt_recovery_debug_final_cpu/status.json) 与 [tests.log](../R002/attempts/AT008_opt_recovery_debug_final_cpu/tests.log) 记录05:36:32.073519–05:36:37.016849 UTC完成，78项物理入口测试和6项隔离测试均OK、总84项、exit0。A007未重新执行测试，独立逐行重算[inputs manifest](../R002/attempts/AT008_opt_recovery_debug_final_cpu/inputs.sha256)与[archive manifest](../R002/attempts/AT008_opt_recovery_debug_final_cpu/archived_sources.sha256)，各16/16一致；manifest SHA256分别为`ada84488b285c4746df664eb47a1f1a0f8f74550a3d92d5ca016b7448eb1e708`、`f0028cd285d5ad55c529a767aae819e8a37c775dc3bc9a517b0f694f451ea737`。[installation.json](../R002/attempts/AT008_opt_recovery_debug_final_cpu/installation.json)的7个after身份均与实际安装字节一致。

集中承接§5.15已审clock delta，并核新reap修正：限定guard125必须保留原status的bytes/hash和survivors；只接受空列表或其原leader，另有退出后的31个PID/start_ticks集合核查、冻结工具log、实际当前`/proc`身份复查。A007独立将[实际父链](../R002/attempts/AT008_opt_recovery_debug_final_cpu/actual_opt_parent_preflight/recovery_parent.json)所指post-termination记录与resources逐项对照，31个原身份精确相等、记录均not_present，当前亦无同身份进程；status、controlled stop、reap、resources及frozen log的bytes/hash均匹配。未来supervisor新增wait/reap后再次查询并分别记录before_reap/owned_survivors；不是任意非零/资源失败都可恢复，也未改原AT004记录。

真实父链保留339综合输入、45 DCP、§5.17的真实OPT DCP及package、原project impl FAIL与自动OPT debug阶段说明。`opt_evidence_complete=false`、`inherited_reports={}`，后继须重取同OPT的完整POST；没有伪造原OPT POST成功。集中审核支持在既有授权下继续R003 AT005同OPT恢复/显式debug/pre_place；本节仅确认执行字节、CPU结果及父链入口，不预判真实工具API、hub关系、reset/XPM/CDC或布局通过。结论已实际消息通知主控与A006。


### 5.20 AT005 实际 restore：hub 时钟关系得到直接证据

独立读取 [debug_restore.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/debug_restore.tsv)，412,429 bytes、SHA256=`2f7eed91d4e08308b55ddcb2df5f3d9f2ad82031f08c4d55d13722f487f43dca`。`dbg_hub/clk`及两`sl_iport*_o[1]`实际均为`mmcm_clkout5_1`；三者所列91个segmented nets的集合完全相等。两个output的实际leaf driver均为DDR1 `u_bufg_dbg_clk/O`（BUFGCE），startpoint均为DDR1 MMCM `CLKOUT5`，有界cone各2个cell；两组各265个扇出C端点全部观察到同一clock。

实际clock PERIOD20.000ns、WAVEFORM`0.000 10.000`、IS_GENERATED1、MASTER_CLOCK=`default_250mhz_clk2_clk_p`、SOURCE_PINS为上述MMCM CLKOUT5；master自身周期4ns。hub属性仍为300,000,000Hz、divider=false。对这一restore状态，实际连通与无分频50MHz一致，没有出现此前假设的独立3.333ns输出关系；因此尚无实证要求实施§5.16任一修复。元数据频率差异保留，不扩称调试功能已验证。

[restored_runtime_settings.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/restored_runtime_settings.txt) 实际临时project=`project_opt`、IP cache从`read write`改为`disable`、threads8，SHA256=`174d39c03034f0ef0e62f1273ac9cfd0b480f141fdbf86a0cd528b3c385102ef`；这只描述本次恢复后的实际策略，不回写AT004策略。[restored_preflight.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/restored_preflight.tsv) 的`PREFLIGHT_ISSUES`为空，SHA256=`7c73eaadf57ddd4179593e332476d94bd7abdf61f287a0402198ffc3de2d5b52`。

restore阶段按入口定义尚不导出最终hub scoped effective XDC，也未完成显式debug命令、debug_materialized/checkpoint及完整pre_place门；这些仍待实际执行。上述证据与限定判断已实际消息同步主控/A006，不提前关闭物理准入、reset、XPM或CDC审核。


### 5.21 AT005 OPT 后 CDC 新差异：定位、诊断准入和正式签核分开

[cdc_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/cdc_opt.rpt) 已完成，SHA256=`7451c566ed781bcc67e2bbc5484378980045df170acb9b2ad884a7d20b94ff67`。summary为CDC-3 Info519、CDC-9 Info19、CDC-10 Critical6、CDC-11 Critical2、CDC-15 Warning5688。两条CDC-11（第2483/4320行）均从XDMA `user_reset_reg/C`到各`d0_gate`/`d1_gate`的`u_base_reset_cdc/arststages_ff_reg[0]/CLR`，Depth4、Asynch Clock Groups；原AT004 INIT同一source/destination在第2514/4562行为CDC-9 Info。相邻仍有同source到HostSplit AUX同步入口的CDC-3（DDR0目的域一条Depth5，DDR1目的域两条Depth5）。不能仅因链长为4或实例为XPM便关闭fanout告警。

对完整Critical集合按`(rule,source,destination)`独立比较：原6条CDC-10中4条身份不变；另外两条core_gate `u_ready0_cdc`/`u_ready1_cdc`同一CLR目的的source从对应DDR的`div_clk_rst_r1_reg/C`变为`u_ddr4_mem_intfc/u_ddr_cal_top/calDone_gated_reg/C`。因此精确集合有4条新增身份：两条CDC-10源锥变化与两条CDC-11；不能用“CDC-10数量仍6”推断其全部来源未变。该变化需与实际OPT后ready/reset探针关联解释。

**原生规则依据。**[UG906 2025.2 Fanout](https://docs.amd.com/r/2025.2-English/ug906-vivado-design-analysis/Fanout?contentId=3BMH0aKTLFpSCAfomopWNA) 将CDC-11归于同一目的域内对一个源信号多次同步、同步延迟不保证逐周期一致的情况；各不同目的域分别一路不属于这一错误，故不能将新增项仅解释为DDR0/DDR1本来独立。[同版异步reset章节](https://docs.amd.com/r/2025.2-English/ug906-vivado-design-analysis/Asynchronous-Reset-Synchronizer) 说明同域不同同步链可能使消费逻辑在不同时刻释放reset，并给出具备busy/流控条件的FIFO Generator及AXI相关安全例子；这些条件不能不经证明泛化到当前自定义gate与HostSplit。[同版规则优先级](https://docs.amd.com/r/2025.2-English/ug906-vivado-design-analysis/CDC-Rules-Precedence) 中CDC-11高于CDC-9，默认每clock-pair/endpoint只报最高优先级。因此改报CDC-11本身不证明4级异步断言/同步释放链已经消失，也不证明其全部消费者安全。

本机2025.2 `report_cdc`/`get_cdc_violations`文档支持限定from/to域、`-all_checks_per_endpoint`和查询violation属性及关联cell/pin/net。已给A006最小后继取证建议：保留本AT真实失败/原字节，从同OPT DCP对XDMA源Q、两UI目的域及准确相关同步入口、完整相关扇出和最终release消费关系取证；7条reset链外若同源HostSplit入口参与fanout，也须纳入这一限定锥，不做无界全设计扫描。原本11小block显式reset_graph只安排于debug_materialized/后续物理点，当前未知Critical可能先在OPT门阻断，不能假装这些图已取得，也不热改运行源码。

主控明确本次判断分三层：①先定位真实新增拓扑及其对物理结果解释的影响；②结构已明确且不损坏时钟/连通/物理测量前提时，可集中评判是否保留精确未决reset行为而继续诊断place/route，不能把这种准入写成CDC安全豁免；③正式功能/reset签核仍需释放差异、重汇合和事务/复位场景证据。当前只有报告差异及同域重复同步的具体候选，实际OPT后局部图与A004源语义核对尚待完成，故尚未给诊断继续或必须重设计的终判。若证明确有必须先修的具体缺陷，只提出有证据的最小修复；不自动把首个物理基线扩大为全局reset架构重设计。异常、准确集合差异和取证建议已实际通知主控、A006、A004。

**随后AT005真实终态与源语义补证。**[status.json](../R003/attempts/AT005_opt_recovery_debug_materialized_place_physopt/status.json) 记录05:37:04.160234–06:01:09.540723 UTC，native/managed exit1、stop_reason=null、owned_survivors=[]。完整OPT POST及原有bounded reset/XPM/head探针已取得；[integrity_opt.json](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/integrity_opt.json) 唯一gate issue为`new/unclassified critical CDC path`，reset_structure仍`DEFERRED_TO_DEBUG_MATERIALIZED_PRE_PLACE`，不能称其结构已经合格。opt_result保持completed0/diagnostic_eligible0/BB0，未执行显式debug或place。

A004专项比对两ready锥的INIT/OPT实际probe：原本均包含div_clk_rst_r1和calDone_gated，并非新引入calDone源；锥从6个cell变4个，LUT2 INIT8→2、两个反相LUT被吸收，OPT四级FDCE显式IS_CLR_INVERTED=1，与真实OPT反相优化记录一致。此为来源选择和有效极性变化的可核解释，最终按精确pin/source-Q映射与导出参数核`ready=calib_done && !ui_reset`，不能以固定CLR_INV=0或LUT字节不变作为必要条件。

**给新AT的最小诊断准入判据（待实际命中，不是当前PASS）：**

1. 绑定同一真实OPT DCP、工具及完整完成报告身份，保留AT005失败记录。当前同OPT检查的8条Critical逐条明确：4条原CDC-10、2条已定位ready代表source变化、2条已定位XDMA→DDR base-reset CDC-11。新增rule/source/target/clock或额外未解释扇出继续阻断，不能靠数值上限或任意CDC白名单放行。
2. 在OPT门之前取得本阶段7条4FF reset链、相关AUX与HostSplit三条相关分支的实际图/小block参数；核目标时钟、ASYNC_REG、级联/CE、有效复位极性和端点唯一性。ready锥须与既定`calib_done && !ui_reset`语义一致。空属性不默认0，使用显式原语参数及pin映射补证；结构已变或锥不明不能继承旧qualifier。
3. 对XDMA源Q到两UI域的相关同步分支，明确base gate和HostSplit入口、完整相关扇出及输出消费身份。这里只要求定位实际同域多release结构及后续可能重汇合的边界，不把事务级release一致性证明强行前置为本轮物理实验条件。若证据出现未同步的直接异步消费、断链、错误clock或错误有效极性，则先定位/修复该具体缺陷；目前尚未取得这种反例。
4. 若上述限定结构检查和原有零BB、实际clock关系/coverage、DRC、IO等门全命中，可自动记为`classified_reset_cdc_diagnostic_only`并继续既有诊断place/route；正式reset/CDC safety和事务/复位行为验证保持OPEN，不能把准入记录写成豁免或功能签核。时序结果仍按真实正负值报告。无需为每个匹配结果新增人工批准停点。

以上判据已实际回传主控/A006，承接本轮首个可解释物理基线的授权范围；具体新AT仍须给出这些限定证据。后继物理阶段的结构资格仍按本阶段实际图重判，不将这里的OPT身份自动套给优化后网表。

主控随后实际确认接受这套最小自动诊断准入，要求A006在新AT真实命中时按既有授权自动继续，不新增单独人工放行文件。该确认是内部架构/适用范围审核，不记作新的用户批准；正式reset/CDC safety仍OPEN。

8项精确机械身份按上述hash的AT005 `cdc_opt.rpt`第181–183、853–855、2483、4320行登记。对k=0/1，每域3项CDC-10均从UI_k（`mmcm_clkout0`/`mmcm_clkout0_1`）到core（`clk_out1_scalellm_vcu118_f05_bd_clk_core_0`）：DDR_k `calDone_gated_reg/C`→core_gate `u_ready{k}_cdc/arststages_ff_reg[0]/CLR`，以及d{k}_gate `u_ready_cdc/arststages_ff_reg[3]/C`→d{k}_smc的`clk_map/psr0`和`clk_map/psr_aclk1`各`U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D`。两项CDC-11从`xdma_0_axi_aclk`到对应UI_k，精确source为XDMA `user_reset_reg/C`、target为d{k}_gate `u_base_reset_cdc/arststages_ff_reg[0]/CLR`。不能仅用“200MHz/100MHz”数值替代实际clock对象身份。HostSplit三分支的精确内部consumer范围由A004继续依据vendor RTL核实后交A006，不能宽泛列白任意vendor reset消费者。

A004随后给出[专项报告§7.6](reset_warning_review.md)的源级consumer边界：三HostSplit wrapper均`C_AUX_RST_WIDTH=1 / C_AUX_RESET_HIGH=0`，ACT_LO_AUX stage3 Q对应该LPF的`asr_lpf(0)`；width1使`ASR_OUTPUT_PROCESS`简化为`lpf_asr <= asr_lpf(0)`。据此新AT实际门对三链尾Q的首个顺序consumer分别要求为本`host_split/inst/clk_map/psr*/U0/EXT_LPF/lpf_asr_reg/D`、FDRE、与该链同clock；`psr_aclk1`为UI0，`psr0`及`psr_aclk2`为UI1。不得将任意LPF/counter都列为尾Q直接消费者；后续`lpf_asr → lpf_int → SEQ`属于后级release路径风险边界。

XDMA源Q在两UI的相关raw fanout按精确集合核对：每域各base同步链四个CLR，加相应HostSplit ACT_LO_AUX stage0 D（UI0一链，UI1两链）。同一合法异步reset链的四个CLR不是四条独立同步链。当前这些是从已核源语义导出的机械预期，仍须新AT实际图命中；若优化别名/额外consumer使集合不匹配，先保留完整图定位，不能凭名称泛化放行，也不能把任何取证不匹配直接等同RTL必需重设计。范围、时钟与consumer判据已实际消息交A006和主控。


### 5.22 R002 AT009 安装、同 OPT 报告复用与诊断门审核

[AT009 status](../R002/attempts/AT009_cdc_reset_diagnostic_reuse_cpu/status.json) 与 [tests.log](../R002/attempts/AT009_cdc_reset_diagnostic_reuse_cpu/tests.log) 记录06:18:29.702749–06:18:37.628777 UTC，87项物理入口+6项隔离测试共93项、exit0。独立重算两manifest各16/16匹配，实际安装4个after身份全部匹配；`inputs.sha256` SHA256=`f927d09b873e0ab7265115113309835f77bb9f94718b99608e82eae752a099fc`，`archived_sources.sha256`=`54ecfb55fc7acc89a903bcedac2850dde54895be74082786d251c025dff5d56e`。未重复运行测试或EDA。

[实际父链preflight](../R002/attempts/AT009_cdc_reset_diagnostic_reuse_cpu/actual_opt_reuse_parent_preflight/recovery_parent.json) 绑定339源/45综合DCP、AT005真实失败/完整祖先及14份已完成报告，14份bytes/hash独立重算全匹配。新父OPT DCP为AT005实际重存的397,273,730 bytes、SHA256=`b209decf321e4a756f3ded455e0ce162b3404467ec235b5312469f9a89171021`，package目标part/top/board/build正确、XML hash=`b0c7d4880f51e42811ec3b6279ba580dbb6ef11812cfd2ff372792d7b31fa291`。已核主日志真实`open_checkpoint`原OPT及写出新OPT，没有再次`opt_design`；故这是同OPT阶段的恢复重存产物，并非与AT004逐字节相同的DCP。原OPT command receipt身份继承保留，未伪造新OPT执行。

集中静态复核限定恢复递归、已完成report与constraints/integrity来源绑定、精确8条Critical、14个fresh reset块、实际source-Q fanout、唯一HostSplit LPF consumer及有效反相判读；与主控追加的合同诊断边界一致。每个base尾Q的全部顺序consumer保留：同域必须是实际对应UI clock；跨域仅对应d_smc的psr0/psr_aclk1 ACT_LO_AUX stage0 D、FDRE且实际core clock，其余/无clock拒绝。此限定定位已同步尾级的消费结构，不扩称同域release一致性或正式CDC安全。

**有限自动检查遗漏：**4条原AUX循环检查FDRE、ASYNC_REG、CE/R、clock、极性和级联，但没有显式断言INIT0；7条async reset链和3条HostSplit则有INIT断言。独立读AT005同一恢复DCP对应的bounded probe，四AUX共16个FF实际INIT均为`1'b0`，未发现实际设计反例。该项已通知主控/A006：在AT006 fresh graph/explicit exports产生时补独立核验这16个INIT值以完成本AT证据，后续合法入口修订补自动断言；不因此机械重跑EDA，不热改本次冻结字节。AT009 CPU/静态结论不代替AT006真实图、debug关系或物理准入。


### 5.23 AT006 实际原语导出：AUX INIT 补证与有来源的缺省参数

AT006的14份`reset_primitive_overrides_opt_*.v`已实际写成，每份包含确切4个FDCE或FDRE；header绑定当前Vivado2025.2/build6299465、目标part、实际`write_verilog -cell ... -mode funcsim -write_all_overrides true`命令和对应小block。独立核验原4条AUX（编号7–10）的16个FDRE均**显式**`.INIT(1'b0)`，补齐§5.22本次实际INIT证据；三条HostSplit（11–13）另12个FDRE亦均显式INIT0。该结果不依赖把空属性解释为0。

| 实际AUX export | SHA256 |
| --- | --- |
| [opt_7：d0_smc/psr0](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_primitive_overrides_opt_7.v) | `aaa413a7a6d62990d92b1e34af23b33355a6d856061f5d57e54f4e6bea641f7f` |
| [opt_8：d0_smc/psr_aclk1](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_primitive_overrides_opt_8.v) | `9facfa7620ad032d0c046ebe550b3ce9e0fe1b4798308d53e3072e69b7471c4d` |
| [opt_9：d1_smc/psr0](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_primitive_overrides_opt_9.v) | `edaf37fe8a217903b6ca4dcc27cd29a15894e239ab36ac567ce6be3f18423a02` |
| [opt_10：d1_smc/psr_aclk1](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_primitive_overrides_opt_10.v) | `c730d795416501a807c4ed013925a5250e2cc095ff707e2e7b94f84a4a37e3d9` |

7个async reset块共28个FDCE均显式INIT1；core base及两ready、DDR两ready块的CLR_INV为1，DDR两base块为0。不能将这些INIT1机械改判为应是INIT0；有效assert/release由真实CLR逻辑、CLR_INV及Q/级联关系共同决定，A004继续作语义核对。

实际export虽使用`-write_all_overrides true`，仍未输出FDCE C/D或FDRE C/D/R默认参数。本机[write_verilog手册](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/write_verilog)明确该选项写出设计中的parameter overrides，包括值恰等于原语default的override，**不是承诺列出原语每一个参数**。手册SHA256=`01159ef1e6afef9bc5cea852b6a232c9089eeb5532da9f3b3ae7b32703b1b591`；因此当前省略本身不是RTL或导出失败证据。

同一2025.2安装附带的明文[FDCE模型](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/verilog/src/unisims/FDCE.v)（SHA256=`74d30d7c788e7db47f12b92d5b4b57b707974a0962708b309e4cc081d5f98b04`）及[FDRE模型](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/verilog/src/unisims/FDRE.v)（`e2965e4b5174bd8de84b82e89a7b4ea5df36d8715c4f585580c16b8e6d9aa80d`）均明确C/D及相应CLR/R inversion默认0；FDCE行为明确`CLR_eff = CLR xor CLR_INV`，GSR令Q=INIT，active异步clear令Q=0。这里“同版本”指当前工具安装随附模型，文件自身历史header并非新写于2025.2。

认可后继有限解析修正：仅对实际导出中确切FDCE/FDRE实例，在完整解析所有parameter overrides、排除局部同名原语重定义/defparam或未知覆盖后，将省略的参数按上述已绑定模型default解释；逐值保留`explicit_override`或`model_default`来源，并与非空cell/pin属性核冲突。不能推广成任意空属性=0，不能忽略显式1/未知表达式，也不因此把INIT1改成0。当前图仍在生成、原冻结parser若保守阻断则保留真实失败；不热改。以上工具语义、16个AUX实际INIT补证及边界已通知主控/A006/A004，未预判整个reset图或物理准入通过。


### 5.24 AT006 终态、离线复位解释与 BRAM 写端口时钟归属

**执行事实：**[AT006 status](../R003/attempts/AT006_cdc_reset_proof_debug_place_physopt/status.json) 记录06:18:56.508528–06:34:16.369985 UTC，native/managed exit均1、stop_reason为空、owned_survivors为空；SHA256=`16a3c5cfc04cf736fee73c684afa56ff812abd0696009930679fe3c45a4b1edc`。本次在保守证据门停止，没有进入显式debug/place。119,909,158-byte reset graph与5,962,741-byte fanout文件已经关闭；不把后继离线解释回写为AT006通过。A006实际消息报告：修正有来源的primitive缺省、`all_fanin`所给C到同一已识别FF的Q归一化及raw `user_reset/Q`的有效极性后，离线reset qualification v2通过。这里记录其工程结果，后继稳定CPU归档与实际综合诊断门仍须各自验证，不能据此填写完整CDC gate PASS。

**独立有界聚合：**完整读取已关闭的[cdc_changed_reset_opt.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/cdc_changed_reset_opt.tsv)，SHA256=`c34f89304691c486f5bd8cc489e7ec68bd96e005426009e9edc2e20470ca0346`；仅按两DDR base同步尾Q的`BASE_RESET_Q_ENDPOINT`分类，未重新扫描119MB图。

| source尾Q | timing endpoints总数 | CLOCKS恰为对应UI | 双时钟BRAM混合CLOCKS | 实际core-only FDRE |
| --- | ---: | ---: | ---: | ---: |
| d0 base stage3 | 6362 | 5904 | 456 | 2 |
| d1 base stage3 | 5282 | 5048 | 232 | 2 |

混合688端点**全部为WEBWE位**，当前集合没有WEA：d0为56个RAMB36E2各8位及2个RAMB18E2各4位；d1为28个RAMB36E2各8位及2个RAMB18E2各4位，合计88个BRAM cell。四个真正core-only FDRE恰是既定`d{0,1}_smc/inst/clk_map/{psr0,psr_aclk1}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D`。未出现其他剩余类别。层级名含`core`的其他数千端点实际CLOCKS为UI，不能按层级名断定域。

原helper `m002_endpoint_clocks(receiver)`对整个接收cell的全部`IS_CLOCK` pin取`get_clocks`，使每个BRAM WEBWE端点都记录`{core,对应UI}`并集。这个归属粒度足以解释全部688项残余拒绝；当前证据不要求假定`all_fanout`跨CLR→Q顺序弧。当前[本机all_fanout说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/all_fanout:15)将`-endpoints_only`定义为timing endpoints，不能把这一输出擅自称为只含直接电气loads。A004另以实际RTL核对base经gate进入async FIFO写使能/寄存器CE属于源码预期；这支持按实际接收端口分类，不等于将所有FIFO或vendor cell列白。

**端口语义来源：**当前Vivado安装的明文功能模型[RAMB18E2.v](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/verilog/src/unisims/RAMB18E2.v:961)在961/964行分别以WEA/WEBWE生成A/B写使能，2320行A写引擎使用`CLKARDCLK_in`，2354/2391行B写引擎在`CLKBWRCLK_in`事件中处理`mem_wr_en_b`；[RAMB36E2.v](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/verilog/src/unisims/RAMB36E2.v:1412)对应1412/1415、3064、3098/3135行，3301–3303行再将WEBWE各位展开至B写字节使能。两模型SHA256分别为`5b5824a9a33980c7019ca4ea18d272134da4e1e3b8a0ba6b576e485eedb27dc5`、`de300b57debd3f31771fa1d7a343f12200658cea6317e4da2a8c3d2f8e61519d`。这支持`WEBWE[*]→同cell CLKBWRCLK`、`WEA[*]→同cell CLKARDCLK`的功能归属；模型`specify`中存在双时钟检查，未用其中任一setuphold条目声称独占端口关系。该归属也不关闭双时钟RAM碰撞、数据CDC或reset release安全问题。

**后继最小实际门：**限定确切RAMB18E2的WEBWE[0..3]及RAMB36E2的WEBWE[0..7]，从实际endpoint对象取得其唯一cell与精确REF_NAME，再从同cell查询唯一`CLKBWRCLK`实际clock pin及其`get_clocks`集合；完整保留旧whole-cell CLOCKS、endpoint、cell、clock pin与实际clock结果。88个cell的clock查询可去重，688个endpoint仍必须逐项完整映射；唯一实际clock必须恰为该base对应UI。旧`{core,UI}`并集不能证明B端已是UI，因此本节没有给出实际端口门PASS。若以后支持WEA，须显式实现并测试A端映射；本次不靠泛称BRAM放宽未知pin。

最小负例包括A=UI而B=core的WEBWE、B clock缺失/多个/另一UI、错误cell的clock pin、未知REF/pin或越界bit、缺行与冲突重复；均应阻断。保留全部base fanout、精确四个AUX例外及raw XDMA实际consumer集合检查，不截掉未知端点，不以写端口解释扩大异步raw-source豁免。实际新增端口取证纳入下一单条授权AT，无需为此独立重跑OPT或另开EDA。

**审核与适用范围：**以上发现、功能模型hash、最小探针和负例已通过真实消息送达主控/A006。主控实际回复接受端口限定取证边界，并要求合并离线修正后继续既有授权的CPU及新AT；这属于内部技术审核，不是新用户批准。待新AT实际端口证据及完整既有诊断门通过后，可按合同继续显式debug、pre_place、place/route；正式reset/CDC安全、最终物理签核仍OPEN。


### 5.25 AT010 稳定归档复核与四个辅助 CDC 枚举上限的窄解释

**CPU与输入事实：**[AT010 status](../R002/attempts/AT010_actual_reset_graph_bram_clock_cpu/status.json) 与[tests.log](../R002/attempts/AT010_actual_reset_graph_bram_clock_cpu/tests.log)记录06:52:49.486901–06:53:03.247021 UTC，93项物理入口及6项隔离测试共99项、exit0，其中包括真实已关闭119MB图的离线结构资格。A007未重新运行测试或EDA；独立逐项复算两个manifest均21/21一致，四个安装after身份一致；`inputs.sha256` SHA256=`f4cb2a9bfd8e1e89125f781133d2031fa8b36a704bfa5baaf1cec679260105d2`，`archived_sources.sha256`=`f038ca526899bc513c357575f0f33218c3507986e43feb0236e6209f56400a7a`。

[实际恢复父链](../R002/attempts/AT010_actual_reset_graph_bram_clock_cpu/actual_opt_and_reset_parent_preflight/recovery_parent.json)绑定339源/45综合DCP、AT006原失败终态、相同397,273,730-byte OPT（SHA256仍`b209decf321e4a756f3ded455e0ce162b3404467ec235b5312469f9a89171021`）及完整祖先。独立复算14份继承报告、14份primitive exports和完整fanout共29项bytes/hash全部匹配。已关闭图的身份为119,909,158 bytes、SHA256=`972611c2c4f5f9c21da17866c6546e73040f2930274ec315aad7cd62a9e17887`，此处核对其原报告身份与父链，没有再次解析整图。父链JSON SHA256=`d495acbf771e748553d4964cbece29a80c0fbf31670a7f547f3902bdc14b01fb`。

[离线reset资格](../R002/attempts/AT010_actual_reset_graph_bram_clock_cpu/actual_reset_structure_requalified.json)为qualified=true、issues空，包含7条async/4条AUX/3条HostSplit及14份exports；SHA256=`f52e4df2bbbf9caa7b58e75868e0066b282196bc4b95046230af00380056434b`。静态delta对应已审核的同安装模型默认来源、明确AUX INIT0、实际同FF C→Q归一化、raw userQ高有效断言及跨层极性折叠。实际14份exports另独立确认没有局部FDCE/FDRE module重定义或defparam；当前自动parser明确拒绝defparam及未知/重复override，但未独立编码局部同名module拒绝，故不把本次实证扩称任意Verilog输入的完整解析器验证。

BRAM delta限定同cell实际WEBWE位、REF_NAME、CLKBWRCLK/IS_CLOCK及唯一实际clock，并保留whole-cell CLOCKS；负例覆盖A端假替代、B端core、foreign cell、多/缺clock、重复及未知REF/pin/bit。新probe当前按endpoint导出688行，cell对象查询可复用；新AT仍须验证原生API结果。相同OPT/约束/工具才可继承关闭图与exports；显式debug及后续物理变换后的图与约束适用范围须以实际新证据重判，不能预填继承资格。

**集中发现的遗漏：**完整检查[actual_fanout_pending_bram_clock.json](../R002/attempts/AT010_actual_reset_graph_bram_clock_cpu/actual_fanout_pending_bram_clock.json)全部1381条issues，恰为688条BRAM端口映射缺失、688条异域consumer判定（两集合逐项完全相同）、1条缺BRAM端口文件以及4条`TARGETED_CDC_VIOLATIONS_UNKNOWN`，没有其他类别。旧Tcl在四个named `get_cdc_violations`集合数量668/668/768/769超过64时直接写该sentinel；不是report命令catch/API错误。冻结parser将所有`*_UNKNOWN`加入issues，故AT007即使688端口通过仍会被这4条阻断。该具体静态遗漏已即时实际通知主控/A006；不热改执行中AT007，不把预期阻断写成已发生终态。

相同AT006的四份已关闭`-severity Critical -all_checks_per_endpoint`报告均完整，独立提取`(rule,source_clock,dest_clock,source,target)`结果如下；总8个唯一元组与同OPT完整默认`cdc_opt.rpt`的8条Critical逐项集合相等。

| targeted报告 | 实际Critical | bytes | SHA256 |
| --- | ---: | ---: | --- |
| [opt_0：UI0→core](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/cdc_changed_opt_0.rpt) | 3 CDC-10 | 3414 | `dd84ac0ca83c91630474d858d153bcbe95f46534829a37cf1721a7a397c0280f` |
| [opt_1：UI1→core](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/cdc_changed_opt_1.rpt) | 3 CDC-10 | 3422 | `d7a16c3c859a5d5c344eb4d0fbe95731610d01f89206a61d91d3801e139f5930` |
| [opt_2：XDMA→UI0](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/cdc_changed_opt_2.rpt) | 1 CDC-11 | 2585 | `ed4dd29ec38557bec16e07d8dcdc43ea828ada4a0e55acf24fc4d6dca5834db5` |
| [opt_3：XDMA→UI1](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/cdc_changed_opt_3.rpt) | 1 CDC-11 | 2593 | `751f9dfc750d24270ed1884bd590bc4d8756aac0bc837317154ea8ddcd0dd4b2` |

本机[report_cdc说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/report_cdc)明确severity/all_checks过滤报告；[get_cdc_violations说明](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/get_cdc_violations)说明`-name`取得named result set并可另按对象属性filter。实测二者数量不同；不能将668/768等对象数称为新增Critical数，也未取得所有对象属性而擅自断定每个对象的severity。

**窄修正规则与实际审核决定：**仅当四个精确sentinel名、相应COMMAND/clockpair、已记录count>64/LIMIT64及四份同身份完整报告相互对应，且四报告8元组与完整默认报告及既定8元组严格相等时，将这四处记为辅助对象属性`coverage_limited`，保留raw sentinel/计数与报告hash，不作为本次诊断阻断。所有其他UNKNOWN、真实API错误、报告缺失或变化、额外clockpair/source/target/new Critical以及未知raw/base消费者仍阻断；完整fanout、14链结构及688实际端口门仍各自必需。此规则不扩大CDC豁免或最终签核。

主控已通过实际消息接受该窄解释，要求AT007先完成端口取证并保留原真实终态，再由A006离线运行完整组合门，将全部残余逐项处理；零隐藏拒绝后从同身份完成数据继续显式debug/place。下一修订可复用已关闭的相同OPT图/exports/报告/端口证据，不能为每个parser问题重扫图或重跑OPT。本节记录内部技术决定，没有新增用户审批或改动算法、RTL、时钟与资源合同；实际AT007端口结果和物理阶段仍待报告。


### 5.26 AT007 实际688端口闭合与 AT011 完整离线组合门

**实际端口证据：**独立核对已关闭的[AT007 bram_port_clocks_opt.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT007_bram_port_clock_debug_place_physopt/bram_port_clocks_opt.tsv)，263,752 bytes、SHA256=`1a4704be88423f55a1825911fce1c57ce24cce83624d78244aeeea386593b69c`。全部688行与AT006完整base fanout中的688个BRAM端点逐项集合相等，缺失/外来/重复均0。每行实际REF、WEBWE bit范围、所属cell、同cell CLKBWRCLK、IS_CLOCK及唯一clock全部匹配；d0的56 RAMB36E2+2 RAMB18E2共456端点实际唯一`mmcm_clkout0`，d1的28 RAMB36E2+2 RAMB18E2共232端点实际唯一`mmcm_clkout0_1`。这补齐§5.24的实际B端时钟缺口，不再仅由whole-cell时钟并集推断。

[AT007 integrity](../../../../hardware/vivado/reports/m002_E002_R003_AT007_bram_port_clock_debug_place_physopt/integrity_opt.json)（SHA256=`202325c7dc7a1c2634ff7b241252388811a5bbfc27c65d3eef7d3e838429bef7`）的reset结构qualified=true、issues空，7+4+3链/14 exports齐全；fanout确实只剩§5.25的四个targeted sentinel，顶层gate仅有由此派生的`critical_CDC`证明未成立一项。结构JSON与AT010离线版逐字节同hash。没有其他隐含端口拒绝或新增实际reset消费者反例。

**尝试终态不改写：**[AT007 status](../R003/attempts/AT007_bram_port_clock_debug_place_physopt/status.json)记录06:53:52.519055–07:05:03.471821 UTC，native/managed exit均1、stop_reason空、owned_survivors空；SHA256=`5c6a853fb20780dd43cfe20924780164f11d426c302d9bd2dd46408648f92517`。独立核实际日志只有恢复`open_checkpoint`，没有再次`opt_design`，没有显式debug/place/physopt命令。端口补证成功与整个尝试失败分别记录。

**完整离线组合门：**[AT011 actual_complete_opt_gate/integrity_opt.json](../R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/actual_complete_opt_gate/integrity_opt.json)为94,060 bytes、SHA256=`ac9614450f0dc9419f52135dfbc502f6b85105c24e1ab4c2137b1aa8d8509a1e`；实际`gate_issues=[]`，reset结构与完整fanout均qualified=true，688端口证据hash与上述原文件相同。四个raw sentinel、668/668/768/769计数、64上限及四份完整报告hash都保留于`auxiliary_cdc_observation`，coverage仅标为`coverage_limited`。CDC分类为`classified_reset_cdc_diagnostic_only`、精确8条、new_critical0；四报告并集与完整/reference报告一致，formal_reset_cdc_safety仍OPEN。

[actual_combined_status.json](../R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/actual_combined_status.json)明确scope为离线当前完整OPT hook、debug/place NOT_RUN；SHA256=`90210bf0c461b226bb8154f409816928334450b351053cefa9233477f3161e8a`。其完整gate及[递归父链](../R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/actual_parent_preflight/recovery_parent.json)文件hash独立匹配，父链SHA256=`e9317ef3b0db94643ee1039219b410fe1e368e723ae4dd44fedf1bf2e8471b11`。新父链继续绑定相同OPT字节、原失败状态、AT006图/14exports/fanout/四报告及AT007实际端口证据，没有捏造新的OPT或debug执行。

**冻结delta与CPU：**[AT011 status](../R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/status.json)及[tests.log](../R002/attempts/AT011_auxiliary_cdc_full_gate_cpu/tests.log)记录07:08:02.840957–07:08:05.954738 UTC，96项物理入口+6项隔离共102项、exit0；A007未重跑。22项archive manifest独立复算22/22一致，SHA256=`8ba3775f64ce45bc915b24fa3ddce7ec2e39c205ad75a5a27379b0f6574b77b8`，四个安装after身份均一致。静态delta只将精确四sentinel与紧邻command/count、四已知报告hash和8元组交叉绑定后分类；额外/变名/错clock/count/limit、API UNKNOWN、缺失/变更报告、全量foreign tuple的负例均保留且本次通过。恢复逻辑递归验证已关闭同OPT证据，继承已取得BRAM端口文件，不再无意义重采。

本轮实际端口、真实失败、完整离线组合门与稳定102项CPU结果已通过真实消息通知主控/A006。当前证据支持依现有授权恢复进入显式debug及pre_place检查；不是新增人工停点。`debug_materialized`与后续物理变换仍按各阶段实际新图、时钟/约束、CDC与fanout重新判定，不能把本节OPT资格当作已通过debug、place、route或正式安全签核。


### 5.27 供后续物理阶段比较的少量 OPT 路径基准

按主控要求在AT008恢复期间只读提取已有报告中的三个代表最差检查，不运行EDA、不扫描实现树。采用已绑定相同OPT的[AT005 timing_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt)（2,367,647 bytes，SHA256=`6fdd2447036515aaa449e98a759bdaaf7650b340f3e8aec0934bfc3318b843d7`）及[pulse_width_opt.rpt](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/pulse_width_opt.rpt)（2245 bytes，`1efcbd441fa55232634c795561f66e631627ff0fa68ab21f31dbf43fe572692f`）。两报告均为Vivado2025.2/build6299465、Design State=Optimized；所列数据和clock net明确标为`unplaced`，route delay是工具当前估计，不是已布线测量。全局WNS/WHS/PW及失败数沿用§5.18，不重复假设全局通过。

| 代表检查与报告定位 | 实际clock pair与路径类型 | Slack / requirement | 数据路径逻辑／布线贡献 | 解释所需的clock或硬核项 |
| --- | --- | --- | --- | --- |
| 全局最差setup，[timing第6224行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:6224) | `GTYE4_CHANNEL_TXOUTCLK[3]_1`（2ns）→`xdma_0_axi_aclk`（4ns）；Setup、Max at Slow | +0.904ns / 2.000ns | 总0.675ns；logic 0.331ns（49.037%）、route 0.344ns（50.963%）；3级，LUT6×2+MUXF7×1 | clock skew −0.400ns；DCD2.631、SCD3.921、CPR0.890ns；uncertainty0.046ns |
| 全局最差hold，[timing第2644行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:2644) | `pipe_clk`→`pipe_clk`（4ns）；Hold、Min at Slow | −0.814ns / 0.000ns | 总0.136ns；logic 0.058ns（42.647%）、route 0.078ns（57.353%）；0组合逻辑级，数据从FDRE Q直接到PCIe硬核输入 | clock skew +0.400ns；DCD3.902、SCD3.428、CPR0.074ns；硬核hold arc0.550ns |
| PCIe最差Max Skew，[PW第22行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/pulse_width_opt.rpt:22) | clock object `GTYE4_CHANNEL_TXOUTCLK[3]_1`（2ns）；同PCIE40E4两个clock pin：`CORECLKMIREPLAYRAM0`相对`CORECLK`；Max Skew、Slow | −0.012ns；required0.436ns、actual0.448ns | 此报告没有data path、逻辑／布线分解；不从其他数据路径推填 | 硬核位置`PCIE40E4_X1Y2`，波形{0,1}ns；属于clock-pin separation检查 |

setup的实际起终点位于`xdma_0/.../scalellm_vcu118_f05_bd_xdma_0_0_pcie4_ip_pcie_4_0_pipe_inst/seqnum_fifo.seq_fifo_0`，由`reg_ram_reg[3][0]/C`发起、捕获于`reg_out_data_reg[0]/D`，均FDCE；这条2ns要求不能误写为core100MHz的10ns路径。hold实际从`scalellm_vcu118_f05_bd_xdma_0_0_pcie4_ip_gt_top_i/phy_pipeline/per_lane_ff_chain[1].phy_rxdata_chain/with_ff_chain.ff_chain_gen[0].sync_rst.ff_chain_reg[1][16]/C`到PCIe硬核`PIPERX01DATA[16]`，数据net为`PHY_RXDATA[48]`。该hold的报告数字满足0.136−0.400−0.550=−0.814ns；短数据路径、clock到达差及硬核hold要求共同决定其估计违例，不能仅看0级逻辑就宣称无时序问题。

上述最差slack路径属于PCIe，不代表全设计负担均集中在PCIe。当前[Intra Clock Table第246行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:246)另列core同域WNS+2.513ns、WHS−0.106ns、761,584个hold失败端点、THS−35,837.066ns；全局992,151个hold失败端点不能只用最差PCIe样本概括。后继比较同时保留全局/clock group失败数与这些少量具体路径；若最差端点或角发生变化，应记录新的端点身份，不把不同路径的logic/route差值说成同一路径改进。

**PW展示边界：**当前命令虽为`report_pulse_width -all_violators`，本机[report_pulse_width手册](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/report_pulse_width)明确`-limit`默认1，含义是每个clock每种check type列出的数量；`-all_violators`只限制为存在violations的对象。因此本文件的一条Max Skew是已报告的最差代表，未取得全部5个PW类失败端点的逐项分类，也没有其clock路径logic/route细分。本边界已实际通知主控/A006；A006回复保持AT008冻结，在后续route入口按实际失败规模设置明确有界limit并另存输入/验证，不为此单独重跑OPT。这项基准准备不作为AT008继续运行前置，也不改变时钟目标或vendor约束。


### 5.28 AT008 显式 debug 命令、新 DCP 与本阶段待验范围

**已发生的执行：**[实际admission_opt.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/admission_opt.txt)记录`clock_coverage COMPLETE_INTERNAL / diagnostic_eligible 0 / debug_materialization_eligible 1`；实际OPT integrity的gate_issues为空、结构/fanout通过、CDC仍为限定诊断类别。这里的0没有改写为place已准入。随后[debug_materialization_command_result.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_materialization_command_result.txt)记录真实`implement_debug_core`、native_tcl_code0、起止epoch均1792048727（07:18:47 UTC），SHA256=`2d6c3d682bb8b6be36640701ea5f5c29404706c4461e53e6bffc5039f5e31119`。实际工具答复`Debug cores have already been implemented`，与先前OPT自动物化的证据一致；这不是新建一套不同debug逻辑的证明。

实际命令条件取到3个debug core：`dbg_hub`及DDR0/DDR1两core。主日志确认[debug_materialized.dcp](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_materialized.dcp)写成；独立复算397,261,751 bytes、SHA256=`e58d89707d21be85a3059a9ba7096651b6a277c125e831a47ebc7ec4f98fc44e`，包内`dcp.xml` SHA256=`2c438131a7ccd7a75abb6d57bbf2570529ea16260e43507fb57f683f109ed741`，part/top/board/Vivado2025.2 build6299465及OutOfContext0均正确。新DCP有独立身份，不能说与OPT字节相同。

**有界约束字节比较：**只读取新DCP内四份文本XDC与已核AT005 OPT对应成员比较。board XDC逐字节相同；late有233条`SRC_FILE_INFO` scoped_inst精确增加一层大括号及5条`src_info`来源行号变化，normal有3条来源行号变化，early移动一条来源metadata及版权注释。去掉确切`set_property SRC_FILE_INFO`、`set_property src_info`与注释/空行后，四文件其余命令行和顺序全部一致（late1405、early785、normal304，board无可执行约束行）。该比较保留真实字节差异，不以泛化文本归一化掩盖实际约束变化，也不替代正在生成的本阶段live clock与scope证据。

| 新DCP内成员 | bytes | SHA256 |
| --- | ---: | --- |
| wrapper_late.xdc | 1932964 | `769626c091368a33c1704675c633cb2605c99678ecf904b1ad90ca1098653930` |
| wrapper_board.xdc | 23847 | `05e6305d815ce9422faa283617f875b0a0a558bed14e2a27a2ef3800baf27fbd` |
| wrapper_early.xdc | 295216 | `52baeed126f5034a7fe8d0cfce165e75ac14f21db48460e6b7477c0f346b5059` |
| wrapper.xdc | 108897 | `67e3f8046ae00f0fa4ca4e3a0d7fedb378d289628cf07f4d0ef12b4ac4c42db3` |

**此时审核状态：**独立debug_materialized DCP已取得，完整POST仍在运行；实际hub输入/两输出/530端点clock、effective scoped XDC、本阶段新reset/CDC/fanout与最终pre_place receipt尚待完整产出。不能从显式命令成功或约束命令未变直接推出这些检查通过；没有在此登记place已开始。A006报告新timing summary数值与OPT一致且仍FAIL，该消息先作为工程阶段信息，待完整本阶段报告集中核验。已通过实际消息将上述新身份与待项通知主控/A006；不新增批准停点或扩大到事务/reset功能签核。

**随后本阶段hub时钟与scope补证已到齐：**A007独立读完整[debug_debug_materialized.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_debug_materialized.tsv)，412,711 bytes、SHA256=`c077a8af95eaf19f2d1f9ba3da99e613a5677728d348ff91b5649d58790679bb`。hub输入与两`sl_iport*_o[1]`各91个segmented nets集合完全相同，实际clock均唯一`mmcm_clkout5_1`；两输出各265个fanout C、共530个唯一端点，fanout与endpoint-clock记录逐项集合相等，全部同clock。该clock实际PERIOD20ns、waveform{0,10}、IS_GENERATED1、master为4ns `default_250mhz_clk2_clk_p`，source为DDR1 MMCM CLKOUT5；两输出实际driver均DDR1 `u_bufg_dbg_clk/O`（BUFGCE），有界source cone各2 cells，关系与未启用divider一致。

实际[debug_hub_effective_debug_materialized.xdc](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_hub_effective_debug_materialized.xdc)为14,003 bytes，SHA256=`e847680aeae1eeb36cf831ae7731d6049f4c78776847580ef4fb48a70a68ae80`，header明确本次`write_xdc -cell dbg_hub -type timing -constraints ALL -write_id`。唯一`create_clock`为第14行独立BSCAN INTERNAL_TCK的50ns；未见sl_iport、XSDB_CLK或3.333ns create_clock，所列XSDB FIFO例外以本阶段实际scope/ID留存。结合全DCP约束命令比较与实际master/source，支持本阶段hub输入—输出—530接收clock关系成立，不以局部scope快照替代祖先作用域或全设计coverage。

A006的本阶段独立parser也报告relationship_qualified=true、relationship_issues=[]，与上述原始行核验一致。`C_CLK_INPUT_FREQ_HZ=300000000`、divider=false而实际50MHz的参数差异继续明确保留；这里没有修改参数或称debug功能验证通过。该局部补证已实际通知主控/A006，其余新reset/CDC/fanout、完整POST与pre_place实际receipt仍待生成，未提前填写place准入。

**XPM合法FF的局部取证与valid导出限制：**本阶段[d0 valid_unavailable](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/xpm_d0_effective_debug_materialized_valid_unavailable.txt)及[d1 valid_unavailable](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/xpm_d1_effective_debug_materialized_valid_unavailable.txt)各633 bytes，均明确保存实际命令与`Vivado 12-2785: The two '-write_valid_exceptions' and '-to' options cannot be specified together`；SHA256分别`a7f952d4729446dd7215e8359c497a608fdc0686aabfcd6bcc593aaf37957dd7`、`c2f6a70631787c2c963c32a6082caae877fc8f8b6771282e385fab67b6fbc1cc`。没有将不存在的valid.xdc称为成功导出。§5.11仅核到手册分别列出这些选项，没有证明两选项可组合；冻结代码的四类cell查询实际仅在`debug_materialized`运行，旧AT005没有这组局部文件，不能补称此前OPT已验证该导出组合。

两处已关闭effective/ignored/scope_override报告各2933/2144/3777 bytes。d0的vendor例外位置662、d1位置686，均为`max_dpo=10 / Invalid endpoint`；[d0 scope_override第18行](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/xpm_d0_effective_debug_materialized_scope_override.rpt:18)与[d1第18行](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/xpm_d1_effective_debug_materialized_scope_override.rpt:18)实际明确`Totally overridden path by CG 171`，不再仅凭LATE顺序推测。两份ignored均为`No ignored timing exceptions found`；不同report选项观察范围不同，不能将此句覆盖scope_override的实际结果。两scope报告SHA256分别`82be704482fb04c238f61c410d1e446999ae7389fea3fe73b00005182a1cec59`、`8689d94b202d17d4ab82b27eae10028b7002e64953fda65356cd3eac0a9d38f0`。

已关闭[d0实际D timing](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/xpm_d0_effective_debug_materialized_timing.rpt)为56,269 bytes、SHA256=`35d5f0873cffd94feaa621adc5872976eff08b280d95039f4aa4601517b64ec2`：4条有界Setup Slow样本均为UI0→UI0、5ns要求、slack+4.158ns，捕获于确切合法`doutb_reg_reg[0]/D`；这是合法D端实际路径存在且有时序分析的证据，不代表全跨域路径或整项约束安全已签核。此时d1实际D timing仍在生成，未预填同样结果。

静态核对当前完整gate与`pre_place_evidence`：它们没有将valid.xdc列为成功条件，也没有给两XPM局部导出写自动PASS；Tcl的catch保存辅助查询失败后继续。当前程序并无单独的XPM valid-export资格分类，不能把未检查包装成已通过。由本节独立原证据审核保留这项导出能力限制及Constraints18-401/完整约束安全OPEN；该API选项组合错误本身不是设计反例，不触发新增EDA、全局导出或人工停点。以上更正与边界已实际通知主控/A006，当前阶段其余真实结构/CDC/pre_place门照常执行。


### 5.29 AT008 完整 pre-place 证据与真实布局启动

**执行里程碑（独立观察截至2026-10-15 08:03:10 UTC）：**本阶段完整POST已关闭，[pre_place_evidence.json](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/pre_place_evidence.json)为2591 bytes、SHA256=`b6a1fc8785afa7e4963c79577e44a2c5a99d5ecdd3678a02c8e6f5f8588c1c5b`。其6项小文件链接（condition、command、result、admission、constraints、integrity）均独立复算bytes/hash匹配；checkpoint绑定§5.28已独立核验的397,261,751-byte新DCP及`e58d8970…fc44e`完整hash，本轮只再次核stat，未重复读取该400MB包。receipt phase为`debug_materialized_pre_place`、physical_signoff=false。

[vivado.log第205行](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/vivado.log:205)真实调用`place_design`，第210/214行两次precondition DRC均0 Errors；第218行`Starting Placer Task`，第224行Phase1.1 checksum=`1f9be8a04`，第230行Phase1.2 IO/Clock Placement checksum=`15705e5ad`，第234行进入Phase1.3 Build Placer Netlist Model。实际初始化、排序、IO/时钟布局子阶段已执行，不能仅概括为发出命令；此时尚未取得place完成receipt/DCP或phys_opt结果。A006继续负责唯一EDA流程、进程资源和原09:08:25 UTC截止时间，本审核未控制进程或运行EDA。

**实际准入与约束身份：**[debug_materialized_result.txt](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_materialized_result.txt)为completed1、diagnostic_eligible1、debug_materialization_eligible0、blackboxes0、COMPLETE_INTERNAL，reset_io_review与cdc_review仍OPEN。空blackboxes导出与[check_timing](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/check_timing_debug_materialized.rpt)一致：no_clock、constant_clock、pulse_width_clock、unconstrained_internal_endpoints、multiple_clock、generated_clock异常和各loop均0；no_input_delay1恰为pcie_perstn，no_output_delay2恰为两个DDR reset_n。原3个reset IO分类没有变成完整IO签核。[本阶段clocks第48行](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/clocks_debug_materialized.rpt:48)再次确认core10ns、两个UI各5ns、hub所属mmcm_clkout5_1为20ns；hub实际输入、两输出和530端点关系及有效scope沿用§5.28同阶段已完成的独立核验。

[constraints_debug_materialized.json](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/constraints_debug_materialized.json)为194,906 bytes、SHA256=`0c19c5af50b15cbebffe82db38554fb1fb2696d21d65984535887a230815e1c2`。与当前OPT记录相比，仅phase及parent/registry/actual_reads链接改变；162项metadata、175项hash、13个生成候选/归档及其余内容完全相同。新三个链接均独立复算匹配，mode仍`embedded_checkpoint_inherited`、new_actual_reads=[]，不将空的临时project约束列表或无新read_xdc说成主设计没有约束。DCP内四份XDC实际命令及顺序比较已在§5.28单独完成。

**新reset结构的有界审核：**[reset_structure_debug_materialized.json](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/reset_structure_debug_materialized.json)为77,252 bytes、SHA256=`8cddf085397d7c7f392349a17578e7384bdcad062f05fc026846076396d4ecc6`，qualified=true、issues=[]。其新图来源为119,909,634 bytes，工程parser记录SHA256=`61a8189c5572500504d0ef6ccd703250635dc27aad01e0c39d86298d1cf2d4fc`；本轮核对该来源路径、stat及与integrity/proof_sources一致的身份，不再次扫描或解析119MB图，也不称图hash在本轮重新独立计算。

结构摘要与已审核OPT逐字段比较，仅source及explicit_primitive_exports身份改变；7条async、4条AUX、3条HostSplit的链、clock、源锥、实际C→同FF Q对应、已分类receiver等全部相同。14个新局部Verilog exports的bytes/hash逐项独立匹配；去掉严格的`//`注释行和空行后，其余原文与对应OPT exports逐行完全相同。直接查看新export primitive声明再次确认28 FDCE全部显式INIT1，core base/ready0/1与两个DDR ready共20个CLR inversion1、两个DDR base共8个inversion0；16个AUX与12个HostSplit FDRE均显式INIT0。没有同名FDCE/FDRE module或defparam。实际安装FDCE/FDRE模型bytes/hash与§5.26所用身份一致；未将模型默认参数当作工具显式override。

**完整CDC与fanout交叉核验：**[新CDC报告](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/cdc_debug_materialized.rpt)3,941,328 bytes、SHA256=`56dc481b7aa5d5465d295841613ed9c5e4c89190840eecb0acb0fecdf593f928`。独立按实际clock分区提取8个唯一Critical元组，与已核OPT及合同明确的8个rule/clock/source/target集合逐项相等：6 CDC-10、2 CDC-11，无新增或缺失；保留`classified_reset_cdc_diagnostic_only`、formal_reset_cdc_safety=OPEN。

[新完整fanout](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/cdc_changed_reset_debug_materialized.tsv)5,960,757 bytes、SHA256=`b3b5e36463819e52fddc34beb869ac2298d348ac4de553f0741e0ce7f8318494`。独立比较全部10个source/base/HostSplit端点集合，与AT006已审原集合完全相同；各组声明计数=实际行数=唯一端点数，未出现UNKNOWN或截断。ready0/1各6362/5282，calDone各938，XDMA Q共73，base0/1各6362/5282，三个HostSplit tail各1。raw XDMA到UI0/UI1的实际分支精确等于预期5/6项，只有各base四个CLR和对应HostSplit stage0 D。

[新BRAM端口导出](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/bram_port_clocks_debug_materialized.tsv)263,752 bytes、SHA256=`1a4704be88423f55a1825911fce1c57ce24cce83624d78244aeeea386593b69c`，与§5.26已完整独立验证文件字节相同，但此处来自新阶段取证。再次将其全部688端点与新fanout BRAM集合对照，缺失/外来/重复均0；实际REF、WEBWE合法bit、同cell CLKBWRCLK及IS_CLOCK均一致。base0分解为5904个本UI普通端点+456个实际UI0 BRAM端点+2个精确core AUX；base1为5048+232+2，foreign0。支持沿用端口限定诊断解释，不扩大raw reset直达消费例外。

**辅助枚举字段的适用边界：**当前integrity的`auxiliary_cdc_observation={coverage:not_limited,raw_sentinels:[],reports:[]}`没有证明旧OPT对象属性枚举覆盖已补齐。冻结Tcl第471行明确对非OPT阶段跳过该辅助枚举，parser第187行只因无sentinel返回此字符串。实际OPT的coverage_limited及四份报告的窄解释仍保留；本阶段的新完整CDC8元组、全量fanout和结构门分别重新取得并核验。该字段语义边界已实际通知主控/A006；A006确认不热改AT008，后继合法入口可只澄清标签而不改变准入。

**d1 XPM补齐与时序结论：**[d1实际D timing](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/xpm_d1_effective_debug_materialized_timing.rpt)已关闭，51,341 bytes、SHA256=`67c250e543a40fd4c2868077cbc9badb09e6b4dc5a6a425f7d173d29ac4d1e9b`。4条有界样本均为同一合法doutb_reg_reg[0]/D、UI1→UI1、Setup Slow、5ns要求、slack+4.158ns；data0.664ns（logic0.290、route0.374）、2级（LUT4+RAMD32）、clock skew−0.145ns。与d0一起证明所选合法D端存在实际分析路径；两个valid导出的API不兼容及Constraints18-401/完整约束安全OPEN仍保留。

[本阶段timing](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/timing_debug_materialized.rpt)2,367,668 bytes、SHA256=`6e0fc7c2b5183a839f8949631da2a99e56223de86845c9829f228cc1bd186cf0`，全局与OPT相同：WNS+0.904ns/TNS0，WHS−0.814ns/THS−48989.652ns、992151个hold失败端点，WPWS−0.012ns/TPWS−0.037ns、5个PW失败端点，明确`Timing constraints are not met`。这仍是Optimized/unplaced报告；place后结果尚待取得。

**本次独立审核判断：**[integrity_debug_materialized.json](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/integrity_debug_materialized.json)92,438 bytes、SHA256=`4ca895baa93da4d59e421b2e21cb56acaedca099213a2273492991916ff7866f`实际gate_issues=[]，本轮有界原证据核验支持已授权诊断place继续。execution为真实place进行中；verdict只覆盖本阶段诊断准入与身份/限定结构/时钟关系；applicability限于当前AT008新debug DCP及冻结合同；review为A007内部阶段核验完成。没有登记用户新批准、最终时序通过、复位释放/事务安全通过或布局完成。关键结果已通过实际消息分别送达主控与A006；head-wave增量由A004独立负责，不重复其完整解析。


### 5.30 AT008 Place 30-1229：当前 IP 的 SLL 放置意图未满足

**实际异常与范围：**[A006封闭告警事实](../R003/attempts/AT008_complete_opt_gate_debug_place_physopt/place_30_1229_warning_facts.json)4103 bytes、SHA256=`0468b48593074fcd234bc6c6c76739fcc1e08d23029790f9df37727e0fd1811e`，绑定[不可变日志前缀](../R003/attempts/AT008_complete_opt_gate_debug_place_physopt/place_30_1229_log_prefix.txt)54,198 bytes、SHA256=`d78585f0f64ce6e393ff16de47bf5c126aca0ed6085adccf260e73ab0bcb888a`。A007独立复算匹配、确认与当前live日志前54,198 bytes逐字节相等，6个样本与抑制行行号/原文均一致。第250–349行恰100条可见WARNING、100个唯一cell；第350行另有1条消息抑制INFO，不能将101个字符串命中说成101条warning，也不能把100当全部受影响cell数。

原文是`SLR partitioner was not able to find solution that obeys USER_SLL_REG property`，随后明确`Ignored property`。这100个可见对象均在d0_mig_slice的AR通道`ar15.ar_multi/triple_slr.fwd`，含payload、ready、reset、handshake寄存器；样本不仅有slr_middle/slr_slave，亦有slr_master reset对象。抑制后其他通道或d1是否有同类问题未知，不从显示顺序推断故障仅限d0。native日志没有逐warning时间戳，事实文件已将资源采样观察锚点与未知实际发出时刻分开。08:23:44 UTC独立观察，布局继续到Phase2.1.1.3 PBP Discrete Incremental，尚无place完成或fatal结论。

**属性来源确在当前综合配置：**[create_vcu118_board.tcl第488行](../../../../hardware/vivado/scripts/create_vcu118_board.tcl:488)的两个profile，以及第507–523行对d0/d1_mig_slice的实际配置，均明确五通道REG15、USE_AUTOPIPELINING0、NUM_SLR_CROSSINGS2，MASTER/MIDDLE/SLAVE各一段pipeline。当前脚本38,045 bytes、SHA256=`f395ccf4fb08e75195dfcc24cd63b4427e9ca9ef0c6f5439d00743df475c0c35`，与fresh synth的339输入manifest逐字节身份一致。两份当前XCI也均独立复算匹配该manifest：d0为40,155 bytes、`4c2ea70a4816bdaef0950e6246451b2d5333501cb0ba23bcfa4a7fc69aa96548`；d1为40,155 bytes、`803ded31112920bd83ac0cca1176b991da9cf4e7846bb9b1e106603ce6ca0c07`。实际component均`xilinx.com:ip:axi_register_slice:2.1`、revision36，component参数的value_src=user，生成model参数与上述数值一致。配置不是当前place中新加入的物理约束。

当前生成IP的[axi_register_slice_v2_1_vl_rfs.v](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ipshared/bc4b/hdl/axi_register_slice_v2_1_vl_rfs.v:2355)174,589 bytes、SHA256=`82727d8cd17427489629f7b4e56fac7321c31b3043e3be44882fda731f472ecf`，由该IP的生成XML列为HDL源。第4606/4617行在REG_AR15选择ar15/ar_multi，第2355行在C_NUM_SLR_CROSSINGS2选择triple_slr；第2750–2776行直接给Laguna reset/payload/ready寄存器添加`USER_SLL_REG="true"`，第2823/2834行亦给FDCE handshake实例添加该属性。FDCE仍有明确INIT0、ACLK、CE1、CLR=ACLEAR及实际D/Q连接；属性与这些功能连接分开表达。[生成仿真网表](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ip/scalellm_vcu118_f05_bd_d0_mig_slice_0/scalellm_vcu118_f05_bd_d0_mig_slice_0_sim_netlist.v:33087)也保留payload FDRE的USER_SLL_REG。此生成HDL/仿真网表用于解释当前IP实现来源，不当作当前placed网表或功能验证。d0综合IP DCP另独立复算1,050,154 bytes、SHA256=`98b23e9e8d8b0852a186371aec790dc24687a3dad81b5f45fc8aa67c1fc216ba`，与现父链的synth_checkpoint_bindings一致；当前主设计中属性实际存在的直接证据仍是这次placer的明确cell告警。

**当前有效约束不被改写：**只读检查§5.28新debug DCP的四个XDC成员，均没有USER_SLL_REG设置命令。d0的[clocks.xdc](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ip/scalellm_vcu118_f05_bd_d0_mig_slice_0/scalellm_vcu118_f05_bd_d0_mig_slice_0_clocks.xdc)710 bytes、SHA256=`2aaba35a2e49e7572ea5cfbba29d4f9c6260d3a523271f1e70aad171a64016d5`，与当前constraints记录一致。它解释multi-SLR模式的异步清除，并设置既有`set_false_path -through ... CLR ... *asyncclear*`；DCP late XDC第911–913行在确切d0_mig_slice/inst作用域保留该命令。OOC的5ns aclk约束与该物理放置属性是不同内容。不能将本告警解释成新增跨域豁免，也不能据既有vendor false_path宣称异步复位安全已签核。

**架构判断与继续条件：**本次具体反例是部分当前IP的SLL/Laguna寄存器放置属性未被partitioner满足；不得宣称预期两次SLR crossing、所有Laguna映射或其性能收益已经实现。工具尚未给出非法放置、不可布通、容量超限或功能连线改变的证据，因此该warning本身不足以中止合同允许的诊断布局，也不足以证明功能完全不受影响。它可能影响这些跨区域payload/ready/handshake路径的物理延迟、hold修复、布线压力与拥塞，影响大小须由后续实际布局/布线证据区分；不能仅凭此warning把后续所有负slack归因于它，也不能猜测根因已确定为容量或某个固定SLR归属冲突。

当前应保留为“当前IP物理放置意图未满足”的基线限制，继续冻结AT008及原资源/时间额度。合同本就不以旧Pblock/固定SLR归属作为新验收，所以不为恢复该意图立即增加硬LOC/Pblock、删除属性或重配REG15；此类改变若后续有具体瓶颈支持，应形成独立可比较尝试并评判pipeline/接口时序影响。本轮没有建议新审批停点或重跑。

后续只利用已有place/physopt/route完成、DRC、资源/拥塞及实际关键路径报告，判断是否合法完成、这些样本是否真的处于违例路径以及逻辑/布线贡献。A006已实际回复：若正常进入后继route入口，在其自然加载DCP时限定已保存6个样本，记录实际LOC/BEL/site/SLR和每个样本至多一条入/出D/Q路径；不存在、被变换或无路径如实记录。无需恢复全部被抑制warning、另开EDA或当前热改探针。该有界取证只解释样本的实际位置和性能，不反推全量USER_SLL_REG满足率。

**审核状态：**来源与影响范围核验完成，诊断继续的既有判断保持；place执行仍进行中，正式功能/reset/CDC及物理签核仍OPEN。已通过真实消息向主控/A006报告来源、计数边界、继续理由和后继最小证据，未修改脚本、约束、RTL或任何原始运行证据。

**恢复成本的只读补充（当前AT008仍运行，非重跑决定）：**若最终没有closed place DCP，§5.28–5.29已经关闭并审核的debug_materialized DCP及同身份pre_place_evidence可作为真实完成的“debug后、place前”恢复点；它不保存当前GlobalPlace的部分进度。[冻结POST第571行](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/stage_sources/m002_diagnostic_common.tcl:571)先写该DCP，其后是报告、只读取证和门检查；[冻结主入口第151–153行](../../../../hardware/vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/stage_sources/m002_resume_physical.tcl:151)在完整POST及pre_place完成后才运行place。对完全相同的DCP、工具、源与embedded约束，可明确继承已关闭完整POST，仅恢复身份、零黑盒、关键clock/hub、实际约束恢复状态及原生DRC等有界live sanity，不重复119MB结构图及全套报告；任何真实身份差异须先判定适用性，不能伪称证据未变。

现冻结恢复入口仅支持init与post_opt_pre_debug，尚没有上述阶段；若后继采用，需先保留AT008真实终态，再建立明确的新恢复阶段、继承来源和父链适配及必要验证，不能只改环境变量跳过现有门。已测成本是07:08:41启动至约07:52进入place共约44分钟，其中显式debug于07:18:47完成后至pre_place约33分钟。复用可避免这段重复POST及部分旧准备，但checkpoint打开、身份核对和live sanity仍有成本，净节省必须实测，不能承诺省满45分钟。这是有具体前置成本缩减机制的方案，不能证明布局在余下额度必然完成；不据此预授权/启动新尝试或延长当前09:08:25 UTC截止，不改变任何检查含义或接口。

**随后真实终态及主控执行决定：**[AT008 status](../R003/attempts/AT008_complete_opt_gate_debug_place_physopt/status.json)已关闭于09:08:31.322092 UTC，2424 bytes、SHA256=`cb4b8dc38d74a150f24186fe83582095b8177a4134a5b6ae2c2f15293b73a34d`；managed exit124、native−15、stop_reason=stage_wall_timeout、owned_survivors=[]。独立核日志末段为Phase3.3 Area Swap Optimization、checksum=`15c11d04b`，place/physopt两命令receipt及两DCP全部不存在，不能登记布局完成。debug DCP与pre_place仍完整，未生成新的物理恢复点。主控此后通过真实消息决定由A006实现一次有界post-debug/pre-place恢复入口，受影响CPU回归通过后自动启动；沿用2小时/8CPU/单EDA，若再次没有新closed物理DCP不重复place。这是当前合同内的实际技术执行决定，不回填为此前用户审批或扩展AT008原截止。A007并行只读审核父终态、同DCP POST继承及新/继承命令区分，仍仅维护本记录；新入口尚待冻结和实际验证，未预填通过。

**随后AT012冻结核验完成：**[CPU status](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/status.json)记录09:41:02.430147 UTC完成、exit0；本轮实际新执行13项恢复测试及6项managed/isolation测试，共19项，96项旧诊断测试明确复用AT011，不能合称本轮重跑115项。A007独立复算[archive manifest](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/archived_sources.sha256)的22/22项一致，manifest SHA256=`e814b3c37a434a0d9253b5a1a2c6a18a92aa2aeb7b0686c8778cf6d766c0f6a7`；[installation](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/installation.json)的5项before均对应AT008冻结源，6项after均与实际安装及flat archive相符。旧诊断测试源与AT011同hash。新增测试覆盖父终态/身份篡改/重复恢复拒绝、fresh guard失败、历史与当前receipt隔离、finalizer/route父链及实际tclsh分支顺序；这些CPU与mock验证不冒称真实EDA。

静态审核确认新`post_debug_pre_place`入口要求真实timeout、无survivor及无新place/physopt产物，拒绝同种再次恢复；精确继承原DCP、源/embedded约束和完整POST。原OPT/debug仅列为`historical_command_receipts`，当前命令receipt只允许place/physopt；新`restored_completed_pre_place`凭据独立绑定旧证据，不覆盖旧receipt。place前执行限定的当前零黑盒、7+4链计数、clock/hub/530端点关系、check_timing/reset IO及原生DRC检查；同DCP有效hub scope显式继承，raw实际clock新取。新分支不重复OPT/debug或全图POST；place后仍须正常新取证。未发现身份或阶段混淆缺陷，无新增人工停点。

**真实原证据回放与补档：**[AT008完成闭合记录](../R003/attempts/AT008_complete_opt_gate_debug_place_physopt/completed_pre_place_post_completion.json)只是终止后封存原来已完成的68项pre-place/POST身份，没有重生成报告或虚构place成功。[AT012实际离线回放](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/actual_replay_status.json)的完整gate_issues=[]，688 BRAM端点、8条诊断CDC、7+4+3链及14 exports均保留，正式安全OPEN。v1因复制图内的原export路径触发目录保护而失败；v2保持实际结构parser不变，在原图路径解析，再将派生hook输出写入v2目录，不视为新网表或EDA证据。审核曾发现同名driver更新后v1历史字节缺口，现已独立核实[补回的v1原字节](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/historical_replay_driver/replay_completed_pre_place_v1.py)为3886 bytes、SHA256=`b451592c476ca95662e002d35088ea5890bb85a57ee978d1553e0f742351669b`，精确匹配旧manifest；[resolution](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/historical_replay_driver_resolution.json)保留原路径映射，旧manifest及失败日志未改。当前v2 driver另匹配v2 manifest，历史来源问题已解决。

**AT009真实父链与启动，fresh guard尚待实际结果：**[冻结实际恢复父链](../R002/attempts/AT012_post_debug_pre_place_recovery_cpu/actual_completed_pre_place_parent_final/recovery_parent.json)为206204 bytes、SHA256=`cb71534a967e2ed472962cd1dc18c7bdcbeba463e059e13dafac140d3f0f3a8e`，与[AT009父链](../../../../hardware/vivado/reports/m002_E002_R003_AT009_completed_pre_place_recovery_place_physopt/recovery_parent.json)逐字节相同。A007核93项小文件身份引用均一致（含重复引用，并非93个唯一文件），包含62项继承报告与17项proof来源；大DCP/图沿用既有已审身份，未重复扫描。实际[command](../../../../hardware/vivado/reports/m002_E002_R003_AT009_completed_pre_place_recovery_place_physopt/command.json)SHA256=`6a83a5a63ca3c398eeb1e468e2ca5f386ac8a7d9fc6fa1977fb37e5006ecfd95`，准确设置`post_debug_pre_place`、原AT008 debug DCP及原pre-place目录。managed启动09:41:02.527929 UTC、deadline11:41:02.527929 UTC；命令记录启动09:41:25.458760 UTC，两时间含义分开。本轮已核启动日志止于`open_checkpoint`/Read ShapeDB Complete，尚未核到新guard、place或physopt完成，不把运行中的terminal status缺失判成失败。

本次execution区分AT012已完成与AT009已启动；verdict仅支持冻结恢复语义、实际原证据继承及安装身份；applicability限同一AT008 debug DCP、冻结源/约束和既有2小时/8CPU/单EDA合同；review为A007本阶段核验完成，后继fresh guard/物理结果待实际证据。此前unplaced hold/PW失败、USER_SLL_REG放置意图未满足及正式reset/CDC/事务安全OPEN全部保留。此次不等待整段EDA结束，不预填布局、时序或签核通过。

### 5.31 仅补缺失物理阶段：私有候选静态审核

**范围与身份：**主控在AT009仍运行、尚未确认新closed物理点时委派本项并行只读审核；原11:41:02 UTC截止及“无新closed点不再place”保持。A006提供[review_snapshot_v1 manifest](/tmp/m002_missing_physical_stage.t6xp0wzs/review_snapshot_v1/candidate.sha256)，1075 bytes、SHA256=`460040b2013d81fa0d84f5be78dcb35f1389b5e2ef298c5e1d325b4320f02b56`。A007独立复算7/7项一致：五份候选脚本、新恢复测试及终态封存脚本。本节只覆盖该私有快照的静态行为；尚未安装、未取得本轮CPU/实际父资格结果，A007未运行测试或EDA。后续正式归档与修复delta须另关联真实身份，不能把本快照审查当作最终安装验证。

**阶段与来源：**`recovery_physical_parent`要求原真实timeout124/native−15、无survivors及终止后封存；封存脚本按采样PID/start_ticks确认同身份进程消失。恢复点还须同时具备成功native命令receipt、实际日志checkpoint关闭消息、同字节DCP与part/top/board/tool包身份，并校验命令晚于原恢复guard。place点只运行fresh guard→缺失POST（或同DCP完整POST继承）→新physopt→POST；physopt点只运行fresh guard→缺失或完整继承POST，两分支均无place命令。完整继承要求completed/diagnostic资格、零黑盒/内部clock完整、空gate_issues、结构/CDC证明及绑定的必需报告；partial不满足时重新取得POST，不能复制后标完成。更后的physopt恢复点还需其真实合格place前驱。`frozen_source`对历史父链使用原stage archive，不将新安装脚本身份套到旧执行；其余设计/probe输入变化仍拒绝，当前新guard仍检查本次实际输入manifest。

**审核结论与边界：**历史命令始终保留原路径；place点的当前命令集合仅`physopt`，physopt点为空集合，合并历史后必须精确覆盖OPT/debug/place/physopt且无重叠。route父链仍检查实际launcher/managed成功终态、无survivors、完整physopt产物与身份和恢复准入，不以存在DCP或本静态意见代替资格。未发现该快照的实质阶段/来源缺陷，已通过真实消息通知主控/A006，不新增批准停点或扩展guard。execution为候选准备；verdict/applicability限上述静态快照；review为静态核验完成。AT009是否产生可用恢复点、最终CPU和安装验证均待原负责人真实证据，物理/时序及正式安全签核仍OPEN。

### 5.32 AT009 Place 30-1995：DDR1 时钟可编程延迟上限

**实际告警：**[AT009日志第868行](../../../../hardware/vivado/reports/m002_E002_R003_AT009_completed_pre_place_recovery_place_physopt/vivado.log:868)及下一行分别指向`scalellm_vcu118_f05_bd_i/ddr4_1/inst/u_ddr4_infrastructure/c0_riu_clk`和同前缀`u_bufg_divClk_0`，原文均为`Horizontal BUFCE_ROW programmable delay is capped at 4 ... due to BITSLICE_CONTROL_PLL_RIU MAX_SKEW requirements`。它们位于Phase4.1 Post Commit Optimization、Timing38-35之后；11:30:16 UTC是主控阶段观察时间，原日志行没有独立时间戳。A007核到两条原文，包含它们的前869行共124309 bytes、SHA256=`292e2f96f4c5982ae25e4894e6c57155f33ac47d9ee5c1a417a36a90236974b7`，该身份只覆盖日志前缀，不把仍增长的整份日志称为冻结文件。

原文说明placer为满足DDR PHY中`BITSLICE_CONTROL`的PLL/RIU时钟引脚Max Skew要求，限制相关水平时钟缓冲的可编程延迟控制值。这是时钟延迟调节范围受到限制的证据，文字未给出“4”的时间单位，不能解释为4ns或4个周期；也没有报告实际skew、slack或违例端点数，不能把两条warning计作两个Max Skew失败。已有OPT实际路径将[c0_riu_clk](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:12558)对应至DDR1 MMCM CLKOUT6→u_bufg_riuClk/O→该net，即`mmcm_clkout6_1`、10ns；[u_bufg_divClk_0](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:11115)对应CLKOUT0→u_bufg_divClk/O→该net，即`mmcm_clkout0_1`、5ns。时钟名/周期另见[clocks_opt第50行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/clocks_opt.rpt:50)及第53行；不将RIU的10ns误写成DDR UI周期改变。

| 已有OPT中的检查族与代表对象 | Required / Actual / Slack（ns） | 与本次告警的关系 |
| --- | --- | --- |
| DDR1 `BITSLICE_CONTROL/PLL_CLK`相对`RIU_CLK`，Slow；`pll_clk[0]_1`、byte0，[timing第1630行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:1630)；`pll_clk[2]_1`、byte10，第1727行同数值 | −0.300 / −0.656 / +0.356 | 与告警命名的PLL/RIU Max Skew规则族对应；这是带方向的有符号检查，不能将绝对值0.656与0.300比较而误判失败 |
| DDR1 `BITSLICE_CONTROL/RIU_CLK`相对`PLL_CLK`，Slow；`mmcm_clkout6_1`、byte0，[timing第2118行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/timing_opt.rpt:2118) | 2.818 / 1.858 / +0.960 | 同一引脚族另一方向的代表检查；所示OPT样本为正slack |
| PCIe `PCIE40E4/CORECLKMIREPLAYRAM0`相对`CORECLK`，Slow；`GTYE4_CHANNEL_TXOUTCLK[3]_1`，[PW第22行](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/pulse_width_opt.rpt:22) | 0.436 / 0.448 / −0.012 | §5.27原最差Max Skew，属于另一硬核与时钟引脚规则；不能用其−0.012ns给DDR1告警定性 |

上述OPT报告仍为Optimized/unplaced，身份沿用§5.27；代表样本的正slack不证明当前placed/routed阶段通过，也不证明DDR1全部检查通过。当前告警本身既不构成新增时序违例判据，也不证明placer最终成功；后续只按原流程产生的实际时序/PW及完成证据判断。execution仍属AT009运行中的告警观察，verdict限该文字及既有OPT对应关系，review为本项有界解释完成；不运行EDA、不热改输入、不新增门，原11:41:02 UTC截止保持。结果通过真实消息通知主控与A006。

### 5.33 AT009 真实终态与本阶段最终有界评判

**执行终态：**[原status](../R003/attempts/AT009_completed_pre_place_recovery_place_physopt/status.json)2447 bytes、SHA256=`80bb8f8fbd5893d4108a8ef8648b7c1f763ce3f2b08b98229d12825a41efc18d`，09:41:02.527929–11:41:11.046467 UTC，managed124/native−15、`stage_wall_timeout`、owned_survivors=[]。固定7200秒截止为11:41:02.527929 UTC；随后约8.5秒终止/回收不登记为批准延长。status的`execution_state=completed`只表示managed尝试已结束，不是设计完成。[terminal_facts](../R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)7399 bytes、SHA256=`fcd1c0f205c3abe6a5b24d6420092b34ac0eeed7a046c2e478167e5bbbaf5561`保留原终态。A007独立核13项小文件身份引用全部一致（含原resources，不重读大DCP/图），并确认其中7个PID均已不存在：6个资源采样身份及另列supervisor。最大进程树RSS32.278GiB，低于192GiB限额；原停止原因是时间上限，不是报告中的内存或磁盘阈值触发。

**实际推进与缺失产物：**[最终日志快照](../R003/attempts/AT009_completed_pre_place_recovery_place_physopt/final_vivado_log_snapshot.txt)128349 bytes、SHA256=`b3029451d0e077b22066341bf955f166b91b5c0ad4be334f1f018d7699f99242`与原日志相同。Phase3 Detail Placement已给checksum，最后完成子阶段是4.1.1.2 BUFG Replication、checksum=`2673ec0ef`，末行停在4.1.1.3 Post Placement Timing Optimization。已出现的原生物理命令只有`Command: place_design`，它没有成功返回receipt。A007直接核报告根目录无任何DCP，仅有pre_place_restore命令receipt；place/physopt两receipt、两DCP、两份timing与integrity全部不存在。日志中的`Starting Physical Synthesis Task`及Physopt消息属于place内部优化，不能登记为后继独立phys_opt_design已经执行或完成。无新closed物理点，内存中的部分布局进度随终止丢失。

**恢复成本假设的实际结果：**[pre_place_restored_facts](../R003/attempts/AT009_completed_pre_place_recovery_place_physopt/pre_place_restored_facts.json)6535 bytes、SHA256=`8041309d8a16bf61bc3a8edea9329ec13bfe1581af0f37d92977549c03917f84`记录本次stage启动至pre-place凭据748.398秒，AT008对应2629.541秒，减少1881.143秒（31分21.1秒）；pre-place时剩余6451.602秒（107分31.6秒）。口径为各次实际启动至receipt文件完成时间，包含恢复、preflight和凭据生成，不等于纯算法运行时。实际新receipt phase为`restored_completed_pre_place`；有界guard native0、166秒、BB0/DRC blocker0、clock groups verified1。本轮确实避免了重复完整POST的前置成本，且推进超过AT008终止位置；但仍没有在本次2小时/8CPU额度内取得closed place，不能把成本收益说成完成布局或时序收敛收益。

**中间估计的适用边界：**[BUFG优化事实](../R003/attempts/AT009_completed_pre_place_recovery_place_physopt/post_place_bufg_opt_intermediate_facts.json)6993 bytes、SHA256=`49be5f726ba6ff3f0ddcc5486d3ff51cdee31d2de0db953e6af754bff36daa09`的逐行原文与最终日志独立匹配。`Estimated Timing Summary`为WNS−1.884ns/TNS−1349.388ns，仅限place内部4.1.1.1优化的中间估计；没有完整端点/clock pair/hold/PW报告，不能作为正式placed指标，亦不能和OPT的+0.904ns直接宣称同一路径退化。该轮BUFG insertion识别10个唯一net，插入0、driver复制0、placement/routing conflicts跳过10；后续BUFG replication候选0。对象包含MLP repack/共享控制/累加和Attention in_fire等，属于值得核查的具体优化候选集合；没有全部高扇出覆盖、冲突资源明细或实际关键路径关联，不能据此证明BUFG容量耗尽、全局不可布通或全部负slack由这些net造成。这里的routing conflicts是局部优化跳过原因，不是route_design失败。

**合同内最终判断：**execution为本次有界尝试已因成本停止，place未完成、后继独立physopt与route均NOT_RUN；verdict支持“同debug DCP继承完整POST能显著降低前置成本”，不支持“当前额度内已获得可用物理候选”。applicability限本综合/约束/工具身份及这两次受限物理尝试；review为A007本阶段证据评判完成。当前证据不足以判定总体架构最终可布、不可布或可达目标时序，也不构成Hadamard、ScaleCode、format05算法被反驳的证据。按主控已有一次恢复边界，本合同不再place，不运行§5.31 missing-physical候选，也不启动route；该候选没有合法的新closed父点，静态核验不产生执行资格。原USER_SLL_REG意图未满足、DDR1 delay上限及正式reset/CDC/事务安全OPEN继续保留，无bitstream或板卡结论。

**若后续另立实验，优先解决的证据与方向：**

- 首要缺口是可重复取得的closed place/physopt DCP及完整POST：实际setup/hold/PW端点、clock skew、SLR利用率/拥塞和逻辑/布线贡献。未来实验需先约定取得该证据的布局策略、阶段成本与停止条件；本节不扩大当前预算。
- 最有具体对象依据的结构方向是MLP/Attention控制与repack广播的物理局部性：先把上述10个net的实际fanout、跨clock-region/SLR范围、关键路径和资源冲突对应起来，再单变量评估局部复制、分层控制或保持协议语义的流水候选。现有日志只提出可证伪假设，不直接授权RTL改变或强制BUFG插入。
- AXI Register Slice的USER_SLL_REG实现意图及DDR1 PLL/RIU时钟限制分开评判；只有取得实际位置/跨SLR路径和对应Max Skew报告后，才比较IP流水/物理策略的收益，不能以告警或旧OPT样本选定根因。算法、接口及core100MHz/UI200+200MHz保持当前合同身份。

本轮未执行额外EDA、CPU回归或源码修改；终态、停止边界及上述后续实验条件已通过真实消息通知主控与A006，不等待更多物理执行。
