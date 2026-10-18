# AT004 route 中途警告独立审核

execution：已完成只读原文核对；观察位于 route 初始化及 Phase 3/3.1，属于非终态。verdict：确认列局部 SLL 超额与 bus-skew 路由优化覆盖缺口，route 成败未定，正式 reset/CDC/IO 安全保持 OPEN。review：独立有界审核完成，不新增停点。

工程 facts 和 74 行原生片段已校验身份，并与实际 vivado.log 第 254216–254289 行逐字一致。

| SLR 边界 | 总估计需求/容量 | 超容量列数 | 最大列需求/1440 |
| --- | ---: | ---: | ---: |
| 1–2 | 11,721/17,280（67.83%） | 2 | 1,748（121%） |
| 0–1 | 12,180/17,280（70.49%） | 4 | 2,296（159%） |

SLR1–2 另一列为 1,445/1,440，原生日志四舍五入显示 100%，仍已超额。总余量不能抵消列局部需求；两次表格是 Phase 3 与 3.1 的重复估计，不相加，也不等同候选 cut pair、最终已分配 SLL 或带宽。Route 35-3311 表示可能无法找到布线解，尚不是失败终态。

Route 35-462 明确列出 6 条未 populate 的目的路径：attention command1 的 bit14/16（grp84）、attention command0 的 bit14/16（grp85）、MLP command1 的 bit16/15（grp86）。Route 35-470 明确说 MLP command0 的 src_hsdata_ff_reg[16]/Q 与另外 2 bits 共享，相关 bus-skew 组将被忽略；日志未打印该组 ID。

按对象名核对，前三组的目的 cells 分别属于 physopt 报告约束 ID85/86/87，忽略警告的源 cell 属于 ID88；对应 requirement 均为 10 ns，之前报告 slack 为 +8.877/+9.292/+9.411/+9.469 ns。内部 grp 编号和报告 ID 不按数字猜映射，第四项只确认源对象集合匹配。既有 94 项 MET 仍是此前 physopt 报告事实，不能证明 route 中所有路径均被纳入优化，也不能换算成“剩余若干组已完整覆盖”。警告本身不证明断连或 CDC 功能失效，但覆盖缺口不能被 MET 数字掩盖。

旧 E005 R004/AT004 同为 Vivado 2025.2 build6299465、同器件、Default router、8 CPUs。grp85/86 的 4 条缺失目的路径和 MLP command0 忽略警告逐项相同；attention command1 旧为共享驱动导致整组忽略，本次变成 2 条路径未 populate，不能据此认定已经修复。旧 route 日志未出现同阶段 SLL 需求表或 35-3311，无法作跨轮 SLL 数值改善比较，缺少警告也不证明旧需求为零。

同阶段 35-445 的高 pin CLB 报告下界为旧 804、本次 135，分别列出 10/7 段。仅可报告该类别数字减少 669；位置和全局布局不同，尚不能据此证明固定热点改善、C01 因果收益或已可布通。

初始化的 2,031,260 failed nets = 1,827,047 unrouted + 204,213 partially routed，node overlaps=0；旧初始化也有 2,031,299 failed nets 和 0 overlaps。这些都不是最终合法性结论。中间 WNS +0.181 ns、WHS −0.562 ns 等同样不作最终时序验收。

按现有合同继续正常 route。自然终态后，现行最终验证须结合实际 route status/timing/DRC、bus-skew 报告和上述精确对象覆盖核对，保留 ignored/unpopulated 差异；不能删除或放松约束来消除警告，也不能仅以 route 命令成功关闭正式安全 OPEN。本审核不新增停点或批准门。

详细对象、原文行号、身份与比较范围见 [JSON 审核记录](route_initial_global_warnings_review.json)。
