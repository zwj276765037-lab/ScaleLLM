# E008：C01 定向卸载与完整物理实现来源

当前批次 R001/AT004 已自然失败结束；本摘要仅覆盖该次实现。唯一主动变量为 SwiGLU `g_row_branch[1].u_branch_leaf` 的合格物理对象硬约束至 SLR2。place=SSI_SpreadSLLs、physopt=Default、route=Default，关闭增量实现。Vivado2025.2/build6299465，VCU118/xcvu9p-flga2104-2L-e；core100MHz、双DDR UI200MHz不变。

父图为 E005/R004/AT003 debug_materialized.dcp（396068466B/SHA8451b2a8…）。AT004消费已审包b9dcabf4…/39实际归档源及144冻结生产输入，原约束/接口/RTL/IP、Hadamard、ScaleCode、format05不变。本次未重复综合/OPT/debug，也未运行bitstream/GPU/板卡/PPL/ACC。用户PDU恢复授权与[本次执行绑定](../../../.research-agent/decision_inputs/E008_R001_AT004_C01_PDU_resume_execution_20261017.json)保持，历史AT001/2入口失败和AT003受控停止均保留。

资格包含完整preplace、每成功阶段全局POST、fresh80保护、RAW/S/P原生对应、全部9491 P落SLR2、完整native端口索引、有向cut及四组through-LOAD有界时序。合格外部driver网省略外部peer LOAD；cap16不是完整cutTNS/SLL/带宽或安全签核。失败后的locality与诊断不代替成功route全局POST。正式reset/CDC/IO安全仍OPEN。

单EDA/CPU0–7/nice5/max8；RSS192GiB、MemAvailable48GiB/30s、disk30GiB保护，正常无墙钟/静默强停。本次自然失败，无资源强停。当前仅终态核验与发布，不重跑、不原样重试、不增新AT。

[完整物理合同](../../../mission/M002_ddr_separation_and_timing_recovery/exact_hotspot_offload_implementation_contract_2026-10-17.md) · [启动绑定与原始证据](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json) · [输入/源/进程/锁终态核验](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_facts.json)。旧逐阶段摘要见publication_history，原始证据不覆盖。


---
Published: 2026-10-17T22:53:01.197632+00:00
Publication: Pb3d3c6e3d5a44eee9fa95c24e1bacf89
