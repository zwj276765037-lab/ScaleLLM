

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

# E004 / R001 运行结果

[负责人维护的本批运行记录](run.md)

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
- 流程改进具体设计：[失败状态保留]

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_readonly_physopt_diagnostics](attempts/AT001_readonly_physopt_diagnostics) | completed | One read-only open/report/get diagnostic; native/supervisor0, 35/48 Tcl queries code0, 13 help failures; BEL slot histogram semantically invalid, native site/util/SRL counts valid. Optimization unimplemented and untested. Source … | [执行收据](attempts/AT001_readonly_physopt_diagnostics/run.json) · [report.md](attempts/AT001_readonly_physopt_diagnostics/report.md) |

## 本批问题与交付文件

- [analysis_plan.md](analysis_plan.md)
- [failure_capture_design.md](failure_capture_design.md)
- [physical_routability_analysis.md](physical_routability_analysis.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
