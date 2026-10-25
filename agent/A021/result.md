# A021：W0交付

第二十次AT002已关闭对象增量：21工件SHA一致；bus-skew四scope有限PASS、十count位合并由真实FF证实。两reset8级/73扇出结构及两DSP末图模式限定接受。发现实质CDC Max-DPO覆盖缺口：AsyncClockGroups优先于10ns DPO，Slack inf不能通过；Root已授权按design §12在同routed独立副本做精确补集约束修正及finite STA资格，不改原102/DCP/quality、不预先重综合/物理。SMC真实D优先级与query终态仍待；新增修正结果NOT_RUN。详见results第二十次AT002增量。

第二十次正式终态增量：R008 native0/nullstop/40owned0survivor/27.379GiB；正式setup+0.002/hold+0.010/pulse0且全部失败端点0，no_clock/internal unconstrained0。末图96lane各148FDRE、Down0/3072DSP/448metaURAM/clock10-5-5/0blackbox已核。DRC0Error/Critical，3072 DPREG条件在绑定core funcsim全部定义中排除（OPMODE00_0tt_0v_0v，内部P不可达）；末图两代表随同十bus-skew/两reset链/两SMC合唯一只读query。CDC6/2准确复位范围及5688vendor/FIFO路径完整分族，六接收链仅按稳定reset合同结构限定接受；整体CDC不自动豁免。原quality FAIL由外部reset3 IO delay和四可选XPM参数互斥产生并保留；内部STA完成不代表外部协议/板卡已验。21报告SHA及原生终态完整，见results第二十次；只余新query原生对象事实，不重复物理。

第二十次首批路由验收：R008原生route_design成功2h02m23s/0error/critical；665825940 B routed.dcp SHA cc34f49b…c7cc4、导出prefix、AT011 parent receipt及102冻结源独立核对一致。1687352条routable nets全部fully routed/0routing errors，结论ROUTE_LEGALITY_PASS；正式timing/check_timing/DRC/CDC、末图guard/clock、十bus-skew路径和四SMC catch尚待，Phase14 +0.002/+0.010 ns不冒充完整验收。旧两CDC11的两base-reset链不在已有24级范围，最小补证已与A022协调同一次必要终态DCP查询。results第二十次/design已更新，后续只核新增报告；本代理无EDA/重测/冻结输入改动。

交付：[design.md](../../project/hardware/source/mlp_linear/design.md)、[results.md](../../project/hardware/source/mlp_linear/results.md)、[abi.json](../../project/hardware/source/mlp_linear/abi.json)，revision 2。

接口：544-bit不可变descriptor、94个CSR、39个错误码、9-bit group cache握手、REC576 parser、独立GU/Down记录流、两opcode计数及地址。正常job_clear保持metadata/epoch；fatal快照不冒充quiescence；身份ACK、安全ABORT和严格工件schema2→布局归一化/schema3规则已定义。

交接已通过实际协作消息发送Root与A022；工程采用模块命名，cache/parser先实现。Root对schema唯一性/对齐/位域做了独立静态核验；本代理已完成同范围schema/公式文件自检。没有功能仿真、综合、route、bitstream或板级结果，结果表如实标记。

后续：按E013里程碑核验cache/parser、计算及控制集成、新构建输入与物理结果。普通实现错误直接连续修复，不增加逐次批准门。

## 首次有界审核交付（2026-10-24）

Host 32项CPU测试限定接受：11来源/5工件/4冻结源码/runner/log SHA均一致，16行整数数值、ABI字节、ROM与独立参考覆盖充分。无本轮范围阻断错误，不涵盖真实模型/Host调度/板级。

AT001 cache和AT003 parser只接受各自历史输入；当前已修订而未新回归，不转移PASS。AT002原runner FAIL保留，原生0+SIM_PASS说明为统计关键词误判。AT004当前9输入一致，接受128列scheduler/BFM pilot；AT005无终态不预判。已向A022交两项计数/中段坏记录覆盖缺口，并通知Root。详细证据和当前源哈希见[results.md](../../project/hardware/source/mlp_linear/results.md)。

本回合无生产写入、测试执行、EDA或ABI变更。已完成并释放活跃槽，后续里程碑再复用。

## 有界整合shape合同交付（2026-10-24）

[design.md §9](../../project/hardware/source/mlp_linear/design.md#9-真实生产层次的有界整合测试合同)已定主TB为GU128/Down64、完整K128/448，覆盖GU尾12/12/8及Down生产同余尾12/4。纠正compute Down组数与GU输出N的耦合，统一metadata2048/1792、输出12288/4096B、内部事务2816/2688及默认生产guard；生产ABI不变。

真实framing完整BRESP错误→排空→维护clear→身份ACK→新epoch重试为必测；global_freeze不可伪造soft-clear。风险与当前有限证据见results。已实际交Root/A022，可连续实施，无逐项批准门。未运行EDA/改生产代码，当前回合结束。

## 板级入口有限预检（2026-10-24）

读入closure107文件/83RTL/100模块，无同名双编；Attention基线SHA与真实cohort16宏选择一致，MLP非线性源不在图。入口仍WIP：七项shape/回执/DCP/生成身份/validate-only/阶段判据/进程归属缺口已实际交Root/A022，详见[results.md](../../project/hardware/source/mlp_linear/results.md)。A022连续修复，尚未对修复版复验。

未运行constructor、EDA或仿真，未等待AT021/023，不把静态事务预算当性能。原shape合同和生产ABI不变，本回合结束。

## 故障恢复/计数有限预检（2026-10-24）

静态确认BRESP discard与transport安全屏障路线、framing不可soft-clear、正常job_clear不影响Attention，以及flow_stall/inclusive计数无控制反馈。五项错误边沿/严重性缺口已交Root/A022，详情见results末节；设计revision4规定首错优先、同拍仲裁、late fatal阻ACK、idle无虚假DONE及recoverable不关闭deadline。

AT028仍按其冻结源取证，本轮不预判终态、不热改源码、不跑EDA。后继普通修复与单位边沿回归连续执行；生产ABI未变，当前回合完成。

## SM026受影响阶段有限验收（2026-10-24）

LIMITED_PASS：AT028真实N128/64、完整K128/448整合235509 checks/139012 cycles；AT030错误优先级/owner/快照单位；AT031当前真实framing恢复30529 checks/23820 cycles。三次六步骤native0/stop=null、唯一PASS、snapshot哈希均核；AT030/031匹配当前全部输入。独立Python gold10240值/96行嵌入不变，AT028后仅两处控制RTL和focused宏差异，正常/数值与原BRESP链按明确论证复用。

五项修复按实际公共行为接受，不声称所有同拍/故障来源穷举。当前入口104冻结依赖、83生产HDL、100模块无重名、44 Attention源一致，默认14336/4096/128/448/enforce1及派生counts实际静态check通过；可按已有授权推进constructor，A022已启动R003/AT003。

详细证据、SHA、复用及未验证边界见[results第五次审核](../../project/hardware/source/mlp_linear/results.md#第五次有界阶段审核sm026受影响范围验收)。未验收constructor终态、新综合/route/时序/DRC/CDC、Attention并发、生产全N、真实模型/Host完整链和上板。本回合无生产改动/EDA/测试重跑/后代，完成后退出。

## SM027构造/综合网表/继承有限审核（2026-10-24）

CONSTRUCTOR_LIMITED_PASS_SYNTH_PENDING：AT003原生0、无stop/漂移/残留，1323文件+XPR与AT004启动链一致，10native工件SHA通过。AT004已导出完整整板DCP211877273 B（cf11b600…bc5a4b）；四序列化XDC/237引脚/235IO标准/主钟与三域异步组存在，23 OOC/top run均综合成功，当前LUT766078/FF954137/BRAM835tile/URAM752/DSP5375。尚无最终result/quality/synth receipt，物理资格未签。

两XDC literal puts清理语义中性，候选runner严格绑定父DCP/constructor/manifest/post-inventory及exact patch；13项CPU synthetic守卫PASS及源hash已核，不冒称已实际继承。支持父终态/原有质量依赖齐后按已授权流程复用DCP，无需因纯诊断重综合或逐次批准。

证据和边界见[results第六次审核](../../project/hardware/source/mlp_linear/results.md#第六次有界阶段审核sm027构造当前综合网表与诊断清理继承)。不等待长报告；后续仅核新增终态/quality和真实应用差异，无EDA/测试重跑/生产修改，本回合结束。

第六次审核终态更新：AT004已自然FAIL（native1/stop=null/changed[]，peak50.06 GiB），失败是末尾REF_NAME前缀误匹配及pre-opt debug占位规则，不能签成功父receipt。保留FAIL，支持以原完整DCP进行修正查询的新原生qualification，不重综合。新增timing/CDC逐范围分类：530/554全部双DDR校准debug，唯一dbg_hub_CV可按UG908 opt阶段取证但必须实际回查消除；PERST/DDR reset缺delay独列。六CDC critical为真实reset控制路径，保留PENDING；未布局hold/pulse-width负值不直接判不可实现，也不预判自动消失。旧13case不覆盖FAIL父或新增build修复集合，须新准确继承身份。

六CDC结构补核：core_gate两项为四级active-low XPM async reset；Smartconnect四项为proc_sys_reset AUX电平四级xpm_cdc_single+LPF/sequencer，不能混称全部async_rst。准确生成连接/配置及vendor HDL已核，按稳定复位电平合同结构限定接受、无当前RTL修改依据；原critical保留，post-opt回查及最终CDC另判。

## SM027 qualification与impl前置有限复核（2026-10-24）

当前build/runner冻结SHA、精确四文件差异、原AT004五份证据/23份synth日志、同SHA DCP和七份质量报告复用均独立核对通过。两XDC仅删诊断输出，两个driver与记录patch完全一致；新来源验证限定原AT004失败，旧13case草案未用于冒充资格。成功receipt与impl依赖门静态接受，没有发现本轮范围内的具体阻断缺陷。

AT004/007/008的原FAIL及无成功receipt状态保留；本轮结束时AT009仍无终态，不声明原生资格PASS。post-opt/pre-place检查只覆盖零黑盒、原530/554目标存续/clock与24级同步结构；精确旧名不命中不等于功能消失、clock存在不等于全部约束充分，最终全局unconstrained/timing/CDC等另判。范围已通知Root/A022并获工程确认。

详情见[results第七次审核](../../project/hardware/source/mlp_linear/results.md#第七次有界审核sm027-qualification来源与实现前置检查)。本轮没有生产文件修改、EDA、测试重跑、后代或共享索引写入；完成并退出，后续仅核新增原生终态和实际post-opt证据。

第七次审核终态补充：收尾时AT009成功结果到齐，native0/null stop/changed[]/4owned/0survivor。receipt SHA f0fee79c…716ee5，26绑定工件SHA、构造/manifest/debug来源及1433项输出inventory一致；实际Attention1/共享核1/非线性0/仅厂商pre-opt占位、10/5/5ns clock和24同步级PASS。qualification限定接受，可继续正常opt；原overall FAIL和最终物理检查边界保留，AT004/007/008失败记录不改。


## 真实post-opt有限验收（2026-10-24）

R004/AT001_impl来源绑定与两native SHA一致。原530/554目标逐名/顺序匹配、全部存续且owner有mmcm_clkout5_1，黑盒/缺clock/移除均0；六链24级与已核对象逐行一致，8 FDCE+16 FDRE的ASYNC_REG/clock/相邻D均PASS。opt原生34m30、0error/0critical、113warnings，place已继续。限定接受post-opt门，无新阻断；全局unconstrained/timing/CDC/DRC/route和runner终态仍PENDING。详细结果见results第八次审核；本轮未运行EDA或改工程输入，完成并退出。


## 同阶段资源归因（2026-10-24）

整板同工具/器件/Synthesized实测减少62796 LUT、75213 FF、110 BRAMtile、76 DSP，URAM752不变，降幅分别7.58%/7.31%/11.64%/1.39%。保留主MLP共享核3072 DSP和当前392384 LUT、metadata672 URAM，加上Attention80 URAM解释面积大头；旧前端早已分时复用。旧输入35118 LUT/42301 FF/66BRAM/8DSP与旧SwiGLU30914/31477/44/68已具体核，DSP76和BRAM110可准确对账。共享核LUT+3241与Attention小幅映射差异明示，未把旧层次简单相加当净省。shape默认链已交Root，详情见results第九次核查。未运行EDA、改工程输入或中断impl，本轮完成。


第九次SLR补充：E006与M003证据确认被删SwiGLU/MLP input不是与热点无关，移除宽汇聚和周边资源具备局部减压机制；但旧最大的shared branch、Down S54/repack、Attention及DDR路径仍保留。早期E004的input大热点属于Attention，未删。E011 driver表475行canonical冲突网合计637893，branch1/branch0/SwiGLU为176163/94638/19406，只是旧失败网driver归属，非预期改善率。四项同阶段后继指标（SLR站点/局部拥塞、真实跨界/SLL、宽控制net-delay/fanout、route与setup/hold终态）已发A022，等待本轮实证，不承诺已减压或必布通。


## SLR诊断入口有界审核（2026-10-24）

发现的三项缺口已由A022连续修复：routed缺历史DCP hash锚、terminal gate未限制异常native退出、report_timing-of_objects与-delay_type互斥。新生成期observer只读且拒父已终态/死原root，routed必须其真实记录；自然0/1及身份/快照/日志门完整，原失败不升级。当前AT003_cpu 22tests及Python/Tcl检查真实通过，六源当前SHA与冻结快照、三日志SHA均一致。SLICE占用按去重实际site，400为四桶返回样本上限、可重叠且非全量；原生对象查询尚待实际执行。详情见results第十次审核，限定静态接受，无EDA/104输入修改或新增停点，完成退出。

AT004代表窗口增量有限静态接受：24tests/三命令日志/六源快照均核一致，最多4窗来源/去重/TSV冻结与原生tile→SLR/clock_region→cells对象链未见新增阻断。区域为包围clock_region矩形，不是精确INT窗口；父最后route日志与早期physopt/placed DCP结合只作空间候选定位，不推出失败网归属或改善量。原生诊断仍NOT_RUN，详情见results同节增量；本轮完成，不等待运行终态。

第十一次调度/拥塞分析：当前GU/DOWN已共用双8×12乘法核，但两branch同时工作，宽广播、LUT归约、两类累加器、6144→8192bit重排保留。真正新直接证据为physopt报告GU FIFO/branch ingress控制1968–2076 fanout；124–136不是最终扇出。执行先后不是已证主因，调度数据通路宽控制是优先候选；新图无手工pblock与继承M003固定CE分组是否相容亦需实际位置证据。详见results第十一次，含准确源码/日志行与三项可证伪区分；未进行EDA或修改冻结文件，已向Root交首轮结论。

第十二次GU-only计划完成：design §10与独立abi_gu_only_draft.json均明确planned。Attention物理DDR0/GU物理DDR1保持，routing仍共用FPGA内部资源；Down现可裁对象60468LUT/47398FF/192BRAM36/224URAM/1DSP不是新净差，3072共享DSP保留。v7/caps0x1D拒绝DOWN、GU-only metadata/epoch与Host租约、完整format05 Host Down数值及G0–G5责任/退出条件已交工程。只读当前R005已出跨SLR宽控制报告作为范围证据，不将其当最终route归因。当前abi.json未变；无实际实现/测试/EDA或吞吐保证。

第十三次完整新方案已交付PRO_plan/ScaleLLM_MLP_Gate_Up_Only_Dual_DDR_Design.md（GU-only v1.0-draft.2），含DDR/SLR事实与新原则、静态删Down和GU37bit、精确Host Down、ABI/epoch/lease、资源与成本及验收矩阵。G5只等硬件G4R，Host32层G4H独立；bounded scalar oracle与高效全shape整数参考分工明确。机器draft revision2、design §10同步，GU传输总量修正并核为1,449,984 B。旧方案/当前ABI/冻结工程不变；规划完成，代码/验证/物理均未伪称已做。

第十四次授权收束完成：独立方案v1.0及完整abi_gu_only.json已AUTHORIZED_FOR_IMPLEMENTATION，94CSR/39errors/544bit有效合同SHA318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a交A022。metadata padding沿原全局fatal并保留真实active owner失败completion，无任务不造DONE，旧DONE不重拍；inactive目标无效/epoch撤销、active数据不直接改。v6及R005未变，验证仍NOT_RUN。本轮结束，后续阶段验收再复用。

第十五次GU-only集中阶段审核：G1合成Down数值/strict工件/Host租约与实际adapter的42项CPU证据限定接受；R006 AT004/006/007/012/013/016/018七项原生PASS及当前全部源SHA一致，G2/G3模块限定接受。独立gold、37bit实际存储/数值、fullU32准入、生产全长度DMA及metadata错误drain范围已核。AT019只有中间四GU通过，CSR/focused metadata/完整生产elab尚无总终态，G4R保留PENDING。新入口原生层次/资源/SLR/route/timing/DRC/CDC、真实32层模型/应用链与Attention并发均未验收。单lane探针证据措辞已交A022并改逐96lane；旧八CDC critical边界保持。结果见results第十五次，映射见design §11；冻结合同未改，无EDA/测试重跑/生产写入，普通实现连续，后续仅补新增阶段证据。

第十五次最终增量：AT019真实GU-only整合222035checks/112509cycles、AT023 CSR4155checks/594writes、AT024真实metadata idle/heldDONE/active-owner三状态恢复、AT026完整N14336/K128/enforce1生产展开均核native0/nullstop/无残留及当前93/8/93/87输入SHA。AT025正确FAIL来自TB guard0，AT026唯一差异改1，生产RTL及断言不变、旧FAIL保留。结论提升为G4R_LIMITED_PASS，按合同可连续新constructor/综合/物理，不等Host32层；G5实际网表/资源/SLR/route/timing/DRC/CDC尚未验收。结果和实现映射已合并原文，Root/A022已获实际通知，本回合完成，无新审批文件/EDA/重测/生产修改。

第十六次G5资源准备完成：同Vivado2025.2/xcvu9p/core Design/Synthesized，v6→GU-only为LUT679798→593717、FF817705→756043、BRAM734→542、URAM752→528、DSP5369→5368；报告/DCP/current102输入SHA已核。新core最终日志314warnings/0critical/0error，不把中间568warnings当总计。正式旧整板基线固定766078/954137/835/752/5375，新整板/native96lane/Down缺席/clock尚待，未签整板或物理PASS。结果第十六次和design映射已更新，Root已获具体同比；未改输入/跑EDA，后续只审新增终态和原生工件。

第十六次正式整板终态审核完成：新679997 LUT/892475 FF/643 BRAMtile/528 URAM/5374 DSP，净降11.2366%/6.4626%/22.9940%/29.7872%/0.0186%；shared仍3072DSP，metadata448URAM，cache64BRAM未减且LUT+1467。原AT007自然FAIL/nullstop/无漂移/0survivor及194407960B DCP SHA783eb0…d398已核；96lane存在而guard查询0不冒称真实宽度0或已通过，A022新资格独立处理。两版530/554逐名集合、6条CDC10准确路径一致，DRC少两项恰为Down scheduler DSP建议；clock10/5/5ns及异步组原文核对。新post-opt debug/24级与vendor两XPM端点有效例外覆盖建议已交工程，最终CDC含旧额外两CDC11仍另判。结论为资源/已完成观察有限接受、AT007 FAIL保留、资格和物理PENDING；详见results第十六次，不等新attempt、不改冻结输入或重跑综合，本回合完成。

第十六次AT011资格增量：receipt228a9569…b712、30工件SHA、同DCP783eb0…d398、七原分析字节复用及102输入精确两driver变动均核。14208原生FDRE逐索引无缺/重/额外，96lane各两组两entry37bit；真实funcsim身份与AT007生成inventory一致。真实Down0/3072DSP/448metaURAM、10/5/5ns clocks、约束对象及六链24级限定通过，结论SYNTH_STRUCTURE_QUALIFICATION_LIMITED_PASS。原AT007/009 FAIL、整体质量FAIL/PENDING和后opt/最终CDC/物理边界不改；A022已按授权进入R008。已通知Root/A022，无EDA/重测/工程输入修改，本回合完成。

第十七次R008 post-opt有限验收：0黑盒，530/554冻结目标逐名顺序/owner一致、全有clock/无移除或缺clock；24级复位结构与AT011逐字节一致。两准确XPM request-FIFO scope各有1真FDRE/D及目标DDRclock、旧_i_1对象是LUT4，原生coverage均列10ns Max-DPO/Endpoints1；50%/33.33%不是当前真实寄存器漏约束比例。四valid/ignored预期文件和最终stage_quality未出，保留PARTIAL/PENDING并待实际catch，不宣称COLLECTED或waived。launch/receipt/102输入及五文件SHA核实，POST_OPT_DEBUG_RESET_LIMITED_PASS；最终物理另验，正常place/route继续，本轮文档完成并退出，无EDA或生产修改。

第十八次Placed有限归因：五份报告真实完整，DCP511010742B SHA cc92d8…fa0cb与导出prefix核实；SLR1/2已用CLB98.28%/97.14%但LUT槽61.80%/59.44%，不能将综合LUT下降当站点同比释放或单因归咎scheduler。真实branch1≈SLR0、branch0≈SLR1、Attention≈SLR2，metadata168/168/112URAM；scope站点可重叠，不转成拥塞贡献率。VHFN受宏/时序限制和22BUFG候选全skip是实际控制候选证据；热点报告尚待。旧-packthru LUT改用Logic+Memory，旧CLB有独立slice_sites锚，当前Placed与旧Physopt不相减。B版候选仅记录，不改运行输入、不启动EDA，详情results第十八次。

第十八次同批热点增量已闭合：placed_congestion完整10924B/SHA bebeeed4…b6bbf，14代表窗中3条Level6主要列Attention postprocess_store/right2/KV，GU branch0/paired_weight/W4/gather为Level5，多窗硬资源局部100%。只作当前Placed候选定位，不按Cell Names百分比定原因份额或route失败网排名；最高热点也不能据此全归GU scheduler。已并入原results/design，当前physopt继续，后继只做同阶段/同明确口径比较，无新增EDA/生产修改。

第十八次Physopt最终增量：新5m01原生成功/netlist未改，DCP511009344B SHA5c8922…0be72、prefix及六报告SHA核对通过；五资源表与Placed一致。同阶段旧独立站点→新CLB140388→137518，净减2870/2.0443%，SLR0/1/2变动-3786/-780/+1696。去packthru Logic+Memory LUT740911→656898减11.3391%，SLL13817→11698减15.3362%，不转为局部拥塞降幅。新报告14行仍是Placer Final Level且与Placed相同，旧min_level3的48行不能作热点数量比；route尚待。记录已通知Root/A022，当前流程继续，本轮结束，无新EDA/输入修改。
