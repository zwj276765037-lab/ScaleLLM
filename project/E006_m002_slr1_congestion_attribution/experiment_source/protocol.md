# E006 / SM010 工程只读归因协议

## 身份与输入

合同为`mission/M002_ddr_separation_and_timing_recovery/slr1_attribution_contract_2026-10-16.md`，SHA256`cf53ff562b1894620ab0d6cc4398e17718cf815b32b8d2d8fd491adb17754263`。Vivado2025.2 / VCU118 / xcvu9p-flga2104-2L-e，core100MHz、UI200+200MHz保持。唯一原生输入为E005 R004/AT003 closed physopt.dcp，579969232B/SHA256766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d；不执行物理命令或write_checkpoint。

E005的144生产输入manifest仍为frozen_inputs_before_current_CDC_recovery.json/a5643a9e…；生产RTL/XDC/IP/构建及E005原运行证据不改。复用R006/AT003 physopt下NW001–NW010原实际tile名单，逐一绑定SHA并在native中验证实际tile对象与名单全等；同区域重叠不相加。模块targets及40失败net targets由A007/R002维护，原生执行前绑定实际文件身份；原失败log仅10节点、每节点最多5个信号，当前实际4条/节点，共40原文unique名字，不等于40canonical nets或全局失败分布。

## 真实尝试与复现

R001/AT001_physopt_attribution实际启动于2026-10-16T15:51:44.063950Z，supervisor942046/start927846090。精确argv/cwd见实际started.json/command.json，全部输入与archived source见input_bindings.json及sources/。新入口为agent/A006/E006_slr1_attribution/launch_detached.py与run_attribution.py，只在未使用的新AT/report中启动；不重用原AT、不覆盖终态或热改正在执行的archived源。

单EDA FLOCK；从实际启动限定CPU0–7/nice5，native maxThreads8。树RSS192GiB、MemAvailable<48GiB持续30秒、disk<30GiB才按保护收尾，正常无墙钟/无输出强停。独立stdio/session supervisor持有native；观察器仅被动读记录，无EDA或进程控制。实际模型未核实，期望gpt-6.1-sol/xhigh。A006无后代，A007只做CPU分析及独立审核。

## 查询顺序与闭合点

1. module_resources：一次open原physopt，保存tool/part/BB身份及真实site→SLR拓扑。枚举全部IS_PRIMITIVE对象，完整NAME/REF/LOC/BEL/siteSLR和互斥owner/细层次；特定Attention、MLP、MLP metadata、weight loader先匹配，core remainder随后，DDR0/1（三兄弟根）、PCIe/debug及其余全局逻辑补齐。逐primitive计数守恒；owner/sharedsite集合保留。原生report_utilization -cells -slr给exact owner/cut资源，再展开33额外已有根/可选深根（同owner根已省重复）。可选深根实际0/多匹配如实记录，不假设存在；required根缺失为真实查询错误。core_other/interconnect余集用实际primitive集合，其余互斥根用exact hierarchy；原生inclusive parent与exclusive cut分列。
2. hotspot_ownership：每个NW由原tile名单→实际tiles/sites/primitives，保存各区和去重UNION完整cell归属及native SLR资源。多个模块共享site、物理LUT/BEL的计数不强行独占；DSP split primitive仅REF histogram，native DSP数量与distinct occupied DSP48E2 sites分开。CPU推导LUT物理slot/寄存器BEL/BRAM/URAM/DSP site后，必须与该区域原生全owner资源核对；不匹配的派生口径明确未验证。
3. failure_samples：对全部10原失败node实际tile取GRID及原生SLR查询状态，并以精确tile名称核对NW成员关系；不用INT Y或SLICE Y推断SLR。对40原文net NAME精确匹配，未命中与多命中保留，不删suffix，不把DOA0/P[22]先改成pin；InstTerms仍为独立上下文。实际源/负载对象来自physopt图，不冒充failed route图；0 primitive driver不等于无真实driver。
4. hotspot_connections：选取UNION所有primitive所附着的net segments，按get_nets -segments合并完整网并以canonical和visited segments去重。输出全部所选网的真实primitive leaf IN/OUT端点、driver/多driver/unknown、SLR/owner、terminal类别、跨SLR负载和module×SLR边。范围是热点UNION附着全部完整网，覆盖其窗口外leaf端点；并非全设计net census。INOUT和top ports未枚举，缺项不补0。terminal分类保守，许多存储/DSP控制名可能落OTHER，可由已导出的REF_NAME/REF_PIN_NAME在CPU细分，不热改源。

每query独立原生code/result/options；每stage独立关闭marker并flush stage_receipts。模块global+10 owner各自query0后可先固定小批事实，不必等33detail；完整module/hotspot stage关闭立即实际消息通知Root/A007，同一会话连接继续。写文件不等于通知。CPU提取器只读闭合产物，生成独立producer/hash/facts和小摘要。

首批使用`capture_closed_owners.py batch001`固定global+Attention/MLP/metadata/loader的自然闭合回执与各报告身份，引用R002已经完成的完整primitive/site独立审核，避免重复扫描676MB输入。首4owner×3SLR的CLB touched、CLB FF、BRAM当量、URAM、DSP共60项一致；raw logic LUT primitive与native CLB LUTs分列。RAMB180/181两种实际半BRAM SITE_TYPE均纳入后续热点物理site派生，不通过改期待值隐藏口径差。

`capture_graph_stage.py failure_samples|hotspot_connections`为后续CPU提取器，等待相应stage真实关闭才执行。逐网按原生声明的driver/load数顺序读取全部端点，检查canonical名称、pin唯一性、driver位置、load cell/SLR/terminal及热点/跨SLR计数；失败样本同canonical别名去重，连接边表由端点独立重算后与native矩阵全等核对。原生terminal类别保持原表，另用实际REF_NAME/REF_PIN_NAME保守细化，DSP.C按算术数据端处理；primitive终端类别不等于RTL协议或payload宽度。未识别仍OTHER，NO_PRIMITIVE_DRIVER不补成真实无驱动。准备阶段仅AST结构检查，无额外回归或EDA API试跑；执行结果以后续独立facts为准。

## 已观测查询成本与后继入口约束

16:29:36 UTC的[成本快照](../experiment_results/runs/R001/attempts/AT001_physopt_attribution/query_cost_observation_20261016T162936Z.json)记录global99s、Attention33s、MLP61s、metadata/loader各6s；core_other仍在执行，已1084s。闭合清单和冻结调用的有界CPU核查见`agent/A006/E006_core_other_argument_cpu_audit_2026-10-16.json`：core_other为32,829个unique primitive leaf余集，无重复、内部祖先/后代重叠或越出core前缀；前4owner则每项仅1个exact hierarchy root。Tcl调用处从既有`dict lappend`集合取值，无再次通配查询或将cell值作为script执行；原生内部参数解释/聚合算法仍未知，不能凭CPU活跃认定结果覆盖正确。

冻结后续10NW与UNION的11项native资源报告也使用primitive集合。原R006同physopt每窗已测54,671–56,489 primitive，本次UNION实际数待取得，不由坐标或重叠推断。没有已完成的大leaf-list查询可建立可靠ETA；当前源保持，不按耗时/静默强停、不叠加查询。A007会在各hotspot query实际0关闭后先交单区事实，完整stage审核仍另行执行。**后继优化的验收入口优先采用native exact hierarchy报告加闭合primitive/site/LOC互斥CPU统计；不照搬本次大leaf-list report_utilization，除非具体缺失指标确有必要且已衡量成本。**

## 对照、异常与验收

相同E005阶段原生global资源和所有者primitive覆盖数为输入核对；原生cross-hierarchy LUT combining使子级LUT和可大于parent，不能强行凑加法。sharedsite/LUTslot/DSPsite明确非加和。全部NW实际tile union20784，原失败10节点只有NODE10/INT_X37Y469落入该union的CPU oracle需与实际device mapping逐行交叉核，而非迎合oracle。固定窗口拥塞API未验证，始终UNAVAILABLE；资源占用、附着segments、unique nets、leaf pins、SLL与流量是不同量。

查询错误按原回执保存并让本尝试自然终态，普通提取/入口修复使用新AT或仅CPU修复解析器，不覆盖旧证据，不新设批准门。除非当前日志和physopt确实无法回答必要路由归属问题，不打开failed route DCP；不扩大百万级冲突枚举。不以观察相关性宣称某单项修改的因果收益。

终态核原生/监督exit、stop/cleanup/survivors、所有原PID/start、锁实际释放、资源样本及保护；144输入、原physopt DCP、archived源、全部外部targets/source在执行前后保持。当前route FAIL、正式时序/CDC/reset等OPEN和无bitstream/板卡/GPU/PPL/ACC结论不改。E006取证交付后，后继针对SLR1/其他SLR的优化仅按主控新合同实施；当前不提前改源或新implementation。
