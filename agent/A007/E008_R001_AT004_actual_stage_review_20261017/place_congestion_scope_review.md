# AT004 place 拥塞报告覆盖审核

execution：实际闭合报告解析完成；verdict：接受工具给出的自适应窗口证据，尚不支持固定窗口或候选压力改善；applicability：Fully Placed / min_congestion_level 3；review：A007，无新增停点。

本轮与旧 E005 都有 48 行：四方向 × Global/Long/Short × level3/4/5/6，最高报告 level 仍为 6。同方向/类型/level 的 48 个窗口坐标全部改变，不能直接相减窗口百分比当作同一区域改善。

C01 字面 hierarchy 在本轮每行所列的三个贡献者中出现 0 次，旧轮为 24 次。只能确认所列热点贡献者发生变化；缺席不能证明候选拥塞为零、所有 P 已迁移、完全离开热点或是 C01 导致的改善。候选实落仍待完整 locality/reconciliation。

报告提供工具选择的窗口、资源百分比及每行三个 hierarchy 贡献者，不是完整固定网格 demand/capacity，也未提供 SLR 列；本审核未将 tile Y 数值自行映射为 SLR。低于level3、未列窗口/贡献者不可当0，NA不改为0。原热点固定窗口拥塞仍为 UNAVAILABLE，本次没有额外查询。

保留当前高拥塞风险，待完整POST和最终route/timing验收；本子步骤不判断布通或C01方法成功。

[机器审核与实际窗口](place_congestion_scope_review.json)
