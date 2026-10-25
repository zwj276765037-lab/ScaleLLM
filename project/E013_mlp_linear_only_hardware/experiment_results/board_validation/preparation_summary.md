# M006 GU-only 上板测试准备（2026-10-25）

用户指定 AT003 工程验证 bitstream，Dell 主机通过 PCIe 接 VCU118；本轮准备加载与功能验证入口。Root 负责整合，工程 `/root/board_host_prepare`（启动参数 gpt-6.1-sol/xhigh）负责主机预检，架构 `/root/board_contract_review`（启动参数 gpt-6-astra/xhigh）负责验证计划。

## 已核事实

- 本地 bitstream 80,159,259 B，SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`，与 AT003 manifest 一致；header `xcvu9p-flga2104-2L-e`，Vivado 2025.2。证据：[bitstream_preflight.json](bitstream_preflight.json)。
- Dell `DESKTOP-D3` / OptiPlex 7000 / Windows 10 Pro 19045，PCI `10EE:9018`、Xilinx DMA、XDMA 服务运行、设备 Status OK / Problem 0。
- 开机后首次未枚举到下载线；复查于 00:59:12 UTC 已出现 FTDI `0403:6014`、串号 `210308B76D50`，Status OK。随后原生 JTAG 探测成功，具体结果如下。
- Dell 已有 Vivado/hw_server 2022.2；预检时服务未运行。当前工程 Host transport 使用 Linux 文件描述符，Windows CSR/DMA 接口仍须对应实际驱动映射。

## Dell 已暂存文件

远端独立目录：`C:\Users\dell\ScaleLLM_board_validation\M006_GU_66a305348d30_20261025`。bitstream 与初始 Tcl/PowerShell 工具已逐件校验，状态 `STAGED_VERIFIED`，无硬件写入。证据：[远端暂存收据](host_preflight/20261025T010121.373220Z_staging/receipt.json)。编程入口只操作 FPGA 易失 SRAM，须显式给定服务器、完整 JTAG target、device 与 bit 路径，校验文件名、长度、SHA256 和唯一 XCVU9P，不自动写 Flash。

## JTAG 实际结果

同机 Vivado/hw_server 2022.2 两次原生只读探测均 exit 0：target `localhost:33121/xilinx_tcf/Digilent/210308B76D50`，唯一 device `xcvu9p_0`、PART `xcvu9p`、IDCODE `14B31093`、PROGRAM.IS_SUPPORTED=1。未执行编程、复位、Flash 或 AXI 写入。证据：[JTAG 收据](host_preflight/20261025T010223.461182Z_jtag/receipt.json)。精确清理本次自有服务树后，[最终复核](host_preflight/20261025T010223.461182Z_jtag/cleanup_recheck.json)确认自有 PID/相关服务和 33121 监听均已退出。

## 测试顺序与当前边界

身份与 JTAG → 加载 SRAM → PCIe 重新枚举 → user CSR ABI/状态 → 独占 scratch DMA 读回 → 完整生产形状 GU 与独立整数参考。预期 ABI 值已从合同生成：[expected_readonly_csrs.json](expected_readonly_csrs.json)。该文件仅预期值，未读回硬件。

固定生产形状为 16 行、K4096、N14336；输入 73,728 B、输出 1,376,256 B / 1792 records。小规模 N128 仿真不能直接替代此 bitstream 的实际输入。

脚本静态校验已通过：Python AST、Tcl 完整性、Dell PowerShell 实际 parser；本地 bit 身份检查通过，缺失精确目标会被拒绝。证据：[校验收据](host_preflight/20261025T0103_checked_scripts/receipt.json)。这些不替代设备写入或功能测试。

本轮实际 FPGA 编程、CSR 读回、DMA 与 GU 数值比较均为 **NOT_RUN**。加载文件/脚本与设备链路准备完成；完整计算测试还需要 Windows XDMA transport 和生产形状诊断输入/独立 gold，这两项为 **NOT_READY**，不能宣称整套计算测试已可立即运行。原 Max-DPO 与外部 reset 签核开放不因工程准备而关闭，原冻结 manifest/物理质量结论不改写。A022 当前约束资格流程及输入未受干预。

[分阶段计划](../../../../mission/M006_mlp_linear_only_hardware/board_validation_plan_2026-10-25.md) · [工程工具与主机预检](../../experiment_source/gu_only/board_validation/host_preflight.md)
