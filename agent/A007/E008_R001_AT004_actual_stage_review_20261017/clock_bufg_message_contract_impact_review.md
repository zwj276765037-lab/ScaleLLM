# AT004 Phase 4.1 时钟与 BUFG 提示审核

execution：只读核查完成；verdict：纳入现有 POST/route 判断，无新增停点；applicability：仍在 place_design 内部，未完成 place/POST，未启动外层 physopt；review：A007。

`Place 30-1995` 为 WARNING。本轮 DDR0 的 c0_riu_clk / u_bufg_divClk_0 早期 Clock Region Placement 报 cap 6/5，Phase 4.1 改为 3/3；旧 E005 在 Phase 4.1 对相同两网也报 3/3。原文是为 BITSLICE_CONTROL_PLL_RIU MAX_SKEW 要求限制水平 BUFCE_ROW 可编程延迟，是工具处理约束的决定，既不是已测 skew 违规，也不是 skew 已通过。日志未给 cap 的时间单位，不能写成 3 ns、频率或 slack；也没有放松时钟/MAX_SKEW 的证据。

`Place 46-33` 实际为 INFO。本轮已闭合的 BUFG 插入子过程汇总为候选 11、插入 0、复制 driver 0、因布局/走线冲突跳过 11，其余跳过原因均 0。全部 11 个目标均不在字面 C01 内。旧轮为候选/跳过 22，精确网名交集 9（含 shared_compute/parent_tail_r[0]）。候选集合不同，不能用 11 比 22 判拥塞或优化改善；这也不是全设计 BUFG 数量。跳过这项优化不等于必须时钟缺失、信号未布通或功能失败，本子过程亦无已实现的插入收益。

当前日志已到内部 Phase 4.1.1.3 Post Placement Timing Optimization；其中 Physical Synthesis/Phase 1 字样属于 place_design 内部。现有观察没有 place 成功或外层 phys_opt_design 命令。旧轮后来 place 成功，只证明这些类别当时非致命，不保证本轮布线/时序。

继续既有 fresh POST/locality、80 个保护边界、全局 clocks/DRC/setup/hold/PW 及适用 skew 证据检查，最终按真实 route 状态验收；不改参数、约束、消费包或工程摘要，不加审批门。后续同类新增消息须另以有界观察记录，不把本次摘录称为持续监控。

[机器审核](clock_bufg_message_contract_impact_review.json) · [带原行号摘录](AT004_clock_bufg_observed_excerpt_20261017.json)
