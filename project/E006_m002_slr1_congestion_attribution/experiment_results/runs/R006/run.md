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

[ C01 cut ](attempts/AT003_buffered_alias_directed_cut/candidate_C01_directed_cut_closed_facts.json)、[ C02 cut ](attempts/AT003_buffered_alias_directed_cut/candidate_C02_directed_cut_closed_facts.json)。每候选四组方向时序各cap16，只描述父physopt估计，不是迁移后时序、完整cut TNS或签核。unknown、常量、时钟和未放置驱动不可按零成本处理。

12归档源、144生产输入、原DCP及全部绑定依赖保持；12登记PID/start均结束且项目EDA资源释放。正常进程无墙钟/无输出强停，原资源及数值/接口/时钟限制保持。

历史：AT001因重复nice在原生启动前失败；AT002完成两membership与C01索引后因同步日志开销拖慢，用户单次批准切换并于03:48:51Z受控结束，全部partial与终态保留。AT003缓冲日志修复后C01本地映射27.893s，与R005的27.597s相近；七份语义账本逐字节一致、167160条事件sidecar完整flush。此为本地阶段实测，不外推全流程速度。
