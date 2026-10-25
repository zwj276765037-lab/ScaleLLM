# M006 GU-only 首轮实际上板验证

2026-10-25，Dell `DESKTOP-D3` / VCU118。指定工程 bit 已实际加载并完成本轮限定验证：**PASS**。bit SHA256 `66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47`，80,159,259 B。此结论仅适用于本次生产尺寸诊断，不代表完整模型、全部存储或物理/reset全签核。

| 阶段 | 实际结论 | 关键证据 |
| --- | --- | --- |
| 文件/JTAG | PASS，两端SHA一致，唯一XCVU9P | [准备摘要](preparation_summary.md) |
| FPGA易失SRAM加载 | PASS，精确target/device，原生program0；三SLR DONE/INIT_B均1、CRC_ERROR均0 | [加载回执](AT_20261025T011600.863121Z_program/receipt.json)、[配置状态复核](AT_20261025T011722.916109Z_collect_program/configuration_observation.json) |
| PCIe/驱动与应用CSR | PASS，精确9018设备重启后3份16CSR快照稳定匹配v7/caps1d/idle08 | [通过快照](AT_20261025T012429.910764Z_csr_after_restart/csr_snapshots.json) |
| 双DDR有限读写回环 | PASS，各local7fff0000页4096B，分别写不同模式，两通道读回/无别名，原始页恢复后再次一致 | [DMA回执](AT_20261025T012513.161146Z_dual_ddr_scratch/scratch_result.json) |
| 结构化生产GU | PASS，epoch1、command1/2，两个cohort；每次1376256B/458752个S24全匹配，先保存结果/DONE再ACK、释放lease | [主例回执](AT_20261025T012608.431477Z_gu_structured_2cohorts/receipt.json) |
| S37大项抵消边界GU | PASS，epoch2、command3/4，两个cohort；中间guard超S36且合法S37、最终无饱和；每次全输出0差异、ACK/lease释放 | [边界例回执](AT_20261025T012650.455542Z_gu_s37_2cohorts/receipt.json) |

Root独立读取四份实际C2H输出binary与gold逐字节复核，总计 **5,505,024 B / 1,835,008个S24，0差异**；并独立核全部DONE身份、字节/record计数与ACK后idle。见 [Root复核](root_byte_comparison.json)。主例output/gold SHA `23e993b366a9e90580237ab63474f2813bf0f6009aced7f701ba2bc6893b20bc`；S37例SHA `dcc2ffa2238305741006f99055f897ed4bf4423daed79e554614e71d7144c631`。

每个命令固定16行、K4096、N14336，输入73728B、输出1376256B/1792 records；每个epoch内覆盖cohort0/buffer0和cohort1/buffer3。独立gold包含原exporter packing parity及独立wire/scalar整数复算；输入没有使用板上输出调整。CPU准备证据见 [诊断交付](diagnostic_gu/delivery_report.json)。Dell旧Python经本地现代Python backend+持久SSH Windows ctypes接口完成实际I/O，ABI/RTL/bit不改。

加载后首读16个应用CSR全FFFFFFFF，完整失败证据[保留](AT_20261025T012136.428143Z_csr/csr_snapshots.json)；该时点未写应用CSR或做DMA。后经一次仅对9018精确实例的设备重启恢复；未重启Dell、移除设备、重装driver或写Flash。DMA/计算只在恢复后ABI/readiness通过才执行。

生成XCI的BAR2参数与Windows实际1MiB+64KiB资源观察分列，不能把H2C/C2H的4GiB AXI地址空间当成OS必须分配的PCIe BAR前置。实际host地址7fff0000/ffff0000读写和GU数据传输已通过；不改写生成参数或忽略观察差异。

Max-DPO、external reset原签核仍OPEN。本次未验证Attention并发、32层真模型/Host Down、全部DDR地址、性能吞吐或故障reset恢复。实际运行计划见 [当前合同](../../../../mission/M006_mlp_linear_only_hardware/board_validation_plan_2026-10-25.md)。最终3份只读快照JOB_STATUS=8、DONE_ERROR=0、ADMISSION=0，PCIe9018仍正常；自有RPC/下载工具进程及33121监听均退出，bit保留配置。见[工程总回执](host_execution_summary.json)及[最终状态](AT_20261025T012753.641597Z_final_idle/)。

架构角色集中独立审核结论 **LIMITED_PASS**，当前已执行scope无阻断，见 [阶段审核](stage_review_20261025.md)。
