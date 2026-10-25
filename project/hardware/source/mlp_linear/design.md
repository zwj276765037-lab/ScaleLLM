# M006 MLP linear：W0 可实施接口合同

版本：revision 4（有界测试与错误边沿规则补充）；日期：2026-10-24；责任：A021（Astra xhigh）。生产ABI/schema仍为revision 2，生产数值、地址及payload规范不变。
状态：**接口已冻结供 SM026 实现；功能与物理验证尚未完成。**

权威机器定义是本目录 [abi.json](abi.json)。本文件补充其握手、状态与恢复语义；若代码与此合同不同，工程报告具体差异，由架构负责人修订受影响条款。普通实现/TB修复不需逐次审核。

## 来源与适用范围

| 来源 | 本合同采用内容 |
| --- | --- |
| [总体设计 v1.0](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix/PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Design.md)，§6–11、§13–14、§17–18 | format05、REC576、两opcode、DDR1槽、CSR、生命周期、cache、epoch、验证 |
| [实现计划](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix/PRO_plan/ScaleLLM_MLP_Linear_Only_Dual_DDR_Implementation_Plan.md)，§2–4 | 实际源码映射、W0缺口、构建旧根绑定 |
| [M006合同](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix/mission/M006_mlp_linear_only_hardware/contract.md) | 硬件主线、A021/A022写入边界、执行授权与阶段验收 |
| 当前源码基线 `0c0d2cdba00ef8e91cc96e678ca4e0b68c4cda60` | 所有复用核/接口与原数值参考；原设计SHA见abi.json |

本任务根为 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM_MLP_fix`。Attention叶子算法/RTL/宏/CSR/DDR0/时钟CDC行为保持。物理两个MLP逻辑half仍只到DDR1；MLP正常job_clear不触发共享maintenance。格式为定点S24/F16、S32/F16，F16不是FP16。

已有目录作为唯一实现入口：本目录保存设计/结果/schema，RTL留在 `project/hardware/rtl/mlp` 或 `rtl/integration`，测试留在 `project/hardware/tb`。不复制另一份可编译模块树。A021不修改生产RTL、TB或构建文件。

## 1. 冻结模块划分

| 模块 | 放置与职责 | 复用边界 |
| --- | --- | --- |
| `hap_mlp_linear_cache16` | resource_top内；16×448×280-bit单命令A8 cache，单物理读端口 | 借鉴旧Down row BRAM；不改Attention cache |
| `hap_mlp_linear_rec576_parser` | tensor DMA局部；18beat组装、metadata/padding校验、完整group提交 | 新模块，无H32/量化 |
| `hap_mlp_linear_compute16_s54` | resource_top内；锁存opcode/权重基址，GU随机/Down顺序读adapter，共享reader/kernel及输出 | 保留双8×12恢复与S44/S54；禁止自动GU→DOWN |
| `hap_mlp_linear_gate_up_scheduler16_s24` | compute内；旧GU gather/tag/repacker拆出S24出口 | 旧full/serial/GU scheduler源保留历史；生产不例化SwiGLU |
| `hap_mlp_linear_tensor_dma` | production_core内；独立load与store-arm命令、parser、GU/Down记录writer、DDR1 AXI256 | 可复用基础DMA，但新取消/错误行为不能修改Attention共用DMA语义 |
| `hap_mlp_linear_job_control` | production_core内；准入/descriptor、load→arm→compute→drain、完成、ACK、epoch | 与AXI-Lite前端分清AW/W收集、提交结果及状态快照 |
| MLP metadata scheduler/resident | production_core内；scheduler按opcode，resident维持A/B协议 | job_clear只到scheduler；resident只接受受控hard_clear |

所有新本地接口在core 100 MHz域，`rst_n`低有效复位。job_clear为core同步单拍，仅在本地事务排空后允许；payload RAM/宽数据寄存器不要求清零。DDR UI仍200 MHz，复用既有CDC握手/快照，禁止直接把UI busy接到core完成条件。

## 2. 精确端口与握手

通用约定：valid/ready同拍为一次接受；valid高且ready低时payload/标签保持稳定；每条流payload与标签原子传递。下表采用实际建议端口名，局部命名等价调整允许，但位宽/顺序/语义不变。公共状态为 `error`、`error_code[31:0]`、`quiescent`；error及首个code保持至安全job_clear/hard_clear。

| 模块边界 | 端口/位宽 | 接受后的行为 |
| --- | --- | --- |
| cache begin | `begin_valid/ready, begin_opcode[1:0]` | 无owner、无pending、无error时ready；锁opcode和expected_groups；非法opcode可接受并报错，不建立可读cache |
| cache写 | `wr_valid/ready, wr_group[8:0], wr_u8x16x32[4095:0], wr_meta_u24x16[383:0]` | owned且未sealed时可写；接受后核group==write_count且小于128/448；非法不写RAM、报CACHE_WRITE_ORDER |
| cache seal | `seal_valid/ready`；输出`sealed` | ready=owned&&!sealed&&!error&&!wr_valid；接受时计数必须准确，提前seal报CACHE_SEAL_COUNT，不通过降低ready掩盖错误 |
| cache读请求 | `rd_req_valid/ready, rd_req_group[8:0]` | sealed且响应容量可用时ready；ready不依赖地址合法性；接受非法地址报错且不访问RAM |
| cache读响应 | `rd_rsp_valid/ready, rd_rsp_group[8:0], rd_rsp_u8x16x32[4095:0], rd_rsp_meta_u24x16[383:0]` | group/data/meta同响应；允许有界弹性流水，读请求和响应严格按序；停止消费时保持 |
| parser输入 | `in_valid/ready, in_data[255:0], in_last`；开始输入锁存opcode | in_last是整条DMA tensor最后beat，不能连接raw RLAST；只有完整检查过的18beat记录才向cache发wr_valid |
| DMA load命令 | `load_valid/ready, load_opcode[1:0], input_base[31:0], input_bytes[31:0]` | 原子锁存；直到reader/parser/cache完整接受才load_done；错误时按§5排空 |
| DMA store arm | `store_valid/ready, store_opcode[1:0], output_base[31:0], output_bytes[31:0]`；`store_armed` | arm只建本地接收状态，不发AXI写；compute启动前必须已armed |
| compute命令 | `command_valid/ready, command_opcode[1:0], gate_half{0,1}_base[31:0], down_half{0,1}_base[31:0]` | 接受后锁存，单任务只启动对应reader/调度；cache必须sealed、writer已armed |
| GU输出 | `gu_valid/ready, gu_s24x16x16[6143:0], gu_tile16[9:0], gu_matrix, gu_last` | 依次G0/U0…G895/U895；last只在tile895且matrix1 |
| Down输出 | `down_valid/ready, down_s32x16x16[8191:0], down_tile16[7:0], down_last` | tile0…255，last只在255 |
| CSR→job | `submit_valid/ready, submit_descriptor[543:0]`；结果`submit_result_valid/ready, submit_accepted, submit_error_code[31:0]` | descriptor的17×32-bit顺序见schema；VALIDATE后返回结果；AXI B响应不得早于该结果 |

GU旧7-bit请求在adapter零扩展，旧bank固定0，返回高2bit必须0。Down adapter顺序请求group0…447；一个group被Down scheduler接受后才进入下一组，每组服务342个内部12列tile。两adapter由锁存opcode互斥选择，同一时刻不存在两个cache读owner。

cache的quiescent仅表示无写提交、无读pending/未消费响应；sealed且持有数据不妨碍quiescent。job_clear释放owner/valid，但只能在上述quiescent成立时。先发出最后读请求不能释放cache。读响应FIFO必须有明确容量和pending计数，不能因同拍消费/返回覆盖数据。

compute对外保留两条独立输出流，DMA在局部按opcode捕获记录并串行化，避免上层宽8192-bit组合MUX。GU和Down不能同时valid；非法输出类型/顺序/last报OUTPUT_ORDER_OR_LAST。GU局部block-last只作内部校验，不接tensor-last。

## 3. 数据与数值检查

REC576字节布局、little-endian与payload长度以schema为准。row10的24-bit metadata跨第16/17号beat；记录padding16 B及metadata[23:22]必须0。code=0时该row的q[0…31]、zero_point、shift全部0；非零code接受1…255，不能增加code≥128限制。

parser可使用分beat/row暂存，完整记录校验成功前不提交有效cache group。首次格式错误后不再提交任何后续group，但维持读端排空能力。输入payload不带group序号，合法组内容交换/复制由Host packer和端到端参考检测，硬件不能凭数据自称检测此类错误。

activation/weight shift各为6 bit，先零扩展到7 bit相加。非零恢复GU总shift20…44、Down12…44；零code路径及canonical行为保持核定义。guard算术右移与投影末尾half-away-from-zero舍入分开。不得修改S17点积、S37/S45 guard、S44/S54归约顺序、末尾饱和定义。

Host H32、Min/Max A8、ScaleCode和SiLU表逐位复现原整数参考；产品S35差值超过4,269,834,239时不提交DOWN。Host `after_attention`已做residual/RMSNorm，预处理不重复RMSNorm。真实模型工件仍需后续登记本地manifest与哈希，有限fixture不能代替模型证据。

## 4. CSR、descriptor与epoch

schema中的94个寄存器条目及39个错误码是生成RTL/Host常量的输入。所有新action/epoch/ACK/clear写full strobe；普通RW按WSTRB合并，zero strobe无副作用。RO写任意strobe均SLVERR且不变。未对齐或未定义访问SLVERR，读值0；0x378/0x37C读0 OKAY、写SLVERR。0x180–0x240旧telemetry保留地址，其MLP非线性专属计数恒0，其余按原名称从本任务有效计数映射，不虚构旧完整命令活动。

0x110仅保留既有maintenance动作bit1；任何包含旧START bit0的写先拒绝且不执行maintenance，其他保留位拒绝。0x174所有写均SLVERR。0x13C仅允许有效WSTRB合并后结果为0，非0拒绝。owner和metadata窗口保留既有协议，metadata COMMIT额外禁止在Validate/active job/未ACK completion时发生；读取非active bank的加载可沿原协议，但新epoch commit要求所有loading/commit-pending已结束。

17个32-bit descriptor字段从低位依schema排列，总544 bit。CSR配置、Validate候选快照、active descriptor和DONE快照独立。执行中CSR配置可更新而不影响当前任务；ABORT用配置command_id匹配active command_id。command/request ID可为0；buffer_generation和weight epoch必须非0；层0…31、cohort0/1、buffer0…5且buffer//3==cohort。

首版只接受规范地址：slot_base=0x10000000+buffer_id×0x800000；GU input/output分别+0/+0x100000，Down分别+0x300000/+0x400000。长度必须精确；以33-bit加法检查完整local范围<0x80000000。四个权重基址固定为0、0x01C00000、0x03800000、0x04600000，不能把Host aperture地址填入CSR。

epoch提交绑定非零epoch、layer、实际active metadata bank/generation及四基址；必须无active/validation/未ACK completion、无fault/maintenance/切owner、全部MLP通路quiescent、active metadata有效且无loading/commit-pending。提交同一个当前active epoch ID拒绝；Host负责整个run不复用ID，硬件不保存历史集合。

START逐项匹配epoch绑定和实际active bank/generation；无有效绑定拒绝。metadata active bank/generation发生任何变化立即失效旧epoch；job_clear和ACK保持绑定；hard_clear/core reset撤销。Host在同层双cohort两个DOWN成功ACK且硬件排空后才释放层租约，硬件不追踪GU→Host→DOWN模型历史。

START准入按schema的错误码判定顺序执行：非法action/strobe→fault/维护/owner→active/cleanup→未ACK completion→opcode/format/identity→长度/地址→metadata→epoch。首次尚未清除的START/epoch拒绝写ADMISSION_ERROR，后来拒绝不覆盖；ACK/ABORT身份错误只返回SLVERR，不污染该诊断。拒绝不启动任何DMA/计算，不产生completion，不覆盖active/DONE。

Host持MLP控制锁，清并回读ADMISSION_ERROR=0，写descriptor和START，再用有序MMIO读取ADMISSION_ERROR。非0判拒绝；0且读序已证实意味着本次写到达并通过，继而等待busy/completion并检查完整DONE身份。必须同时检查reset_required并在硬件故障时退出。B响应延迟到Validate结束，且拒绝诊断先于B可见；真实XDMA ordered-write/read及SLVERR传播仍须在集成/上板中证实，pwrite返回4本身不证明START接受。

旧0x288–0x29C完成寄存器可作为新DONE的身份别名，op_id仍1；旧status映射成功0、协议1、DDR2、数值3、超时4、abort5。新Host以0x328–0x350为权威。0x114只保留可靠busy/done/error诊断，旧phase不是新phase的权威接口。正常0x2A0 ACK必须full strobe、ID匹配、completion有效、busy=0、quiescent=1、reset_required=0且不在maintenance；其读回仍沿原诊断语义。

## 5. 生命周期、错误与清理

正常序列：

1. Idle接受提交候选进入Validate；只锁候选，不启动工作。合法时给accepted结果并进入Load；非法回Idle，返回SLVERR及admission原因。
2. Load先接受cache begin，再启动input DMA。全部输入接收、parser空且正确组数后请求seal；sealed后进入ArmOutput。
3. ArmOutput握手store arm并确认armed，随后发送compute command。metadata scheduler从compute command fire开始，按opcode发请求。
4. Compute继续消耗metadata/权重/cache并产生输出。compute_done只说明计算侧期望输入/输出和内部队列已退役；不等同DDR写完成。同步保存compute_done/store_done脉冲以支持任意先后。
5. Drain等待metadata drained、cache响应空、kernel/tag/gather/repack空、weight reader及CDC命令/数据/统计快照结束、DMA全部B确认。数量精确且无错才冻结DONE/计数，进入Complete，busy=0。
6. ACK释放DONE valid并发本地job_clear。该clear完成前不再准入新START；resident metadata和epoch保持。该一拍cleanup可返回BUSY拒绝，不得误接收新cache owner。

metadata drained必须独立从请求/交付计数、resident读pending和响应FIFO为空形成，不能依赖command_done先清active，否则会与job完成循环等待。各模块drained汇总进core域，禁止直接用局部busy=0代替真实退役。正常成功quiescence不依赖completion ACK。

错误分类具体码见schema：

| 类型 | 首版动作 | 完成与恢复 |
| --- | --- | --- |
| 准入拒绝0x10xx | 不启动事务，保留首个admission原因 | 没有completion；诊断清除后允许合法重试 |
| 输入padding/reserved/canonical错误0x2001–0x2003 | parser转discard，接收剩余固定输入DMA；不seal、不compute、不arm写出 | 完全read drain后失败DONE；quiescent时ACK并job_clear可恢复，metadata/epoch保持 |
| 输入长度/last错误0x2004 | 在传输计数仍可信时discard至接受的DMA终点；若传输framing失效升级fatal | 不把缺失beat当成功；不可能排空时reset_required |
| cache/meta计数/tag/output顺序/数值0x2010–0x2051 | 锁首错，停止新工作，保留已有事务状态；已接受AXI事务按可能边界排空 | fatal快照、reset_required=1；不能普通ACK清错重用 |
| AXI/reader/metadata错误0x21xx | 保持既有fatal语义；不撤销已接受AR/AW/W；不继续新job | fatal快照、reset_required=1；恢复由原受控maintenance/reset条件决定 |
| ABORT/maintenance abort0x2201/0x2202 | 校验活动ID后停止新job准入；健康的已接受job继续原内部推进直至结束，再走既有受控共享maintenance | 输出整体无效；hard_clear使metadata/epoch失效；排空后失败DONE，可ACK；不是正常job切换 |
| watchdog0x2200 | 默认10,000,000 core周期，从START接受到终态；不清空在途状态 | reset_required，按能否排空走维护；参数0只用于明确有界TB，不能在生产静默关闭 |

ABORT_DRAIN是控制状态，不得因此门控已接受job的内部forward progress；否则会把本可自然完成的命令挂住。ABORT可能等待Attention已接受工作结束，这是异常维护路径的既有系统代价。普通GU/DOWN/ACK均不走这条路径。

DMA实现需保证错误恢复真实可行：输入格式错误时提供discard sink；输出在发AW前保留足够的已验证payload以完成该burst；fault后不再发起新的burst，已拉高但未握手VALID不得撤回。基础hap_axi256_dma缺乏中止接口时，可由MLP wrapper分burst提交或使用MLP私有DMA变体；不得通过异步clear丢弃对端已接受事务。RLAST损坏/reader freeze可能永远不quiescent，必须保留reset_required和未排空状态，不能伪造成功排空。

首个错误码一旦锁存不被后错覆盖；后错严重性可把recoverable升级为reset_required。同拍优先级：硬复位、AXI/reader fatal、协议/数值、输入格式、watchdog、ABORT、成功。fatal进入Fault时冻结身份/首错/当时计数，completion_valid可为1，同时busy/quiescent继续忠实反映未退役事务；ACK被reset_required禁止。这是失败诊断快照，绝不表示tensor或硬件已安全完成。Host保存诊断后再执行明确维护/reset；真正core reset会清快照。

错误边沿的最小确定规则（2026-10-24补充）：已有首错始终保留；仅在尚无首错时按本拍AXI/reader fatal→协议/数值→输入格式→watchdog到期→合法ABORT握手→本拍维护请求→既有abort_pending→成功选择终态码。ABORT/维护与正常DRAIN完成同拍必须依据本拍事件，不能因NBA尚未更新而写成功0；同拍输入错误优先于新ABORT，较早拍已锁ABORT则不能被后续LOAD错误覆盖。多个同级来源由固定组合选择定义，不能依赖多个时序赋值的后写顺序。

活动且尚未终态的任务持续计时，recoverable错误不能关闭watchdog；超时有旧首错时保留该码，仅升级reset_required，无旧首错才用0x2200。可用单元TB缩短timeout验证，无需让整合等待生产10,000,000周期。fatal严重性在Idle、Validate、执行、Complete等阶段均须采集，同拍fatal禁止ACK/新准入；已有未ACK DONE的身份/首错/计数不得再次snapshot，只升级reset_required。Idle fatal不制造任务DONE，之后hard_clear也不能仅因诊断busy=1使用旧active_descriptor补MAINTENANCE_ABORTED；只有真实已接受且尚无DONE的任务才允许补该快照。

paired global_freeze或data conflict立即阻止新MLP准入并保持真实故障诊断，不能用局部idle伪装quiescent。paired错误可映射WEIGHT_READER_ERROR=0x2110，data conflict映射协议/COMPUTE错误0x2030；旧首错不覆盖。健康SHARED模式下MLP的正常quiescent仍按MLP本地compute/cache/metadata/tensor/reader状态判定，不无条件AND全Attention+MLP的paired_core_quiescent；全局故障通过明确error门强制非quiet。全局维护仍必须满足既有双域/双引擎真实屏障，framing丢失/global_freeze不能以soft-clear假装恢复。


| 清理对象 | job_clear（正常ACK后） | 受控engine hard_clear | core reset |
| --- | --- | --- | --- |
| cache owner/valid、命令FIFO/tag/计数/error | 清，先确认无pending | 清，先满足维护屏障 | 清 |
| cache/payload RAM内容 | 不清 | 不清 | 无语义要求 |
| resident metadata valid/generation | 保持 | 撤销 | 撤销 |
| epoch绑定 | 保持 | 撤销 | 撤销 |
| DONE快照 | ACK已释放valid，数据可保持 | 未ACK的valid/身份/首错/计数全部保持；活动命令无DONE时先锁MAINTENANCE_ABORTED | 清 |
| ADMISSION_ERROR | 保持 | 保持；仅0x374合法清除可清 | 清 |
| Attention状态 | 不影响 | 遵守已有共享维护 | 原系统复位 |

受控engine hard_clear仅在既有维护屏障建立安全复位边界后清live fault/reset_required、active局部协议及epoch；不能取消AXI对端已接受事务。未ACK的DONE保持原错误及计数，live故障清除后busy=0、quiescent=1、phase=Complete，允许身份匹配ACK；job_error仍反映非零DONE_ERROR。若尚无DONE但有active命令，先锁MAINTENANCE_ABORTED再清live。admission诊断跨hard_clear保留。不能安全建立屏障的故障须保持reset_required，真正core reset后的恢复属于新会话初始化。

新生产resource/core可采用`*_linear.sv`独立源图、保持模块接口外壳名字并仅由新manifest选择；不得同时编入新旧同名模块。此方式保留旧生产文件及旧测试基线，生产选择仍须证明MLP非线性实例消失。

## 6. 计数与联合预算

`DONE_INPUT_BYTES`=完整合法cache提交记录数×576，不能在parser仅组装完成尚未cache接受时计入。`DONE_OUTPUT_BYTES`=OKAY BRESP确认的burst字节数；故障时即使非0也不是有效tensor。`JOB_RECORD_COUNT`=输出writer接受的完整记录数，与B确认字节独立。所有计数/周期32-bit饱和不回绕，终态后至ACK稳定。

LOAD_CYCLES覆盖Load；COMPUTE_CYCLES从compute fire到compute_done；STORE_DRAIN_CYCLES从arm到store/全部排空，可与compute重叠；STALL_CYCLES为有效执行期任一规定流valid&&!ready的周期并集，每周期最多加1，不能相加冒充总延迟。具体资源和性能推导见[results.md](results.md)，不以目标时钟声称实际收敛。

## 7. 工件兼容与构建身份

权重布局标识固定 `0x57344635`（ASCII W4F5），它与运行MLP ABI v6分开。严格接收旧artifact schema2且mlp_abi恰为0x00050000，内部只读归一化为该weight layout；保留原manifest和全部权重bytes/hash，不把旧ABI字段与新硬件控制ABI直接比较。

新导出schema3用 `mlp_weight_layout_id=0x57344635`替换顶层`mlp_abi`，其余顶层字段及嵌套大小/哈希校验保持严格。未知schema/旧ABI变体拒绝。runtime证据另记control ABI、linear ID、buffer layout、weight layout、原artifact schema/manifest SHA；旧运行evidence不自动升级为新任务通过。

新构建采用新根新输入manifest，保留旧M003冻结manifest/G2证据。create/build入口显式选择新模块图，移除MLP非线性层次及旧宏别名，保留Attention选择。旧C01/SwiGLU约束选择器退出新生产图；剩余metadata/kernel约束按实际层次重新验证，空匹配/过宽匹配失败，不能绕过身份检查。

## 8. 首次工程验收点

cache/parser可按本合同直接实现；下一集中审核读取工程真实结果：全16行REC576、row10跨beat、零code/保留位/padding、128/448 seal、随机/顺序重放与持续背压、错误后完整read drain、job_clear保持metadata。随后审核GU/DOWN共享核及控制集成、同epoch四任务、最后B阻塞、错误ACK、epoch切换、SHARED隔离。

纯诊断XDC清理不改变有效约束时可复用已完成综合DCP：须保留父成功终态/receipt、DCP和生成IP身份，严格绑定新旧manifest及精确差异；只删除已确认的literal打印不等于更改约束。任何RTL/IP/ROM、shape、源图或有效约束变更均不适用该豁免；候选CPU守卫测试不能替代真实父链校验，物理质量仍独立判断。

独立oracle不得从新RTL控制逻辑生成gold；旧小fixture只能证明其声明范围。缩小参数TB必须标明仅局部覆盖，生产全形状计数/尾列/真实计算须另有对应证据。不得因阶段普通修复新设逐次放行门。

## 9. 真实生产层次的有界整合测试合同

2026-10-24集中决定：主整合TB使用GU输出128列、Down输出64列；**只缩输出N，实际计算仍包含GU的128个K组和Down的448个K组**。此前N128/N32或Down仅4组的独立compute尝试保持原冻结身份，不重标成此合同通过。两个opcode是独立线性任务；缩小GU输出不能直接生成完整Down输入，TB分别提供合法16×4096与16×14336输入及独立整数gold，不声称完成整层Host SwiGLU链。

### 9.1 形状与统一推导

`INTERMEDIATE_COLUMNS`在新增linear层次表示GU输出列数N_GU；`HIDDEN_COLUMNS`表示Down输出列数N_DOWN，不能据名称反推另一opcode输入维度。主TB显式设置128/64及`ENFORCE_PRODUCTION_SHAPE=0`；生产默认14336/4096及enforce=1。

| 项目 | 通式或固定边界 | 主整合TB |
| --- | --- | --- |
| GU输入/Down输入 | 16行；K组128/448；REC576与9-bit group保持 | 73,728/258,048 B，全部组参与计算 |
| GU输出records | 2×N_GU/16，每条768 B | 16条、12,288 B；tile0…7，G/U交错，last仅U7 |
| Down输出records | N_DOWN/16，每条1024 B | 4条、4,096 B；tile0…3，last仅3 |
| GU权重/metadata records | GU输出records×128 | 2,048条；padded metadata65,536 B |
| Down权重/metadata records | Down输出records×448 | 1,792条；padded metadata57,344 B |
| GU内部计算事务 | 2×ceil(N_GU/12)×128 | 2,816；最终投影22个12列pass |
| Down内部计算事务 | ceil(N_DOWN/12)×448 | 2,688；最终投影6个12列pass |
| 分块尾列 | GU按48列分块，Down按48列分块 | GU尾32→12/12/8；Down尾16→12/4，与生产同余 |

合法小shape仍要求N_GU为正32倍数且≤14336、N_DOWN为正16倍数且≤4096；metadata地址宽保持18/17，cache group宽9，GU tile宽10和Down外部tile宽8保持。内部Down窄tag显式零扩展到8位，不能静默截断。所有派生记录/事务数须正数、地址容量足够、满足reader八事务打包约束。

### 9.2 参数传播与生产保护

| 文件/实例 | 实现要求 |
| --- | --- |
| `rtl/integration/hap_attention_mlp_production_core_linear.sv` | 唯一整合shape来源；暴露N_GU/N_DOWN/enforce默认，记录数和bytes作为派生常量；传resource、job、tensor及三个metadata模块 |
| `rtl/integration/hap_attention_mlp_resource_top_linear.sv` | 原样传N/enforce给compute，cache/parser不缩；固定外部端口宽度 |
| `rtl/mlp/hap_mlp_linear_compute16_s54.sv` | `HIDDEN_GROUPS=128`、`DOWN_GROUPS=448`；默认Down组数改为448，移除非生产检查中`DOWN_GROUPS==INTERMEDIATE_COLUMNS/32`耦合，仍核两输入组数；向GU/Down scheduler与shared kernel传正确派生数 |
| `hap_mlp_linear_job_control.sv`、`hap_mlp_linear_tensor_dma.sv` | 同一GU_OUTPUT_RECORDS/DOWN_OUTPUT_RECORDS/enforce；输入长度固定，输出长度/最后tag/接收上限/终态计数统一派生，不留下1791/255/1792/256硬编码分支 |
| `hap_mlp_linear_metadata_scheduler`、`hap_mlp_weight_meta_resident_ab`的linear文件、`hap_mlp_meta_dma_loader` | 三者GU count/depth统一2048、Down统一1792；生产默认229376/114688；PRODUCTION_SHAPE接enforce，地址宽18/17保持；loader仍每条224bit+32bit padding，bank完整性和commit精确计数不放宽 |
| `hap_mlp_linear_axil_control` | CSR字段、版本、动作和身份不变；TB通过真实CSR写小shape output_bytes，长度由job按静态参数核；六槽canonical地址、权重四基址及epoch约束不变 |

生产guard为默认1，所有新增参数化入口都保留固定生产值检查。缩小配置只能由明确TB实例/仿真顶层传入；不新增CSR、宏环境变量或运行时旁路关闭guard。生产create/build入口仅选择默认参数，并在新manifest记录生产参数绑定与源码SHA；工具可公开实际elaboration参数时另记实际值，未公开时明确标static_bound_source及actual_elaboration_parameters=unavailable，并保留实际top/defines/compile-order/BD可见属性；脚本前置检查enforce=1、14336/4096/128/448及全部派生counts，失败即停止。不能仅依赖可能被综合忽略的initial `$error`；负向elaboration用例应证明小shape+enforce1被拒绝。禁止编入新旧同名模块双份源图。

小shape不是第二种板卡ABI；abi.json保持生产规范，不把12,288/4,096 B等测试长度加入Host合法集合。允许工程用localparam消除派生参数的外部覆盖；若保留可覆盖参数，必须检查跨层一致性。已开始的冻结尝试不热改；新参数化源码须新attempt与哈希。

### 9.3 真正整合的必要路径与错误恢复

TB例化真实linear production/resource层次，使用真实CSR router/control/job、metadata DMA/resident/scheduler、REC576/cache、双8×12共享核、weight frontend/CDC/双DDR专属路由、tensor DMA。BFM仅替代外部AXI-Lite主机、DDR存储器与时钟/复位源；不可force内部ready/quiescent/done、替换算术核或直写resident RAM取得成功。Attention若使用stub须单列范围，不能据此宣称SHARED隔离通过。

metadata先经外部DDR映像和真实CSR LOAD/COMMIT生效，再commit epoch。输入q/W4随group、lane变化，row/column code/shift包含不同合法非零值；独立gold按既有整数恢复/归约/舍入计算。必须覆盖两opcode、完整16行、GU交错/两侧尾列、输出背压与末B延迟、同epoch四job和匹配ACK；元数据交付数、全部K组cache读、writer接收和B确认bytes分别核对。

恢复整合必须使用真实路径状态，至少完成以下行为：

1. 中段坏REC仍排空输入，已提交前缀计数准确，无seal/compute/AW；失败DONE后身份ACK及同epoch合法重试成功。
2. 正常任务最后B持续阻塞时无成功DONE、无job_clear；释放B后正常完成。ABORT/维护请求不能门控已接受任务前进；既有Attention工作若存在仍须排空。
3. 注入framing完整的tensor BRESP错误：锁首错/身份/计数、reset_required阻止ACK；已接受AW/W/B退役，禁止新burst，真实维护屏障能安全释放本地失败owner。hard_clear保留未ACK DONE和ADMISSION_ERROR、撤销epoch/metadata，再允许匹配ACK；重新加载/commit后新job成功。
4. 注入reader/AXI framing损坏或无法排空：保留reset_required和真实非quiescent，不回撤VALID、不伪造soft-clear成功；既有paired leaf已global_freeze时只允许受控core reset/new session恢复。此类结果单列，不与第3项可排空故障混为一类。

合同冻结时生产core的`mlp_clear_safe`同时依赖job !busy、compute !busy、scheduler !active和tensor !busy；FAULT job busy又依赖paths_quiescent，而tensor STORE/compute可能等hard_clear才退出。这是需第3项动态闭合的明确风险。实现应区分“正常任务完成”与“故障后可安全复位”：可排空故障先停止新工作并持续退役已接受传输/CDC，再按真实transport安全边界放行维护，不要求已不可能取得的成功compute_done/完整输出计数。不能简单删除busy条件或把paths_quiescent接常1；本地尚未提交的无效算术/记录仅在安全屏障后丢弃。若屏障不可建立，保持fault并采用第4项恢复，不能声称第3项通过。2026-10-24阶段复核：AT028已用真实BRESP/discard/transport维护链完成第3项，AT031以当前控制修订完成第4项；适用范围和未变数据路径复用见[results.md第五次阶段审核](results.md#第五次有界阶段审核sm026受影响范围验收)，该历史风险在受测N128/64、K128/448范围获得动态闭合，不扩展为全部故障与生产全N证明。

### 9.4 证据适用范围与成本

主整合内部事务5504，相比128/32且完整K的4160增加32.3%；metadata共3840条/122,880 B、权重有效payload共983,040 B、输入331,776 B、输出16,384 B。这是静态工作量，不是实测时长；scheduler/BFM每周期速率不能代替真实kernel成本。工程按原资源协议连续实现/修复/回归，不增加逐项架构审批。

此TB可证明相同生产模块连线、真实控制/数值/传输与恢复在受测静态形状下成立。它不能替代默认形状联编、全shape GU/Down调度与DMA计数/4KiB/尾列证据、完整14336/4096输出的数值、生产metadata容量/高地址、整层Host链、SHARED并发、吞吐/资源/时序/CDC/上板验收。即使小shape与独立全shape模块均PASS，也不能标为全shape整板端到端PASS。

## 10. 下一版GU-only：已授权实施，Down移Host

日期2026-10-24。用户明确“可以开始进行”，本节状态为**AUTHORIZED_FOR_IMPLEMENTATION**，不改变前述当前冻结v6合同。有效完整机器合同为[abi_gu_only.json](abi_gu_only.json)，包含完整base字段与v7有效语义；原增量draft仅保留历史。当前abi.json、R004/R005输入与证据链保持原样。新图必须使用新manifest/输出目录，不能将当前失败实现或历史功能证据重标为GU-only通过；新实现验证结果仍NOT_RUN。

独立[GU-only v1.0](../../../../PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md)为已授权的下一版主文档，本节作为摘要保留；完整GU-only schema冻结供生成器使用，当前v6合同不受影响。

### 10.1 目标与DDR边界

FPGA执行Attention和MLP Gate/Up；Host执行原SiLU、H32/A8预处理和**完整Down矩阵乘法**，之后进入原S32/F16输出、residual及下一层流程。全部32层保留，权重字节、format05数学和模型结构不变。双8×12 GU核、16row cohort、GU14336列、hidden4096、128个输入group与core100/DDR200 MHz不变。

Attention确实只访问物理DDR0、MLP只访问物理DDR1。[constructor](../../vivado/scripts/create_mlp_linear_board.tcl:576)分别把DATA/WEIGHT_C0连接d0 SmartConnect/MIG，把MLP_DATA/WEIGHT_C1连接d1；[dedicated reader](../../rtl/integration/hap_axi512_dual_engine_dedicated_read.sv:3)将Attention的两个逻辑half合到DDR0，将MLP两个half合到DDR1。`gate_ddr0_base`等旧逻辑half名称不表示GU访问物理DDR0。分DDR消除了两个引擎争用同一外部DDR通道的设计关系，但两组AXI/CDC、计算和metadata仍在同一FPGA使用INT节点、CLB及跨SLR连线；route node overlap是静态布线资源冲突，不是运行时AXI地址冲突或证据表明DDR分离失效。新版本继续此DDR分工，不额外承诺引擎独占某SLR。

### 10.2 删除范围与可量化边界

下表来自当前AT004整板Synthesized层次，行之间不重叠；是**被裁对象当前占用**，不是新综合资源净差。

| Down专属对象 | LUT | FF | RAMB36 | URAM | DSP |
| --- | ---: | ---: | ---: | ---: | ---: |
| Down scheduler（已含S32 repack） | 13947 | 16880 | 0 | 0 | 1 |
| 两branch S54 accumulator合计 | 41830 | 16038 | 192 | 0 | 0 |
| 两Down输出队列合计 | 3230 | 12356 | 0 | 0 | 0 |
| Down metadata bank0/1合计 | 1461 | 2124 | 0 | 224 | 0 |
| 不重叠合计 | **60468** | **47398** | **192** | **224** | **1** |

另移除compute Down FSM/activation顺序读adapter、GU/Down输入选择、Down tags/tile路径、tensor 8192bit serializer与Down长度/末尾判断、metadata DMA/scheduler Down阶段和resident对Down计数的等待。S32 repack当前8290 LUT/8282 FF已包含在scheduler行，不能再加一次。两个GU metadata bank仍各224 URAM；若Attention80不变，总逻辑需求由752降到528 URAM，但仍以新综合/布局结果验收。

cache深度448→128，逻辑容量2,007,040→573,440bit，减少71.43%；每row280bit宽读端口与BRAM最小配置粒度意味着当前64 RAMB36**未必减少**，第一步保持16row group响应带宽/延迟协议，不为了宣称BRAM收益偷偷串行化读取。默认只接受group0…127；9bit外壳可保留，但高位非零必须拒绝，存储实际深度为128。

双8×12共享乘法阵列3072 DSP本来已经被GU/Down时分共用，移除Down不自动节约其中1/3。GU仍需S17 dot、ScaleCode恢复、S37 guard、128组S44累加和S24输出。实施先删除Down专属模块并固定GU mode；随后将GU专用内核/队列收窄到37bit，消除S45额外存储、Down模式tag和移位范围12…19分支。37bit专化须单独对当前GU核作逐位对照，不用“输入都合法”替代数值/溢出/停顿验证。其额外LUT/FF收益目前不报价。

本次方案形成期间已读到[R005原生crossing报告](../../vivado/reports/m006_slr_AT001_physopt_slr/crossing_global.rpt:118)：保存的Physopt DCP中，Down repack `input_fire`扇出6185，SLR1/2 loads为3113/3072；tensor `output_error118_out`为8196、4100/4096。下一版删除Down重排/宽serializer确实针对当前跨区宽控制结构。与此同时GU projection tag仍有6149/6148，GU repack `input_fire`仍4650，故删Down不能等同解决全部宽控制。它们是保存Physopt的实际网，不是最终失败route网的冲突排名，更不能由扇出数预测成功率。工程按同一合同整理的[依赖方案及实际BD边证明](../../../E013_mlp_linear_only_hardware/experiment_source/gu_only/engineering_scope.md)只作实施支撑，不替代本节及机器草案。

### 10.3 GU-only运行接口

草案采用MLP_ABI_VERSION=`0x00070000`、MLP_LINEAR_ABI_ID=`0x4D4C0002`，CAPABILITIES=`0x1D`（GU/cohort16/REC576/GU_INTERLEAVED，DOWN bit1为0）；numeric_format、weight_layout和buffer_layout=1保持。Host先匹配ABI/能力再提交，旧v6 Host不能静默使用v7。新构建只消费新schema生成物，当前v6生成器和104输入不热改。

仅opcode1合法，opcode2/其它值在START准入返回既有BAD_OPCODE=`0x1010`，无DMA、metadata fetch、cache owner、compute或completion副作用；首ADMISSION_ERROR、在途身份与未ACK DONE规则继承。544bit descriptor字位置保持；Down两个base字改保留零，非零候选报BAD_ADDRESS。CSR0x134/0x138/0x170读0，仅WSTRB合并后结果为0的写可成功，非零SLVERR无副作用；Down metadata计数与Down saturation旧RO地址恒0，不伪造活动计数。其它协议、错误优先级、fault升级、真实排空和受控恢复保持，不因删Down弱化Attention隔离。

GU输入仍73728 B、128×REC576；输出仍1792×768=1376256 B，G0/U0…G895/U895，last只在最后Up。六槽及GU input/output偏移不重排，旧Down偏移保留未使用；移除Down DMA后不能把未实现流默认为成功。两个GU weight half基址仍0和0x01C00000，均在DDR1。

metadata仅两个GU A/B bank，每bank229376条；DMA只读取7340032 B（32 B/条），scheduler每GU交付229376条，Down count永久0。commit只检查GU完整性和原有generation/owner/quiescent条件，不等待不存在的Down phase/count。epoch绑定epoch/layer/实际GU active bank+generation/两GU基址；metadata active身份变化、hard_clear和reset撤销，ACK/job_clear保留，ID不复用规则保留。旧四基址descriptor中的Down项只作保留零检查，不进入新的权重绑定。

完整32bit opcode必须等于1，高位非法不能先截2bit；仍继承fault/busy/未ACK的高优先级拒绝。cache须表示count=128，先校验9bit group再截7bit地址。weight metadata每条有效28 B、尾4 B padding；新loader显式检查高32bit零，首错0x2120使目标bank无效/禁止commit并排空已接受AXI。inactive预取错误不直接改active bank字节/generation，但全局MLP metadata fatal阻准入、撤销epoch资格和升级reset_required。无accepted GU不得造DONE；真实active GU按首错/fatal规则给失败DONE；未ACK DONE保持内容仅升级reset_required。受控恢复后重载/commit并发布新epoch，不删除owner响应。

FPGA层租约在双cohort GU均成功、匹配身份ACK、通路排空且GU输出已复制到Host自有buffer后可释放；不再等两个硬件DOWN。Host必须另持不可变的layer-specific Down权重句柄和中间buffer租约直到CPU Down及后续消费者结束，不能因FPGA切层覆盖CPU正在读的数据。中央runtime保持同cohort层依赖，独立CPU Down任务可与另一cohort/GU重叠；不得在backend阻塞等待未来epoch。每层每cohort只有Attention+GU两个硬件命令，32层双cohort为128，MLP命令为64；Host Down是依赖图任务，不能伪装成硬件completion或消耗旧DOWN command计数。

### 10.4 Host Down的精确数值与工件

复用[现有Host预处理](../../host/scalellm_mlp_linear.py:266)产生的同一q/zero-point/code/shift，只是无需再向DDR1上传Down REC576。SiLU ROM hash、S48乘法舍入、S35 H32、min/max/ScaleCode以及范围检查不变；after_attention已有RMSNorm，仍只执行一次。Down权重从原`mlp_down_c0/c1/meta`逐字节验证后解码，按[原record规则](../../model/verify_scalellm_real_mlp_artifacts.py:84)group-major、每组256个16列record拼合，保留低/高nibble符号与两half的列对应，不重新量化或修改export manifest。

每个(row,column,group)：`dot=sum32((q-zp)*w4)`检查S17；`raw=dot*activation_code*weight_code`检查S33；非零总shift为12…44，左移或算术右移对齐F24后检查S45；按group0…447累加并检查S54；最后且仅最后作half-away-from-zero右移8位，再饱和S32/F16。零code贡献0，canonical与metadata/padding检查仍严格。边界参考见[mlp_fixed](../../model/mlp_fixed.py:127)，但其ROWS=8 fixture不得直接当16row整层实现。

先提供独立Python整数oracle与blocked int64实现对照；标量oracle仅跑有界输出列/完整448组/边界，全shape用高效独立整数参考，不将0.94G MAC纯Python运算作为每次回归。合法点积/恢复/S54范围均可由int64精确容纳，禁止使用FP32/TF32 GEMM冒充逐位等价。原权重manifest schema2/3严格验证和数值/布局身份不变，runtime v7不是权重版本；Down虽不装入FPGA，Host仍必须验证、持有并使用该层Down工件。每cohort Down约939,524,096整数MAC，CPU缓存/线程/内存开销尚未测量；不得承诺吞吐不变。每cohort可省原Down input上传258048 B及S32下载262144 B，总520192 B传输，但新增CPU计算可能成为主要成本。

### 10.5 连续实施顺序与退出条件

| 阶段 | 文件责任与实作 | 必须交付/退出条件 |
| --- | --- | --- |
| G0 新图与合同 | A022建立独立GU-only manifest/构建profile；本目录draft作为新版本输入，保留v6历史文件 | 显式v7/caps/shape；新图源闭合，无旧同名模块双编；当前R005只读输入不受影响 |
| G1 Host精确Down | Host/model负责人实现独立oracle、W4/meta解码、blocked int64和runtime CPU节点；A022协调文件所有权 | 448组/16row/列边界与负数移位、半值舍入、S54/S32边界逐位对照；真实层工件验证；CPU用时/内存实测，失败不继续下一层 |
| G2 先裁Down专属硬件 | A022新GU-only compute/resource/production、metadata loader/scheduler/resident、tensor/job/CSR，cache128 | 无Down schedule/accum/queue/repack/metadata bank/serializer实例；GU counter/metadata/last精确；DOWN拒绝零副作用；ACK/fault/maintenance回归 |
| G3 GU内核专化 | A022新GU-only dual/local/slice/lane变体或严格generate分支；保留原核做oracle | GU guard/queue37bit、无Down mode/tile/shift12路径；双8×12/3072DSP结构不变；与v6 GU逐位对照，包含backpressure/clear/tail |
| G4R 硬件整合 | 真实GU-only生产层次TB和board入口 | 依赖G0/G2/G3及独立gold；GU逐位、故障/排空、Attention边界、生产shape和新源身份闭合 |
| G4H Host系统 | Host Down、runtime依赖/租约、residual及32层链 | 依赖G1及接口；两cohort层依赖/权重租约、命令数/身份与错误退出正确；与硬件主线独立推进 |
| G5 同阶段物理检验 | A022沿现有单重EDA资源协议综合/实现，不复用有语义变化的v6 DCP | 依赖G4R，不等待G4H；新实际层次/资源、SLR/route/timing/DRC/CDC独立验收，不预判收益或布通 |

G1和G2可按所有权并行推进，G3随后验证；G4R通过即可启动G5，不因完整Host32层/吞吐未完成阻塞硬件。首次A版静态删Down/GU专化与后续B版GU locality改造分开留证据，按新综合作轻量预算，不预设branch迁区或盲用旧CE分组。普通修复连续执行，不新增逐项批准。若CPU Down尚慢，先保真再做等价整数优化；若GU-only仍拥塞，依据实际新热点调整，不把DDR独占当SLR隔离保证。独立方案/完整schema已授权实施，本代理本轮只有合同收束，验证结果仍NOT_RUN。

## 11. GU-only已实施映射与阶段适用范围（2026-10-24）

本节记录实施状态，不修改§10或独立方案的数值/接口合同。有效生成输入是完整`abi_gu_only.json`（SHA256 `318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a`），历史draft不参与生成；v6 ABI与旧失败图保留。各次原始结果及本次独立核查见[results第十五次审核](results.md#第十五次审核gu-only-g1与g4r已完成部分)。

| 已实施范围 | 当前代码/入口（相对hardware） | 本次可接受证据 |
| --- | --- | --- |
| G1精确Host Down | `host/scalellm_mlp_gu_only.py`、`*_artifacts.py` | 全16×4096、K448的int64结果与独立group-major参考65536值一致；224坐标Python大整数oracle；原exporter实际record解码/strict manifest/hash检查。限合成输入，真实模型工件仍待验证 |
| G4H任务/传输支撑 | `host/scalellm_mlp_gu_only_runtime.py`、`*_backend.py` | FPGA/Host租约分离、复制→ACK→真实backend quiescent条件、层依赖与故障保留；26数学/运行图加16实际adapter方法的fake-transport CPU测试。应用Attention/residual/RMSNorm回调与真实32层执行未验收 |
| G2缓存/输入 | `rtl/mlp/hap_mlp_gu_cache16.sv`、`hap_mlp_gu_rec576_parser.sv` | 128深度/9bit先验址、非法128/256不别名，坏record全drain、prefix/末记录commit背压；AT006/007 |
| G3真实37bit内核 | `hap_a8w4_gu_group32_lane2_s37.sv`、`hap_a8w4_gu_slice8x12_group_s37.sv`、`hap_mlp_gu_dual_slice16x12_s44.sv`、`hap_mlp_gu_compute16_s44.sv` | AT004旧GU逐周期控制/错误/停顿与512数值+在途clear；AT012真实双8×12、N128/K128、4096独立gold输出。无S45 guard存储/mode队列；保留S17/S33恢复、先扩展再移位、S44累加 |
| G2新控制与传输 | `rtl/integration/hap_mlp_gu_{job_control,tensor_dma,axil_control}.sv` | AT013完整U32 opcode拒绝/owner/首错/timeout/ACK单位；AT016完整73728B输入、1792条输出和末B/4KiB/错误屏障；AT023真实CSR/16种WSTRB及mock job结果；AT019真实production的准入/坏REC/ABORT/BRESP/framing恢复 |
| G2 metadata | `hap_mlp_gu_meta_dma_loader.sv`、`hap_mlp_gu_metadata_scheduler.sv`、`rtl/mlp/hap_mlp_gu_weight_meta_resident_ab.sv` | AT018真实三模块32条加载；AT024真实production N32/K128中idle/held DONE/active GU三种padding fatal及drain/维护/重载重试，active身份和代表地址字节保持 |
| G0/G4R/G5图 | `rtl/integration/*_gu_only.sv`、`vivado/manifests/mlp_gu_only/`、`m006_gu_entry.py`及`*_mlp_gu_board.*` | AT019真实N128/K128整合；AT026完整N14336/K128/enforce1 production展开/存储及复位通过。AT025测试guard遗漏FAIL保留；constructor/新原生综合网表和物理另验 |

metadata故障实现采用两层状态：resident只废弃失败inactive目标，active读路径继续服务已接受计算；production把该故障升级为全局MLP fatal，job撤epoch/阻新准入，保留已有DONE或给真实owner失败DONE，计算输出可discard。安全维护仍需真实weight/metadata/cache/compute及AXI transport排空，普通job_clear仅清MLP任务路径，resident/Attention不受普通ACK清除。单位mock quiescent不能替代真实生产故障证据。

G5依赖保持为：有界真实N128/K128整合与故障/CSR闭合、完整N14336/K128生产elaboration，以及已通过的生产全长度模块证据；不新增全N×32层长仿真要求，不等待G4H真实模型应用链。新综合后必须实际核Down scheduler/S54 accumulator/Down queue/S32 repack/Down metadata实例缺席、GU两branch/3072 DSP、GU metadata448 URAM、96个lane的37bit接口；cache128由绑定RTL和实际elaboration证明，不从BRAM primitive512深反推逻辑容量或收益。

上述功能依赖已由本次AT019/023/024/026及先前模块证据闭合，当前状态为**G4R_LIMITED_PASS**，可按授权连续进入G5。AT026只修TB实例enforce0→1，未改生产RTL或放宽断言；G1/Host接受范围仍限合成数值与fake transport，真实模型工件/32层应用不冒称已通过。所有历史失败和各阶段适用范围见results第十五次。

新版原生综合资源及已完成层次/clock已获得下述限定观察，SLR/route与最终timing/DRC/CDC仍未通过验收。旧六条复位CDC的24级探针只覆盖其自身；旧R004另两条XDMA `user_reset`至d0/d1 gate `arststage` CLR的CDC-11没有因此获准豁免。新报告须逐来源判断同步器/复位合同或实施必要修复，保留原critical与新证据；不得用未布局时序或旧图结构检查替代最终物理验收。G5沿已授权普通修复/运行连续推进，无新增逐次审核停点。

G5同阶段整板资源已实测为679997 LUT、892475 FF、643 BRAM tile、528 URAM、5374 DSP；相对v6减少86081/61662/192/224/1，详见[results第十六次](results.md#第十六次审核准备gu-only与v6同阶段资源比较)。shared核3072 DSP与GU metadata448 URAM原生确认，Down禁止层次0，cache仍64 RAMB36。AT007整次原FAIL保留：96lane存在，但guard pin选择器未取得有效位宽；同SHA DCP的修复查询资格由A022连续处理，不能以已有功能37bit证据代替此综合网表项。实际core/DDR clocks为10/5/5 ns；pre-opt530无clock、554内部未约束及6条CDC10均与旧同阶段准确对象一致，须由新post-opt和最终物理证据闭合。面积下降不构成SLR或route成功保证，本次不改变冻结接口/数值合同。

AT011后续资格已闭合上述综合网表项：同SHA DCP原生逐96lane核两channel×两entry×37位真实guard FDRE，共14208个、无缺位/重复/额外位。rebuilt边界原端口改名，故采用绑定原生funcsim实测名称后的完整存储对象集合；不放宽37bit要求，也不只凭RTL文本或单lane样本。receipt及30工件/102输入身份已核，结构/clock/六链24级限定通过；原AT007/009失败与旧分析报告的FAIL/PENDING保留。当前为**SYNTH_STRUCTURE_QUALIFICATION_LIMITED_PASS**，可连续进入正常opt/物理；新post-opt、SLR/route及最终时序/DRC/完整CDC尚待，详见results同节资格增量。

R008实际post-opt进一步达到**POST_OPT_DEBUG_RESET_LIMITED_PASS**：0黑盒，冻结530/554目标全部存续且clocked，六链24级结构保持。两个限定XPM scope各1个真实FDRE/D及clock、对应10ns Max-DPO coverage已记录，valid/ignored报告尚缺，保留残余PENDING；coverage百分比不是当前真实寄存器漏约束率。该阶段证据不替代最终全局时序/CDC，也不构成SLR/route成功，详见[results第十七次](results.md#第十七次有界审核gu-only真实post-opt及两xpm-scope)。正常place/route按既有授权连续推进，无新增审核停点。

R008新Placed实测SLR0/1/2站点83.75%/98.28%/97.14%，而LUT槽45.44%/61.80%/59.44%；全板逻辑资源下降并未使局部站点自动宽松。实际branch1主要SLR0、branch0主要SLR1、Attention主要SLR2，GU metadata448 URAM跨三SLR168/168/112；旧位置不能套用。宽FIFO/capture控制fanout和BUFG候选跳过已有日志证据；本批拥塞报告最高Level6的三个代表窗主要列Attention postprocess/right2/KV，GU branch0/paired_weight/W4/gather在Level5窗，局部硬资源可达100%。报告列项比例不是因果份额，仍不据此判唯一根因。只记录B版locality/跨区及局部硬资源预算候选，不改本轮冻结图；新Placed不与旧Physopt及不同-packthru Total LUT直接相减，详见[results第十八次](results.md#第十八次有界归因gu-only-placed站点压力与实际模块分布)。

新增Physopt后五资源/scope表与Placed数据相同，native明确无setup违例、netlist未改；保存DCP和六报告身份已核。同Physopt旧站点独立基线→新CLB总140388→137518，仅减2870（2.0443%），SLR1只减780而SLR2增1696；Logic+Memory归一化LUT减11.3391%、全局SLL减15.3362%，均不能换算局部拥塞改善率。新congestion自身仍为Placer Final Level，旧另用min_level3，表行数不可比；当前route连续执行且终态尚待。本增量仅记录实际实现结果，不修改冻结架构或提前签物理通过。

R008四组十条Route35-462已按冻结RTL映射为Attention固定81920的group_count位14/16及GU固定229376的位15/16/17，两half各一套。payload reset为0、接受命令后置位，故只证明同轨迹冗余，不证明实际网表常量化或路径可豁免；四scope的10 ns bus-skew/Max-DPO有效约束仍在。原生端点/driver及实际覆盖分类保留PENDING；两SMC可选valid/ignored四报告须以最终stage_quality catch或真实工件判断，缺文件不能记作ignored=0。详见results第十九次，本次只补实施状态，不改协议、约束或当前物理流程。

R008已实际达到**ROUTE_LEGALITY_PASS**：routed.dcp SHA `cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4`及来源锚/102冻结输入独立核对一致，1687352条routable nets全部fully routed、0routing errors，原生verification及route_design成功。Phase14摘要setup +0.002 ns/hold +0.010 ns仅为已见阶段结果；最终完整timing/check_timing/DRC/CDC、末图guard/clock及十bus-skew路径/四SMC catch仍分别待核。该状态不提前提升为G5全部通过，分项及后续增量见results第二十次。

上述待核项已有正式终态增量：R008自然native0/0survivor/输入无漂移；正式setup/hold/pulse失败端点全0、最差+0.002/+0.010/0 ns，no_clock/内部unconstrained0，末图96lane双37位/Down0/3072DSP/448metadataURAM/10-5-5ns身份保持。DRC0 Error/Critical；CDC仍六CDC10/两CDC11及vendor/FIFO警告，按准确复位/跨域结构分类，未全局豁免。原quality FAIL保留，明确来自三个外部reset IO缺省delay与四次可选报告参数冲突；PERST详细路径已有接收端False Path，但不代表外部复位协议验证完成。DPREG-7的内部P反馈条件已在3072个真实OOC定义中排除，末图两个代表与十bus-skew/两reset链/两SMC补证合入单次只读查询。GU-only实现及合法route已完成；“已施加内部STA”不包含被异步例外切掉的绝对数据延迟，AT002已发现下节所列真实约束覆盖缺口，故尚不能称G5全部闭合。外部reset/板级仍单列，不用“未布通”泛指这些缺口。

## 12. R008同物理图的CDC约束收敛合同

**状态：AUTHORIZED_FOR_IMPLEMENTATION；修正后资格NOT_RUN。** Root已明确将AT002发现的Max-DPO优先级缺口按现有硬件授权收敛。原102输入、AT001/002及routed.dcp `cc34f49b…c7cc4`不变；不改变RTL、10/5/5 ns时钟、握手或reset语义。工程由A022连续实施，新增结果另存，原quality FAIL不重标。

**最新交付顺序：先生成工程验证版bitstream文件，再继续本节约束收敛。** 用户最新明确“不能先生成bitstream吗”，Root据此授权从原已合法route、已施加同步域STA通过的`cc34f49bef612472367f7d273596d09dede15128d3b72a2708507e4c6d6c7cc4` routed DCP生成`.bit`；取代此前“修正后资格通过才生成文件”的安排，不以尚未闭合的Max-DPO或外部reset覆盖新增文件生成前置审批/测试。A022仍唯一EDA owner；若AT002辅助只读查询尚在运行，按用户最新优先级收束、保全其PARTIAL与原始结果后生成文件，随后继续下述约束修正，不把PARTIAL标PASS。

该`.bit`必须标为**工程验证版，约束覆盖未完全闭合**，绑定原DCP完整SHA、102源身份、实际生成命令/工具日志、原生终态及文件大小/SHA；不得引用尚不存在的“修正后资格”回执。保留原quality FAIL，随文件列出Max-DPO被异步clock group覆盖、必要SMC端点结论尚待、外部reset协议/板级未验证等边界；不据文件存在宣称G5全部通过或板卡可用。生成过程保留工具原生检查，不降级DRC或添加任意delay/waiver以强行成功；若原生生成失败，保留实际失败并按已有授权处理。**本次仅生成并交付文件，不下载、不配置板卡、不进行上板/GPU验证。** 约束修正后如需另生成合格版本，须使用其独立DCP/资格身份与另名工件，不能覆盖或重标本次工程验证版。后续实际交付已见[AT003回执](../../../E013_mlp_linear_only_hardware/experiment_results/runs/R008/attempts/AT003_preliminary_bitstream/delivery_receipt.json)：80159259 B，SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`，保持上述工程验证范围，约束修正仍未由此通过。

四个准确scope为`u_compute/u_attention/u_weight_frontend/u_command{0,1}_cdc`和`u_compute/u_mlp/u_w4_frontend/u_command{0,1}_cdc`。AT002已证十个告警D由共享真实FF驱动，四组bus-skew分别1.072/0.652/1.364/1.084 ns、满足10 ns；但逐D timing均为Asynchronous Clock Groups及Slack inf。厂商`xpm_cdc_handshake.tcl`按DEST_SYNC_FF=2、DDR period=5 ns产生10 ns Max-DPO与bus-skew；RTL源数据锁存在请求发出时保持，目标经两级请求同步后capture。这支持原10 ns预算，不允许以总线位间偏差替代绝对延迟要求。[AMD 2025.2约束优先级](https://docs.amd.com/r/2025.2-English/ug903-vivado-using-constraints/Exceptions-Priority)明确clock groups覆盖Max-DPO而不覆盖bus-skew；`-reset_path`不能越过clock groups，2025.2的`set_clock_groups`也没有`-allow_paths`。

最小修正和验证范围如下，先在保存routed图的独立内存副本完成，无依据不重综合/物理：

1. **来源与零差异重放。** 绑定AT001自然终态、原DCP SHA、AT011父链、102源及AT002原生对象。由同一已布线图导出完整有效XDC，先做不改内容的`reset_timing`及完整`read_xdc`重放对照；核clock/生成关系、case analysis、uncertainty、例外、同步域setup/hold/pulse及route身份一致。该官方命令只重建内存时序视图，必须主动重读完整约束；不以旧综合XDC代替route后真实约束，不清理原报告。[UG835 reset_timing](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/reset_timing)
   - **AT007导出非幂等的精确处理。** 只读CPU比对已定位717条实际约束中714条在临时`set`变量按定义scope/query归一后逐序一致；仅`host_split/inst/m00_nodes/m00_r_node/.../gen_mem_rep[0/1/2].inst_xpm_memory`的三条原有5.000 ns Max-DPO由scoped动态query变为root显式pin/cell名单。新增3条`set`不是新增约束，但不得据此忽略三条差异。预冻入口在同一session的重放前、重放后分别求值原式及显式式，逐条保全`-from/-to`实际对象的CLASS、绝对NAME、数量及双向差集；原scoped wildcard与显式残余列表取真实对象并集，不能只比残余名单或仅在重放后的状态互比。所有显式名字必须准确解析，源/目标集合前后相同、无缺失/新增，且原序、5.000、`-datapath_only`和其他选项不变，才允许这三条以原生对象集合身份替代文本序列化身份。其他714条及最终scope保持严格比较；仅端点集合内部顺序可规范化，不能排序约束执行顺序。变量解析限于已冻结的纯查询定义，不执行从运行输出注入的新代码。实际对象存在与例外端点合法性分开记录，原有Invalid/ignored诊断不能因对象集合相等而消失。该证明只接受序列化等价，后续50clock、完整STA指标/同域极值和物理身份门仍须通过；任一集合或时序差异则在修改用户group之前停止，不能以clock相同代替零重放资格。
2. **仅替换一个用户group的语义。** 定位`board_clock_domains.xdc`的PCIe派生/DDR0/DDR1三域全切，其他vendor内部group和非目标约束保持。DDR0↔DDR1继续原隔离；PCIe派生域↔各DDR域采用原有有向clock-pair限制下的精确终点补集，令原cut集合仅扣除受检数据路径。不能粗删所有clock groups，不能把两异步域当同步域分析，也不能靠路径分段绕过优先级。
3. **本固定图采用through遍历点补集。** 四scope动态D为34/34/35/35，共138，常量D按原生driver另列。为避免`all_registers`未证明完整包含clock-gating CE，本次允许批量取全部primitive的非clock leaf输入作为遍历点全集`I`，每个原有向PCIe派生域→DDR域采用一次`-through`集合`I − T`，并保留原`-from/-to` clock限制；`T`为该域准确目标D。这里组合输入是路径遍历点，不冒称时序终点。反方向和DDR0↔DDR1隔离保持。该构造只在以下实物断言成立时等价于“原cut减准确目标路径”，任一不成立则失败并细化集合，不放宽断言：
   - 逐138个动态D均为正确目标clock的FDRE，唯一leaf driver是同scope、正确源clock的`src_hsdata_ff` Q，直接net连接，无BUF/LUT/其他primitive输入中间点；源C/目标C确为clock pin且不在`I`。不能由已核十个count位外推其余128个D。
   - 目标数据路径与最终所有through集合交集为空。若另加top output/inout driver集合以覆盖外部输出边界，必须验证它不包含任一目标launch Q或其他目标路径点；只从`I`减D不够。直接FF Q同时驱动top output时须细分，禁止用这个额外集合把目标重新切掉。
   - 对所有非目标原cut路径，捕获输入D/CE、clock-gating CE、同步/异步控制、RAM/DSP输入或外部输出边界至少一个点仍在through集合内。按类别核实际集合包含关系，不能仅打印类别数量后写完备；有效入向INOUT、被工具标作clock的特殊控制pin等须明确纳入或实证本图不存在相应遗漏。双时钟RAM/宏的关联由原有向clock clamp保持，不能因cell兼属两个clock而新切同域路径。
   - 目标集合去重/计数/逐名差集正确；非目标仍cut、目标真实finite Max-DPO，以及前后clock interaction/未约束/同步域检查共同验证。因为所有新false-path均限制在原本已cut的clock pair内，不得扩展到其他pair；对于任一目标若发现组合中间点，该直连专用证明立即失效。
   - **同一载图内的分类适配。** AT004实测`all_registers -data_pins`有32个对象未被当前输入谓词覆盖，尚无名字/角色证据；不得猜测它们是clock或output。[UG835 all_registers](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/all_registers)未承诺data/clock/output查询集合互斥，单项成员关系或`IS_CLOCK=1`不是排除真实capture的充分依据。新入口在启动前冻结完整决策树：先批量收齐两个DDR域各类别差集，逐名保留owner/ref、REF_PIN_NAME、DIRECTION、IS_CLOCK及data/clock/output/async/CE成员关系；有界导出必要原生library pin/实际clock角色，关闭或flush证据后再处理，不在首个数量不符处丢失对象名字。
   - 决策分为`ADD_EXACT_CAPTURE`、`EXCLUDE_PROVEN_NONCAPTURE`、`UNKNOWN`。真实入向data/control/async capture按准确pin加入through，即使泛化谓词漏掉它；纯launch output必须有方向、输出成员及primitive/library角色支持，且仍检查外部输出边界；纯clock传播/时钟输入必须同时有实际clock和primitive/library专用时钟角色证据，不能用`CLK*`名称、clock集合成员或IS_CLOCK单独判断，更不能将CE/CLKEN等控制误排除。混合角色、缺属性或无法解释的对象保持UNKNOWN，在任何时序约束修改前终止。不得以“只差32个”为由跳过包含门。
   - 分类后重建同一补集，记录原集合、精确新增、已证非capture、UNKNOWN及最终包含关系；UNKNOWN必须为0，所有准确目标D仍排除且完整目标路径/输出driver交集为空。规则中所有可执行分支、界限和失败行为随入口源一起冻结，实际对象/分类为运行输出，允许在同一原生session继续零差异重放及资格步骤；不在活跃session热改脚本、动态加载后写规则或放宽断言来避免重新载图。这样已知工具分类差异可一次处理，真正未知语义仍保留失败证据，普通修复无需新增用户审批。
4. **恢复真正生效的预算。** 四scope保留厂商10 ns Max-DPO和bus-skew，起终点为实际FF/pin集合、含合并后的源；每个动态D均有实际max路径、finite slack、10 ns datapath-only requirement，不能仍由clock group/false path覆盖。需覆盖所有138动态端点及相关min/max角落，报告缺路径/重复/超范围即失败。bus-skew仍单独报告，不以Max-DPO代替偏斜检查。
5. **SMC不得套用直连证明。** 仅`d{0,1}_smc/.../gen_fifo_req.inst_fifo_req/gen_xpm_memory_fifo.inst_fifo/gen_mem_rep[0].inst_xpm_memory/xpm_memory_base_inst`各一真实`doutb_reg_reg[0]/D`。vendor广泛`*doutb*reg*`集合含非法LUT对象，整条报告标Invalid endpoint不自动证明实际D失效。AT002保全的d0最差一条`-to D`路径为同域5 ns Setup、slack +4.076 ns/data0.865 ns，不证明异域Max-DPO生效；d1未采。首次修正目标仍仅138条握手路径，SMC原cut保持。必要时在同资格副本按准确异域源clock限定`-from`检查真实D及原10 ns预算；若存在组合路径需要放开，不能只从`I`扣该D，因为其中间输入仍会触发false path。须先列完整目标路径/共享节点，再改用按真实捕获终点划分的补集或等价精确路径分区，证明共享组合节点不会造成其他路径意外暴露；不能静默扩成140目标、删整段组合cone或对该D的全部来源添加新例外。仍只修受影响实际接口，不改其他XPM memory预算。
6. **资格退出条件。** 对修正副本重做受影响STA/exception覆盖、clock interaction与CDC差异；全局timing summary/check_timing证明同步域和非目标cut未回退，目标绝对延迟及skew真实通过。保留reset IO的原1/2缺省delay及原Critical/Warning分类，不能为了清计数加waiver。核cell/net连接、LOC/BEL/route及合法route计数不变后才可保存另名“约束修正后”DCP/receipt；它不能沿用原DCP SHA或将历史FAIL改成PASS。若出现真实负余量，先报告准确受影响端点与差值，再由工程按普通修复范围处理，不预先重跑全物理。
   - **DCP重存与物理身份分开。** AT008原→zero的六内部DB成员均改变SHA，部分长度显著变化，不能归为仅容器页眉，也不能据此断言place/route改变。先保全zero→qualified的六成员实际对照；全同只直接证明这两个快照的相应成员相同，不自动补上原→zero桥。同DCP/同工具、相同9340项Unisim转换及严格timing-only的命令/约束来源链支持受控派生，50clock/STA相同仍不等于全图配置身份。不得将不透明二进制字段任意剔除、靠汇总计数/少量路径一致，或只把比较基准改成zero来宣布原bit已获新资格；活动入口现有硬门和实际FAIL保持。
   - **需要绑定原bit时的有界完整证据。** 若其他修正资格已通过而原→修正副本的全图身份仍无完整证据，优先从该副本另名生成一次仅供等价取证的bit，保持原bit及其回执不变，不重综合/物理、不下载板卡。比较同器件、同工具和原生配置属性下的完整配置数据payload逐字节相等；按`.bit`实际封装字段和长度解析，原AT003的e字段从151 B起、80159108 B，完整覆盖至文件末。保留并比较器件/tool/UserID等元数据，容器日期/时间或文件名差异单列；不能只截sync word后某片段、只比FDRI帧/CRC，或忽略配置中的AXSS/USERID/启动命令/CRC等任何字节。厂商[UG570](https://docs.amd.com/r/en-US/ug570-ultrascale-configuration/Configuration-Bitstream)指出配置流包含配置命令和数据；[USR_ACCESS](https://docs.amd.com/r/en-US/ug570-ultrascale-configuration/USR_ACCESSE2)还可带硬件可见时间戳，故“时间戳”不能笼统豁免。只有完整payload相同才可用`CONFIGURATION_PAYLOAD_IDENTICAL`把该副本的时序资格关联到已交付原bit，不冒称DCP内部表示逐字相同。若不同，先保全准确差异和配置属性，不能为达等价而改属性；此时才决定是否需要规范化全图原生逻辑/位置/连线证据或真正新版本交付，不能默认百万对象扫描或重生成替代文件。该取证为既有授权范围内的条件性后续，不是当前运行的新停点或逐项审批。

这是四握手及必要两SMC的明确收敛范围，不证明其他被原global group切掉的vendor多位路径已有绝对延迟保证。若资格差异暴露同一替换影响的其他接口，必须列为剩余对象，不能以IP名称自动豁免或把新增false path当修复。外部reset协议/真实板卡仍按既有边界独立验收。
