# SM008 / E004 / R001：物理可布线性分析

负责人 A006 `/root/m002_build_verify`。唯一一次只读诊断已自然结束；execution=completed，物理事实 verdict=supported（限定下列原生报告/对象），优化收益 verdict=untested，review待主控/A007。写入仅 R001 和 agent/A006，生产 RTL/XDC/IP/时钟/数值接口没有改动。所有物理对象属于成功 physopt 父点，不能重建失败 route 的全量路由图。期望模型gpt-6.1-sol/xhigh，实际未独立核实。

## 已成立的判断

**首选应先验证 Attention 输入 slot 译码/本地使能及 MLP output CE 本地化，SRL→FF 映射是可独立取舍的次选。** 新原生高扇出报告已证实两个 input wave 的全部五个 capture_index bit 都分别驱动约6170个负载。相比只依据源码位数，控制高扇出是直接可测的修改目标；但它仍不能证明这10根网造成了全部245279节点冲突。

| 已测基线 | 物理意义及边界 |
| --- | --- |
| CLB sites146472/147780=99.11%；LUT814935/1182240=68.93%；CLB registers1019698/2364480=43.13% | 站点近满与槽位余量共存；不等于LUT耗尽，也不能直接证明control-set碎片是主因。收紧packing可能减少跨度，也可能增加局部pin密度。 |
| SLR0/1/2 CLB49193/48810/48469，仅余67/450/791 sites | 总站点余量只有1308，新增局部控制与FF的代价必须在位置和packing上核实。并不能把一个功能模块硬塞入单SLR。 |
| control sets22410/295560=7.58%，最低21980，综合/物理复制增加411/19 | 全局计数不是严重超额证据；小集合可局部不利，但不能把22k集合一概视作无效。 |
| physopt SLL Used0–1=8811/17280，1–2=9471/17280；失败route早期0–1 estimated demand21886/17280=126.66% | 已放置SLL实际计数与router估计需求不是同一指标。只有后者暴露列级估计超额；不能用前者约51%否定压力。 |
| 48个placed拥塞窗口，Combined LUTs最高34%；12个Level6窗口为6–16% | 当前未见>40%组合密集窗口；不支持把全局关闭LUT combining当首选。窗口重叠、属于Fully Placed，不是失败route全图。 |

原证据与SHA见[清单](existing_evidence_inventory.json)；窗口逐行数据见[placed_congestion_windows.json](placed_congestion_windows.json)。E003 native最终route失败、245279 overlaps/248289 congestion signals的口径保持不变，自动失败DRC零Errors不能覆盖合法布通失败。

## 新的定向证据

[原生top50报告](attempts/AT001_readonly_physopt_diagnostics/high_fanout_top50.rpt)已取得code0；[派生逐行表](high_fanout_native_analysis.json)保存其SHA与来源行。

| 对象 | fanout / driver | 对候选的影响 |
| --- | --- | --- |
| input wave0和wave1的capture_index_r[0..4] | 每wave依次6174/6173/6172/6171/6170，FDCE | 10根均进top50，支持优先验证24slot/wave固定目的写及组合本地CE。新网表应使index驱动有限译码/状态，而非仍有约6170个展开端点；每slot数据CE256bit。 |
| input activation_wave | 6163，FDCE | 输入与frontend之间整组6144bit选择也有控制压力；不能只修写端便声称整条路径已优化。保留快照/ownership合同。 |
| MLP Down output payload控制 | 8201，LUT4 | 16row×512bit本地output CE是明确可测目标；原资格rst_n&&!clear&&input_fire&&produces_output_c不可改变，不打一拍。 |
| MLP Gate output payload控制 | 6145，LUT6 | 16row×384bit本地output CE，与Down独立记录delta。 |
| MLP Down history控制 / Gate input_fire | 6192 LUT6 / 4652 LUT5 | history映射和output CE是两个机制，不能互相替代。S24 depth2改FF理论CE端点4608→9216；S32 depth1为6144→6144，故S32-only更适合作独立次选。 |
| rope_output_index_r[0..2] / quant_row_r[3:2] | 3902/3885/3836；3097/3086，FDCE | postprocess确有选择/写入控制负载，单bank/窄接口变化仍须原模块可见性及parent事务oracle证明，不能混入纯同周期首改。 |

top50末位fanout1782，context控制未列。它只说明当前有界榜单不支持context与input同等优先；不能断言context无拥塞。是否加入context64个局部CE边界须另有该scope实测，而不是按源码规模一起安装。

### 原生scope分项（各项查询code0）

| lexical scope | 物理LUT | CLB registers | scope内去重涉及CLB站点 | control sets | CLB站点SLR0/1/2 |
| --- | ---: | ---: | ---: | ---: | --- |
| Attention | 241355 | 271716 | 48845 | 3998 | 0/11052/37793 |
| Input | 18651 | 12341 | 5560 | 56 | 0/0/5560 |
| Output | 3947 | 12327 | 4146 | 69 | 0/2/4144 |
| Context | 5044 | 6594 | 2395 | 21 | 0/0/2395 |
| Postprocess | 22870 | 24629 | 5159 | 289 | 0/0/5159 |
| Attention projection | 166329 | 190795 | 40405 | 3134 | 0/11033/29372 |
| MLP u_mlp | 481288 | 583569 | 91242 | 14829 | 47571/38751/4920 |

这些是查询清单中精确层次的统计。CLB站点可与其他scope共用，嵌套/相邻scope都不能加总；u_mlp不含外置权重store及DDR等整个MLP功能系统。Input只有56个control sets却存在10根约6170负载的控制，故主假设应是译码/控制分发而非该scope控制集合总数爆炸。Attention的LUT/FF主要在SLR2，MLP主要在SLR0/1，须分别跟踪两处拥塞机制。Attention内部SLL1↔2为4909、0↔1为0；不拿它替代全局SLL或router estimated demand。

### 目标网络的空间分布

[target_net_fanout.tsv](attempts/AT001_readonly_physopt_diagnostics/target_net_fanout.tsv)共52个网络，日志27个唯一冲突样例全部找到。下表是成功physopt父点中的叶输入pin数；这些例子去重load-cell数恰好相同。`FLAT_PIN_COUNT`比这些值大1，包含driver pin，不能混称fanout。

| 目标 | 叶输入pins | load cells SLR0/1/2 | driver LOC |
| --- | ---: | --- | --- |
| wave0 capture_index[0..4] | 6174/6173/6172/6171/6170 | 每bit全SLR2 | bits0/1：SLICE_X93Y673；bits2–4：SLICE_X90Y673 |
| wave1 capture_index[0..4] | 同wave0 | 每bit全SLR2 | bits0/1：SLICE_X98Y674；bits2–4：SLICE_X102Y681 |
| Down output CE | 8201 | 4105/4096/0 | SLICE_X100Y261 |
| Gate output CE | 6145 | 3073/3072/0 | SLICE_X133Y270 |
| Down history CE | 6192 | 3119/3073/0 | SLICE_X110Y292 |
| Gate input_fire | 4652 | 2348/2304/0 | SLICE_X133Y280 |
| postprocess rope_read_pair[3] | 769 | 0/0/769 | SLICE_X65Y793 |
| frontend input_fire_local_21 | 256 | 0/0/256 | SLICE_X100Y680 |
| accumulator expected_output_wave复制 | 128 | 0/0/128 | SLICE_X106Y788 |

已有local CE仅256负载仍出现在失败日志样例，是“局部化不是充分布通条件”的具体反证。样例中还存在单负载的数据网络；节点冲突不能只按fanout排序解释。当前查询保存driver位置与load SLR计数，**没有**每net load REF_NAME直方图及SLR内端点坐标包络，不能凭源位数或临时net名补造这些字段。

primitive DONT_TOUCH显式1全局146589、Attention41225（其中projection41072）、u_mlp79211；Input/Context/Post和两repack返回空属性而非1，Output有64个显式1。Context/Post层次KEEP_HIERARCHY=YES。空属性只按原值记录，不将不支持/未设置一概解释为false；现有受保护复制可能服务于局部扇出，不能据计数一律解除。

## 计数核对与不能预支的收益

control_sets详细22410行的native BEL loads1089753，与Flip-Flop Distribution1019696和六类LUTRAM/SRL primitive70057之和精确相等；FF另有2个AND/OR形成CLB Registers1019698。见[BEL计数复算](BEL_load_accounting_reconciliation.json)。这支持顺序BEL负载口径，不能把1089753全叫FF。按CE/SR来源划分的桶不是load hierarchy，Slice Load Count相互重叠，不能相加成unique CLB sites。

新native hierarchy确认core整体仅5376个物理SRL LUT，而显式repack源码SRL16E共10752。两scope原生分项已核实：

| repack | SRL16E原语 | 实际SRL-LUT | SRL-LUT SLR0/1/2 | scope总LUT/FF | scope去重涉及CLB站点/CLBM | control sets |
| --- | ---: | ---: | --- | --- | --- | ---: |
| Gate S24 depth2 | 4608 | 2304 | 1152/1152/0 | 7003/6245 | 1693/950 | 10 |
| Down S32 depth1 | 6144 | 3072 | 1536/1536/0 | 5195/8285 | 2344/1253 | 8 |

Gate总scope CLB站点SLR0/1为823/870，Down为1130/1214。两处均不涉及SLR2。native控制集合中对应history的BEL loads分别4608/6144，Slice Load Count288/384，均16BEL loads/slice；这些顺序BEL负载不应称作FF。SRL16E在此实际两个逻辑原语共享一个物理LUT，5376是当前被触及的SRL物理槽位，不是净LUT或CLB节省。原SRL所在site还可能与其他cell共用，不能预测释放672个CLB。

任何“减少10752 LUT”“必降同数CLB”的说法均无效。S32-only至多直接移除当前3072个SRL-LUT映射需求，新增6144个声明FF状态位；S24改法触及2304个SRL-LUT而需9216个FF状态位，并可能使history CE端点翻倍。15360仅两个候选history FF状态位合计，实际净FF、LUT、CE和站点变化需修改后综合/布局。单改MLP history不直接处理SLR2的Attention控制压力。

## 下一次工程动作与测量

1. 独立修复失败产物保留入口，具体设计见[failure_capture_design.md](failure_capture_design.md)。它不改善拥塞，不能计入RTL收益；native失败码仍须完整保留。
2. 首改候选分成两个可审查diff：input两wave48slot本地译码和MLP32个row output CE边界。保留所有payload/metadata/valid、reset/clear同拍语义、输出stall稳定与吞吐。局部保护只限必要标量边界，不全局KEEP/DONT_TOUCH，不新增大data reset。
3. 功能验证采用独立事务oracle和旧模块逐拍对照；覆盖长背压、同拍消费/产生、reset/clear与fire同拍、首末group/wave、异常tag/mask、clear后重入。既有Hadamard/ScaleCode/format05/ABI和正确数值规则不变，不改expected迎合实现。
4. 新综合须查真实index负载类型、48slot decoder和32local CE是否确实存活；比较LUT/FF/BUFG/RAM、control sets、端点数及新增控制代价。若综合重新合并成原展开结构，则不声称候选已实现。当前冻结查询未导出每net load REF_NAME直方图，不能把6170+负载全先验称作某种LUT或FF pin。
5. 同器件/同约束place/physopt后比较真实target SLR分布、局部密度、packing、跨界网络、拥塞窗口、setup/hold。没有一个任意CLB占用百分比或单项fanout阈值能保证布通；若新增控制造成密度/时序回退，先定位而非盲扫router参数。
6. 主控/A007依据2025.2官方UG904选择下一阶段单一首选placement `SSI_SpreadSLLs`，route保持Default；`SSI_SpreadLogic_high`仅条件后备，不一次同时切换一串策略。物理理由是SLR0–1估计需求和列级分布压力；这些directive存在不等于会布通。官方依据见[方法笔记](../../../experiment_source/amd_methodology_2025_2.md)，当前安装版native help仍有缺口，留下一阶段轻量预检，不为此重开DCP。本轮没有调用这些实现命令。全局no_lc、全局DONT_TOUCH、粗硬Pblock和只调MAX_FANOUT均不列首选。
7. 最终合法布通仍须真实route自然成功、closed DCP/完整POST、routable>0、fully_routed==routable且unrouted/partial/errors均0。WNS/TNS、hold、CDC、安全和板卡验收独立判定。局部功能/映射改进不代表目标已达成。

## 只读诊断状态与局限

AT001 2026-10-15T23:25:10.387090Z真实启动，2026-10-15T23:53:35.703493Z监督结束，约28分25秒；native/监督/工具会话均exit0、stop_reason=null。open_checkpoint9:07后code0；48个query中35个code0，13个初始help失败。全部12scope原生util/SLR、top50/top64、目标nets和属性查询均code0。CPU0–7/max8/nice5、单EDA及资源保护生效，无wall/no-output强停。

[终态校核](attempts/AT001_readonly_physopt_diagnostics/postrun_integrity_facts.json)独立复算337个资源样本，峰树RSS26255056896 bytes（24.45GiB），最低MemAvailable436206272512 bytes，最低磁盘484638769152 bytes；5个跟踪PID/start身份及supervisor均已退出，锁独立可获取。原DCP后SHA仍为`c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91`、568389035 bytes；冻结query/targets/manifest/runner身份未变。

初始13项help使用不存在的redirect而code1；同一native93382/port10000的两次help恢复RPC仅客户端20s超时，未停止EDA，也未因此重开DCP。未生成native help恢复文件，当前安装版实现directive实际help未核实，不能把总体exit0等同全部查询PASS。下一阶段实现前按主控要求轻量检查，不新增本轮EDA。

已发现语义无效项：自建global BEL histogram虽然Tcl code0，但只得到LUT/FF槽全0；原始BEL非空，正则只认未带前缀的A6LUT/AFF等字面形式，未匹配实际格式。其CLB站点总数及每SLR均与native完全一致，故站点统计有效；槽填充直方图必须标INVALID，不能据此说空槽很多。只向同一native尝试了一次利用缓存向量的规范化汇总，客户端20s超时且未生成恢复文件；不追加请求、不重开DCP。原生utilization中结合后的LUT、FF和SRL槽统计不受该自建聚合错误影响。

日志10个失败INT tile均原生定位到SLR2，clock-region涉及X0–X5、Y12–Y14。它们属于工具打印的10个样本，不能外推所有248289失败signals在同一区域。
