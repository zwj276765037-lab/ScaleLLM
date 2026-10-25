
历史原文已保留：[整理前原文](../../../../../.research-agent/navigation_history/115499a4e002af1c6c535cdf09c02cc105d796f3403a066346f74264e39f0e25.md)

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E013 / R007 运行结果

未发现独立 run.md；原目录和收据保留。



## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_entry_cpu](attempts/AT001_entry_cpu) | 未登记；查看原记录 | CPU entry helpers and system Tcl syntax only; no native Vivado query proof | [执行收据](attempts/AT001_entry_cpu/result.json) |
| [AT002_csr_repro_cpu](attempts/AT002_csr_repro_cpu) | 未登记；查看原记录 | isolated full schema regeneration; both outputs byte identical; no production writes or EDA | [执行收据](attempts/AT002_csr_repro_cpu/result.json) |
| [AT003_entry_cpu_reproducible](attempts/AT003_entry_cpu_reproducible) | 未登记；查看原记录 | CPU source guards and system Tcl syntax; no native query proof | [执行收据](attempts/AT003_entry_cpu_reproducible/result.json) |
| [AT004_all_lane_probe_cpu](attempts/AT004_all_lane_probe_cpu) | 未登记；查看原记录 | CPU source guards and system Tcl syntax; no native query proof | [执行收据](attempts/AT004_all_lane_probe_cpu/result.json) |
| [AT005_lane_collection_cpu](attempts/AT005_lane_collection_cpu) | 未登记；查看原记录 | CPU source guards and system Tcl syntax; no native query proof | [执行收据](attempts/AT005_lane_collection_cpu/result.json) |
| [AT006_constructor](attempts/AT006_constructor) | completed | 未登记 | [执行收据](attempts/AT006_constructor/result.json) · [input_manifest.json](attempts/AT006_constructor/input_manifest.json) |
| [AT007_synth](attempts/AT007_synth) | failed | 未登记 | [执行收据](attempts/AT007_synth/result.json) · [input_manifest.json](attempts/AT007_synth/input_manifest.json) |
| [AT008_qualification_cpu](attempts/AT008_qualification_cpu) | 未登记；查看原记录 | CPU source guards and system Tcl syntax; no native query proof | [执行收据](attempts/AT008_qualification_cpu/result.json) |
| [AT009_dcp_qualification](attempts/AT009_dcp_qualification) | failed | 未登记 | [执行收据](attempts/AT009_dcp_qualification/result.json) · [input_manifest.json](attempts/AT009_dcp_qualification/input_manifest.json) |
| [AT010_guard_storage_cpu](attempts/AT010_guard_storage_cpu) | 未登记；查看原记录 | actual core generated structural funcsim Verilog; exact primitive names/counts and per-type bindings; full-board native query still required | [执行收据](attempts/AT010_guard_storage_cpu/result.json) |
| [AT011_dcp_qualification](attempts/AT011_dcp_qualification) | completed | 未登记 | [执行收据](attempts/AT011_dcp_qualification/result.json) · [input_manifest.json](attempts/AT011_dcp_qualification/input_manifest.json) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->

AT007于UTC17:31:14自然FAIL，23项综合和完整新DCP/报告完成，guard port筛选全0导致资格拒绝，peak50.096GiB/0survivor。原FAIL保留；同DCP AT009资格于UTC17:39:22真实启动，仅两驱动精确patch，七报告原字节复用，仍须原生逐96lane完整37bit结果。来源/负例/名称fixtures见AT008及experiment_source/gu_only/dcp_qualification；无RTL/约束变化或重综合。

AT009实际NAME dump证明Vivado rebuilt lane边界已重命名CO/DI/D/Q等，guard原端口不可见，原FAIL保留。AT010先核真实生成的514MB funcsim网表：96定义/96lane实例各148 guard FDRE完整、共14208，与AT007 IP inventory绑定；实际名称/索引CPU14+9检查通过。AT011资格已UTC17:57:29真实启动，逐native核全存储37bit而非原端口名，freeze b03f1d...7d71，同DCP与七原报告；两SMC post-opt只读取证已合并，成功后直接既定impl。

AT011于UTC18:07:00资格原生0/null/无漂移/0survivor完成，peak19.041GiB，真实96lane每个双组双entry37bit数据FF完整、共14208；Down0/DSP3072/meta448URAM/10-5-5ns/24reset级PASS。30工件/1433生成文件及同DCP成功receipt SHA228a9569...3b712已签，原整体质量FAIL/七分析报告保持。按授权R008/AT001_impl已UTC18:07:59实际启动，输入freeze b03f1d...7d71不变。
