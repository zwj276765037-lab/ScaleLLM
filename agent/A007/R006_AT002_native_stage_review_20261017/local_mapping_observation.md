# R006 C01 local mapping 有界性能观察

观察时间：2026-10-17T03:16:51.333436+00:00。仅读取已归档源码、R005完整账本与R006既有日志；没有EDA、DCP、进程控制或工程源码编辑。

R005的C01 LOCAL_PIN_NET_MAPPING由02:01:13.943至02:01:41.540闭合，27.597秒。R006由03:01:00.662开始，03:13:43.406仅到owners5120/9514，仍未闭合。4864→4992同一owner进度区间旧1.960秒、新319.427秒；对应日志行差从1行增到19383行。这些是实际区间，不作线性时间预测，也不把整个cut阶段耗时混入local mapping。

两个运行的candidate_inspector.tcl字节相同；已关闭candidate_local_owners_C01.tsv逐字节一致（SHA256 d6060a3e939faa6ef1e53273c872d1f5dd4008fd987f7769ea1b67b7a5293dbc）。local owner/pin循环、去重及directedSegmentCanonical缓存入口保持。新包增加完整segments NAME缓存，后续减少重复NAME元数据调用，没有在local loop扩大候选范围。

新directed_alias对每次调用（含缓存命中）增加ALIAS_NET_NAME BEGIN/END；首次closure额外增加ALIAS_NATIVE_SEGMENTS及ALIAS_SEGMENT_NAME BEGIN/END。directed_trace每条puts后flush stdout，新增大量同步console工作。至R006日志第114099行，11611次native-segments BEGIN对应原R005完整alias账本11611个不同canonical组，重复组0、缺失0；当前没有closure缓存失效或重复同组查询证据。索引build在local mapping结束后才调用，当前慢区间还未进入新top-port原生索引。

性能判断：这是实际新观察输出开销的强嫌疑，不能称为仅揭示旧成本；目前未隔离其精确耗时或排除环境贡献。ALIAS trace的BEGIN时间戳在puts/flush之前，成对时间包含日志输出，不能作为净原生API耗时。原始日志和源码保持，不因本观察停止R006。

主控后续已派发最小E008-only普通修复：将上述三类冗余细trace移出同步console，可缓冲sidecar保留全部事件；保留top-port协议细BEGIN/END、完整原生收据、阶段/owner进度、完整图覆盖/资格/时序。原1425/dcc64和当前绑定源不改。仅集中核受影响差异，复用已有验证；实际C02/index优先，不新增协议或用户批准门。

证据：R005/R006各实际报告目录vivado.log；各实际attempt/sources/directed_exporter.tcl、candidate_inspector.tcl；R005 candidate_segments_C01.tsv及两运行candidate_local_owners_C01.tsv。
