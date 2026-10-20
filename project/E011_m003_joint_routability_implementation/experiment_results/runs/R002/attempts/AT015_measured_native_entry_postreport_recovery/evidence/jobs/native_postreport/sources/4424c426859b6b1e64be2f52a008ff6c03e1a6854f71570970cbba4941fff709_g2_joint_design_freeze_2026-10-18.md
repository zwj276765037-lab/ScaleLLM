# M003 G2：联合设计冻结与连续实施决定

2026-10-18，项目主控与架构评判。用户“可以开始进行mission”的执行授权继续有效。本决定依据[主合同](contract.md)、[G1限定接受](g1_scope_and_sm014_start_2026-10-18.md)、工程最终设计包及A007实际独立审核，批准 **C-M2 + C-A3 + C-P1** 作为同一版本进入SM015–SM017；G2为设计资格通过，不是功能、综合、布线或时序通过。不将本主控决定记为用户对技术结果的批准。

## 1. 冻结身份与审核

- 工程包：[design_delivery_manifest.json](../../agent/A006/M003_SM014_design_20261018/design_delivery_manifest.json)，SHA256 `6d74e85db325a939c8b1ffbd637de6dbd35e2016188bdd0050d62cc5a2b9706b`，34个文件。原包中的“Root未选/G2未过”是交付时历史，不改写原件。
- A007最终绑定：[G2_final_binding_check.json](../../agent/A007/M003_SM014_review_20261018/G2_final_binding_check.json)。34文件共59,139,703 B全部匹配；144条记录与旧基线元数据一致。生产输入实际重哈希由A006完成，A007独立核记录与回执，不把两者混写。
- A007[最终集中审核](../../agent/A007/M003_SM014_review_20261018/G2_consolidated_design_review.md)，SHA256 `ed4551d9c0d1b007a73ded8876cd4549a023d328d0df4a45a966ea528ae47cbe`。Root已读完整原件，结论与本决定一致：核心设计无阻塞，推荐M2+A3+C-P1；TOP01未直接处理的负时序不阻塞G2，但必须保留到后续实测。最终审核JSON SHA256 `acac9d32af31d7e1b07c00bfaa186aafba785dbe6c3eff36742b90594ed56820`；不重写冻结原件。
- 权威设计：工程包中的F1、F2、F3、两份F4、整合计划及81组映射。旧27逻辑组文件仅作历史，不作为实施输入。
- M2逐bit映射：[F1_F3_C_M2_region_groups.json](../../agent/A006/M003_SM014_design_20261018/F1_F3_C_M2_region_groups.json)，SHA256 `75abfae1d81cb75d13a8543a63f4f79ef1c70e25fee08d19d77a2c0f1627ad0f`。
- A006 finalization回执的`started_utc=0`是局部变量覆盖造成的无效时间字段，不能当真实启动时间；原件保留。实际设计启动02:42:57Z、最终exit0/observed时间、内容身份与受限CPU重算证据分别使用，不倒填。

## 2. 候选集中决定

| 候选 | 决定 | 依据与范围 |
| --- | --- | --- |
| C-M2 | selected | Parent两个实际CE各驱动6560 FF；用原CR内81个组合缓冲改变真实CE连接，精确保留状态/数据/周期。 |
| C-A3 | selected | 两片128位、各81920深、各40 URAM；各17位独立同沿地址状态，让两个数组实际读取各自地址。 |
| C-P1 | selected | 注册唯一正式M003 overlay，保持旧C01 hard-SLR2，配套M2区域与A3资源池；固定物理策略。 |
| C-M1 | deferred | 私有字段每branch2416bit已单读者；搬head可能把Q跨区转到D，完整复制增加3456FF及控制/时钟负载，缺少净收益证据。 |
| C-A1 | deferred | 单memory-side副本仍驱动整个存储的12个旧直接地址根，不能独立形成多簇。A3已包含所需同沿状态，不另叠加A1。 |
| C-A2 | deferred | 深度银行增加选择及256位返回汇聚成本；本版用宽度切片，不新增该机制。 |
| C-R1 | deferred | 粗模块冲突统计不足以支持特定位精确算术变换；保留现有算法和计算链。 |

## 3. M2精确冻结

生产TILE_W=9，head6560+tail6560=13120 FF保持；按旧实际(SLR, CR)分桶、原packed bit排序、每组最多256位，**head42/tail39共81组，23个CR**。81个显式`LUT1 INIT=2'b10`仅作同周期使能缓冲，实例DONT_TOUCH、输出网KEEP；master分别只驱动42/39个I0，局部输出真实驱动所属FF CE。不增加寄存级、宽reset、D端替代mux或payload副本。

每个CR建立一个hard、非独占、非routing-contained pblock，资源为该CR实际SLICE集合，容纳其buffer和映射FF；不固定单个LOC/BEL，不改变原FF所属粗CR/SLR。区域总slice数不等于空闲兼容槽，控制集合由2到最多81的打包代价必须在新图和布局中核验。不能临时改soft或退回27组。

F2状态方程为权威：保留原计数case含非法状态行为、两entry非旁路、满时无同拍pop credit、双支原子接受和原branch ingress。head full+pop读取旧tail，其他写入读取输入；宽payload无reset。非9位参数允许原CE兼容路径，但生产构建和生产宽度用例必须证明81组真实启用。

## 4. A3精确冻结

原81920×256容量与位序保持，分为[127:0]和[255:128]两数组，每片40 URAM，总80。生产core明确启用`LOCAL_ADDR_COPIES=1`；其他原实例默认0保持旧路径。单一原控制器/token/valid/计数/格式判定不复制；共同读写事件，两半同沿采样/写入并拼接，读写同址保持旧值语义，无输出流水或深度bank返回mux。

原core地址A继续供标签/范围/pending。新两helper各17位FF，用自己的旧Q增量；S=system_clear，L=实际launch且weight_command_ready，R=resident rsp_fire。异步reset清零；`CE=S||L||R`，`INC=R&&!S`，`D=INC?(own_old+1):0`。S优先，L+R递增旧地址，Q请求本身不递增；abort-only不代替地址S。禁止local<=A。各helper显式LUT3 CE INIT=8'hFE、LUT2 INC INIT=4'h2（I0=R，I1=S），最小保护34FF与4个控制LUT，增量锥各自独立。

最早t沿请求、t+1沿消费、t+2沿再次请求，最小请求间隔2个clock周期；不改变原外部吞吐或延迟。

| 片 | URAM实际资源池 | 地址逻辑实际CLB池 |
| --- | --- | --- |
| 0 | URAM288_X3Y80:Y119，40位；CR X4Y5/Y6/Y7 | SLICE_X112..141Y300..419，CR X4Y5/Y6，3480实际sites |
| 1 | URAM288_X3Y120:Y159，40位；CR X4Y7/Y8/Y9 | SLICE_X112..141Y480..599，CR X4Y8/Y9，3480实际sites |

逐site集合以冻结F4库存为准，不能用矩形文本代替原生有效site清单。两URAM池互斥，两CLB池互斥。内存与地址逻辑各用hard、非独占、非routing-contained pblock；无单site LOC/BEL。片内允许上述CR间合法级联，禁止跨池/列/SLR；地址至所属URAM根的CR纵向索引跨度≤2，横向均X4。公共控制/响应自由合法放置，不新增soft偏好。

新图必须验证URAM原点/实际ADDR消费者、级联/宏、RDW配置、响应寄存器映射、地址FF控制集合/CARRY连续位置和硬约束交集。preplace核对象和资源资格，不要求未布局LOC；实际LOC/跨度在place后验。池不兼容先关闭本版本入口并报Root，不能自行扩大区域或改片数。

## 5. C-P1与资源预算

明确保留旧C01：`u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`。维持`m002_exact_hotspot_SLR2`的hard-SLR2范围、非独占/non-routing-contained和25个原保护。新成员按原点/角色重建，不机械硬编码旧9491个成员。E009 TOP01是另一实例`u_mlp/u_serial_command/u_shared_compute/u_branch1`，不得混同。

正式新overlay名`project/hardware/vivado/constraints/m003_joint_locality.xdc`，经当前M002构建链注册、加载和恢复后验证；旧mission0004/0005被拒XDC继续拒绝。原board/clocks/DDR/IP约束和80保护重新核验。

固定策略：place=`SSI_SpreadSLLs`，phys_opt=`Default`，route=`Default`；增量关闭，不扫seed。旧DCP仅作证据，不作新RTL综合网表。

预算：M2新增81 LUT1、0FF；A3新增架构状态34FF（新图FF总增量≤34）、LUT≤96、CARRY8≤8、URAM40+40；联合新增LUT≤177、CARRY8≤8、FF34，额外URAM/BRAM/DSP均0。明确受保护LUT85个。名义局部新增控制集合上限+81，不充当工具全局实测。预算差异先解释/修复；需扩大预算则Root重新冻结，不静默放宽。

## 6. 实施、验证与连续推进

A006是唯一生产/公共入口/实验负责人和唯一EDA执行者；A007只写自身新审核记录并独立核查；Root维护mission/goal/results和集中决定。最多3活跃含Root、无后代。共享workspace有其他工作，保留他人修改，M004/E010不属本任务。

具体文件与必要用例采用冻结[整合计划](../../agent/A006/M003_SM014_design_20261018/integration_files_tests_and_freeze_plan.md)：三个RTL文件、正式overlay及构建检查、TB/结构测试及实验运行脚本。MLP上游serial command数据选择无需修改。生产只在project/hardware，不改旧根/旧归档包。

1. SM015先实现全部selected RTL和局部独立差分验证；必须生产TILE_W9及LOCAL_ADDR_COPIES=1，另验兼容参数/default路径。覆盖MLP占用/push-pop/不对称stall/reset/clear；A3全事件优先级、边界/非法地址、读写碰撞、拼接、token/stall/标签/计数及abort差异。LUT仿真使用真实库或经INIT真值验证的模型。
2. SM016一次配齐overlay/来源/角色/保护/恢复检查及必要正负例、联合功能回归。不能用mock替代新图；也不等不存在的SM017产物才能验SM016检查实现。
3. G3a/G3b真实证据且A007无阻断后，A006直接登记真实新E/R/AT并开始SM017新综合，重建生产源/参数/IP/XDC/工具身份。无需普通再次批准。
4. SM017/G4在新图核全连接/容量/预算/保护/约束与F4反证。通过且独立审核无阻断后，同一冻结输入直接进入SM018 place→physopt→route；阶段真实回执及时报告，不等待用户催促。Root当前已允许结构/约束合法但负时序时继续一次诊断route，最终验收不降低。
5. 常规编译/功能/来源/工具适配自然失败保全原证据、新AT、修复并重验后继续；改变结构/池/片数/策略/预算或无法保持语义则报Root集中重冻结，不能长实现中热改。route自然失败不原样无限重跑，依新证据集中判断下一版本。

所有编译/XSim/Vivado共享单EDA；CPU0–7/max8/nice5、树RSS192GiB、MemAvailable<48GiB持续30s、disk<30GiB保护保持；只控制已核归属与start的进程。正常运行无墙钟/静默强停。无bitstream、板卡、GPU/PPL/ACC；保持数值/ABI/双DDR/core100MHz/UI200MHz和80保护。

## 7. 未关闭风险与最终验收

- E009报告547548与canonical569597差22049保持OPEN，限定G1并未变成无条件PASS；网级分类覆盖77.8389%不等于修复覆盖。旧固定导出缺tail D/meta D-CE/所有C pin，不编造；改后真实连接在G4核。
- TOP01 `u_shared_compute/u_branch1/clear_kernel_row[0]→MLP control rdata`代表−2.896ns（data12.289ns、route11.776ns）**未被M2/A3直接处理**。当前没有保持周期并已充分论证的额外改动，故不加入新清空寄存级；后续同角色路径与全局时序仍须实测。保留C01不表示修复TOP01。
- M2多一级LUT及更多控制集合可能恶化时序/打包；A3写控制/响应聚合仍可能长线；SLR2仍拥挤，资源池名义空间不等于新宏一定合法。
- G2仅授权有依据的联合实验，不能承诺一次布通。完整合法route、全时钟setup/hold/PW、原+0.5ns余量、DRC/CDC/reset/IO/bus-skew及版本可复现性逐项验收；任何必要项FAIL/OPEN均不记整体成功。
