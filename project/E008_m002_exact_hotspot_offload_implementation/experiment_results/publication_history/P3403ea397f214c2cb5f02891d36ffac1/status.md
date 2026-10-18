# E008：AT004实际place PBP运行中

execution_state: running
verdict: unassessed

用户“可以继续了”已解除PDU暂停，AT004于北京时间17:23:05真实启动；39源/b9dc、144生产输入/父8451、完整restored preplace及真实SSI_SpreadSLLs调用已独立接受。当前10:40Z实际place已自然推进到Phase2.1.1.1 PBP（Partition Driven Placement），RSS28.78GiB/MemAvailable465.44GiB/disk391.0GiB，PID/start保持且CPU持续增长；尚无place命令完成/POST/locality/physopt/route结果。

本轮PBP告警经[A007只读独立审核](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/place_warning_contract_impact_review.md)核查：全设计SLR1→SLR2当前需10865/17280 SLL（62.88%），仅阶段估计，不是候选专属代价、最终用量、合法route或timing；旧10594对应SLR0→1不可同边界相减。USER_SLL_REG忽略提示可见100个DDR/MIG对象，随后抑制、真实总量未知；旧轮亦存在且曾非致命，不证明本轮无害。9525原策略快照不含这些DDR对象/该属性，原字节保持不等于placer实际兑现，也不能由warning反推工程删除或软化。无新增停点，原流程/完整验收保持。

后续连续执行实际place及fresh POST/80保护/成员reconciliation/全部P落SLR2/cut/timing，再physopt和route；自然终态后核输入/源/PID/start/lane和资源。原同C01常规来源修复/独立delta/真实新AT重试委派保持，选型/架构/验收变化归Root。

正常无墙钟/无输出强停，单EDA、CPU0–7/nice5/max8及RSS192GiB/Mem48GiB30s/disk30GiB保护保持，无bitstream/GPU/板卡/PPL/ACC。AT003原始用户停机/14项收尾和所有旧证据保留。


---
Published: 2026-10-17T10:40:50.959695+00:00
Publication: P1c7f61b693d245aab109ea0d9c6e32b3
Execution state: running
Research verdict: unassessed
Applicability: AT004 full restored preplace independently accepted; actual place Phase2.1.1.1 PBP running. Early SLL/USER_SLL_REG warnings independently bounded, no new stop gate. Fresh POST/locality/80 protections, actual P in SLR2, physopt/route and formal safety remain pending/OPEN.
Evidence:
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/started.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_PBP_warning_observed_facts_20261017.json
