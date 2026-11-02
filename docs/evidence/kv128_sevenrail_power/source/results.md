# 七轨 KV128 重复测量阶段结果

状态：**正式四工况各三重复均已采集；综合判定 PARTIAL_WITH_LIMITS**。空闲和完整 KV128 解码步的六个窗口有完整七轨共同覆盖；Attention、MLP 重复的六个窗口各有真实采样缺口，只能给已覆盖区间的遥测均值。原控制器收尾 `FAIL` 回执保留，不能等同全链路 PASS。本文件记录可复核原始证据和实现状态；数值口径遵循 [design.md](design.md)。发布 RTL、bitstream 和稳压器配置未改动，未综合或重新烧录。

## 目标、平台与成本

- 固定 Dell / VCU118 / Decode16 / 80 MHz，发布 bit SHA-256 `96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85`。
- 七轨地址 `0x70, 0x11, 0x12, 0x15, 0x14, 0x72, 0x73`。三条 MAX20751 每轮各 fresh 读取 VOUT/IOUT/POUT；四条 MAX15301 只读 VOUT/IOUT，POUT 明确为 `null`/`NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET`。
- 正式目标：idle、五层循环 Attention 重复、L0 MLP 重复、完整 KV128 32 层解码步各至少三次。A/M 每窗至少 120 s、每轨至少 200 个有效 V/I 点；完整步一次须包含 64 条 FPGA 命令以及 CPU Down、LM-head 和 token commit。
- 旧真实 KV128 完整 128 轮记录的模型墙钟为 9843.491879 s。按已确定的恢复设计，预期复用经完整证据检查的 DDR 或仅一次重建前缀，再分别运行三个完整末步；不能把既有五层单命令捕获称为完整末步。正式板上成本需以 as-run 记录为准。

## 只读短 pilot，2026-11-02

[原始收据](../DOWNLOADS.md#archive-files)、[元数据](../DOWNLOADS.md#archive-files)、[逐点原始码与单次读取包络](../DOWNLOADS.md#archive-files)与[独立离线分析](../DOWNLOADS.md#archive-files)已转存。Dell 运行版脚本、官方 runtime manifest 的身份核对及只读预检见 [部署回执](../DOWNLOADS.md#archive-files)和 [身份记录](../DOWNLOADS.md#archive-files)。

| 项目 | 实测 |
| --- | ---: |
| 状态、sampler 原生退出、板锁释放 | COMPLETE、0、是；无残留本任务进程 |
| 七轨完整 sweep / 轨点 / 读取错误 | 594 / 4,158 / 0 |
| 遥测 fresh 读取 | 10,098（每轮 17 次），另有 7 次 VOUT_MODE |
| 采样阶段持续 | 60.1483689 s |
| sweep 起点间隔 p50 / p95 / max | 101.6167 / 106.529 / 170.1735 ms |
| sweep 自身耗时 p50 / p95 / max | 100.51735 / 104.931 / 164.0938 ms |
| 正式预定目标周期 D / 最大插值间隙 G | 140 / 420 ms |

MAX20751 三轨现场 `VOUT_MODE=0x20`，VID 原码分别解码为 VCCINT 0.85 V、MGTAVCC 0.90 V、MGTAVTT 1.20 V；三轨主要量是实测 V×I，与单独 READ_POUT 对照。VADJ 负电流原码是合法观测，保留符号，不裁零。pilot 为空闲读取速度试验，它的点算术均值不能替代正式按同一时间覆盖区间积分的功率均值。传感器物理平均窗与滞后仍无上界，严格物理活跃均值保持 `null`。

pilot 原运行版已冻结；其记录是每个 V/I/P 事务各自 QPC 包络，但单次 read 直到该轨点完成才作为轨点写入。正式采样器改为每次 read 后即时独立写 `bus_read`，并保存 read_id、相位和每轮起点调度。该改动不追溯改写 pilot 原件。

## 正式格式短时核查，2026-11-02

[smoke 原始收据](../DOWNLOADS.md#archive-files)、[采样元数据](../DOWNLOADS.md#archive-files)、[逐读原码](../DOWNLOADS.md#archive-files)和[独立格式与时序复算](../DOWNLOADS.md#archive-files)已转存。冻结的脚本经 Dell PowerShell ParseFile 检查后，在独占板锁内只读 20.1408105 s；sampler 退出码 0，板锁释放，未发 FPGA 命令。

| 项目 | 实测 |
| --- | ---: |
| 完整 sweep / 七轨点 / 独立 bus_read / 读取错误 | 141 / 987 / 2,418 / 0 |
| 读取构成 | 141×17 遥测 + 7 VOUT_MODE + 14 CAL；全部 CAL `returned` |
| sweep 起点间隔 p50 / p95 / max | 142.28925 / 143.6864 / 159.512 ms |
| sweep 耗时 p50 / p95 / max | 109.4972 / 120.0984 / 140.614 ms |
| 超出预定起点 2 ms 次数 / 最大迟到 | 78/141 / 19.512 ms |
| 固定正式 D / G | 140 / 420 ms |

已逐条核对独立 `bus_read` 与轨点嵌套记录字节完全相同、read_id 连续、QPC 包络顺序、七轨轮转、原始小端解码和 CAL 状态。漏截止次数如实报告；本次 sweep 最大间隔仍远小于 G，不构成跨过长空档插值的证据。CAL 码只作为读回记录，不据其反算未确认的校准模型。

[七轨离散原点图](../DOWNLOADS.md#archive-files)和[逐轨原码 CSV](../DOWNLOADS.md#archive-files)是从 smoke 原始 JSONL 导出的辅助视图；图中不作平滑，MAX20751 的 READ_POUT 与 V×I 分别画点。

## 正式尝试 main_001：测量窗前安全退出

[attempt 原始收据](../DOWNLOADS.md#archive-files)、[PMBus 元数据](../DOWNLOADS.md#archive-files)、[逐读原始日志](../DOWNLOADS.md#archive-files)、[QPC 命令日志](../DOWNLOADS.md#archive-files)和[独立 sampler 诊断](../DOWNLOADS.md#archive-files)已保留。资格完整步运行到第 43 条命令（command_id 8235）并 ACK；尚未写出任何正式四工况窗口。workload 因采样文件心跳检查报错而安全退出，launcher 释放板锁，没有遗留任务进程。此 attempt 的功率点不得充作三重复结果。

独立复算 sampler 仍 `COMPLETE`：758 个 sweep、5,306 个轨点、12,907 条独立读取、0 错误；相邻 sweep 起点最大间隔 295.4486 ms，无任何超过 1 s 的空档。最后 ACK 后约 0.72 s 仍有采样记录。文件 `mtime` 心跳门误判是最符合现存证据的故障类别；该次没有记录实际计算的 age，因而不能断言具体是并发写入造成负 age。先查文件时间再查当前时间的修正仍在 main_003 重现同类误判。最终版改用日志末尾最近完整 bus_read/sweep 的同轴 QPC 时戳执行原有 10 s 心跳门；恢复前只读核对旧 attempt 最后 ACK、现场 CSR 和 256 MiB KV 快照，命令号连续递增。各 attempt 保留独立原始目录和 as-run SHA。

下一次 main_002 尝试在资源预检处因可用内存低于 2 GiB 提前停止，未打开 XDMA、未发 FPGA 命令，亦未产生正式测量窗。主控按 [所属监控进程清理记录](../DOWNLOADS.md#archive-files)核验并清理了先前本任务遗留的只读进度监控进程，未放宽内存门；随后使用新的 native/main_003 attempt 目录。该资源失败与 main_001 的采样文件心跳竞态分开记录。

main_003 在恢复资格步继续到 command_id 8285（50 条新命令全部 ACK）后再次因文件 `mtime` 心跳门提前安全退出，仍无正式窗口。[原始日志](../DOWNLOADS.md#archive-files)及[独立 sampler 诊断](../DOWNLOADS.md#archive-files)显示 804 sweep、5,628 轨点、13,689 条读取、0 错误；最长相邻 sweep 0.519 s，无超过 1 s 的停采。该单次 0.519 s 间隔已超过预先固定的 G=0.420 s，后续正式积分规则必须将这种空档断开；不能因心跳误报而修改 G。后续恢复门须核 main_001→main_003 完整命令链、现场末 ACK/CSR 与全量 KV。工程修正为用日志中最近完整 bus_read/sweep 的同轴 QPC 时戳执行仍为 10 s 的严格心跳门，舍弃不可信的 NTFS `mtime` 判定；控制器仍检查 sampler 进程、内存和总时限。

## 正式 main_004：十二窗口完成，完整覆盖六窗

[原始采样元数据](../native/main_004/telemetry.json)、[逐次 PMBus 读取日志](../DOWNLOADS.md#archive-files)、[QPC 命令记录](../DOWNLOADS.md#archive-files)、[工作负载窗口](../native/main_004/workload/windows.jsonl)、[原控制器收据](../native/main_004/receipt.json)均原样保存，[传输 SHA 清单](../provenance/main_004_transfer.json)逐文件核对。全部 12 个正式窗口完成：空闲、五层 Attention 循环、L0 MLP 循环和完整 KV128 32 层 FPGA+CPU 解码步各 3 次。QPC 命令日志共 9,129 条完整 DONE/ACK，其中 9,055 条属于正式窗口，74 条为窗外资格阶段命令。sampler 元数据为 `COMPLETE`，10,116 sweep、70,812 七轨点、171,993 独立 bus_read，零读错。主控只读结束检查确认板端静默、错误寄存器零、无寄存器写入；但原控制器收尾因要求每条命令都必须观察到 BUSY 而写 `FAIL`，其 sampler 原生退出字段为 `null`，原件不改写。

[正式修正分析](../DOWNLOADS.md#archive-files)与[逐窗七轨 CSV](../results/main_004_window_rail_v2.csv)按各轨 V/I 读取包络中点连线、在共同有效时间交集积分；相邻有效点相距超过预先固定的 G=420 ms 则断开，不跨缺口外推。结果已与方法角色完全独立的原始记录积分逐窗核对；状态 `PARTIAL_WITH_LIMITS`，原始记录验证 `PASS`。每轨有效 V/I 完整读包络点至少 456 个（完整步）或 794 个（120 s 负载窗），高于 200 点门槛。下表三重复等权，单位 W；“完整”仅指遥测共同覆盖，不表示传感器物理平均窗/滞后已知。

| 工况 | 三重复七轨均值 | 重复样本标准差 | 共同覆盖与完整窗均值 |
| --- | ---: | ---: | --- |
| 空闲 | 11.112454 | 0.011856 | 三窗均 100%，完整窗均值成立 |
| Attention 重复 | 11.339012 | 0.018545 | 97.057%–98.532%，仅已覆盖区间均值；完整窗均值 `null` |
| MLP 重复 | 12.076557 | 0.035709 | 97.496%–97.921%，仅已覆盖区间均值；完整窗均值 `null` |
| 完整 KV128 解码步 | 11.182172 | 0.040880 | 三窗均 100%，完整窗均值成立 |

完整解码步各约 65.4–65.7 s，均有顺序 32 层 Attention/MLP 共 64 条 FPGA 命令及 CPU 步骤；窗口含 host/ACK 间隙，不能按 BUSY 占比倒推物理活跃功率。两条完成命令的保守 BUSY 内窗为 `null`：10084 仅观察到一次 BUSY 读，14365 未观察到 BUSY，但 DONE、错误码、字节数和 ACK 均符合协议。所有命令的七轨 BUSY 内共同有效覆盖为零，因此不报告时间加权 BUSY 七轨总均值；[BUSY 原始条件点](../results/main_004_busy_points_v2.csv)与[按 opcode/层号拆分的点分布](../results/main_004_busy_by_opcode_layer_v2.csv)仅为完整读包络落在保守 BUSY 区间的观测点统计。严格物理活跃均值与能耗因传感器内部平均窗和滞后未界定，仍为 `null`。

[逐轨原码 CSV](../DOWNLOADS.md#archive-files)保留 VOUT/IOUT/POUT 各次读取的原码与前后 QPC；四条 MAX15301 的 POUT 明确不支持。三条 MAX20751 的 V×I 对 READ_POUT 比较见逐窗七轨 CSV，READ_POUT 是异步 2 W 分辨率读数。图包括[三重复与覆盖](../results/main_004_v2_summary.png)、[七轨离散点](../results/main_004_v2_rail_points.png)、[三轨 V×I/POUT](../results/main_004_v2_vi_pout.png)、[共同有效曲线和实际缺口](../results/main_004_v2_common_coverage.png)、[BUSY 与 host 间隙](../results/main_004_v2_busy_host.png)、[BUSY 条件点分布](../results/main_004_v2_busy_conditional.png)，每张都有同名 SVG。旧版边界截断输出留在 [superseded_contained_only](../DOWNLOADS.md#archive-files)，边界数值正确但状态过宽的中间版留在 [superseded_prestatus](../DOWNLOADS.md#archive-files)，均不可作最终引用。

## 工程映射与待限定事项

- [正式七轨采样器](../DOWNLOADS.md#archive-files)：只读 XML/地址白名单、原码/逐 read QPC、MAX20751 VID 和 Linear11、MAX15301 Linear16、既有校准只读记录、按 D 调度、流式 JSONL。**20 秒 smoke 与 main_004 十二窗口采集完成；main_004 控制器原回执 FAIL 保留**。
- [只读 probe 入口](../DOWNLOADS.md#archive-files)：持板锁、bit/官方 runtime 身份、32 位 PowerShell、60 秒无额外 sleep、ready/stop 与自有进程清理。**probe_001 PASS**。
- [离线原码与 pilot 复算](../DOWNLOADS.md#archive-files)、[正式格式短时复算](../DOWNLOADS.md#archive-files)、[共同时间覆盖积分](../DOWNLOADS.md#archive-files)与[诊断图](../DOWNLOADS.md#archive-files)：CPU 单测覆盖原码、小端、无 POUT 轨、窗口边界两侧插值、长缺口及失败点阻断。正式数值经独立复算；完整窗六个、覆盖区间六个。
- 完整步使用经只读现场检查的现存 DDR 快照和恢复资格步；其来源受原始 `run_002` 捕获范围限制，详见 [方法设计](design.md)及主报告。严格物理活跃均值仍因 PMBus 传感器内部平均窗与滞后缺上界而未建立。

阶段验收须区分采集、已覆盖时间上的七轨遥测均值、完整窗均值和严格物理活跃均值；不以采样点数替代恢复或 BUSY 窗证据。
