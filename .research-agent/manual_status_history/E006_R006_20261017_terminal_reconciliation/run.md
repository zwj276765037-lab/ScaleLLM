# E006 / R006：完整端口索引获取

当前执行：running，AT003_buffered_alias_directed_cut；verdict：unassessed。

范围为同一E005 physopt图上C01/C02完整有向边界与方向时序，遵循[获取补充](../../../../../mission/M002_ddr_separation_and_timing_recovery/top_port_reverse_index_acquisition_revision_2026-10-17.md)及原scope；资源和热点按原身份复用。

AT001因调用重复nice在原生启动前失败，[原始事实](prelaunch_AT001/R006_AT001_prelaunch_failure_facts.json)保留。AT002于02:51:03Z真实启动，两membership及C01完整native端口索引通过；高频同步alias日志造成明显额外工作。用户对此次AT002单独批准切换后，于03:48:51Z受控结束，16项真实收尾通过。[终态事实](attempts/AT002_top_port_index_directed_cut/terminal_facts.json)。完整cut/时序未闭合，已得索引和全部partial保持。

缓冲日志版AT003于2026-10-17T03:49:59.301815Z真实启动，[启动核验](attempts/AT003_buffered_alias_directed_cut/native_start_verified.json)确认12归档源/23be、144输入、CPU0–7/nice5与本项目唯一EDA。仅alias高频细trace写入完整缓冲sidecar，查询/缓存/图覆盖/索引资格/方向时序保持。当前新图仍须实测，尚无本AT完整cut/时序或选型。

实际比较和终态闭合后衔接已授权E008。AT002停止例外已使用，不授权停止当前正常AT003。正常运行无墙钟/无输出强停，原资源及范围限制保持。
