

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E006 / R006 运行结果

[负责人维护的本批运行记录](run.md)

# E006 / R006：完整端口索引与候选比较已完成

执行 completed，AT003_buffered_alias_directed_cut 于2026-10-17 03:49:59.301815Z启动、04:45:04.960209Z自然结束；native0 / supervisor0，没有停止或清理动作。[真实终态](attempts/AT003_buffered_alias_directed_cut/status.json)、[25项收尾](attempts/AT003_buffered_alias_directed_cut/terminal_summary.json)。两候选成员资格、完整有向cut及四组有界时序全部闭合；选择和后继实现状态另见[E008](../../../../E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)。

范围为同一E005 physopt图上的C01/C02比较，遵循[端口获取补充](../../../../../mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md)及有向scope；资源与热点复用原R004结果，外部peer普通LOAD在合格网不枚举，不能声称完整整网fanout。

| 实测 | C01 SwiGLU branch1 | C02 Down weight repack |
| --- | ---: | ---: |
| canonical nets | 14307 | 10317 |
| ingress / egress nets | 3087 / 55 | 2998 / 1795 |
| 边界driver-load对 | 21479 | 19325 |
| ingress最差setup / hold（ns） | +1.416 / −0.128 | +2.537 / −0.055 |
| egress最差setup / hold（ns） | +1.848 / +0.035 | +2.537 / −0.027 |

[ C01 cut ](attempts/AT003_buffered_alias_directed_cut/candidate_C01_directed_cut_closed_facts.json)、[ C02 cut ](attempts/AT003_buffered_alias_directed_cut/candidate_C02_directed_cut_closed_facts.json)。每候选四组方向时序各ca

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_top_port_index_directed_cut](attempts/AT001_top_port_index_directed_cut) | failed | Supervisor invocation failed before native startup/attempt creation/lane acquisition: duplicate nice5 produced nice10, reset to5 denied. Exact owner exited, lane free, no design result. Original receipt/log retained; AT002 uses l… | [执行收据](attempts/AT001_top_port_index_directed_cut/run.json) · [report.md](attempts/AT001_top_port_index_directed_cut/report.md) |
| [AT002_top_port_index_directed_cut](attempts/AT002_top_port_index_directed_cut) | failed | Authorized controlled switch; INTERRUPTED_INCOMPLETE. Both member stages and C01 native port index qualified. C01 full cut/timing and C02 incomplete. All actual input/PID/lane closure passed. No candidate selected/refuted. | [执行收据](attempts/AT002_top_port_index_directed_cut/run.json) · [report.md](attempts/AT002_top_port_index_directed_cut/report.md) |
| [AT003_buffered_alias_directed_cut](attempts/AT003_buffered_alias_directed_cut) | completed | Candidate-directed complete local leaf and aliases with native class/role-qualified external-driver reduction, all top ports, declared full fallback and bounded timing. External peer ordinary leaf loads NOT_ENUMERATED on qualifie… | [执行收据](attempts/AT003_buffered_alias_directed_cut/run.json) · [report.md](attempts/AT003_buffered_alias_directed_cut/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
