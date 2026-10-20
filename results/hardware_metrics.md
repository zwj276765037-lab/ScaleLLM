# 当前硬件指标：M003 / E011 / R003 / AT006

更新时间：2026-10-20。平台 VCU118 / xcvu9p-flga2104-2L-e，Vivado 2025.2。

本版 place 和 physopt 命令及完整阶段资格通过，route 自然失败（797175 node overlaps / 615840 resource-conflict nets）。以下资源为本版实际 **physopt postPlace** 统计；失败图时序仅供诊断，尚无合法布线 Fmax、bitstream 或板卡吞吐。

## 实际时序

目标 core100 MHz（10ns），独立 DDR UI200 MHz。WNS/WHS/WPWS 分别为 setup/hold/pulse-width 最差余量；负数表示对应检查未通过。

| 实际阶段 | WNS ns | WHS ns | WPWS ns | setup失败端点 |
| --- | ---: | ---: | ---: | ---: |
| place | -2.797 | -0.565 | 0.000 | 42325 |
| physopt | -2.753 | -0.565 | 0.000 | 42241 |
| route_failed | -12.617 | -0.147 | -0.363 | 532329 |

physopt 最差 setup 是 core_gate/u_ready0_cdc/arststages_ff_reg[3] 到 MLP projection_repack/g_output_payload_row[11].out_payload_r_reg[4561]/CE，10ns同核心时钟路径。数据延迟12.042ns，其中 route11.628ns（96.562%）；失败route图的最差路径是 MLP serial_command/state_r_reg[2] 到 shared_compute parent_head_r[3806]/D，数据22.607ns，其中route22.285ns（98.576%）。这些比例支持互连压力的诊断线索，不证明全部时序违例有同一根因。

若只用physopt这条10ns同频setup最差余量作周期换算，1000/(10+2.753)≈78.4MHz；这不是已实现Fmax，不包含完成合法布线后的路径/时钟变化，也不能关闭hold或pulse-width问题。原100MHz和余量目标未改变。

原始报告：[place](../project/hardware/vivado/reports/m003_E011_R003_AT006_successful_place_POST_physopt_route_cwd_fixed/timing_place.rpt)、[physopt](../project/hardware/vivado/reports/m003_E011_R003_AT006_successful_place_POST_physopt_route_cwd_fixed/timing_physopt.rpt)、[失败route](../project/hardware/vivado/reports/m003_E011_R003_AT006_successful_place_POST_physopt_route_cwd_fixed/route_failed_timing.rpt)。

## 实际资源

| 资源 | 已用 / 可用 | 使用率 |
| --- | ---: | ---: |
| CLB LUT | 801147 / 1182240 | 67.77% |
| CLB registers | 1021742 / 2364480 | 43.21% |
| DSP48E2 | 5451 / 6840 | 79.69% |
| BRAM tile（36Kb等价） | 941 / 2160 | 43.56% |
| URAM | 752 / 960 | 78.33% |
| CARRY8 | 54224 / 147780 | 36.69% |
| 占用CLB站点 | 145778 / 147780 | 98.65% |

| 区域 | 占用CLB站点 | LUT | registers | DSP |
| --- | ---: | ---: | ---: | ---: |
| SLR0 | 96.71% | 57.38% | 36.98% | 79.52% |
| SLR1 | 99.33% | 70.38% | 43.68% | 88.82% |
| SLR2 | 99.90% | 75.54% | 48.97% | 70.75% |

站点占用表示逻辑已经铺开到多少CLB，不等同LUT/FF槽位全部用尽。全局槽位有余量与局部线路拥塞可以同时存在。

来源：[全板资源](../project/hardware/vivado/reports/m003_E011_R003_AT006_successful_place_POST_physopt_route_cwd_fixed/utilization_physopt.rpt)、[分SLR资源](../project/hardware/vivado/reports/m003_E011_R003_AT006_successful_place_POST_physopt_route_cwd_fixed/utilization_slr_physopt.rpt)。

## 性能条件估算

按core100MHz、每个MAC算2次有用运算、阵列每拍接收有效组、无背压的条件：

- Attention投影物理8行×16列×32元素：0.8192 TOPS（A8W8）。cohort16由两波复用同一物理阵列，不能再乘2。
- MLP两个8行×12列×32元素阵列：1.2288 TOPS（A8W4）。
- 两引擎同时满载时矩阵峰值合计2.048 TOPS，混合精度；它不代表整机持续算力。
- 单DDR权重接口512bit×200MHz/8=12.8 GB/s，两通道合计25.6 GB/s（接口理论上限，非实测DDR有效带宽）。

[现存架构模型](../project/hardware/data/attention_mlp_architecture.json)明确board_measured=false，历史条件输入而非本版重新测量。它给出32层cohort16：Attention22668478周期/0.22668478s、MLP22292480周期/0.2229248s；理想双cohort流水重叠70.5826 aggregate tokens/s，串行诊断相加35.5864 aggregate tokens/s。串行值与理想重叠值是两种情景，不是本版性能置信区间；Host周转、真实DDR和全阶段重叠尚未完成测量。MLP局部当前XSim验证了2048输入/2048issue周期与II=1，但不能据此替代整层/整机周期。

**当前专属DDR下的关键带宽限制：** MLP32层矩阵payload为2818572288B，按cohort16完美复用一次计算，DDR1 payload-only上限为12.8e9×16/2818572288=72.6609 aggregate tokens/s。70 tokens/s仅MLP矩阵就要12.3313GB/s，即单DDR1峰值96.3379%，尚未计metadata、数据读写、协议和访问损失。因此不能由旧双DDR总25.6GB/s的约71%利用率判断70 tokens/s有充分余量。

| 假设DDR1有效权重payload带宽 | payload-only吞吐上限，aggregate tokens/s |
| --- | ---: |
| 理论峰值60%（7.68GB/s） | 43.60 |
| 理论峰值70%（8.96GB/s） | 50.86 |
| 理论峰值80%（10.24GB/s） | 58.13 |

这些是带宽情景下的上限，不是实测吞吐或预测区间；需要同时满足核心频率、权重16行复用、调度/算子、元数据/数据和Host限制。真实端到端吞吐可能更低；batch1、prefill、不同上下文长度不能套用这一aggregate口径。当前M003尚无已验证的整机tokens/s。

依据：[MLP调度模型](../project/hardware/model/v5_schedule_contract.py)、[Attention物理阵列](../project/hardware/rtl/attention/hap_a8w8_array_16x16_s42_col3.sv)、[MLP物理阵列](../project/hardware/rtl/mlp/hap_a8w4_slice8x12_group_s37.sv)、[DDR专属接口](../project/hardware/source/m002_dedicated_ddr.md)、[当前局部XSim](../project/hardware/vivado/reports/m003_E011_R001_AT002_M2_production_dispatch/xsim.log)。

---

下列为原E002历史指标，保留原文；不覆盖上方M003实际版本。

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
