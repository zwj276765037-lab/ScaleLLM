# Dell / VCU118 实际板测交付

2026-10-25，工程执行完成，限定结论 **LIMITED_BOARD_FUNCTION_PASS**。本次实际使用 bit SHA `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`（80159259B），同机 Vivado 2022.2 已加载 `xcvu9p_0` SRAM，program/configuration 两次原生退出码均0。没有写 flash、重启 Dell、安装驱动或改 RTL/bit。

权威执行明细与全部实际源码 SHA：[host_execution_summary.json](../../../experiment_results/board_validation/host_execution_summary.json)。本文件补充并取代旧 preflight 中后续阶段 NOT_RUN 的当前状态；旧预检/失败证据保持原文。

| 阶段 | 结果 | 实际证据目录（`experiment_results/board_validation/` 下） |
| --- | --- | --- |
| SRAM 编程/配置 | PASS，3SLR DONE/INIT_B=1，CRC_ERROR=0 | `AT_20261025T011600.863121Z_program`；原生日志 `AT_20261025T011722.916109Z_collect_program` |
| 初次应用 CSR | FAIL，全FF；未写应用CSR/DMA | `AT_20261025T012136.428143Z_csr` |
| PCIe 恢复 | 一次 scan 后仍FF；精确单设备 restart 后恢复，均exit0 | `AT_20261025T012321.542161Z_pcie_scan`；`AT_20261025T012357.782981Z_pcie_restart` |
| 三份只读身份/状态 | PASS，GU-only ABI/caps/idle 全符合且稳定 | `AT_20261025T012429.910764Z_csr_after_restart` |
| 两 DDR scratch | PASS，各local `0x7fff0000` 4096B；备份、不同pattern、无alias、原页恢复读回一致 | `AT_20261025T012513.161146Z_dual_ddr_scratch` |
| 完整生产非零 GU | PASS，同epoch1，command1/2，两个cohort，各1376256B/458752个S24全量零差异 | `AT_20261025T012608.431477Z_gu_structured_2cohorts` |
| S37 guard 大项抵消 | PASS，新epoch2，command3/4，同样两个cohort全输出零差异 | `AT_20261025T012650.455542Z_gu_s37_2cohorts` |
| 最终空闲/清理 | PASS，三份最终快照一致、无未ACK DONE/错误；board-tool/RPC进程与33121监听均空 | `AT_20261025T012753.641597Z_final_idle` |

共 **4 个完整生产尺寸 GU 命令，5505024 输出字节 / 1835008 个S24值全量一致**。每个 cohort 都先持久化完整输出、DONE 和逐字节比较，再 ACK；每组两个 cohort 完成后 release，两个最终 lease 均为 null。保留当前 bit 配置，没有为收尾复位或重新编程。

Windows Python 3.6.5 仅运行自有标准库/ctypes RPC bridge，本地现代 Python 运行冻结 backend 与独立 gold。实际远端/本地 adapter SHA 均为 `ff64ca61a9bb1345d55fd805e4c43f67c13538de1f58db60580453e1a369fa91`；Windows py_compile 和4项地址/精确字节数/短IO/取消资源寿命单元检查通过。每请求5s overlapped等待，CancelIoEx后至多1s取消排空，未完成则保留buffer/OVERLAPPED并poison；RPC外层8s，无自动重发START/ACK。本次正常I/O均成功，未在真实设备上注入超时故障，因此不声称已板测证明所有驱动取消路径。

实际 Windows 资源为 `0x70600000..0x706fffff`（1MiB）和 `0x705f0000..0x705fffff`（64KiB）；它们与 XCI 声明参数、4GiB AXI DMA 地址空间是不同证据。两通道 scratch 和实际GU DMA已通过，不据资源表扩改 BAR 或原 XCI。

本结论仅覆盖指定 bit 的有界 GU 板级功能。Max-DPO/external-reset 签核仍开放；完整32层、Attention并发、Host Down、模型精度与硬件性能基准未在此验证。记录中的约1.8秒含SSH/RPC/CSR/输出传输，不作为FPGA原生延迟或吞吐。
