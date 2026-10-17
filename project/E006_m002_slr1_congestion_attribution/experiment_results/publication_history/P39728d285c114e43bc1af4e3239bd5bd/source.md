# E006：SLR1热点归因与候选比较

在同一冻结E005 physopt图上比较C01 SwiGLU branch1与C02 Down weight repack，遵循[候选有向边界范围](../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)与[完整端口索引补充](../../../mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md)。coverage_version=candidate_directed_cut_v1；外部peer普通负载在合格唯一外driver网可不枚举，并明确NOT_ENUMERATED，不能宣称整网扇出完整。所有候选边界、clock/reset/constants/unknown/INOUT/top端口保持，方向max/min各cap16。

R006 AT003实际12份运行源匹配23be缓冲日志包；系统Python/子进程环境隔离保留。资源、热点和失败样本复用R004及此前闭合证据；R005 C01完整cut/时序保留。端口获取路径按相同协议执行，当前只把高频alias细trace写入全缓冲sidecar；每个真实图仍自动核验完整库存、别名闭包、互查与投影。AT002 C01真实index资格通过可作为历史依据，新图仍须独立实际核验，性能不预填。

本诊断不修改物理设计。选择至多一个有实测支持的候选并完成真实收尾后，按E008完整流程实施。Hadamard、ScaleCode、format05、RTL/IP/ABI/时钟保持。


---
Published: 2026-10-17T03:52:00.110254+00:00
Publication: P67c50ae1308d441bbc988d20e2604fba
