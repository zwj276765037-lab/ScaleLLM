# M002 / SM009 同周期局部控制实现说明

授权：[2026-10-16优化合同](../../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)。依据：[冻结方案](../../E004_m002_routability_optimization_analysis/experiment_results/optimization_plan.md)，SHA256 `9b666f60371b07f67284b0ae402fda28ee3e1ae30db8bac243bd03064a7567f3`。原算法、format05、ABI、时钟与数值来源沿用[design.md](design.md)对应章节，本次只改变同拍目的写/CE物理结构。

Attention `hap_tensor24_input_buffer` 每个实例分24个固定256-bit slice owner，双wave共48个。每个slot一个受保护标量LUT6，I4:I0为capture_index，I5为 `!clear && active_r && !output_valid_r && read_stage_valid_r`；INIT只有bit32+slot为1。因此CE与原动态目的写资格等价。每slice仍用 `posedge clk or negedge rst_n`、reset清零、clear保持。active/valid/index/pending/read stage、BRAM读延迟、slot23→valid和6144-bit外部快照及波选择均不变。序列化输出模块字节不变。DONT_TOUCH只标量decoder，未保护data bank。

MLP s24/s32 history2 每个生产ROWS16实例分16个固定输出row owner，共32个组合LUT1 identity CE；资格严格 `rst_n && !clear && input_fire && produces_output_c`，分别驱动384/512-bit slice。原reset/clear分支不更新payload，新增同拍资格维持此优先级。out_valid/metadata/count/error控制always除移出payload赋值外不变。SRL16E实例/INIT/地址/CE原文保持，尤其不把SRL input_fire改成受reset/clear抑制。无新增周期、无端口或数值变化。

功能准备及真实结果入口：[E005/R001](../../E005_m002_optimized_implementation/experiment_results/runs/R001/run.md)，[执行清单](../../E005_m002_optimized_implementation/experiment_results/runs/R001/functional_execution_list.md)。修改前小文件、源diff、参考派生和当前源身份分别保存，未复制整套生产工程。实现功能、综合、布局布线、时序和板卡结论独立记录；80个控制边界不是净80个LUT增量或可布通保证。

## 本次功能结果

2026-10-16，A006单EDA执行、A009重读原日志核验：Attention AT001 PASS（1265488差分周期、192中断、196epochs、4完整双wave128group）；MLP AT003/v2 PASS（Down2477周期/49独立输出，Gate4821周期/98输出，同拍consume/refill/reset/clear与错误场景均命中）。AT002/v1仅TB声明位置编译失败，原版保留，v2前移声明不改RTL/刺激/oracle/断言。

[本批最终小facts与冻结3RTL身份](../../E005_m002_optimized_implementation/experiment_results/runs/R001/rtl_functional_final_facts.json)。功能、原生综合边界、物理布局/布通/时序分别取证，当前仅完成局部功能范围。
