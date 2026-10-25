# GU-only 硬件源码与构建

## 已发布设计身份

发布 bit 对应 R008/AT001 的 102 项输入，其 SHA 存于 `deploy/hardware_release_manifest.json`，原样副本位于 `deploy/vendor/hardware/`。本次逐项复核当前源码、父 manifest 和父 source_snapshot：102 项全部一致。`ddr_timing_recovery.xdc` 虽相对 Git 为 modified，但与该 bit 父输入 SHA 相同，不是把后续约束结果混入旧 bit。

顶层为 `hap_attention_mlp_resource_top_gu_only` 系列：Attention 与双 DDR 保留；FPGA 只执行 MLP Gate/Up，Down 在 Host。GU ABI7、caps `0x1d`；Attention ABI2。不能替换成旧 v5 整板 checker 或旧 Linear/Down 顶层。

- FPGA：`xcvu9p-flga2104-2L-e`（VCU118）。
- 核心 100 MHz，DDR UI 200 MHz。
- **实际构建设计工具：Vivado 2025.2。** 已测 SRAM 下载工具为 Vivado 2022.2。
- 已发布 bit：80159259 B；SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`。
- 已合法布线并通过所述板上数值验证；Max-DPO 与外部 reset 的完整物理签核仍开放，不等同产品级全签核。

## 新建构建树

需要 Linux x86_64、Python 3.10+、Vivado 2025.2 及适用许可证和官方 VCU118 board files（同一个目录内含 `board.xml`、`part0_pins.xml`、`preset.xml`）。AMD 工具、IP 和 board store 由使用者自行安装并接受其条款。

```bash
python3 deploy/build_hardware.py prepare \
  --work '/data/builds/ScaleLLM GU build' \
  --vivado '/opt/AMD/2025.2/Vivado/bin/vivado' \
  --board-files '/opt/board-store/boards/Xilinx/vcu118/2.4' --dry-run
# 核对后移除 --dry-run：只物化新源码树并 freeze/check，不运行 Vivado。
```

`prepare` 校验 102 个发布输入，然后复制到新目录；只修改副本中的 Vivado 可执行文件路径和三个 board XML 路径，再生成新 freeze。原发布副本不变。board XML SHA 和两项适配 SHA 保存在 `portable_build.json`。用户选择不同 board files 或工具补丁会形成新输入身份，不承诺重建 bit 逐字节相同。

## 连续构建入口

```bash
python3 deploy/build_hardware.py stage --work '/data/builds/ScaleLLM GU build' \
  --stage create --attempt AT001_constructor --dry-run
python3 deploy/build_hardware.py stage --work '/data/builds/ScaleLLM GU build' \
  --stage synth --attempt AT002_synth \
  --project '/data/builds/ScaleLLM GU build/project/hardware/vivado/project/m006_gu_AT001_constructor' --dry-run
python3 deploy/build_hardware.py stage --work '/data/builds/ScaleLLM GU build' \
  --stage impl --attempt AT003_impl \
  --project '/data/builds/ScaleLLM GU build/project/hardware/vivado/project/m006_gu_AT001_constructor' \
  --synth-dcp '/path/from/successful/synthesis.dcp' --dry-run
```

每次先核计划，移除 `--dry-run` 才运行原 `run_mlp_gu_board.py` 和 `create_mlp_gu_board.tcl` / `build_mlp_gu_board.tcl`。实际 DCP 路径从本次成功原生日志取，不把历史 DCP 伪装为新综合结果。若原生 netlist/clock/DRC 检查失败，先审错误，不能绕过资格检查继续 impl。

实现通过后可独立生成工程验证 bit（`--output` 是**不存在的新目录**）：

```bash
python3 deploy/build_hardware.py bitstream --vivado '/opt/AMD/2025.2/Vivado/bin/vivado' \
  --routed-dcp '/path/to/accepted_routed.dcp' --output '/data/builds/new_bit_output' --dry-run
```

原 runner 使用 Linux flock 单重 EDA、8 个 Vivado线程/OOC4，限制选取的 CPU 集合最多32；包含 64 GiB MemAvailable/磁盘余量检查及进程树保护。历史物理构建使用高内存主机，工程曾按 192 GiB 树预算运行。不要将 8 GiB Host 推理预算误用于 Vivado。新机器先评估内存和工具许可，重型阶段不与其他 EDA 争用；本次发布整理未重新执行 EDA。

## 再生文件与历史记录

新 constructor 从 RTL、XDC、manifest、官方 board/IP 重新生成 BD/XCI；不读取旧 constructor `.gen`、`.cache`、`.ip_user_files` 或 `generated_phy_snapshot` 来构建。本次只清除了可再生缓存，保留了 `.srcs/.xpr/constructor_identity/.runs` 与 reports/DCP/bit。旧缓存的生成文件全量字节复核不再可执行，不能据此宣称历史 generated inventory 仍齐全。

独立新目录的 `prepare` 与 freeze/check、带空格路径均有 CPU 测试；这只证明源闭包与路径准备，不能证明新机器综合、时序或实现成功。完整报告和资源见 [性能与资源](PERFORMANCE_AND_RESOURCES.md)。
