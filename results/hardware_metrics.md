# 硬件性能与资源

当前基线为E002/R001/AT002新工程正式综合，VCU118 xcvu9p-flga2104-2L-e、Vivado2025.2、core100MHz/UI200MHz。数字来自[综合事实](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/synthesis_stage_facts.json)与[板级资源](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth/observed_utilization_post_synth.json)，是综合网表统计，不是上板实测。

| 指标 | 正式综合结果 | 优化后结果（未布局） |
| --- | --- | --- |
| LUT | 841576 / 1182240（71.18%） | 828255（70.06%） |
| FF | 1029313 / 2364480（43.53%） | 1021363（43.20%） |
| DSP | 5451 / 6840（79.69%） | 5451（79.69%） |
| BRAM | 945 / 2160 tiles（43.75%） | 941 tiles（43.56%） |
| URAM | 752 / 960（78.33%） | 752（78.33%） |
| Setup估计 | WNS +0.904ns；TNS 0 | WNS +0.904ns；TNS 0 |
| Hold估计 | WHS -0.814ns；THS -49355.641ns | WHS -0.814ns；THS -48989.652ns |
| PW报告栏目 | WPWS -0.012ns；5个失败，最差为PCIe Max Skew | WPWS -0.012ns；5个失败 |
| 布局/布线结果 | 尚未取得 | AT009超时结束，无完整place DCP；独立physopt/route未运行 |
| 布局中间估计（非完成报告） | 不适用 | AT009内部优化WNS−1.884ns、TNS−1349.388ns；未取得对应完整hold/PW报告 |
| 吞吐/延迟/功耗 | 本轮未测量 | 本轮未测量 |

优化后数字来自[OPT命令/DCP与资源身份](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT004_complete_recovery_preflight_opt_place_physopt/opt_command_facts.json)及[实际时序](../project/hardware/vivado/reports/m002_E002_R003_AT004_complete_recovery_preflight_opt_place_physopt/timing_opt.rpt)。

布局中间估计来自[AT009原日志取证](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/post_place_bufg_opt_intermediate_facts.json)；它出现在place内部优化初始化，不是独立physopt或完成布局报告。10个BUFG插入候选全因placement/routing conflicts跳过，不能据此判route DRC失败。AT009峰值树RSS32.28GiB，终态为原2小时wall timeout而非内存/磁盘保护，见[终态事实](../project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R003/attempts/AT009_completed_pre_place_recovery_place_physopt/terminal_facts.json)。

聚合资源未超不代表物理可实现；综合时序仍FAIL，不能用未布局setup正值宣告100MHz收敛。旧工程性能预测及native025的未布线结果不与本次新网表作直接优劣比较。完整数值、真实互连事务与板级验收边界见[M002报告](missions/M002_summary.md)。
