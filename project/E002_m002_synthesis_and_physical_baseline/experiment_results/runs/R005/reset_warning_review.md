# A004：29 条 Synth 8-7137 复位优先级告警只读核查

日期：2026-10-15。角色：工程实验 `/root/m002_rtl_repair`。合同：[本轮 implementation 合同](../../../../../mission/M002_ddr_separation_and_timing_recovery/implementation_contract_2026-10-15.md)。

## 结论与适用范围

- execution：completed（源码核查 + AT002/AT004 INIT局部网表补证与轻量CPU逻辑核对）；未执行 EDA/仿真，未改任何 RTL/TB/build 输入。唯一写入为本报告。
- verdict：未发现源码中同一寄存器同时 set/reset 的优先级歧义或多过程驱动。29 条均关联“带异步 reset 的控制进程中，payload/tag 自身没有 reset 赋值，仅在 enable 分支更新”的结构，属于保守推断/编码结构告警候选，**不能仅凭源码未变而整体豁免**。
- 当前更新：AT004完整INIT补证中，该实例head/tail为INIT0的FDRE，head共享Q、tail→head选择和D/CE实际LUT均有证据；有界CPU逐位检查与源码一致。原“独立head初值01/10”风险在这个INIT实例上可限定关闭，未发现该head/tail reset优先级实现偏差；其余告警不整体豁免。第5节保留AT002时点，最新结果见第6节。
- applicability：E001 R003 AT004的29条原告警及冻结源，E002 R003 AT002真实INIT checkpoint与从其恢复的AT004局部INIT证据。AT002 POST失败记录保留；AT004 INIT POST完成并进入OPT，但本核查不是OPT/place/route或全复位验证签核。
- review：submitted to parent/A007。建议保持输入冻结完成当前 fresh synth，再做有范围的网表检查；不为消 warning 重写数值模块。

来源：[原告警 provenance](../../../../E001_m002_repair_quick_validation/experiment_results/runs/R003/attempts/AT004_final_complete_board_rtl_elaboration/reset_priority_warning_provenance.json)。已重新计算三份当前文件 SHA256，均与该 provenance 的 current/M001/old-source 身份相同。这里只核验来源连续性，不把 hash 相同当作安全证明。

| 源文件 | 告警记录数 | 当前 SHA256 |
| --- | ---: | --- |
| `project/hardware/rtl/attention/hap_activation_cache_8row.sv` | 4 | `834fa52acae54f7a1985dee2ace242bc221f86dab4c5b2860b482eeb131aa8cf` |
| `project/hardware/rtl/attention/hap_linear_tile_accum_dual_s42.sv` | 16 | `498837de12135c2f91a5d30aa2b4c5c4ade8705c9451ca9a98aa5795d3660d91` |
| `project/hardware/rtl/mlp/hap_mlp_silu_mul.sv` | 9 | `028d5cc6971322b6e77b00b0514793e4b3ee6ba36d62d85d53b4cd7571933c97` |

29 是消息记录数，不是寄存器位数或最终实际实例数。cache 的 4 条是两个参数化模块中的 bank/group 两类；guard 和 product 多位寄存器也各只记一条。

## 1. activation cache：4 条

源码：[声明及输出](../../../../hardware/rtl/attention/hap_activation_cache_8row.sv#L53)、[唯一控制进程](../../../../hardware/rtl/attention/hap_activation_cache_8row.sv#L217)。告警位置 117/119 是输出引用，246/247 是实际写入；不能只看报错行判断复位结构。

`rd_mem_bank_r`、`rd_mem_group_r` 无 declaration/initial/reset/clear 初值，仅在 `rd_req_fire` 时赋请求 tag。唯一时序块明确 `!rst_n > clear > normal`，没有两个同优先级赋值。

有效性路径如下：

1. `rd_req_fire = rd_req_valid && rd_req_ready`；ready 的113行同时要求 `rst_n && !clear && !error`。所以复位/clear 同周期不会接受新 tag，也不会触发独立 BRAM read。
2. 深度1：`rd_mem_valid_r` 在 reset/clear 清0；新请求写 tag 和固定 BRAM 数据输出的同一有效时钟建立 valid，115–125行只在 `rd_rsp_valid` 有效时应解释输出。无新请求时 payload/tag 可为旧值/X，但 valid 为0。
3. 深度2：reset/clear 同时清 `rd_mem_valid_r`、response count 和两个 pointer。`rd_mem_advance` 仅在旧 mem-valid 且队列有空间时移动数据和 tag；新建队列 valid 以 count 为准。刚清空后的首个有效条目只能来自新的 rd_req，tag 与数据走相同 advance/write-entry。
4. 分离的 response payload/tag 写进程未全部显式门控 clear；clear 边沿可能仍写旧 entry，但同边沿 count/valid/pointer 全部失效，旧 payload 不构成有效响应。不能要求所有无效 payload 在 clear 时不变化。

限制：`rd_rsp_valid` 没有直接组合门控同步 `clear`，其在 clear 生效的时钟边沿被清零；这是清空协议，配套消费者也必须遵守该边沿 flush。不能把 clear 边沿当作普通成功传输计入 scoreboard。异步 `rst_n` 则直接清有效性状态。

判断：源码控制优先级明确，未找到确定功能缺陷；保守结构告警候选。fresh netlist 仍需确认 read-tag 与 valid/BRAM 输出/queue entry 的同周期对齐，不能只检查 tag 原始值。

## 2. dual accumulator buffered input：16 条及一个必须保留的观察路径

源码：[wrapper ready/lockstep](../../../../hardware/rtl/attention/hap_linear_tile_accum_dual_s42.sv#L518)、[buffered input](../../../../hardware/rtl/attention/hap_linear_tile_accum_dual_s42.sv#L568)、[唯一 buffer 时序块](../../../../hardware/rtl/attention/hap_linear_tile_accum_dual_s42.sv#L600)。告警覆盖 lower/upper × head/tail × wave/first/last/guard，共16类。

16类 payload/tag 均无初始值或 reset 赋值。reset/clear 只把 `buffer_count_r` 清0；其他分支唯一且互斥。输入 `in_ready = rst_n && !clear && count!=2`；`buffer_drain = count!=0 && lower_ready && upper_ready`；bank valid 由 drain 驱动。bank 自身 ready 还门控 rst_n/clear（81行），故 clear/reset 下不能排空旧 head。

对有效数据路径，可从 count0 归纳：

| 合法旧 count / enqueue / drain | 新 count | payload 行为 |
| --- | ---: | --- |
| 0 / 1 / 0 | 1 | lower/upper head 全字段写新输入 |
| 1 / 1 / 0 | 2 | lower/upper tail 全字段写新输入 |
| 1 / 0 / 1 | 0 | head 值保留，但不再有效 |
| 2 / 0 / 1 | 1 | 只从此前已写入的 tail 提升 head |
| 1 / 1 / 1 | 1 | 当前 head 消费后，新输入替换 head |

count2 时 enqueue 被 in_ready 禁止；count0 时 drain 禁止。这样 first/last/guard 和 tail-wave 都不会作为有效 bank 输入在首次完整写入以前被消费。reset 后旧 payload 留存不等于旧 token 仍有效。

**但 ready lockstep 观察不是上述 valid 掩码的一部分：**

- `lower/upper_bank_in_wave = lower/upper_head_wave_r`（591–592行）。
- bank 的 `input_sequence_legal = in_wave == expected_input_wave_r`（71行），ready81行依赖它。
- wrapper 的 `lockstep_mismatch` 526–530行无条件比较 lower/upper ready；542–548行在 reset/clear 之外将 mismatch 锁存到 error，540行对外导出。这里没有 `count!=0` 门控。

在空队列、reset 已释放、两 bank 的 expected-wave=0、其他 ready 条件均真时，轻量 CPU 直接枚举四种 head-wave 值：

| lower head-wave | upper head-wave | lower/upper ready | bank valid | ready mismatch |
| ---: | ---: | --- | ---: | ---: |
| 0 | 0 | 1 / 1 | 0 | 0 |
| 0 | 1 | 1 / 0 | 0 | 1 |
| 1 | 0 | 0 / 1 | 0 | 1 |
| 1 | 1 | 0 / 0 | 0 | 0 |

这证明“count 清0”本身不充分。表的01/10是**独立任意初始值模型的条件反例**，不是观测到的 FPGA 运行失败。实际 FPGA INIT、综合合并可能排除这两种组合，必须取证。

所有 head/tail wave 的 lower/upper 赋值都成对使用相同 in_wave 或成对复制相应 tail；一旦已建立相等，可按全部分支保持相等。首个 enqueue 会建立 head 相等；tail 首次被提升前已成对写入。因此最小缺口集中在首 enqueue 前 INIT/等价性，以及综合后两份 CE/hold/reset 行为是否一致。无显式 payload 初始化；末尾 initial 只有参数合法性断言。

判断：14类告警可列为有 occupancy 论据的保守结构候选；两个 head-wave 告警保留“有潜在可观察控制影响、待新网表排除”的更严格状态。两类都没有 fresh netlist 签核，不能直接全体关闭。

## 3. SiLU × up：9 条

源码：[payload 声明与唯一时序块](../../../../hardware/rtl/mlp/hap_mlp_silu_mul.sv#L44)。9类是 input gate/up、s0 gate/up/zero/bypass/top-entry、s1 product、output product。没有这些寄存器的 initial/reset/clear 赋值；唯一 initial39行只加载 ROM 内容。

103–140行优先级是 `!rst_n > clear > pipe_advance`；reset/clear 显式清 input_valid、s0_valid、s1_valid、out_valid 与 sticky overflow。`pipe_advance = !out_valid || out_ready`，因此 clear 在 output stall（pipe_advance=0）时仍清全部 valid，优先级没有被 enable 反转。

payload 与有效性对应：

| payload 更新条件（均在 normal && pipe_advance 内） | 对应 token |
| --- | --- |
| `in_valid` → input gate/up | input_valid 下一拍建立 |
| `input_valid_r` → s0 gate/up/branch tags；ROM 同步读并共享 pipe_advance | s0_valid 下一拍建立 |
| `s0_valid` → s1 product | s1_valid 下一拍建立 |
| `s1_valid` → output product | out_valid 下一拍建立 |

stall 时上述所有 stage/ROM/valid 同步停住；clear/reset 后旧 product 可以留存，但四层 valid 都失效，新的有效输出须经过新的四级 token 更新，overflow 也只在 s1_valid 条件内检查。源码未找到数据被有效性掩码旁路导出错误状态的路径。不要把 reset 后 out_product 必须等于0列作要求；接口有效结果由 out_valid 解释。

`in_ready` 本身没有 rst_n/clear 门控；clear 是 flush，不把 clear 边沿的 `in_valid && in_ready` 当作保留事务。若未来验证上游必须保持该输入，则先核实既有 reset/clear 协议，不能通过改 golden 弥补。

判断：保守结构告警候选，未发现确定源级优先级错误；需确认正式网表保持 ROM/data/valid 相同 stall 节奏。既有 `hap_mlp_rebuild_silu_s32_tb` 覆盖首启和 output stall，但其 clear 固定0，不能充当 clear+stall 或 warm reset 验证。本轮未重跑该测试。

## 4. 最小后续核查，不扩展成完整数值任务

第一优先是 A006 完成 fresh synth 后只读获取29类实际存活实例的 primitive/INIT/CE/D/reset cone 与有效性控制连接。工具可能复制/合并/优化这些寄存器，需按层级和驱动追回，不能只搜一个旧实例名或把“找不到”当PASS。

1. **accum 的两个 head-wave 优先**：确认是否物理合并；未合并则确认所有副本 INIT 一致（记录真实 primitive/INIT，不推测 FPGA 默认值）、D 和 CE 等价，并确认 ready→lockstep cone。相同 INIT 加相同更新可封闭首笔输入前缺口。若 INIT 不同或无等价证据，告警仍开放；此时提出一次最小局部启动/clear后的 lockstep 事务检查，由父协调冻结边界，不能自动重写整组数值逻辑。
2. **cache**：仅深度1/2各一个局部实例，检查 rd-tag/valid/BRAM/queue-entry CE。若有疑点，最小 directed 场景为“建立pending响应→hold rsp_ready=0→clear同时提出不同bank/group请求→flush→重新写入并读取一个不同tag”，检查无旧有效响应、首个新有效tag/data配对。无需整模型。
3. **accum queue**：只 PHYSICAL_SPLIT=1、INPUT_BUFFER=1、LANES32；检查 count1/count2 clear、count1 enqueue+drain、count2 drain后首个新 token。用上下半部不同且非零的小 guard、不同 wave/first/last 区分 stale head/tail，不改S42 golden。观察 bank_in_valid 对应 token 与 lockstep_error。
4. **SiLU**：只一个叶子实例，用现成固定正/负/零向量；先填满并 out_ready=0，再 clear+in_valid 同边沿，释放后输入不同向量。检查 clear 胜过 stall、pipeline不泄漏旧valid、输出数量和原期望值一致；另一次有效数据在途时 hard reset。比较有效输出与overflow，不比较无效payload初值。若正式网表控制已明确等价，先记录连接证据，不机械扩跑全部数值回归。

这些是最小有区分力的建议，**本轮均未启动**。当前无需为消除warning修改任何源。若正式网表证明 CE/reset/valid 不等价，或观察到有效旧token/lockstep误报，才形成明确实现问题，报告受影响实例与上述局部回归范围，由父协调后单一负责人修复并生成新源身份；不得给当前综合网表贴上修改后的源码身份。

## 5. AT002 INIT 实际寄存器补证（2026-10-15 更新）

实际目录：[R003 AT002 report](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt)。A006在真实INIT阶段生成 `init.dcp`；本轮只读取文本探针，没有自行打开DCP或运行EDA。

### 子报告完整性与阶段失败边界

[reset_register_probe_init.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT002_project_init_opt_place_physopt/reset_register_probe_init.tsv) 实际492459 bytes、1500行、27/27个目标寄存器类，末尾有newline；最后一个s1_product FDRE block含Q/C/CE/D/R全部5个pin，未截断。SHA256为 `bcba4640edb748e24011900a091ea96bcacc70637ae6bde68bee73fda940a47b`。27类是29条原消息去除参数化重复后的类名数，不是27个FF。

实际 `vivado.log` 记录随后 `CDC probe target missing: ...core_gate/inst/u_ready0_cdc/arststages_ff_reg[0]/CLR`，INIT POST hook失败；`init_result.txt` 保持 `completed=0`、`diagnostic_eligible=0`。脚本在进入CDC探针前已关闭register report，因此该子报告可用，**不能把它扩称INIT POST/OPT/place完成**。预定 `head_wave_fanin_init.tsv` 和 `lockstep_error_r_reg_fanin_init.tsv` 未生成，标记NOT_RUN，不能等待/假定其存在。

### 目标实际层级与已观测状态

以下公共前缀记为P：

`scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/u_compute/g_projection_rtl.u_projection/u_array/u_center12/u_region2_cols8_11/g_dual_accumulator.u_accumulator`

这对应源码 `PHYSICAL_SPLIT=1 / INPUT_BUFFER=1 / LANES=32` 的 buffered branch。下列行号均为完整 `reset_register_probe_init.tsv` 的一基行号：

| 目标/字段 | 实际证据 | 原行 |
| --- | --- | ---: |
| `P/g_physical_split.g_buffered_input.lower_head_wave_r_reg` | 唯一匹配FF，`FDRE INIT=1'b0`，非blackbox | 115–116 |
| head C | P/clk，时钟 `clk_out1_scalellm_vcu118_f05_bd_clk_core_0` | 118 |
| head R | P/`<const0>`，没有对该payload施加active reset | 121 |
| head CE | net `P/g_physical_split.g_buffered_input.lower_head_wave_r` | 119 |
| head D | net `P/g_physical_split.g_buffered_input.upper_head_wave_r` | 120 |
| head Q | net `P/g_physical_split.g_buffered_input.lower_head_wave_r_reg_n_0` | 117、127–128 |
| 同一head Q驱动lower ready前级 | `P/g_physical_split.u_lower_bank/in_ready_INST_0_i_1/I4` 与 `in_ready_INST_0/I5` | 164–165 |
| 同一head Q驱动upper ready前级 | `P/g_physical_split.u_upper_bank/in_ready_INST_0_i_1/I4` 与 `in_ready_INST_0/I5` | 201–202 |
| `P/...lower_tail_wave_r_reg` | 唯一匹配FF，`FDRE INIT=1'b0`，同core clock、R=`<const0>` | 317–324 |
| tail Q | net `P/g_physical_split.g_buffered_input.upper_tail_wave_r` | 320 |
| tail CE | net `P/g_physical_split.g_buffered_input.lower_tail_wave_r` | 322 |
| tail D | P/in_wave | 323 |
| 原upper head/tail寄存器名字 | `ACTUAL_CELLS=0`；单独该结果不是合并证明 | 427、533 |

**已成立的限定判断：**本实际实例的上下ready前级接到同一个head Q物理net，且其driver是已定位的INIT0 FDRE；原先两份独立head寄存器处于01/10的条件反例，在这组实际连接中被排除。这里依据Q driver与两侧实际consumer pin的正向连接，不依据upper寄存器zero-match，也不依据“源码未变”。无需为该独立初值反例现在修改数值RTL。

**不能误读网名：**`lower_head_wave_r` 此处是CE组合网，`upper_head_wave_r` 是D-mux网，二者不是上下两份状态Q；探针还直接记录前者由 `lower_head_wave_r_i_1/O`、后者由 `lower_head_wave_r_i_2/O` 驱动（126、430行）。同样，tail Q保留upper_tail旧网名并不自动证明全部tail用途已被检查。必须按driver/pin追踪，不能把旧名当作逻辑状态身份。

### 仍未成立的判断与最小补证

目前只给出head/tail CE、D的**连线名**，没有其LUT `INIT` 和各输入；tail-Q是否正确进入head D选择、CE是否在reset/clear/合法occupancy下满足原更新行为，均尚未完成逻辑核对。上/下ready虽然共用head Q，其他bank控制输入和最终ready比较/lockstep error cone仍未提取；不能由此宣称两ready整体等价或29条告警全安全。其他数据类存在只取16个代表的限制，少量zero-match还可能为重命名、吸收、常量化等，未按全部类关闭。

已向A006提出下列有界补证，直接从真实INIT checkpoint按P精确查，不重读/重扫全设计：

1. 两个存活head/tail-wave FF的C/Q/D/CE/R/INIT及上述4个ready consumer的pin-net等同性。
2. head CE/D、tail CE三个直接driver LUT的REF_NAME、INIT和全部pin-net；必要时各限2级fanin、最多32个cell。取得tail-Q→head-Dmux输入和控制选择，不以D/CE网名代替逻辑。
3. P内 `lockstep_error_r_reg` 的D/CE限3级fanin、最多64个cell，并记录上下in_ready的实际LUT INIT和inputs。超过上限先报告数量/边界，不无界展开；找不到必须追实际driver/输出，而不是宣称已删除。

以上是AT002时点的补证计划，当时为NOT_RUN；其后AT004实际结果见第6节，不覆盖AT002失败。当前仍不改源、不启动额外仿真。若A006在不同OPT/physopt阶段改变复制/合并，应重新限定本共用Q证据的适用阶段。

## 6. AT004 完整INIT局部补证与实际LUT核对（2026-10-15 最新）

A006从AT002的 `init.dcp` 恢复，`command.json` 明确 `HAP_RECOVERY_CHECKPOINT` 和 `HAP_INIT_REPORT_DIR` 均指向AT002。AT004 `stage_inputs.sha256` 第15行绑定该检查点SHA256 `3a8e4ab2b407cc9796d24bc39ada8be48897da270e4757856262a34bfbd17d46`，可继承同一INIT对象的AT002 shared-Q fanout证据；并非把另一次综合当作相同设计。

证据目录：[R003 AT004 report](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt)。`restored_preflight.tsv` 已关闭，6个精确CDC target都唯一匹配；A006明确通知完整INIT POST已完成。`init_result.txt` 实际为 `completed=1 / diagnostic_eligible=1 / phase=init / physical_signoff=false`，仍保留 `clock_coverage=PENDING_TOOL_DEBUG_MATERIALIZATION`、`reset_io_review=OPEN`、`cdc_review=OPEN`。这些阶段和全局限制不因本局部核对而关闭。

### 6.1 文件完整性与有界范围

[head_wave_local_init.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/head_wave_local_init.tsv) 实际202836 bytes、519行、末尾newline，SHA256 `7828db57253b8a2e9610e1add0c0a4957f7d394e9835c6fecaf4eee4729f984c`。去重34个cell。head CE/D各3级cone为13/20个cell，tail CE/D为13/7个，lockstep CE/D为1/11个；全部小于64上限，无数量截断。上下ready各3个LUT亦完整提供。这里只判读这些局部证据，未打开DCP、未运行EDA或RTL/网表仿真。

公共层级P沿用第5节，以下是一基行号：

| 实际对象/证据 | 字段/连接 | 原行 |
| --- | --- | ---: |
| head存活FF | `lower_head_wave_r_reg`，FDRE，INIT0，R=`<const0>`，C=P/clk | 18–23 |
| head CE driver | `lower_head_wave_r_i_1`，LUT6，INIT=`64'h4444040000040000` | 2–9 |
| head D driver | `lower_head_wave_r_i_2`，LUT6，INIT=`64'hFFD0FFFF2F000000` | 10–17 |
| tail→head正向连线 | head D LUT的I5为 `...upper_tail_wave_r`；同net由唯一存活tail FF的Q驱动 | 17、122–127 |
| tail存活FF | `lower_tail_wave_r_reg`，FDRE，INIT0，D=P/in_wave，R=`<const0>`，同P/clk | 122–127、250–255 |
| tail CE driver | `lower_tail_wave_r_i_1`，LUT6，INIT=`64'h4044444000000000` | 242–249 |
| drain组合driver | `g_physical_split.u_lower_bank_i_1`，LUT4，INIT=`16'hE000` | 39–44 |
| enqueue组合driver | `buffer_count_r[1]_i_4`，LUT5，INIT=`32'h00A20000` | 73–79 |
| lockstep error FF | FDCE INIT0，CE=`<const1>`，CLR与count控制同网 | 392–397 |
| lockstep sticky D | LUT3 INIT=`8'h54` | 412–416 |
| ready/out valid/wave比较 | `lockstep_error_r_i_2`，LUT6 INIT=`64'h6FF6FFF6FFF66FF6` | 417–424 |
| lower ready三个LUT | 主LUT6 `0008000000000008`、slot LUT6 `808040FFFFFF40FF`、enable LUT2 `2` | 479–498 |
| upper ready三个LUT | 相同三种INIT，对应upper bank同名控制端口 | 500–519 |

head/tail类中实际对象数分别3/2（FF与LUT一起计数），不是3/2份独立状态。寄存器名字zero-match仍未用作合并证明；head共享状态依据AT002同一Q net对上下ready实际consumer pin的连接，以及AT004对同检查点的恢复与实际FF/LUT绑定。

### 6.2 可复现的轻量CPU逐位推导

将真实Xilinx LUT的 `INIT` 按 `index=I0+2*I1+4*I2+...` 取位，没有调用EDA或把工具warning当作期望值。下列变量C0/C1是合法occupancy C的低/高位，V为in_valid，RL/RU为两bank ready，W为新输入wave，T/H为旧tail/head wave：

```text
bit(INIT, inputs) = (INIT >> sum(inputs[i] << i)) & 1
E = bit(0x00A20000, [V,C1,C0,clear,rst_n])
D = bit(0xE000,     [C1,C0,RU,RL])
HC = bit(0x4444040000040000, [clear,rst_n,C0,C1,E,D])
HD = bit(0xFFD0FFFF2F000000, [C0,C1,D,W,E,T])
TC = bit(0x4044444000000000, [clear,rst_n,C1,D,C0,E])
next_H = HD if HC else H
next_T = W  if TC else T
```

与源码独立分支表比较，结果如下：

| 核对范围 | 输入组合数 | 结果/边界 |
| --- | ---: | --- |
| head/tail更新与原600–689行状态分支 | 768 | 全部相等；C∈{0,1,2}且count与其replica相等，遍历rst/clear/V/RL/RU/H/T/W |
| head CE在reset或clear时 | 48 | 不论其余4个输入，CE恒0 |
| tail CE在reset或clear时 | 48 | 不论其余4个输入，CE恒0 |
| lockstep sticky-D | 8 | 等于 `!clear && (mismatch || old_error)` |
| lockstep mismatch | 64 | 等于 `RL!=RU || VL!=VU || (VL && VU && WL!=WU)` |
| lower ready三级LUT组合 | 1024 | 等于源码reset/clear/error/finalize、wave合法性、slot/输出退休函数 |
| upper ready三级LUT组合 | 1024 | 同上，逐项使用upper实际LUT而非仅假定上下等价 |

reset/clear的CE恒0检查不依赖合法count或replica相等，故head/tail FDRE的R虽接0，payload仍按源码在reset/clear时保持，不发生reset与enable同拍抢占。D选择只在CE为1时比较，避免把无效D的don't-care当成实现差异。

在合法状态下，可将实际更新写成：空队列enqueue写head；count1 enqueue且不drain写tail；count1同时enqueue/drain替换head；count2 drain把实际tail Q提升head。没有发现数值规则、golden或接口语义偏移。

ready组合比较使用完整源码函数，包括 `out_valid` 对rst/clear的门控、输出slot是否为空及同wave输出退休；不是只比ready两个LUT的INIT字符串。lockstep比较仍然**没有新增occupancy门控**，与原源码一致；安全改善证据来自共享实际head状态，而不是假设工具删除了该观察路径。

### 6.3 当前可关闭事项与残余缺口

可以限定关闭：在所列INIT检查点的这个buffered accumulator实例上，“lower/upper head各自未初始化而不同，空队列误报ready lockstep”的具体假设被实际共享Q/INIT0排除；head/tail payload在reset/clear下的hold以及合法队列状态下D/CE更新，经实际LUT核对未发现实现优先级偏差。**目前没有为这项假设修改生产数值RTL的依据。**

仍保持开放/限定：

- 768组合更新比较使用 C与其replica一致的边界条件；局部图显示primary/replica均FDCE INIT0且同C/CE/CLR（61–72、88–99行），但各自完整next-state driver未全展开，不把该比较扩称顺序等价证明。
- lockstep异步CLR与count的实际共同net已记录，CLR的完整上游reset graph及其时序不在本局部D/CE比较内；reset IO/CDC由相应阶段审核负责，仍为OPEN。
- 上下ready各自实现匹配源码不等于任意bank内部状态都等价；真实数值overflow或其他bank控制差异仍可合法触发lockstep error。未验证这三份数值模块的全部事务、全部29类寄存器或全模型。
- AT002对其他类仅代表样本，无法将本head/tail结论推广到所有复制位、吸收于DSP/BRAM的寄存器或zero-match类。新的局部仿真仍NOT_RUN。
- 本证据为INIT阶段。后续OPT/phys_opt若改变寄存器复制/合并或控制图，应按新身份重新限定；不预先声称place/route已通过。

当前无需仅为该head/tail疑点再扩跑EDA/数值回归。若后续阶段出现不同INIT、CE/reset连接变化或实测有效token/lockstep异常，再对具体差异做已有最小局部验证，不把阶段诊断改成无界完整数值任务。

## 交付边界

本报告已通知父/root及A007；AT004所列head/tail primitive/INIT/D/CE、tail→head及ready/lockstep组合cone为 LOCAL_INSPECTED_AND_CPU_CHECKED；全部29类/完整顺序等价/全局reset-CDC签核仍未完成，局部新仿真为 NOT_RUN。源身份与E001一致只允许复用未受影响的证据，不能将E001路由/reader测试扩称为这三份数值模块的reset-priority验证。正式物理实验可依合同在告警开放且风险明确的诊断状态下推进；最终时序/功能签核另行审核。


## 7. AT005 OPT 的 CDC Critical 精确增量与最小 reset 核查

本节为2026-10-15附加审核；不改上文的INIT局部结论。execution：本轮只读文本与轻量CPU解析已完成；未运行EDA/仿真，未改RTL、TB或构建输入。verdict：**两条CDC-11与两条source变化的CDC-10已定位到有限reset边界，安全资格仍OPEN**；尚无证据要求立即改生产RTL。applicability：AT004完成的INIT报告与AT005完成的OPT报告/局部探针；review：提交父/root和A007，诊断准入由其独立评判。

### 7.1 证据身份与真实终态

本节使用以下已闭合文件，不把AT005中不存在的reset graph或primitive override当作已取证：

- [AT005 OPT CDC](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/cdc_opt.rpt)：3,941,307 bytes，SHA256 `7451c566ed781bcc67e2bbc5484378980045df170acb9b2ad884a7d20b94ff67`；报告行3–10为Vivado2025.2、xcvu9p-flga2104、Optimized状态，日期2026-10-15 13:53:48。
- [AT005 OPT reset局部探针](../../../../hardware/vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/reset_cdc_and_io_probe_opt.tsv)：63,797 bytes、355行，SHA256 `484fc23cb047cb32048f36fdf3e6edb4a5e137f0608be5dcd810ddccc337b0c7`。
- [AT004 INIT CDC](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/cdc_init.rpt)及[INIT reset局部探针](../../../../hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/reset_cdc_and_io_probe_init.tsv)；后者SHA256 `5eaf12ea6aeabe61f5fe19738ab273fe838765c91c5b14a9e6ef99ca4de14aa2`。它们只作INIT对照，不能替代OPT结构。
- AT005 `opt.dcp`为397,273,730 bytes、SHA256 `b209decf321e4a756f3ded455e0ce162b3404467ec235b5312469f9a89171021`。`opt_command_result.txt`记录opt_design的native Tcl code0；`opt_result.txt`仍为completed0、diagnostic_eligible0；`launcher_status.txt`为native/managed exit1。A006已确认无本次存活子进程，终止点为未获资格的CDC gate；没有进入place的成功证据。

因此，“OPT命令成功”“报告已完成”“OPT诊断资格”“place/route成功”保持分开。

### 7.2 精确集合差异：新增四条Critical tuple，不能只看数量

以`(rule, source, destination)`解析实际Critical数据行：INIT有6条，OPT有8条；精确保留4条、移除2条、新增4条。CDC-10总数仍6，另有CDC-11两条。以下P均为实际层级`scalellm_vcu118_f05_bd_i`，省略仅为可读性；报告source列的`/C`是launch FF时钟pin，不是把该pin视作复位信号本身，实际驱动仍需从其Q及组合连接核查。

| OPT行 | rule / destination | INIT→OPT source或分类 | 时钟与Depth |
| --- | --- | --- | --- |
| 181 | CDC-10；`P/core_gate/inst/u_ready0_cdc/arststages_ff_reg[0]/CLR` | `P/ddr4_0/inst/div_clk_rst_r1_reg/C` → `P/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_top/calDone_gated_reg/C`；INIT行180 | UI0 `mmcm_clkout0` → core100；4 |
| 853 | CDC-10；`P/core_gate/inst/u_ready1_cdc/arststages_ff_reg[0]/CLR` | DDR1对应`div_clk_rst_r1_reg/C` → DDR1对应`calDone_gated_reg/C`；INIT行852 | UI1 `mmcm_clkout0_1` → core100；4 |
| 2483 | CDC-11；`P/d0_gate/inst/u_base_reset_cdc/arststages_ff_reg[0]/CLR` | 同一`P/xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/C`；INIT同端点行2514为CDC-9 Info | `xdma_0_axi_aclk` → UI0；4 |
| 4320 | CDC-11；`P/d1_gate/inst/u_base_reset_cdc/arststages_ff_reg[0]/CLR` | 同一XDMA source；INIT同端点行4562为CDC-9 Info | XDMA → UI1；4 |

四条均有Asynch Clock Groups例外。其余精确保留的四条CDC-10是d0/d1 gate末级ready FF到本SMC的psr0/psr_aclk1 AUX同步入口；“集合保留”只表示身份没有变化，不代表它们已获全局安全豁免。

### 7.3 两条CDC-10：两种launch早已共存，极性折叠解释仍需实际alias确认

[板级构建源](../../../../hardware/vivado/scripts/create_vcu118_board.tcl)173–185、424–440行的规定是`ready = calib_complete && !ui_clk_sync_rst`，两份ready分别进入core_gate的四级active-low XPM reset链；[core gate源](../../../../hardware/rtl/board/hap_v5_dual_async_ready_gate_xpm.sv)27–41行在core域同步release后与base reset相与。

实际局部探针给出以下有限证据：

- INIT的ready0/1 CLR上游各为6个cell（探针32–60、204–232行），**每个锥中已经同时包含**本DDR的`div_clk_rst_r1_reg`和`calDone_gated_reg`。OPT相同CLR上游各为4个cell（29–51、192–214行），仍同时包含这两种FF。因此report_cdc选择的source变化，本身不能证明calDone是OPT新引入的功能依赖。
- INIT有`ddr*_and` LUT2 INIT=`4'h8`、`ddr*_not` LUT1 INIT=`2'h1`、XPM `reset_pol` LUT1 INIT=`2'h1`。OPT仅余`ddr*_and` LUT2 INIT=`4'h2`；后两种INV在该锥内消失。LUT8函数是`I0 && I1`，LUT2函数是`I0 && !I1`；这与吸收UI-reset反相、再将XPM reset_pol反相折叠进CLR极性的优化解释一致。
- OPT ready0四级FF见5–28行，ready1见168–191行：均FDCE、INIT1、ASYNC_REG1、CE常1、首级D常1，后级D接前级Q，C均关联core时钟；四级的`IS_CLR_INVERTED=1'b1`均显式给出。`div_clk_rst_r1_reg`与`calDone_gated_reg`在每个阶段仍关联本DDR UI时钟。

这些是4-level有界all_fanin采样，不是整个MIG内部reset/calibration证明。现TSV对上下游记录使用不同的层级net alias，尚未把LUT各输入与两源Q、LUT输出与XPM src_arst/CLR的实际同网关系显式展开；INIT某些极性属性还为空，空值不能读作0。**故“优化折叠合理”目前是有证据的候选解释，不是已证明的reset等价或CDC-10豁免。**最小补证是确认I0/I1具体映射、两级反相的有效合成极性，以及四级release末端到core_gate AND的实际连接；无需扩为全量warning重扫。

### 7.4 两条CDC-11：同一UI域有并行同步副本，关键在消费者与复位顺序

两条CDC-11均对应现有d0/d1 gate的base链。[单DDR gate源](../../../../hardware/rtl/board/hap_v5_reset_gate_xpm.sv)15–38行规定base与ready各自四级、async assertion/synchronous release，输出为两份同步结果AND；d0/d1分别在自己的UI时钟工作。**一个reset分别进入两个不同UI时钟域，不构成这两条规则的充分解释；要查的是同一launch在同一目的UI域内的多份同步。**AMD UG906 2025.2的[Asynchronous Reset Synchronizer](https://docs.amd.com/r/2025.2-English/ug906-vivado-design-analysis/Asynchronous-Reset-Synchronizer)规则解释由A007负责；不得把FIFO Generator/AXI FIFO的busy条件例外自动套用到自定义gate与HostSplit。

实际OPT CDC紧邻行已经给出同UI域的并行路径：

| 目的UI | 同一user_reset launch的其他同步入口 | OPT / INIT行 | report Depth |
| --- | --- | --- | ---: |
| UI0 | `P/host_split/inst/clk_map/psr_aclk1/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D` | 2484 / 2515 | 5 |
| UI1 | HostSplit对应`psr0/.../syncstages_ff_reg[0]/D` | 4321 / 4563 | 5 |
| UI1 | HostSplit对应`psr_aclk2/.../syncstages_ff_reg[0]/D` | 4322 / 4564 | 5 |

这些HostSplit路径仍为CDC-3 Info，但不能据此推断与gate副本共同使用时安全。Depth5/4不等于已证明相差一个周期释放；还取决于实际链、有效极性、复位条件和输出处理。即使同深度，独立同步副本也可能在不同目的时钟周期release。

板级源343、442–451、544–558行给出需要检查的真实边界：XDMA `xrstn`同时直接给HostSplit aresetn，并进入d0/d1 gate base；HostSplit各本地UI复位处理与gate独立。gate输出给core的相应DDR域、d0/d1 SMC和MIG slice；HostSplit的M00/M01 AXI又进入对应SMC（530–536行），存在跨这些reset边界的实际事务连接。MIG AXI aresetn另由rst_ddr0/1产生（458–461行）。这确立了需检查的消费者/握手边界，**尚未证明某个组合重汇合、错误事务或必需重设计**。

当前OPT局部probe仅采到每条base链的stage3（d0为102–107、158–163行，d1为265–270、321–326行）：FDCE INIT1、ASYNC_REG1、CE常1、D为stage2、C为本UI；显式`IS_CLR_INVERTED=1'b0`。它不覆盖base四级全链，也未解析launch Q/CLR的实际alias与有效极性，不能将其与源参数RST_ACTIVE_HIGH0直接作字符串比较而判错误。七条gate链加四条d0/d1 SMC AUX链的数量检查也**不覆盖以上三条HostSplit AUX链**。

### 7.5 最小未完成证据与阶段判断

A006已确认AT005终态没有执行reset_graph/primitive override导出；下一独立AT将从合法同OPT父链补缺失结构，保持原报告和失败终态。要求仅限：

1. 实际`user_reset_reg/Q`驱动net、有效极性和有界fanout，按UI0/UI1分组；完整d0/d1 base四级FF、明确primitive override和最终消费者。
2. 上表三条HostSplit AUX release链的实际输出、目的时钟和消费者；沿本UI reset/AXI边界检查与gate副本是否重汇合，以及是否存在经实际证明的busy/隔离/握手条件。没有busy证据就不写FIFO例外。
3. 第7.3节两条core ready源锥的pin-to-net alias、显式极性及release输出；保留源合同的`calib && !ui_reset`语义，不仅匹配critical数量。

当前判断是`STRUCTURE_LOCALIZED / QUALIFICATION_OPEN`：异常已收敛到现有reset多副本和ready组合输入边界，没有成立的直接数据CDC缺陷或必须改RTL的结论；也没有足以关闭Critical的重汇合/生命周期证明。是否允许标记风险的物理诊断继续，与最终reset/CDC安全签核分别由父主控/A007判定；本报告不新增批准、放行或豁免。原29条reset-priority、数值正确性、完整顺序等价及place/route结论均不因本节而扩大。


### 7.6 HostSplit三条AUX末级Q的精确消费者预期（源码分类，非OPT实测）

按A007后续问题，将第7.5节的诊断结构边界缩到可机械检查的对象。当前生成的HostSplit三个wrapper（`psr0`、`psr_aclk1`、`psr_aclk2`）各自synth VHD的142–145行均明确`C_AUX_RST_WIDTH=1`、`C_AUX_RESET_HIGH='0'`。其[vendor proc_sys_reset VHD](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ipshared/9438/hdl/proc_sys_reset_v5_0_vh_rfs.vhd) SHA256为`df892cc9994a5a02f7089876a26e2129d449d8221c4e6cbf45f46e28e4a32696`：

- 1010–1026行的ACT_LO_AUX为四级xpm_cdc_single，`dest_out=asr_lpf(0)`，目的clk为Slowest_Sync_Clk；它不是异步clear reset primitive。
- width1使1067–1077行AUX_LPF追加移位循环为空；1081–1093行变成`asr_and=asr_lpf(0)`、`asr_nand=!asr_lpf(0)`，926–934行ASR_OUTPUT_PROCESS因此化简为同clk下`lpf_asr <= asr_lpf(0)`。
- 后续`lpf_asr`进入LPF的`lpf_int`，再到本PSR的SEQ复位排序；这些是后续顺序级，不应混入stage3 Q的直接/首个顺序消费者集合。

因此，对每条`P/host_split/inst/clk_map/<psr>/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[3]/Q`，实际OPT应针对以下精确首个顺序endpoint取证，不能以“某个vendor内部对象”泛化放行：

| psr | 预期首个顺序endpoint / REF_NAME | 目的clk |
| --- | --- | --- |
| psr_aclk1 | `P/host_split/inst/clk_map/psr_aclk1/U0/EXT_LPF/lpf_asr_reg/D` / FDRE | UI0 `mmcm_clkout0` |
| psr0 | `P/host_split/inst/clk_map/psr0/U0/EXT_LPF/lpf_asr_reg/D` / FDRE | UI1 `mmcm_clkout0_1` |
| psr_aclk2 | `P/host_split/inst/clk_map/psr_aclk2/U0/EXT_LPF/lpf_asr_reg/D` / FDRE | UI1 `mmcm_clkout0_1` |

[HostSplit生成BD](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ip/scalellm_vcu118_f05_bd_host_split_0/bd_0/synth/bd_8cce.v)1397–1431行明确M00_ACLK=aclk1、M01_ACLK=aclk2，三个PSR的slowest_sync_clk与上表对应；psr0的interconnect reset再作为其他PSR的ext_reset_in，不能把这些不同顺序位置的副本视为同一release事件。

[HostSplit生成sim_netlist](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ip/scalellm_vcu118_f05_bd_host_split_0/scalellm_vcu118_f05_bd_host_split_0_sim_netlist.v) SHA256为`2f377a097876398cbd514bdd72908d0b19ddd24e8f9eb9969f546b590e3da11b`，提供与源码推导一致的生成结构：psr_aclk1的lpf_asr_reg在7356–7363行、psr0在7626–7633行、psr_aclk2在7217–7224行，均为INIT0的FDRE，D=asr_lpf_0、CE1、R0、C为对应aclk；各XPM module的dest_out明确为stage3 Q。**生成sim_netlist不是当前OPT checkpoint导出，也未在本轮运行仿真**；以上仅建立结构预期和精确查询范围。

A006机械核对可要求：actual stage3 Q的完整首个顺序endpoint集合恰为上表对应单个D，REF_NAME/clock/有效极性一致，没有额外数据、FIFO、控制reset pin或其他时钟endpoint。若OPT复制/合并或名称变化，保留差异并由审核者按实际图重新分类，不自动扩大scope。此核对用于把当前Critical定位为已知reset内部多副本边界，**不把完成事务级release安全证明增设为诊断实验的门槛**；最终重汇合、生命周期及CDC安全资格继续OPEN，由父主控/A007按已授权诊断语义独立判定。


### 7.7 AUX初值与launch极性的生成证据补充

回应A006的限定问题：ACT_LO_AUX的vendor实例明确`INIT_SYNC_FF=0`；不能套用gate xpm_cdc_async_rst的INIT_SYNC_FF1/INIT1要求，也不能只从generic0推成源合同强制清0。上列生成sim_netlist的AUX XPM四级FDRE均没有显式`.INIT`，该生成primitive的有效缺省INIT为0；actual OPT应记录显式INIT/primitive override，若与此生成结构不同则报告差异，不能据此推出系统powerup/reset安全。

当前[XDMA生成sim_netlist](../../../../hardware/vivado/project/m002_E002_R001_AT001_fresh/scalellm_vcu118_f05.gen/sources_1/bd/scalellm_vcu118_f05_bd/ip/scalellm_vcu118_f05_bd_xdma_0_0/scalellm_vcu118_f05_bd_xdma_0_0_sim_netlist.v)25413–25417行是LUT1 INIT=`2'h1`，输入user_reset、输出axi_aresetn的driver；160651–160656行的PCIe user_reset_reg为FDPE、Q=user_reset。结合HostSplit AUX源1013行的`not Auxiliary_System_Reset`，预期stage0 D与launch user_reset/Q**同相**（两处反相抵消），不是其反相。此处仍是生成结构的预期，actual OPT的跨层alias与有效引脚极性须由A006目标探针核实。

父主控已采纳“已定位reset结构可供诊断判断、最终安全资格OPEN”的分层。本只读任务到此结束；后续仅在新AT实际pin/全链/consumer证据完成并由父派发后，复用本agent做有界差异核查，不继续扫描或增设验证门槛。


## 8. AT006 两条core ready链的INIT/极性语义补核

本节为父主控追加的只读问题：实际导出INIT1/CLR_INV1是否与原INIT0预期矛盾。只写本报告，不修改RTL/构建，不执行EDA或仿真。初步结论：**两条active-low xpm_cdc_async_rst的正确源初值就是1；排除此前讨论中的INIT1疑虑，AT006未出现已证实的初值改变。原自动检查对七条async链一直正确要求INIT1。**实际pin/输出alias待闭合图后补在本节，当前不使用未闭合图作全图结论。

### 8.1 已关闭导出与历史初值连续性

A006明确确认AT006 point=OPT的14个小block exports全部已关闭。两个core ready导出为：

| scope | export | bytes / SHA256 |
| --- | --- | --- |
| core_gate/u_ready0_cdc | [opt_1.v](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_primitive_overrides_opt_1.v) | 23,820 / `bd0072526adbb6a49c84c4b2ee76fff1258d7546b52aa736277f34f30f754363` |
| core_gate/u_ready1_cdc | [opt_2.v](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_primitive_overrides_opt_2.v) | 23,814 / `427407270dce9dda209e9c1034a77c337e59cbb5106f74ad332b239aa800ccbf` |

两文件17–20行均保存DEF_VAL1、INV_DEF_VAL0、DEST_SYNC_FF4、INIT_SYNC_FF1、RST_ACTIVE_HIGH0与ASYNC_RST属性。37行为`dest_arst = arststages_ff[3]`；42–89行四个primitive均FDCE、显式INIT1、显式IS_CLR_INVERTED1、CE1，stage0 D=1，stage1–3 D=前级Q。没有输出反相或Q状态取补。

独立解析AT004 INIT、AT005 OPT与AT006继承OPT的三个已闭合reset_cdc_and_io_probe文件，每份两条ready链均为8个唯一FF，INIT全部1。故这不是AT006从INIT0改变为INIT1；排除的是此前讨论中的INIT1疑虑。A006已确认原自动检查对七条async链一直正确要求INIT1，未存在“代码要求这两链INIT0”的缺陷。本次机械检查修复针对缺省参数解析、有效极性与别名归一化。AUX的xpm_cdc_single/INIT0是另一类结构，不能与本active-low async reset链混用；四条原SMC AUX缺少完整断言的问题由A007/A006单独核对，不因本节async证明而关闭。

### 8.2 同版本XPM源直接规定INIT1与有效active-low语义

本轮读取实际Vivado2025.2安装下的[XPM CDC源](/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/ip/xpm/xpm_cdc/hdl/xpm_cdc.sv)，绝对路径为`/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/ip/xpm/xpm_cdc/hdl/xpm_cdc.sv`，SHA256 `27592359d8363d7e6575298f9d0faa7c9f9258ea77f19c9a38946fbaf3783f09`。权威语义来自xpm_cdc_async_rst本身：

- 1223–1227行：RST_ACTIVE_HIGH0令DEF_VAL1、INV_DEF_VAL0；`arststages_ff`声明初始化为四份DEF_VAL。INIT_SYNC_FF不能被误读成“寄存器值必须为该参数数值”；此处实际INIT1直接来自active-low模式的DEF_VAL。
- 1243–1246行：`dest_arst=lastQ`、async_path_bit=1、reset_pol为src_arst取反。
- 1251–1256行与宏81–88行：reset_pol断言时异步把四级清0，未断言时每个目的时钟上升沿移入1。仿真INIT分支另在GSR时强制DEF_VAL，126–143行没有改变上述有效极性。

因此源合同是：src_arst低→dest_arst异步低；src_arst高→经过四级目的clk移入1后dest_arst高；初始存储向量1111，与导出INIT1和lastQ直出完全一致。INIT1代表该active-low输出的deasserted初始值，不能被扩称系统已完成校准或全局powerup/reset安全证明。

### 8.3 闭合exports的局部有效逻辑核对

A007已核同安装的FDCE模型：省略C/D inversion参数的声明缺省均0，GSR加载INIT，CLR_eff=CLR xor IS_CLR_INVERTED，CLR_eff为1时Q清0。write_all_overrides未打印缺省参数不等于未知值；本节采用A007已核的实际模型缺省，不把任意空cell属性当作0。

令r为该scope输入src_arst，q=[q0,q1,q2,q3]为旧状态。源与导出primitive在二态逻辑下均为：`r=0 -> next_q=0000`；`r=1 -> next_q=[1,q0,q1,q2]`，输出为q3；初始化均1111。轻量CPU逐位比较遍历16种旧状态×2种r，共32组next-state全部一致，初始向量也一致。该核对没有运行RTL/网表仿真，不覆盖模拟亚稳态、脉宽、GSR恢复或全系统复位时序。

OPT标记RETARGET与此前reset_pol反相消失、CLR反相属性出现相符；这属于实现形式变化，不需要强求原INV/LUT/INIT字符串逐项相同。就两条ready reset原语内部而言，当前未见INIT、Q/D或dest_arst语义矛盾；外部`calib && !ui_reset`及lastQ到最终AND的actual alias在图闭合后另核，仍保留本报告的诊断/最终安全分层。


### 8.4 闭合actual OPT图：ready输入、四级连接与最终AND均匹配

A006随后确认AT006已failed1终态且无本次存活子进程；fresh [reset_graph_opt.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/reset_graph_opt.tsv)确定已close，119,909,158 bytes、259,337行，SHA256 `972611c2c4f5f9c21da17866c6546e73040f2930274ec315aad7cd62a9e17887`。本节只对所列对象做文本判读，不把AT006门检查失败改写为成功。

以下P同第7节。actual PIN记录同时保存跨层net segments与leaf driver，现可填补第7.3节的层级alias缺口：

| 图行 | 实际连接 | 解释 |
| --- | --- | --- |
| 152081–152084 | ddr0_and LUT2 INIT2；I0的leaf driver=`P/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_top/calDone_gated_reg/Q`，aliases含c0_init_calib_complete；I1的leaf driver=`P/ddr4_0/inst/div_clk_rst_r1_reg/Q`，aliases含c0_ddr4_ui_clk_sync_rst | 函数确为calib && !ui_reset |
| 152085–152088 | DDR1对应LUT及两种Q，精确同构 | 同上，非仅名称相同 |
| 17196、20649、24102、27555 | ready0四级CLR的leaf driver均为ddr0_and/O，aliases同时含core_gate/async_ready0与u_ready0_cdc/src_arst | 四级接同一有效ready，CLR_INV1使ready低时清0 |
| 31010、34463、37916、41369 | ready1四级对应ddr1_and/O | 同上 |
| 13921、17374、20827、24280；27735、31188、34641、38094 | 两链各四个FDCE，INIT1/CLR_INV1；D0实际driver为各自VCC/P，其余D为前级Q；八个C均关联core100时钟 | 与exports及XPM源码逐级一致 |
| 27288、41102 | ready0/1末级Q的aliases分别含ready0_sync、ready1_sync | dest_arst仍为有效active-low release结果，无输出取反 |
| 95–104 | core_gate的aresetn__0与aresetn__0_lopt_replica均LUT3 INIT80；两者I0均接base末级Q，I1/I2分别直接接ready0/1末级Q | 两份实际函数均为base_sync && ready0_sync && ready1_sync；primary O aliases含core_gate/inst/aresetn |

轻量CPU按实际INIT逐位检查每个DDR ready LUT的全部4种输入、每份最终AND的全部8种输入，均等于上述源函数。结合第8.3节的每链32种状态更新核对，**两条ready链的初值、有效断言/release、Q/D连接与最终dest_arst/AND语义没有发现矛盾**。这限定排除了本次“INIT1异常或OPT改变ready含义”的疑点；不会据此关闭CDC-10、亚稳态、脉宽或全系统复位生命周期风险。

report_cdc/图GATE_INPUT上游对象为FF/C时，必须先识别其所属launch FF，再从该FF实际Q和pin图重建驱动；不能把C对象直接与Q端口字符串比较后判数据来源改变。实际I0/I1 leaf driver已给出此归一化依据。

### 8.5 同一有界复核中的d0/d1 base断言极性：按实际user_reset/Q判断

A006报告两条base链的机械门仍卡在“层级base_aresetn/src_arst应低断言”的字面预期。本节不扩为新架构问题，仅解释已取证的同一reset极性：exports3/5的四级FDCE均INIT1、**显式CLR_INV0**、D0=1/后级D=前Q、dest_arst=lastQ；actual graph44828/100095行的首级CLR leaf driver均为XDMA user_reset_reg/Q，259333行该Q记录包含57个跨层net aliases。stage3 Q在54920/110187行，直进本gate LUT2 AND的I0（41549/96816行）。

令u为实际active-high user_reset/Q。原生成设计为xrstn=!u，源active-low XPM的clear=!xrstn=u；OPT实际为CLR=u且CLR_INV0，仍是u高时异步清Q0，u低时四级移入1、输出lastQ高。二态32组旧状态×u的next-state比较与原有效源关系完全一致，初始向量亦仍1111。**可以且应以launch Q的有效极性、实际primitive CLR/D及最终Q语义核对；不能要求已被跨层逻辑折叠的base_aresetn/src_arst内部标签继续保持原端口真值。**HostSplit首D同userQ也符合原not aresetn的两处反相抵消结果，详见第7.7节的生成基线。

本解释不以层级名或ASYNC_REG属性代替连线证据，也不声称多份独立release同时发生。对于未知driver、不同primitive极性或未解释的新消费者，仍需报告差异；此次实际pin/exports没有支持“这两base因CLR_INV0而断言反向”的结论。

### 8.6 本次交付边界

execution：只读源码/闭合export/actual图与轻量CPU逻辑核查completed；仅追加本报告，未执行EDA/仿真、未改RTL/构建。verdict：本次两ready INIT/极性疑点及附带base字面极性疑点已按所列OPT证据限定排除；原自动检查对七条async的INIT1预期正确，本次修复针对缺省参数解析、有效极性和别名归一化，未发现需要改生产RTL的矛盾。四条原SMC AUX的断言覆盖与本局部async证明分别记录。applicability：AT006恢复的同OPT父链、所列闭合文件与Vivado2025.2 XPM/primitive语义；不预判后续物理优化后的图。

已通知A006、A007和父主控。当前CDC最终安全资格、同域多release/重汇合与完整powerup/复位生命周期仍OPEN；它们不自动成为已定位诊断实验的新验证门槛。AT006原失败门和终态保持，由A006修正有证据支持的预期/归一化，再由父主控/A007独立审核后继诊断入口。


### 8.7 base末级Q进入core FIFO/RAM控制的源码预期边界

按父主控新增问题，仅补源码边界，不重复A007负责的完整消费者集合审核。板级gate输出本就作为core的相应DDR reset；[resource_top](../../../../hardware/rtl/integration/hap_attention_mlp_resource_top.sv)120/127行把物理DDR0 clock/reset接Attention两条逻辑权重流，172/179行把物理DDR1 clock/reset接MLP两条逻辑权重流。各frontend将相应reset接u_half0/1的ddr_rst_n：[Attention frontend](../../../../hardware/rtl/attention/hap_dual_ddr_weight_frontend.sv)290–313行、[MLP frontend](../../../../hardware/rtl/mlp/hap_mlp_w4_dual_ddr_frontend.sv)467–492行。

- [Attention半组FIFO](../../../../hardware/rtl/attention/hap_ddr512_halfgroup_async.sv)50、56–57行：beat_fire=beat_valid && beat_ready，beat_ready显式要求ddr_rst_n；96–103行在beat_fire且末beat时写fifo_mem，106行起的DDR状态另有异步reset。
- [MLP W4半组FIFO](../../../../hardware/rtl/mlp/hap_ddr512_w4_halfgroup_async.sv)52、56–57行、86–99行具相同reset门控写事务结构。

因此base末Q经gate AND进入同一DDR侧FIFO写允许、RAM write enable或payload寄存器CE，是源码已有的reset控制用途。不能把合法消费者机械限制为CLR/R/reset pin，也不能仅因对象位于core层级就视为core时钟域数据CDC。这里说的是控制用途，不是允许任意FIFO/RAM的D/DI/地址pin；超出已定位控制边界的实际对象仍需A007/工程按pin语义判读。

闭合[cdc_changed_reset_opt.tsv](../../../../hardware/vivado/reports/m002_E002_R003_AT006_cdc_reset_proof_debug_place_physopt/cdc_changed_reset_opt.tsv)（5,962,741 bytes，SHA256 `c34f89304691c486f5bd8cc489e7ec68bd96e005426009e9edc2e20470ca0346`）的有界四个实例与该预期相符：15920/18253行是Attention u_half1/u_half0的fifo_mem_reg_9/WEBWE[7]；19989/22086行是MLP相应两个half的同类RAMB36E2写使能pin。这里引用该具体控制pin，不作全部6,362/5,282个base fanout端点的重新审核或安全豁免。

这些RAM记录的CLOCKS同时列core与本DDR UI，是从该RAM primitive全部clock pin取得的关联集合；不能把集合中存在core clock直接当作WEBWE受core clock采样的证据。准确的RAM写端口/clock pin归属由A007及A006机械门按实际primitive连接处理。本小节不证明异步FIFO在独立复位、warm PCIe reset或任意中断事务下的生命周期安全；维持已授权诊断边界，不扩大数值回归或EDA范围。
