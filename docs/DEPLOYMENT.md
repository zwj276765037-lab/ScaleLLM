# 部署 Host + FPGA Llama 推理

本入口面向一台本地 Windows x64 CPU 主机与一块 PCIe 连接的 VCU118。FPGA 实际执行 Attention 和 Gate/Up；CPU 执行 RMSNorm、残差、激活/编码、整数 Down、LM head、tokenizer 和独立数值参考。没有 GPU 或 CPU 替代 FPGA 的路径。

已测功能为 Llama-3.1-8B-Instruct、两条请求、每条两步生成：`Hi` → `It's`，`Hello` → `Hello!`。公开入口保留每个 FPGA 输出的全字节 gold 比较以及证据落盘，运行时间包含验证开销。详细速度、功耗和资源见 [性能报告](PERFORMANCE_AND_RESOURCES.md)。

## 1. 准备硬件和软件

- VCU118，器件 `xcvu9p-flga2104-2L-e`，连接板卡电源、PCIe 与 USB-JTAG。
- Windows 10 x64；已测版本为 22H2 build 19045。实际测试 CPU 为 i7-12700、16 GiB RAM。运行限制为 8 个逻辑 CPU、RSS 不超过 6 GiB、可用 RAM 至少 2 GiB；建议留至少 8 GiB 可用 RAM。
- 模型原始 BF16 约 16 GB；硬件导出物约 4.28 GiB，Host FP32 embedding/LM head 约 3.91 GiB，加上程序与逐次证据。准备至少 35 GB 空间，导出期间建议更多余量。
- 已测下载工具 Vivado 2022.2 Hardware Manager/hw_server。**设计构建使用 Vivado 2025.2**，二者用途不同，见 [构建指南](BUILD_HARDWARE.md)。不分发 AMD 安装程序。
- CPython 3.12 x64；实际板测为 3.12.10。CPU 便携性检查也通过了 Linux CPython 3.12.3。依赖固定为 NumPy 1.26.4、tokenizers 0.20.3、Jinja2 3.1.6。
- 专用 Windows XDMA 驱动：`10EE:9018`、设备接口 GUID `74c7e4a9-6d5d-4a70-bc0d-20691dff9e9d`、DMA `POLL_MODE=1`，用户 IRQ0 被修复策略屏蔽。**先读 [驱动准备说明](../deploy/driver/README.md)**。本包不含机器专用签名 SYS/CAT 或证书，不自动改变启动或信任策略。

当前 transport 要求系统中只有一个匹配的 `10EE:9018` XDMA 接口。`pci_instance_id` 只增加身份核验，不能选择多块同时连接的同型卡。其他程序、旧测试和 GUI 不得同时占用 XDMA。

## 2. 创建隔离 Python 环境

在解包根目录执行（PowerShell）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r deploy\requirements-windows-py312.lock
.\.venv\Scripts\python.exe deploy\scalellm.py --help
.\.venv\Scripts\python.exe deploy\scalellm.py dry-run
.\.venv\Scripts\python.exe deploy\scalellm.py preflight
```

`dry-run` 仅使用标准库，核验 133 个 vendored 文件并显示路径；模型尚不存在时会列入 `missing_paths`。默认 `preflight` 只核 Python、依赖、源码 SHA 与导入，不打开设备。无需 Torch、Transformers 或 GPU。Windows 3.12 锁文件固定了实际板测所用的全部 17 个 wheel SHA；Linux CPU 检查可使用 `deploy/requirements.txt`，该文件只固定三个直接依赖。

程序在导入 NumPy/运行时之前设置 `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`、`TOKENIZERS_PARALLELISM=false`，并设置参考 LUT 的项目内路径；不修改系统 PATH 或全局 Python。`vendor_manifest.json` 是原实测源码和原硬件输入的身份边界，禁止直接修改 vendor 来绕过检查。

## 3. 自行获取和严格导出模型

按 Meta 的模型许可自行取得 **Llama-3.1-8B-Instruct** 原始 safetensors checkpoint 及 tokenizer/config。项目不下载模型，也不随包分发权重或 tokenizer。不能换用 base 模型同名旧 exporter；公开入口调用的是原严格 hardware exporter。

```powershell
.\.venv\Scripts\python.exe deploy\export_model.py identity --model-dir 'E:\models\Llama-3.1-8B-Instruct'
```

已测 checkpoint 的严格 SHA（由 config、tokenizer 身份和全部 safetensors 内容组成）为：

```text
8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d
```

确认身份后导出到新目录：

```powershell
.\.venv\Scripts\python.exe deploy\export_model.py export `
  --model-dir 'E:\models\Llama-3.1-8B-Instruct' `
  --output 'artifacts\llama31' `
  --expected-checkpoint-sha256 8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d
```

该入口逐层生成完整 32×9 个硬件文件、真实 RoPE 和原 schema2 `scalecode_manifest.json`；Host 资产采用按 256 行分块的精确 BF16→FP32 转换，不同时装入两个大矩阵。再次验证原 checkpoint 身份，防止导出过程中源文件变化。保留原量化与 layout，不更换数学。导出无 GPU、无隐式模型下载；`--resume` 只传递给原硬件 exporter，已存在的 Host assets 不会覆盖。

实际 32 层权重导出、原始 checkpoint 全内容验证与 Host 资产校验已完成。新的可移植包装器只做过 CPU 路径/小矩阵转换测试，没有再次导出整模型；本次真实板运行仍使用原冻结导出物。

## 4. 配置路径和驱动身份

复制 `deploy/config.example.json` 为 `deploy/config.local.json`。文件路径相对于 **配置文件所在目录**；可使用绝对路径或环境变量，不依赖用户名、盘符或远程 SSH。

主要字段：

| 字段 | 含义 |
| --- | --- |
| `artifacts` | `scalecode_manifest.json` |
| `host_assets` | `host_assets/manifest.json` |
| `output_dir` | 逐次新建的证据目录，默认根目录 `outputs/` |
| `bitstream` | 默认 `bitstream/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit` |
| `expected_checkpoint_sha256` | 严格 checkpoint 身份，Host 与硬件资产必须相同 |
| `expected_driver_sha256` | 使用者本机已审核、已安装的 `XDMA.sys` SHA；实际运行必须填写 |
| `expected_driver_inf` / `expected_driver_version` | 可选附加安装身份断言 |
| `pci_instance_id` | 可选精确 PCI 实例核验；transport 仍只支持唯一匹配卡 |
| `prompts` / `max_new_tokens` | 恰好两条非空 prompt；每条生成 1–2 个新 token |

通过 `Get-FileHash "$env:SystemRoot\System32\drivers\XDMA.sys" -Algorithm SHA256` 记录自己的驱动身份，并核对其与自行审核签名的包成员相同。不要将他人的已测 SYS SHA 当成自己的构建产物。

## 5. 精确下载工程 bitstream

随包 bitstream 大小 **80,159,259 B**，SHA256：

```text
66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47
```

先在 Hardware Manager 或只读 `deploy/jtag/probe_jtag.tcl` 中确认唯一目标链和 FPGA 名称。可由同版本 `hw_server` 连接并调用：

```powershell
& 'C:\AMD\Vivado\2022.2\bin\vivado.bat' -mode batch `
  -source deploy\jtag\probe_jtag.tcl -tclargs 'localhost:3121' '完整 target 名称'
```

获得精确 target 和 device 后，先打印计划，再显式下载：

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json program `
  --vivado 'C:\AMD\Vivado\2022.2\bin\vivado.bat' --server 'localhost:3121' `
  --target '完整 target 名称' --device 'xcvu9p_0' --dry-run
# 核对后删除 --dry-run 才执行 SRAM 编程。
```

脚本校验 bit SHA、精确 target/device、链上唯一 xcvu9p；没有 first-device 默认选择，也不写 Flash。SRAM 编程后 PCIe 资源可能需要重新枚举。先检查 PnP 和实际 CSR；本入口不自动重启、复位、重新安装驱动或循环尝试恢复。

## 6. 只读预检和推理

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json preflight --models --device
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json run --mode pilot
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json run --mode full
```

`--models` 校验全部工件/Host 资产与模板长度。`--device` 仅读设备身份、ABI、双 DDR/core/idle 及 IRQ 策略，不写应用 CSR。刚编程的干净 MODE_IDLE 允许通过初始依赖核查；原生产后端在 stage 时切到 SHARED，最终必须 SHARED 且排空。

`pilot` 只执行真实 layer0 的两条 Attention/GU、HostDown 和数值闭环，**不是完整生成结果**。`full` 每步遍历全部 32 层并将实际 FPGA 输出传入下一层。默认两个 prompt 使用原聊天模板（已经含 BOS，encode 不再加 BOS），右侧 padding 到 16 行，取最后有效行 logits 贪心采样。模板后的 prompt 长度与新 token 预算合计必须不超过 16。每次生成重算完整前缀，没有持久 KV decode；已结束请求只作为合法第二 cohort 伴随，不额外计新增 token。

每条 Attention 输出 196608 B、GU 输出 1376256 B 都先全量 C2H、独立整数 gold 比较和耐久落盘，才允许 clear/ACK。GU 两个真实 cohort 完成后 release；任何短 IO、超时、身份/数值错或资源不足停止，保留 pending/lease，不重试 START、不创建新 owner 清账。请保持前台终端到 native 进程自然退出。

结果在唯一 `outputs/AT_*_llama/`，入口 `run_summary.json`；邻接 `.driver_calls.jsonl` 为逐边界 trace。保存配置副本、vendor/运行源 SHA、驱动/boot、每层 raw output/gold/hidden、Down、完整 logits、token ID、最终 idle/句柄关闭状态。不要仅凭退出码忽略 `verdict`、计数与最终状态。

## 7. 可复现边界

本机完整板推理已实际通过；新的公开路径包装器完成了 CPU 依赖、身份拒绝、初始/最终状态、BF16 分块、独立硬件树 freeze/check、带空格目录搬移测试。未在第二台物理主机重复完整板测，也未重新综合/布局布线。驱动公共基线下载身份的缺口和签名条件见驱动说明；这些不是默认已经解决的外部依赖。

## 8. 固定 bit 的软件驻留模式

独立入口 `resident` 使用相同模型和整数/FP32 数学。首次把全 32 层 Attention 权重、Attention metadata、GU metadata 和 RoPE 写入各自 DDR 地址，逐项全量读回核 SHA；Attention 此后按层切地址。GU 权重受当前 RTL 的 canonical base 检查约束，仍逐层装入固定 56 MiB 窗口并全量读回；本模式没有全层 GU 权重切地址或 KV decode。具体布局和协议见 [软件合同](SOFTWARE_ONLY_INFERENCE.md)。

单个 IO owner 管理独立的 Attention/GU pending 身份，两 CPU worker 可准备下一层和执行 HostDown。metadata 预取只允许在当前层两条 GU 输出完整复制、核身份并 ACK 之后进行，与 CPU Down 重叠；COMMIT、换权重和新 epoch 仍等待旧层两条 Host consumer 释放。不得恢复旧的 GU 执行中并发 metadata LOAD 路径：该路径已在实板触发 watchdog，失败证据保留。程序不会自动维护、reset、重配、清 fault 或重试 START。

默认 `deferred` 模式允许配置中任意合法的两条短 prompt，不读取旧 run/baseline 目录。它保存完整真实输入/输出、身份、DONE、HostDown、hidden 和 logits，严格检查 IO 长度、错误、复制与 ACK/lease 生命周期，然后报告 `EXECUTION_COMPLETE / NUMERICAL_VERIFICATION_PENDING`。这个状态说明执行结束，尚不是数值 PASS。运行前可先查看计划：

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json resident --dry-run
# 两层 pilot 覆盖一次真实跨层预取，不执行 LM head，不生成完整模型结果。
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json resident --mode pilot --pilot-layers 2
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json resident --mode full
```

每个命令创建新 `outputs/AT_*_resident/`，保存源 SHA 和配置副本。源目录在运行后保持不变，或保存整个 `deploy/` 快照。随后在**同一执行主机、CPU/NumPy/BLAS 环境**做独立全输出审计；跨平台 LM-head BLAS 的 FP32 舍入差异不能被当成严格逐字节通过：

```powershell
.\.venv\Scripts\python.exe deploy\scalellm.py --config deploy\config.local.json offline-audit `
  --run 'outputs\本次AT目录' --source-root '.' --receipt 'outputs\本次AT.audit.json'
```

审计不打开 FPGA，不读取旧 baseline 输出，使用原独立 `ReferenceLayer` 重算每条实际输入的完整 Attention/GU gold、原 int64 Down、Host 边界和生成反馈。它核验实际源、权重/metadata/RoPE 和全部输出覆盖，写入新的独立 receipt；原始 summary 不改。receipt 必须是新文件。缺文件、身份变化、任何数值差异或未释放 owner 均不得 PASS。完整 32 层 CPU 审计有额外耗时，应与推理热路径时间分列。

`--validation-mode audited_baseline --baseline-root <已独立审计的原始run目录>` 是固定输入基准测试选项，要求实际输入 SHA 与已审核模型、gold 全匹配；缺项即停止，不静默退回 deferred。它不是部署一般 prompt 所必需的依赖，也不把 baseline 输出作为推理输入。两种验证模式在 `run_summary.json` 中显式记录，不能混用其验收结论。

2026-10-25 实测闭合：修复版两层 pilot 和默认 deferred 完整 32 层/两请求/两步均正常退出，完整运行实际完成 128 Attention、128 GU、128 HostDown、64 epoch release，得到 `It's` / `Hello!`。独立审计对 1032 个完整数值边界、256 处残差、4 份完整 logits/argmax 与 token 反馈全部通过；原 summary 保持 pending，独立 receipt 给出该次数值结论。正式推理 213.643 s，另首次准备 18.356 s；没有在新软件运行时同步测功耗。其他合法 prompt 的参数接线/无 baseline 路径已做 CPU 测试，尚未逐一实板验证，仍须自己的独立离线审计。旧的并发 metadata watchdog、一次安全维护/内部 soft clear 及失败任务退休证据保留，不并入本次成功结果。
