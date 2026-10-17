# E008：单个热点模块卸载协议

权威：[SM012原执行合同](../../../mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md)与[有向cut范围修订](../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)共同适用。C01/C02资源引用E006/R004已闭合结果，有向边界/时序及实际选择依赖E006/R005，当前尚未选择。候选绑定必须有真实证据，不以此计划代替。

同 E005 debug_materialized 父图、同 RTL/IP/时钟/数值和 place/physopt/route directive，唯一主动变量为一个选中模块的 SLR2 hard、非排他、不限制走线 Pblock。先核实际 RAW/S/P、原有硬约束和完整 pre-place/cut，再完整实施。原输入前端 E007 保留为探索对照，不改其原主题。

实际源码、命令、输入、选择依据及 PID/资源/收尾由新 R/AT 保存；当前尚无 R/AT 或实际实现。原始证据不覆盖，正常进程无墙钟/无输出强停。

新口径共通入口源码准备已完成，最终 [manifest](../../../agent/A006/directed_candidate_cut/E008_entry/prepared_manifest.json) 为11126 B / `1d612c65a3900669eb6fb73eac8f127e7955f5ef63879035601c486904f16706`，含13份自有源码、16份复用源码及2项CPU记录。[独立源码核查](../../../agent/A007/E008_directed_review_20261017/final_review.md)通过，实际P投影/空时序账本及原物理保护均已核。原b59与中间9f包保留，native/pre-place/implementation仍未执行。真实选择与E006收尾仍是实际依赖。

E006/R005 AT001因其独立inspector缺少owner辅助函数而自然失败，尚未进入新cut采集，正在同范围修复重试。本入口的runtime_hooks保留自身完整owner，未受该缺失影响；共享collector局部测试不等同完整诊断入口原生通过。
