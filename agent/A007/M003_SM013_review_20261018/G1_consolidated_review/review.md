# SM013 / E009 G1 独立综合审核

2026-10-18；审核人 A007 `/root/m002_physical_architecture_review`。适用对象：E009/R001/AT003 `failed_route_full_attribution_scalar_fix`，准备包 `f0ac0b91d8d91703ba34405bdd5a1154da1ff12f9b892b8ba6209ad119812101`；父图、生产输入和工具身份沿用已审真实启动/终态绑定。

**建议主控限定接受现有证据，推进 SM014 的 F1–F4 设计与集中候选判断；547548 原生报告的精确归因仍为 OPEN，不能登记无条件 G1 PASS。** 固定原生 CONFLICTS 查询的全量去重清单和分类可复算，但其 569597 个 canonical 与报告之间的 +22049 尚无原因及逐网映射。使用该清单作分母必须明确写出查询口径。若拟选机制依赖“这些网就是报告547548的精确集合”或依赖未测物理事实，该依赖须先关闭；其余有实测端点支持的设计工作可以继续。正式 G1 处置及候选决定由 Root 记录，本审核没有选择候选、通过 G2 或授权越过下游技术条件。

## 状态分列

| 维度 | 本次结论 |
| --- | --- |
| execution | AT003 于 02:11:43.478705Z 自然完成，native0 / supervisor0 / stop_reason=null。独立终态、实际审计回执和有界时序回放已完成。 |
| verdict | 固定查询口径的 alias、去重、归属、分组、union 和精确 deep 选集 supported；完整报告级对账、唯一因果归因和任何优化收益 inconclusive。 |
| applicability | 仅限冻结失败图、AT003 已归档查询/输出及其代表时序；不外推新综合网表、全 cut 时序或合法 routed 签核。 |
| review | 独立证据审核完成；建议 limited acceptance for SM014，report reconciliation OPEN；Root 正式阶段决定另记。 |

## 已核证据与数字

原生 CONFLICTS 行 2886261；包括固定补充的唯一 segment 2914086。全部 alias handle/NAME 元素配对通过，raw audit 没有重复或矛盾 alias；569597 个冲突 canonical 的 848 个互斥主组守恒。原始端点 7135972 行。前20完整组 436749，补充冲突集6761，交集142，union443368，占同一 canonical 分母 **77.838893%**。这表示完整组分类覆盖，不是代表深查覆盖或因果解释率。

深查实际为20534个唯一网：前20组各字典序16个代表共320、补充唯一20239、交集25；逐ID/tag选择经 raw audit v3 核验。80保护单元48/16/16与 DONT_TOUCH=1 已独立小表审核。

535331个冲突网的 driver 与全部可见负载位于同一已知 SLR；另12194为已知源且有非本地/port负载集合、22051源SLR未知、21已知源而负载SLR未知。端点同SLR不证明实际路由始终在该SLR，也不能据此指定拥塞原因。前三组：MLP branch1 SLR2本地151527、Attention projection array SLR1本地84058、MLP branch0 SLR0本地55822；不应把全部压力简化成跨SLR问题，也不能仅据模块总数选择内部算术改造。

| 冻结补充范围 | canonical总数 / 冲突数 | 可用事实与限制 |
| --- | ---: | --- |
| parent head模式 | 13509 / 5058 | 2408为SLR2→SLR0，1720为SLR1→SLR0,SLR2；其余本地或小集合。模式包含helper，不等于payload位宽。 |
| parent tail模式 | 6561 / 1551 | 942本地SLR2、608本地SLR1、1为SLR2→SLR1,SLR2。不能从head/tail名称推定每位实际读者。 |
| meta address模式 | 35 / 20 | 20个冲突均SLR1本地。较少网数不能反驳高扇出/长跨度代价；仍需逐位读者与硬块接入证据。 |

## 时序适用性已独立关闭至代表范围

A007 实际 CPU 回放 session40815 exit0：一次扫描269620299字节 candidate_endpoints，先收集所选网的完整leaf-IN集合再按组union/sort/cap，与工程流式top-k重建方式不同。28组选网与归档生成Tcl匹配，56份报告身份相同，104条实际DATA路径匹配预定集合；104个真实launch C/CLK负对照全部排除。TOP09/TOP10的max/min共4份原生无路径报告保留为无路径，不当作通过。

冻结算法是每tag字典序前16个网，再对这些网的全部leaf-IN并集**整组取前16个pin**，max_paths2/nworst1。多个Command头显示同一XDMA对象；原生实参列表没有单独导出。独立回放验证的是归档算法重建范围及路径DATA表成员/合法primitive输入弧，排除了Command头、launch/capture clock及launch clock-to-Q。它不能补造原生argv证明，也不支持全cut TNS或全局时序签核。

| tag | 捕获代表 max / min slack，ns | 范围限制 |
| --- | ---: | --- |
| META | +8.668 / +0.186 | 地址自身逻辑；不是全部URAM消费者路径。 |
| HEAD | +2.403 / +0.246 | 包含cache响应/metadata error链；不是全部payload。 |
| TAIL | −2.977 / +0.060 | 最差max为maintenance_soft_clear→tail[0]/CE。 |
| TOP01 branch1 | −2.896 / +0.060 | 最差max为clear_kernel_row[0]→MLP控制rdata。 |
| TOP02 Attention array | +5.863 / +0.179 | 仅当前代表集合。 |
| TOP03 branch0 | +7.930 / +0.275 | 仅当前代表集合。 |

工程交付中的route/total延时拆分未在本次独立回放重新解析；上述slack、起止点与DATA范围是本次实际复核项。失败DCP未合法布通，正slack不能作为物理通过证据；负的控制路径提示F3不能遗漏CE/clear成本，也不能将其泛化为全部字段的关键路径。

## OPEN 与依赖处置

1. **报告差额 +22049 OPEN。** 原生冲突字典在补充seed处理后清空并仅由CONFLICTS填充，不能用“混入补充种子”解释。CONSTANT22050由真实driver REF_NAME GND/VCC识别，与差额近似相等不是等价证明，不能删常量凑数。当前已知的是两个实际计数不同；原因和逐网报告映射未测清。
2. **物理未知。** CONSTANT22050全部source SLR UNKNOWN，其中22042有负载、8无负载。剩余1非constant源未知加21负载未知，共22唯一canonical；本次对2.8MB deep表和20KB处置表独立求精确ID交集为0，均不在现有deep20534及HEAD/TAIL/META补充内。规范driver模块和ID有记录，未知端点精确owner/LOC未在固定深查导出，保持NOT_MEASURED。仅阻塞实际依赖这些物理事实的候选，不从名称补猜位置。
3. **未测项目。** 完整overlap-node→net映射、full cut TNS、per-net SLL保持NOT_MEASURED；702396重叠节点仍是独立资源指标。现有数据可用于F1提取，但尚未自动构成全连接/控制/物理兼容性证明。

## SM014 候选依赖建议

所有候选当前均未冻结。不能按冲突网数量自动纳入或排除；必要补证据以选定机制的真实依赖为界，先消费已导数据，不自动新开EDA或无界扩查。

| 候选 | 当前支持的工作 | 冻结前必须闭合的依赖 |
| --- | --- | --- |
| C-M1 parent字段组织 | head实际跨SLR负载使字段级局部化值得设计比较。 | F1逐字段位宽、真实D/Q、全部读者和原tail→head路径；F3上游输入/选择、bank D、下游Q及CE/clear/clock总成本。不能把+3456FF参考估算直接作为选定预算，不能删branch ingress。 |
| C-A1 地址同沿副本 | 已测地址冲突/本地SLR端点，可按真实URAM消费簇比较。 | F1所有地址位、真实URAM读者与控制源；F2原同沿更新/标签语义；F3复制后的上游控制负载；F4局部FF的兼容位置。不能因20个网就断言无价值。 |
| C-A2 深度分银行 | 可比较机制和成本，现统计不证明必须分银行。 | 实际80-URAM映射、bank选择及宽响应汇聚、同沿读写/响应与stall、mux代价和兼容区域。缺证据可deferred；不默认10×8192或与C-A1叠加。 |
| C-R1 算术内部结构 | 大模块本地组提示后续应核内部实例/控制/硬块接入。 | 实际归因必须指向具体算术结构，给位精确、原II/外部周期和资源/连接预算。粗模块计数或top样本不足以选入。 |
| C-P1 联合物理策略 | 需要随所选RTL共同明确C01取舍及布局策略。 | 原硬约束、macro/物理父、兼容资源、硬块接入和全连接影响；occupied CLB不等于槽位耗尽，SLR2不是空闲区。无凭空坐标；新图对象资格留给SM017/G4实核。 |

F2有两项已由Root明确的必核语义：[准备记录](../F2_and_physical_selection_preparation.md)。parent满FIFO当拍pop也不给上游credit，仍为`rst_n && !clear && !full`；保留两entry、原子pop和无宽复位。meta普通周期中launch清零在前、后续meta_rsp_fire递增NBA在后，若同拍则后赋值胜出，除非证明不可达；不能用包含abort的datapath_clear替换事件集合，也不能`local <= original`增加一拍。

## 审核方法与证据入口

A007独立审核过原生alias资格、小表守恒、终态和保护；审读raw audit v3实际算法并执行其独立正负fixture，核实际工程session7567 exit0及来源/结果/stdout身份。**未重复扫描3.66GB全端点表，不将工程实际复算冒称A007第二次全量复算。** 本次自行完成269MB代表候选端点/104路径回放。DCP和144生产输入完整性由A006实际核验，A007明确引用其证据而未读取DCP。

最终有界绑定检查通过：raw审计、collector、status身份匹配；初次与最终manifest中18个共同文件身份不变，仅property_alignment由空文件变为表头，新增deep_cells/deep_site_tiles/timing_receipts；coverage仅final_native_deep_capture从false变true。此处比较的是已记录的大表身份，未重哈希大表。原始证据和已绑定prelaunch审核未改。

- [最终绑定与未知交集](final_binding_checks.json)
- [A007实际独立时序回放](../AT003_prelaunch_f0ac0b91/timing_scope_independent_replay.json)
- [A007终态/来源/进程/锁/资源](../AT003_prelaunch_f0ac0b91/native_terminal_review.json)
- [raw audit v3算法/fixture审核](../raw_audit_v3_preparation/review.json)
- [工程G1交付及原始结果索引](../../../../project/E009_m003_failed_net_attribution/experiment_results/g1_engineering_handoff.md)

本次仅写A007所有目录，无EDA、DCP读取、生产编辑、信号/锁修改、后代或外部会话重绑定。未增加用户批准门；按主控正式G1范围继续SM014设计审核。
