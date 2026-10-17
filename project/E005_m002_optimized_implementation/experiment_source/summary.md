# E005：优化依据与验收范围

依据用户“开始优化和新的implementation”授权、[E004冻结方案](../../E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)及[SM009合同](../../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)，实施Attention固定slot48个局部写控制、Gate/Down32个同拍输出CE；新综合后采用SSI_SpreadSLLs布局，独立physopt与router为Default。

平台为VCU118 / xcvu9p-flga2104-2L-e / Vivado2025.2，core100MHz、双DDR UI200MHz，Attention→DDR0、MLP→DDR1。Hadamard、ScaleCode、format05、数值格式和Host ABI不变。局部功能以冻结原版逐周期差分与独立oracle验证；实际网表核80边界，物理结果严格比较同阶段。合法布通要求原生命令成功、完整DCP/POST、全部routable已合法连接且无重叠/错误；时序及正式安全单独判断。

单EDA、CPU0–7/nice5/max8线程，保留192GiB树RSS、48GiB可用内存持续30秒、30GiB磁盘保护；正常进程无墙钟或无输出强停。未运行bitstream、板卡、GPU、PPL/ACC。两项RTL与布局策略同时改变，本轮不能分离各项因果贡献。旧工程及E003失败原证据保持。


---
Published: 2026-10-16T15:16:56.476634+00:00
Publication: Pc1f7cce8522f40539c3c16660e923a0e
