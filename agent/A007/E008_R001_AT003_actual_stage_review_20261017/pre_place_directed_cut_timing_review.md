# AT003 pre-place 有向 cut 与有界时序独立审核

- execution：闭合原始文本完整重放完成；verdict：接受；applicability：仅 AT003 pre_place；review：完成。
- 实际归档 validator 完整重放并逐字段等于实际摘要；原始 18 项 cut 投影及新增 timing 投影身份均已核对。DCP 仅核对工程绑定元数据，未读取或哈希 DCP。
- 14,307 条网、55,605 个候选 leaf pins、1,276 个断开 pins、58,361 个保留端点；3,087 个外部驱动定向 ingress、11,220 个候选驱动完整枚举。完整 JOIN、成员、方向、native class/role、别名和 timing scope 均通过。
- 44,054 个候选相关 driver/load pairs，21,479 个边界 pairs；所有位置均 UNPLACED。已知 crossing=0 不能解释为跨 SLR 或拥塞改善。
- 完整方向引脚集 ingress 20,534、egress 945。max/min 各返回16条，64条原生报告与表的起点、终点、slack、datapath delay逐项一致。最差 setup 为 +6.158/+6.859ns，hold 为 −0.074/+0.081ns（入/出）。
- 查询采用 through-pin 集合，可能覆盖内部或其他驱动路径；不保证每条返回路径经过候选边界边。布局前估算不可与旧 physopt 值作改善比较，非 full-cut TNS 或时序签核。物理实现继续。

机器证据见 `pre_place_directed_cut_timing_review.json`；重放脚本及输出单独保全。
