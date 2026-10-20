# 联合差异、测试与工程冻结计划

A006工程建议，G2尚待Root选型/A007审核。唯一当前写入为本A006设计文件夹及自身console状态；**本文件不授权提前改生产、启动综合/implementation**。保留其他人的改动，旧目录与SM013冻结证据不动。

## 拟实施文件及唯一owner

| 文件/范围（均相对project/hardware） | 拟差异 | 后续owner |
| --- | --- | --- |
| rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv | C-M2生产9bit tile的81 LUT1、精确CE和固定bit组；n/所有branch ingress/宽D/Q不变；非生产参数保持原CE路径 | A006（或Root明确后继工程owner），单一写入者 |
| rtl/attention/hap_weight_meta_resident.sv | C-A3生产启用参数与内部S/L端口、两128bit数组/独立17bithelper；单控制器；legacy默认原单数组 | 同上 |
| rtl/attention/hap_attention_board_cohort16_core.sv | 原A/pending/NBA不动；u_meta生产参数启用，接S与实际L内部sideband | 同上 |
| 新约束vivado/constraints/m003_joint_locality.xdc及配套物理角色解析/资格脚本 | M2每CR唯一pblock；A3两40URAM/地址CLB池；C01原hard-SLR2角色重新登记；不引用旧被拒XDC | 同上，入口整合一个owner |
| vivado/scripts/m002_physical.tcl、build_vcu118_board.tcl及当前生产source/XDC注册 | 注册唯一overlay、前/后阶段资格与报告；新源及IP身份重算，禁止增量DCP | 同上；不改旧归档stage_sources |
| tb/原shared dispatch及新增M003差分bench、tests/结构资格测试 | 见下；保留现有回归 | 同上；A007只读审查 |

不改`hap_mlp_serial_ddr_command16_v5_s54.sv`的数据选择；不改C01算法/数学、DDR/接口/时钟、Hadamard、ScaleCode、format05、E005 input48/outputCE32。C-R1无算术变换。

## 验证映射及停点

| 阶段/范围 | 必须检验 | 独立期望/反证 |
| --- | --- | --- |
| SM014离线设计证据 | 原生字段/81组/80池完整；方程对齐 | A007 `M2_equation_check.json`为设计方程256组合；A006 `F2_A3_offline_equation_check.json`穷举1048576地址事件状态并跑30000切片周期；二者均**非RTL仿真/新图证明** |
| SM015 M2功能 | 原shared dispatch回归；新增生产TILE_W9 old/new周期差分，分支不对称stall，0/1/2/full+pop，clear与事件并发，无宽reset；非9bit参数fallback编译/运行 | 独立队列scoreboard+保留的旧状态方程；逐有效transaction数据/计数/ready/latency对齐；不能只跑fallback |
| SM015 A3功能 | 生产81920×256预载/边界/非法addr，默认0与生产1编译；tile/group标签、S/L/R所有组合、同拍L+R尾NBA、Q不递增、abort-only、reset及背压 | 原resident/core同周期模型，原字与两半拼接逐bit；同地址read/write必须旧值；一份token/count/format/error，response stall稳定 |
| SM016/G3b联合功能 | 现有attention cohort16 integration contract、全MLP/production smoke及原算法位精确回归；SM015选入项同版本合并 | 原独立参考与预期不可改以消除失败；smoke不等于物理/全规模性能验证 |
| SM016/G3b入口实现及正负对照 | overlay正式登记/消费、角色解析/数量/资源/祖先/macro/80保护/restore检查实现；正例闭合，漏overlay、空匹配、错误数量/资源/身份、硬冲突、保护丢失、恢复后约束失效等反例必须拒绝 | 用有界fixture/mock验检查实现与错误处置，保留原exit/期望；不把未来新综合/native结果提前记PASS，不为缺SM017产物阻塞G3b |
| SM017正式新综合 | 新生产参数、实际81 LUT1、34新addrFF、4控制LUT、40+40URAM、原13120payload FF及单控制器、资源预算 | 明确新源/XDC/IP完整身份；未保留副本、误走legacy/default、共同地址根或超F3预算均失败 |
| SM017/G4物理入口 | 原点/真实物理父/宏/祖先约束、CE逐pin分组、D/Q/clock/reset及addr自有increment，URAM实际ADDR/EN/WE/级联/RDW/响应寄存器 | preplace无LOC亦可查资格，不强迫未place位置；兼容打包/池容量/硬保护交集不成立先停入口，回Root，不暗中扩大区域/改片数 |
| place/physopt/route | M2每组FF与buffer同原CR；A3池与跨度；全局拥塞/SLL、WNS/TNS/端点、D/Q/CE/clear/clock及WR/response聚合 | 结构存活不表示收益，WNS成功不替代route/hold/DRC；任一route失败保存全部原证据，不替换为模板PASS |

仿真应使用真实UNISIM或经过INIT真值验证的LUT1/2/3功能模型，不能tie output或用wire跳过结构。M2 INIT2、A3 OR-FE与R&&!S-2的输入次序写入测试。A3物理RDW与级联输出周期需综合原生属性和RTL差分共同支持；功能模型本身不能证明URAM配置。

## 一套物理策略和预算处置

建议沿用既有可审入口的direct commands：place=`SSI_SpreadSLLs`、phys_opt=`Default`、route=`Default`；不扫seed、不消费增量checkpoint。唯一M003 overlay在source/XDC注册、project加载和各checkpoint恢复后都记录hash/实际消费与对象匹配；不编辑旧拒绝的mission0004/0005 XDC绕检查。原board/clocks/DDR/IP约束和80保护原样核验。

CPU0–7、nice5、最多8线程、唯一EDA锁；RSS192GiB/available48GiB持续30s/disk30GiB原资源保护保持，正常无墙钟/无输出强停，不运行bitstream/板卡/GPU/PPL/ACC。G2前无EDA；后续只按Root正式合同阶段授权运行。

预算：M2新增81 LUT1，A3新增≤96LUT/≤8CARRY8/+34FF/总80URAM，合计≤177LUT、≤8CARRY8、+34FF、BRAM/DSP/URAM增量0。副本/控制集合/CE/CLK/CLR按F3实测；资源或语义不符即当前版本不能进入长implementation。常规代码/入口修复可按已授合同继续；需要改变选型、片数/池、周期/接口/预算必须Root重新冻结，不能运行中滚动叠加候选。

## 版本冻结

源读入身份写入`design_input_identities.json`；设计包身份见`design_delivery_manifest.json`。它们是SM014建议包身份，**不是G2已批准或未来生产输入身份**。Root集中决定M2/A3/C-P1与deferred项，A007复核后，A006只实施这同一冻结版本；后续新生产源/XDC/IP/完整manifest重新生成，旧144输入不冒充新版本。
