# AT004 高拥塞提示与临时 WNS 审核

execution：有界只读审核完成；verdict：确认 placer 报告高拥塞风险，未建立失败或候选效果；applicability：Phase 4.1 告警及随后原生 place 命令成功，完整 POST/locality 尚未闭合；review：A007，无新增停点。

本轮日志 85273 的 `Place 46-14` 明确提示 highly congested / may have difficulty routing，与旧 E005 同阶段 1005 行原文完全相同。该风险需保留供布线结果解释；它不是已发生的布线失败、place 失败，也不提供候选或 SLR1 的定量压力变化。旧轮也有该提示不代表本轮风险相等或已消除，更不能据此判 C01 有效/无效。

`Place 30-746` 和 `Place 46-19` 的内部 WNS 均为 +0.147，旧轮均为 +0.103；原文都要求完整 report_timing 获取更准确结果。仅保留临时原值，不把差值解释为候选改善，不宣称 setup/hold/PW、TNS、CDC/reset/IO 或 routed timing 收敛。

核验期间日志继续推进至 85360 行 place_design completed successfully；原生命令回执 code 0，start 1792231620 / end 1792239478，耗时 7,858 秒。仅确认 place 命令成功，完整 POST/locality 结果仍未生成，尚无外层 phys_opt_design 命令。两条 DDR0 cap3 提示在该阶段后再次出现，本前缀共 6 条；数值未变，不据重复计数新增 skew 失败。已归档 m002_post 原有 congestion（min level 3）与完整 timing summary 入口保持，将在既有流程执行；本审核没有新跑任何报告。

初次审核脚本因“place 仍未完成”的状态断言过时而停止，未产出结论；保留该脚本，V2 按新日志和回执更新，非设计失败。正常流程继续，后续按真实阶段 facts 独立核完整 POST/locality、80 个保护边界、同阶段拥塞与时序、最终 route 状态。

[机器审核](congestion_provisional_timing_review.json) · [前后阶段及原行号摘录](AT004_congestion_timing_observed_excerpt_20261017.json)
