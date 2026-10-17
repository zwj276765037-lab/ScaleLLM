# E003：阶段结果

129项CPU检查已通过：14项新profile、13项既有恢复、6项隔离和96项既有物理检查本次均执行。真实339综合输入、45 DCP路径及AT008完整debug/pre_place资格通过；5份生产/测试文件已安装，Tcl、RTL、XDC不改。主控独立核5份安装后hash一致。[检查结果](runs/R001/attempts/AT001_full_implementation_profile_cpu/validation_result.json)、[实际源资格](runs/R001/attempts/AT001_full_implementation_profile_cpu/actual_source_qualification.json)、[安装身份](runs/R001/attempts/AT001_full_implementation_profile_cpu/installation.json)。

本次实际Vivado于2026-10-15 12:22:11.492419 UTC启动，正在恢复原AT008完整debug/pre_place检查点。尚无新的place/physopt/route完成结果。[实际启动](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_eda_started.json)。

监督起点12:21:48.608023 UTC；place/physopt阶段截止2026-10-16 00:21:48.608023 UTC，总物理截止2026-10-16 12:22:11.492419 UTC。8CPU/nice5/原资源保护保持，重试不得重置预算。[实际预算](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/effective_budget.json)。

基线来自[E002总报告](../../E002_m002_synthesis_and_physical_baseline/experiment_results/engineering_final_report_2026-10-15.md)：综合、OPT/debug/pre_place已完成，原AT009无完整布局DCP，不能继承部分布局。新授权与E002旧政策、原失败均分开。负时序可继续诊断布线，完整物理与最终时序/安全验收分别判断。无bitstream/板卡/GPU/PPL/ACC。


---
Published: 2026-10-15T12:24:02.917416+00:00
Publication: Peac508fd37364b2286b8c4450e3b7219
