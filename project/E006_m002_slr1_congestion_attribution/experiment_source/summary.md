# E006：SLR1热点归因与候选比较

同一冻结E005 physopt图上比较C01 SwiGLU branch1与C02 Down weight repack，按[有向边界合同](../../../mission/M002_ddr_separation_and_timing_recovery/directed_candidate_cut_scope_revision_2026-10-17.md)和[完整端口索引补充](../../../mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md)采集。R006 AT003实际12份源匹配23be缓冲日志包；资源、热点和失败样本明确复用R004及此前闭合结果。

coverage_version=candidate_directed_cut_v1；候选完整leaf、全部别名、driver、top ports及clock/reset/constants/unknown/INOUT均保留。合格唯一外driver网的外部peer普通LOAD不枚举，不能声称整网fanout完整。每候选四组方向时序各cap16/nworst1，不测完整cut TNS。新图分别重建269端口/269组/2772别名完整索引，每候选2170次原生查询均0。

只读诊断不修改设计。后继E008仅将获支持的一个候选迁SLR2，保持RTL/IP、Hadamard、ScaleCode、format05、ABI和时钟。


---
Published: 2026-10-17T04:51:34.492335+00:00
Publication: P124524e4d3404c68bd13aa4db86ab57d
