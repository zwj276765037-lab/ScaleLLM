# PDU维护停机：暂停与续接记录

状态：**已按用户指令停止并暂停。** 2026-10-17北京时间16:44:09，Vivado及监督器结束，14项收尾检查通过、项目EDA锁释放；两只读观察器随后自然exit0，无残留本项目运行进程。**未经用户新的“继续”指令，不启动EDA、观察器、自动重试或新AT。** 本次强停由2026-10-17当前用户明确授权，原因是服务器关机更换PDU；不判为方法失败，不判完整implementation完成。

## 当前任务与已完成范围

M002 / SM012 / E008，唯一选定候选C01：

`scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`

将其9491个实际P成员放到SLR2 hard、nonexclusive、non-routing-contained Pblock。原RTL/IP、Hadamard、ScaleCode、format05、Host ABI、core100MHz和双DDR UI200MHz保持。E006完整比较与终态已闭合，C01选择保持。

当前AT003：`project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation`。
报告：`project/hardware/vivado/reports/m002_E008_R001_AT003_C01_physical_xdc_fix_full_implementation`。

AT003于北京时间15:43:04启动。已完成并独立接受成员RAW9514/S9507/P9491、资源与before策略、真实物理XDC导出、9491成员SLR2 Pblock、9525对象after策略保持、完整端口索引、有向cut和四组有界时序；完整restored pre-place通过，已真正进入SSI_SpreadSLLs布局。尚未取得place完成、physopt或route结果。

有界时序仅为未布局估计：ingress setup/hold +6.158/−0.074ns，egress +6.859/+0.081ns。不是迁移收益或route签核；80旧synth/place/physopt保护表为继承证据，本次post-place仍须fresh核验。

## 本次停止与保全

[明确授权](../../.research-agent/decision_inputs/E008_user_PDU_shutdown_stop_and_pause_20261017.json)。A006唯一信号执行者，已于16:44:00.987566向重新核验的supervisor1560167/start933552991发SIGTERM。原生Vivado为1560384/start933554214；监督终态16:44:09.782954，native−15、supervisor125，stop_reason=`KeyboardInterrupt:signal 15`。原始status中的completed只代表监督生命周期结束，不能当作实现成功。

[原始终态](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/status.json)、[信号回执](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/user_PDU_supervisor_signal_sent_20261017.json)。[14项真实收尾](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT003_C01_physical_xdc_fix_full_implementation/terminal_summary.json)全部通过：144生产输入及运行源保持、登记PID/start结束、资源锁释放；观察器65187/12141已自然exit0。终态facts SHA256 `ed000baf22e8e16cd48dbe5f1c950bdb7dfd4c0988cf459dffb2534ca7a5a798`。

## 恢复入口与限制

本次报告目录没有完成的`.dcp`产物，不能从内存中的布局阶段原地继续。恢复使用原E005已冻结父图，重新应用同一候选约束并执行pre-place→place→physopt→route；无需无依据重做综合、OPT/debug或未受影响功能测试。

父检查点：`project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/debug_materialized.dcp`，396068466B，SHA256 `8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f`。

已审运行包：`agent/A006/E008_physical_xdc_fix/E008_entry/prepared_manifest.json`，SHA256 `b9dcabf46f82b505e0a49de9a2c14eb013b7d71937e2d2805a9538f7545227bb`，本次39份归档源。它包含RLOC_ORIGIN真实schema兼容和`write_xdc -type physical`修复；旧失败AT001/AT002及旧包保留，不退回旧入口。

实际选择绑定：`.research-agent/decision_inputs/E008_R001_AT003_C01_physical_xdc_fix_execution_20261017.json`，14144B，SHA256 `c8c3a3eaf6bb13d2315bf678eec2c7ea9eceb72a15f7773f64e409c03894454a`。当前合同为同目录`exact_hotspot_offload_implementation_contract_2026-10-17.md`，同时适用`directed_candidate_cut_scope_revision_2026-10-17.md`与`top_port_reverse_index_acquisition_revision_2026-10-17.md`。

用户通知继续后，先读本记录、[E008状态](../../project/E008_m002_exact_hotspot_offload_implementation/experiment_status/summary.md)和[工程续接记录](../../agent/A006/resume_E008.json)，核挂载路径/Vivado2025.2/许可/磁盘/内存/唯一EDA及144生产输入/父DCP/运行包身份。新开下一AT（当前预计AT004，以实际登记为准），保留AT003，不覆盖原尝试。直接使用既有launcher，不在外层重复nice/taskset。普通同C01修复委派在恢复后继续有效；本次暂停优先，不得利用旧委派自动重启。

原资源限额：本项目唯一EDA，CPU0–7/nice5/max8，树RSS192GiB、MemAvailable48GiB/30s、磁盘30GiB。正常无墙钟/无输出强停规则在用户恢复后仍适用；本次PDU授权不是今后任意强停许可。无bitstream、GPU、板卡、PPL/ACC，旧工程只读。

## 已完成备份

GitHub `zwj276765037-lab/ScaleLLM` main已发布当前源代码快照：`85303c79965cf7995b581d389c97116daf3c50a8`。[发布回执](../../results/verification/github_publication_20261017.json)。该快照保留144生产输入及有界记录，**不包含大型DCP、完整原始报告或本次随后发生的停机终态**；恢复依赖服务器保留的原文件。未安排服务器关机后的自动重启或自动通知。
