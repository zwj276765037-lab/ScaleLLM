# E002：执行状态

execution_state: running
verdict: unassessed
applicability: 正式综合AT002完整完成，物理入口适配/47项CPU验证完成；R003/AT001入口格式错误已修复，AT002已真实启动，尚无布局结果。

A006唯一EDA执行者，R003/AT001在launch前退出1，无INIT或遗留进程；属性值按同一语义改用0/1，47项回归通过。R003/AT002_project_init_opt_place_physopt于2026-10-15 03:23:12 UTC启动，supervisor3086186、owned group3086187。新入口按project init/opt实际物化debug hub并取证，OPT后自动检查全设计黑盒/时钟/覆盖/DRC和限定CDC/IO，未过则停在place前。原339输入与45 DCP冻结，新阶段脚本单独归档；A004待head-wave网表probe，A007复核实际阶段结果。

本次8 threads/8 logical CPU、nice5，进程树RSS192GiB、MemAvailable48GiB/30s、free disk30GiB保护，单次place/phys_opt流程2h。负时序数值如实保留，诊断准入与最终签核分开；无bitstream/板卡/GPU/PPL/ACC。


---
Published: 2026-10-15T03:27:29.074026+00:00
Publication: P4a307edf5dcf449c86d710b26cdfc9e5
Execution state: running
Research verdict: unassessed
Applicability: 正式综合完成；47项物理入口CPU检查通过，R003/AT001入口格式错误已修复，AT002真实init/opt/place/phys_opt流程运行中，尚无物理通过结论
Evidence:
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/observed_utilization_post_synth.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/cdc_critical_rows.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/synth_checkpoint_bindings.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/attempts/AT004_physical_diagnostic_final_cpu/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT001_project_init_opt_place_physopt/started.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT001_project_init_opt_place_physopt/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT002_project_init_opt_place_physopt/started.json
