# 全DSP版本七轨功耗重测结果

本阶段完成12/12窗采集和板端收尾。工程离线结果为 **PARTIAL_WITH_LIMITS**，三类原生进程均退出0。独立审核结果由source/independent单独保存。

## 镜像、参考及资格

实际镜像SHA256为 `5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7`，VCU118/XCVU9P、80 MHz、16槽、KV128/position127。01:36:27 UTC完成SRAM编程，精确目标Digilent/210308B76D50、xcvu9p_0，原生exit0、Startup HIGH、两MIG。

复用封存旧128轮参考及六条完整捕获，旧参考镜像SHA96df1a5c…单独保留。完整268435456字节KV快照SHA为fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8，已实际恢复全部32层并逐字节读回。保留五层16槽×127历史独立字节比较、另外27层缺独立历史oracle的限制。

新bit资格执行64条完整32层A/M命令，16输出token及完整槽位提交与封存结果相同，六条选中输入/完整输出逐字节一致。host state规范JSON的before SHA为3889a90f2ce2231afc7297f800b2bf8998fca1485e748c93bc775ddf27832c68，after SHA为3a7b15d6e874014d731b78d8c51377f2147b0bb1d2fa7a75241681c6eec7a4c2。全模型独立数值oracle尚未建立。

## 新pilot及采集设计

新60秒只读pilot获得538 sweeps、3766轨点，读取错误0、采集和启动进程原生exit0。按raw sweep.start_ticks的537个间隔，最近秩p95为118.3493ms，既定公式得到D150ms/G450ms。旧版本采用140ms/420ms，比较时需携带该差异。

最初沿旧辅助分析器以首V读取起点得到118.3577ms，冻结原稿和原分析均保留；随后更正主字段为实际sweep起点。两种数值均导出150ms/450ms，正式参数没有改变。固定三组次序、120秒idle/算子窗、完整步CPU Down/LM head/token commit边界均按合同执行。

## 共同覆盖段统计

每窗在七轨共同覆盖上作时间加权积分，各类三重复作等权平均和样本标准差。以下四类汇总均为covered-time mean。

| 工作负载 | 三重复均值 ± SD / W | 每窗共同覆盖范围 | 全窗均值成立窗数 |
|---|---:|---:|---:|
| Idle | 11.090993 ± 0.006155 | 99.96046–100.00000% | 2/3 |
| Attention L0/8/16/24/31 | 11.343160 ± 0.015590 | 97.52732–98.32836% | 0/3 |
| MLP L0 | 11.826220 ± 0.046526 | 96.87886–98.36237% | 0/3 |
| 完整32层KV128一步 | 11.138985 ± 0.013304 | 99.19497–100.00000% | 1/3 |

全窗均值只在idle1、idle3、full3成立，另外九窗保持null。缺失段未补零、未外推、未扩大G。七轨为选定稳压器输出，整板输入功耗、未知传感器窗口下的严格物理BUSY均值均保持null；负电流码、恒码和校准只读结果保留在raw与离线分析中。

## 执行、资源与收尾

正式采样9399 sweeps、65793轨点、159804次只读事务，读取错误0；9137条命令完成ACK。未观测到BUSY的命令为[10329, 12688, 17100]，不足两次BUSY的命令为[10329, 11048, 12688, 17100]，相关覆盖为空，完成/数值断言保留。

sampler、workload和外层launcher实际exit均0。正式外层进程时长1549.290192秒。整个运行未设置固定累计墙钟终止。workload观测RSS峰2520072192字节，stage guardian观测聚合峰2882166784字节，最低系统可用内存7564156928字节、D盘剩余181706133504字节。

最终CSR身份/空闲/错误检查exit0，38项runtime源复核PASS，自有采集和编程进程均退出。2026-11-15T02:12:12.8758997Z正常关闭guardian并释放lease，候选保留在volatile SRAM。

## 主机适配与保留的失败

SRAM下载后的首次CSR读取全FFFFFFFF，按唯一已核实XDMA实例做设备级restart后恢复；驱动SHA前后均bfc1039ae17cbac465a268a96922d60ebd702dfe2388df8b66d51b2a60fb0932。两通道各196608字节DDR读写回验通过。

首次restore在任何板访问前因嵌入式Python本地模块路径缺失而import失败，随后添加显式路径并成功。attempt1 stdout/stderr/原生exit回执保留。外层guardian首次未匹配.NET StartTime与CIM CreationDate的0.4微秒精度差，核对PID、命令和精确.NET时间后按CIM归一并跟踪完整六进程树；launcher/runtime自身的资源检查持续执行。首次归一检查的DateTime本地/UTC运算被拒绝，统一到UTC后通过，相关失败和修正记录保留。

## 交付

完整raw位于outputs/resource_optimization_power。远端清单132文件、861122432字节，传输逐项size/SHA全部PASS，raw_inventory SHA为61788ae90ffcfe914568d39add8fb360feeedc2b2a0eb4f2bc06b29d03d85d99。私有256MiB快照和vendor运行库留作外部身份依赖。

工程完整分析为outputs/resource_optimization_power/derived/main_001_analysis.json。公开小型结果为results/summary.json、window_summary.csv、busy_by_opcode_layer.csv、repeat_summary.png及原生退出/恢复/传输回执。原始ZIP和公开报告由根代理发布。
