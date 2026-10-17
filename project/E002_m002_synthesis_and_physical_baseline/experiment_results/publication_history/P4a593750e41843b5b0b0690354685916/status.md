# E002：执行状态

execution_state: running
verdict: unassessed
applicability: 正式综合完成；物理入口CPU检查通过，但实际INIT探针发现对象查询问题，正在常规修复。尚无布局布线结果。

R003/AT001启动属性错误已修复。AT002已完成真实project link与初始检查点写出，于2026-10-15 03:59:05 UTC结束，exit1、owned_survivors=[]；失败点为INIT POST的CDC目标查询。原始证据保留，A006唯一EDA执行者，准备修复后新AT，优先使用已保存真实project-init DCP并验证完整源码、约束、检查点及未完成探针的来源，避免重做无变化的完整link。原339输入及45个综合DCP路径继续冻结。

A007已核实工具debug占位和530/554对象的实际关联，仅支持限定诊断OPT；coverage/blackbox仍PENDING。A004核查完整register probe及待补head-wave/lockstep逻辑证据。未因CPU测试、源hash或对象名宣告物理/功能PASS。

同一时间最多一条EDA流程；8CPU、nice5、RSS192GiB、MemAvailable48GiB/30s、free disk30GiB，place/phys_opt每次2h。常规修复按现有授权继续，不改数值/时钟/接口合同，不运行bitstream/板卡/GPU/PPL/ACC。


---
Published: 2026-10-15T04:00:28.735535+00:00
Publication: Pcbabd7e8e0ca4d4cb3e5ad0038446eff
Execution state: running
Research verdict: unassessed
Applicability: 正式综合完成；真实project-init DCP已保存，INIT探针查询失败后常规修复中，OPT/place/route尚未执行
Evidence:
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/observed_utilization_post_synth.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/cdc_critical_rows.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/synth_checkpoint_bindings.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/attempts/AT004_physical_diagnostic_final_cpu/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT001_project_init_opt_place_physopt/started.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT001_project_init_opt_place_physopt/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT002_project_init_opt_place_physopt/started.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT002_project_init_opt_place_physopt/status.json
- project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R005/architecture_review.md
