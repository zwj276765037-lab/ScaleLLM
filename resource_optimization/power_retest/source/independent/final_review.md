# 全 DSP 七轨功耗独立审核

最终结论为 **PARTIAL_WITH_LIMITS**。新 run 为 `kv128_sevenrail_main_20261115T014454Z`，bit 文件 SHA256 为 `5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7`。独立程序只使用 Python 标准库读取本地封存证据。

## 原始记录与状态来源

独立复核了全部 132 个传输文件，合计 861122432 字节，大小与 SHA256 全部匹配。正式遥测包含 9399 sweeps、65793 rail points、159804 bus reads，逐原始小端字节、VID/Linear11 解码、七轨轮转、即时 read_id 引用与 QPC 顺序通过。VADJ 的 9390 个合法负电流点保留符号。

内部审核重新读取原封存 256 MiB snapshot，核对其 SHA256，并逐一对比实际 256 对 1 MiB 写入/回读日志与本地 snapshot 对应字节。新 bit 的实际完整恢复、32 层摘要和回读结果一致。原五层各 16 槽的 position0..126 历史与原捕获逐字节一致。其余 27 层历史保留 `independent_full_model_oracle=NOT_ESTABLISHED`。

全部 9137 条命令的 descriptor、16 槽 position127/epoch1、80 MHz、DONE 字节数与 cycles、输出传输和 ACK 顺序通过。新资格前 64 条命令为 8193..8256，包含完整 32 层 A/M。六条目标 input/完整 output 的 SHA 与原始捕获文件一致，16 个输出 token 匹配，host 入口/提交状态的规范 JSON 摘要分别匹配原 steps126/127。四次完整步的 host 状态与 KV 恢复验证通过。

## 共同覆盖积分

新 60 s pilot 的实际 sweep 起点间隔最近秩 p95 为 118.3493 ms，预先冻结 `D=150 ms`、`G=450 ms`。每轨从全程序列构造支持段并在窗口边界裁剪，七轨使用同一共同覆盖集合积分。12 个正式窗口均达到原命令与逐轨点数门槛。

| 负载 | 三次 covered mean 的等权均值 ± 样本 SD，W | 完整共同覆盖窗数 |
| --- | --- | --- |
| idle | 11.090992779 ± 0.006154938 | 2/3 |
| Attention 五层循环 | 11.343160085 ± 0.015589760 | 0/3 |
| MLP L0 | 11.826220331 ± 0.046525941 | 0/3 |
| 完整 KV128 step | 11.138985200 ± 0.013303595 | 1/3 |

完整窗口均值只在 idle1、idle3、full3 建立，其余九窗的该字段为 null。工程分析与独立复算的逐窗、逐轨、去边 10 s、ZOH、重复统计及 BUSY 条件分布一致，绝对容差为 `1e-10`，最大绝对差为 `3.552713678800501e-14`，差异列表为空。

另以相同实际 150 ms cadence 的 raw、`G=420 ms` 作单独敏感性复算。最大 covered mean 绝对差为 0.014377027 W，出现在 MLP1。full3 的覆盖率在该敏感性口径下为 99.3291108%。主结果使用预先冻结的 450 ms。

## 退出与限制

sampler、workload、launcher 的实际原生退出码均为 0。最终 guardian 为 CLOSED，租约释放，自有进程清理与资源记录通过。外层 guardian 曾记录 .NET/CIM 创建时间的 0.4 µs 归一，归一前完整进程树覆盖保持未建立，launcher/runtime 资源保护记录保留。

命令 10329、12688、17100 缺少 BUSY 观测，命令 11048 少于两次 BUSY 观测。四条命令的保守 BUSY 内窗留空，所属正式功耗窗口及完整输出/ACK 记录保留。严格物理 active mean、physical active energy 和整板输入功率均为 null。测量范围为七个指定稳压器输出的 V×I 遥测，传感器内部平均窗口、lag 上界与绝对精度仍为 UNKNOWN。

公开复算以封存身份记录核对六条数值参考和 host 状态，逐项核查恢复日志，明确记录 `private_snapshot_bytes_rehashed=false` 及 `original_private_capture_bytes_rehashed=false`。内部全量审核保留实际重新读取私有 snapshot/capture 的结果。

## 证据文件

- [全量内部审核](main_001_independent.json)、[公开证据复算](main_001_public_recompute.json)、[稳定资格身份](qualification_001_final_independent.json)。
- [逐文件传输核验](inventory_132_independent.json)、[pilot 独立复核](pilot_001_independent.json)、[实际完整恢复核验](restore_001_independent.json)、[公开恢复日志核验](restore_001_public_log_audit.json)。
- [独立程序](audit_retest.py) 的冻结 SHA256 为 `bd09b38ddadab99b3fe4b8545823aef50ed9db73aba7357b68ced4836b5122f1`。

早期资格预览保留在 `qualification_001_independent.json`，其三份原始前缀已封存于 `outputs/resource_optimization_power/audit_inputs/qualification_prefix/`。正式发布采用完整 sealed raw 上重算的 `qualification_001_final_independent.json`。
