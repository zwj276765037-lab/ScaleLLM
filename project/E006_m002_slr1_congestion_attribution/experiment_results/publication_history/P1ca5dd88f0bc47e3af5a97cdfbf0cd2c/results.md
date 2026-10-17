# E006：当前实测与候选修正

原生模块报告确认，SLR1的MLP使用248355 LUT/288933 CLB FF/361 BRAM tile，Attention使用29578 LUT/38447 CLB FF/57 BRAM tile；两个engine外另有107987 CLB FF，主要来自XDMA、双SMC、tensor与host_split，MIG本体在SLR1无CLB FF。DDR访存归属并不形成SLR放置隔离。原报告与对比见[首批原生审核](runs/R002/first_attention_mlp_native_review.json)、[外围拆分](runs/R002/peripheral_slr1_primitive_review.json)。

轻量R003/AT001已完成失败样本、热点归属、9个exact hierarchy资源阶段（各stage0），连接导出遇到单元属性批量对齐错误而自然结束native1/supervisor1。输入、DCP、原归档、全部PID/start与EDA锁收尾已核，未强停；[实际终态](runs/R003/attempts/AT001_lean_physopt_attribution/terminal_summary.json)。连接缺失保留为工具问题，不判方法失败。

| 已闭合观察 | 当前结论 |
| --- | --- |
| 10峰窗去重UNION共103313条primitive记录，全SLR1；MLP79277（76.735%）、Attention10986、DDR1 4462、loader3021 | MLP为所采热点主要归属，primitive记录数不等于原生LUT/FF利用率 |
| UNION实际5634个CLB站点；热点原生资源报告未查询 | 站点共享和窗间重叠不能相加，也不能当拥塞等级 |
| 40个失败exact网均命中，40个canonical、4877个IN/OUT叶端点；43个已知跨SLR负载涉及4网 | 仅日志原样本，未覆盖全设计失败、INOUT与top端点 |
| 10失败节点9个位于SLR1、1个位于SLR2；仅NODE10落10窗UNION | 峰窗不能代表全部失败位置 |
| 原输入前端候选在UNION中仅1042条记录（约1.01%），涉及310个SLICE，0DSP | 原候选直接覆盖主要热点的证据弱 |
| 原候选只命中3/40失败样本网，各为1LUT驱动256FDRE.CE，全候选内部/SLR1；合计只有23/657样本热点负载 | 支持一个输入CE散布探索，不支持宣称主要拥塞已被针对 |

原始阶段事实：[热点归属](runs/R003/attempts/AT001_lean_physopt_attribution/hotspot_ownership_closed_stage_facts.json)、[失败样本](runs/R003/attempts/AT001_lean_physopt_attribution/failure_samples_closed_stage_facts.json)、[候选独立交集](runs/R003/independent_candidate_raw_intersections.json)、[设备映射](runs/R003/independent_initial_device_mapping_review.json)。固定窗口拥塞仍UNAVAILABLE，raw LUT/站点不是native utilization或拥塞。

主控已将原输入候选降为探索对照。两项更直接候选为SwiGLU独立8-row producer1（热点8697原语）和down/weight_repack（热点2303原语）；其完整资源/边界与时序尚待同一DCP的精确比较，不能按热度直接搬或拼成组合。新R004登记范围为连接缺项修复及这两个候选的资源/位置/完整边界比较，已于北京时间07:57启动只读EDA、当前恢复原检查点；E007旧入口保留但暂非下一完整实现默认首选。E005失败、原R001受控中止及R003查询失败证据均保持。

R004入口集中审核已完成；方向时序集合、物理父约束属性和属性probe原值缺项已修复，受影响CPU检查通过。这仅说明入口准备，实际候选资源/完整cut/时序与适用性待测。[源码范围审核](runs/R004/independent_source_admission_review.json)。

## R004 已闭合资源阶段（北京时间 08:07）

| exact候选 | native LUT | CLB FF | BRAM36 | DSP | 物理P对象 | 热点原语交集 | CLB触及/共享/当前独占 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| C01 SwiGLU producer1 | 1890 | 6317 | 6 | 2 | 9491 | 8697 | 1788 / 1776 / 12 |
| C02 Down weight repack | 3348 | 3557 | 0 | 0 | 7257 | 2303 | 1347 / 1339 / 8 |

两候选 P 均实际位于 SLR1，原生资源/成员阶段分别 code0；P leaf policy anomaly 为0，不替代祖先/macro/新pre-place资格。三张辅助成员表出现 TAB表头/SPACE数据格式差异，捕获器按保留空字段的严格列数及成员/物理父/站点关系核查，原始字节保留；原生资源报告未受影响。9对象probe本次向量NAME/REF/LOC/BEL/IS_PRIMITIVE长度均9，LOC/BEL各含一空；没有复现旧对齐错误，不能归因到LOC/BEL。

完整cut、当前有界时序与独立最终候选判断仍未完成，candidate_scope_supported 尚未建立。后继[SM012/E008](../../E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)正在准备无默认候选的共通入口；没有开始implementation。


---
Published: 2026-10-17T00:11:19.164584+00:00
Publication: Pbb276a0685c6448380c740fb76299253
