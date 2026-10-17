# E004 R003：下一次布线的架构候选与实施次序

本记录为已完成的架构分析交付。负责人A007；源/时钟/数值/Host ABI冻结，未运行EDA或修改实现。§1–9保留分析与修正过程，当前首选、后备和最终证据以§10–12为准。目标是基于可复算的因果假设选择下一次修改组合，不能保证未经执行的布通结果。合同见[SM008](../../../../../mission/M002_ddr_separation_and_timing_recovery/routability_analysis_contract_2026-10-16.md)。

## 1. 必须同时解释的基线事实

E003 R004 §4、§6–8已逐阶段核验：place与独立physopt成功且完整POST存在；一次默认route自然Tcl/native exit1，245279重叠nodes与248289拥塞失败signals。Phase8未布/部分布线0不覆盖节点互斥合法性。没有失败route DCP、完整route_status或正式routed timing，因此新physopt查询只能解释布局及潜在连接压力，无法重建失败router最终路径。

- 146472/147780 CLB站点被占用（99.11%），但physopt LUT814935/1182240（68.93%）、FF1019698/2364480（43.13%）；这是分散站点占位与逻辑槽余量共存，尚未证明控制集合碎片是主因。
- 先前完整placed拥塞表同时含MLP/DDR区域和Attention区域。MLP/DDR窗口局部URAM或BRAM100%；Attention South/Long Level6窗口列postprocess_store等。失败的top10节点30次/27唯一nets全Attention，仅是工具选择样例，不能外推全部失败网络。
- route早期SLR0–1 estimated demand21886/17280=126.66%、9/12列超1440，最大2997/1440；这是估计需求，不等于physopt实际SLL Used8811/17280。两种口径都保留，不能取较小的一个否定压力。
- 精确MLP repacker LUT驱动控制net已知跨SLR0/1、fanout8201/6192/6145/4652；工具尝试的BUFG优化因placement/routing conflicts跳过。需要减少这类远距控制负载或重组局部性，不能仅把MAX_FANOUT数字调小即称解决。
- 全局control sets22410/295560=7.58%是A006从现有report取得；还需目标层级/低fanout集合、实际packing及坐标才能判断碎片机制。

## 2. 当前区分性假设（排序待R001/R002闭合）

| 候选 | 当前证据与假设 | 可证伪预测 | 反证/限制 |
| --- | --- | --- | --- |
| H1：按row/bank组织Attention写使能、索引译码和读选择 | 源含动态宽写、全幅wave/source mux、postprocess多级选择；局部RTL可能生成跨多个bank的控制/数据扇出 | 同行为重组后目标scope宽mux/LUT负载、最长控制包络及局部拥塞降低；不能仅看源码更短 | synthesis可能把等价结构重新合并；必须核网表及实际place，不将代码bank数量当物理bank |
| H2：MLP浅SRL历史与输出控制局部化 | 显式10752个SRL16E只存depth1/2；控制远跨SLR、四个大扇出有原报告 | 改resetless FF历史需15360声明FF状态位，释放实际SRL所占SLICEM LUT数待映射；如果该区域CLEM/互连压力下降且功能/throughput不变，假设获得支持 | SRL primitive不能1:1当物理LUT；额外FF与CE路由也可能更坏，需目标scope实测；原代码已静态slice、并非通用barrel shifter |
| H3：SLR数据flow/局部控制分配调整 | 真实跨界控制与estimated per-column需求超额 | 同功能候选后跨边界pin/net、数据宽度及per-column estimated demand降低，目标区域资源不超 | 不能把Attention/MLP各塞一个SLR；专用资源位置、总资源和DDR/PCIe固定接口可能使硬Pblock更坏 |
| H4：采用拥塞/SSI导向placement策略 | 当前一次默认布局在高站点占位下仍有局部压力 | 在相同设计/约束下改变一个明确的placement机制，新的局部拥塞/SLL指标与最终route可比较 | directive不改变数据并行度/控制语义，不能消除结构必需连接；具体2025.2支持项和作用范围待A006/主控来源 |
| H5：Attention前端6144→768b逐行读取 | 消费实际上每拍一row，窄化有减少宽级联mux/瞬时连线的潜力 | 在证明数据寿命、加credit/ownership或快照后，接口束宽/跨界负载减少且吞吐符合预算 | 原源在activation_fire立即复用；直接删snapshot必错。新增背压/延迟/双缓冲是实质内部协议变化，暂不列低风险首改 |

## 3. 已排除的轻率方案

- 不因CLB站点99.11%宣称LUT耗尽，也不通过随意降低并行度/位宽/频率解决；用户参数与正确算法保持。
- 不把浅SRL改法称为BRAM化。全幅同时读出和CE历史语义需要明确端口宽度；普通BRAM单端口不能无代价替代数千bit并行历史。
- 不重复“删掉所有data reset”：MLP历史已经resetless；A008确认Attention frontend/context/output/postprocess宽data也已不reset。仅input activation两wave存在异步清零，可另按完整覆盖/valid不可见性分析。
- 不以源码alias或重复wire证明复制已发生；综合可能合并。不得全局DONT_TOUCH或KEEP所有bank来强行制造物理层次。
- 不只优化全局最差PCIe/XDMA setup就声称路由拥塞可解；该时序问题与当前route legality是不同验收维度。

## 4. 待依赖证据及下阶段验收草案

A006单次只读physopt查询将给目标层次资源/SLR/site/BEL、控制扇出/端点包络、样本物理对应与官方help。A008给Attention全幅/局部读写实际并行度、动态索引、reset/valid/source lifetime、可复算规模。每个候选随后明确文件/行、最小修改范围、协议/延迟/资源代价及独立oracle。

未来实施应先做受影响功能/背压/clear/reset/非法序列验证，再综合对照真实映射；在完整place报告比较目标局部窗口、跨SLR连接、control/fanout及资源合法性，继续以真实route结束判合法布通。不能以WNS暂时改善、GR计数0、Phase8零未布或DRC0代替最终route_status。失败也保存DCP/route_status/timing/DRC的工具入口修正独立于RTL改法，必须列入下一次运行流程，但本轮不安装或试跑。

当时阶段记录：execution=analysis running；verdict=candidates untested；最终组合见§10–12。

## 5. 首轮组合的边界草案（尚待物理映射排序）

首轮应由独立的失败产物保留修复、低语义风险RTL局部化和一次有依据的新placement组成，而不是换一串router参数。失败报告修复不改变设计，可单独验证；RTL改法分别留下功能/综合delta，最后才合成一次候选。工具directive是否纳入及选择SSI平衡/分散或logic spread，需等待R001的实际SLR/区域分布，不预填多个同时启用。

### 5.1 MLP浅history原地换映射：精确等价义务

源码入口是`hap_mlp_projection_repack12_to16_s24_history2.sv`和`s32_history2.sv`，实际scheduler实例ROWS16、MATRICES2/1。两个history共10752显式SRL16E，分别只需2/1个已接受输入的历史。可探索用两级/一级resetless FF实现，所有级只在同一`input_fire`时移位，不能每时钟移位。当前拍`assembled_output_c`读取的是时钟沿前的旧history，须用相同nonblocking语义；不增加一个拍或一个accepted beat延迟，不改mask/order/error/ready/valid。

SRL的INIT全0须保持，或对所有合法使用证明启动不可观察；不得为便于初始化给数千payload FF新增reset。当前SRL CE=`input_fire`在reset/clear分支之外，替代时不能不经论证把history shift包进`if(!clear)`。clear/abort后控制重新暖机且历史不能提前用于valid输出；覆盖MATRICES2交错、尾列12→8→4、连续fire、长stall、非法tag/mask、clear与fire同拍。原接口、计数器、输出稳定性和吞吐应逐拍相同。

**收益口径更正：**10752是显式SRL16E primitive/source实例数，15360是候选FF历史状态位，不是物理资源delta。现全设计原生LUT as Shift Register仅9047而SRL16E primitive有10993，表明不能按一primitive一LUT换算；此前基于该假设的LUT下降0.91个百分点计算已撤回，不进入最终摘要。实际释放的SLICEM LUT需R001精确scope/BEL共享占位，实际新增FF/控制逻辑亦需修改后综合；不能直接以源码位数调整全设计利用率。`SHREG_EXTRACT`等阻止重新抽成SRL的局部机制也须核实际工具支持和网表，不能只换Verilog写法后假定已改变映射。

### 5.2 Attention同周期局部化：只承诺结构目标

input的256b×24槽、context的384b×16槽、output固定序列serializer和postprocess局部pair选择可按真实row/bank拆出静态slice与局部译码。目标是使capture_index/pair/valid等信号经本地控制作用于对应bank，减少远距离多负载trunk与嵌套选择；保持原input_fire、output_fire、有效数据、clear/abort和输出stall稳定。由于综合可能将等价译码重新合并，必要判据是目标scope实际高fanout/包络与实现映射改变，不是源码多了generate或alias。不得全局DONT_TOUCH/KEEP以制造无法优化的新障碍。

A008 source facts中的mux2-equivalent数字是选择复杂度记账，不等同FPGA LUT数；将bank重写成one-hot不能默认省掉这些门，反而可能增加one-hot线路与局部控制集合。具体层次边界需R001 physopt证据，避免把本已局部复制的信号再盲目复制。

### 5.3 后备结构变化与为何不混入首轮

| 变化 | 潜在收益（声明结构，不是实测） | 必须先解决的语义/协议 |
| --- | --- | --- |
| postprocess两768b/row合成单bank，K原位RoPE、V直接quant | 理论少12288声明payload位及部分全组copy，可能减局部控制/布线 | 原`rope_read_s24`读projection_pair而`quant_s24`读独立post_group，两个无valid端口可同时观察；合并会改中间可见值。只能在父FSM合法消费范围定义等价，证明pair已读后才写、无回读、Q/K/V互斥、所有stall/clear重入；查debug与测试，保留non-destructive cursor/wrap原测试含义，不删断言当等价 |
| 两input wave共享loader/组装寄存器 | 潜在少6144b activation、512b BRAM读流水和6144b wave选择 | 原wave1 group0预取可长期保持；共享后wave边界重新fill约26拍（待精确测量）。需保持Host192KiB布局、wave/group顺序、反压/计数与吞吐预算 |
| frontend6144b snapshot改768b row口 | 有机会减少6144b两层源选择/复制链 | 源在fire后立即refill；必须增加ownership/credit至row7或独立快照，否则读下一组。需定义延迟、吞吐、source hold和清空协议，不直接删除snapshot |
| 跨SLR边界加内部pipeline | 可分段长线并稳定边界局部性 | 本core100MHz不能机械套用文档>250MHz的三级建议。先定位真实总线；valid/tag/ready/credit及backpressure必须与数据同步，不擅改交易顺序或提高缓冲在途数 |

相关官方依据见[AMD方法笔记](../../../experiment_source/amd_methodology_2025_2.md)：control sets7.58%只刚进入建议减少区；placement通常比routing选择更影响拥塞；全局禁LUT combining可能在近满CLB占位背景下更糟。具体版本help、局部组合比例与目标资源实测未取得前，这些都是有条件候选。

分析过程更正：A006指出SRL原语与物理LUT存在共享/packing，A007已撤回原一对一资源推算，保留历史假设在source facts内供追溯。当前仅采用10752原语/15360候选状态位，实际资源delta待证据。

## 6. MLP输出CE的具体同周期方案（独立于SRL替换）

两个repacker源在78–79/180行定义`output_capacity`、`input_fire`和`in_ready`，193行外层reset/clear分支中没有payload赋值，236–238行在`input_fire && produces_output_c`时写全部payload。因此纯组合写使能必须精确为：

```verilog
payload_write_ce = rst_n && !clear && input_fire && produces_output_c;
```

未来候选只把`out_payload_r`更新拆成16个不重叠row slice：Down每row `16×32=512b`，Gate每row `16×24=384b`；每row一个`LUT1 INIT=2'b10`组合identity buffer输出local CE。只对32个精确标量buffer做必要保护，数据FF/整个row bank与模块层次不锁定；这里32是拟新增原语实例数，不是净物理LUT增量。当前工程可参考`hap_attention_frontend_8row.sv:83–98`已有24个protected LUT1 local-CE模式，但其历史有效性不自动证明新位置也有效。

数据`assembled_output_c`、其静态pass slice、metadata/valid/count/error/order状态逻辑均保持；移出原payload赋值后，每一payload bit只有唯一时序写入owner。保留原`rst_n/clear`资格使payload在reset/clear当拍保持（原payload本来不清零），不得顺手加reset。buffer是组合逻辑，不是控制打一拍，不增加内部或外部延迟。

对应基线精确物理net：`.../u_down_scheduler/u_projection_repack/out_payload_r[8191]_i_1_n_0` fanout8201、SLR0/1 loads4105/4096；`.../u_gate_scheduler/u_projection_repack/out_payload_r[0]` fanout6145、SLR0/1 loads3073/3072。源代码支持这些是大payload更新事件，具体物理net仍可能带少量非payload负载，不能把相减结果擅定为metadata数。目标是global CE驱动16个副本加实际其余控制，local CE每行最多512/384个声明payload端点；真实副本、LUT/FF映射、CE控制集合和SLR端点包络须综合/布局核查。

**配套验证：**旧模块与新模块同输入逐周期比较in_ready/out_valid/所有有效输出及计数/错误；独立按matrix维护append有效列→满16列产出记录的oracle，不只以旧代码作唯一参考。覆盖clear/rst与input_fire同拍、stall时data/valid稳定、同拍消费旧out并产生新out、连续输出、pass/matrix/tag/mask异常。新增同值CE副本不等于新的独立状态，不能造成row更新不一致；用断言所有row CE同值及每行write资格等于原全幅write条件。

**为何需要与C1分开：**SRL→FF改变的是history映射，不能修复仍有8201/6145端点的output CE。S24 depth2替换还可能让history CE终端4608→9216；S32 depth1则6144→6144。故最小候选可优先S32-only或先做这组output CE局部化，S24只有在target映射收益与local-history CE配套验证成立时加入；两种变更各自保存diff和网表delta，不能把全部效应归给SRL替换。

## 7. 受影响回归的具体入口与缺口

本轮没有运行这些测试。未来实施验证复用实际工程入口，不能把source manifest/构建CPU检查当payload功能仿真。

| 变更范围 | 现有入口/可复用覆盖 | 必须补充或确认 |
| --- | --- | --- |
| MLP S32 history/输出CE | `tb/hap_mlp_rebuild_repack_s32_tb.sv`已有独立column映射（12*p+lane→16*record+lane）、超S24范围的S32值、尾16列、长/随机stall、clear后非法序列拒绝 | 该TB line9实际MATRICES=2，而生产Down是MATRICES=1。必须覆盖生产MATRICES1，不能只重跑旧bench；若纯同周期改法，比较全周期ready/valid和有效payload/tag/计数/error，另证明reset/clear同fire优先级 |
| MLP S24输出CE（若纳入） | 同一pass-major规则可用独立按matrix列队列oracle | 测实际ROWS16/MATRICES2、S24符号极值、gate/up交错，不能以S32 bench或builder-source检查替代 |
| input两wave slot-local capture | `tb/hap_tensor24_cohort16_buffers_tb.sv` | 24slot×128group×2wave身份、final-slot→valid同拍关系、跨group stale pending、所有slot中断/clear/新epoch与payload保持；DMA输入镜像位序独立oracle |
| context16×4region capture | `tb/hap_attention_cohort16_local_stores_tb.sv` | 16slot/4096地址覆盖算式与实际BRAM pending/drain执行分开测；clear边沿旧pending写不可见payload行为与父valid保持；slot0/15、两wave/group边界 |
| 保持快照/外围集成 | `tb/hap_projection_core16x16_w8_reuse_tb.sv`、`tb/hap_attention_mlp_production_v5_joint_tb.sv` | 仅选择受影响链的真正集成覆盖，确认source快照/accepted消费及数据/valid/tag同步；已有未变算法单元结果可明确继承，不能冒充新运行 |
| 若以后涉及reset/CDC或新pipeline | `tb/hap_attention_mlp_production_v5_cdc_tb.sv`与当前reset/CDC诊断证据 | 功能回归不替代正式reset/CDC/事务安全资格；新增存储/valid/credit必须定义清空和重新预热，正式安全OPEN保留 |

针对C2静态bank，证明`slot_ce`只在原写条件下对唯一slot成立及所有payload bit唯一owner；对C3输出CE，证明32个本地组合副本与原write条件同值。资源验证先确认新设计真实落到netlist且无RAM→FF爆炸/新黑盒/锁存/未约束端点；时序检查不能因目标是布通而略去。下一次route仍需完整合法终态，任何局部功能/资源改善都不代替该验收。

## 8. 物理比较需保持的口径

SLR0/1负载数4105/4096与3073/3072恰接近两半payload容量，可支持输出CE分布很广；它们不能证明RTL row0–7/8–15恰按该顺序落在两个SLR。row-local CE是一个自然的逻辑owner选择，实际每row端点是否聚集、是否跨界仍应由位置数据判定。没有证据时不指定硬LOC/Pblock或把坐标/row编号当SLR归属。

A006已复核同阶段congestion报告48个Level≥3窗口：Combined LUTs最大34%，12个Level6窗口为6–16%，未出现UG949建议评估禁组合的>40%局部比例。这使全局no_lc不具当前优先证据；不把官方经验阈值误当数学定理，但当前近满站点背景下不额外制造全局LUT/位置压力。

place/physopt比较实际cross nets/loads/SLL Used、每SLR资源/局部区域填充和同范围拥塞；route Phase3才有本次可比的Estimated SLL Demand per-column，不能把此字段提前当作placed已有报告。新的routing legality仍以最终合法终态判定，指标改善只为支持尝试的证据，不是保证成功。

## 9. 新原生扇出证据后的排序更新

A006单次physopt只读查询的`high_fanout_top50.rpt`已返回code0；本查询整体终态及target位置仍待后续。A007独读原报告lines30–39：两个input wave的capture_index[0..4]均为FDCE源，每bit扇出依次6174/6173/6172/6171/6170，十根全部命中；line40 activation_wave扇出6163。MLP既有8201/6192/6145/4652亦全部一致。独立原行/身份见[排序更新证据](physical_rank_update_evidence.json)。这把input capture控制从源码线索提升为真实物理高扇出证据，且与既有route样本多次出现的capture_index相交；仍不代表全部245279节点由它造成。

**当前最小组合倾向：**两wave的24×256b固定slot及48个精确local CE decoder作为首轮RTL主项；MLP两repacker32个row-local output CE作为配套；另选一种有依据的新placement。context64边界暂不强绑（未进top50只说明不在该有界榜单，不能称无压力）；保留所有6144b快照、现有data reset、projection复制和pipeline。S32浅history映射是待精确BEL/区域后选择的小结构项，S24转FF继续后备，避免把一轮扩大为所有候选一起做。

input目标是让每capture_index位主要驱动24个slot decoder输入及实际状态/控制，而非约6170个展开端点；每slot CE只作用于256b固定目的。新native scope只有56个控制集合，现有网表很可能已有槽级CE，故不能断言当前完全没有local CE，也不能把6170+负载全叫CE负载。**改法关键是固定目的slice使256b data直连对应寄存器，将索引对数据选择网络的作用限制在局部写资格；同时核查data steering与CE两类实际负载。** 保留256b输入data仍需送到24个目的这一物理事实，不能称所有广播已消失。若新网表仍是原高fanout展开、protected边界未保留或映射等价，则本分支未实现机制，不因源码变成generate就进入完整route。

## 10. 目标原生资源闭合后的首选与后备

小型原报告、精确行和SHA已独立读取保存在[target_physical_evidence.json](target_physical_evidence.json)。只读查询整体终态及最终位置汇总已在§12闭合；下表是原生基线资源，不是优化后的结果。

| 范围 | 当前原生资源/位置 | 对候选优先级的影响 |
| --- | --- | --- |
| Attention input | LUT18651、FF12341、去重涉及CLB5560、控制集合56，全SLR2 | 十条index各6170+扇出是直接目标；控制集合数接近48个slot，不能用“控制集合爆炸”解释其LUT或全部高fanout。缺每网REF_NAME直方图，不能把18651LUT具体归给D-mux/译码某一类 |
| Attention context/postprocess/output | LUT5044/22870/3947，FF6594/24629/12327；context/post全SLR2，output仅4LUT/2FF在SLR1 | 这些scope需要和input所在区域整体比较；context没有相同强度top50证据，post有rope index3902/3885/3836扇出，可作同周期后备 |
| Gate S24 repack | SRL16E4608、物理SRL LUT2304，SLR0/1各1152；scope LUT7003、FF6245、CLB1693、控制集合10 | 这是当前占位，不是替换后的净节省。双深history会增加候选CE终端，暂不混入首轮 |
| Down S32 repack | SRL16E6144、物理SRL LUT3072，SLR0/1各1536；scope LUT5195、FF8285、CLB2344、控制集合8 | S32-only可解除3072个现有SRL LUT槽的该种用途，代价为6144声明history FF及实际控制；新FF和其他cell可占同site，不能推算回收3072 LUT净值或384个CLB |
| 整Attention | DSP2296，SLR0/1/2=0/337/1959；LUT0/60981/180374，FF0/44043/227673，内部SLL1↔2=4909 | 冻结网表不可能整引擎塞单SLR。全局native DSP Used/Util%为1614/70.79、1875/82.24、1962/86.05；按两位小数舍入区间，每组唯一整数容量均2280，Attention超单SLR容量16个。2280是原字段的可复算推导，原表没有显式per-SLR Available列 |

**首选最小组合已经明确：**（1）Attention input双wave固定slot写/48个精确局部资格边界；（2）Gate/Down两组共32个row output CE组合driver；（3）一个基于本轮位置与2025.2接口证据选择的新placement策略。前两项各自保留功能对照及综合网表delta，满足后才整合新布局。失败取证入口修复独立实施和验证，它不计入布线优化收益。具体首选为§11的SSI_SpreadSLLs，安装版无DCP轻量核验列下一阶段启动前工作；不同时叠加多项策略，也不默认硬Pblock。

S32-only history FF转换为可独立取舍的次选：若首选控制结构已落实而MLP局部SLICEM/CE分布仍构成压力，且独立综合与局部映射显示解除SRL位置限制的收益没有被FF分散/控制代价抵消，再合入候选。现有测量足以确定3072个当前SRL槽，仍不足以预测净LUT/CLB回收或布通概率。S24、context64译码边界、input reset移除不自动随之加入。

### 10.1 保留双bank的postprocess固定pair写，优先于singlebank复用的后备

`hap_attention_cohort16_local_stores.sv:107–127`已有独立`projection_pair_row_r`与`post_group_s24_r`，后者同时有V阶段全768b拷贝和RoPE动态48b目的写。可以保留两个bank和所有无valid观察端口，只把RoPE目的写拆成16row×16pair的256个固定48b slice；pair-local资格为row-qualified `rope_store_valid && rope_store_pair==p`。这256是目的写边界数，不是净LUT成本或必须保护256个原语的结论。

**关键同拍优先级：**原always先执行`projection_post_capture_valid`全bank赋值，再执行RoPE选中48b赋值。同拍两者成立时，选中pair必须由RoPE覆盖，其他15pair仍取得V拼接值。每pair唯一时序owner可表达为`if (pair_rope_write) pair<=rope; else if (projection_post_capture_valid) pair<=projection_concat[p*48+:48]`。不添加reset，不改projection_pair写、read mux/cursor、quant口、数据寿命和所有快照；因此有条件做到逐拍全端口等价，和singlebank只在父FSM合法消费范围等价不同。

此项值得列后备：已有原生rope_output_index0/1/2扇出3902/3885/3836，postprocess全部SLR2且当前LUT22870。须先以pair0/15、每row、同时全写+pair写、游标wrap及无valid端口逐拍对照证明，再看新网表index数据选择/控制负载与局部位置。它只处理目的写；rope_read_pair和quant_row的读选择、48b数据广播仍保留，不能预报全部postprocess压力消失。首轮不把此项加入48+32最小组合。

## 11. 首选placement与有条件替代

**首选只改变`place_design -directive SSI_SpreadSLLs`，后续physopt和router先保持原冻结Default设置。** 这是一项待检验的策略选择，不是已运行或能保证成功的配置。使用新RTL综合后的新布局，不从失败旧布局直接重试router；不安装整套同名implementation strategy，避免其同时改变physopt/router。

A007于本轮实际读取AMD [UG904 2025.2 Available Directives](https://docs.amd.com/r/2025.2-English/ug904-vivado-implementation/Available-Directives)的361–376行：`SSI_SpreadLogic_high`为SSI器件最高程度的逻辑分散，`SSI_SpreadSLLs`在跨SLR划分时给高连接区域更多空间；[同版Implementation Strategy Descriptions](https://docs.amd.com/r/2025.2-English/ug904-vivado-implementation/Implementation-Strategy-Descriptions)366/372行分别说明相关SLL策略有横向分散跨界连接倾向，以及SSI high的大范围逻辑分散目标。所读两页版本栏均明确2025.2、日期2025-11-20，不能用搜索返回的2026.1页面冒充当前安装版本。以上为官方方法定义，下面的排序为本设计证据上的工程推断。

| 选择 | 支持当前排序的事实 | 风险与区分判据 |
| --- | --- | --- |
| 首选SSI_SpreadSLLs | 旧route SLR0↔1估计总需求126.66%、9/12列超额，单列峰208.125%；Attention跨1↔2不可完全消除且多个目标bank集中SLR2。需要给高连接区域留路由空间并改善边界连接分布 | 不保证降低总SLL数量，空间分配也可能挤压相邻DDR/MLP/Attention。place比较目标/邻域占位、端点包络、实际cross loads与固定/新最坏拥塞窗口；route早期再比较每列Estimated Demand。原样或恶化时不能按名字宣称改善 |
| 条件后备SSI_SpreadLogic_high | 如果首选RTL机制已落实、SLL列集中得到改善而SLR内部仍有广泛局部拥塞，进一步分散逻辑具有区分价值 | 三SLR站点均98–100%占用，不能假设有空闲SLR承接整个bank；highest spread可能拉长6144b连接、增加跨界和控制包络。采用此后备须冻结同一RTL，记录首选的反证/剩余问题，单独新批次，不两项叠加或自动扫参 |

`SSI_BalanceSLLs`、全局no_lc、硬Pblock、频率/并行度变化不作为本轮首选替代。此处不是证明SSI_SpreadSLLs一定优于high；基线只有一次默认尝试，下一次成功率无法量化。当前RTL两项的独立综合delta可分清结构是否落实，最终整合布局若无消融仍只能报告组合效果。

A006同一native进程的help取证失败/恢复客户端超时是已知工具证据缺口，不能由官方网页替代为“安装版已核”。下一阶段在加载大DCP和正式place之前，以安装Vivado2025.2无DCP帮助/参数接口核查确切directive、器件支持和入口实际传参；保留回执并沿用资源/无墙钟强停政策。普通轻量核验不需要新增用户批准，也不因本轮缺少native help无限延长只读查询或重开DCP。本轮不执行该工程动作。

## 12. 最终证据闭合与交付判断

R001唯一只读AT001于23:25:10→23:53:35 UTC自然结束，native/监督exit0、stop_reason=null。A007最终直接复算48条query回执（35个code0、13个help失败）、核对6个小输入身份和前后DCP身份记录，独立检查5个原PID/start及supervisor均不再存在；没有重读568MB DCP或控制进程。总体exit0不能代表全部query有效。

52个目标net中原日志27个唯一样本全部找到。10根input index的leaf load数6174…6170与top50逐项相符且全部SLR2；4个MLP控制的0/1负载分布和driver位置得到确认。10个样本INT tile原生get_slrs均SLR2，clock-region范围X0–5/Y12–14。仍没有每net负载REF_NAME直方图或SLR内部端点包络，不能扩大到全部失败网络。

自写BEL histogram把LUT/FF槽全部计为0，与独立native utilization矛盾，**INVALID**；只能保留其去重site计数和已独立核对的原生资源。没有使用该直方图推论“空槽很多”、packing根因或预计CLB回收。当前SRL-LUT5376来自native scope，未被该错误推翻。native help缺口、没有失败route全图和没有候选实测均在最终报告明确保留。

最终独立审核已核主控`optimization_plan.md`的27297 bytes、SHA256 `9b666f60371b07f67284b0ae402fda28ee3e1ae30db8bac243bd03064a7567f3`，未发现阻碍本轮分析交付的实质问题。证据见[final_review_evidence.json](final_review_evidence.json)，完整审核判断见[integration_review.md](integration_review.md)。首选为input48固定slot与MLP32输出CE，加单一SSI_SpreadSLLs新placement，后备按剩余热点选择S32-only或双bank固定pair写；不把80个控制边界称为80个净LUT新增。

execution：分析与独立审核completed；verdict：候选效果inconclusive/未实施；applicability：E003冻结源与成功physopt父点、本文有界源/原生证据；review：A007分析交付审核，无实施授权或用户验收含义。正式route合法性、setup/hold/PW、reset/CDC/事务安全和板卡验收仍分别待真实新实验。A007未运行EDA、仿真或测试，未改生产RTL/XDC/算法/接口，不声称后台持续监控。
