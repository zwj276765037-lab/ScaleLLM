# E005 R005：SM009连续架构与阶段独立审核

负责人A007 `/root/m002_physical_architecture_review`；期望gpt-6-astra/xhigh，实际配置未独立核实。独占R005与自身agent记录，生产树只读，不运行EDA/仿真、控制进程或创建后代。A009拥有3个RTL及功能TB，A006拥有构建/物理/取证入口并统一调度全部EDA；保留他人修改。

## 1. 合同初审：范围一致，无新增批准门

当前用户授权“开始优化和新的implementation”，[SM009合同](../../../../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)取代SM008仅分析边界。E004方案冻结SHA `9b666f60371b07f67284b0ae402fda28ee3e1ae30db8bac243bd03064a7567f3`已重新核实；合同身份与本次读取时间见[contract_review_evidence.json](contract_review_evidence.json)。

首轮只做input双wave48固定slot、MLP32个row output CE、单一SSI_SpreadSLLs新place以及独立的失败取证/无墙钟执行入口。原算法、数值、Host ABI、DDR职责、core100MHz/UI200+200MHz保持。S32 history替换、context/postprocess、窄frontend、reset移除与新流水不自动合入。原physopt和router维持Default；不安装会同时改多个阶段的整套strategy。无bitstream/板卡/GPU/PPL/ACC，旧工程只读。

合同覆盖生产参数独立oracle、旧版逐周期对照、新综合映射、完整物理POST、失败保全和原始终态；单EDA/8CPU/nice5及RSS/可用内存/磁盘保护明确，取消固定墙钟与静默强停。合法且结构落实但改善不足的候选可说明风险后按授权继续一次route，不额外向用户索批；负setup/hold不自动禁止诊断route，也不能称时序通过。**本次合同初审未发现实质阻碍。** 工程照当前授权连续进行，后续阶段结果仍待真实交付。

## 2. RTL与功能覆盖的关键判据

| 范围 | 必须保留的行为 | 本阶段需真实证据 |
| --- | --- | --- |
| input固定256b目的slice | 原async payload reset、clear时payload保持、BRAM读流水、index/valid/pending与最后slot完成拍、6144b快照及wave/group顺序 | 冻结旧版同拍对照和独立非零、每wave/group/slot区分镜像；双wave×128group×24slot完整覆盖，任意slot reset/clear后互补新epoch、长/随机stall、末slot和pending/drain边界 |
| Gate/Down row output CE | 精确组合资格`rst_n && !clear && input_fire && produces_output_c`；reset/clear当拍payload原本保持，metadata/count/order/error/valid独立保持；不改SRL或加拍 | S24 ROWS16/MATRICES2与S32 ROWS16/MATRICES1均有独立12→16列队列oracle及旧版逐拍对照；consume/refill同拍、stall稳定、尾mask、matrix/tag/非法顺序、reset/clear与fire同拍 |
| 标量保护与唯一owner | 48slot资格/32个identity LUT1仅在必要标量driver上保护，data bank/整个module不锁死；每payload bit唯一时序写入owner | 精确diff与保护对象清单，模块仿真只证明行为，最终综合报告确认保护后的实际结构 |

Input原scope有56个控制集合，十根capture index的6170+负载并未分类；不能称原来完全没有local CE。固定slice的核心目标是data直连、减少索引进入宽数据选择，同时局部化写资格。新网表需同时核data steering、译码和CE负载；仅generate语法或局部原语实例数不证明机制落实。

MLP旧S32测试MATRICES2不是生产Down参数；S24不能由S32测试或builder源码检查替代。旧版对照也不是独立数学oracle，两种证据都需区分。无效期payload的未知值及clear/reset当拍状态按原合同比较，不修改expected、删除断言或跳过失败用例。

## 3. 工程入口、综合与物理阶段判据

失败捕获设计独立验证原始Tcl code/result/options的传播；各报告独立catch、单项失败仍继续、没有design时记录不可用、证据不覆盖、失败DCP不能进入成功父链。无DCP轻量核安装版directive/器件支持及真实传参；原native help缺口不等于策略已通过安装核验。

真实源/XDC/IP/工具/父点冻结后综合；按实际driver→consumer图适配物理入口，保留未约束路径、黑盒、锁存及reset/CDC负例标准，不复制旧对象名白名单取得通过。模块LUT/FF/SRL/控制集合、48/32边界、目标索引/CE负载类型和数量与基线同口径比较；80边界不是净80 LUT。

完整place和独立physopt后的审查同时看SLR2 Attention与SLR0/1 MLP、固定/新最坏拥塞窗口、局部占位、跨界load和每SLR专用资源、setup/hold/PW。旧全局BEL槽填充直方图INVALID，不作packing基线；需要该字段时按native有效来源取得，不能把旧0当空槽。SLR每列Estimated Demand只在route早期同阶段比较，不混同placed实际SLL Used。

route前工程报告结构落实与合法性；若有已知残余拥塞/负时序，明确风险及适用范围，按合同继续一次诊断route，不增用户审批。真实route完成须原生命令成功、closed DCP/完整POST、routable>0、fully_routed==routable、unrouted/partial/errors均0且无重叠；失败保留实际错误和尽力现场。功能、合法布通、时序、正式CDC/reset/事务安全和板卡资格分别判定。

## 4. 合同初审时状态与后续回传

execution：contract review completed，SM009连续审核running；verdict：新优化尚未验证；applicability：本合同与E004冻结首选；review：A007内部阶段判断，不代表用户对未来结果验收。

重要结论已通过实际消息发送主控、A006及A009。后续以其阶段摘要/精确diff/小身份及有界原始报告为入口，只对明确疑点进一步读取；不重复完整大日志/DCP，不宣称无人值守后台监控。当前尚无本轮RTL功能、综合或物理阶段PASS。

## 5. 首版RTL与功能测试源审核

[v1源码核验](rtl_tb_v1_review_evidence.json)绑定10个交付输入、4个冻结原件及4个参考派生。原件身份匹配，参考只做已声明的模块提取/重命名，忽略外层空白后逐文本相符；不是重新写成DUT相同结构的伪参考。三份生产RTL差分限制于payload写入owner和精确组合CE；控制、metadata、SRL历史和周期无改动。

Attention每wave24个固定256-bit slice拥有独立时序owner，保留async payload reset；LUT6 I5为`!clear && active_r && !output_valid_r && read_stage_valid_r`、I4:0为capture_index，INIT置位在32+slot，资格正确。MLP每个生产模块16行，LUT1 identity资格为`rst_n && !clear && input_fire && produces_output_c`，每行Gate384 bit / Down512 bit；reset/clear保持payload，历史SRL独立写资格未改。仅标量driver保护，未对整个bank加DONT_TOUCH。**未发现实质行为合同问题；此源码结论不替代编译、仿真或实际网表检查。**

两份TB已完整有界读取。Attention冻结旧版逐周期比较包含无效payload及两个private wave；独立DMA地址oracle使用wave×3072+(slot/3)×384+group×3+slot%3，非零互补图案区分地址/word/epoch。MLP使用每matrix列FIFO和独立order/capacity/count/error模型，生产S32/M1/ROWS16与S24/M2/ROWS16并测，不复用DUT的SRL拼接case；包括随机/长stall、consume/refill、非法mask/顺序/matrix、terminal residual与reset/clear输出资格重叠。保留原参考全接口逐拍比较及独立数学oracle两种不同证据。

## 6. 入口与安装版directive独立核查

具体身份、状态字段与适用范围见[阶段证据](functional_entry_stage_review_evidence.json)。R002/AT001原测试log明确150+6=156项PASS、两进程exit0，包含5项失败捕获测试及无deadline新授权。独立阅读测试与捕获实现确认：原始Tcl result/code/error options传播；某个report失败不阻断其余项；无design记录不可用；已有证据不覆盖；失败诊断不能成为成功parent。当前34个输入中32个仍匹配，preflight Tcl和优化监督入口随后改变，故不把原CPU结果无条件归于所有当前输入；已通知A006在最终入口记录说明两项变化和受影响覆盖。新版本已分别被后续原生preflight和功能运行实际使用。

R002/AT004目标器件上下文`preflight_identity.tsv`明确Vivado2025.2、xcvu9p-flga2104-2L-e、virtexuplus、`Vivado Implementation 2025`与默认strategy；原生help第136/143行明确列`SSI_SpreadLogic_high` / `SSI_SpreadSLLs`。实际run属性place=`SSI_SpreadSLLs`、physopt/router=`Default`，native及监督exit0、stop_reason null、无残留、无wall/no-output deadline。前一AT在create_project前返回Advanced Flow帮助，其缺少SSI指令不适用于此器件的classic flow；差异已由原生上下文解决，**无需变更合同策略**。这是安装兼容性检查，尚未实际布局。

## 7. Attention功能PASS与MLP普通编译修复

Attention R001/AT001原`xsim.log`、`launcher_status.txt`、`inputs.sha256`与监督终态已独立核：v1源/TB/参考身份一致，原PASS marker，native/监督exit0、stop_reason null、无survivors，fault_lines为空。实际覆盖：1,265,488周期及冻结差分、1,263,504 slot oracle检查、192中断、196 epoch、4个完整双wave镜像、13,591 stall检查；last-slot-before/after各4、有效输出中断4、非时钟沿async reset97、wave0/group127边界2。**指定v1 Attention功能范围PASS**；不是整芯片功能、网表映射或物理结论。

MLP R001/AT002在xvlog阶段退出1，原错误是TB第259行使用`saved_input_target`早于声明，未开始仿真；无资源或时间强停、无残留。该尝试是工具编译失败，不能据此反驳CE方法。A009保全v1 TB并交v2；已独立核全部10个v2交付hash，唯一文本差异是将该integer声明移到第一次task使用前，RTL、oracle、刺激和断言均未改变。A006已启动AT003；本节记录时其功能结论仍待核。正常修复按现有授权继续，无新增审核门，也无需重跑输入未变的Attention。

execution：本次源/入口/Attention阶段审核completed，SM009连续审核running；verdict：Attention指定功能PASS，MLP待实际仿真，优化物理效果inconclusive；applicability：阶段证据绑定的v1/v2与AT身份；review：A007内部独立阶段判断，真实消息已发送主控/A006/A009，非用户最终验收。下一步核MLP终态及新综合48/32真实控制边界、负载类型和资源。

## 8. MLP功能阶段完成与最终179项入口核查

[本阶段独立证据](functional_complete_pre_synth_review_evidence.json)绑定R001/AT003及R002/AT005原记录。MLP v2原`xsim.log`只有一个预期PASS marker，launcher complete/exit0、native/监督exit0、stop_reason null、owned_survivors空，fault_lines为空。运行manifest内5个相关DUT/TB/reference身份与v2交付及当前文件相符；三生产RTL自首版未改，AT002编译失败与v1保留。

| 生产配置（均ROWS16） | cycle / diff | 独立输出oracle | 同拍替换 | stall | reset / clear输出资格重叠 | 错误用例 | tail4 / tail8 | signed/high lanes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Down S32 / MATRICES1 | 2477 / 2477 | 49 | 2 | 1368 | 1 / 1 | 16 | 6 / 6 | 7168 |
| Gate S24 / MATRICES2 | 4821 / 4821 | 98 | 5 | 2754 | 1 / 1 | 17 | 12 / 12 | 14456 |

全局结束48207ns，run-all实际5分41秒；没有默认300秒墙钟中止。结合§5已核独立oracle及旧版逐拍对照，**两种MLP生产参数的本次有限功能范围PASS**。与Attention AT001一起完成本轮受影响功能要求；不是全芯片形式等价、全局事务安全或物理签核。

R002/AT005原log为151+6+11+11=179项PASS，四组exit0，当前38个登记输入逐一hash匹配。范围包括原错误传播/独立取证/不覆盖/失败parent拒收、无wall/no-output终止、新E005源manifest anchor与后续source tamper拒收、builder sources和ROM staging。新anchor测试确实加入新输入、通过新身份验证后更改该输入并要求拒收。此前AT001中preflight与supervisor两个后续版本变化由此次最终当前源CPU记录及AT004实际执行覆盖闭合，历史156项原证据仍保留。

execution：功能及入口有界审核completed，整体连续审核running；verdict：本次受影响功能PASS，入口检查PASS；applicability：AT001 Attention、AT003 MLP v2、AT005最终入口与各自输入身份；review：A007内部独立结论已实发主控/A006，不新增启动批准门。

## 9. 新工程创建前身份与综合阶段待核范围

`experiment_source/frozen_inputs_before_create.json`共141个生产源、ROM、manifest、XDC及工程工具输入，34838 bytes / SHA256 `f94724cb255978e7f77acd8f5f0cc0f7dfb025b6ae8c272aaccac1eb17f21dc1`；全部位于新`project/hardware`，已逐一验证当前hash与bytes一致，三份生产RTL与功能运行身份相同。此清单是**创建前源闭包**，不冒充随后实际生成的IP/XDC和综合网表完整身份。

R002/AT006已真实启动fresh create，命令/启动事实指定新工程`vivado/project/m002_E005_R002_AT006_fresh`及独立报告目录，E005合同/profile、CPU0–7/nice5、192GiB/48GiB/30GiB保护、无墙钟及无输出timeout符合合同。该阶段记录时没有create终态或正式综合结果，未把启动写成成功。

已读新`freeze_m002_optimized_synthesis.py`与`synth_lineage`受影响段：完成后须真实top/OOC共23个生产DCP、原生日志22个consumed IP、45个独立路径及逐对hash绑定，新源manifest/工具/完成/终态分别anchor；旧E002固定anchor仅保留历史适用。当前仅源码和对应负例检查通过，实际新绑定待综合完成。主控和工程已收到精简交付要求，不读取大DCP。

已读80边界probe：目标scope分别48 input LUT6、16 Gate/16 Down LUT1，实际叶pin须分别为256/384/512个CE；同时输出REF_NAME与REF_PIN_NAME计数、INIT/DONT_TOUCH、上游控制fanout，物理阶段增加driver/load位置、SLR分布与slice XY包络。后续核真实报告中的INIT、连接和负载变化，不能只数原语。无网表/布局结果前不宣称时序、拥塞或跨SLR改善。

## 10. 原综合监督失联后的同进程接管独立审核

用户追加继续；A006恢复工具访问后发现R003/AT001原监督156037已消失，工具session不可用，但原leader和Vivado仍在运行。A007于2026-10-16 02:17:23Z直接读`/proc`确认：156037不存在；leader156038/start_ticks922452770已由PID1收养，Vivado156138/start_ticks922452788仍属于原进程组156038，二者CPU0–7/nice5。没有将最新旧资源样本01:42:20.571935Z当作当前心跳。

A006已独立启动guard243730，接管起点02:17:17.956761Z。A007于02:17:37Z直接核其命令、FD3与fdinfo：同`project/hardware/vivado/.m002_eda.lock`实际由243730持有FLOCK ADVISORY WRITE；新resources样本来自原PID/start树，连续CPU计数增加。完整核验快照、旧文件hash及新资源记录已读前缀身份见[监督接管审核证据](supervision_handover_live_review_evidence.json)。guard脚本SHA `650861d2487b3e03bb3b60097068d456fae5a672c2576c329562cbfbcdb93a1a`，独立位于agent/A006，未热改生产源；保留192GiB树RSS、48GiB可用内存持续30秒、30GiB磁盘保护和无wall/no-output强停。接管时观测RSS约20.34GiB，既有native未重启。

旧最后样本到接管起点共2097.384826秒（约34分57秒）为**资源监督观测缺口**。这不证明原监督精确何时消失，也不能证明缺口内各时刻满足资源保护；已记录不回填。A006的`original_evidence_snapshot.json`所绑定原started/command/resources的bytes/hash均经A007重新核实，原resources未追加，原`status.json`仍不存在。**原失联监督器退出状态UNKNOWN，不补写native/监督exit0。**

已读接管脚本：结束时独立写handover status，native_exit_code保留null并标记`native_exit_not_waitable_after_orphaning`，记录当时owned进程及原wrapper的launcher文本。该新guard不是原leader父进程，不能以进程消失或23个子run完成推导原wait结果。原`run_vcu118_board.sh`若自然执行到EXIT trap，其原始launcher_status中的native_rc仍可证明其直接调用的Vivado返回，但应与未知的原监督器wait分开。最终综合资格须按真实闭合证据处理，不能直接使缺失的旧status变成成功，也不因监督失联无依据重跑已成功的综合子任务。

execution：紧急资源监督已由A006恢复、原综合报告阶段继续；verdict：同进程身份、实际锁和新资源保护已确认，原监督完整性存在上述缺口；applicability：本次AT001与独立handover记录；review：A007只读阶段判断已实时发主控/A006，不阻塞接管、不开新EDA或控制进程。

## 11. 当前342项正式综合输入与原生子运行事实

已独立读取正式`inputs.sha256`：87724 bytes / SHA `f889d3d953c1a23c551f85111928a613c3195cb794c05983fc56a7396d0a4db5`，342行/342独立路径，逐一hash与当前输入匹配；其中三份优化RTL与已通过功能版本相同。包含178 XCI、48 memory、87 SV及构建manifest/约束等，外部输入仅3个Vivado安装板卡XML。`build_identity.txt`明确2025.2、xcvu9p-flga2104-2L-e、VCU118、目标wrapper和原定义，Synthesis Defaults/2025 flow。

已在指定新工程的23个top/OOC synth目录有界核到23个`.vivado.end.rst`、0个`.vivado.error.rst`，各自DCP已存在；只读取小回执及DCP文件stat，没有载入或hash大DCP。原controller log中有22条真实`Reading design checkpoint`记录。45路径的最终生产/消费hash绑定仍待A006交付，不能只凭同名或文件存在判定相等。

本次快照时原wrapper launcher_status、fresh_synth_complete、80边界/控制源报告及正式综合时序报告仍未取得，controller在open_run/后处理阶段。故本节判定仅为**342输入身份一致、23个原生综合子运行有完成回执**，不代表外层综合完整终态、80边界机制、时序或物理通过。新阶段报告到达后继续有界审核。

## 12. 已生成综合利用率报告的同阶段比较（外层终态仍未闭合）

已独立读取E005原生`utilization_post_synth.rpt`及hierarchical报告，并与E002/R001/AT002正式综合原报告逐项比对。两份报告均明确Vivado2025.2 Build6299465、xcvu9p-flga2104-2L-e、相同board wrapper、Design State=`Synthesized`；不能以E003 physopt的814935 LUT作此基线。原manifest有88个共同生产RTL，恰好本轮三份RTL hash改变，无新增/删除生产RTL。完整报告身份、原行号和差值见[同阶段资源证据](synthesis_utilization_preterminal_review_evidence.json)。

| 同阶段原生指标 | E002正式综合 | E005当前综合报告 | 差值 |
| --- | ---: | ---: | ---: |
| CLB LUTs | 841576（71.18%） | 828763（70.10%） | −12813（相对−1.5225%） |
| CLB Registers | 1029313 | 1029316 | +3 |
| 严格Register as Flip Flop | 1029311 | 1029314 | +3 |
| Register as Latch | 0 | 0 | 0 |
| Unique Control Sets | 22322 | 22353 | +31 |
| LUT as Distributed RAM / Shift Register | 29200 / 14551 | 29200 / 14551 | 0 / 0 |
| BRAM Tile / URAM / DSP | 945 / 752 / 5451 | 945 / 752 / 5451 | 0 / 0 / 0 |

CLB Registers两份均包含2个AND/OR资源，因此总数与严格FF子行分开；hierarchical报告自身列名FFs采用总数。LUT变化全部来自Logic LUT（797825→785012），LUT memory总数43751不变。资源报告的Black Boxes两份均列`dbg_hub_CV × 1`，与既有综合后debug状态一致；不把latch0误写成零黑盒，后继debug物化及安全检查仍需真实证据。

| 目标层级 | LUT E002→E005 | FF E002→E005 | 其他保持 |
| --- | ---: | ---: | --- |
| Attention input buffer | 18648→6421（−12227，−65.5674%） | 12341→12341 | RAMB36=42、RAMB18=2 |
| MLP Down repack S32 | 8267→8289（+22） | 8285→8282（−3） | SRL=6144 |
| MLP Gate repack S24 | 9308→9327（+19） | 6245→6245 | SRL=4608 |

两wave的层级LUT不对称在旧报告中已存在，且输出wave选择/逻辑归属仍会影响层级统计；不能仅据层级大小断言某wave优化失败。input层级明显减少与移除宽索引写入选择的预期相符，但80个实际CE边界、上游index扇出和负载类型仍待专门网表报告。MLP行级复制局部LUT增加41，不能把更大MLP父层级的净变化全部归因于这32个driver；本次为组合优化，没有独立消融。

execution：此资源报告审核completed，controller后处理仍running；verdict：同阶段资源变化已观测，优化对拥塞/合法布通/时序的收益尚未验证；applicability：绑定的原生Synthesized报告与342输入；review：已实时通知主控/A006。原监督退出UNKNOWN和观测缺口保持不变，未据资源报告宣告完整综合成功。

## 13. 80个真实CE边界与综合检查报告独立核验

原`optimized_structure_synth_result.txt`为`issues=`空、48input/16gate/16down，明确`physical_signoff=false`。A007对`optimized_boundaries_synth.tsv`全部80行逐行复算，独立结果见[结构与检查证据](synthesis_structure_preterminal_review_evidence.json)，并未只采用原脚本PASS字样：

- Input两wave各slot0–23完整，48个LUT6的每项INIT均等于`1 << (32+slot)`、DONT_TOUCH=1；每项恰256个FDCE/CE输入，总12288位。
- Gate各row0–15完整，16个LUT1均INIT=2、DONT_TOUCH=1，每项384个FDRE/CE，总6144位。
- Down各row0–15完整，16个LUT1均INIT=2、DONT_TOUCH=1，每项512个FDRE/CE，总8192位。

14条真实上游net/driver记录亦已核：每wave五个capture index bit0–4负载分别32/31/30/29/28，全部是LUT输入；每wave write qual为24个LUT6/I5。Gate上游资格16个LUT1/I0；Down25个负载由16个LUT1/I0和9个metadata FDRE/CE组成，未把metadata排除而伪报16。Gate源net沿用`out_matrix_r[0]`等综合网名，依实际driver/连接判断，不以预期RTL信号名称替代图证据。

**本次Synthesized网表的48/32逻辑CE结构判定PASS。** 结合input层级LUT减少，支持本轮预定结构已被综合实现；当前LOC/SLR均未布局，不能宣称空间局部性或拥塞收益。旧6170+ index负载来自E003 physopt，故不与本次synth28–32计算同阶段布线改善比例。后继place/physopt需再次核实际复制、位置、SLR与fanout。

新综合时序原表：WNS +0.904ns / TNS0 / setup failing0；WHS −0.814ns / THS −49356.691ns / hold failing1000188；WPWS −0.012ns / TPWS −0.037ns / PW failing5。相较E002同阶段setup/WHS/PW相同，THS多负1.050ns、hold failing+5。**这是综合估计，hold与PW仍FAIL，不称时序通过，也不作为诊断物理执行的自动禁入条件。**

`check_timing`12类计数和实际列出的对象集合已与E002同阶段逐项比较：530 no_clock、554 unconstrained_internal_endpoints、1 no_input_delay、2 no_output_delay，其他类0；每类对象无增删。这保留既有debug/IO未闭合范围，不声称无未约束端点。CDC汇总同为434 CDC-3、19 CDC-9、6 Critical CDC-10、6198 Warning CDC-15；忽略表行号/空白后的六条Critical记录连同clock pair/source/destination完全一致。正式CDC/reset安全仍OPEN；后继debug物化及物理资格按实际图重新执行。

execution：结构/检查报告阶段审核completed，整体综合父链审核待controller及handover真实终态/45DCP闭合；verdict：局部功能PASS、目标synth结构PASS、综合hold/PW FAIL、物理效果inconclusive；applicability：当前原生报告和已核342输入；review：实发主控/A006。原监督UNKNOWN与资源观测空窗不因结构PASS而消除，无新增用户审批门。

## 14. 原控制进程自然终态已独立闭合，父链恢复资格另核

原`vivado.log`现有80边界完成标记、`COMPLETED: synth`和2026-10-16 02:31:56Z自然Exiting；原wrapper自身的`launcher_status.txt`记录native_exit_code=0、exit_code=0，并指向本次新工程/报告。`fresh_synth_complete.txt`绑定已核342源manifest SHA `f889d3d953c1a23c551f85111928a613c3195cb794c05983fc56a7396d0a4db5`及build identity SHA `6880434eac78be5fdf41d2a1d2385f0634647f18ef26d93003ef5b4ca63a7afc`，均已重新hash核实。

handover原status结束于02:32:00.556483Z，stop_reason null、final_owned_processes空；其native_exit_code仍null且标记不可wait。A007于02:33:32Z直接确认原监督、leader、两中间wrapper、Vivado与guard共六PID均不存在。旧started/command/resources仍匹配保存的原始身份，原AT001/status.json仍不存在。已知的是**原wrapper观察到native0及自身整体0、资源接管观察到原树结束**；未知的仍是失联监督器自身及其原wait结果。

证据见[原控制进程终态审核](synthesis_original_terminal_review_evidence.json)。这确认原生综合及报告命令自然完成，无需重跑已成功综合；342/23/22/45最终父链资格、恢复入口负例及其独立closure将在A006交付后集中核验，不生成伪造旧status、不消除资源观测空窗。后续物理仍按当前合同执行，时序与正式安全范围分开。

## 15. 综合恢复入口与45条DCP父链集中审核完成

[可发布简洁事实](synthesis_stage_review_facts.json)汇总本轮综合阶段；[独立恢复审核证据](synthesis_recovery_closure_review_evidence.json)保留完整身份与核验范围。已通读421行工程入口差异及新增recovery helper/测试：仅在E005综合、原status确实缺失、原wrapper native/aggregate均0、原始记录与接管身份一致、原树真实结束、完成标记/80结构/源身份正确时接受独立closure。原有status路径未放松，不伪造旧status、不将失联监督或leader wait填0；物理来源同时归档恢复helper与closure原证据。四个改动脚本的原字节已独立核对归档与141创建前freeze一致，变化发生于原controller完成后，无实质审核问题。

R002/AT007 cwd import失败原证据保留；AT008实际164项PASS（151既有m002+13恢复正/负例），native/aggregate0、无stop/残留，12项输入before/after/current全部一致。负例涵盖wrapper缺失/非零、后处理失败、资源停止、final/live进程、源/DCP/closure/原资源快照篡改、原status遮蔽与marker/structure缺失；正例明确保留UNKNOWN wait及不连续监督。此164项不冒充前一179项完整回归的重新运行。

已独立核17个closure证据身份、6个anchor及当前342源hash；23个生产原生run、22条消费记录、45条独立DCP路径身份一致，22个生产/消费对hash相等，22条原生日志line/path/cell重算相符，当前45个DCP size+mtime匹配。**完整DCP二进制hash由A006实际成功的freeze命令计算**（原command/status证明CPU-only、native0，stdout与qualified lineage逐字段一致）；A007核全部绑定与文件stat，没有读取大DCP或运行生产validator。

恢复closure SHA `bb4e24d7d8122a26968d0670d25bd80b1e5b3df97a5a264ac31463f7b0f1e7e4`，anchor SHA `42029fd046a3feb74aa9caef17789416ac9d8cb047965b7619a621b4226f5f03`，DCP bindings SHA `872d7c4a63c548f068f431955a134842cf326b492757f5d2be1eefe5f69faa69`。正式结论为**综合与报告自然完成、逻辑结构PASS、恢复后父链支持进入已授权诊断物理阶段**；原监督/leader wait UNKNOWN及2097.384826秒资源观测缺口继续保留。综合hold/PW FAIL、正式CDC/reset安全OPEN。

execution：综合阶段独立审核completed，SM009/E005物理审核继续；verdict：预定综合机制与恢复父链supported，物理收益inconclusive；applicability：本次342源、新综合及上述closure；review：A007内部阶段结论，非用户最终验收、不新增启动门。R004/AT001已由A006实际启动，启动与142输入冻结另行有界核查。

## 16. 新物理AT001实际启动与142输入冻结独立核查

R004/AT001 `fresh_place_physopt`于2026-10-16 02:46:43Z实际启动，使用新的E005工程和独立报告目录；当前为INIT/link/logic preparation，未取得place/physopt结果。[启动审核证据](physical_startup_review_evidence.json)记录A007在02:51:30Z对真实`/proc`、内核锁与冻结文件的只读核查。

`frozen_inputs_before_physical.json`142个唯一输入当前bytes/hash全部一致，SHA `c34da1cfa5f8dec2a0bba93c282c5c07c71b8ed0bdcfc390330bc3261cce1e01`。相较141创建前清单恰为§15已核四个工程脚本变化及新增recovery helper，无删除；三RTL、XDC及其他生产输入不变。此冻结不是替代342项实际综合源及45DCP父链，而是新增物理入口源码的明确版本。

监督265616/start923136210已由PID1收养，处独立进程组265616，实际持同`.m002_eda.lock` inode169247080的FLOCK WRITE；leader265627/start923136332及controller265743/native implementation266576均为已记录相同start身份。四进程均CPU0–7/nice5，native CPU计数较启动交接增长；资源样本从02:46:43Z连续进入当前运行，最近观测树RSS约7.75GiB，未见资源停止。命令明确无wall/no-output/global deadline，保持192GiB RSS、48GiB/30秒可用内存及30GiB磁盘保护。

独立session和文件stdio降低与执行session的耦合，不保证永久运行，也不解决旧监督失联原因；旧综合UNKNOWN wait和观测空窗保持。此节只确认**新物理真实启动、资源监督与输入身份**，OPT/debug实际物化、clock/reset/CDC、80边界空间分布与后继place/physopt/route仍须各自报告；不预写通过。重要启动核查通过实际消息交主控/A006，已授权运行继续。

## 17. Fresh OPT到显式debug恢复路径的有界预核

主控要求继续核最小恢复来源与时钟/约束验收。当前R004/AT001仍在运行；本节是冻结源码路径核查，**没有观测到OPT终态或预填失败**。源身份与完整判据见[路径核查证据](fresh_opt_recovery_path_review_evidence.json)。五个受影响入口当前字节与运行归档相同，A007未修改生产代码、执行EDA/测试或控制进程。

`hook_batch(opt)`在source/constraint校验后、写`integrity_opt.json`前明确要求`checkpoint_restored_commands`，因此本次`project_runs`不能通过该准入。正常`m002_post(opt)`会先写OPT DCP、completed0与报告/图，再进入guard；是否全部产出仍由实际终态逐项核实。既有`recovery_opt_parent`仅接受已恢复模式、旧upstream parent、独立OPT命令回执与特定CDC失败integrity，不能直接套到本次fresh来源。

A006已收到最小适配要求：等原运行自然结束，保留真实错误/退出/进程与原文件；为E005 fresh OPT建立窄来源分支，绑定本次native OPT成功日志、实际生成检查点/package、准确guard失败、新综合342源/45DCP和本次142工程冻结/执行归档。project hook没有`m002_command opt`回执，不能补造原`opt_command_result`、成功`.end.rst`、upstream parent或缺失integrity；若派生完成证据须标明log-derived。只补未闭合报告/资格和显式debug，不重复已成功synth/INIT/OPT。

另已发现恢复Tcl当前调用裸`place_design`；open_checkpoint的临时工程不会承接候选XPR run的SSI属性。E005恢复须在**实际命令**显式选择`SSI_SpreadSLLs`，保留独立physopt/route Default、原route失败捕获及旧流程适用范围。此问题已实时发A006/主控，等待终态后常规实现，不是新的用户批准门。

时钟/约束验收复用既有判据：本次checkpoint实际part/top/BD、IP cache disable/threads，原XDC metadata/hash和embedded来源，以及新OPT内PHY/hub派生源及真实读取范围；OPT仅获debug资格。实际core条件与显式`implement_debug_core`回执、新DCP、完整debug POST和独立pre_place须先于place。重新核hub输入/输出master/source/period/fanout、黑盒0及完整内部时钟覆盖；新reset图/14局部导出/fanout/BRAM端口和实际Critical CDC用于当前分类。旧canonical8报告只定义已核诊断类别，不代表新图已相同；旧E002图不能替代本次图。只有同一新OPT字节/约束/工具且各来源完整绑定时才复用本轮报告。

XPM两条Constraints18-401与旧日志对象相同的事实仅支持历史一致性；当前合法seq/D及约束作用仍待debug_materialized实际报告。冻结源码还保留`-to`和`-write_valid_exceptions`组合，旧E002 §5.28已实际遭Vivado12-2785拒绝，不能把valid.xdc写成已导出。effective、ignored、scope_override和合法D timing分别按本轮原生语义核；旧CG编号与slack不当作新结果，也不为辅助API导出限制增加新EDA/全局扫描或审批门。完整约束、正式reset/CDC与事务安全保持OPEN。

## 18. 本次新PHY实际禁用缓存来源的有界核查

[独立来源证据](generated_phy_disabled_cache_review_evidence.json)绑定R004/AT001的116文件快照，共61,190,878 bytes；清单记录/hash字段与snapshot manifest全部逐项一致、116份归档size正确，67份小文本（含实际worker script/log/XDC）独立重hash一致。四个DCP的记录/原路径/归档尺寸及两组hash记录相等已核；DCP完整hash采用A006实际快照/校正记录，A007没有重新读取DCP二进制或两份大EDF。

`get_cs_ip.tcl`第23–24行绑定两个ddr4_phy:2.2模块（列表顺序d1、d0），第30–32行绑定本次runtime的两个out/result.dcp，第39–40行明确新project.cache/ip与`ip_cache_permissions disable`。原worker log第47–48行配置相同；第73/1203行两次no-cache-hit、第1181/2119行两次synth_design成功、第1187/2125行各自生成produced DCP、第2133行自然Exiting。这里确认一份脚本/worker流程综合两个PHY模块，不虚构两个独立worker PID。两条实际Parsing XDC的原路径、归档与hash已逐一核。

phy0 produced/result均2,318,792 bytes / SHA `fc9a413b10f6e685a2cd3a3ced8726e8a242e20cc7f377104b7de70bdff7102c`；phy1均2,303,362 bytes / SHA `344efdbbeaf832bb228a97267b39835abb618c7390bff7f1cba505c4a1f91237`。本次只读观察worker-local `.cache/ip`不存在，实际声明project repo存在但无两PHY缓存DCP。**旧validator的失败来自要求一份worker-local cache的谓词，不是这两组produced/output不相等；禁用缓存来源不需要伪造第三副本。** 此观察不扩大为所有可能路径或时刻绝无缓存。

发现原`generated_phy_evidence.json.cache_writes`仍沿用“outputs/cache copies written...”模板，已实发A006；原JSON/快照保持不改，新`generated_phy_observation_correction.json`（4746 bytes / SHA `bece16785002c5239c021c498c507e75c7d3639fde339c073022d6dfa8e583af`）明确撤回缓存写入声称、单列旧失败谓词与两组实际output。A007核其绑定原JSON identity一致并接受该事实更正。generic Added synthesis output文字不作为磁盘cache写证据。

已与A006核定窄分支条件：仅在已资格E005 fresh OPT上下文显式选择；本次stage/runtime归属、script/log的新repo与disable一致、两个确切module/IP/part/output、两次真实no-hit/成功/退出、完整归档及实际worker XDC、每组produced/result实际hash匹配均保持。未知/readwrite配置不能因cache数量0自动放行；旧readwrite三副本分支默认严格保留。主设计后续读取/embedded约束资格与worker读取分开，现场捕获XDC版本也不自动证明精确read-time字节。受影响负例应拒收配置不符、错模块/输出/外来源、缺成功/nohit/退出、产出不等、script-log不一致及清单/XDC篡改。

execution：该来源差异与最小校验路径审核completed，原生OPT仍继续；verdict：当前禁用cache与两份真实新PHY产出有证据，整体OPT父链资格/显式debug/物理结果pending；applicability：本次冻结E005来源，非泛化放松cache规则；review：实发A006/主控，不新增审批、EDA或重跑PHY/OPT。当前142生产输入未热改，新分支实施与实际CPU资格由A006在原stage自然终态后继续。

## 19. Fresh OPT恢复草稿的独立代码审核

[草稿审核记录](fresh_opt_recovery_draft_review_evidence.json)保存8份当时未安装草稿的独立快照、字节数与SHA，避免并发编辑混淆版本。审核仅限代码/设计，未运行validator、CPU测试、EDA或读取DCP；A006仍独占运行与生产树。原生OPT最近工程消息推进到Phase9.1，真实终态和具体失败原因尚未由本次审核确认。

独立log-derived OPT证明的设计可用：原`opt_design`完成与POST失败分别记录，原failed状态和原始材料不改；不制造不存在的`opt_command_result.txt`、成功rst或integrity。新的显式debug回执、DCP、完整POST、当前graph/clock/CDC与pre_place资格仍必须真实取得。恢复Tcl已显式使用`place_design -directive SSI_SpreadSLLs`、`phys_opt_design -directive Default`、`route_design -directive Default`。

已指出并在快照草稿核到修复的项目：PHY script和实际traced log的唯一字面赋值绑定确切module/VLNV/part/board/output/cache repo/disable；约束registry/read身份、162条完整metadata及全部原log read记录重建；授权managed_attempt与manager command→started→status精确链；以固定终态repo观察代替可变现场文件列表进入历史proof；纯`write=False`缺失PID/repo观察时拒收；fresh原始POST虽未资格但完整raw `cdc_opt.rpt`可供当前Critical源/目标probe；optimized supervisor在清理HAP变量后由显式互斥place recovery CLI传父report。

快照尚存三类整合跟进，已实发A006：①继承log-derived证明在符合来源合同的后续恢复中独立传播，不再无条件读旧native OPT receipt；`parent_recovered_place`的新receipt集合按实际恢复phase选取，避免与post_debug/post_place集合冲突，初次log-derived scope也不能写成original_stage_flow。②剩余placed-parent校验仍仅接受裸`place_design`，须接受并强制本E005确切directive；旧分支保持严格原语义。③新report内proof副本、固定观察receipt与proof直接来源纳入完整stage/archive身份。并不要求扩展旧timeout来源契约或预先虚构未来失败，实际终态后按发生的状态做最小适配与有判别力的正负例。

曾提出的`owned_before_reap==[]`附加条件已撤回：该字段在信号发送后记录，不能证明从未cleanup；不将其设为准入。真实native/supervisor失败、stop_reason、实际PID/start身份和原始日志分别保留。`.vivado.begin.rst`中wrapper PID也不自动等同于native PID。

execution：有界草稿审核completed，工程实施/测试及原OPT终态pending；verdict：来源证明设计支持继续整合，尚未取得实际恢复资格或物理结果；applicability：链接所列8份未安装草稿快照，非生产已验证版本；review：实发工程与主控，不新增审批停点，正式reset/CDC和完整时序签核保持OPEN。

## 20. R004/AT001真实自然终态、新OPT与原始报告审核

[独立终态与来源记录](native_opt_terminal_review_evidence.json)确认原监督于04:15:48.372065Z自然终态：native/aggregate各1、stop_reason null、owned_survivors空。40个tracked PID/start与原supervisor共41个身份独立读取/proc均不再存在，command→started→status及授权attempt精确一致。`owned_before_reap`空不被用于证明从未cleanup。

原native日志实际次序为唯一`opt_design`完成成功（0 Errors）→进入POST→写出本次opt.dcp→确切`native project mode has no qualified explicit pre-place debug admission`异常；生成的native Tcl和`.opt_design.error.rst`对应失败分支，成功end rst、原OPT command receipt、integrity及后续debug/place/physopt产物均不存在。原opt_result completed0/BB0不改。本次新opt为218,327,530 bytes / SHA `af634c358eecf869c83cb45c0755d0164b39d5a9f5aed316bcaa52cd3c02919e`，A007独立核stat、两固定hash记录及原日志；二进制hash由A006实算，A007未读DCP。

142原冻结输入的实际保留版本全部重hash一致，21原stage源码archive全部hash一致，162约束metadata与原project完全相等且实际/保留源hash逐条一致；52条主日志XDC读取的line/path/scope/hash完整重建与原JSON一致。新hub快照23文件/884,009 bytes的清单与全部尺寸已核，14份小文本重hash，5条worker读取及observer版本hash已核。观察到的XDC bytes不伪称独立证明精确read-time版本。PHY主日志两条cache-addition消息与固定终态repo0文件/无第三PHY DCP的事实同时保持。

本轮原始Optimized报告：no_clock0、unconstrained_internal_endpoints0、no_input_delay1（pcie_perstn）、no_output_delay2（DDR reset outputs）；Critical 8=6×CDC-10+2×CDC-11，后两条来自xdma user_reset到d0/d1 base reset fanout。WNS+.904/TNS0，WHS−.814/THS−48990.676，WPWS−.012/TPWS−.037，故timing FAIL。LUT815443、CLB Registers1021366、BRAM941、URAM752、DSP5451；这些是本次OPT阶段数值，不与Synthesized值混作同阶段收益。

execution：原AT001 failed，独立来源审核completed；verdict：新OPT执行与独立log-derived继承来源支持，原POST资格失败事实保留；applicability：上述确切E005原stage；review：已实发主控与工程。显式debug、新DCP/graph、完整POST和pre_place仍待本次实际恢复验证，正式reset/CDC安全OPEN，不把内部覆盖0缺口写成安全签核。

## 21. 安装后恢复入口与实际198项CPU回归审核

[安装后独立证据](opt_recovery_installation_review_evidence.json)确认04:17:27Z仅安装5个入口脚本并新增helper/测试；7份当前hash全部对应安装回执。5份旧源码均独立匹配原142冻结与原stage archive，未覆盖历史原料；7个改动路径与真实342综合输入清单无交集。新144输入冻结全量hash一致，SHA `30861cdf97097602d20ec28077efac169671d4a54e9ab082ee9a921cba4de328`。

R002/AT009实际安装后CPU回归于04:18:29.886424Z终态，native/supervisor0、stop null、无残留；原日志198条ok及完整Ran198/31.988s/OK已独立核。包含164既有与34新增恢复案例，覆盖精确PHY来源、旧cache规则、错误module/output/board/repo/attempt、约束漏读/错scope、无成功marker/伪receipt/实际后续命令、纯验证不补观察、同OPT failed POST延续、当前CDC来源和旧archive basename别名正/篡改例。6个CPU监督/被跟踪身份独立核无匹配进程。此前未捕获wait的draft回归仍UNASSESSED，不用本次结果回填。

§19跟进已在当前初次恢复适用范围闭合：初次历史OPT/新debug-place-physopt scope明确；同一OPT字节及原报告的pre-debug失败延续独立携root proof并拒绝后续命令重放；finalizer/route-parent强制本E005实际directives；新proof副本、固定观察和直接/递归身份绑定stage inputs，旧stage_sources同名文件按其原路径核验。原仅timeout来源的pre_place/placed恢复契约保持，未预先放宽；其旧裸place谓词不适用于本次初始来源，若未来真实失败涉及该路径，按实际状态独立补适配。

execution：入口安装/CPU资格审核completed，恢复原生运行及新图资格pending；verdict：当前来源恢复入口具备实际CPU证据，无新增审批停点；applicability：安装回执与新144冻结版本；review：交主控/A006。此项不替代新debug/pre_place或物理/时序结果。

## 22. R004/AT002实际启动与继承OPT/当前CDC来源

[独立启动核查](opt_recovery_startup_review_evidence.json)确认04:20:06.601791Z新监督已真实启动：supervisor345108/start923696505，PPID1/独立PG345108；leader345119/start923696626/PG345119，native345274/start923697105，同为CPU0–7/nice5。实际`.m002_eda.lock` inode169247080由345108持FLOCK WRITE，未仅据元数据声称资源隔离。启动receipt记录345181是Vivado bash wrapper；原生PID按真实进程树另外核对。

实际命令由`--opt-report`指向本次AT001，并设置checkpoint_restored_commands、post_opt_pre_debug、HAP_RECOVERY_OPT_LOG_DERIVED1、OPT_EVIDENCE_COMPLETE0；原parent仍FAIL/incomplete，独立proof SHA `458a75098c185500684514bd68c8341f1bdc30ebe55e3a0979ec72f12fb240d1`与新report副本逐字相同。373行stage inputs包含194个proof直接/递归来源及原archive身份，新副本也绑定；22份新stage archive全部独立hash，298份小文本输入hash独立匹配。75个二进制/超过2MiB输入只核清单绑定与stat，不重新读取DCP/大EDF或泛称独立重hash。

实际probe的5个Critical sources与8个targets精确来自本次raw cdc_opt记录，包含xdma user_reset两条新OPT fanout分类对象；不是只继承旧综合6条targets。CPU completion_facts中的原status/log、新freeze、root proof和installed diff五身份亦独立重hash匹配，实际read-only父链再资格PASS是A006执行记录，A007以独立原始链核查支持其来源。

本次native日志已实际开始`open_checkpoint`本轮opt.dcp，观察前缀尚无新`opt_design`，没有用copy/replay包装成新执行。此为启动/加载开始事实，不预报open完成、显式debug成功或pre_place通过；新graph/clock/reset/CDC与完整物理报告仍待实际产出。原生实现继续，无新增审批门或进程控制。

execution：AT002 running，启动审核completed；verdict：实际来源与监督/输入链支持当前恢复；applicability：当前冻结入口、同一新OPT；review：实发主控/A006，正式安全与时序仍OPEN/FAIL范围保持。

## 23. AT002实际新图POST失败：旧定向CDC报告hash适用性

[独立有界核查](AT002_targeted_CDC_cap_review_evidence.json)确认AT002于04:36:17.349319Z自然native/supervisor1、stop null、无owned；6 tracked加监督共7个PID/start独立核无匹配身份。实际加载本次OPT，未重OPT，未执行显式debug/place/physopt/route，也未取得后续成功receipt/DCP。原opt_result仍completed0/inherited_identical_opt_checkpoint，失败integrity与新graph原样保留。

本次`reset_structure qualified=true, issues=[]`，按冻结判据已覆盖7 async、4 AUX、3 HostSplit四级链与14局部primitive exports；14份导出及相关模型hash独立一致，实例计数每份4。定向读d0 base reset导出可见FDCE INIT1/CLR非反相、首级D1/三级Q→D；HostSplit FDRE INIT0/CE1/R0/四级Q→D。当前记录的d0/d1物理assert源为XDMA user_reset/Q、高有效，HostSplit同UI三链输入同源、末级分别仅接对应LPF。对实际fanout文本仅核具体11个同UI user_reset消费者行及12行定向报告记录，不重扫119,917,902-byte大graph。BRAM实际端口时钟文件hash与688记录范围绑定已核；这里没有声称独立重新证明整图安全。

唯一资格根因为`auxiliary_cdc_limits`中固定旧`TARGETED_OPT_REPORT_HASHES`。4份本次定向CDC完整报告只有2.6–3.4KB，独立与旧E002/R003/AT006原报告逐行比对：每份仅2/12行分隔线宽度、4行日期、6行本次输出路径不同，其余完整正文逐字相同，行数29/29/27/27。实际对象数仍668/668/768/769、LIMIT64；完整Critical分别3/3/1/1条，其source→consumer union精确等于本次继承raw cdc_opt的8条（6×CDC10+2×CDC11）。旧hash适用性失败之后四条TARGETED_CDC_VIOLATIONS_UNKNOWN未获限定解释，导致fanout qualified=false；没有出现新的链/极性/consumer判据失败。

建议已实发A006：为新E005绑定本attempt真实report、native命令、clock pair/name/phase/count、完整tuple与本次完整main report身份；原4条UNKNOWN作为aux对象属性枚举受限事实保留，不降为完整对象枚举成功，其他未知/缺报告/错pair/新tuple均拒收。不能只替换固定hash或借旧图豁免。旧严格历史分支与原failed integrity保持；工程按现有授权完成最小入口修复与CPU资格后继续。

execution：AT002 failed，原因核查completed；verdict：旧完整报告固定hash不适用于本次新日期/路径，同一完整CDC语义有直接证据；applicability：上述本次四份完整报告和原图判据，未全局放松；review：实发主控/工程，正式reset/CDC与事务安全仍OPEN。新显式debug/pre_place/完整物理结果仍pending。

## 24. 当前完整CDC绑定修复、219CPU及AT003实际接续

[安装与启动独立证据](current_CDC_binding_installation_review_evidence.json)核到新144输入冻结SHA `a5643a9e8adb13d6e76f3e78b2dfb6804b9b8ac193f7006f5ceff1b0c4f5a26f`全部当前hash一致；相对上一144冻结仅两Python入口和一测试文件变化，5份预修复archive保全并匹配原身份。安装记录、diff、固定binding与实际重资格记录身份独立匹配。新binding SHA `859459c464e6badc502a5d80adee76e6758954b00337f6c8bd1b7d4a599f3fd3`的26个小来源身份逐项重hash，4个大来源仅核已记录身份/stat，不重读大graph/DCP。

代码窄分支先核E005同OPT、自然失败前debug来源、原约束与producer/archive，再绑定4份本次完整报告。旧四hash常量保留；无新binding仍按旧分支拒收。新分支检查准确report command/name/clock pair/phase/count、tool/design/device/Optimized header、每对3/3/1/1个完整Critical tuple，以及与本次完整main report和原canonical8的union一致；既有binding之后任何原料变化拒收，write=False不补建receipt。4条raw UNKNOWN仍只作为aux get_cdc_violations对象属性枚举的coverage_limited，其他UNKNOWN与未知consumer仍进入fanout issues；正式reset/CDC安全OPEN。

A006实际重新解析同OPT原reset graph/14primitive/688BRAM/fanout+8Critical并取得诊断资格；新的结构结果被代码要求与原qualified reset_structure完全相等，原failed integrity SHA `be4eeb32464319ae164f95b7b2be3f998733b28443b161eb42acb044b5b6d528`仍未改。A007核其新记录`same_OPT_current_targeted_CDC_requalification.json` SHA `b0fc93038f41992130a9e05954cbe59e94ab5488e9382f195f785e530ba9e66a`、原图/导出/BRAM身份与限定继承路径，未替工程重扫119.9MB原图；资格只覆盖同一未变OPT，不覆盖debug或物理变换后新图。

R002/AT010完整安装后回归实际219条ok、Ran219/34.072s/OK，04:45:27.145327Z native/supervisor0、stop null、无owned；198既有+21新例覆盖缺/改报告、错command/name/pair/phase/tool/design、错count/新Critical/不完整union、变DCP/constraint/archive/graph及缺binding。6个被跟踪CPU身份独立核无匹配进程；completion身份与144冻结一致。

AT003已于04:45:47.330804Z真实接续，supervisor362464/start923850572（PPID1/独立PG）、leader362482/start923850699、native362779/start923852212，CPU0–7/nice5；FLOCK WRITE真实归362464。430项stage inputs含新binding及45个直接来源/局部导出，22个stage archive独立重hash。继承graph/fanout/BRAM路径精确指向AT002已重新资格的同OPT原料，root log-derived OPT proof保持；native开始open AT002同一af634c检查点，未重OPT。

execution：修复/实际CPU/接续启动审核completed，AT003 running；verdict：当前完整CDC报告来源与同OPT原图复用有资格证据，未将AT002原失败改成通过；applicability：以上冻结、binding和同OPT原料；review：实发主控/A006，当前接续无待修实质问题，不新增审批门。新显式debug/完整POST/pre_place以及SSI布局、physopt、route仍待实际阶段产物。

## 25. AT003新OPT准入、显式debug回执与物理比较准备

[本次实际小证据](AT003_OPT_and_debug_command_review_evidence.json)独立核到OPT completed1、debug_materialization_eligible1，但diagnostic_eligible0；blackboxes0、COMPLETE_INTERNAL、gate_issues空。7/4/3链与14primitive、688BRAM及fanout已在同OPT绑定下资格，Critical8为诊断分类、new_unclassified0；原4个aux对象枚举UNKNOWN仍以coverage_limited保存，正式reset/CDC安全OPEN。AT002原failed integrity be4eeb...未改，不通过改写历史取得新准入。

实际显式`implement_debug_core`回执phase正确、native_tcl_code0，起止epoch同1792126591。原生日志在本次OPT继承准入之后明确提示`Debug cores have already been implemented`：这证明显式调用真实返回成功，不声称又综合了一份hub或一定发生新网表变换。记录时工具在写debug_materialized新DCP；完整DCP身份、debug POST当前图、hub实际clock关系与新pre_place尚未完成，尚无place命令。后续按真实报告节点独立核，不增加审批门。

[同阶段物理比较准备](physical_comparison_reference.json)冻结旧E003 placed/physopt的小报告身份、正式时序事实和原生SLR/CLB/LUT/控制集行，并复用此前48个placer-final窗口/4个优先热点。当前物理报告未取得，不预填改善。新阶段重点核48 input LUT6×256FDCE/CE、16 Gate LUT1×384FDRE/CE、16 Down LUT1×512FDRE/CE的INIT与真实位置/SLR/负载包络及上游控制源；保留80个边界只支持机制存在，收益仍由当前物理证据判定。

比较严格按placed↔placed、physopt↔physopt；CLB站点占用、LUT用量、局部拥塞窗口、Unique Control Sets、SLR Used与router estimated SLL demand分开。当前全局拥塞可能选择新窗口，旧窗口未出现不等于零拥塞；mixed原生tile范围不可用SLICE包络直接代替。旧E003 route无完整routed结果，不能给出不存在的正式同阶段routed时序改善；本轮联合RTL+SSI策略也不能单独归因每项修改。

execution：本次OPT/显式命令审核及比较准备completed，AT003 debug POST running；verdict：显式调用与当前诊断准入成立，pre_place/完整物理/时序收敛pending；applicability：以上实际回执和冻结比较资料；review：实发主控/A006，未知项继续拒收，正式安全保持OPEN。

## 26. AT003冻结物理报告覆盖与最小补证据范围

[逐项覆盖证据及可执行目标映射](AT003_frozen_physical_reporting_coverage.json)绑定当次两个stage源码、合同第26行及旧比较资料身份。实际冻结入口已有80边界的REF/INIT/DONT_TOUCH、driver LOC/BEL、真实leaf CE/ref计数、load SLR分布和SLICE包络；其自动guard只强制48/16/16边界数量及256/384/512 CE-only总负载，不能把发出INIT/ref字段等同全部属性已经自动断言通过。当前实际物理产物尚未取得。

覆盖缺口有明确范围：①边界driver SLR及相对driver的精确跨SLR负载未发出，内部site→SLR表未保留；②上游索引/控制source仅发出driver LOC及load类型/总数，缺负载位置/SLR分布；③全局congestion最坏窗口不保证固定旧窗口有当前值；④只有overall/-slr利用率，无层次利用率。global `report_slr_crossing -max_nets 32`不保证覆盖目标控制网，不能代替其逐网跨SLR数。

最小目标为`u_compute/u_attention/u_input_buffer/*u_capture_decode`的48个LUT6、`u_compute/u_mlp/u_serial_command/{u_gate_scheduler,u_down_scheduler}/u_projection_repack/*u_output_payload_ce`的各16个LUT1，以及这些实际边界输入端的unique upstream nets；JSON给出完整层次名/实际filter。补driver site/SLR、逐SLR leaf pin数和跨SLR pin数、unknown/unplaced/多driver情况、按SLR的位置包络，并取得三个目标模块的有界层次利用率。保持实际pin与unique cell计数单位，不把总跨SLR负载和SLL物理使用量混为一项。

旧窗口完整48行仍引用`old_congestion_windows_reference.json::reference_rows`，优先四行为North Global6 `(CLEL_R_X27Y183,CLEM_X57Y246)`、South Global6 `(CLEL_R_X27Y199,CLEM_X57Y262)`、East Global5 `(CLEL_R_X54Y234,DSP_X69Y265)`、South Long6 `(CLEL_R_X19Y770,CLEL_R_X49Y833)`。它们是mixed native tile端点，必须保留真实device tile/site/SLR映射，不能直接用SLICE_XY包络替换。若本安装版不能合法查询任意固定窗口的congestion值，保留UNAVAILABLE，另列有来源的资源/连接占用；占用不能冒充拥塞等级，旧窗口未出现也不能填0。新最坏窗口另列，原48行重叠/嵌套和Placer Final Level性质保持。

A006已实际消息确认：当前144冻结与正常实现继续；自然place/独立physopt闭合后，用准确closed DCP按单EDA安排独立最小只读补证据，保留阶段/身份/命令，不重放place/physopt、不热改、不增用户审批门，随后继续已授权完整route。此审核只列取证缺口，不预先断言补证据成功。05:14:21Z仍为debug_materialized completed0/BB0，完整integrity与pre_place/place产物未有；原生日志新增exceptions报告完成，未观察到终态。

execution：覆盖审核completed，原生implementation继续；verdict：冻结入口部分覆盖，物理收益pending；applicability：以上确切AT003冻结入口，非所有历史脚本；review：已实发主控/A006并获工程确认，正式reset/CDC/事务安全OPEN，时序未收敛事实不变。

## 27. 最小只读物理补证据草稿复核

[草稿与后续修复证据](physical_supplement_draft_review_evidence.json)保存A006提供的两个小文本快照及SHA；最终审核脚本10,440 bytes / SHA `355e6e1bee851832d154465f1b6edcf3eb6f974a68cfead4b1a2fb8ac73f9948`，targets 3,969 bytes / SHA `f960f1a2858d7855c7af97d730a3d3a9bf5b72ee32658285000705aa6983fd83`。这是`agent/A006/physical_supplement`草稿，未安装生产、未执行EDA；A007仅静态阅读和字面映射核查，没有运行Tcl测试。

草稿只选80个真实边界及unique upstream nets；leaf pin、unique cell/ref、source-relative crossing、unknown/unplaced/multiple driver、分SLR包络均分别输出。固定48窗用原生tile端点的实际GRID_POINT构造区域，再取真实tile/site/SLR映射、资源站点占用与附着连接；当前固定窗congestion先标UNAVAILABLE，plain help只记录实际API证据，不用资源/连接占用代替拥塞。旧48行的direction/type/level/两端点及顺序已逐项相等，非全器件图扫描。

已实际消息指出并核到三项草稿修复：目标hierarchy必须恰好一个且NAME精确相等才执行`report_utilization -cells`，避免空集合被工具按全设计处理；上游source增加driver_REF_NAMEs；48个窗口各自query/catch，一个失败不跳过后面窗口。query原错误result/options保留，补证据不执行place/physopt/route或改检查点。原生API合法性、产物完整性和实际补证据效果仍须工程真正运行后审核，静态完整不能写成native成功。

execution：本次有界草稿审核completed，补证据NOT_RUN；verdict：取证范围及已修复保护支持，实际数据pending；applicability：上述确切草稿身份，生产144冻结保持；review：实发A006/主控，无新审批门。新debug完整图/pre_place和物理阶段仍等真实产物；此交付不表示后台持续监控或implementation完成。

## 28. AT003完整新debug POST、pre_place与真实SSI布局启动

[本次独立有界证据](AT003_completed_debug_pre_place_review_evidence.json)核对A006完成facts SHA `548828d9741c8d208302a3d79fdb7298e40f66ed0376d9537476bf7b88f75592`及pre_place/完整integrity原料；53项身份中49份小文本独立重hash相等，4项大来源仅核记录绑定与stat，没有读取DCP二进制或119.9MB全图。完整debug result为completed1、diagnostic_eligible1、blackboxes0、COMPLETE_INTERNAL，gate_issues为空。pre_place SHA `b8590bcb628c37e6ed74ae1a3a6181ee9f74bafb59b92e3e9e12913ac56102dc`绑定新DCP396,068,466 bytes / SHA `8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f`及完整integrity SHA `f242f62685e205e21ca3bbdc3a3fa48d3ecc2129904d96e668312dadcb672a43`。DCP大hash采用A006实算，不伪称A007重hash。

本阶段确有新reset graph119,918,238 bytes / SHA `a6b3e6ae3c12ccdceab971d690e6f2969b4d4fc4e8bc7c6503e44bffaeb126ee`和新fanout5,960,745 bytes / SHA `cdbddaa6336760f96bada85aeac1b53717275b7f03318e291543fc6221fc7b7a`；结构/fanout qualified且issues空，7 async、4 AUX、3 HostSplit链的14份本阶段primitive导出独立hash/实例计数全部4级，相关primitive model身份匹配。抽核d0 base reset FDCE INIT1/CLR非反相/CE1/首级D1及三级Q→D；HostSplit FDRE INIT0/CE1/R0和四级Q→D。实际fanout只抽具体11个XDMA user_reset消费者，逐一对应8个d0/d1 CLR及3个同UI HostSplit首级D；整图语义由A006本次解析，A007不重做大图扫描。

本阶段小BRAM时钟probe独立核688条/688独立endpoint，其中RAMB36E2 672、RAMB18E2 16，DDR0 mmcm_clkout0 456、DDR1 mmcm_clkout0_1 232，逐行cell/CLKBWRCLK/IS_CLOCK一致。当前完整raw CDC实际8条（6×CDC-10+2×CDC-11）和具体source/target与限定分类一致，new_critical0；正式reset/CDC及下游release/transaction安全仍OPEN。新fanout的auxiliary.coverage=`not_limited`仅表示当前没有raw cap sentinel：冻结Tcl在非OPT阶段跳过定向aux get_cdc_violations对象枚举，不能把该字段解释为本阶段对象枚举完整；旧OPT四UNKNOWN/coverage_limited及失败历史保持。

实际hub input及两输出均mmcm_clkout5_1/20ns，源为DDR1 MMCM CLKOUT5→BUFGCE，master为default_250mhz_clk2_clk_p/4ns；两输出各265端点，共530个不同端点，全部同实际时钟，effective hub XDC身份匹配。raw debug_proof `verified=0`和声明300MHz/实际50MHz/divider=false的不匹配原样保留，与独立actual timing-clock relationship_qualified分开；显式implement_debug_core回执0及原工具“already implemented”仍只证明真实调用成功，不声称又生成新hub或一定发生网表变化。

当前constraint mode为embedded_checkpoint_inherited，162 metadata、175 source hashes、13 generated source archives及其候选说明与已核OPT父资料完全一致；actual_reads明确new_actual_reads=[]，未伪造本stage新读入。原OPT failure/incomplete状态与独立log-derived父proof保持，只有新debug/pre_place被本次实际资格。no_clock0/unconstrained_internal0；外部input1/output2缺delay仍独立保留。两XPM原查询各命中LUT4+FDRE，LEGAL_EXCEPTION_TARGET已选实际FDRE及D端；effective报告仍Invalid endpoint、ignored无条目、scope_override为CG171 totally overridden，实际定向D时序均报告4.158ns slack/5ns requirement。`-write_valid_exceptions`与`-to`不兼容的Vivado12-2785及valid_unavailable原证据保持，无有效valid.xdc，不能据此宣称原vendor异常约束已经修复。

新debug时序WNS+0.904/TNS0、WHS−0.814/THS−48990.676、WPWS−0.012/TPWS−0.037，hold992156端点/PW5端点，因此timing FAIL。raw DRC本阶段summary只有6类warning/15914 checks，原header保留Synthesized/Floorplan checkpoint_opt；不把该报告称作已placed/routed signoff。

原生日志第207行明确debug COMPLETE_INTERNAL，208行真实`Command: place_design -directive SSI_SpreadSLLs`，215行工具确认directive；随后precondition DRC0 Errors并进入Phase1.3。本次读取时没有place成功receipt或完整placed结果，不能将启动写成完成。正常implementation继续，不等审核签字；§26–27固定窗口/层次/目标SLR补证据仍按自然闭合点与单EDA计划处理。

execution：本次debug/pre_place/实际place启动审核completed，原生place running；verdict：当前诊断准入和真实SSI调用有证据，完整物理结果与收益pending，timing FAIL；applicability：上述确切本阶段新图、DCP及冻结父链；review：实发主控/A006，不新增批准门。physical_signoff=false，正式安全/外部IO/板级验收保持独立OPEN。

## 29. AT003实际placed资源、80边界、时序与拥塞独立比较

本节汇总在完整POST前已取得的正式小报告；完整placed资格随后见§30，不回写早期观测。真实`place_design -directive SSI_SpreadSLLs`原生Tcl0，1792128495→1792136882，8387秒；日志1092–1093明确成功及02:19:47。实际place.dcp 579,966,904 bytes / SHA `32b4af05f2ba43c8f63ec8ee44f7fcd40dbc1d6f5012638d404bb0cb6678bdf2`，A007核stat、生成日志和A006绑定，不读取或重hash大型DCP。原生Place46-14高度拥塞警告保留，见[过程风险证据](AT003_place_process_risk_review_evidence.json)。四条共享入口pointer日志中的2067→133、1968→124、2067→133、1632→103仅为约束/macro后可优化子集数，不能称实际总fanout降幅，也不与本次80个CE边界混算。

[资源证据](AT003_place_resource_pre_POST_review_evidence.json)按同器件、同约束、同为Fully Placed的E003旧报告比较。标签保留原生“CLB Registers”。

| 原生指标 | E003旧placed | E005本次placed | 差值 |
| --- | ---: | ---: | ---: |
| CLB LUTs | 814911 | 801751 | −13160 |
| CLB Registers | 1019696 | 1017050 | −2646 |
| Unique Control Sets | 22399 | 22369 | −30 |
| CLB sites | 146472 / 99.11% | 143802 / 97.31% | −2670 |
| Block RAM Tile | 941 | 941 | 0 |
| URAM | 752 | 752 | 0 |
| DSPs | 5451 | 5451 | 0 |
| SLR2↔SLR1 SLLs Used | 9451 | 8509 | −942 |
| SLR1↔SLR0 SLLs Used | 8812 | 10474 | +1662 |
| Total SLLs Used | 18263 | 18983 | +720 |

新SLR0/1/2的CLB分别48769/49185/45848，占99.00/99.85/93.07%；整体资源下降，SLR1仍接近填满。SLLs Used是原生资源指标，与目标网跨SLR负载pin数及router Estimated SLL Demand分别记录。

[正式时序证据](AT003_place_timing_pre_POST_review_evidence.json)来自完整时序报告summary，并保留12项原生数值和最坏路径样本：

| 指标 | E003旧placed | E005本次placed |
| --- | ---: | ---: |
| WNS / TNS (ns) | −1.819 / −818.651 | +0.103 / 0 |
| setup failing endpoints | 1014 | 0 |
| WHS / THS (ns) | −0.620 / −2150.556 | −0.695 / −2145.408 |
| hold failing endpoints | 33141 | 30885 |
| WPWS / TPWS / PW failures | 0 / 0 / 0 | 0 / 0 / 0 |

setup WNS改善1.922ns；最坏hold恶化0.075ns，THS改善5.148ns且hold失败端点减少2256。整体timing仍FAIL（hold），+0.103ns仅为布线前估计余量。新最坏setup为PCIe CORECLK→XDMA rdcplpend D，data3.248ns（logic0.941/route2.307）；旧为同源/同clock group→RQ_FIFO Head CE，data5.070ns（logic0.669/route4.401）。新最坏hold为XDMA aa256 bit185→PCIe SAXISCCTDATA bit185，旧为bit51。端点/bit不同，不能说相同路径改善；该组合试验也未隔离RTL与SSI策略各自因果。

[80边界证据](AT003_place_boundary_pre_POST_review_evidence.json)独立逐项比较同一cell set、REF/INIT/DONT_TOUCH1及实际typed CE负载，与新综合零差异：48个input LUT6×256 FDCE/CE=12288，16个Gate LUT1×384 FDRE/CE=6144，16个Down LUT1×512 FDRE/CE=8192，总26624实际CE pins。80个driver LOC/BEL非空；14个upstream source的实际负载数量/类型与综合相同。

input全部12288负载在SLR2，但每个256-pin组的SLICE坐标包络跨度X59–68/Y186–192，单SLR不等于布线紧凑。Gate负载在SLR0/1为3069/3075，Down为5120/3072。79组负载单SLR；Gate row5为SLR0 381、SLR1 3，driver实际LOC=SLICE_X96Y357/BEL=SLICEL.C5LUT。driver SLR尚未观测，不以Y坐标推断；该组跨SLR负载严格下界为3，不能填精确3。Gate包络跨度X16–42/Y13–177，Down X17–111/Y46–138，均为SLICE坐标步数，不是native拥塞tile窗口或物理距离。已保存[56个unique driver site映射参考](AT003_placed_driver_sites_for_device_mapping.json)，绑定80边界及14 upstream source的原placed LOC；后续同器件site→SLR映射可复用device拓扑，不能用physopt时刻LOC替代placed LOC。

[拥塞独立证据](AT003_place_congestion_pre_POST_review_evidence.json)重hash当前报告SHA `0b95a7cc6612be99e5208b93bad917c5edb2387dc18e63cb76f226943b6af868`，48条原生行与A006 facts逐行相等。Global/Long/Short各四方向，共12种组合的新旧峰值均Level6。48行存在重叠/嵌套，不能解释为48个独立失败；相同粗等级不证明精确需求相同。

| 本次Global Level6方向 | 原生最坏窗口 |
| --- | --- |
| North | `(CLEL_R_X12Y416,CLEL_R_X41Y479)` |
| South | `(CLEM_X14Y417,CLEM_X44Y480)` |
| East | `(CLEL_R_X15Y412,CLEL_R_X45Y475)` |
| West | `(CLEL_R_X13Y415,CLEL_R_X43Y478)` |

四窗口均报LUT77%、RAMB100%、DSP89–91%，URAM依次75/90/87/87%；Cell Names含Gate projection_repack/SwiGLU及Attention projection的u_center12/u_region1_cols4_7。这是热点关联线索，不能据此认定某CE网造成拥塞。新旧完整(direction,type,window) tuple无一精确重合；旧48固定窗口在本阶段的值仍NOT_MEASURED，未被选入最坏列表不等于0或改善。报告为Placer Final Level，不能冒充route拥塞或合法布通结论。全局`-max_nets 32` SLR report未出现本次target片段，不能替代目标网跨SLR量化。

阶段判断：80控制机制和资源/setup改善有实际支持；SLR1 99.85%、SLLs Used增加720及12类峰仍Level6说明布通风险仍高，hold尚失败。合同允许结构落实、诊断资格合法但改善不足的候选继续完整route；不因本风险另加批准门。层次利用率、placed上游负载分布、精确driver跨SLR与旧固定窗口仍按§26–27补证据，不能由physopt数据推填placed空缺。

execution：本节有界比较completed，implementation继续；verdict：资源/setup与控制机制supported，整体timing FAIL、routability未验证；applicability：上述确切AT003 placed与E003同阶段基线；review：内部独立审核，真实消息交主控/A006，非用户签核。

## 30. 完整placed POST新图闭合与独立Default physopt真实处理

[本次有界审核证据](AT003_completed_place_POST_physopt_command_review_evidence.json)核A006 completed-place facts 5335 bytes / SHA `821b78f0b61f210e300ab2fdf7b6a4ab00bec27cefef291a6ee9dce42608eede`。57项绑定中52份小文本独立重hash匹配，5项大来源仅核stat及记录绑定。place_result completed1/diagnostic_eligible1/blackboxes0/COMPLETE_INTERNAL，integrity SHA `0bd12504fabd28c6de1e710df56c24f439777ad2c7d8b54c176a9a73629078e4`且gate_issues为空；原生日志1135已明确placed诊断阶段完成。此为新placed阶段真实资格，原OPT失败历史不变。

新reset graph119,929,146 bytes / SHA `ee66f2ea3ab131a555a7afc9e7d5a07709a7d046ef1dce45d7878a0578f1179c`、fanout5,986,831 bytes / SHA `db5ee4af3162d67126a38af46da6bbc81df684450d43b6b4cee5d1090b8e7ee7`，来源确为place。A007不重扫大型整图；独立核14份本阶段primitive导出，各4级、实例集合和effective参数与已审核debug相同，7 async/4 AUX/3 HostSplit链保持。抽核本阶段11个XDMA定向消费者与预期精确集合一致；688条BRAM probe各自cell/CLKBWRCLK/IS_CLOCK关系成立，672 RAMB36E2+16 RAMB18E2，DDR0/1时钟456/232。d0 ready/base计数从debug各6362变为placed各6416（+54），保留真实阶段差异，不宣称fanout所有数量不变；本次完整parser仍qualified/零issues。

raw CDC实际6×CDC-10+2×CDC-11，8条source/target tuple与已审核debug相等、new_critical0。非OPT auxiliary `not_limited`仍只指无cap sentinel，不代表进行了定向CDC对象枚举。正式reset/CDC、下游release/transaction及外部IO继续OPEN。no_clock0/internal unconstrained0；外部no_input_delay1/no_output_delay2原样保留。

placed约束mode=embedded_checkpoint_inherited，父constraints_debug_materialized身份独立匹配；162 metadata、175 hashes、13 generated archives及候选来源与debug完全相等，actual_reads新读入为空。完整synthesis来源字典与先前审核的debug父绑定相等，pre_place原证据身份保持。新完整POST支持后继诊断命令，不等于physical signoff。

日志1136真实调用`phys_opt_design -directive Default`，回执1792138805→1792138830，Tcl0/25秒。日志1140内部Estimated WNS=+0.255/TNS0；1141明确setup物理综合优化全部跳过；1142明确“No setup violation found. The netlist was not modified.” 因而该成功调用不是新的优化收益，更不能推断hold修复。内部估计+0.255与正式placed+0.103分别保留，不混作同类时序对比。

日志1158已有physopt.dcp generated；本次证据截点physopt_result仍completed0/eligible0。A006随后实发新physopt DCP 579,969,232 bytes / SHA `766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d`及同part/top/board/build包身份；该消息保留为工程新里程碑，完整physopt POST及成功route父链须后续实际审核，不能由25秒命令0替代。

A006实际消息转达主控调度：合格physopt自然闭合后优先一次完整Default route；route终态后在单EDA资源内分别打开closed place/physopt DCP补齐固定窗口、层次和source分布。无需重放place/physopt；缺项在补证据成功前继续NOT_MEASURED。该顺序是当前真实工程安排，不是新增用户决定，也不设审核签字等待。

execution：本次完整placed与physopt命令核查completed，原生后继POST继续；verdict：新placed诊断准入supported，独立physopt原生成功但未修改网表，完整physopt/route资格pending；applicability：本次新图、确切父链与原生调用；review：内部独立核查已实发，用户/全局签核未替代，physical_signoff=false。

## 31. 独立physopt已保存DCP及正式资源/时序部分结果

[本次小证据](AT003_physopt_saved_DCP_partial_reports_review_evidence.json)核A006新checkpoint observation和disposition，独立重hash其command/disposition/utilization三项小来源全部匹配；physopt DCP579,969,232 bytes的stat匹配，SHA与包身份由A006实算，A007未读取大DCP。该DCP为本次独立Default原生命令之后真实保存，完整POST尚未闭合。

新utilization原生状态为Physopt postPlace；除报告header以外正文与本次placed逐字一致。新formal timing同为Physopt postPlace，A007有界读取前145行，12项summary全部与本次placed相同：WNS+0.103/TNS0/setup0；WHS−0.695/THS−2145.408/hold30885；WPWS0/TPWS0/PW0。因此没有本次placed→独立physopt的正式时序或资源改善，符合原生跳过setup优化、网表未改的说明。完整2.39MB timing报告未由A007重新hash，已保存实际读取前缀的SHA和stat范围；不能将命令内部+0.255估计替代正式+0.103。

execution：本次有界部分结果审核completed，原生完整POST继续；verdict：成功保存新DCP及正式部分报告supported，hold FAIL、完整physopt/route父链pending；applicability：本次独立physopt阶段；review：内部核查，不新增签字停点。

## 32. route终态后双阶段只读补证据草稿增量审核

[静态审核与三个文本快照](two_phase_supplement_draft_review_evidence.json)保留本次core/targets/two-phase-driver身份，原§27 reviewed_v1保持。新driver在单native会话按jobs顺序source core，各自open精确closed DCP，phase receipt/result/options分开；core NO_EXIT允许单阶段失败后继续下一阶段，并保留原逐query错误。EXCL不覆盖旧产物，未加入place/physopt/route/write_checkpoint命令。新56个saved placed LOC与A007参考顺序逐项一致，实际site映射要求同part、唯一精确NAME和真实siteSLR；没有把当前driver位置替换原placed LOC。

当前只是未运行草稿。已实发A006一项普通完善：实际launcher必须绑定place/physopt恰好两项及各自closed DCP hash/父链、不同输出目录，在jobs消费前拒绝空/重复phase或输出目录，防止空jobs出现aggregate0。尚未核到该补强的最终版本，不写作已经完成。固定窗口仍计划输出原生tile/site资源占用；无合法API时congestion字段保持UNAVAILABLE，不能由占用反推拥塞等级。

execution：静态增量审核completed，补采NOT_RUN；verdict：分阶段身份/只读取证方向支持，原生API和最终产物pending；applicability：上述保存的草稿版本；review：实发A006，当前完整implementation继续，route优先及终态后单EDA补采次序不变。

## 33. route后补采启动器与三项普通修复闭合

A006实际followup要求有界只读审核`run_closed_comparison.py`及双phase新守卫；[初版快照](closed_comparison_launcher_review_initial/review.json)保存182行/11,314 bytes启动器及Tcl、8项隔离guard测试回执。A007未运行脚本、测试、EDA或控制进程。双phase已补exactly2、place/physopt集合、不同规范化DCP/输出及输出不复用，8项owner测试回执与当前driver SHA相符；测试范围仅隔离Tcl输入守卫，不是原生补采通过。

独立指出三项普通缺口并真实消息交A006/主控：route wrapper自然失败不一定执行过route_design；补采finally的残留清理不能伪装正常成功；新补采不能忽略此前E005/R006未闭合或幸存attempt。A006随后修复，[最终静态复核快照](closed_comparison_launcher_review_fixed/review.json)启动器15,639 bytes / SHA `62a096ff8133fdc2a2ede6aa4a53bbaa74a492004e1af64542bd9a4cc80ef93a`。

最终草稿要求真实`route_command_result.txt`的phase=route、精确`route_design -directive Default`、native Tcl0或1及有效起止，并绑定原receipt；正常native退出且没有owned rows时不调用终止，异常清理记录清理前状态并stop/125，持续幸存则保留EDA锁及清理历史重试。所有E005已started attempt须有闭合状态或原综合已核恢复例外，并检查已登记PID-start及可用的detached supervisor身份确实不活跃。上述问题在静态版本中闭合，尚无实际补采结果。

父链调用安装版parent_place，适用于本次fresh-OPT recovered路径；guard、evidence及synthesis-recovery来源纳入既有144freeze。R006每次采用全新AT/report，归档启动器/Tcl/jobs，各自原place/physopt DCP预期SHA与144输入在前后检查，归档query source结束后复核。单EDA flock、8 CPU/nice5/max8线程和原192GiB/48GiB持续30秒/30GiB资源保护保持，没有墙钟或无输出强停。补采脚本没有place/physopt/route/write_checkpoint操作。

execution：最终静态复核completed，补采NOT_RUN；verdict：本范围未见剩余阻断问题，原生API、实际输入/输出与真实资源闭合仍以执行后证据为准；applicability：上述确切快照，不把未来草稿修改自动纳入；review：三项普通修复已实际消息闭合，不挡当前route，不替用户签核。

## 34. 完整physopt POST、新图、自然终态与成功route父链

[完整独立审核证据](AT003_completed_physopt_POST_parent_review_evidence.json)核A006小facts 4440 bytes / SHA `e6838493806fc5251ffd4df44e9171557d0cc52f4624786d125c6c83a7233823`。70项来源分为41份新小文本独立SHA匹配、21份复用先前已核小身份并核stat、8份大来源仅核记录SHA绑定/stat；未重扫大图、大DCP或全部144输入。A006全144复核unchanged与安装版parent_place实际接受记录单列，A007不伪称重新执行该validator。

新integrity SHA `3b3d6275743ac3239099ddb2ad134370845e9bcc0560b6e26839f70e7172ba2e`、constraints SHA `3d1ab4c599bca06ec577b94535979466b4c9a1e887ea43230531cd4d5f5f410d`实际匹配。physopt_result completed1/eligible1/blackboxes0/COMPLETE_INTERNAL，gate_issues=[]。本阶段新reset图119,929,202 bytes / SHA `0f3abdefb8f5af203981a065e76ad61b07169ff9329f5e2cf9c0fd76cbd76e4a`和fanout5,986,843 bytes / SHA `c705da438ec07ae35bbf7a029017bdb43e5ead0648b86ac0785145ad817dfea7`来源成立；14份primitive各4级、精确实例与effective参数逐项和placed相同，7/4/3链、11XDMA消费者、688BRAM探针关系保持。所有consumer_counts与placed相同。raw CDC仍6×CDC-10+2×CDC-11，其8条tuple和placed相同，new0；结构/fanout均qualified且无issues。

约束继承placed父身份，162 metadata/175 hashes/13 archives以及候选来源完全相等，阶段new_actual_reads为空。内部no_clock和unconstrained均0；外部input1/output2缺delay及formal reset/CDC/release/transaction安全OPEN。非OPT auxiliary不执行定向对象枚举的原范围继续保留。

新diagnostic父链明确execution_mode=checkpoint_restored_commands、restored phase=post_opt_pre_debug，执行范围为`new_debug_place_physopt__inherited_native_project_opt`。新debug/place/physopt三回执均原生0；historical_command_receipts与伪project-run native receipts均为空，继承OPT证明另有真实来源，原失败不重写。成功checkpoint绑定实际physopt.dcp 579,969,232 bytes / SHA76621792…，pre_place仍绑定已核b8590bcb…，synthesis字典与完整placed完全相同。父链声明12份必要正式报告并有各自身份，不把该数字等同所有阶段文件总数。

原生日志实际完成physopt hook、close_design和controller，于2026-10-16 08:57:21 UTC自然退出；监督status于08:57:32.868921Z完成，native0/aggregate0、stop_reason=null、owned_before_reap=[]、owned_survivors=[]。A007按18条登记PID-start直接检查，均已不在。当前A006已将单EDA资源交AT004，不能把旧锁释放历史写为现在没有EDA。

与旧E003**同阶段独立physopt**比较，区别于§29旧placed基线：

| 指标 | E003旧physopt | E005本次physopt | 差值 |
| --- | ---: | ---: | ---: |
| CLB LUTs | 814935 | 801751 | −13184 |
| CLB Registers | 1019698 | 1017050 | −2648 |
| Unique Control Sets | 22410 | 22369 | −41 |
| CLB sites | 146472 | 143802 | −2670 |
| Total SLLs Used | 18282 | 18983 | +701 |
| WNS / TNS (ns) | −1.290 / −762.165 | +0.103 / 0 | +1.393 / +762.165 |
| setup failing endpoints | 980 | 0 | −980 |
| WHS / THS (ns) | −0.620 / −2150.556 | −0.695 / −2145.408 | −0.075 / +5.148 |
| hold failing endpoints | 33141 | 30885 | −2256 |

BRAM941/URAM752/DSP5451不变。SLR2↔1 Used9471→8509（−962），SLR1↔0 Used8811→10474（+1663）。整体timing仍FAIL；当前placed→physopt无资源/正式时序收益，不能把新旧组合变化归因于本次被跳过的physopt优化。

[新physopt边界与拥塞独立证据](AT003_physopt_boundary_congestion_partial_review_evidence.json)确认80边界和14upstream整个TSV bytes与当前placed相等；congestion报告除header外正文逐字相等，48行/12方向type峰6复算一致。该physopt阶段报告原生仍为Fully Placed/Placer Final Level表，不是新route拥塞测量；driverSLR、精确crossSLR、旧固定窗口和层次等补采缺项保持原范围，不由网表未改推填。

execution：完整physopt/自然终态有界核查completed，AT004 route独立推进；verdict：本次成功诊断父链supported，setup/PW通过但hold FAIL，布通尚未验证；applicability：本次完整新图/约束/原生命令及同阶段旧基线；review：已实际消息交主控/A006，不设置签字等待，physical_signoff=false。

## 35. AT004真实监督启动与精确physopt父DCP打开

[实际启动审核证据](AT004_actual_route_launch_parent_review_evidence.json)核新AT004授权、监督及report command、阶段输入与父身份。真实supervisor611388/start925368939、native611607/start925370167及另外3个登记进程均通过当前PID-start检查且nice5；实际flock owner为611388。监督无墙钟/无输出强停，父HAP_PLACE_REPORT_DIR指向AT003，HAP_RECOVERY_CHECKPOINT精确为上述physopt.dcp，synthesis字典相同。56条stage输入中21条与既有144freeze交集的SHA字串相同；A007未重新hash所有输入，A006启动前144实际复核单列。

日志第59行真实`open_checkpoint`该DCP路径，随后恢复ShapeDB/timing archive。在本次证据截点未观察`Command: route_design`，没有route命令终态receipt或监督status，因此只交付实际监督入口及父DCP加载事实，不提前写路由内核开始或布通成功。正常运行由A006继续；后续真实命令/异常/终态事件复用A007集中核查，不把本轮交付结束写成后台监控。

execution：本轮有界启动审核completed，AT004正常running；verdict：实际启动与正确父DCP打开supported，native route invocation/结果pending；applicability：确切AT004启动及记录截点；review：实际消息交主控/A006，无新门。

## 36. AT004原生Default route已实际进入Phase 1

[最小独立启动证据](AT004_native_Default_route_started_review_evidence.json)只读当前原生日志前134行，并保存该读取前缀SHA及真实行号。第59行打开§34–35已核的AT003 physopt.dcp；第120行确认Vivado2025.2 build6299465，121行open_checkpoint实际elapsed00:09:24。第122行明确`Command: route_design -directive Default`，128行确认Router directive Default，129行确认最多8 CPUs，131行实际进入`Phase 1 Build RT Design`。据此将§35时刻“调用pending”推进为真实router开始，不回写先前截点。

本次继承已完成的完整physopt POST、诊断父链和AT004实际PID/锁审核，没有重扫DCP/整图/144输入。检查截点无route命令终态receipt、无route.dcp；启动不证明布通或时序收敛，先前hold FAIL/Level6风险与正式安全OPEN继续保留。后续按原生自然终态或重大异常再集中审核，正常长运行不持续重复报告，不声称后台监控。

execution：最小启动审核completed，原生route running；verdict：Default调用、8 CPU及Phase1已实际支持，路由结果pending；applicability：本次AT004及确切已核父链；review：真实消息交主控/A006，无新增停点。

## 37. AT004中间拥塞、前两轮迭代与E003同名route阶段

[独立比较证据](AT004_vs_E003_route_intermediate_comparison_review_evidence.json)核AT004保存的初始拥塞、overlap及progress快照，10项被引用小文件身份全部匹配，每条被选记录的native_line/raw与对应不可变prefix逐字相等。初始facts SHA `ca4aa1097277afe8092ba24ddf784c7aab7a1402694d4dafd03f665362ed4051`及35-447 facts SHA `5c9f258293f2bc5824c47c2e35f3a959884beec0d9004d89b7701b7e56bf26ec`与实际消息一致。对照直接取E003 R003/AT001已闭合原生日志，并保存[前430行有界摘录](E003_route_initial_and_iterations1_2_native_excerpt.txt)；不读取大型DCP，不执行EDA、停止、换策略或重跑。

比较范围为相同工具build6299465、器件及router同名阶段，均原生最多8 CPUs。E003原生命令字面是`route_design`（默认调用），E005为显式`route_design -directive Default`，保留此区别。E005有新RTL及SSI_SpreadSLLs布局，输入网表/布局工作量不同；该比较不能分离RTL与布局策略因果，也不是等工作量性能benchmark。

E005日志245与E003日志263的Route35-447均说明拥塞妨碍全部nets布线，router优先完成连接、其次时序。两次初始表后的35-448均明确Global/Short Level7 (128×128)，35-581均明确Timing Level7 (128×128)。Long等级未独立明示，不从size反推；两次均未给Timing窗口列表。这些是**router Initial Estimated Congestion**，不能与placed Placer Final Level6直接相减或当同一测量。

独立解析新旧各4方向×3类型=12组、各60窗口（每组5条），新12组/60窗与A006 facts完全相等。下表百分比保留原生`% Tiles`口径，差值为百分点，不求和为全局拥塞面积。

| 方向 / 类型 | E003 size | E003 % Tiles | E005 size | E005 % Tiles | 差值(pp) |
| --- | --- | ---: | --- | ---: | ---: |
| North / Global | 128×128 | 10.12 | 128×128 | 20.09 | +9.97 |
| North / Long | 128×128 | 23.59 | 128×128 | 30.52 | +6.93 |
| North / Short | 16×16 | 3.99 | 128×128 | 14.74 | +10.75 |
| South / Global | 128×128 | 14.60 | 128×128 | 13.68 | −0.92 |
| South / Long | 128×128 | 33.84 | 128×128 | 27.87 | −5.97 |
| South / Short | 32×32 | 3.42 | 64×64 | 7.77 | +4.35 |
| East / Global | 64×64 | 5.89 | 128×128 | 14.45 | +8.56 |
| East / Long | 64×64 | 9.84 | 128×128 | 15.02 | +5.18 |
| East / Short | 32×32 | 8.04 | 128×128 | 17.52 | +9.48 |
| West / Global | 64×64 | 7.68 | 128×128 | 14.37 | +6.69 |
| West / Long | 64×64 | 12.41 | 128×128 | 14.19 | +1.78 |
| West / Short | 64×64 | 9.06 | 128×128 | 19.03 | +9.97 |

新%Tiles有10组更高，仅South Global/Long两组更低；8组报告size扩大、4组不变。60条窗口保留原生INT两端及对应物理tile两端，不把离散size标签改写为坐标差。新旧完整type/direction/INT/physical tuple仅3条相同，均为South Long的重叠子窗；其他旧窗未被新最坏列表选中不等于其拥塞为0或改善。窗口重叠/嵌套，60条不代表60个独立失败。

前两轮仅按原生同名阶段保存完整出现顺序：

| 原生阶段 / 指标 | E003 | E005保存截点 |
| --- | --- | --- |
| Phase5.2 Iteration1 overlap节点序列 | 1861520 → 988355 → 501530 | 2183923（仅一次） |
| Iteration1中间WNS / TNS (ns) | −17.994 / −2261923.747 | −13.535 / −1866986.607 |
| Iteration1中间WHS / THS | N/A / N/A | N/A / N/A |
| Phase5.3 Iteration2 overlap节点 | 2025963 | 2472092 |
| Iteration2完成或中间timing | 有阶段完成；无对应中间timing行 | 当前prefix无完成或timing行 |

E003 Iteration1有三次内部计数，E005只有一次；即使同名iteration，日志也未证明每个计数来自相同内部子步骤/固定工作集合。不能只挑旧最后501530与新唯一2183923声称相同子步骤的收敛率。Iteration2新旧相差446129个报告节点仍是过程比较；跨轮增加不是单调收敛进度条。**Number of Nodes with overlaps是节点计数，不是congestion-failed signals、未布通net数或最终失败数。** Phase2.3 clock nets的overlap0也不能外推全设计布通。

新Iteration1中间setup数值较旧少负4.459ns（WNS）及394937.140ns（TNS），但这些是未完成路由的Route35-416估计，不能作为正式routed时序改善或最终收敛证据。WHS/THS原生N/A保留字符串及numeric null，不当作0或PASS；与前置physopt的hold FAIL分属不同阶段。

原生Time行是router累计CPU/elapsed，不能直接把累计值当单轮耗时。可核到的elapsed如下：

| 完成点 | E003累计elapsed | E005累计elapsed |
| --- | --- | --- |
| Phase4.2 Update Timing | 00:29:42 | 00:20:28 |
| Phase4 Initial Routing | 01:01:40 | 00:55:52 |
| Phase5.1 Iteration0 | 01:06:53 | 01:01:07 |
| Phase5.2 Iteration1 | 03:44:12 | 02:11:27 |
| Phase5.3 Iteration2 | 05:05:28 | 尚无完成Time行 |

由相邻完成点差分，Iteration1 elapsed为旧02:37:19、新01:10:20；旧Iteration2为01:21:16，新Iteration2尚不能计算。新Iteration1较早结束是观察事实，不推导等工作量加速、剩余运行时长或收敛比例。计数行本身没有精确native时间戳；新I1计数首次保存于10:35:25Z、中间timing说明保存于11:22:44Z、I2计数保存于12:01:24Z，这些仅是观测/归档时间，不能替代原生事件发生时刻。

progress `capture_003`（12:18:50Z）与`capture_002`及overlap capture002的prefix逐字相同，SHA均 `117fb04f2d8811af44973a099e3589bfdb3c384a079fa3a0488ac198b88550d3`。producer v2新记录的35-447/448/581仍是原245/381/383行，全部早已出现在初始prefix；因此是回填原告警，不是12:18新发生三次异常。35-448/581原生位置在Phase4 Initial Routing完成之后、Phase5开始之前；capture最近phase标签不替代这一日志先后关系。

execution：本次有界中间比较completed，AT004由A006正常持续；verdict：多数初始拥塞组的报告覆盖更大、计数/中间timing已核，尚不能给新route终态或方法最终判断；applicability：上述不可变prefix至新406行及旧同名阶段，不把旧终态混入新过程；review：已真实消息交主控/A006供终态复核复用，Default不改、无重跑/强停或新增审核门，等待真实终态或重大事件再续审。

## 38. AT004 Phase9合法布通失败与末期原生诊断

13:27:55Z独立保存[原生日志前缀](AT004_phase9_failure_native_log_observed_prefix.txt)至658行，51088 bytes / SHA256 `7f840327c1ea7d7499d7f3f1b48327098732777c9e34c61c293ecc4b31489e50`，对应[保存身份](AT004_phase9_failure_native_log_observed_prefix_identity.json)。[同阶段独立证据](AT004_phase9_failure_same_stage_review_evidence.json)逐项保留新旧原生行号、20个末期窗口、top10节点及所有列出的net/InstTerms、完整同名阶段时间；[解析脚本](review_AT004_phase9_failure.py)仅处理这两个小日志，Phase8统计明确在对应阶段取值，避免与早期clock-only零重叠表混淆。E003已闭合日志另存[原文副本](E003_closed_route_native_log_final_comparison.txt)，旧源未改。

本次log520 Route35-162为**758463 signals因拥塞失败**；log464和630为**1148579 overlap nodes**；log626明确Verification failed，630明确Design is not legally routed。这是当前候选合法布通失败的原生证据。Phase8的failed/unrouted/partial各0只是该表内连通状态，不能覆盖独立Phase9合法性失败，也不能将信号/节点两项相加。与E003同阶段对照：

| 指标 | E003 | E005 AT004 | 新−旧 |
| --- | ---: | ---: | ---: |
| Phase9 overlap nodes | 245279 | 1148579 | +903300 |
| Route35-162 congestion-failed signals | 248289 | 758463 | +510174 |
| Phase8 Global Vertical Routing Utilization (%) | 50.5855 | 52.2381 | +1.6526 pp |
| Phase8 Global Horizontal Routing Utilization (%) | 49.857 | 50.852 | +0.995 pp |

末期GLOBAL Congestion的utilization threshold两次均0.85；四方向原生窗口标签均64×64。该表的Max Cong不是§37 initial `%Tiles`，也不是placed Placer Final Level。

| 方向 | 旧Max Cong (%) | 新Max Cong (%) | 差值(pp) | 旧→新cluster level | 旧→新effective level |
| --- | ---: | ---: | ---: | --- | --- |
| North | 85.471 | 116.672 | +31.201 | 5→5 | 6→7 |
| South | 86.437 | 100.013 | +13.576 | 5→6 | 6→7 |
| East | 86.551 | 102.451 | +15.900 | 5→5 | 6→7 |
| West | 87.3848 | 112.353 | +24.9682 | 5→5 | 6→7 |

新每方向5窗、合计20窗，与旧同方向完整端点tuple没有相同条目。新North首窗INT_X0Y452→INT_X63Y515，South首窗INT_X0Y388→INT_X63Y451，East/West首窗均INT_X0Y516→INT_X63Y579；其余原生窗口在JSON完整保留。窗口交叠，不是20个独立错误；旧窗口未被本次最坏列表选中，不代表旧位置已经改善或拥塞为零。原生INT tile坐标与其它报告的物理tile/SLR需另做映射，不能混用。

新top10节点位于INT_X66Y462、INT_X92Y532、INT_X62Y532、INT_X29Y532、INT_X20Y544、INT_X74Y716、INT_X15Y590、INT_X60Y587、INT_X17Y573、INT_X37Y469，各报告4个overlapping nets并各列4条；旧top10各为3个overlapping nets。新列出的40条net涵盖MLP计算/调度、Attention计算/前端、tensor控制与DDR0互联。两条`u_tensor/input_beat_write_enable[40]`和`[31]`出现在第4/9个样本；旧`u_input_buffer/u_wave*/capture_index`多次出现在旧样本。它们只是被选择的10节点争用例子，不能由旧名字消失证明局部优化解决原瓶颈，也不能据此判定40条为全局失败分布或唯一根因。当前RTL与SSI布局同时改变，二者因果仍不能分离。

新log445 Route35-468指出1个同时setup/hold-critical的MLP leaf `s0_valid_r_reg/D`，router尝试以setup slack换hold；该条不是正式hold通过。§37的Iteration2完成缺项现由log409补齐：累计elapsed新03:56:27、旧05:05:28；相邻I1完成点差分新01:45:00、旧01:21:16。Phase9累计新04:16:55、旧05:12:07；log649原生`Total Elapsed time in route_design`新15510.3秒、旧18814.9秒。较短失败耗时不是成功性能、等工作量加速或收敛收益，且该原生内部时间不等于外层命令、后续自动DRC、失败取证及监督全程时间。

在此658行观察截点，Phase10/11已完成，log655明确Router encountered errors，log656为Ending Routing Task；**仍未在这份prefix内取得route Tcl receipt、原错误重抛、failed DCP/诊断报告闭合或native/监督退出证据**。原始失败取证由A006继续；不将工具/锁/资源/freeze写为已闭合，不据原生free physical字段代替监督MemAvailable保护判断。成功POST与成功route父链资格保持未取得，后续只对实际产物和真正自然终态续审。

execution：Phase9及末期日志有界核验completed，失败取证/监督终态审核pending；verdict：当前组合在本次AT004未合法布通，较旧同阶段重叠/失败信号与末期拥塞更多，通用方法可行性仍inconclusive；applicability：确切新prefix和旧同平台同阶段，但新RTL/SSI布局混杂；review：实发主控/A006，无EDA/重跑/策略变更/强停或新增批准门，正式安全与全局物理签核保持OPEN。

## 39. AT004自然失败、完整失败取证与成功POST拒收

[终态独立证据](AT004_natural_failure_terminal_review_evidence.json)与[有界审核脚本](review_AT004_natural_failure_terminal.py)核22项文件hash（含报告流式hash，未展开全部DRC违例）；闭合`vivado.log`与`implementation_run.log`逐字同身份，§38前缀是其精确前缀，另保留[闭合原文](AT004_natural_terminal_native_log.txt)。原生命令确为`route_design -directive Default`，Tcl/native/launcher/监督均exit1。Vivado真实退出为2026-10-16 21:56:20 CST（13:56:20 UTC），监督`ended_utc=2026-10-16T13:56:35.660913+00:00`，stop_reason=null，owned_before_reap/owned_survivors均空。6个已登记PID/start身份独立实查均不在，核查时对应EDA lane锁无owner；不推断其他项目进程状态。

五项失败取证receipt均原生code0并按顺序连续完成：checkpoint189秒、route_status152秒、timing422秒、congestion445秒、DRC241秒，合计1449秒。`route_failed.dcp`为779113008 bytes / SHA256 `6d1cf5ef3fea7b8ca0ab7ba27aaa61383ce487a640bcb63248cb6a9af7009590`；A007核stat、真实write_checkpoint成功行、receipt和A006已算hash绑定，不重复读取大DCP。其余6份失败产物hash与`failed_route_artifacts.json`逐一匹配；该manifest的synthesis及精确physopt父来源与真实launch/先前父链审核相同。保存失败检查点支持诊断可复核，不使失败图成为成功route父点。

`route_failed_original_error.tcllist`实际保存code1、原Common17-39 result、errorstack/errorcode/errorinfo/errorline及原命令；5项取证完成后原Common17-39在native log再次出现，调用栈经过`m002_route_with_failure_capture`和`m002_command route {route_design -directive Default}`直至退出。冻结归档及当前3份相关脚本hash相等，真实`return -options $options $result`路径与先前CPU错误传播覆盖一致。`launcher_status`实际native/aggregate1，`evidence_error`明确native physical controller exited1；没有将某个取证code0转为route成功。11项成功POST/成功checkpoint产物实际不存在，`eligible_as_successful_parent=false`且无成功diagnostic_evidence，失败父链拒收边界成立。

四种耗时分别保留：

| 时间口径 | 本次事实 | 范围 |
| --- | --- | --- |
| 原生内部`Total Elapsed time in route_design` | 15510.3秒 | Phase10后打印的router内部值 |
| 原生Ending Routing Task累计elapsed | 04:18:45 | 含Phase11，仍在自动失败DRC之前 |
| 原生`route_design: Time` elapsed | 04:23:02 / 15782秒 | 包含工具自动失败DRC，尚未应用自定义capture |
| `route_command_result`起止epoch差 | 17233秒 / 04:47:13 | 经过1449秒失败capture后才写receipt |
| 整AT监督起止差 | 17864.645122秒 / 04:57:44.645122 | 包含父DCP打开、native调用、取证和外层收尾 |

wrapper start到原error capture epoch差15784秒，与工具原生15782秒保留2秒的包装/取整口径差，不强行相等。E003同原生命令elapsed为19065秒；本次少3283秒只是较早以失败结束，不称成功吞吐或优化性能收益。`report_route_status`原生elapsed153秒与capture整数epoch差152秒同样分开。

失败route_status原文给出logical7145486、routable2031772、fully_routed1273309、routing_errors758463、resource_conflicts758463；fully+errors恰为routable，但fully不等于routable且errors不为0。该报告没有独立列出unrouted/partial两项，保持null/未报告；不由省略行填0，也不与§38的Phase8零值混用。Phase9节点1148579是另一计数，继续单列。

失败图诊断时序：WNS−13.528ns、TNS−1920757.000ns、setup违例546167/3209751；WHS−0.258ns、THS−468.768ns、hold违例13151/3208307；WPWS−0.537ns、TPWS−3.018ns、PW违例10/1095381。setup/hold/PW均FAIL。内部no_clock/unconstrained为0，外部no_input_delay1/no_output_delay2继续OPEN；原生提示bus_skew需独立报告，本次未取得成功POST bus-skew资格。timing报告header写Routed仅是工具标签，不能覆盖非法布通；这些数值属于失败图诊断，不能变成正式routed时序验收或与旧缺失的失败图时序给出同阶段delta。

完整失败DRC为15918 checks：RTSTAT-13 Critical Warning1；DPIP-2 7275、DPOP-3 5192、DPOP-4 325、DPREG-7 3072、PDCN-1569 3、REQP-1858 22、REQP-1935 28。RTSTAT-13实际明确“A significant portion ... is not routed”，因此RTSTAT-* routed-net检查未运行。自动失败DRC的0 Errors和自定义report_drc code0都不证明布线DRC通过；report header为Partially Routed，正式安全签核仍OPEN。

失败congestion报告仅有两节：Placer Final Level24行（12方向/type峰均6），Router Initial21行（South/Short峰6，其余11组峰7），**没有Router Final节**。该报告header是Fully Placed；不能因其在失败后生成，就把初始/placer表改称最终布线拥塞。真正末期GLOBAL MaxCong、20个INT窗口与effective level继续引用§38原生Phase8日志；报告中的物理tile窗口和层次百分比只按其自身初始/placer口径解释，不能相互替代。

execution：AT004真实自然失败并完成5项诊断capture，核心终态有界审核completed；verdict：成功合法布通目标未达成、时序诊断亦FAIL，取证机制及成功父链拒收supported；applicability：本AT004精确父图/命令与冻结版本，§38同阶段比较复用；review：已实发主控/A006，新144freeze及资源封存小facts到达后补核来源，后续R006只读补采按既定顺序继续，不重放物理、不新增审核门。

## 40. AT004终态来源、资源、冻结与失败检查点绑定补核

[补核证据](AT004_terminal_facts_resources_freeze_crosscheck.json)确认工程终态summary SHA `1b7d2cf05ececa27c0a2e181dadbbed203f4b32837f33ce625ecfbe0dad7f4c5`绑定14517-byte full facts SHA `92129a868d3ef19f54a008aafe269cc580aa1ce9224d6ba88732ca44fda3f525`；新15项文件hash匹配、11项闭合产物复用§39已实际计算的同身份hash。原生/保留闭合log、supervisor status、原Tcl receipt、producer与144freeze manifest均相符。A006 producer真实循环重算144项输入身份，记录零mismatches；A007核manifest/producer及§39三个相关实际脚本身份，没有另做全144重复扫描，也不改变生产冻结。

A007独立读取并重算本AT的3515条资源样本，峰tree RSS29300494336 bytes（27.2882GiB）、最低MemAvailable413704990720 bytes（385.2928GiB）、最低磁盘434214965248 bytes（404.3942GiB），与工程facts及监督status逐值相同，均在合同保护范围内。最早样本08:58:51.077510Z、最晚13:56:35.415163Z，最大采样间隔6.013834秒；所有样本中记录进程nice5，5个资源PID/start身份集合与terminal tracked完全一致。上述结论限周期采样，不伪造未采样瞬间的资源值；真实stop_reason=null，没有时间或资源强停证据。

工程6个登记PID/start已不在、真实非阻塞独占锁取得并立即释放，与§39 A007实际6身份消失及`/proc/locks`快照一致。A007未获取/修改锁或控制进程；该结论是AT004自然收尾，不阻止A006之后合法占用同一lane开展R006。

`failed_checkpoint_saved_observation`3108 bytes / SHA `161cf9b2da2a985e2212a925cb4277c14d2cfb049dfa87a0748a5afcae85ca57`及其独立保留receipt/log/producer均已核hash；早先189秒checkpoint receipt与完整五项receipt一致，早先log和receipt是闭合产物精确前缀。checkpoint身份与最终failed manifest完全相同，原错误文本逐字不变，先前保存未被后续取证覆盖。继续限定A007为DCP stat/原生回执/工程实际hash的绑定核查，没有读取779MB DCP。

execution：AT004原生自然失败、五项取证及外层资源/进程/锁/冻结收尾审核completed；verdict：成功合法布通及正式时序目标未达成，失败取证与拒收机制有效；applicability：本AT004完整原证据，§37–39阶段界限保留；review：已真实通知主控/A006，R006首次入口在Vivado前误拒历史failed状态的普通修复单独续审，place/physopt补采及全局验收仍未完成。

## 41. R006首次入口失败保全与旧CPU回执识别窄修

[窄修独立证据](R006_AT001_guard_repair_review_evidence.json)核22项身份：AT001 `preflight_failure.json`2750 bytes / SHA `82dc36acf777d132ac3e4e656c5aa738def93c6a00ff7ce2ee44f0ed17458b54`，固定snapshot manifest2884 bytes / SHA `5ebb3e6017098a42f239b748a1438dcc8058e74475b3ff8f6807403f940f73c5`，old wrapper SHA62a096ff（§33已审）与new4cfa0400、diff、测试/日志及两份旧status/started均匹配。原生前stderr确实在`prior_attempts_closed`拒绝R002/AT007，旧main顺序在创建report/native Popen之前；该尝试是实际pre-EDA admission failure，没有执行Vivado，原launch/source/error保留，不伪称补采失败或覆盖原尝试。

R002/AT007、AT008原status均**没有execution_state字段**；AT007原native/aggregate1、02:40:01.639198Z结束，AT008原0、02:41:55.592381Z结束，各自拥有与started一致的起点、明确CPU-only scope、stop=null和owned_survivors=[]。两份started记录的leader260673/start923092895、261956/start923104375当前实际不在；status/started各自SHA精确绑定，新逻辑没有把历史failed改写为completed或把旧失败测试算成PASS。

新guard只允许这两个精确R002路径与status/started双hash在缺state时走旧CPU schema分支，并继续要求stage/profile/scope/argv/cwd一致、真实带时区起止时间和两项整数exit、无survivor/stop、inputs_unchanged及真实leader PID/start。普通completed或failed仅表示所有权结束，仍须实际终态时间、两exit、空survivors和可核非空登记身份；running/UNKNOWN/null/任意缺state、无身份、冲突或仍活着的同PID-start均拒绝。PID复用而start不同不误认原owner。登记集合包括tracked、started/status的leader/supervisor及匹配detached receipt；成功parent的native0与POST资格继续由独立原判据控制。

实际diff与原/新源独立生成结果逐字相等。AST核对除legacy绑定、三个新helper及`prior_attempts_closed`外其他顶层语义完全不变；原synthesis recovery限定分支的条件/validate/记录/continue相同，仅original JSON读取外提。main中的原route自然终态、正确Default receipt、成功physopt父链、两份精确DCP、144freeze、单lane、无墙钟/资源守卫均未改。144manifest身份与§40一致，工程实际全144实核未变，A007没有重复全扫描或热改生产。

工程23项CPU真实exit0/log中Ran23/OK与固定源码身份相等。测试覆盖精确旧回执、普通failed/completed保留原exit、起止/exit/state缺失、bool exit、survivor、未知state、被改hash、实际当前PID的live拒绝、不同start的PID复用、空/冲突身份等。该覆盖针对helper与真实旧回执，不等于Vivado API验证；A007只读测试内容/原log，没有重跑测试或EDA。

execution：固定窄修审核completed；verdict：有界历史schema识别修复有依据，改动范围未发现实质阻碍，历史失败保留；applicability：固定4cfa0400 wrapper及对应23CPU来源；review：实际消息交主控/A006，AT002按已有授权继续，非用户批准或补采结果验收。

## 42. R006 AT002真实只读补采启动与正确place父DCP

[实际启动独立证据](R006_AT002_actual_start_review_evidence.json)核21项小文件hash，包括真实input_bindings `cb4029c7fcc6f3200bfdac7777274fc13b5308b87d01914c7e4ecc724f4c0e52`、parent/phase integrity/command、AT004闭合status/Default receipt、source/jobs、144manifest及资源helper。两份DCP大小与§34原身份完全相符：place579966904 bytes/SHA32b4af05，physopt579969232 bytes/SHA76621792；A007仅stat及身份绑定、不读取大DCP。真实归档wrapper为§41已审4cfa0400，16项prior closures中两旧CPU分支保留各自exit和空live，不由静态修复推填实际准入。

启动时间14:09:31.002290Z，supervisor874653/start927231694、leader874789/start927232928、native874879/start927232940及中间wrapper874808/start927232931四身份逐项实查相符，全部nice5/CPU0–7。对应FLOCK WRITE owner实际为874653；没有第二条A007 EDA或进程控制。max8/资源限额及wall/no-output null记录与合同一致，AT004原lane闭合后由本次合法占用。

[原生日志启动前缀](R006_AT002_actual_start_native_log_prefix.txt)44行独立保存：第27行实际`open_checkpoint`本轮AT003自己的place.dcp，第32行实际加载xcvu9p-flga2104-2L-e。jobs归档为place后physopt各自DCP及独立输出目录；当前只确认正确place图加载开始，不提前写已打开physopt或完成任何目标API/数据查询。后续按真实双phase输出、API错误或终态事件复用本审核，不重复轮询正常加载。

execution：有界启动审核completed，AT002只读会话running；verdict：正确父链、实际窄修版本与单EDA启动supported，局部性/固定窗口/层次补采结果pending；applicability：真实AT002绑定及本次保存截点；review：实发主控/A006，无新增审核门，完整SM009/物理/正式安全验收未完成。

## 43. R006 AT002 placed补采：实际源相对跨SLR、位置、层次与旧固定窗

[独立placed补采证据](R006_AT002_place_supplement_review_evidence.json)及[有界解析脚本](review_R006_place_supplement.py)核76项文件hash，包括4250-byte summary SHA `ff04992de5c21e578068ccdb5e829689c5ab5ee59dc439af7eb241755ddf8d7e`、138834-byte full facts SHA `e151be401b138df8618f91a78831abeb49e3c7c522b17652d591ecf3529ba574`及61项phase产物。真实phase receipt为place/native code0，epoch1792159776→1792160831，共1055秒；60项query全0，其中48项是逐旧窗口查询。原place DCP工程重hash仍32b4af05/579966904 bytes，A007核stat/既有身份而不重读。保存[place闭合后打开physopt的原生前缀](R006_AT002_place_closed_then_physopt_open_native_prefix.txt)，不能把place phase完成写成整个监督或physopt完成。

94个目标net的driver、REF/terminal、leaf pin/unique cell计数与97条分SLR位置包络逐行重算，与工程facts完全相等。所有目标源均为SINGLE_PLACED_DRIVER，无UNKNOWN/UNPLACED，所有负载位置落在SLICE；新80边界的cell/INIT/DONT_TOUCH/LOC/BEL、负载REF/terminal/SLR及总XY包络与原本轮placed TSV逐行相同，14上游的net/driver/LOC/负载类型和数量也相同。本次新增的是actual device site→SLR与源相对统计，不是重布局得到新图。

| 目标组 | net数 | leaf输入引脚 | driver所在SLR计数 | 负载SLR引脚分布 | 源相对跨SLR leaf引脚 |
| --- | ---: | ---: | --- | --- | ---: |
| input | 48 | 12288 | SLR2:48 | SLR2:12288 | 0 |
| Gate | 16 | 6144 | SLR0:3 / SLR1:13 | SLR0:3069 / SLR1:3075 | 1917 |
| Down | 16 | 8192 | SLR0:10 / SLR1:6 | SLR0:5120 / SLR1:3072 | 0 |
| upstream | 14 | 389 | SLR2:12 / SLR1:2 | SLR0:13 / SLR1:28 / SLR2:348 | 13 |

input48×FDCE/CE256、Gate16×FDRE/CE384、Down16×FDRE/CE512均保持；LUT6为48个input driver，LUT1为32个MLP driver。跨越算法从canonical net的unique leaf输入pins取总数，减去**实际driver所在SLR**上的pins。单位是每net负载引脚，不是SLR边界导线数、SLL Used或全局唯一cells；每net本次unique load cells恰与leaf pins相等，跨net加总仍可能重复计同一cell的不同输入。

Gate的1917精确来自以下5行，driver均SLR1：

| Gate row | driver LOC | SLR0负载pins | SLR1负载pins | 源相对跨SLR pins |
| --- | --- | ---: | ---: | ---: |
| 2 | SLICE_X95Y366 | 384 | 0 | 384 |
| 4 | SLICE_X96Y357 | 384 | 0 | 384 |
| 5 | SLICE_X96Y357 | 381 | 3 | 381 |
| 6 | SLICE_X94Y361 | 384 | 0 | 384 |
| 7 | SLICE_X95Y360 | 384 | 0 | 384 |

其余Gate11行cross0。80边界中79组负载hist单SLR，但实际源相对cross0只有75组；4个整组384 pins的driver在另一个SLR。此前row5缺driver SLR时严格下界3仍是当时合法限定，本次实测driver SLR1后精确值为381，不能保留“精确3”。上游13来自Gate `out_matrix_r[0]`源SLR1、16 pins中3在SLR0，以及Down `g_output_payload_row[15].u_output_payload_ce_i_1_n_0`源SLR1、25 pins中10在SLR0；其余12上游cross0。这些是两个层级各自负载pin统计，不相加声称全设计物理跨线数量。

同SLR也不等于紧邻布局。按每net每SLR包络的原生SLICE坐标差（max−min，无长度单位、不加1），input X跨度59–68、Y186–192；Gate X2–42/Y13–61；Down X17–111/Y46–138。Gate row5的381个SLR0负载包络为X115–137/Y209–243，3个SLR1负载为X96–98/Y325–386。其余完整包络保存在独立证据。这是位置范围，不能转换成实际route长度、延迟或拥塞。56个“原placed LOC”是**本E005先前placed报告**的原位置，经同part原生device拓扑映射，与当前94个driver的SLR逐项一致；不是E003旧net的leaf相对跨SLR基线。缺失的旧同口径数据不补造改善delta。

三个精确层次根查询各命中唯一NAME；原生报告重复显示根汇总一次，不能把两行相加。报告指标按其自身Total LUTs/Logic LUTs/SRLs/FFs口径保留：

| 本轮placed层次 | Total LUTs | Logic LUTs | SRLs | FFs | RAMB36 / RAMB18 |
| --- | ---: | ---: | ---: | ---: | --- |
| Attention u_input_buffer | 6422 | 6422 | 0 | 12383 | 42 / 2 |
| Gate u_projection_repack | 7024 | 4720 | 2304 | 6245 | 0 / 0 |
| Down u_projection_repack | 5216 | 2141 | 3075 | 8282 | 0 / 0 |

三根LUTRAM/URAM/DSP Blocks均0；Gate/Down的Total LUTs包含SRLs，不只等于Logic LUTs。input子层次原文u_wave0为130 LUTs、u_wave1为6278 LUTs，两者均6166 FFs；这是本报告的资源归属，未据此单独确定不对称原因或旧→新收益。全层次depth7报告也完整保留，本次未以层次和替代全局资源正式表。

48个旧窗口的direction/type/old_level及原生端点全部与原参考逐行相等。以真实GRID_POINT_X/Y建立闭区间rectangle，而非将混合CLEL/DSP/URAM命名当SLICE XY；48个actual_tiles文件逐个校验唯一计数与两端点存在。每窗site_TYPE容量与SLR site计数之和等于site_count，primitive_REF计数和等于primitive_count，逐类型occupied distinct sites不超过容量。四个预先选定热点的当前实际占用如下：

| reference row / 原窗口 | 当前site所在SLR | SLICE已占/可用site | URAM288已占/可用site | DSP48E2已占/可用site | attached net segments |
| --- | --- | --- | --- | --- | ---: |
| 3 North Global，CLEL_R_X27Y183→CLEM_X57Y246 | SLR0 | 3050 / 3051 | 16 / 16 | 77 / 130 | 197758 |
| 7 South Global，CLEL_R_X27Y199→CLEM_X57Y262 | SLR0 | 3002 / 3003 | 16 / 16 | 90 / 130 | 207716 |
| 10 East Global，CLEL_R_X54Y234→DSP_X69Y265 | SLR0 | 682 / 684 | 8 / 8 | 32 / 56 | 58557 |
| 23 South Long，CLEL_R_X19Y770→CLEL_R_X49Y833 | SLR2 | 3009 / 3136 | 16 / 32 | 121 / 130 | 194623 |

SLICE占用是SLICEL+SLICEM的distinct occupied sites，不是旧报告LUT%或CLB寄存器利用率；BRAM不同模式site容量不能相加当物理BRAM blocks；primitive_REF含DSP拆分子原语，不能直接把其总数当DSP Blocks。attached segments是所选原语pins上附着的层次net segments去重计数，不是全局唯一logical nets，更不是穿越窗口边界的nets。48窗重叠，不求和为全器件负载或独立拥塞。

**48个当前fixed-window congestion字段全部为`UNAVAILABLE_NO_VALIDATED_FIXED_WINDOW_CONGESTION_API`。** query code0证明资源查询完成，不证明取得拥塞API；原old_level只保留旧参考，不能复制成当前等级，也不能将未取得数值填0。原native拥塞日志和§29/38的不同阶段拥塞比较继续独立保留，不能用此占用表补造同固定窗拥塞改善。

execution：place单phase只读补采与本次独立审核completed，physopt/监督终态仍running/pending；verdict：80边界保持、新源相对局部性/位置/层次/固定窗资源有真实证据，Gate5行跨SLR清楚，合法布通/正式时序未因此改变；applicability：本轮AT003 closed placed图，不补造旧E003细粒度基线；review：已实发主控/A006，physopt独立继续，最终freeze/锁/进程及双phase总体验收留待真实终态。

## 44. 新最坏窗口映射覆盖仍缺；§43不能替代这项合同义务

按主控明确覆盖复核，[小范围缺项证据](R006_new_worst_window_mapping_coverage_gap.json)对照合同“固定及新最坏拥塞窗口”、AT003当前原生报告、R006实际归档Tcl和§43全部产物，确认：R006闭合placed仅提供**旧48固定窗口**的device GRID/tile/site/SLR资源映射。新placed最坏原生列表已有，但本次没有其对应空间映射/占用表；两者不可替代。此前§43的逐项PASS仅限已列范围，不是完整合同覆盖。

当前place/physopt原生拥塞报告分别为32891 bytes/SHA `0b95a7cc6612be99e5208b93bad917c5edb2387dc18e63cb76f226943b6af868`、32897 bytes/SHA `e6d69e49e8667cd81d54170196f0433c54011ea97e1a99705ac8189fe6e3b1d9`。各有48行/45个唯一端点区域，与旧48参考窗没有一个相同区域。每方向/type峰值Level6共12行，因South Global与West Long、South Short与West Short共用区域，最小覆盖为10个唯一区域；完整原生行及12峰映射已写入缺项JSON。

先核能否CPU推导：已存旧48窗tile名称并集39043项，12峰行的24个端点名称均不在该并集；归档只有旧窗aggregate site/primitive/SLR计数、tile名称，以及56个本轮原placed driver site映射和94目标net包络。原生`topology`的全device site→SLR字典只在Tcl会话内存，未写全器件GRID/site/cell位置归档。因此现有已封存文本不能可靠计算新区域的真实GRID范围、site/SLR及资源占用。不得从名称坐标、旧窗口aggregate或原新窗口资源百分比猜出缺失映射。

已实发A006协调最小剩余义务：保持当前AT002自然结束和原始文件不改；其后若无新的已封存完整拓扑可供CPU复用，在同一单EDA额度中有界只读打开各自closed place/physopt DCP，针对12峰行→10unique新区域采实际端点GRID、tile名单/计数、site类型/SLR与同口径资源及attached-segment数据，并保留原生行到唯一region的关联。两phase原列表相同不等于可代填各自资源测量；不重复80边界/94net/三层次报告或物理步骤，不热改当前会话，不新增用户批准门。

fixed-window拥塞API仍按合同允许明确UNAVAILABLE，本次补证据不以“取得拥塞数值/等级”作为目标。execution：覆盖核查completed、新最坏映射义务pending；verdict：§43原有成果有效，完整补采覆盖尚未结束；review：已真实通知主控/A006，待工程既定自然终态及有界补证据后核实完成，不以消息答复或计划视为解决。


## 45. 新12峰行／10unique区域的固定补采准备已核

主控已明确接受每phase 12个direction/type峰行→10个唯一新region的最小补证据范围，完整48原行保留；当前AT002自然结束后使用各自closed place/physopt DCP，不能以一phase测量代填另一phase，不新增审批门。A007已实际向主控/A006交付[独立目标清单](R006_current_peak_window_targets.json)，21254 bytes / SHA `67ac387aa81b03ee6137614deabd2483bd22e90ab4733bc69846e3f74354c651`。固定NW001–NW010及native line/source index/方向/type/level/端点精确关系，映射范围为12峰行，不能扩大称已映射48行。

[准备独立证据](R006_AT003_new_peak_preparation_review_evidence.json)及[有界文本解析器](review_R006_new_peak_preparation.py)核22项文件身份。A006固定V2 manifest为4461 bytes / SHA `a73ce3317d064cdca7fb2f42fd48399943d4e441eb3d44aba802b458924d0f97`；wrapper22524 bytes / SHA `a4178f45767acc229b972d62c3826f651ea4ff382ee5115c65832cb9e0880ca0`。两phase各48行独立从原生报告重解析，与固定manifest及Tcl逐行全等；12峰选择、10区域和独立目标清单精确全等。9项实际CPU检查的raw log、facts、producer与该wrapper绑定，A007没有重跑测试。

相较已核4cfa wrapper，13个既有函数AST全同；从新main仅除去目标校验、manifest归档、源报告输入绑定及post一致性新增后，剩余整个main AST与原文完全相同。因此原单EDA flock、先前尝试真实终态、精确closed父链/DCP、144冻结、CPU0–7/nice5/线程8、192GiB/48GiB/30GiB资源保护、无墙钟/无输出强停及原owned cleanup/terminal处理均保持。双phase driver字节同一，真实启动后仍分别加载各自DCP。

新core仅identity、实际site→SLR拓扑、目标范围和10个逐region catch；以实际端点GRID闭区间取tile/site/primitive，保存tile名单、site容量/不同occupied site、primitive REF和SLR计数，以及primitive pins附着的层次net segments。没有重新80边界/94net/三层次查询，也没有物理命令或checkpoint写入。当前fixed-window congestion保持明确UNAVAILABLE；query0不是拥塞级别或合法布通证据。原始报告的native Level6是选窗来源，不是新测fixed-window数值。

execution：固定准备有界静态审核completed，实际AT003尚未据此宣称启动；verdict：该固定稿未见实质静态阻碍，新峰值空间映射仍pending；applicability：上述固定V2、原AT003 place/physopt DCP；review：真实消息已交主控/A006，遵守AT002自然闭合和单EDA资源，实际输出/冻结/锁/进程尚待阶段证据。


## 46. R006 AT002 physopt与双phase自然终态独立闭合

[独立physopt／终态证据](R006_AT002_physopt_terminal_review_evidence.json)及[有界解析器](review_R006_physopt_terminal.py)核160项身份记录，其中包括61项physopt产物及复用placed审核的61项实际产物。physopt summary4268 bytes / SHA `a3ac7dcee4f2e3b1ba3ba18ae32a89807758c4ae655e66029e40df5ba02344fc`，facts138974 bytes / SHA `d510ec65526cb1a927a3389cf52c6bfbbba5e0a1d60a9ff1ffbfc19b2539c002`。原生确实打开本轮自己的physopt.dcp，phase epoch1792160831→1792161905，共1074秒，60query全0；不能仅因此前physopt未改网表就省略该真实测量。

**实际双phase数据相同**：80driver、94net、97位置包络、48旧窗占用/attached segments和48个tile名单逐字相等。56个原E005 placed site映射仅phase_context标签不同；三个精确层次和depth7的全部原生表格值相同，报告日期、输出路径及`Fully Placed`／`Physopt postPlace`真实状态差异保留。原本轮physopt的80边界和14上游原始TSV也与placed逐行相同。因此§43已独立重算的input0/Gate1917/Down0及上游13个source-relative跨SLR leaf负载、Gate五跨越行、位置包络、层次资源和四热点资源同样适用于本次真实physopt图。这里是逐phase实际观测相等，不以placed复制代填。

终态summary3518 bytes / SHA `aa14c8430e2034774a7bd1aad9df626b7de5cde7ec5a3d571017e95cc90dfc5f`，facts14597 bytes / SHA `478ed2e363eac53c0dcaf991904fe2a50bf5b20916283204adb7d55620359406`。闭合native log与Vivado原log字节同一，含此前保存前缀、两phase完成及总完成；原生14:45:05 UTC退出，监督14:45:12.436500 UTC自然退出，native/aggregate均0，stop=null，cleanup_was_required=false，owned before cleanup/reap及survivors均空，post_integrity_error=null。整AT从14:09:31.002290 UTC起为2141.43421秒，和place1055秒、physopt1074秒分别记录。

原始4个PID/start身份874653/927231694、874789/927232928、874808/927232931、874879/927232940独立查已不在。A006于14:45:57终态取证实际非阻塞取得并立即释放单EDA锁，producer与记录绑定已核；A007只读`/proc/locks`时锁已由后继AT003监督899702持有，未尝试取锁、不误称当前锁闲置或影响正常后继。

422个资源样本独立重算，每样本tree RSS等于其实际进程之和，全部记录nice5；峰RSS22.775665GiB，最低MemAvailable375.224209GiB、disk403.499451GiB，最大采样间隔5.146364秒，和原status/facts一致。144生产freeze manifest身份/count、工程实际完整重hash producer及wrapper after-freeze全部绑定、mismatches=[]；两原DCP的工程真实重hash和A007独立stat与已核父身份一致，5份归档源也全保持。A007未重复读大DCP或重hash144全树。

AT002终态20项boolean中的`new_peak_source_reports_unchanged=true`来自其空字典的`all(empty)`；明确是**该AT不适用**，不是新峰报告已采集或覆盖缺口关闭。48旧窗当前congestion仍全UNAVAILABLE，不是0，不以资源占用替代拥塞。§45后继AT003准备与实际启动由A006独立继续，其12峰行／10unique区域各phase真实输出仍是最终交付前剩余义务。

execution：AT002双phase只读补采和自然监督终态审核completed；verdict：既定控制／位置／旧窗／层次证据完整且两phase实际同值，不改变R004/AT004合法布通FAIL、hold FAIL或正式CDC/reset安全OPEN；applicability：原本轮各自closed DCP及冻结输入；review：已实际通知主控/A006，SM009整体证据仍等AT003新峰映射后汇总。


## 47. R006 AT003 placed新峰区域实际映射：SLR1站点高占用

[独立新峰placed证据](R006_AT003_place_new_peak_review_evidence.json)与[有界解析器](review_R006_new_peak_phase.py)核36项身份、17项phase产物。summary3024 bytes/SHA `8dbc013a32e1ef7fb516f0288ca405d2d42ed69f5ef70b75495e4e657341e067`，facts51764 bytes/SHA `2ddb6a74c9d3b9bafd78e95872044890a738de5ba6faa39e16f4f94a78fe493e`。各自原place DCP实际打开、phase epoch1792161981→1792162733自然code0，共752秒，15query全0。已审固定V2与实际6份archive相符；父链／原route／144freeze／2DCP绑定等15个字段与已核AT002完全一致，A007仍仅stat/工程实际hash绑定，不读DCP。

全部48个原生报告行逐行核native line、方向/type/Level/端点，原文完整保留。12个Level6方向/type峰行与独立67ac targets精确一致，映射为NW001–NW010。South Global与West Long共用NW002，South Short与West Short共用NW009。其余36非峰行保留但未各自空间测量，本次范围不含route末期INT窗口；不能改称全48行／所有route热点均已映射。

实际端点GRID取闭区间rectangle，各region tile名单计数／唯一性／两端点存在已核，计数恰等于GRID矩形点数。site类型容量之和与SLR site之和均等于site_count，primitive REF和等于primitive_count；每类不同occupied site不超过可用site。全部10区的全部site实际归SLR1，SLICEL及SLICEM均被占用；实际结果如下：

| region／对应峰行 | occupied SLICE／容量 | RAMB36 site已占／容量 | URAM288 site已占／容量 | DSP48E2 site已占／容量 | attached segments |
| --- | ---: | ---: | ---: | ---: | ---: |
| NW001 North/Global | 2944/2944 | 36/36 | 12/16 | 153/168 | 276784 |
| NW002 South/Global, West/Long | 2944/2944 | 39/39 | 36/40 | 162/182 | 295743 |
| NW003 East/Global | 3008/3008 | 39/39 | 28/32 | 141/156 | 269994 |
| NW004 West/Global | 2944/2944 | 39/39 | 28/32 | 167/182 | 297517 |
| NW005 North/Long | 2944/2944 | 39/39 | 12/16 | 189/208 | 315208 |
| NW006 South/Long | 3072/3072 | 39/39 | 36/40 | 111/130 | 246097 |
| NW007 East/Long | 3072/3072 | 36/36 | 28/32 | 102/120 | 235599 |
| NW008 North/Short | 2944/2944 | 39/39 | 16/20 | 169/182 | 293959 |
| NW009 South/Short, West/Short | 2944/2944 | 36/36 | 28/32 | 154/168 | 283228 |
| NW010 East/Short | 2944/2944 | 39/39 | 20/20 | 198/208 | 323764 |

“全部SLICE occupied”仅表示每个SLICEL/M site至少有一个被映射的primitive；不是所有LUT／FF／BEL槽100%占满，不直接证明没有合法重打包空间。RAMB36列只按该site mode，不能再把RAMB181/RAMBFIFO18等可选site相加为BRAM blocks；DSP primitive REF包含8种拆分subprimitive，不能加成DSP blocks。primitive input/output pin总数是所取原语pins，attached hierarchical net segments是附着段去重数量，不是跨窗口边界nets、SLL导线、全局唯一logical nets或流量。

10个tile名单并集20784 unique tiles，45对region全部有交叠；资源、primitive、连接统计不能逐区相加当全设计总量或10个独立失败。全部site在SLR1不是所有route失败都位于SLR1的证明。原报告Level6是选窗依据，当前fixed-window congestion仍全部UNAVAILABLE；新实际100%站点占用与旧热点不能互换成同窗口拥塞delta。

[本次原生前缀](R006_AT003_place_closed_native_prefix.txt)实际含place闭合并打开own physopt.dcp。该physopt尚未有闭合输出，本节不代填；监督终态／最终freeze／资源／进程及锁仍待真实终态。execution：placed新峰子范围测量与审核completed；verdict：所选峰区域在SLR1且SLICE站点全占用的事实supported，但唯一拥塞因果未成立；applicability：本轮closed placed DCP、12峰行／10unique区域；review：已实际消息主控/A006，原会话physopt继续。


## 48. AT003 physopt与自然终态：最终接受范围的覆盖缺口已关闭

[physopt独立证据](R006_AT003_physopt_new_peak_review_evidence.json)核36项身份、17项phase产物，summary3042 bytes/SHA `4c7c9b13bc4f22fca2c22301ba644e3c763189336bf730bdfa63d6c7fee0d59a`，facts51838 bytes/SHA `7e3bd79fe4a0b6b30d1785657c235023de037b40f3150e2d184cc3f33dd0aeb0`。原生实际打开own physopt.dcp，epoch1792162733→1792163491，758秒，15query全0。每phase各自保留48行、12峰→10NW映射精确相等；实际资源／连接两TSV和10个tile名单与placed逐字一致，原报告身份各自独立。§47全部SLR1、SLICE site全occupied及重叠限制因此有两个阶段各自实测支持，不是代填。

[自然终态／范围闭合证据](R006_AT003_terminal_coverage_review_evidence.json)核29项身份；terminal summary3552 bytes/SHA `d5fa7542629093b9b47906636a17376194ddac7b5050e4db07e140d5009c87b4`，full17444 bytes/SHA `fb70c3db34cf6dc13c1b52453a98a1ef1d2f4b57188409caad5079774bc5b269`。原生于15:11:32 UTC退出，监督15:11:38.117704 UTC自然退出，native/aggregate均0；从14:46:16.548276 UTC起整AT1521.569428秒，无stop／cleanup／owned残留，post_integrity_error=null，physical/write_checkpoint均false。

300资源样本独立重算，tree RSS逐样本等于其进程和，nice全部5；峰RSS22.821053GiB、最低MemAvailable375.171288GiB、最低disk401.564053GiB、最大间隔5.157572秒，与原status/facts相符。4原PID/start899702/927452343、899811/927453483、899830/927453486、899901/927453495独立检查均不在。A006真实终态flock取得并立即释放；A007只读kernel lock表，该inode无owner，没有操作锁或控制进程。

144freeze manifest/count、工程完整重hash producer及wrapper-after绑定一致，2原DCP工程真实hash与A007独立stat相符，6归档源、2原source congestion报告保持。工程终态producer仅相对AT002新增独立目标identity检查、结果boolean及明确applicability字段；A007另实际重hash独立target，与原67ac身份、archive manifest及terminal expected/actual逐值相等，记录于[最终事实](final_internal_review_facts.json)。这次是实际2源报告+独立target检查，不是AT002的empty字典真值。

**已关闭的是主控接受的各phase12方向/type峰行→10unique区域补证据缺口。** 完整48原行保留，36非峰行不各自声称空间测量，route末期INT窗口不在该测量范围。固定窗口拥塞API全部明确UNAVAILABLE仍为允许的未测量项，不改填0或原Level6；资源占用不能替代拥塞。原M002/SM009合法布通与正式时序、安全目标仍未达成。

execution：AT003两phase补采、自然终态和本轮A007独立审核completed；verdict：物理比较的既定补证据范围已齐，本次优化组合implementation失败、单项因果inconclusive；applicability：当前冻结版本／精确DCP／上述范围；review：已实际消息主控/A006，最终内部判断见[总审核](final_internal_review.md)，不替代用户结果审核。
