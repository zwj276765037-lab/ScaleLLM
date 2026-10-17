# E008：pre-place 成员子步骤独立审核

接受当前 C01 literal 成员和物理父映射，完整 pre-place 资格尚未闭合；实现继续，无新增等待门。[机器审核](pre_place_membership_review.json)。

从真实账本独立重算整个 membership JSON，逐字段完全一致：RAW 9514、排除 4 GND/3 VCC 后 S 9507、物理父归一后 P 9491。精确根为 `g_row_branch[1].u_branch_leaf`，使用完整 NAME 前缀匹配，无越界成员。16 个 DSP 内部对象全部映射到根内两个真实 DSP48E2 父；P-parent 覆盖完整，无未解映射。RAW/S/P 与已审核 E006 C01 账本逐字节相等，这是本次实际核对结果，不是预设跨阶段必须相等。

本次 P 全部 UNPLACED、LOC/BEL 空。实际对象包括 FF 6317、LUT primitive 1941、CARRY8 25、MUXF7/F8 816/384、RAMB36E2 6、DSP48E2 2。对象计数不等于已打包利用率；先前 R004 的 native LUT 1890 是另一报告口径，未用本次对象数替换它。

`utilization_candidate_pre_place_SLR.rpt` 是 Optimized 图的 `report_utilization -slr`，仅给 SLR 连接及 IO 表，未提供新的 LUT/FF/DSP/BRAM 利用率总量。其 SLL=0 不能解释为迁移没有跨区代价。真实资源准入与完整约束几何仍由正在执行的 constrain 及后续资格检查闭合。

25 个 DONT_TOUCH 非空对象和 40 个 ORIG_CELL_NAME 如实保留；fixed、macro、SLR 属性当前为空，未擅自解释成已知 false。该子步骤标记 physical_policy_modified=false，仅说明成员导出没有修改物理策略，不代表后续 overlay 已通过。候选约束、cut/timing、全局保护与实际布局验收分别待其真实阶段结果。
