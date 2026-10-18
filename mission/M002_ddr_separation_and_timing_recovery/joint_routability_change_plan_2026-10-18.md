# M002：下一轮联合修改范围与完成标准

2026-10-18，项目主控整合 A006 源码核查和 A007 架构评判。用户要求：“我想知道的是需要修改什么，我希望这次修改能一次到位，一次修改完毕。”

本文件将后继工作收敛为一个配套版本：实际 RTL、物理约束、测试及验证入口一起交付，通过功能与结构核验后再运行完整 implementation。当前是修改范围设计，**生产 RTL/约束尚未修改，没有新的 EDA 或 AT**。全量失败网归因和物理端点映射尚未完成，部分银行数、复制范围及位置仍不能冻结；本清单不是已经验证有效或保证一次布通的补丁。

## 必须先锁定的四张表

利用已保存 AT004 失败图，补齐失败网络的模块×区域统计及代表源/负载拓扑，再形成下列四表。已有原始报告、成员与终态审核直接复用；不为这一步重新综合。

1. 字段—消费者：每组 payload、地址、控制的真正生产者/消费者、扇出与跨区跨度；避免将 top10 样本当全量根因。
2. 状态方程—采样时刻：FIFO push/pop/reset/clear、元数据地址与响应标签的事件及优先级，明确同拍等价要求。
3. 资源—连接成本：新增/减少 FF、LUT、RAM、控制集合及入口扇出；确认吞吐/II 和存储容量不变。
4. 约束实际对象：综合网表中唯一对象、硬块/时钟区、跨 SLR 端点与列映射、兼容资源余量及真实输入注册。

若某一候选仅改变 RTL 名称、把长线转移到上游或引入更多压力，应在冻结修改包之前剔除。面积主导项若由本次归因确认，应在同一次范围收敛中加入，不能因预先只列三个文件就忽略其他主因。

## 联合修改清单

| 项目 | 文件范围 | 具体行为与配套要求 | 当前确定程度 |
| --- | --- | --- | --- |
| MLP parent FIFO 数据分区 | `project/hardware/rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv`；必要的生产者连接在 `hap_mlp_serial_ddr_command16_v5_s54.sv` | 按两个分支需要的字段组织现有 head/tail 捕获点；保持中央 occupancy、两支原子接受、非旁路、满队列行为及现有 branch ingress。局部分发须有实际物理分区配套，限定必要副本保护。 | 字段与等价规则可确定；复制范围/位置及收益待端点归因。 |
| Attention 元数据地址分发 | `project/hardware/rtl/attention/hap_attention_board_cohort16_core.sv`、`hap_weight_meta_resident.sv` | 地址副本与原状态按相同事件同沿更新；维持读采样、单 pending、响应标签与存储读写语义。存储分银行是需资源/时序测量的备选，不能无依据叠加。 | 事件与协议可确定；副本/银行组织需物理和资源依据。 |
| 当前 M002 物理约束 | M002 正式构建/实现入口与新的局部性 overlay | 给被选中的源寄存器、捕获银行和硬块入口明确分区；结合实际跨界端点分散列需求，核验对象数量、真实落区、保护及来源。 | 必须随 RTL 配套；具体区域/坐标尚不能冻结。 |
| 功能与物理验证 | 受影响 testbench、构建输入清单、综合结构及阶段检查 | 一起补齐逐周期协议、数值、生产参数、结构和物理入口验证；生成新来源身份和新综合，不把旧 DCP 当作改后网表。 | 必需配套项。 |

### MLP 的准确设计边界

TILE_W=9 时，当前 parent payload 为 6560 bit，head/tail 共 13120 bit。按消费者的双银行方案，每分支包括：activation2304、acode64、ashift48、weights1536、wcode96、wshift72、mask12、mode/first/last/tile12，合计 4144 bit。两分支各有 head/tail 时总量16576 bit，较原设计增加3456 FF。这是源码状态位成本，不是已实现物理代价或收益。

保留 `parent_pop = parent_valid && ready0 && ready1`；空队列 push 写 head、非空 push 写 tail、满队列 pop 将 tail 搬到 head、占用1同时 push/pop 直接替换 head。保留 reset/clear 对占用的优先级，当前宽数据寄存器无复位，不增加宽数据复位。后续两 entry branch ingress 保存不同在途事务，不能直接删除或合并。

单纯将向量拆成两个变量不会减少网络。必须证明所选数据银行与源和消费位置共同缩短关键连接，且没有把同等或更大的长线需求移到 D 端。共享字段是否复制及具体粒度由前置四表确定；不默认将整个宽 payload 完整复制。

### Attention 元数据的准确设计边界

原 `meta_read_addr_r` 还用于响应 tile/group 标签。首选同事件状态副本遵循原异步 reset、`system_clear`、`ST_LAUNCH && weight_command_ready` 的清零，以及 `meta_rsp_fire` 时递增，并保留原赋值优先级。目标不变量是每个有效采样周期 `local_addr == original_addr`；从原 Q 再打一拍不满足该条件。`datapath_clear` 含 abort，不能直接代替原地址全部清零事件。

保持按 response 消费推进地址，可沿用现有 FSM 和标签规则；若改变为 request 接受即推进，需另锁响应标签并重新修订协议，不能暗中作为等价修改。

深度分银行可评估10×8192×256等组织，但这会引入银行选择、响应选择器及新的布局需求。其银行数、80个URAM映射、同址读写行为和输出路径必须核实；不作为当前确定必改项，也不增加未声明的输出流水级。

### 正式物理入口与检查

`project/hardware/vivado/scripts/m002_physical.tcl` 第19行起与 `build_vcu118_board.tcl` 第457行起明确拒绝历史 `mission0004_metadata_width_local.xdc`、`mission0005_coordinated_partition.xdc` 成为M002活动输入。新约束须在M002正式入口注册并采集来源，更新fresh对象/数量/落位核验；修改这两个历史文件不能构成本轮有效优化。E008冻结运行包保留，以新的包和来源身份进入后继流程。

SLR0/1/2当前physopt occupied CLB为94.95/99.68/99.92%，不是LUT槽全部耗尽。新分区必须考虑站内打包、DSP/URAM/BRAM及pin接入空间；SLL初始估计表列号不能直接转换为X/LOC/BEL坐标。80保护边界、板级时钟/接口及正式验收保持。

## 一次配齐的验证

- MLP：复用 `hap_mlp_shared_dual_s44_s54_dispatch_tb.sv` 的整数参考、Gate/Down、mask、事务守恒、II=1、反压与clear验证；补生产TILE_W=9、所有占用/push-pop边界、两支非对称阻塞和新旧逐周期ready/valid/payload/status比较。
- 元数据：补专测覆盖银行/末地址/越界、读写碰撞、响应停顿、clear/abort/launch后的地址与标签对齐、计数/格式检查及同拍行为。既有上层测试不能代替这些边界证明。
- 算术：现有DSP与量化精确规则保持。若归因后纳入内部结构改动，必须补受影响位精确、舍入/溢出、吞吐及协议回归；E005已完成input48/CE32不重复当作新优化。
- 综合与实现：新综合确认实际副本没有被无意合并、保护仍有效、资源成本与字段/消费者一致，验证overlay确实消费正确对象。随后同一个固定版本完整place→physopt→route；setup/hold/PW、合法路由、DRC、CDC/reset/IO及bus-skew覆盖分别验收。

“一次集中改完”意味着在完整物理实验之前，将选定RTL、约束、验证和入口适配集中完成；常规编译和功能修复在该版本内连续进行，不逐项增加用户批准门。合法布通仍由最终零冲突/零未布通及完整验收报告决定，无法在测量之前保证第一次物理实验成功。

## 依据

- [Q003当前解释与源码定位](../../question/Q003_M002_route_overlap_remediation/answer.md)。
- [A007联合包架构审核v2](../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/joint_change_package_architecture_review_20261018_v2.md)。
- [E008实际终态](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/summary.md)。

本文件保留待定项，不创建新执行尝试，也不将候选优化解释为已经实施。
