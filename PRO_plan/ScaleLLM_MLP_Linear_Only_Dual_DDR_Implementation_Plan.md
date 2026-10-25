# ScaleLLM MLP 线性投影专用化：实现计划

日期：2026-10-24。状态：**规划完成；生产实现、回归、EDA、上板均未执行。**

本计划将[设计规范 v1.0](ScaleLLM_MLP_Linear_Only_Dual_DDR_Design.md)转为文件级工作、接口冻结项和阶段验收。原设计全文 1303 行已分段读取，SHA-256 为 `c3e80544bdebfba336e53ff74c112751afdac96f63cec5e15cecb858b574e6d9`，保持原文不动。下文的“建议”是在开工 W0 中需要落实的技术细化，不表示新接口已经实现。

## 1. 本轮边界与实现目标

唯一活动工程根为 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`。以下文件映射均相对此根，硬件入口仍为 `project/hardware`，不建立另一份生产源码树。当前 HEAD 是设计指定的 `0c0d2cdba00ef8e91cc96e678ca4e0b68c4cda60`；本轮只新增本计划。

已读取适用的根/工程 `AGENTS.md`、research-agent 的工作流及 hardware-agent 的规格证据要求。工程副本中的旧 M003 任务状态、A006/A007 身份、旧绝对路径和历史启动授权仅作为历史资料；本轮不恢复这些任务、代理或 EDA 进程。

| 项目 | 本次目标与状态 | 依据 |
| --- | --- | --- |
| 分工 | 明确要求：Host 完成 MLP 两处 H32、动态 A8/ScaleCode 编码及 SwiGLU；FPGA 执行 GU、DOWN 两类独立线性任务 | 设计 §1–6 |
| 数值 | 明确要求：format05、原权重、S44/S54 累加及舍入/饱和语义保持 | 设计 §6 |
| 平台 | 设计目标：VCU118 `xcvu9p-flga2104-2L-e`；Vivado 2025.2；core 100 MHz、两 DDR UI 200 MHz | 设计首页；构建脚本静态配置 |
| Attention | 明确要求：算法、RTL、参数、编译选择、CSR、DDR0 布局及 CDC 行为保持；集成后重新回归 | 设计 §4、§17.3 |
| MLP 存储 | 明确要求：物理 DDR1，6×8 MiB tensor 槽；单命令 max448-group A8 工作 cache；单层权重 epoch | 设计 §8、§11.2、§13 |
| 完成标准 | 两类任务、整层/模型数值、生命周期、资源、合法布线与板级结果分别验收 | 设计 §17–18 |
| 本轮事实 | 完成静态阅读和公式复核；没有本轮测试 PASS、网表、bitstream、板级吞吐或路由成功结果 | 本次工具操作范围 |

## 2. 当前代码到目标实现的映射

表中 `H/` 表示 `project/hardware/`。推荐保留历史 full-command 源文件用于旧基线测试，新生产层次使用明确命名的 linear 模块；确切新文件名在 W0 固定，不能靠旧 ABI 模块重命名掩盖接口变化。

| 责任域 | 当前代码与已核位置 | 实现工作与复用边界 |
| --- | --- | --- |
| 生产 MLP 顶层 | `H/rtl/integration/hap_attention_mlp_resource_top.sv:153`；`H/rtl/mlp/hap_mlp_full_command16_v5_s54.sv:14` | 现例化名 `hap_mlp_full_command16_s54` 经宏映射到 V5；改为 linear compute top，替换 S24 输入/双 bank、单一 Down 输出端口 |
| 自动完整命令 | `H/rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv:147,586` | 当前 GU done、reader done、产品 cache full 后自动转 DOWN；新 top 按锁存 opcode 仅启动一个投影任务 |
| GU 调度出口 | `H/rtl/mlp/hap_mlp_gate_up_v5_scheduler16_q4.sv:304,340,520` | 在 S24 repacker 出口拆开；保留 gather、请求/tag FIFO 和重排；移除 SwiGLU 消费及等待448组产品的 done 条件 |
| Down 调度/共享计算 | `H/rtl/mlp/hap_mlp_down_v5_scheduler16_s54.sv`、`hap_mlp_shared_dual_slice16x12_s44_s54.sv` | Down 改接外部 A8 顺序 adapter；保持双8×12、恢复、S44/S54、部分和存储、mask 与末尾处理 |
| A8 工作 cache | 旧 `hap_mlp_input_frontend16_compact_cache.sv`、`hap_mlp_down_activation_cache16.sv:3,47` | 新建 MLP 私有 max448-group、16 row bank cache；借鉴280-bit行存储及局部寄存响应，不修改 Attention 共用 cache |
| Tensor DMA | `H/rtl/integration/hap_mlp_tensor_dma_bridge.sv:3,44,90` | 当前固定48 beat S24输入和32 beat Down输出；新增 REC576 parser、24 beat GU/32 beat Down writer及对应标签检查 |
| AXI 基础 DMA | `H/rtl/attention/hap_axi256_dma.sv:3,65,149,186` | 复用16-beat、4 KiB切分及最终B响应完成原则；Attention共用源行为保持，MLP新错误/取消需求由外层处理或私有实现承接 |
| Metadata 调度 | `H/rtl/integration/hap_mlp_metadata_scheduler.sv:7,210` | 命令锁存opcode，GU/DOWN分别检查消费计数，保持深度2的寄存响应FIFO边界，显式导出排空状态 |
| Metadata 驻留 | `H/rtl/mlp/hap_mlp_weight_meta_resident_ab.sv:290,379` | hard clear撤销valid/generation；正常job clear不连接此clear；导出或汇总真实读/写pending、bank状态供quiescence判断 |
| CSR/完成 | `H/rtl/integration/hap_mlp_axil_control.sv:122,194,337,388,452` | 新版本/CSR/准入、完整descriptor快照、epoch绑定、完成快照、身份ACK；保留独立AW/W握手与既有维护接口 |
| 集成/clear | `H/rtl/integration/hap_attention_mlp_production_core.sv:125,140,185,196,375` | 旧clear同时影响metadata和引擎，软件clear还发起共享maintenance；新增本地job_clear与硬清理边界，替换旧compute_done+store_done拼接 |
| 构建/物理入口 | `H/vivado/scripts/create_vcu118_board.tcl:6,20`；`build_vcu118_board.tcl:435,474` | 更新生产图、宏、required/rejected源检查、ROM用途、约束选择器和输入身份；保持Attention选择与板级双DDR连接 |

Host 映射由主控并行静态核查后纳入：

| 文件 | 现状与迁移要求 |
| --- | --- |
| `H/host/scalellm_memory.py` | 新增MLP六槽布局、按opcode长度与范围验证；DDR0常量和地址转换保持 |
| `H/host/scalellm_hostops.py:302,461` | `PinnedActivationPool`现每槽262144 B，容不下1376256 B GU输出；新增按tensor类型的MLP缓冲管理。`after_attention`已做residual/RMSNorm，GU准备不得重复RMSNorm |
| `H/host/scalellm_hardware.py:531` | 替换`buffer_id & 1`、`layer_id+1` generation、分离load/arm/start；两opcode各一次提交，完整核验completion |
| `H/host/scalellm_runtime.py:47,95,511` | 扩展MLP identity/decoder，保留Attention解码；中央调度在submit前过滤epoch并优先ready DOWN，禁止backend等待未来epoch |
| `H/host/scalellm_artifacts.py:123,307` | manifest把`mlp_abi`与运行ABI严格绑定；需显式迁移。`mlp_weights()`跨单命令持锁租约改为事件式epoch，保留失败poison语义 |
| `H/host/scalellm_board.py:138,2856` | 每pair命令128→192，更新跨pair续号、trace、evidence schema及性能统计 |
| `H/model/export_scalellm_llama31_artifacts.py:54`；`generate_scalellm_workload_reference.py` | 导出器仍使用MLP ABI v5/schema2；和工件loader、board evidence同步迁移，权重字节与哈希保持 |

## 3. W0 必须冻结的接口细节与设计缺口

原设计已确定职责，不需要重新选择Host/FPGA分工。以下问题会影响正确实现，必须形成一份共用的机器可读schema和接口表；不由多个实现者各自猜测。

### 3.1 控制 ABI、工件版本与提交结果

1. **单一schema。** 固定全部新CSR、复用字段、RW/RO/WO、reset值、strobe、保留位、错误码及RTL/Host生成位置。保留 `0x104=0x00060000`、新标识、`0x2A0`身份ACK；0x300–0x37F不得与旧0x100–0x2FF窗口碰撞。生成器的输出只是定义，仍需独立地址/行为测试。
2. **旧入口逐动作处理。** `0x110`旧START拒绝；原maintenance请求语义保留；START+maintenance等复合写不能产生部分副作用。`0x174`旧S24 load/store入口拒绝，不能仅拒绝load却仍留下外部store-arm生命周期。`0x13C`旧activation bank字段的读写行为需明确，建议只允许0且不参与新cache选择。
3. **descriptor快照。** START必须一次锁存设计§9.3全部字段。配置、active descriptor、DONE快照三者分开；执行期CSR改写不改变DMA地址、长度、权重地址、opcode或身份。AW与W任意先后到达，Validate完成后才给本次START的B响应。
4. **工件身份分层。** 不能直接把Host常量改为v6后拒绝所有未改变的权重manifest，也不能删除`mlp_abi`检查放行。W0选定显式的旧工件schema迁移/适配规则，分开数值格式、权重布局、运行控制ABI、tensor布局；导出器、loader、reference生成及board evidence共同使用，未知版本继续拒绝。
5. **Host可观察准入。** `XdmaSession.write32`只核验`os.pwrite`写满4 B，静态代码未证明AXI-Lite SLVERR会向Host传播。冻结传输层契约并在W4/W5验证：若写返回不足以证明接收，则在串行控制区核验本次ADMISSION_ERROR/JOB_STATUS及匹配的即时完成状态，避免拒绝后无限等completion。具体确认序列需覆盖“接受后极快完成”和历史admission错误，不能只看busy瞬时值。
6. **错误表。** 给每类准入、输入格式、算术/协议、RRESP/RLAST/BRESP、超时、ABORT错误分配稳定码，列明首次错误优先级、已写数据、drain策略、可否本地恢复、reset_required及ACK条件；不能把所有错误映射为成功done或仅清sticky恢复。

### 3.2 数据、标签与地址

| 边界 | W0冻结内容 | 关键约束 |
| --- | --- | --- |
| A8写cache | 9-bit group、4096-bit U8、384-bit metadata及原子记录提交；128/448 expected_groups | row10 metadata跨beat；16 B padding和metadata高2bit必须检查；未seal不读、seal后不写 |
| GU cache读取 | 请求/响应group与数据metadata绑定；旧7-bit group零扩展，bank固定0 | 返回高位非0、超128范围、错bank明确失败；响应持有到消费者接受 |
| Down cache读取 | 顺序0…447，只有scheduler握手后推进 | scheduler持有一个group服务全部342内部tile；最后发出读请求不等于cache可释放 |
| GU输出 | 6144-bit S24、10-bit tile16、matrix、record/tensor-last；1792记录 | `tile16=3×block48+record_index`；严格G0/U0顺序；局部block-last不是tensor-last |
| Down输出 | 8192-bit S32、8-bit tile16、tensor-last；256记录 | 342内部12列tile不能直接作为外部256条记录地址 |
| 输出DMA局部边界 | payload和标签同握手进入局部FIFO；按opcode串行化为24/32 beat记录 | 不把宽组合MUX/单一高扇出CE引回跨SLR路径；FIFO深度、读延迟与背压规则写入模块设计 |
| 地址准入 | 32-bit DDR1 local地址，以至少33-bit算术验证base+bytes；绑定buffer_id/区域/长度 | 建议首版仅接受规范槽及对应分区基址；若允许分区内偏移，须明确完整范围与其他对象不重叠规则 |
| 身份 | command_id、buffer_generation、epoch运行内不复用；cohort/buffer位序保持 | Host记录run/pair完整身份；硬件只核验当前descriptor/epoch，无须保存模型历史 |

单个activation shift为6 bit；设计§6.4中的20…44（GU）和12…44（Down）是**activation shift与weight shift之和**，用7-bit相加。不能在A8 parser对activation shift单独施加该区间。parser负责可独立判断的padding/reserved/canonical-zero规则，配对后kernel保持原总shift检查；canonical zero确切允许值在W0按原参考固定。

A8输入可在本地暂存/分row写入，但数据与metadata必须原子可见，完整记录合法前不能增加“有效group”计数。读取DDR的beat数、完整接收group数、计算投影数、输出入FIFO数、DDR写响应确认字节数分别定义。

`DONE_INPUT_BYTES`建议定义为完整合法输入记录的576 B累计；`DONE_OUTPUT_BYTES`定义为已成功BRESP确认的payload字节累计。故障时这些值不使部分tensor变得有效；`JOB_RECORD_COUNT`的提交边界、周期计数起止/停顿范围和32-bit溢出策略也必须在schema中明确。

### 3.3 完成、clear与epoch

- **拆分三个结束事件：** scheduler计算完成、整个硬件通路quiescent、Host ACK释放completion。成功完成必须包含期望计数、cache响应、metadata请求/响应/FIFO、kernel/tag/repack、权重reader/CDC以及数据DMA/B响应全部退役。
- **避免循环等待。** metadata scheduler当前依赖`command_done`清active；新quiescent若再直接等待active=0可能形成环。以issue=delivery=期望值、无pending/FIFO为显式drained，再由controller提交完成及局部clear。
- **本地clear矩阵。** job_clear清命令协议、cache有效性、tag/局部累加协议及live计数；保留resident A/B valid、active bank/generation和epoch。DONE及统计先锁存且ACK前稳定。hard clear/reset按原维护合同撤销metadata/epoch。
- **局部idle不充分。** resident bank内部已有read/write pending及idle条件，weight frontend也有CDC命令/响应状态；新增顶层drained必须覆盖这些状态，不能用`!scheduler_active`或`!mlp_busy`代替全部排空。跨域状态沿原同步/握手路径回传。
- **错误后的流控。** parser发现非法记录不能简单撤掉RREADY把已接受burst挂死；需按已接受事务边界丢弃/排空或进入明确fatal状态。输出错误时也必须处理已接受AW/W/B。暂不能排空的fatal保留reset_required，不伪造quiescent或ACK可恢复。
- **epoch原子绑定。** 提交绑定layer、active metadata bank/generation、四个weight bases与非零epoch；metadata切换使旧epoch失效。job_clear/ACK保留绑定；新epoch仅在完整quiescent、无completion、无loading/commit-pending且无fault时接受。
- **所有权独立。** epoch、DDR tensor slot、片上cache、metadata A/B是不同对象。Host在两个固定参与者DOWN成功并ACK且硬件排空后释放epoch；Host仍读取Down输出时可继续持有tensor slot。

### 3.4 已确认的构建迁移阻塞

`H/vivado/constraints/m003_entry_manifest.json`中48个source path全部绑定旧根 `/Workspace/ScaleLLM/`，没有一个绑定当前新根。`m003_entry.py:check_sources`要求path位于当前`HW`且匹配旧G2/源哈希，而`create_vcu118_board.tcl:12`在建工程前调用它。因此当前副本入口不能直接用作新方案构建入口；此结论来自JSON与源码静态核查，未运行EDA。

W0须明确新的输入manifest/工程入口及新根路径策略，W6前完成实际闭合。旧M003冻结manifest和历史证据保留；不改写旧根、不绕过哈希或路径检查、不把旧G2签名当新架构认可。生产源图中旧full/serial宏、必选源、SiLU ROM staging以及C01/SwiGLU物理选择器需要分别重定向/退役，Attention相关约束保留语义并重新验证覆盖。

## 4. 阶段工作包、依赖与验收

按设计W0–W8标识继续，内部可拆小任务。W2/W3/W4a接口稳定后可并行；W4b负责唯一集成写入。并行任务拥有独立文件，修改共享模块或schema由单一负责人整合。

| 阶段 | 依赖 | 具体交付/拥有范围 | 退出条件 |
| --- | --- | --- | --- |
| **W0：合同与基线** | 本计划 | 单一schema、接口/clear/错误表、Attention不改清单、工件版本迁移、新根构建入口方案、实际模型工件路径登记 | 地址/长度/计数独立核对；旧入口处理和SLVERR可观察策略明确；所有W1–W5输入合同可执行 |
| **W1：Host数值与codec** | W0 | 新MLP数值/codec模块；`hostops`的MLP边界与缓冲管理；独立oracle/定点向量 | H32、A8/meta、SwiGLU、REC576和GU解包全部16行逐位一致；S35超范围明确拒绝；RMSNorm恰好一次 |
| **W2：两个纯线性计算任务** | W0；W1提供向量接口 | 新linear compute top、GU scheduler出口、Down输入adapter、opcode metadata调度；保留kernel数值 | GU/DOWN各自可完成；权重/metadata/计算pass/输出计数正确；单独/连续/交替任务和持续背压通过 |
| **W3：cache与DMA** | W0；W1 codec | 新私有A8 cache、REC576 parser、GU/Down writer及局部FIFO；基础AXI DMA保持或私有适配 | 128/448 seal；随机/顺序重放；跨4 KiB/16beat burst；非法输入及部分响应处理；输出最终B前不得完成 |
| **W4a：控制合同实现** | W0 | CSR生成定义、AXI-Lite控制、job FSM、epoch及稳定completion；用mock状态接口测试 | 原子descriptor、准入无副作用、strobe/AW-W/ACK/ABORT/版本及计数行为全部符合冻结表 |
| **W4b：RTL生产集成** | W2、W3、W4a | `production_core`、`resource_top`及必要board wrapper；clear/metadata/epoch/排空接线 | 单epoch四个GU/DOWN顺序复用metadata；SHARED模式正常MLP切换不触发Attention维护；故障按分类恢复/锁定 |
| **W5：runtime与epoch** | W0、W1；硬件接入依赖W4b | `memory/hardware/runtime/artifacts/board`及export/reference兼容改动 | fake backend确定性调度、真实CSR/BFM集成、迟到completion与取消测试通过；192命令/pair、跨pair身份不复用 |
| **W6：新综合及资源归因** | W1–W5功能闭合；新构建入口与资源合同 | 新生产manifest/宏/生成定义、构建检查、约束选择器、输入manifest；实际新网表及分层/SLR资源 | MLP H32/A8编码/SiLU/产品层次为0，Attention相关层次保持；双8×12/S44/S54无误复制；资源与新增开销可解释 |
| **W7：完整物理实现** | W6架构/资源审核 | 新网表opt/place/physopt/route、时序/DRC/CDC/约束覆盖报告 | 合法布线，全部必要时钟setup/hold/pulse-width与规则检查闭合；失败保留原生结果，按新归因调整 |
| **W8：板级闭环** | W7；对应执行范围已授权且板卡可用 | 新bitstream/Host/模型身份；GU、DOWN、整层、32层双cohort及重复运行日志 | 数值/地址/身份/epoch一致；真实DMA、拒绝可观察性及恢复受测；Host/PCIe/权重staging/硬件busy/总wall time分项完整 |

阶段关系：`W0 → {W1, W2, W3, W4a}`；`{W2,W3,W4a} → W4b`；`{W1,W4b,W5} → W6 → W7 → W8`。W5调度模型在W0后可先开发，其数值与硬件闭环必须等待W1/W4b。W6可提前准备静态入口，不能提前把未通过功能集成的设计当已验收硬件。

## 5. 首轮开工顺序

建议首次实现范围为 **W0＋W1**，同时固定W2/W3/W4a之间的端口；本计划本身不启动这些工作。

1. 登记当前新工程根、baseline、唯一生产/集成负责人及本阶段合同，建立本任务导航；不重建旧任务或修改自动索引生成区正文。
2. 完成schema、工件ABI迁移规则、descriptor/clear/错误表、新根构建manifest方案；列出Attention叶子源/宏/共享源不改集合。
3. 实现独立Host参考与REC576/GU codec；先用小型确定性整数向量覆盖边界，再接实际模型输入。现有fixture只作单元证据。
4. 调整MLP专用缓冲容量、`after_attention`边界及Down前S35范围检查；产出可用于RTL验证的payload、期望输出与哈希。
5. W0/W1集中验收后，按文件所有权推进W2/W3/W4a；数值/接口实质变化交架构负责人集中修订，普通实现修复在阶段内连续完成。

W0若仍缺真实32层工件的本地manifest路径，可先完成schema、单元参考和RTL接口工作；接真实模型、W6候选身份和W8验收前必须补齐，不在其他工程中猜选数据。

## 6. 验证安排与独立判据

下表是待执行矩阵。本轮未运行列出的测试，也未把既有PASS报告计作本次结果。

| 验证组 | 范围/关键用例 | 独立通过依据 |
| --- | --- | --- |
| 数值迁移 | 16行全覆盖；H32正负边界；RNE ties；SiLU ±16端点；乘法舍入/溢出 | 冻结原整数公式/SiLU表；逐边界逐位比较，不由新codec/RTL自身生成gold |
| S35拒绝 | `D=4269834239`、`4269834240`；旧helper夹码仍返回场景 | 前者按合同处理，后者Host失败且DOWN提交数为0 |
| 数据ABI | 576/768/1024 B；row10 metadata跨beat；尾GU block仅32列；G/U重排 | 独立字节索引公式与完整payload比对，不能仅pack→同一unpack自洽 |
| A8 cache | GU128 seal、DOWN448 seal；乱序/超界read；seal前读/后写；长响应停顿 | scoreboard逐group/row核对，payload与metadata不分离，旧命令响应不进入新命令 |
| DMA | 16beat限长，页内4032 B记录起点，AW/W/R/B各自停顿，错误RRESP/RLAST/BRESP | AXI BFM检查地址/beat/last/响应；完整记录计数与成功B确认计数分别核验 |
| GU/Down计算 | 零点非零、W4极值、总shift边界、尾列mask、全尺寸计数 | 独立group恢复/累加oracle；GU229376 metadata/305920 pass/1792输出，Down114688/153216/256 |
| 控制准入 | 所有非法opcode/长度/地址/format/epoch，完整/部分/零strobe，AW先/W先 | 非法START返回拒绝、无DMA/compute/完成副作用；descriptor执行中不被CSR写改变 |
| 完成/ACK | 最后结果后阻塞输出/B响应；未ACK新START；错ID/迟到/重复ACK | DONE快照稳定，成功completion仅在全部事务退役后，错ACK不能清其他结果 |
| clear/epoch | 同epoch四任务；连续GU/连续Down；metadata切换；epoch相同但绑定不同 | metadata valid/generation和epoch跨job保持，硬清理撤销；不把加载非active bank等价于允许切层 |
| 双cohort调度 | Host处理长短不一、下一层GU先ready、取消/失败、跨pair重复layer | 当前epoch DOWN总可被调度；无锁等待未来epoch；固定参与者失败不提前释放权重槽 |
| Attention保持 | 单独/SHARED、MLP load/compute/drain/Host停顿及正常切换 | 同输入与工件输出逐位一致；DDR0/CSR/时钟CDC保持；无正常MLP触发全局维护 |
| 完整链 | 原完整MLP参考 vs Host→GU→Host→DOWN；单层→32层→双cohort→多pair | 各边界张量/元数据/哈希可定位；差异定位到阶段，不用cosine代替逐位要求 |

现有CPU测试入口集中在 `H/tests/test_scalellm_{artifacts,hostops,memory,hardware,runtime,board,export}.py`，构建入口测试包括 `test_vcu118_builder_sources.py`、`test_vcu118_builder_rom_staging.py`、`test_rebuild_contract.py`。调整其原有行为断言并新增真实风险用例，不能直接更改gold迎合DUT。

现有RTL测试可复用其BFM/激励：`H/tb/hap_mlp_{axil_control,metadata_scheduler,weight_meta_resident_ab,launch_readiness_local,tensor_dma_bridge,tensor_dma_bridge_banked_stall}_tb.sv`、`hap_mlp_shared_dual_s44_s54_dispatch_tb.sv`及 `hap_attention_mlp_production_v5_{joint,cdc}_tb.sv`。新任务/cache/REC576/epoch应有独立测试入口；旧full-command测试保留其基线含义，不因新生产图而改成假兼容。

`H/model/mlp_fixed.py`的默认`ROWS=8`需显式扩展验证至16行。`H/data/rebuild_v5_frontend/swiglu/manifest.json`自述`finite_integer_unit_fixture_not_model_or_weight_evidence`且`golden.executed_or_imported=false`，不能用作真实32层模型/权重验证证据。

## 7. 主要风险与处理优先级

| 优先级 | 风险 | 处理/不能越过的边界 |
| --- | --- | --- |
| 首批闭合 | ABI升级误拒绝旧权重工件，或放松检查导致错工件通过 | W0显式schema迁移并保留权重bytes/hash；W1–W5验证正负兼容样例 |
| 首批闭合 | 新根仍受旧M003绝对路径/G2绑定阻塞 | 新任务新输入manifest与入口；历史冻结文件不重写，无视绑定检查不算修复 |
| 功能关键 | GU完成条件仍依赖SwiGLU、metadata要求两阶段消费 | W2按opcode结束，显式队列排空；全尺寸握手计数受测 |
| 功能关键 | job_clear撤销metadata或epoch，或通过共享维护暂停Attention | W4b连接矩阵和同epoch四任务/SHARED回归 |
| 功能关键 | Host中间处理期间权重被换层、未来GU占住唯一worker | W5中央epoch过滤、DOWN优先、事件租约及FAILED_DRAIN |
| 功能关键 | parser/输出错误导致已接受AXI事务无法排空 | W3/W4错误表与故障注入；reset_required严格保留 |
| 集成关键 | START写成功不等于硬件接收；快速completion或旧admission状态误判 | W0冻结确认序列，W4/W5 transport测试，W8真XDMA验证 |
| 物理关键 | 新wide FIFO/MUX/CE抵消删除非线性的收益 | W3局部存储/寄存设计，W6分层与扇出报告，W7实际路由证明 |
| 系统关键 | GU输出缓冲不足、Host中间计算与额外PCIe成为瓶颈 | W1分类型缓冲；W5/W8分项测量，保持正确性oracle与优化实现性能口径区别 |

既有全板LUT/DSP/URAM和route失败记录只用作可比较的历史基线。385→245 KiB cache逻辑payload、3072个保留kernel DSP的结构推导，都不能直接作为新综合节省量或可布线证明。

## 8. 阶段记录、模型分工与执行约束

- 架构/接口/数值合同及集中阶段验收由Astra xhigh承担；本轮该文档工作按此配置委派。工程实现采用项目 `agent/model_policy.md` 当前role覆盖 `gpt-6.1-sol / xhigh`，实际启动时核验并登记；本轮没有工程代理或EDA启动记录。
- 模块实际开发时维护`source/design.md`和`source/results.md`，链接本设计及对应条款，保留现有生产源码/测试布局。实验记录使用现有research-agent三份摘要及R/AT原始证据，不为每次普通修复新建批准文件。
- 每阶段一次写清独立参考、测试范围、退出条件、写入所有权及资源合同，随后连续实现/验证/修复；规格不变的普通错误不反复请求批准。实质架构、接口、数值或验收变化集中修订受影响合同。
- 后续重工具维持单一实际EDA owner与项目共享资源协调；CPU线程、RSS、最低系统可用内存、许可与进程/运行边界须按本次环境确认。本轮不继承旧owner或杜撰数值预算，也不以旧snapshot中的running为当前运行事实。
- 所有实际尝试保存源码/依赖/参数/宏/schema/XDC/模型输入身份、工具版本、原生命令/退出码、完整日志和PASS/FAIL/NOT_RUN。性能计数定义与数据哈希进入结果，复用未变旧证据必须注明其原适用版本。
- 正常推进的长任务遵守项目有效停止/资源规则，不因静默或缺少一次新审核签字强停；出现资源保护或无新可检验原因的重复失败时停止无效循环，记录具体阻塞和替代覆盖。

## 9. 本轮静态结论与尚未验证范围

已完成：全文设计及所需技能/工程约定阅读；HEAD与设计基线比对；RTL命令/调度/CSR/metadata/clear/DMA/生产构建映射；主控提供的Host/ABI/现有测试核查；35个设计源码引用的本地存在性核对；REC576、四类payload、305920/153216内部pass、192命令/pair和六槽范围/对齐/不重叠的静态复算；旧M003 manifest的48个旧根路径核查。

上述结果支持进入W0/W1实现准备，不代表任何新硬件或Host实现已经通过测试。当前未验证：新schema/RTL/Host行为、实际模型工件本地可用性与哈希、真实XDMA拒绝传播、工具/许可/资源可用性、功能仿真、综合、物理时序、板级数值和性能。原设计文件保持不变，生产代码保持本轮开始时状态。
