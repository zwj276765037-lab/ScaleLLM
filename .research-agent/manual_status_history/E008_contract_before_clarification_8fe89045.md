# M002 / SM012 / E008：单个热点模块向 SLR2 卸载与完整 implementation

用户已授权“进行针对性优化后开启下一轮implementation”。本合同将 E006/R004 的候选比较接到实际物理验证，沿用该授权，不增加用户批准门。当前仅准备后继入口，候选尚未选定，实际 implementation 未启动。原 SM011/E007 输入前端候选保留为探索对照，不将其源码准备结论改写为热点迁移已获支持。

## 候选与唯一主动变量

E006/R004 的两项精确候选独立比较，实际执行时最多选择其中一个：

- C01：`scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`。
- C02：`scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_down_scheduler/u_weight_repack`。

选择依据是 R004 原生资源、完整连接、位置/约束、有界当前时序、热点和失败样本交集，以及 SLR2 已闭合原生容量。主控在真实证据到达后将候选 ID、字面 root、依据和适用限制写入 E008 的实际执行绑定；空选择或二者均不支持时不得启动，不能将两个候选合并或改用旧输入组。选型是现有授权内的工程判断，无新增用户批准。

唯一主动变量为选中模块的 SLR2 位置要求。维持 E005 的 RTL/IP、数值、Hadamard、ScaleCode、format05、Host ABI、双 DDR 和时钟，place=SSI_SpreadSLLs、physopt=Default、route=Default，关闭增量实现。placer 引起的其他位置变化作为结果记录。若需 RTL/pipeline/IP 变化，应集中修订受影响范围和验证，不能冒充本单变量物理实验。

## 输入与复用边界

父输入为 E005/R004/AT003 的 `debug_materialized.dcp`，396068466 bytes，SHA256 `8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f`。采用真实成功 place/physopt 父链的恢复适配，保留 Vivado2025.2 / xcvu9p-flga2104-2L-e、144 冻结生产输入与 175 项约束来源身份。继承 DCP 嵌入约束，不重载消失的 `.Xil` 临时文件；不重复综合、OPT/debug 生成或未受影响功能测试。复用结果标明原运行身份，不写为本次新实测。

复用 E007 已验证的物理流水与监督器，重新绑定本合同、选中 root、新实验/尝试和实际源码身份。E006 physopt 集合只是选型证据，不是新 pre-place 匹配保证。前置 E006 必须真实结束并完成输入/进程/锁收尾，单 EDA 资源释放后才启动本实验。

## 实际资格、位置要求与完整流程

1. 新的 AT、报告、冻结运行源和收据独立保存。在实际 pre-place 图唯一解析所选 root，字面匹配后代（尤其 `[1]`），重建 RAW（保留常量）、S（仅排除 GND/VCC）、P（真实可放置物理对象），记录 NAME/REF、数量、fingerprint 和映射。DSP 内部 primitive 按实际父关系归一到 DSP48E2；保留原生 BRAM/URAM 与其他资源，不继承旧两套 12288 bank、四量化器/Hadamard、8 DSP、无 BRAM/URAM 或旧排除表断言。未知资源和映射显式处理，不静默丢弃。
2. 保存 S/P 的实际 LOC/BEL、固定属性、USER_SLR、Pblock、RLOC/macro 和实际物理父约束。既有硬约束不得清除或软化；组外 macro 搭档、专用时钟/IO 等冲突必须按实际证据解释，未解决则不得进入布局。原完整 pre-place 资格、80 个保护边界、timing/CDC/reset/IO 检查保持。
3. 建立一个覆盖真实 SLR2 clock-region 全域的 hard Pblock，显式 `IS_SOFT=false`、`EXCLUDE_PLACEMENT=false`、`CONTAIN_ROUTING=false`。只约束合格 P，不排他保留 SLR2、不限制走线。原生读回范围、SLICE/DSP/RAMB18/RAMB36/URAM 站点及成员；核非候选原约束没有变化。容量可容纳不代表打包或布通。
4. 同一实际图导出完整 S/P 附着 canonical nets/aliases、leaf IN/OUT/INOUT 与 top ports，保留常量、时钟、控制、未知、多 driver 及组内/组外位置。时序入向采用完整组内 LOAD 集合、出向采用完整组外 LOAD 集合，各 max/min cap16，未知方向单列；不把 cap16 当全 cut TNS 或签核。P 父 policy、站点共享/独占和成员映射保持可核查。
5. 资格通过后连续完成 place → physopt → route，按既有真实检查规则处理常规错误，不逐项增设审批。布局后解释存活、复制、新增、丢失与未放置对象；要求已解析 P 全部实际位于 SLR2，unknown/missing/unplaced/outside 不得假通过。记录非候选变化、SLR 资源、共享站点、热点与完整连接代价；资源统计使用 exact hierarchy 原生报告，避免大 leaf-list 逐项报告。无法取得的固定窗拥塞仍写 UNAVAILABLE。

## 判断、交付与失败保全

与 E005 同阶段比较，分别判断卸载生效、局部压力变化、合法布通、setup/hold/PW 和系统安全。合法 route 须以真实 route 状态、无冲突/未布通信号及完整报告为证；保持全部时钟要求（含 core100MHz、双 DDR UI200MHz），不放宽约束。路由成功不自动证明正式 CDC/reset/IO 或板级验收。

若自然失败，保存原错误、失败 DCP、route 状态、重叠节点、拥塞失败信号和真实监督终态；输入身份、资源、PID/start 与锁收尾必须真实核查。失败不能覆盖，也不自动叠加另一个候选。当前合同只授权这次选定范围的完整实现及常规修复，不预判成功。

## 分工与资源

A006 唯一 EDA 执行者，拥有准备源码和运行证据；A007 负责架构和实际结果独立核查；主控维护合同、实际选择绑定、实验摘要、任务与索引。复用当前 agent，不绑定旧对话；最多 3 个活跃 agent 含主控，无后代，保留他人改动。期望模型与实际未核实配置继续分开记录。

单 EDA，CPU0–7/nice5/max8；树 RSS192GiB、MemAvailable 低于48GiB持续30秒、磁盘低于30GiB 的既有保护保持。正常运行无墙钟或无输出强停；仅管理本任务 PID/start。用户原 R001 停止例外不扩展到本次。无 bitstream、板卡、GPU、PPL/ACC；旧工程及全部原始证据只读保留。
