# E006 / R002：输入预处理向 SLR2 分担的单变量候选

execution：CPU 选择集合、源码职责与资源核查已完成；未实施。verdict：有依据的候选，拥塞收益及合法布通尚未验证。applicability：E005 原 physopt 图和144项冻结输入；更早 OPT 必须重新解析。review：交主控内部审核，非用户验收。E006 仍只读，热点/端点归因继续。

建议首轮只改变一个物理局部性组：**tensor 输入 bank + frontend S24 capture、Hadamard、4 个量化器及其附属控制移向 SLR2**。bundle、两组 activation cache、Gate/Down 调度器和 compute 核不加入这个组；tensor 输出、DMA 本体与 DDR/PCIe 互联也不加入。同 RTL、同 IP、同数值/ABI、同 SSI_SpreadSLLs、同 physopt/route directive。SMC/slice 调整另留后续，不叠加首轮。

这项优先级尚待 E006 实际热点/连接闭合确认。若候选不触及主要热点、或其边界控制无法满足时序，本候选不因资源数量较大而自动成立。

## 1. 功能与真正消费者

9 份实际 RTL 已逐项匹配 E005 冻结 SHA；源码行、hash、选择规则和计数在 [事实文件](input_frontend_locality_candidate_facts.json)，可复现 CPU 入口为 [audit_input_frontend_candidate.py](audit_input_frontend_candidate.py)。

`u_tensor` 从 256-bit AXI 数据读通道收集 48 拍，形成 12288-bit S24 cohort16/group32 输入。frontend 保持同一完整输入，折叠 Hadamard32 逐行运行；4 个 A8 quantizer 依次处理16行，0/1负责前8行，2/3负责后8行。完成行暂存于 bundle，最后原子写入两个8行 ping-pong cache。

cache 响应是4096-bit U8 +384-bit metadata（源码接口4480位）。它只送 Gate/Up scheduler，组合减 zero-point 后，激活 S9、ScaleCode 和 shift 进入 shared_compute 中心两项 parent FIFO，再按前/后8行分给 branch0/1。两套 parent_head/parent_tail 各6560个实际FF全部在SLR1。Down 读取的是 SwiGLU 输出后的独立 down_activation_cache，不直接读取这两组输入 cache。此处不改 Hadamard、ScaleCode、format05 或协议原子性。

整 frontend 单独移动会暴露12288-bit输入和4480-bit响应两侧接口；整个 tensor 一起移动又会暴露8192-bit输出 tile。选择输入侧子集可以保留这些宽连接的局部性：tensor input→S24 capture在新组内；bundle→cache→Gate保留原侧；主要源码载荷边界缩为256-bit DMA读入和四个quantizer的 `4×(256+24)=1120` 位输出。**这些是静态源码接口位宽，不是实测活跃位、unique net、leaf pin、SLL数量或带宽。**

## 2. 精确选择规则与当前计数

前缀基址 `B = scalellm_vcu118_f05_bd_i/core/inst/u_core/`。

1. 取 `B + u_compute/u_mlp/u_input_frontend/` 下全部 primitive 名称，排除 `u_cache0/`、`u_cache1/` 后代，再排除 root-relative 名称以 `bundle_u8_bank_r`、`bundle_meta_bank_r`、`g_bundle_row[` 开头的单元。
2. 并入 `B + u_tensor/` 下 root-relative 名称以 `g_input_beat_bank[`、`input_beat_r`、`input_group_r`、`input_group_valid_r`、`input_beat_count`、`input_group_count` 开头的单元。

规则使用字面字符串前缀，方括号不是glob字符。不是 `*input*` 搜索，也不是整 tensor。当前集合77360个primitive，排序NAME清单SHA `a478123e7b8a5605017a4ecd1f423abe715a8715f2f3923c1eb056cd01782a73`。其中77246条已放置且全在SLR1；114条未放置为76 GND+38 VCC，**不需硬绑**。8 DSP每块包含一个DSP48E2及8个内部子primitive，约束端须归一到实际DSP放置对象，不把72条记录当72 DSP或分别硬绑内部单元。

| 选中组成 | 当前 SLR1 CLB FF | raw logic LUT primitive | DSP块 |
| --- | ---: | ---: | ---: |
| frontend S24 capture/局部CE | 12288 | 97 | 0 |
| Hadamard | 5301 | 8151 | 8 |
| 4 quantizer合计 | 10412 | 23240 | 0 |
| frontend其他控制/胶合 | 260 | 125 | 0 |
| tensor输入bank/局部CE | 12288 | 52 | 0 |
| tensor输入控制与计数 | 78 | 44 | 0 |
| 合计 | **40627** | **31709** | **8** |

选中组BRAM/URAM均0。保留的cache0、cache1各4796 FF+33 BRAM36K当量；bundle实际4448 FF（源码24-bit metadata中的常量位不会全部成为寄存器）。两套12288位输入存储均逐索引核全：tensor48×256、frontend16×768，没有靠名称模糊计数。

所选组当前触及13230个SLICE，**12254个还包含组外primitive，仅976个当前完全由该组占用**。移动不能宣称释放13230个站点；主要假设是降低现有站点内的资源/局部连线负担，净释放站点和重打包结果以新place为准。

## 3. SLR0 与 SLR2 接收预算

原生来源：[global_SLR](../../../../hardware/vivado/reports/m002_E006_R001_AT001_physopt_attribution/utilization_global_SLR.rpt)，表行69–94；总容量来自E005原physopt utilization。三个SLR容量相等：每区394080 LUT、788160 FF、49260 CLB、720 BRAM36K当量、320 URAM、2280 DSP。

| 当前剩余/使用 | SLR0 | SLR2 |
| --- | ---: | ---: |
| 原生LUT剩余 | 142117 | 180399 |
| CLB FF剩余 | 463633 | 531004 |
| 空CLB站点 | 491 | 3412 |
| BRAM剩余 | 568.5 | 398.5 |
| URAM剩余 | 40 | 128 |
| DSP剩余 | 419 | 525 |
| 与SLR1原生SLL已使用/总量 | 10474/17280 | 8509/17280 |

两侧FF/DSP计数均容得下本组；LUT这里只能把31709 raw primitive当逻辑规模参考，不能与原生CLB LUT报告直接相减预测。SLR2相对有更多空站点和跨区资源余量，故列首选。SLR0贴近MLP DDR1的物理端，但该候选没有搬DMA/SMC，不能因此假设256-bit读入已本地化。SLR2也不是空白区域：Attention仍在其中运行，站点占93.07%；剩余LUT/FF槽不保证打包、局部路由或时序可行。不能用1120等静态位宽直接从原生SLL剩余量扣除并称“足够”。

## 4. 控制边界和时序风险

完整物理cut的canonical nets和所有leaf端点**尚未覆盖**，以下是源码级必要类别，不能冒充完整跨界net清单。

| 方向/关系 | 源码接口与需要核的风险 |
| --- | --- |
| 留存DMA/状态→SLR2输入组 | 256-bit `dma_rd_data`；读握手、load/start/state、active_bank、clear/reset等控制。输入beat/group/count已选中，tensor全局state/DMA留存，必须核decode实际归属。 |
| SLR2量化→中央bundle | 四套U8/meta共1120位；quant fire/输出wave与row写使能。原保护LUT/CE必须保持，不能把CE叶恢复成全局高扇出树。 |
| SLR2预处理控制↔中央cache | bundle_valid与bank/group标签、两半wr_ready；读/释放计数及原子性检查也在frontend其他控制集合，可能增加小控制路径的往返。 |
| 组内→上层状态 | frontend四项32-bit计数、error/format_error；tensor两项32-bit输入计数。实际优化/合并后的有效net须另核。 |
| 公共时钟/复位 | core同钟，物理跨SLR不自动变CDC；rst_n/clear的reset/release与原约束仍须保持和重验。 |

量化结果→中央bundle的现有寄存器边界没有新增流水，距离增加可能伤setup/hold。缓存ready/valid合并、错误检测和tensor全局状态也可能形成跨区组合控制。当前选择把所有frontend剩余胶合一起带走，范围明确但并未证明最优；如native cut发现强控制往返，先修改该局部性组的边界，不同时叠加SMC或算法变更。若必须加FIFO/复制寄存器/RTL重构才满足时序，应另立RTL候选和功能差分范围，不能称仍为纯放置实验。

## 5. 纯放置复用与最小验证

可以提出复用同一原OPT来源，不需因本候选自动重综合。更清晰的共同起点是E005 AT003已经资格的 `debug_materialized.dcp`：396068466 bytes，SHA `8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f`；原 `completed_debug_pre_place_facts.json` 绑定了该图和pre_place/integrity/constraint证据。这里仅核工程收据，没有再次读取大DCP。

**physopt上得到的名字/资源不能直接套用OPT或debug_materialized图。** place可能复制、合并和改名，DSP内部对象也不同于可约束物理单元。工程在下一合同的同一次checkpoint打开中，先重新解析exact roots/前缀，保存完整selected/excluded NAME+REF清单、数量及fingerprint；核两套输入寄存器索引、4 quantizer、1 Hadamard、8 DSP，核没有cache、bundle、tensor输出/SMC/MIG或clock buffer误入。任何数量差异需按阶段网表身份解释；不靠“与physopt完全等数”代替语义核验。114常量排除，DSP按物理父单元归一化。

在该图按真实SLR2站点范围给选中组增加一个SLR级放置约束，边界不预设手写坐标，不引入routing containment或排他保留区域，不修改其余组的位置要求。硬/软属性需在合同中明示：若目标是验证实际卸载，应要求所选可放置单元确实落SLR2；只有软偏好时必须报告实际服从率。继承约束和固定LOC冲突须预核，原pre_place完整资格检查继续，不能用E006图身份替代新尝试资格。

随后保持 `place_design -directive SSI_SpreadSLLs`、原Default physopt与完整route设置，单EDA、相同资源限制；首轮唯一实验变量为这个局部性组的SLR放置要求。placement全局重排是变量的后果，必须在报告里记录，不能假设组外布局不变。

布局后先验证实际selected组位置/缺失/复制、保留组变化、SLR1资源和共享站点、SLR2容量与新热点、canonical跨区端点、控制扇出以及原80保护边界。报告setup/hold/PW、CDC/reset/IO资格，并按同阶段比较固定窗口及新增最坏峰；未测固定窗口拥塞仍为UNAVAILABLE。达到单项局部改善不提前宣称成功，继续完整route；终态要求合法路由无冲突、报告实际setup/hold/PW和所有既有安全限制。若route失败，保存失败图、原错误、重叠节点/失败信号和完整监督收尾；不把失败覆盖成PASS，也不自动扩大下一轮改动。

本候选的可证伪预期：选中组确实卸载SLR1，SLR1热点/局部连接压力下降，且SLR2与新跨区路径没有形成更严重瓶颈。资源移走但原热点不变、跨区控制恶化、或全局重排加重失败都构成需要重新划边界的证据。合法布通仍需实际完整implementation证明。

## 6. 执行边界附录：选择、硬约束与完整cut

本附录细化上述范围及[后继合同](../../../../../mission/M002_ddr_separation_and_timing_recovery/slr2_input_locality_candidate_contract_2026-10-17.md)第3/4项，不增加批准停点。机器可读规则、拒绝条件和覆盖字段见[执行边界计划](input_frontend_locality_execution_boundary_plan.json)。execution：有界CPU规格完成；verdict：可据此准备工程入口，原生API/对象行为与物理收益未验证；applicability：指定父图及真实重解析的候选；review：内部交付，候选仍planned，E006未完成。

**实际pre-place选择。** §2字面前缀在本次图重新求值，逐条保留include/exclude原因。原始匹配记录、排除GND/VCC后的逻辑集合S、可放置集合P分开；P只含逻辑leaf及去重的DSP48E2父对象。DSP内部primitive通过原生祖先关系或逐层exact路径查询并核REF映射，保留child→parent证据，不用未放置图的LOC或名称后缀猜测。当前physopt参考值为77360 raw→77246 S→77182 P（77174逻辑leaf+8DSP）；其中64个DSP内部记录折叠到父对象，不能以此强求pre-place同数。核两套12288 payload索引、4量化器、1 Hadamard及8DSP；未识别REF、clock/I/O/BRAM/URAM或组外payload误入均显式报错，不能静默过滤以凑数。

**hard Pblock与冲突。** 对真实SLR2全域所需SLICE/DSP站点求原生集合，再压缩资源ranges并验证展开后的实际SLR归属，不复用历史坐标。唯一新Pblock为`m002_input_locality_slr2`，属性固定为`IS_SOFT=false`、`EXCLUDE_PLACEMENT=false`、`CONTAIN_ROUTING=false`；P须在SLR2，其他逻辑可共享站点、走线可越界。以下只是尚未执行的构造片段，变量必须来自真实对象及上述检查：

```tcl
create_pblock m002_input_locality_slr2
resize_pblock [get_pblocks m002_input_locality_slr2] -add $actual_slr2_resource_ranges
set_property IS_SOFT false [get_pblocks m002_input_locality_slr2]
set_property EXCLUDE_PLACEMENT false [get_pblocks m002_input_locality_slr2]
set_property CONTAIN_ROUTING false [get_pblocks m002_input_locality_slr2]
add_cells_to_pblock [get_pblocks m002_input_locality_slr2] $candidate_placeable_cells
```

保留现有LOC/BEL固定状态、pblock/SLR约束及相对放置macro成员。名称已占用且来源未资格、区域为空/不明确、macro需要组外搭档、既有硬约束不相容、加入P会改动其他membership或属性读回/成员集不符，均拒绝该次约束应用并作合同内修复；不清LOC、不改soft、不削弱DRC或全局时序。布局后按实际对象关系核存活/复制/丢失，要求经解释后的P及真实克隆100%位于SLR2、零未解释missing/unplaced/outside；不能仅依赖`_rep`后缀或原NAME数量。

**完整cut与必要原生诊断。** 枚举P所有引脚及DSP外部接口，DSP内部leaf按物理父归属处理；由其附着net追全原生hierarchical segment并归并canonical electrical net。保存全部leaf IN/OUT/INOUT和相连top ports，不只取热点UNION或数据输出。top input可为设计外driver、top output可为load，不能照搬leaf方向规则；常量、时钟、无driver、多driver、双向和unknown都保留。端点至少含NAME/REF/REF_PIN、归一父、组内外、owner、LOC/BEL/site/tile/actual SLR及未解析原因。REF参与pin分类：DSP.C是数据，FD.C是时钟，LUT.I0不能自行判成数据或控制。

覆盖计数须足以发现漏采：S/P及各方向unique pin、未连接pin、segment/canonical net、闭合错误/截断、top/INOUT、missing parent、无/多driver及未放置对象。分别报告unique cut nets、边界load pins、物理driver/load cells、组内外fanout、模块/时钟/实际SLR对及可测空间跨度；矩阵重复贡献不可冒充全局unique数。pre-place空LOC写UNPLACED/UNKNOWN，拟定target SLR2另列，绝不回填成实际位置。原生全局SLL单列；源码256/1120位、net和pin均不等于SLL用量。

保持全部继承时钟下全局setup/hold/PW报告；边界min/max路径按方向与时钟对保留端点、slack、logic/net delay和exceptions，并声明路径条数上限及过滤范围，不能从截断列表计算“完整cut TNS”。阶段对应使用语义及实际对象证据，不仅按net字符串连接。原physopt已有导出未覆盖完整cut时，基线填NOT_MEASURED；本附录不授权追加当前EDA查询。

**CPU准备及修订触发。** A006可在自有目录准备未执行的selector/parent归一、排除ledger、真实站点range生成与readback、完整cut导出/schema/分类/比较、受限timing入口及新AT来源绑定，并做直接相关CPU语法和边界检查。实际资源范围、API通过、热点适用性与迁移收益均待原生证据。发现漏选/误选、DSP父不明或约束冲突，先修复相应边界；若完整cut暴露意外宽payload或共享控制往返，须解释或修订机制，不能继续只引用1120/256。与采样热点无交集/关联会降低当前适用性，但10个窗口不代表全部拥塞。合法执行中时序/接收区压力恶化按真实结果记录，继续合同内完整route，除非触发现有资格/停止条件；失败用于修订下一候选，不增加中途审批。需要FIFO/RTL/IP/pipeline改动时集中修订合同与验证范围，不静默扩大纯放置变量。
