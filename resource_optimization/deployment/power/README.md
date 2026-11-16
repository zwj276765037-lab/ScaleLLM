# 便携七轨功耗复现

日期为 2026-11-16。本目录提供 fresh KV128 benchmark 的离线来源检查、完整 KV 检查/恢复、新 pilot、12 窗三重复采集与离线分析入口。CPU 回归、Windows 原生参数回环和 PowerShell 语法解析已通过；便携启动器打开 PowerTool/板卡及 fresh benchmark 链路的实机状态为 `NOT_RUN`。

## 输入与配置

先按主部署文档取得 VCU118/XCVU9P、80 MHz all-DSP 位流、驱动、模型导出物和 Python 环境，完成 SRAM 编程，并通过公开 `benchmark-kv128` 生成一个新结果目录。该目录包含 `run.json`、`requests.json`、`benchmark_source.json`、`benchmark_commands.jsonl`、`benchmark_capture.json` 和 `captures/`。采集中的 256 MiB `captures/kv_snapshot.bin` 应由本机完成的 128 步/8192 命令运行生成，其发布参考 SHA256 为 `fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8`。

`config.example.json` 列出必须自行设置的本机路径。把副本保存为 `$config`，设置 `$repo` 为公开 checkout 根目录，设置 `$python` 为已安装 Python 可执行文件。全部相对路径按配置文件所在目录解析，命令行覆盖参数也遵循这一规则。含空格与中文的路径可直接使用。`StageRoot` 指向包含 `project/hardware`、`deploy/vendor/runtime` 和公开源码清单的 checkout。

`BoardLockPath` 应与该主机其他板卡流程使用同一个独占文件路径。启动器持有 FileShare.None 租约，记录 PID/出生时间，并在结束时释放。执行期间关闭 AMD 硬件工具、PowerTool GUI 和其他板卡任务。

`PowerToolRuntimeRoot` 指向自行取得的官方 PowerTool 2.32.27 运行库。`powertool_runtime_manifest.json` 固定 EXE、DLL、XML 的尺寸/SHA256与官方产品页面。启动器自动使用 Windows 的 32 位 PowerShell。`AdapterSerial` 填实际适配器序列号。官方软件获取与许可条件见主部署文档。

## 离线来源检查

配置完成后，在 PowerShell 中先从该配置读取实际路径。以下示例的 `power.local.json` 是你填写后的配置副本，所有输出放在它所在目录。

```powershell
$config = (Resolve-Path './power.local.json').Path
$configDir = Split-Path -Parent $config
$settings = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
function ConfigPath([string]$value) {
  if ([IO.Path]::IsPathRooted($value)) { return [IO.Path]::GetFullPath($value) }
  return [IO.Path]::GetFullPath((Join-Path $configDir $value))
}
$repo = ConfigPath $settings.StageRoot
$python = ConfigPath $settings.Python
$benchmark = ConfigPath $settings.BenchmarkRoot
$programReceipt = ConfigPath $settings.ProgramReceipt
$pilot = Join-Path $configDir 'pilot-001'
$capture = Join-Path $configDir 'power-001'
$derived = Join-Path $configDir 'derived-001'
```

以下命令只读取本地文件。

```powershell
$power = Join-Path $repo 'resource_optimization/deployment/power'
& $python (Join-Path $power 'portable_source.py') --main $benchmark --program-receipt $programReceipt
```

来源检查在分析主机保留原始编程 host/boot 身份与成功回执。来源检查要求完整 128 步、16 槽固定活跃、8192 个已 ACK 摘要、每条合法 ABI 描述符、逐步 host 状态和全部 manifest 绑定。1784 个输出 token 对公开 token 文件比较，12 条捕获输出对公开 operator 参考比较，全部捕获文件逐项验证尺寸/SHA256，完整快照验证发布 digest 与32层独立文件内分块哈希。`benchmark_commands.jsonl` 表示实际后端 ACK 后的 hook 摘要，其时间采用 monotonic ns。正式功耗运行另行生成 QPC START/STATUS/DONE/ACK 原始记录。

## 板端检查或完整恢复

以下命令需要本机 VCU118。`inspect` 读取完整 32 层 KV 并比较 fresh benchmark 快照，要求 CSR 等于该 benchmark 最后一条 ACK。重新编程或需要重新建立 KV 基线时执行 `restore`，它在 quiescent 状态写入并逐字节读回全部 32 层，保留前后 CSR 恒等检查。

```powershell
& (Join-Path $power 'run_power.ps1') -Action inspect -ConfigFile $config -OutputDir './inspection-001'
# 根据当前板状态选择 restore，输出目录须为新目录。
& (Join-Path $power 'run_power.ps1') -Action restore -ConfigFile $config -OutputDir './restore-001'
```

通过后的检查文件分别位于 `inspection-001/inspection/inspection.json` 或 `restore-001/inspection/inspection.json`。后续用 `$inspection` 指向实际通过的一份检查文件，例如执行 inspect 后设置 `$inspection = Join-Path $configDir 'inspection-001/inspection/inspection.json'`；执行 restore 则改为其对应路径。该文件绑定本次完整快照、源码、编程回执和 OS boot。Live 检查要求编程回执属于当前主机和本次启动，正式运行继续绑定同一份回执。CSR/ABI 可核对接口状态，同一 OS boot 内的外部重新编程仍依赖编程后的独占流程记录。恢复与正式运行之间应保持该 DDR 基线。

## 新 pilot 与冻结参数

```powershell
& (Join-Path $power 'run_power.ps1') -Action pilot -ConfigFile $config -OutputDir './pilot-001'
& $python (Join-Path $power 'pilot.py') --metadata (Join-Path $pilot 'telemetry.json') --jsonl (Join-Path $pilot 'telemetry.jsonl') --receipt (Join-Path $pilot 'receipt.json') --output (Join-Path $pilot 'freeze.json')
```

`$pilot` 为配置目录下 `pilot-001` 的完整路径。默认 pilot 采集60秒不加节拍延迟，至少200个完整 sweep。冻结规则使用原始 `sweep.start_ticks` 的最近秩 p95，`D = ceil_10ms(max(100ms, 1.25 × p95))`，`G = 3D`。2026-11-15 历史数据得到 D150/G450 ms。新运行使用本机重新测得的参数。正式运行会重新读取 pilot 原码、校准读值、计数和原生退出回执，验证冻结文件，要求 host/boot/adapter/采样脚本/官方运行库身份一致。

## 12 窗三重复

```powershell
& (Join-Path $power 'run_power.ps1') -Action run -ConfigFile $config -InspectionJson $inspection -PilotRoot $pilot -OutputDir './power-001'
```

固定三个 block 的顺序为 `idle/attention/mlp/full`、`idle/mlp/full/attention`、`idle/full/attention/mlp`。Idle、Attention L0/8/16/24/31 轮转和 MLP L0 窗各至少120秒、每轨至少200个有效 VI 点。Full 窗包含一个 position127 的完整32层 A/M 步，包含 CPU Down、LM head 和16槽 token 提交。正式测量前执行完整 token/host-state 资格验证、六条数值回放和五层完整/局部 KV 恢复等价验证。每个窗口边界都确认完整 KV 基线，最终要求空闲、12窗完成、句柄关闭和所有原生进程退出。

启动器保留 PMBus 只读、逐读原码/原生 API 状态/QPC、七轨轮转、校准只读值、负电流码和 adapter disconnect 回执。采样设备操作停滞触发10秒心跳超时，初次 ready 为30秒，XDMA 单操作为5000 ms，硬件命令为120秒。资源上限为8个 CPU、数学库单线程、聚合 RSS 8 GiB、系统可用2 GiB和实际输出卷可用40 GiB。正式运行的累计墙钟时限保持关闭，结束窗口和故障收尾按安全 ACK 边界处理。

## 离线分析

`$capture` 和 `$derived` 已在前面的路径块中定义。下面先创建新的分析目录，`$D` 从该次 pilot 冻结文件读取。

```powershell
New-Item -ItemType Directory -Path $derived -ErrorAction Stop | Out-Null
$D = (Get-Content (Join-Path $pilot 'freeze.json') -Raw | ConvertFrom-Json).target_period_ms
& $python (Join-Path $power 'kv128_sevenrail_windows.py') --metadata (Join-Path $capture 'telemetry.json') --jsonl (Join-Path $capture 'telemetry.jsonl') --windows (Join-Path $capture 'workload/windows.jsonl') --commands (Join-Path $capture 'commands.jsonl') --target-period-ms $D --output (Join-Path $derived 'analysis.json') --window-csv (Join-Path $derived 'windows.csv') --command-csv (Join-Path $derived 'commands.csv')
```

两个积分/解码文件与冻结 `analysis_frozen` 文件逐字节一致。历史全 raw 复算得到与已存整份 JSON 完全一致的 `PARTIAL_WITH_LIMITS`。每轨共同覆盖、gap、边界插值、原码解码、负码和覆盖质量规则均沿用原方法。七轨输出功耗、covered-time mean、全窗均值、QPC BUSY 覆盖和未知传感器 aperture/lag 的限制保留在结果中。整板输入功耗、严格物理 active 均值和独立全模型数学 oracle 的验收状态保持 `NOT_ESTABLISHED`。

## 本目录验证记录

2026-11-16 CPU 回归覆盖 fresh-source 完整 schema、公开数值参考、snapshot pin、host-state/bit/payload/descriptor/journal 篡改拒绝、相对配置路径和 Windows 参数编码调用点。Windows 原生进程参数回环测试在 Linux 标记 `SKIP`，随后在独立 Windows Python 环境通过（包含空格、中文、引号、末尾反斜杠及空字符串）。可以在 Windows 用 `python -m unittest discover -s tests -p 'test_portable_power_*.py'` 执行。source 完整 fixture 使用合成全 KV digest，仅用于验证来源检查行为。fresh benchmark 快照生成、Windows 启动器的设备调用、PowerTool 和板端12窗流程的本阶段实测状态均为 `NOT_RUN`。
