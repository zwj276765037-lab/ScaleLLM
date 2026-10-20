# SM014 F4 与 G2 有界审核准备

2026-10-18；A007。execution：既有E008/C01小表和当前相关RTL有界读取完成；verdict：事实与设计判据可用，尚未选方案或通过G2；applicability：Root正式[G1限定接受决定](../../../mission/M003_joint_routability_closure/g1_scope_and_sm014_start_2026-10-18.md)、E008已审失败图及现生产源码；review：独立设计准备。A006负责E009的115MB deep_cells和269MB candidate_endpoints单次提取，本审核不重复扫描。

## C01真实对象及约束

**C01与E009 TOP01是不同对象。** C01根为`u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`；TOP01根为`u_mlp/u_serial_command/u_shared_compute/u_branch1`。151527冲突网和−2.896ns代表属于后者，不能直接用作C01保留/撤销的因果证据。

[本次有界提取](F4_existing_C01_physical_evidence.json)复用既有E008 route_failed实际记录，按membership保存的身份核2.5MB物理表，与既有约束/映射小表交叉：

- RAW9514、语义S9507、可放置P9491。16个非identity raw→physical映射归并DSP内部子原语；不得在新图重复算作额外DSP实体。
- P全部SLR2；6317FF、1941 LUT primitive实例、25 CARRY8、816 MUXF7、384 MUXF8、6 RAMB36E2、2 DSP48E2。这里LUT primitive数1941来自REF计数，旧资源报告LUT1890是工具资源口径，二者不能混写。
- 当前6个RAMB36与2个DSP位于原生clock region X2Y12：RAMB36_X5/6Y150–152，DSP48E2_X9Y301/302。这是既有落点，不是M003强制坐标建议。
- `m002_exact_hotspot_SLR2`范围为器件实际SLR2的`CLOCKREGION_X0Y10:CLOCKREGION_X5Y14`，hard (`IS_SOFT=0`)、非独占 (`EXCLUDE_PLACEMENT=0`)、不包含routing (`CONTAIN_ROUTING=0`)。不能从非独占/非routing-contained理解为非约束。
- 9491个实际成员`IS_LOC_FIXED=0`、`IS_BEL_FIXED=0`；USER_SLR_ASSIGNMENT/RLOC/RLOC_ORIGIN/MACRO_NAME在直接表中均为空，25个DONT_TOUCH=1。旧preplace逐成员PBLOCK为NONE，后续均加入上述pblock。空字段不推广为“全设计/祖先无约束”，25个既有保护也不是可清除对象。
- 真实运行策略为SSI_SpreadSLLs / Default / Default，direct commands，无增量checkpoint消费。生产通用入口同样拒绝两个旧mission XDC；新overlay须正式注册，不能改旧被拒XDC冒充生效。

既有failed图C01完整有向cut仍有7124普通边界逻辑对，其中已知跨SLR121对；普通指排除clock/reset/constant，保留mixed/unknown。E006旧图“组外固定”搬迁估计与该实测不是同一布局条件；实际placer可连带移动组外对象，因此不能把旧预计7124条全当作失败图跨SLR实测。剩余UNPLACED源位置保持未知。这些逻辑对不是SLL或拥塞因果，完整external fanout、full cut TNS仍未测。

## G2必须定下，G4再用新图检验

| 范围 | G2必须明确 | G4/物理阶段需要的新证据 |
| --- | --- | --- |
| C01 | Root明确保留、缩小、调整或替换；解释与选定RTL的协同机制。若解除旧pblock，精确限定只处理该实验约束并保留硬约束/保护。 | 新图角色/原点/物理父解析、实际成员与祖先约束；新P数量按结构推导，不能机械要求9491。 |
| 局部副本 | 实际字段/份数、消费者分配、同沿方程、保留或禁止合并对象的最小范围；不只写local命名。 | 副本存活、真实D/Q/readers、物理位置和约束作用；重连失败/重新合并必须在长implementation前被发现。 |
| 区域 | 基于真实读者和硬块选区域的方法、所需资源种类、兼容性边界及失败处置；无需编造新综合网表尚不存在的坐标。 | 合法region/site/tile映射、macro/物理父/硬约束交集、FF控制集合及LUT/MUX/CARRY/硬块兼容打包。 |
| 成本 | F3包括源至D、tail→head、Q至reader、选择/CE/clear/clock及响应汇聚。数量/预算、延迟与II不留到route时决定。 | 实际综合网表资源和控制扇出；新增结构未实现或超预算时重新冻结，不用估算替代。 |
| 策略/入口 | 一套明确place/physopt/route策略，overlay名称/注册/消费及对象规则，关闭增量，不默认扫seed。 | 新输入身份、加载证明、preplace/各阶段恢复后验证、80保护及新图范围；不复用旧144输入充当新版本。 |

SLR0/1/2在E008 physopt的occupied CLB为94.95/99.68/99.92%，FF利用率36.46/44.77/48.40%、LUT54.79/71.73/76.31%，URAM70/77.5/87.5%、DSP67.5/88.9/82.68%。全SLR百分比既不能证明无容量，也不能证明消费簇附近存在兼容空槽；F4必须说明物理可实现机制，不能只报全局剩余FF。缺新图精确坐标可留G4，但“为何存在可检验的局部化机会”、核心粒度和约束策略不能全留待未来。

## 代表负时序与控制成本

E009 TAIL代表−2.977ns是`maintenance_soft_clear→tail[0]/CE`，TOP01代表−2.896ns是`clear_kernel_row[0]→MLP控制rdata`。仅能证明两条有界失败路径，不能推广为全部payload/clear路径或C01路径。但选择复制/分区时必须把新CE、clear、clock和上游D负载计入F3，防止只降低Q端扇出而增加原已脆弱控制链压力。不能以它们为借口增加一拍clear或更改reset/abort/事务语义。

F2保持[已审要求](../M003_SM013_review_20261018/F2_and_physical_selection_preparation.md)：满parent即使当拍pop也不开放上游ready，原两entry/原子pop/无宽复位；meta launch清零后同拍rsp递增的最后NBA优先级不变。未知项只阻塞实际依赖该事实的候选。

## 下一阶段

接收A006首个精确Q/D/物理子表后核对象身份、字段覆盖和遗漏，随后评判C-M1/C-A1可实施机制及F3预算。C-A1单read_addr的结构限制另见[机制审核](C_A1_single_read_address_mechanism_review.md)。本次不选C-P1、不提供新坐标，不开启EDA或改生产。
