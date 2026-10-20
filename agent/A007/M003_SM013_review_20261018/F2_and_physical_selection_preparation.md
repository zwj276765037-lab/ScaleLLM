# SM014 F2 与物理选型审核准备

2026-10-18；A007。execution：有界源码阅读和审核要点准备完成；verdict：仅描述现有语义与后续证明义务，未选择候选、银行数或物理坐标；applicability：下列源码身份及 M003 合同；review：内部准备，未执行编译、仿真、新综合或 EDA。

Root 在本轮真实消息中已明确：下述“满 FIFO 非直通 credit”和“meta launch/rsp_fire 同拍 NBA 优先级”是 G2 必核项，不得简化成事件列表相同。此为主控对现有周期不变量的具体核验要求，未增加用户审批或原生查询范围。

## 读取来源

2026-10-18T00:30:23.620402+00:00 记录身份，仅检查相关声明、握手和状态更新片段，未全量审计模块。

| 源码（`project/hardware/rtl/` 下） | 字节 | SHA256 |
| --- | ---: | --- |
| `mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv` | 35274 | `a9818a41ef29c1f9d364f7477fdd7128d477d7cb5feed630384d6eb727114db3` |
| `attention/hap_attention_board_cohort16_core.sv` | 40528 | `c40e986c0c0371bb5f86715ddfea0d0731b8ec3fe3324340e11c4571a42b842e` |
| `attention/hap_weight_meta_resident.sv` | 4933 | `a0ccf69e9ebb1d952a9cc5d043c78ab3bf56e1f6622ad9f246fdf02a858f7153` |

## 1. Parent FIFO 必须保留的转换

共享模块第 115–124、215–240 行：`in_ready = rst_n && !clear && count!=2`；`pop = parent_valid && ready0 && ready1`。分支 valid 含对方 ready，因此两个分支同沿原子接受，远端 ready 只影响 pop。不能把满队列当拍 pop 加进上游 ready，这会改变外部接受周期并重新形成 ready 组合路径。

以下 push 为实际 `in_fire`，不是裸 in_valid；表以无 reset/clear 为前提。

| 原占用 | push / pop | 新状态 |
| --- | --- | --- |
| 0 | 0 / 0 | 保持空；payload 无效不要求清零 |
| 0 | 1 / 0 | head←新 payload；count=1，不当拍旁路下游 |
| 1 | 0 / 0 | 保持 head 和 count |
| 1 | 1 / 0 | tail←新 payload；count=2 |
| 1 | 0 / 1 | count=0；旧 head 之后无效 |
| 1 | 1 / 1 | head←新 payload；count=1 |
| 2 | 0 / 0 | 保持满；上游 ready=0 |
| 2 | 0 / 1 | head←旧 tail；count=1，上游此沿仍不接受 |

count=0 时 pop 和 count=2 时 push 均不可由原合法握手产生。同步 `!rst_n || clear` 只清 count；原 head/tail 无宽复位。局部银行必须按同一 push/pop/clear 事件采样原输入字段或旧 tail，保留非阻塞赋值的旧值语义及两个分支的字段一致性。两 entry branch ingress 保存不同在途事务，不能因复制字段而删除。

F2 必须给出每个选定字段的新旧 D/CE/reset/保持方程及上述转换的断言；同时核逐周期 ready/valid、有效 payload、事务守恒与非对称 stall。只比较最终算术结果不够。

## 2. Meta 地址与响应时序

core 第 270–285、354–355、441–459、484–505、630–633、679–684 行确认：地址既供存储读地址，也供响应 tile/group 标签；请求受单 pending 约束，原地址按 response 消费推进。地址寄存器异步 reset，system_clear 在外层优先清零。普通周期的 `ST_LAUNCH && weight_command_ready` 赋零在 case 中，之后的 `meta_rsp_fire` 赋 `old_addr+1` 在同一 always 的更后位置。

因此同拍两个赋值若同时发生，原 RTL 的最后一次非阻塞赋值优先。F2 应保持该顺序，或以明确可达性不变量证明冲突不可达；不能仅凭口头“launch 优先”重写。`datapath_clear = system_clear || command_abort_clear_r` 送往子模块，但地址原状态并非遇每个 datapath_clear 都清零，不能直接替换事件集合。

本地地址副本必须同沿由相同旧状态/事件计算，不能 `local <= original` 增加一拍。至少在每个有效存储采样沿证明 local 与原地址相等；response 消费前标签保持与所读数据对应。将推进改到 request 接受属于协议变更，不能隐藏在副本复制中。

resident 第 38–53、74–119 行确认原存储非 fall-through 请求令牌、response 寄存器、reset/clear 及计数优先级。响应 stall 保持有效数据；同址读写在当前 RTL 中同沿读旧存储值，综合后的 URAM 实际模式须另核，不能凭 RTL 仿真推定物理 read-during-write 行为。条件性分银行必须同沿选择 bank/data、保持响应 mux 延迟和所有边界行为，不自动增加输出级。

## 3. 物理选型排除条件

以下是候选资格检查，不是已发生的候选缺陷：

- 只有重命名或层次拆分，预期网表连接未改变；没有可证伪的消费者局部化机制。
- 新副本只移动长线到上游 D/CE/reset，未核完整来源和消费者；盲目增加宽 reset 或全域 DONT_TOUCH。
- 用 occupied CLB 直接推导槽位耗尽，或把 SLR2 当空闲区；缺兼容打包、硬块接入、原物理父/macro 和原硬约束证据。
- 从 SLL 报告列号猜 LOC/Pblock 坐标；没有器件对象映射或新图匹配仍宣称已冻结可执行坐标。
- 只用 top10、重叠节点重复出现次数或分组成员数之和宣称全量根因；候选关键端点未知却已选入。
- 去掉 80 保护或改动时钟/数值/外部协议；以精度、吞吐、容量或可观察延迟损失换布通。
- 未计额外 FF/LUT/mux、时钟/CE/reset 负载及存储实际映射；资源估算冒充已测物理收益。

在 G1 完成前，不预选完整双银行、10×8192 存储划分、C01 约束变化或新策略。G1 只建立事实范围，SM014 集中选择，SM017 新图和后续物理结果分别证明结构与效果。
