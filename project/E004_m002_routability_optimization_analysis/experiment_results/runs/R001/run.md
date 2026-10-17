# R001 — E004

Recorded: 2026-10-15T23:14:51.802357+00:00

Execution state: completed
Verdict: supported（仅已核物理事实）；优化收益未实施验证

负责人 A006 `/root/m002_build_verify`；本批只写 R001 与 agent/A006，不改生产实现，不开后代。当前分析合同见 [SM008](../../../../../mission/M002_ddr_separation_and_timing_recovery/routability_analysis_contract_2026-10-16.md)。

- 实际尝试：[AT001](attempts/AT001_readonly_physopt_diagnostics/started.json)，2026-10-15T23:25:10.387090Z 启动。只读单次 open/report/get，原始 argv/cwd、输入 SHA、身份与资源策略都在尝试目录。
- 平台：Vivado2025.2 / xcvu9p-flga2104-2L-e；恢复成功 physopt DCP，SHA `c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91`，568389035 bytes。不是失败 route DCP。
- 资源：单 EDA、CPU0–7/max8/nice5；树RSS192GiB、MemAvailable48GiB持续30秒、磁盘30GiB；无 wall/no-output 强停。
- 真实结束：2026-10-15T23:53:35.703493Z，native/监督/工具会话均0，stop_reason=null；5个PID/start身份及supervisor均退出，单EDA锁独立核实释放。48query中35code0/13help失败；自建BEL槽hist语义INVALID，站点计数有效。
- 已知查询异常：13个初始 help 因 `redirect` 不存在而 code1；不影响 open/report/get。只向同一原生实例的本地 Tcl 接口尝试 help 恢复，客户端超时只表示 RPC 未获答，不是 EDA 超时/停止。不会因此重开检查点。
- 独立核验：既有 native 资源/控制集合报告复算；BEL负载精确算术分解见 [计数核对](BEL_load_accounting_reconciliation.json)。48个 placed 拥塞窗口及组合比例见 [窗口数据](placed_congestion_windows.json)。
- 流程改进具体设计：[失败状态保留](failure_capture_design.md)，本轮未安装，不计入拥塞改善收益。
- 最终证据：[物理报告](physical_routability_analysis.md)、[完整派生统计](physical_diagnostic_summary.json)、[原生终态与DCP后SHA校核](attempts/AT001_readonly_physopt_diagnostics/postrun_integrity_facts.json)。52个目标网络含全部27个日志唯一样例；无load类型直方图/SLR内端点包络，缺失败route全图。本轮不重开DCP、不新实现。

A run record alone does not establish PASS or a method verdict.
