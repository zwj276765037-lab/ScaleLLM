# M002 / SM011 / E007：输入局部性组向SLR2卸载与完整implementation

状态：入口工程准备中，实际EDA尚未启动。用户先授权“查明清楚后进行针对性的优化SLR1 可以让别的SLR区帮忙缓解压力的吗”，随后明确“进行针对性优化后开启下一轮implementation 我希望下一次就能成功”。本合同覆盖定向位置优化和完整物理实现，普通工程步骤不增加用户审批门。E006热点与端点的实际结果用于核定候选适用范围；当前E006只读会话继续，单EDA资源尚未释放。新指令不冒充对中止当前正常只读会话的明确答复，原无强停要求保持。

## 假设与唯一变量

以[独立架构候选](../../project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R002/input_frontend_locality_candidate.md)为技术依据，优先测试将tensor输入bank、frontend S24 capture/Hadamard/四量化器及所列附属控制迁至SLR2，减轻SLR1局部逻辑与连线负担。bundle、两组activation cache、Gate/Down调度、compute、tensor输出/DMA与DDR/PCIe互联保持原位置约束政策；不叠加SMC/slice调整。

当前physopt候选77360 primitive：77246已放置且在SLR1、114常量未放置；40627 CLB FF、31709 raw逻辑LUT primitive、8物理DSP、无BRAM/URAM。raw LUT不直接等于原生CLB LUT。候选触及13230 SLICE但仅976当前独占，不能据此承诺腾空站点。1120位量化输出和256位输入是源码静态接口预算，不是完整物理cut、活跃位或SLL用量。实际热点关联、控制往返及端点范围仍由E006补证；若不支持此边界，则先调整候选，而非直接启动未经解释的实施。

## 输入与不变量

采用E005 R004/AT003已资格的debug_materialized.dcp：396068466 bytes，SHA8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f，详见[父链与约束CPU核查](../../agent/A006/followon_placement_parent_cpu_preparation_2026-10-16.md)。保持Vivado2025.2 / xcvu9p-flga2104-2L-e、原144输入、嵌入约束及175项来源身份；不重读已失效的.Xil临时路径，不重复综合、OPT或debug生成。原资格不能替代新尝试检查。

同RTL/IP、算法/数值/format05/ABI/时钟；place=SSI_SpreadSLLs，physopt=Default，route=Default，关闭增量实现。唯一主动变量为上述局部性组的SLR位置要求；placer引起的其他布局变化作为结果记录。无bitstream、板卡、GPU、PPL/ACC，不修改旧工程或E005原始证据。纯放置不重新运行未受影响功能仿真；复用范围和身份明确。若需改变RTL、pipeline或IP结构，应集中修订受影响合同和验证范围，不能称仍为本单变量实验。

## 可执行入口与验收

1. E007独立AT/report/source/附加物理约束与运行收据，沿用已验证guard和post_debug_pre_place恢复入口。E006真实结束并释放单EDA锁后再开实际会话，不热改本次冻结源。恢复适配必须认可真实E005成功place/physopt父链及debug_materialized来源，不能为迁就旧timeout恢复分支伪造中止祖先；继续执行新图pre-place探针。A006在agent/A006中准备薄层适配和选择/约束/测量hook，实际冻结入口另行记录身份。
2. 在实际原pre-place图重新解析候选的精确字面前缀和排除集合，保存NAME/REF/数量/fingerprint；验证两套12288输入索引、四量化器、Hadamard/8DSP，排除常量及DSP内部子对象，确认cache/bundle/tensor输出/SMC/MIG/时钟缓冲没有误选。physopt集合不直接当OPT匹配保证；差异需有阶段语义解释。
3. 核SLR2真实范围、已有LOC/固定属性和资源冲突；加入单个覆盖SLR2的hard Pblock，显式设`IS_SOFT=false`、`EXCLUDE_PLACEMENT=false`、`CONTAIN_ROUTING=false`，只约束选中的可放置物理对象，不为该组排他保留SLR2或限制走线。既有LOC/Pblock冲突不得自动清除。raw语义集合S与可放置集合P分别保存，DSP内部primitive归一到物理父对象；常量和clock buffer不加入P。实际API、属性读回和新图覆盖仍须原生验证，不把设置属性等同迁移成功。完整pre_place资格保持；新图资格失败或重大DRC失败不得跳过原门限进入下一物理阶段，合同内普通修复连续进行。
4. 在同一pre-place会话导出完整候选S/P的canonical连接及全方向leaf端点（IN/OUT/INOUT）、top ports、常量/时钟/复位与unknown；归一物理父对象后标注组内/组外，完整cut不由E006热点UNION替代，时钟/复位与数据/其他控制分列。完整place/physopt/route连续执行。布局后核候选实际SLR分布，区分存活、丢失、新增复制、未放置与未解决对象，核SLR2实际服从率、保留组变化、SLR资源/共享站点、新热点、canonical端点/控制扇出和原80保护边界；复用原timing/CDC/reset/IO检查。资源报告采用exact hierarchy及闭合primitive/site/LOC的CPU统计，避免大leaf-list report_utilization。原固定窗拥塞未测时仍为UNAVAILABLE。
5. 与E005同阶段比较，区分“卸载生效”“压力改善”“合法布通”“setup/hold/PW达标”和全局安全。合法route要求实际无冲突/未布通信号，时序继承全部原时钟约束（含core100MHz、双DDR UI200MHz），不放宽约束。成功路由不自动证明正式CDC/reset/IO/板级验收。若失败，保存原错误、失败DCP、route状态/重叠节点/拥塞失败信号和完整监督终态；不自动叠加下一候选或覆盖失败证据。

## 连续执行与责任

A006为唯一EDA执行者，A007负责独立架构/实际结果核查，主控维护新任务合同、实验摘要和总报告；每份源/记录单一负责人，无后代，总活跃agent不超过3。沿用已登记模型期望与实际未核实状态，不声称模型配置已验证。

单EDA，CPU0–7/nice5/max8线程；树RSS192GiB、MemAvailable低于48GiB持续30秒、磁盘低于30GiB的既有保护保持。正常进程不设墙钟或无输出强停；只管理本任务PID/start，不影响其他任务。普通选择器/入口/解析修复在同一已授权范围内连续完成、保留每次尝试；不为每项修复重开用户审批。关键阶段及时报告，最终真实退出、输入身份、资源及PID/start/锁收尾经独立核查后交付。
