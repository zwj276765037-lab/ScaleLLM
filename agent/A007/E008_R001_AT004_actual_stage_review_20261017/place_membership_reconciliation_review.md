# AT004 place 成员、原生对应关系与实际SLR2落区审核

execution：当前真实文本证据重放完成；verdict：接受精确C01的9491个原始P对象全部实际落在SLR2这一子步骤；applicability：AT004 place图，combined候选compliance/cut/timing/阶段回执另审；review：独立接受，不新增停点。

RAW9514/S9507/P9491三份名称与REF账本同本轮已审pre-place逐字节相同。4 GND、3 VCC排除，16 DSP内部对象按真实映射归一为2个DSP48E2父。当前完整membership与reconciliation纯函数重放均等于工程JSON；original/literal/actual-Pblock/resolved全9491，无丢失、外来对象或replacement，lineage全部ORIGINAL_SURVIVING。

全局native ORIG_CELL_NAME查询实际执行、属性支持、Tcl code0，空origin表有成功回执支撑。所有P均有非空LOC/BEL、native SLR2及范围内clock-region。有效Pblock为CLOCKREGION_X0Y10:X5Y14、IS_SOFT/EXCLUDE_PLACEMENT/CONTAIN_ROUTING全0。5个已有物理策略字段与pre-place一致；IS_LOC_FIXED/IS_BEL_FIXED各9491项从pre-place空字段变为当前0，保留实际跨阶段差异，不声称逐字节相同。9491条位置与SLR2_compliant=1逐表互证。

独立原生端口索引审核另已通过：269端口/269组、2772别名、2170调用；167160条闭合别名事件完整配对。当前候选native packed利用率为SLR2内CLB971、LUT1883、register6317、BRAM6、DSP2、URAM0；9491是物理对象数，不是packed LUT数或路由需求。当前落区不单独证明拥塞改善、时序收益或布通。

全局hold FAIL与正式reset/CDC/IO OPEN保持。完整候选cut/timing/compliance/阶段回执另审；未调用EDA、读取或哈希DCP、控制进程/锁或修改工程文件。
