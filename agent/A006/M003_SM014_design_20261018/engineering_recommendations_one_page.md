# SM014工程建议：先审M2+A3，未作Root选型

2026-10-18，A006。执行：离线取表及设计中；生产RTL/XDC未改，无新EDA。适用E009/G1限定接受范围，不宣称原报告547548与canonical569597差22049已解决。

| 候选 | 工程建议 | 真正改变的连接及完整代价 | 可证伪边界 |
| --- | --- | --- | --- |
| C-M2 | 推荐纳入联合版本，待Root决定 | head42组/tail39组，共81个protected LUT1；原两CE各6560FF改为42/39个buffer输入，各局部CE≤256FF。按原生CR固定bit分组，buffer+该组FF同原CR；0新增FF、0新增clock负载，控制集合最多2→81（+79），多一级LUT延迟。 | 逐13120个CE pin核唯一定义/组覆盖及真driver；place后同CR且各≤256。保留原data mux和旧CR，不复制payload、不跨原CR搬数据。控制集合打包/约束冲突使本项不合格。 |
| C-A3 | 推荐两片128bit，不叠加A1/A2，待Root决定 | [127:0]/[255:128]各81920深，40URAM/片；两份独立同沿17bit地址计数器，共+34FF、2个17bit增量锥；单控制器/256bit响应不变。真实互斥X3Y80..119和120..159池：60现meta+20原未占，0其他owner。 | 新图每片实际40URAM，实际读地址来自自己17Q；没有共源/无负载副本，无额外输出拍/宽mux；新cascade/macro、地址FF兼容打包及RDW模式G4核验。 |
| C-P1 | 推荐保留旧C01 hard-SLR2，配套M2/A3新overlay | C01为`u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`；9491旧物理成员/6 RAMB36/2 DSP/25保护，按新角色重建资格；不引用TOP01 −2.896ns为C01因果。M2 CR分派和A3两池明确约束，其余公共控制/响应自由合法放置。 | 不消费旧拒绝XDC、不清保护、不固定旧单site；preplace对象/资源资格与place后位置分开验收。SLR2原拥挤仍是风险。 |
| C-M1 | 推荐deferred，不与M2叠加 | 私有2416bit/branch本已各1读者。head搬移可能把Q跨度转到D端。完整双bank+3456FF，head/tail CE各+1728、clock+3456，缺少相抵收益。 | 当前不需用尾D缺项阻塞M2；若将来真选payload银行才补对应上游全锥/物理资格。 |
| C-A1 / C-A2 | 推荐deferred | 单memory-side副本仍承受12原直接地址根；深度bank增加选择及256bit返回汇聚风险。A3给真实分开读者且无深度mux。 | 不把增加同值counter当已分簇；深度bank未有原lane/cascade/选择时序预算，当前不选。 |
| C-R1 | 推荐deferred | 现有证据不足支持具体位精确算术改写；不改变Hadamard/ScaleCode/format05。 | 粗组数不是特定算术变换的收益证明。 |

F1实测：head6560、tail6560、meta17个真实FF；head D/Q/CE、tail Q/CE完整，tail D、meta D/CE、所有C pin未在固定网集导出，保持NOT_MEASURED。HEAD13509=6560Q+6949helper；TAIL6561=6560Q+1helper；META35=17Q+18helper，不能把canonical `parent_*_r[0]`误当Q[0]（其实为CE helper）。每个tail Q恰好一个同bit head-D helper。元地址251读者=204个URAM地址pin+47逻辑pin，皆SLR1。

首个F4实案见[F4 A3](F4_C_A3_two_slice_resource_rules.md)，固定81组完整逐bit映射见[F1/F3 M2](F1_F3_C_M2_region_groups.json)。旧27逻辑组跨8/9CR，不采用；其文件仅保留比较过程。完整方程见[F2](F2_state_sampling_and_assertions.md)，资源预算见[F3](F3_complete_costs_and_budgets.md)，文件/测试/冻结见[整合计划](integration_files_tests_and_freeze_plan.md)。G2前不实施。
