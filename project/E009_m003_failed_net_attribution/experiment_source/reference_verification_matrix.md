# M003：验证与验收矩阵

本矩阵属于[主合同](contract.md)，定义需取得的证据。2026-10-18创建；M003工程项均NOT RUN，设计决定OPEN。“通过条件”不是已有结果。

| ID | 对象 / 必测内容 | 通过条件和证据 | 阶段 / 当前状态 |
| --- | --- | --- | --- |
| A01 | E008失败DCP、原网数与阶段身份 | 原始清单/hash一致、口径明确，不改父产物 | SM013 / NOT RUN |
| A02 | 全部冲突网、alias、模块×区域 | 可对账，未知/多driver/时钟单列，网/端点/连接对分开 | SM013 / NOT RUN |
| A03 | 前20组、所有拟改对象 | 实报覆盖率，关键源/负载/硬块/跨界映射完整 | SM013 / NOT RUN |
| D01 | F1字段与F2状态采样 | 原/新D/Q/CE/reset与有效采样等价，无关键未知 | SM014 / OPEN |
| D02 | F3成本、F4物理策略及选型 | 银行/副本/策略明确、预算可检，C01变更显式记录 | SM014 / OPEN |
| F01 | MLP生产TILE_W=9、小参数、Gate/Down、mask | 独立整数参考位精确，覆盖/seed保存 | SM015–016 / NOT RUN |
| F02 | occupancy=0/1/2及所有合法push/pop | 计数/head/tail/同时出入队逐周期一致 | SM015–016 / NOT RUN |
| F03 | 非对称stall、单支ready、连续背压 | 原子接受，无丢失/重复/乱序及新增ready组合环 | SM015–016 / NOT RUN |
| F04 | MLP在途reset/clear、有效payload稳定 | 原优先级、清空、队列容量保持，无效payload不误判 | SM015–016 / NOT RUN |
| F05 | ready/valid/有效payload/status及接受/返回周期 | 新旧逐周期一致，II/吞吐/延迟不变 | SM015–016 / NOT RUN |
| F06 | Meta地址副本 | 有效存储采样沿local==original，事件同沿/优先级等价 | SM015–016 / NOT RUN |
| F07 | 首/末/银行边界/越界 | 原边界行为、格式/错误计数等价；选银行则所有边界覆盖 | SM015–016 / NOT RUN |
| F08 | 单pending/token、stall、同址读写 | 数据/响应/读写冲突语义不变，无额外延迟/吞吐损失 | SM015–016 / NOT RUN |
| F09 | reset/system_clear/abort/launch/meta_rsp_fire组合 | 地址/标签/FSM/计数与原完整优先级一致 | SM015–016 / NOT RUN |
| F10 | 选入的DSP/除法/量化内部变化 | 独立位精确参考、合法范围/边界、符号/舍入/溢出和协议通过；未选可N/A附据 | SM015–016 / NOT RUN |
| F11 | 系统接口/DDR/Host/format05适用性 | 影响范围完整，变化项新验，未变证据按身份复用 | SM016 / NOT RUN |
| C01 | 正式overlay注册/加载 | SM016完成入口实现/测试，SM017新图原生加载/来源SHA/数量/属性一致，旧禁用XDC仍拒绝；分别记结果 | SM016–017 / NOT RUN |
| C02 | 空匹配/少对象/错身份/保护缺失负对照 | SM016必要正负对照；SM017核真实新图/恢复父图，不能以准备完成提前记原生PASS | SM016–017 / NOT RUN |
| C03 | 原硬约束、物理父/macro、80保护 | 新图完整解析，无误改，C01只按冻结决定改变 | SM017–018 / NOT RUN |
| S01 | 新RTL→新综合→新manifest | 源/参数/IP/XDC/Tcl完整，DCP可打开，不以旧图当新网表 | SM017 / NOT RUN |
| S02 | 实际副本/银行与消费者 | 合并/复制/丢失可解释，符合F1–F4，D端及CE扇出纳入 | SM017 / NOT RUN |
| S03 | 资源/控制集合/容量 | 估算实测分列、偏差处置，银行方案的80-URAM映射实核 | SM017 / NOT RUN |
| S04 | opt/debug/pre-place及最终策略/对象 | 身份一致、非法约束/容量冲突关闭，实现输入冻结 | SM017 / NOT RUN |
| P01 | place/独立physopt完整阶段 | 原生命令/DCP/POST齐，实际落位/存活符合设计 | SM018 / NOT RUN |
| P02 | 三SLR打包/硬块/固定与新最坏热点 | 同阶段口径，无法取得标UNAVAILABLE，不用occupied CLB断言槽满 | SM018 / NOT RUN |
| P03 | 跨SLR/SLL、局部及上游扇出 | 估计/实测分开，说明是否转移压力，不把改善当根因消除 | SM018 / NOT RUN |
| R01 | 合法路由 | 原生成功、closed DCP、完整POST，routable>0且全部fully routed，未布/部分/错误/冲突/重叠均0 | SM018 / NOT RUN |
| T01 | 合法routed全时钟setup | WNS≥0、TNS=0、违例端点0，覆盖完整/例外合法 | SM018–019 / NOT RUN |
| T02 | 合法routed全时钟hold及脉宽 | WHS/WPWS≥0、THS/TPWS=0、违例端点0 | SM018–019 / NOT RUN |
| T03 | 原100MHz setup/hold余量 | 原目标≥+0.5ns分别实报，不以0ns规则PASS替代 | SM019 / NOT RUN |
| G01 | DRC、warning/Critical Warning | 完整原报告，逐项归属/修复/依据，无未解决DRC违例 | SM017–019 / NOT RUN |
| G02 | 正式CDC/reset/IO | 每项源/端点/同步复位/例外有证据，未证明保持OPEN | SM017–019 / NOT RUN |
| G03 | bus-skew目的pin/shared source及未覆盖路径 | 完整覆盖并满足规则，关闭E008六个未populate目的pin及ignored组等缺口，不用例外掩盖 | SM018–019 / NOT RUN |
| H01 | 终态收尾、失败保全和来源 | 原exit/时间、PID/start消失、锁释放、资源/输入核验，失败尽量保全诊断 | SM018–019 / NOT RUN |
| H02 | 独立审核/三摘要/主控总报告 | 逐项PASS/FAIL/OPEN/有据N/A，execution/verdict/applicability/review分开 | SM019 / NOT RUN |

NOT RUN代表未执行；OPEN代表证据/设计未关闭。N/A须有适用性依据，不得隐藏失败；合法路由、时序、原目标余量、保护、安全和最终交付不能整项N/A。任何外部可观察数值/周期差异都需修复或明确修订范围，不能仅凭最终值相等忽略协议变化。

结构合法但负时序可以进入诊断route，不因此强停正常进程；最终签核仍须满足必要条件。全局判断按主合同第9节，指标改善或收尾成功不代表mission目标完成。
