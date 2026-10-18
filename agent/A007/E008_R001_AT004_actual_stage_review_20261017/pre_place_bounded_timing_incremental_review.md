# AT004 pre-place 有界时序增量审核

- execution：实际归档验证器重放完成；四组共 64 条原生路径的起点、终点、起终时钟、slack 和 data path delay 与表逐项一致。当前报告日期及原生日志的完成事件绑定通过。
- verdict：接受完整方向查询集合及有界结果。INGRESS 20,534 / EGRESS 945 个 LOAD 引脚，max/min 各 16 条、nworst 1。最差 setup 入/出为 +6.158 / +6.859 ns；最差 hold 为 −0.074 / +0.081 ns。语义及统计与已审 AT003 一致。
- applicability：仅本轮未布局的 Optimized 图。through-pin 查询可能返回内部或外部驱动路径，并不保证逐路径跨候选边界；非 full-cut TNS、时序签核或迁移改善。查询 ledger 无逐行 epoch，绑定依据为本轮投影、index/cut、报告日期及已完成日志事件。
- review：本子步骤接受，无新增执行停点。完整 pre-place 与 place/route 另行审核；未读取或哈希 DCP。

[机器审核与 64 条路径核对结果](pre_place_bounded_timing_incremental_review.json)
