# A021：当前状态

日期：2026-10-25本地。
execution_state: completed_partial（第二十次AT002已关闭对象增量及约束修正合同完成；SMC/查询终态及新资格结果待增量）。
verdict: ROUTE_LEGALITY_PASS / APPLIED_SYNCHRONOUS_STA_PASS / FINAL_GU_STRUCTURE_PASS；BUS_SKEW_LIMITED_PASS，CDC_MAX_DPO_COVERAGE_OPEN，原quality FAIL不改。

AT002增量已独立核21关闭工件SHA；十告警D证实共享真实FF，四scope skew1.072/0.652/1.364/1.084ns满足10ns。实际逐D仍AsyncClockGroups/Slack inf，确认用户group覆盖Max-DPO的真实缺口，不能据coverage签绝对时序。两XDMA链8级/完整73fanout及两DSP代表与既有合同/3072模式证明一致，限定接受结构，原CDC/DRC不waive。Root已授权同routed副本约束修正；design §12明确只替换用户group语义、保留全部非目标cut和10/5/5时钟，逐138动态目标finite Max-DPO及物理不变资格，NOT_RUN。两SMC仍待同query真实D timing/ignored，d0 Invalid endpoint不独自判全失效。无EDA/测试/冻结源改动，Root/A022已收到合同；以下历史原样保留。

第二十次正式终态增量已核：native0/nullstop/0survivor、21带SHA报告一致；setup/hold/pulse失败端点全0，no_clock/internal unconstrained0，末图96lane双37位/Down0/3072DSP/448URAM/clock保持。6CDC10/2CDC11/5688CDC15已精确分族，DRC0error/critical；DPREG3072个OOC定义均无可达内部P反馈条件，两个末图代表随同十bus-skew/两reset链/两SMC在唯一DCP查询补证。四可选XPM缺报告已查明参数互斥，三个IO是外部reset覆盖边界，非未布通。正式报告增量已落results/design，等待唯一native query实际事实；以下为首批及历史状态。

已独立核665825940 B routed.dcp SHA cc34f49b…c7cc4、生成日志prefix、AT011 parent receipt和102冻结输入全部一致。正式1687352条routable nets全部fully routed/0routing errors；route_design原生成功2h02m23s、0error/critical。Phase14 setup+0.002/hold+0.010 ns不替代完整报告；十bus-skew实际路径和四SMC catch保留待核。当前只补新增报告，无EDA/重测/冻结输入修改。详情results第二十次；下列为此前阶段记录。
applicability: 同Physopt站点独立基线、去packthru Logic+Memory及全局SLL比较；当前congestion仍Placer Final Level，不转成route因果或成功结论。

新Physopt DCP5c8922…0be72/511009344B及日志prefix、六报告SHA核实；资源表与Placed数据相同，native5m01/无setup违例/netlist未改。旧新站点140388→137518减2870=2.0443%，SLR分量-3786/-780/+1696；逻辑LUT减11.3391%、SLL减15.3362%，不能外推局部拥塞同降。新14行congestion与Placed相同，旧min_level3/48行不作计数改善；仍有Level6 Attention与Level5 GU/权重代表窗。Root/A022已获结论，文档完成退出；当前route自动继续，无EDA或冻结输入修改。

新Placed SLR1/2站点98.28%/97.14%而LUT槽61.80%/59.44%，明确站点占用与LUT总量不同；不能由controlset总数判唯一根因。真实分布为branch1主SLR0、branch0主SLR1、Attention主SLR2，metadata168/168/112URAM。placed DCP SHA及导出prefix核实，五SLR及congestion六报告完整；Level6代表窗列Attention postprocess/right2/KV，GU branch0/paired_weight/W4/gather为Level5，列项比例不当因果份额。旧-packthru Total LUT需归一化Logic+Memory，旧站点另有slice_sites原生独立锚；等待新Physopt同口径后比较，不重启旧EDA。B版仅记录宽控制locality/模块与局部硬资源预算候选，不改冻结输入；Root/A022已获结论。

R008 launch/AT011 receipt/manifest身份吻合，当前102输入0漂移。原530/554目标逐名顺序/owner匹配且全部clocked，0黑盒/removed/missing；24级与AT011逐字节相同。两XPM各1真FDRE/D、有DDRclock，旧非法对象是LUT4；两coverage均10ns Max-DPO/Endpoints1，百分比仅原指定pin集合口径。四valid/ignored报告及最终quality未出，保留PENDING并待实际catch，不新增停点或打断place/route。results第十七次/design映射与记录已完成，Root/A022已获结论，本轮退出。

AT011已自然0/nullstop/无漂移/无残留，receipt228a9569…b712及30工件SHA一致；同DCP783eb0…d398，七件原分析字节复用，102输入只有两driver相对AT007变化。独立解析14208原生FDRE索引集合完整，96lane各148、两组两entry37bit；真实funcsim SHA与旧生成inventory绑定。结构资格限定接受，正常物理按授权继续；24级仅限六链，不豁免CDC或替代post-opt。本轮已通知Root/A022并更新已有文档，不等待后继物理、不改输入或运行EDA。

新整板679997 LUT/892475 FF/643 BRAMtile/528 URAM/5374 DSP，同阶段减少86081/61662/192/224/1；cache仍64BRAM且自身LUT+1467。AT007自然native1/nullstop/changed[]/0survivor，DCP194407960B及SHA783eb0…d398已核，原FAIL保持。原生96lane存在/Down0/3072DSP/448 metadataURAM/10-5-5ns clocks有限接受，guard宽度待有效查询。新旧530/554端点集合与6 CDC10准确路径一致；原pre-opt debug/CDC诊断保留，24级探针不覆盖旧最终两CDC11。vendor两18-401的精确post-opt目标/例外覆盖建议已交A022。结果第十六次、design§11和记录已更新，Root/A022已获结论；无EDA/重测/生产修改，不等待新qualification终态，本回合完成。

终态增量：AT019 222035checks/112509cycles，AT023 4155checks/594writes，AT024真实三种metadata owner及恢复，AT026完整N14336/K128/enforce1展开/存储/复位；对应当前输入93/8/93/87项一致。AT025失败仅TB guard0，AT026唯一差异改1且保留所有断言。G4R依赖闭合，可按授权继续G5，不等待Host32层；新constructor/综合/物理仍另验。已通知Root/A022并完成文档，无EDA/重测/生产改动，当前回合退出。

本次独立读原始result/inputs/native日志并重算当前SHA；七项RTL源均无变化，Host26项当前身份一致，backend16项只有顶端docstring改动（其余AST完全相同）。整数/工件/租约及新生产图有限接受，未发现本次范围实质阻断。design §11与results第十五次已落盘并通知Root/A022；G4R已由下述新增终态闭合，G5不等Host真实32层。实际新综合/物理、Attention并发、真实模型/PCIe/板卡尚未接受。无测试重跑/EDA/后代/生产修改，后续只补新增终态，旧审核记录保留如下。

初始三缺口已交A022并修订：routed历史SHA锚缺失、自然终态未限native退出码、report_timing互斥参数。当前routed强制生成期观察/父身份，terminal gate严格0/1及结果一致，report_timing只消费原timing_path。22项CPU测试及三命令日志/六源SHA/source_snapshot独立读取核对通过，未由本代理重跑。

当前只读来源门、无物理修改、失败保留/PARTIAL边界、原生对象集合、SLICE去重站点口径与四桶最多400返回样本静态接受。结果不是原生查询或物理PASS；新routed观察器实际执行与SLR报告NOT_RUN。

结果已落results第十次审核，Root/A022已获三项具体反馈及闭合结论。无EDA、104输入改动、后代或共享索引写入；当前实现继续，本轮完成并退出。

AT004仅新增最后原生报告最多4去重代表窗、冻结TSV与原生tile→SLR/包围clock_region资源和8scope统计。24项CPU及三日志/六源快照身份已独立读取核对，未重跑；对象类型按安装2025.2手册合法，有限静态接受。原生诊断NOT_RUN。失败route日志窗口+physopt/placed保存布局仅作候选空间定位，不当精确INT范围、失败网driver归属或拥塞改善量；已交Root/A022并写results增量。

第十一次：区分执行顺序与调度数据通路物理实现。双branch仍同时接收、6560bit parent/1536bit共享权重/6144→8192bit Down汇聚、LUT归约和独立S44/S54累加均保留；ready/clear已有局部隔离。当前physopt真实报告GU及branch ingress1968–2076 fanout，124–136仅可优化loads。旧M003 CE分组与新无手工分区只是待核候选。优先实际宽控制load分布、保留数据/硬资源邻近、旧分组适配三个可证伪方向，未声称已找到全局主因；不改工程、不跑EDA、不等待终态。

第十二次完成：核DDR0/DDR1真实分工与内部routing共享，量化Down专属现占用60468LUT/47398FF/192BRAM36/224URAM/1DSP，明确不是新净差且3072DSP保留、cache128不保证BRAM下降。草案定义v7/caps0x1D/拒绝DOWN/GU metadata及epoch、Host bit-exact Down和新图执行顺序，保留模型全部层。当前abi.json SHA未变；只新增本人草案/更新文档，无生产修改、测试或EDA。

第十三次完成独立中文新方案，正文含Mermaid、完整数值/接口/SLR原则/实施验收，新增G4R/G4H分离及G5不等Host32层；纯Python oracle只作有界fullK边界验证。稿件与机器revision2一致，1,449,984 B GU总传输及资源/MAC公式已核；原方案保留。Root可交付用户，本轮结束，不扩范围或等待R005。

第十四次：用户已授权开始。完整有效schema SHA318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a已交A022，94CSR/39errors/544bit静态核一致。padding故障沿原全局fatal：无accepted不造DONE、active owner失败响应、已有DONE只升级reset；inactive目标bank失效且撤epoch，activebank数据不直接改。无EDA/生产改动，验收仍NOT_RUN，完成退出供Host并行启动。
