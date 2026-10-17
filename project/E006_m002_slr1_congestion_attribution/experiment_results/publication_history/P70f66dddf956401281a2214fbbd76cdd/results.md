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

主控已将原输入候选降为探索对照。两项更直接候选为SwiGLU独立8-row producer1（热点8697原语）和down/weight_repack（热点2303原语）；其完整资源/边界与时序尚待同一DCP的精确比较，不能按热度直接搬或拼成组合。新R004登记范围为连接缺项修复及这两个候选的资源/位置/完整边界比较，尚未启动EDA；E007旧入口保留但暂非下一完整实现默认首选。E005失败、原R001受控中止及R003查询失败证据均保持。


---
Published: 2026-10-16T23:46:46.113962+00:00
Publication: P86b4dbba6081407eb74f26be7f884ff6
