# M006：MLP 线性投影硬件工程

日期：2026-10-24。用户当前要求：“创建子智能体完成新项目工程的搭建 最重要的目标就是完成硬件工程”。本合同落实于新副本，状态为执行中，不能以目录和模板齐全代替硬件完成。

## 2026-10-25 最新交付顺序：先生成 bitstream

用户在询问生成时间后明确要求“不能先生成bitstream吗”。按该优先级，允许立即从R008/AT001_impl已保存、合法布线与同步域时序通过的routed.dcp生成工程验证版bitstream文件；不再以前述Max-DPO约束修正/完整外部reset签核作为生成文件的前置。生成文件不等于完成硬件全签核，工件须明确标注跨时钟绝对延迟覆盖及外部reset验证未闭合，禁止自动下载/上板/GPU。不得降低DRC严重性或绕过真实生成阻断。

A022仍为唯一重EDA owner。若AT002只读取证仍运行，按用户先生成的优先级收束剩余SMC辅助取证，保全已完成及partial工件、输入身份、实际退出状态、归属进程清理和锁释放，再开始独立bitstream attempt。收束原因是USER_PRIORITIZED_PRELIMINARY_BITSTREAM，不是时间/静默超限。原routed DCP与102冻结输入不改写；bitstream另存并绑定父DCP/工具/日志/SHA。文件生成后继续design §12约束修正与资格核验。此条取代此前本任务尚未进入bitstream及Root安排修正后才生成文件的限制；板卡范围仍未开启。

## 权威输入与目标

- 工程根：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`；基线 `0c0d2cdba00ef8e91cc96e678ca4e0b68c4cda60`。
- [设计规范](../../PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Design.md) 与 [实现计划](../../PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Implementation_Plan.md) 是本任务输入。
- FPGA MLP只执行GATE_UP/DOWN，保留双8×12、S44/S54、format05恢复/舍入；全部MLP H32/A8编码/SwiGLU在Host。Attention、双DDR职责及原时钟/CDC语义保持。
- 硬件为主线：真实RTL、可复现仿真、新目录可构建Vivado工程、功能合格后新综合与物理验证。Host优先交付数值oracle、REC576/GU codec和硬件验证驱动；完整应用调度不得取代或阻塞独立硬件模块工作。

## 阶段与所有权

| 子任务 | 工作与退出条件 | 负责人 |
| --- | --- | --- |
| SM025 | W0接口/schema/clear/错误/工件兼容冻结、模块设计，直接供工程实现 | A021，Astra xhigh |
| SM026 | W2/W3/W4硬件及生产集成，W1所需数值支撑；模块与集成验证 | A022，GPT-6.1 Sol xhigh |
| SM027 | 新根构建入口、功能覆盖、新综合及物理结果，按依赖推进 | A022执行，A021阶段审核 |

Root唯一维护AGENTS、goal、mission/current、共享索引及主任务记录。A021独占`project/hardware/source/mlp_linear/`架构文档与机器可读schema。A022独占新/修改RTL、TB、Host参考、构建脚本与E013工程证据。其他人也在工作，不撤销他人修改；接口实质差异交架构负责人，普通错误直接修复。

## 必须验收的行为

1. GU128组输入、1792条交错S24输出；Down448组输入、256条S32输出，尾列、metadata、恢复正确。
2. 单命令A8 cache、REC576 parser、跨4KiB DMA与背压正确；completion晚于所有reader/CDC/tag/cache/meta/B响应退役。
3. descriptor原子快照、旧入口拒绝、身份ACK、错误传播、job_clear/hard_clear分离；同epoch四任务复用metadata，正常切换不暂停Attention。
4. Host迁移整数边界逐位一致，覆盖16行、S35超范围拒绝、原SiLU表与输入S24舍入。
5. 新生产层次真实移除MLP非线性/量化，保留共享kernel；源清单与约束绑定新根，旧M003冻结清单保留历史身份。
6. 仿真、综合、合法route、时序/DRC/CDC、bitstream/板级分别记录，未执行写NOT_RUN；静态检查/fake backend不替代真实RTL/物理证据。

## 执行和资源

- 允许连续源码实现、CPU参考测试、编译/仿真、工程生成及功能闭合后的综合/实现；尚未进入bitstream下载、板卡运行或GPU/ACC/PPL任务。
- Root加两个子智能体，无后代。单重EDA owner；先核实际工具、许可、CPU/内存与共享资源，再写入E013协议。当前可用内存不是独占额度，不操作旧工程或其他进程。
- 普通修复/回归连续执行；实质接口、数值、职责变化集中修订。不能降断言或换参考迎合DUT。
- E013保存命令、全部输入哈希、工具版本、日志、原生退出码；源码仍在project/hardware。正常任务不因墙钟/静默强停；资源保护或重复失败无新原因时记录并调整。
- 缺完整模型工件或重工具时继续独立模块与工程入口，明确剩余验证缺口，不虚报完成。

## 启动状态

M006/SM025–SM027/E013已登记。A021负责接口冻结，A022负责硬件搭建与实现；当前状态以E013三摘要及真实工具证据为准，不恢复历史M003进程。

## 当前并行分工补充

A021已交付W0 revision2并完成Host参考及早期模块证据的有限独立审核。A021已完成design revision3 §9有界整合验证合同；A021已完成新板级入口和生产图有界预检并空闲；当前活跃为Root、A022硬件/EDA、A023构造与构建Tcl加固。A023已完成Host数值支撑和32项CPU测试，追加独占`project/hardware/tb/hap_mlp_linear_axil_control_tb.sv`与`project/hardware/vivado/manifests/mlp_linear/csr.list`，只写自检测试，不改RTL或执行EDA。A023独占`project/hardware/host/scalellm_mlp_linear.py`、`project/hardware/tests/test_scalellm_mlp_linear.py`、E013内`experiment_results/host_reference/`和agent/A023；A022不编辑这些文件，继续其余硬件主线。Root统一整合。后续整板资源按[最新资源决定](../../.research-agent/decision_inputs/M006_resource_profile_revision_20261024.json)：32核可用范围/192GiB RSS，Vivado单流程8线程、独立IP/OOC最多4jobs，单套完整implementation。小仿真保持8核/96GiB。

A023追加独占`project/hardware/tb/hap_attention_mlp_linear_integration_tb.sv`与`project/hardware/vivado/manifests/mlp_linear/integration.list`，继续只写测试、不跑EDA。A022可接管已交付CSR TB的普通仿真修复。主整合测试采用GU N128/Down N64、完整K128/448，生产ABI与默认形状保持；遵循[design.md §9](../../project/hardware/source/mlp_linear/design.md)的派生计数、默认生产保护及真实错误排空/复位边界。

A022已明确移交A023独占`create_mlp_linear_board.tcl`和`build_mlp_linear_board.tcl`；A022继续独占`m006_entry.py`、`run_mlp_linear_board.py`、RTL/manifest/EDA及三摘要。A023先修复其整合TB参考模型，再交A022真实运行；参考公式和原literal不放宽。

A023已交付整合Python独立gold与构造/构建Tcl加固，相关TB及两份Tcl的普通修复所有权归还A022。A021已完成design revision4错误决策规则及五项实现缺口的有界审核并结束；当前活跃为Root与A022。A022保持唯一重EDA owner，按冻结attempt终态→普通修复/回归→真实构造/综合/物理依赖继续。

## 用户补充关注：SLR 问题

用户明确关注本次删除MLP前后处理能否缓解长期SLR拥塞。整板资源下降仅为中间证据；物理结果必须对照旧热点，核各SLR CLB站点/packing与局部拥塞、保留共享核/Down/Attention及DDR-meta通路的实际跨区连接和关键路径，并以合法route与setup/hold结论收束。当前单一冻结implementation自然推进；现有报告不足时，终态后可对已保存同阶段DCP进行一次有界只读取证，不热改运行输入、不并发重EDA、不为统计重复implementation。若需进一步结构改造，依据实际新热点集中选择，不预设迁出非线性必然解决。

## 下一版方向：GU-only（用户 2026-10-24 补充）

**最新执行授权：用户已明确“可以开始进行”。** 上述新版方案现进入G0–G5实施阶段，取代下文此前仅规划限制。A022负责独立GU-only RTL/TB/构建图及唯一EDA；A021将机器草案集中冻结为独立GU-only合同并完成阶段验收；Host Down与软件整合由Root分配独立工程所有权。旧v6 ABI/源图和R005冻结输入不热改；可立即创建新版本文件，重EDA依单owner串行执行。普通修复、受影响测试、新综合和物理验证连续推进，无逐次批准。硬件G5只依赖G4R，不等待G4H完整32层Host链或性能测量。bitstream/板卡/GPU范围仍未开启。

A021已交付完整 `abi_gu_only.json` 并结束本轮合同收束；当前Root+A022+A023活动。A023独占新增 `project/hardware/host/scalellm_mlp_gu_only*.py`（生成 `*_abi.py` 归A022）、`project/hardware/tests/test_scalellm_mlp_gu_only*.py`、`E013/experiment_results/host_gu_only/` 和A023记录；旧Host模块只读复用，避免改变R005输入。A022独占新RTL/TB/生成器/EDA，其首批7模块已在R006/AT001取得xvlog语法通过，尚不代表数值或层次验收。Host CPU工作限定8核、子树目标8GiB并计入现有总额度，无GPU/板卡。

**Root阶段收束决定（新版执行授权后）：** R005已采集全局/八scope/站点/拥塞/旧窗口核心证据；剩余新窗口与显式路径样本不再作为GU-only实现依赖。Root在用户已授权的新目标下取消这部分可逆补充取证，交唯一owner A022受控停止R005归属树、保全原始partial/输入身份/退出码并核零存活后释放锁。原因是 `SCOPE_SUPERSEDED_BY_AUTHORIZED_GU_ONLY_IMPLEMENTATION`，不是时间或静默超限，不声称用户单独发过kill指令；未完成查询标NOT_COLLECTED，诊断仅PARTIAL，不改原R004自然FAIL。此阶段决定取代此前继续旧诊断全部查询的安排，不形成未来正常任务的墙钟强停规则。之后新GU-only小仿真按8核/96GiB及单重EDA继续，无新增批准。

用户随后明确要求“删除Down，重新规划一个新的方案出来”。本轮交付独立新版设计 `PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md`，由 A021 主笔、A022 核实施依赖、Root 整合。新方案与 `abi_gu_only_draft.json` 均标记计划状态，本轮不启动下一版生产修改或新综合；既有 R005 只读取证按原授权继续收尾。原 GU+Down 设计、ABI、功能与失败物理证据继续保留其原身份。

用户要求考量下一版移除 FPGA 的 Down 矩阵计算，仅保留 MLP Gate/Up。本次先形成可执行架构与资源评估；Down 移到 Host 完成，不能解释为删除模型数学中的 Down 投影。A021集中修订下一版职责、数值/ABI/metadata/验证方案，A022提供实现依赖和资源事实。方案状态与已实现状态分开；旧 ABI、失败 attempt 和正在执行的 R005 只读取证输入均保留，不热改。

R004/AT001_impl 已自然失败：473423 signals failed to route、545088 node overlaps；不能以失败后 DRC 的局部成功覆盖非法布线结论。R005 继续按原单 EDA 范围对已保存 physopt DCP 取证，不原样重跑旧 implementation。

下一版保留 Attention、Attention→物理 DDR0 / MLP→物理 DDR1 路由、GU 数值规则和当前双 8×12 并行尺寸；拟静态删除 Down 专属调度/S54 累加/输出队列与重排/metadata A/B，裁剪共享恢复路径的 Down 专属部分并缩小 GU 工作缓存。禁止只禁发 DOWN 而保留全部硬件。共享乘法阵列仍供 GU 使用，不能预设 DSP 减少三分之一；缓存逻辑容量缩小也不能直接换算成 BRAM 净减少。资源预估来自当前互不包含的层次对象，最终净变化须由新综合验证；是否缓解 SLR 仍须按相同阶段物理证据验收。
