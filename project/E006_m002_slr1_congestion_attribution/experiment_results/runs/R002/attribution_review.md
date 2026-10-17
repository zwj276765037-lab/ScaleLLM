# E006/R002 独立归因审核

execution: running；verdict: 下列有界事实 supported，优化因果未判；applicability: E005 原 physopt 图及原 route 失败日志；review: 阶段事实已通过真实消息交主控/A006，非用户验收。

## 1. 已闭合 primitive 归属

A006 `complete_exclusive_ownership` 原生 query0 后，A007 顺序读取完整 **676367399-byte** `all_primitive_locations.tsv`，逐条重算 NAME 唯一性、最长层次前缀 owner、owner×SLR×REF 计数和物理 site-owner 集合。2,204,250 个 primitive 全部唯一、owner 匹配0差异，全部REF计数及153,056个site-owner集合与原生摘要一致。详见 [闭合事实](closed_primitive_ownership_review.json)，复现入口 [CPU分析](audit_primitive_ownership.py)。

SLR1 内有 **23,285 个 SLICE site 同时包含多个 owner**；MLP触及42,934个SLICE，Attention触及8,286个，不能直接相加解释互斥面积。DSP按不同LOC计数，MLP1291、Attention544，与已闭合原生资源表相同；不能采用分别11619和4896条DSP子primitive记录作为DSP块数。

FF原语与CLB寄存器口径不同：SLR1 DDR0有1211个、DDR1有1098个FD/LD原语在非SLICE站点；这2309个应排除后再与原生CLB Registers对照。审核保存全部站点与SLICE站点子集两类计数。

## 2. 首批 Attention / MLP 原生同根变化

以下来自 E006 原生 `report_utilization -cells <exact root> -slr`，global/Attention/MLP三个查询都已独立 query0 关闭；完整模块阶段仍在运行。原表SHA、行号和同根E003对照见 [首批原生事实](first_attention_mlp_native_review.json)。旧表直接复用主控的 `old_physopt_owner_baseline.json`，不重新解释旧源。

| SLR1 指标 | MLP E003→E005 | MLP差值 | Attention E003→E005 | Attention差值 |
| --- | ---: | ---: | ---: | ---: |
| 原生 CLB LUTs | 193322→248355 | +55033 | 60981→29578 | −31403 |
| 原生 CLB Registers | 246829→288933 | +42104 | 44043→38447 | −5596 |
| 原生 Block RAM Tile（36K当量） | 102→361 | +259 | 28.5→57 | +28.5 |
| 原生 DSPs | 1538→1291 | −247 | 337→544 | +207 |

MLP 的 BRAM 分布从 SLR0/1/2 =385/102/0 变成126/361/0；Attention从0/28.5/324.5变成0/57/296。两者SLR1 BRAM增量287.5解释全局+307.5的93.50%，且独立 primitive→36K当量重算与原生表一致。MLP现在SLR2资源为0。

SLR1拥挤不能概括为“两 engine 的所有资源都移入中心”：Attention LUT/FF反而减少，DSP和BRAM方向又不同。全局SLR1 LUT/FF增量扣去这两个原生同根数的净增量后，算术余项为 +44072 LUT、+78976 CLB Registers；还需其余owner表解释，并保留跨层次LUT合并导致的原生加法口径差，不将余项当作已逐cell追踪的迁移。

## 3. 失败样本与窗口覆盖边界

[CPU精确tile交集](failure_nodes_cpu_tile_intersection.json)使用已闭合的10个NW实际tile清单，去重并集20784 tiles。原route日志top10失败节点只有NODE10/`INT_X37Y469`在这个并集内（NW001–007及009）；其余9个在外。并集不是实际失败节点的全覆盖，不能把窗口内模块排名直接推广到所有失败；区域外也可能拥塞。后续原生tile/SLR映射将独立核对。

## 4. 继续审核范围

先交已闭合资源事实，再独立审核深层模块、10窗口及UNION资源组成、canonical net全leaf端点与40个原文失败net。连接查询目前的端点范围是leaf IN/OUT，不含INOUT/top ports；原语terminal分类的OTHER不能强行当数据。全套工作仍在同一A006只读会话中进行，A007没有启动EDA、修改运行源/生产RTL或控制进程。

用户通过主控新增要求：归因清楚后针对性优化，让其他SLR分担。A007后续给最小可检验卸载候选，必须结合实际子模块/配套存储控制、接收区域多类资源预算和跨区边界；本记录不预设硬分区，也不把当前观察当因果证明。

## 5. 外围与 tensor 缓冲的独立 CPU 拆分

[同一闭合表的外围细分](peripheral_slr1_primitive_review.json)将FF限制在实际SLICE站点，当前SLR1除Attention/MLP外共107987个CLB FF。主要为XDMA25894、d1_smc16458、d0_smc16457、u_tensor16455、host_split14841、u_paired_weight6540、d1_mig_slice4238、u_meta_bank2050、d0_mig_slice1898。u_tensor占core_other的18274个SLR1 FF中90.05%。raw LUT primitive计数在事实表单列，不混原生LUT资源。

旧DDR0/1原生表仅覆盖`ddr4_0/1`本体，E006 grouped DDR owner还含SmartConnect和MIG slice，不能直接相减。按完整NAME拆出MIG本体后，二者SLR1 FF均0，与旧同根原生0一致。XDMA同根旧→新SLR1 CLB FF9770→25894，增16124；BRAM30→50，增20，补齐全局SLR1 BRAM增量307.5。

可确认的外围聚合下界：d0_smc+d1_smc+u_tensor+host_split目前SLR1合计64211 FF；旧SLR1扣除Attention/MLP/XDMA后的所有模块也仅`319883−44043−246829−9770=19241` FF，因此这四类合计中心FF增加至少44970。这个下界不分配各模块旧delta，不证明同cell迁移；旧具体分布未知，当前不为补它另开EDA。

## 6. Slice 迁移边界与实际配置

[LAGUNA类型核验](ddr_non_slice_ff_site_types.json)通过实际native LOC join实际SITE_TYPE确认：d0_mig_slice在SLR1/2各1211个FD/LD、373个LAGUNA站点；d1_mig_slice在SLR1/0各1098个FD/LD、357个LAGUNA站点。不能当普通CLB寄存器自由迁移。

[外围接口配置事实](peripheral_interface_config_facts.json)中五个XCI hash全匹配原综合`inputs.sha256`；原create constructor summary亦记录BD、XCI component/model相同设置。两slice均为512-bit AXI、五通道REG15、USE_AUTOPIPELINING=0、NUM_SLR_CROSSINGS=2（模型亦为2），master/slave/middle各1级。不是单crossing默认值；参数2不直接代表实际几何穿越次数。继承的slice时序XDC含异步CLR false_path，当前自定义DDR XDC无LOC/pblock；有界源码核查不替代完整placed cell固定属性导出。

因此SmartConnect移向DDR同侧的纯放置试验仍保留该多SLR流水结构，不能预设它自动变成本地路径。减少/重构slice crossing属于单独IP/拓扑适配，必须重建并核对生成参数、AXI回压/顺序/数据、CDC/reset与约束适用性；不和纯放置实验混成一个不可解释改动。

## 7. 热点 CPU 提前归因的证据缺口

当前全primitive表列为NAME、REF、LOC、BEL、SLR、owner、detail，**没有tile列**；site-owner表也无tile映射。旧R006/AT003保存actual tile名单与聚合site/primitive资源计数，没有完整site名单或cell↔tile映射。因此目前不能将LOC字符串直接与tile清单做exact join，也不猜SLICE与CLE/INT坐标关系。既定原生hotspot查询将按真实设备对象导出cells，届时再审核。此缺口已实发主控/A006。


## 8. 输入预处理单变量卸载候选

[候选说明](input_frontend_locality_candidate.md)和[精确事实](input_frontend_locality_candidate_facts.json)已交主控：tensor输入bank及输入控制、frontend S24 capture/Hadamard/4quant与附属胶合形成一个SLR2局部性组；bundle/cache、tensor输出/DMA及SMC/slice不加入。9源hash匹配144冻结；两套12288 FF逐索引完整。当前选中77360 primitive，其中77246已放置全SLR1、114为GND/VCC；40627 CLB FF、31709 raw logic LUT primitive、8 DSP、0 BRAM/URAM。DSP内部子primitive必须归一，不按72条记录当72块。

源码主要载荷边界256-bit读入/1120-bit量化输出，不是已测canonical cut或SLL。当前候选触及13230个SLICE，其中12254与其他primitive共享、只有976候选独占；不能等同释放13230站点。SLR2比SLR0有更多空站点/资源余量，但也占93.07%站点，packing/route收益未知。

更早OPT/debug_materialized图须重新解析selector及资格；以同RTL、同SSI、同Default physopt/route隔离一个物理放置变量，完整route及失败取证验收在后续合同。E006实际热点、完整端点和失败样本仍待闭合，不提前完成归因或实施。单区partial审核入口[audit_one_closed_hotspot.py](audit_one_closed_hotspot.py)已准备：只有该hotspot实际query0才读；多段原生SLR表或资源不符不冒认aggregate，完整UNION集合审核留给整stage。


## 9. 后继合同与lean只读入口集中审核

[合同/原生表范围审计](candidate_contract_and_report_scope_review_20261017.json)确认planned范围、全部继承时钟和资格门；原五native主资源与身份不变。A007 parser已限制唯一SLR表/表界并保留<0.01等百分比边界。

[lean R003入口审结](lean_candidate_source_review_20261017.md)记录3个证据守卫、R003输出/R001原身份退出守卫、14个有界源hash及缩减覆盖。准备与内部审核完成，当前未EDA/stop或用户切换决定；实际原终态/新API与热点连接仍未发生。本阶段不把E006标成completed。
