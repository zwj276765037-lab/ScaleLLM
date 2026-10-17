# M002：面向下一次合法布通的优化方案

主控整合，2026-10-16。**详细分析已完成；本文件交付优化设计与下一次验证计划，不是优化实施或布通报告。** 本轮不改生产RTL/XDC/IP，不跑新的综合/布局/布线。执行边界见[SM008合同](../../../mission/M002_ddr_separation_and_timing_recovery/routability_analysis_contract_2026-10-16.md)。

## 1. 结论与证据范围

当前有可操作的优化方向，但尚不能保证下一次布通。下一轮应改变已定位的资源映射和连接结构，并重新布局；仅延长时间或在同一失败布局上重试默认router缺少足够依据。E003已正常计算至自然失败，不是被时间上限截断。

**当前最强的新证据是Attention双wave的10根capture_index位，每根实际fanout6170–6174，全部进入全局top50。** 这些控制也出现在失败节点样本中，已把具体源码结构与真实物理负载对应起来。首轮RTL主项应为两wave固定slot写入/局部译码，配套MLP输出CE分组；context复制、浅SRL替换是否同时纳入须分别证明必要性。

必须分别处理MLP局部资源/高扇出控制、Attention宽数据选择/局部连接、跨SLR分配及流程取证。先选不改变算法、接口和周期行为的最小组合；需要改数据所有权、增加延迟的窄接口方案保留为明确的后备设计。

本轮报告的“位数”“mux2等效数”是源码可复算规模，不是LUT/FF综合结果，更不是可以按比例换算的全设计布线降幅。候选收益未经实施验证。

## 2. 固定基线：究竟失败在哪里

原始来源：[E003工程总报告](../../E003_m002_full_implementation/experiment_results/engineering_final_report_2026-10-16.md)、[E003物理审核](../../E003_m002_full_implementation/experiment_results/runs/R004/architecture_review.md)、[R001现有证据](runs/R001/existing_evidence_inventory.json)。

| 指标 | E003事实 | 对决策的含义 |
| --- | --- | --- |
| route终态 | `route_design`自然exit1，19065秒；245279重叠节点、248289拥塞失败信号 | 这是合法性失败。Phase8未布/部分布线0、自动DRC0均不能覆盖节点重叠失败 |
| LUT / FF | 814935/1182240=68.93%；1019698/2364480=43.13% | 尚有逻辑槽余量，不能直接称全器件逻辑耗尽 |
| 占用CLB站点 | 146472/147780=99.11%；各SLR99.86/99.09/98.39% | 几乎所有可用位置都已接入设计；需要看实际局部填充、连接密度与专用资源，不能凭此推断唯一根因 |
| DSP / URAM | 79.69% / 78.33%；SLR2分别86.05% /85% | 可移动空间受专用资源分布限制，不适合随意把整个引擎塞进单个SLR |
| control sets | 22410，按2364480/8容量计7.58%；原生另报28860未用寄存器位置 | 全局刚进入官方建议减少区，未证明控制集合碎片主导。明细BEL loads与FF数是独立口径 |
| 早期route SLL需求估计 | SLR0–1为21886/17280=126.66%，9/12列超额，单列峰208.125%；SLR1–2为83.81%，4/12列超额 | 跨界存在分布压力；不能用实际placed SLL约51%/55%否定估计，二者口径不同 |
| 拥塞/冲突样本 | 布局拥塞表含MLP/DDR与Attention；失败日志top10节点的27条唯一net均属Attention | 同时保留两组线索。有限样本不能代表全部248289条失败信号 |
| 最后正式时序 | physopt WNS−1.290ns/TNS−762.165ns；WHS−0.620ns/THS−2150.556ns；core约0ns打印精度 | 即使下一次合法布通，也仍需独立完成setup/hold、CDC/reset签核 |

本轮只读physopt的目标模块测量如下。CLB是scope内去重涉及的站点，可与其他scope共用；父子scope和相邻scope不得相加当全芯片独占占位。

| 目标scope | 物理LUT | FF | 涉及CLB站点 | control sets | 实际SLR位置 |
| --- | ---: | ---: | ---: | ---: | --- |
| [Attention input](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_AttInput.rpt) | 18651 | 12341 | 5560 | 56 | 全SLR2 |
| [Attention context](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_AttContext.rpt) | 5044 | 6594 | 2395 | 21 | 全SLR2 |
| [Attention postprocess](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_AttPost.rpt) | 22870 | 24629 | 5159 | 289 | 全SLR2 |
| [Attention output](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_AttOutput.rpt) | 3947 | 12327 | 4146 | 69 | 除4LUT/2FF在SLR1，其余SLR2 |

四scope均无LUTRAM/SRL。Input只有56个控制集合，却有10条6170–6174扇出索引网，支持优先处理动态写译码/控制分发；不是全局control-set爆炸。未导出每条index负载的REF_NAME分类，不能断言全部端点都是D-mux或FF CE；56个控制集合也不能用来宣称现网表没有局部CE。下一次须分别比较index在数据选择/译码/控制端的负载，核实固定slice数据直连和slot资格是否真的替代了宽动态目的选择。

[Attention总体分布](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_SLR_Attention.rpt)为LUT 0/60981/180374、FF 0/44043/227673、DSP 0/337/1959（SLR0/1/2），其内部SLL1↔2使用4909；因此Attention主要是SLR2及与SLR1连接的局部问题，不能用MLP的0↔1优化代替。

控制集合原报告的BEL load合计1089753，经[独立口径复算](runs/R001/BEL_load_accounting_reconciliation.json)，等于1019696个FF Distribution加70057个LUTRAM/SRL原语；另2个AND/OR计入CLB Registers形成1019698。该明细不能当1089753个FF，按CE/SR来源分桶也不能冒充实际负载层级。

本轮唯一只读AT001于2026-10-15 23:25:10→23:53:35 UTC自然执行完成，native/监督退出均0、stop_reason=null；无残留进程，单EDA锁已可取得。原DCP后SHA保持不变。48项query中35项code0、13项help失败；总体退出0不等于全部查询有效。详见[R001终态与输入完整性](runs/R001/attempts/AT001_readonly_physopt_diagnostics/postrun_integrity_facts.json)。

本轮查询也保留缺口：自写BEL填充直方图的正则未处理带site前缀的BEL名，虽query code0却把LUT/FF槽计成0，该直方图INVALID，不能用于任何packing结论；原生utilization/SLR/SRL槽数不受影响。native help重定向及同实例恢复未成功取得帮助输出，下一阶段做轻量接口核验。本轮不为这些缺口再打开第二次DCP。

原日志10个冲突INT样本的原生位置查询均落SLR2，clock-region覆盖X0–X5、Y12–Y14；这与Attention目标scope吻合，仍不代表全部245279重叠节点或248289失败signals的空间分布。

E003没有失败route DCP和完整route_status，无法重建最后的全量冲突图。本轮查询的是成功physopt父点，SHA256为`c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91`；不能将其说成失败路由现场。

## 3. 候选机制与修改边界

C编号仅标识候选；执行优先级与最小组合见第5节。

### C1：MLP浅历史由SRL改为无复位FF

位置：`project/hardware/rtl/mlp/hap_mlp_projection_repack12_to16_s24_history2.sv`与`hap_mlp_projection_repack12_to16_s32_history2.sv`。来源：[R003源码事实](runs/R003/mlp_shallow_history_source_facts.json)。

S24为4608条两次accepted输入的历史，S32为6144条一次accepted输入的历史；源码共显式实例化10752个SRL16E。候选使用9216+6144=15360个FF保存等价历史，目标是释放SRL占用的SLICEM LUT；SRL只能映射到SLICEM，SLICEM本身也能做普通逻辑，新FF可使用更广的CLB位置。10752是SRL原语/源码实例计数，不能视作10752个物理LUT：原生报告全设计Shift Register LUT为9047，而SRL16E原语为10993，已有非一对一映射。15360是候选历史FF状态位；真实净LUT/FF变化和可回收SLICEM位置必须由目标层次映射与新综合测量，不预报资源百分比或整体布线降幅。

保持每次`input_fire`才推进，S24按两次accepted输入历史、S32按一次历史取值；保留SRL原有INIT语义或证明有效事务前不可观察。不能增加异步data reset，也不能把当前独立于clear/reset分支的SRL CE误改为受其抑制。保留输出容量、mask、matrix/tag、错误检测和背压下payload稳定性，纯原语替换不增加周期。防止综合重新提取SRL的属性只作用于这两组历史，不全局禁用SRL。

本轮原生[Gate报告](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_MLPgateRepack.rpt)与[Down报告](runs/R001/attempts/AT001_readonly_physopt_diagnostics/utilization_MLPdownRepack.rpt)已确认二者都横跨SLR0/1、无SLR2：Gate scope总LUT7003、FF6245、涉及CLB1693、control sets10，4608个SRL16E占2304个SRL-LUT槽（两SLR各1152）；Down scope总LUT5195、FF8285、涉及CLB2344、control sets8，6144个SRL16E占3072个SRL-LUT槽（两SLR各1536）。合计5376是当前实际SRL槽数，不能直接作为未来净LUT或CLB节省。Down-only确实触及3072个SRL槽，但不能解决SLR2的Attention输入问题。

两处不能按相同风险处理：S32深1替换为6144个FF，历史CE逻辑端点仍为6144；S24深2替换会将4608个SRL的CE端点变为9216个FF端点，原input_fire已跨SLR且扇出4652，可能加重控制压力。因此最小候选优先S32；S24须先配套局部CE或取得综合后扇出不恶化的证据，再纳入。

关键预测：真实网表目标scope内SRL减少、FF增加，所在区域SLICEM/控制连接压力下降。若FF被迫分散、CE跨界负载增大或拥塞转移，则不因LUT下降而接受。

### C2：Attention按slot/row组织捕获和选择，保留现有快照

来源：[R002源码与协议分析](runs/R002/rtl_routability_analysis.md)、[可复算事实](runs/R002/rtl_evidence.json)。input两wave的activation共12288声明位；单wave按24个256bit slot捕获。顶层有wave选择和input/context选择两级6144bit mux，frontend接收时再快照6144bit，然后按768bit行送Hadamard。context由16个384bit slot拼成6144bit。postprocess按16行组织，两组768bit/行共24576声明位。

[本轮原生top50报告](runs/R001/attempts/AT001_readonly_physopt_diagnostics/high_fanout_top50.rpt)实测：两个wave的capture_index[0..4]分别为6174/6173/6172/6171/6170，driver为FDCE；activation_wave为6163。定向对象查询复核这10根index的leaf loads数量与top50相符，全部在SLR2；52个目标net取得结果，日志27条唯一样本net全部找到。十根index与失败capture样本的对应支持优先修改input目的写。要求新网表中每根index的主要负载变成24个slot decoder和少量状态逻辑，而非扩展到几千个payload相关节点；数量级下降是该局部机制的验证目标，不是布通保证。

最小明确改法：`hap_tensor24_buffers.sv:95`的变量目的写改为每wave24个固定256bit slot，使每个payload数据片段直接接对应256bit读数据并由slot资格更新，双wave共48个局部译码边界。context的`hap_attention_cohort16_local_stores.sv:305`可改为16slot×4个96bit region，但没有同等物理证据前作为独立备选，不把64个边界自动加入首轮。原BRAM延迟、index/valid/clear状态机和6144bit快照均保留。同拍局部CE为原write资格与slot等值译码的合取，不给控制额外打一拍；特别保留context在clear边沿旧pending可能写无效payload的原语义。

普通generate重写可能综合回原结构。只有网表证据支持时，才在必要的精确标量CE边界保留局部译码：input为24/wave×2=48个边界、context64个，若两候选全部实施则全设计112个，首轮input-only为48个；预计算qual还有逻辑成本，112不是净LUT增量上界。意图将每条CE负载限制为256bit或96bit。index/qual仍需送到各decoder，data仍广播，物理拥塞是否改善必须实测。不能给整个bank添加DONT_TOUCH，也不能删掉已有frontend/output的有效局部CE保护。

row内读选择、output串行mux的改写另作备选：对照综合网表判定是否真的消除集中宽mux/广播，不能把case/onehot或wire别名当物理改善。已有projection复制/流水用来保持局部性，不按“重复位数”直接删除。

此项仍保留activation_wave的6144bit选择，不能声称已消除6163扇出的wave选择网络；RoPE/quant等其他高扇出来源也需看新布局是否仍构成瓶颈，不把top50都盲目复制。

验证要求：每个slot完整覆盖且仅写一次；读写跨边界顺序一致；最后一个slot到valid时刻一致；双wave交错、停顿、clear/reset及输出稳定性逐周期对照。变更组合路径仍须测时序。

### C3：对已实测大扇出控制做局部化

MLP四条精确已知控制net的扇出为8201/6192/6145/4652，存在跨SLR0/1负载；先前自动BUFG候选因物理冲突跳过。**C1历史替换不解决已有大输出CE，二者须分别处理。**

[目标net实测](runs/R001/attempts/AT001_readonly_physopt_diagnostics/target_net_fanout.tsv)进一步确认：Down输出8201个叶负载分为SLR0的4105与SLR1的4096；Gate输出6145分为3073/3072。两driver均位于SLR0。Down history6192分为3119/3073，Gate input_fire4652分为2348/2304。这里采用leaf loads；某些对象的FLAT_PIN_COUNT包含driver而多1，不能混算。已取得SLR分布，未导出每个load的类型及SLR内完整位置包络，行分组是否实际聚集仍要新布局验证。

可以将两repacker的`out_payload_r`更新拆成16个固定row owner：Down每row512bit，Gate每row384bit。精确同拍资格为`rst_n && !clear && input_fire && produces_output_c`；按原源`input_fire`定义及reset/clear优先级保持全部条件。每row使用一个组合identity LUT1缓冲CE（32个标量副本），最小保护范围只含这32个driver，不保护payload或整bank；既有frontend已有同类局部CE结构。保留assembled_output、metadata/valid/count/order/错误检测，数据不加拍、不改时钟。

基线8201/6145并非保证全是payload负载：残余metadata/control继续用原控制。目标是全局资格控制主要驱动16个局部副本及真实残余负载，每副本约512/384个数据CE端点。不得把源码拆成16行便视为达成，必须检查真实driver副本、每副本fanout、端点包络、跨界负载和时序。即使最大fanout降低，若局部拥塞转移也不能宣布成功。已有frontend局部CE `input_fire_local_21`本身也出现在失败样本中，说明局部复制不是充分条件，仍须改善所在区域的资源与连接分布。

验证reset/clear当拍payload保持、stall稳定、同拍消费并接受新输出、metadata逐拍对齐、无重叠多always写；与原模块逐周期对照。S24历史enable另有端点增长问题，不由输出CE分组自动解决。全局MAX_FANOUT、全局DONT_TOUCH、强插BUFG不列默认方案。需要寄存控制的其他方案必须连同数据/valid/tag/ready设计，不能只给CE加一拍。

### C4：拥塞或SLR导向的重新布局

**首选`place_design -directive SSI_SpreadSLLs`，physopt沿用既有默认设置，router保留Default。** A007已核AMD UG904 2025.2 Available Directives与Implementation Strategy Descriptions：该placement方向针对跨SLR划分时的高连接区域分配更多空间。原route的SLR0–1列级估计需求超额、Attention必须跨SLR1/2、三SLR站点均接近占满，使它比无条件全器件最大程度分散更有针对性。这仍是有依据的试验选择，效果必须测量。

`SSI_SpreadLogic_high`作为有条件后备：若新RTL已落实、同阶段报告显示主要残余问题是区域内拥塞，且跨SLR分配/列级需求已经改善，再新开一次有明确变化的尝试。高程度分散可能拉长6144bit路径或增加跨界，不默认两个策略连跑，不无界扫参。`SSI_BalanceSLLs`保留为后续确有分配失衡证据时评估，不作为本轮首选。

本轮安装版本native help未成功取得，官方2025.2文档足以支持提出具体候选，但启动下一阶段前仍须做不加载DCP的轻量命令/器件适用性核验。若不支持，记录真实错误并明确修订策略，不静默替换参数。源/约束/器件身份与每项directive全部冻结；同阶段比较，组合改法的整体效果不冒充单项消融。

首轮不加紧硬Pblock、不改DDR/PCIe固定位置、不降100MHz、不添时序例外。Attention当前2296个DSP已超过单SLR的2280容量，不能把整Attention硬压入一个SLR；2280由原生各SLR Used与两位Util%反演并与全器件6840核对，详细复算由R003保存。若未来做软层次/SLR引导，必须先核每SLR的LUT/FF/DSP/BRAM/URAM、跨界宽度和连线方向。[已有48个布局拥塞窗口复核](runs/R001/placed_congestion_windows.json)中Combined LUTs最高34%，Level6窗口仅6%–16%，当前证据未触及UG949提示的局部>40%场景。因此全局关闭LUT combining不列首选；这不证明局部试验永远无效，而是要求先有新的针对性证据。

### C5：后备架构——逐行读取与postprocess存储复用

6144bit→768bit逐行接口具有减少同时传递连接的潜力，但原source在接收握手后可复用，现有frontend快照是必要的数据寿命边界。直接删除会把后续行读成下一组数据。正确方案必须保留banked快照，或新增显式ownership/credit/双缓冲，证明8行消费期间不能覆写，并测最小启动间隔和背压传播。不能宣称减少8倍全设计布线。

postprocess若将K RoPE原位写回、V直接量化，理论可少一组16×768=12288声明位；但当前原始projection与postprocess读口可同时观察，原位写回可能改变未带valid端口和测试可见行为。须明确实际消费事务、pair读写顺序、phase互斥、clear/stall及调试可见性后再立内部合同，不能删断言迎合设计。两者列中高风险备选，不混入首轮简单等价替换。

较小的postprocess后备应优先于单bank复用评估：保留projection/post双bank及现有读口可见性，仅将RoPE动态48bit目的写改为16row×16pair固定目的/局部资格。它针对top50中的rope_output_index扇出3902/3885/3836，但必须保留整bank projection_post_capture与后置RoPE写在同拍的原优先级；256个局部写边界并非净LUT增量。此项单独验证后再决定，不顺带变更RoPE/quant生命周期。

补充备选：仅input双wave的12288bit activation payload存在异步清零，其他主要宽payload已经resetless。去掉这部分data reset必须先证明同一epoch完整24slot覆盖后才产生valid、任意slot reset/clear不会泄露旧数据，且无效期零值不是既有接口要求；保留所有控制/错误/valid复位。这不减少12288个数据位，也不能直接报FF节省。不与首轮小改法顺手合并。

## 4. 下一次实验的次序与判据

1. **先补失败取证入口并保留错误语义。** route成功保持现有完整POST；route失败时尽力分别保存带`failed`身份的DCP、route_status、拥塞、时序和DRC，并保留原始Tcl错误码/信息。每项诊断单独catch，某一报告失败不阻止其余取证；任何诊断成功都不能把route返回值改成成功。失败产物不得被正常恢复父链误收。具体入口与错误传播检查见[R001失败取证设计](runs/R001/failure_capture_design.md)；这只改善取证，不计入布线收益。
2. **独立功能验证后合并候选。** 用冻结旧模块与独立事务oracle比较受影响模块；正常连续传输、随机/长背压、全部slot/matrix/tag、首尾/clear/reset/非法次序都覆盖。纯原语/分银行为要求逐周期等价；新增流水候选另用accepted事务顺序及位精确比较，同时记录延迟/启动间隔。已有`hap_mlp_rebuild_repack_s32_tb.sv`使用MATRICES=2，而生产Down为MATRICES=1，必须补实际MATRICES=1的逐拍与独立列重排oracle覆盖；不能仅重跑旧bench便宣称生产参数通过。Gate输出CE改法还需S24/MATRICES=2自身的功能验证，源清单CPU测试不能替代payload仿真。Attention两个直接TB的现有覆盖与最小补测见[R002 §9](runs/R002/rtl_routability_analysis.md)；input已有完整双wave/128group/24槽及短stall，但无运行中reset/clear；context只wave0/group5，无read_issue空洞和中断恢复。以每slot中断后的新epoch互补payload检查旧数据泄漏，不能用projection stub和全零集成TB代替。
3. **一次新综合确认改法落到网表。** 冻结源/约束/hash；查看C1实际SRL/FF/LUT变化、C2宽mux/控制扇出、各模块资源；保持DSP/数值位宽/Host接口与时钟。若修改被重新合并或产生新黑盒/锁存/未约束路径，先修正再消耗完整布局时间。新网表的对象名/代表源可能变化，物理入口只按真实driver→consumer图适配身份，继续验证时钟/复位/CDC类别和负例；不能复制旧名白名单或放宽安全判据来取得POST。
4. **重新place并physopt，完成完整POST。** 保留层次利用率、SLR分布、控制集合、高扇出负载位置、拥塞表、时序和DRC。比较固定坐标窗口及新最坏窗口，避免仅挑变好的窗口。关注SLICEM是否真正释放、局部拥塞是否下降、实际跨SLR nets/loads与SLL Used分布是否改善、是否挤坏DDR/PCIe路径。
5. **route前作一次有证据的决策。** 对结构没有落实、资源/约束不合法的候选不进入route；对结构已落实且目标拥塞改善的候选按冻结策略做完整route。不存在“LUT低于某百分比”或“level降一级”即可保证成功的阈值。未达到理想改善但仍合法的情况需明确记为风险实验，不能隐藏后直接宣称优化有效。
6. **所有正常执行沿用无墙钟/静默强停策略。** 现有通用`run_xsim_tb.sh`默认每步timeout300秒，下一阶段需适配执行入口，不能直接套用；测试中的有依据协议断言/周期完成条件与外部墙钟强停分别处理。完整route开始后不因耗时长或暂时无输出终止。 继续单EDA资源保护。报告变化用于解释进度，不把单阶段计数下降当完成率；以真实终态判定。若再次失败，用新增失败DCP定位剩余网络，避免再次只剩10个样本。

首轮功能验证应形成以下可审核证据（本轮尚未执行）：

| 受影响范围 | 独立检查重点 | 通过范围 |
| --- | --- | --- |
| Attention双wave input | 非零且每wave/group/slot不同的输入映像；全部24槽、128组、两wave；任意slot的reset/clear后用互补新epoch重入；短/长stall下valid/tag/data稳定 | 固定slot捕获与原合格事务逐位、逐拍一致；不覆盖整模型数值签核 |
| MLP Down S32输出CE | ROWS=16/MATRICES=1的12列→16列重排独立oracle，高位有符号数据、尾16列mask、同拍消费并填新输出、stall/clear/非法顺序 | 生产参数payload/metadata和原控制周期等价 |
| MLP Gate S24输出CE | ROWS=16/MATRICES=2，矩阵交替与两次accepted历史，跨任意stall取旧值，valid/mask/order保持 | Gate/Up重排和输出资格等价，不替代SwiGLU/Hadamard数学全链验证 |
| 取证/物理入口 | route error与单项report error注入；失败产物不可进入成功父链；新源/约束/父点身份；reset/CDC对象真实连接和负例 | 原失败返回码不丢失，报告成功不能冒充路由成功 |

若纳入context，增加双wave和group0/1/126/127、read_issue空洞、16slot及最后drain边沿中断；若纳入S32历史FF，额外验证原INIT/独立CE行为。候选新增周期、reset资格或数据所有权变化时必须另补其事务与性能合同，不能继续标为上述逐拍等价小改。

比较指标须同源、同阶段、同范围：全局占用与目标scope资源、每SLR占位、SLICEM/FF填充、最大/分位fanout、跨界负载、固定窗口拥塞和最坏窗口、每列SLL估计（仅在route早期同阶段比较，不冒充place指标）、setup/hold及完整route状态。前后源有变化时报告组合效果；未做消融不声称某单项独自带来全部收益。

合法布通要求native route成功、closed route DCP与完整POST、`routable>0`、`fully_routed==routable`、unrouted/partial/routing errors全0且无节点重叠。时序收敛另要求100MHz与两200MHz UI约束下setup/hold/PW完整合格；CDC/reset/事务安全和板级验收继续独立，不能由布通替代。

## 5. 首轮最小组合与后备顺序

按已取得的原生资源、top50、目标负载SLR分布和自然终态，建议下一轮采用下表。本轮未启动实施；候选收益和合法布通仍待新实验验证。

| 顺序 | 范围 | 选择与验收重点 |
| --- | --- | --- |
| 必备流程 | route失败捕获、测试入口与新网表物理资格 | 保留失败DCP/route_status及原始非零退出；无外部墙钟强停；保持原CDC/时钟/成功POST要求。不是拥塞收益 |
| 首轮RTL A | C2的input部分：双wave固定24×256bit目的写，48个局部边界 | 直接对应十根6170–6174负载索引；保持data reset、快照、valid与全部周期语义，检查index数据/控制负载实降 |
| 首轮RTL B | C3：MLP Down/Gate各16row output CE，32个局部驱动 | 对应8201/6145输出控制；每row512/384bit，保留资格与metadata，目标本地化且跨界主干负载下降 |
| 首轮物理 | fresh synthesis→完整place/physopt→route；place选SSI_SpreadSLLs，其他策略保持默认 | 完整准入后运行；比较两个区域与跨界连接，不以一项资源或fanout变化代替合法route |
| 第一后备 | C1 S32-only，或保持双bank的postprocess固定pair写 | 根据新布局剩余热点选择其一；前者触及SLR0/1的3072个SRL槽，后者针对SLR2的RoPE写控制。分别验证，不自动全部叠加 |
| 后续局部选项 | context64个边界、wave/row选择局部化、S24历史FF及其局部CE | 要求对应负载/位置证据；context未进当前top50不是无风险证明，也不支持强绑首轮 |
| 较大架构后备 | frontend逐行ownership、共享input loader、postprocess单bank | 需独立内部协议/可见性/延迟合同与验证；不作为第一轮同周期修改 |

最小首轮共80个计划中的局部控制边界（48+32），不是净新增80 LUT的承诺。保留每项独立diff和模块验证，合并后一次新的正式综合与物理流程；是否需要后备取决于新网表和布局证据。若主项未落到网表、热点不改善或资源/时序反而明显恶化，先在下一次route启动前修订，不为完成流程而重复旧失败结构；已开始的正常完整route仍自然运行至终态。

来源：[R001物理分析](runs/R001/physical_routability_analysis.md)、[R002源码/测试映射](runs/R002/rtl_routability_analysis.md)、[R003架构方案](runs/R003/architecture_plan.md)、[AMD 2025.2方法](../experiment_source/amd_methodology_2025_2.md)。

execution: 分析完成；verdict: 优化效果尚无实施证据，inconclusive；applicability: E003冻结设计的成功physopt父点与绑定源码；review: 由R003独立审核记录及主控SM008记录分别承载，用户尚未进行下一轮结果验收。
