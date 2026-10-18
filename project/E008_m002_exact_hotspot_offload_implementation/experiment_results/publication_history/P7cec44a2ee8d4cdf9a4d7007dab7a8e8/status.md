# E008：AT004实际place命令成功，完整POST运行中

execution_state: running
verdict: unassessed

12:17:58Z实际place_design SSI_SpreadSLLs自然native0、耗时7858秒，native明确completed successfully，已[独立核实](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/congestion_provisional_timing_review.md)。当前12:20Z仍在保存布局检查点/完整POST过程中；完整POST、80保护边界、成员reconciliation、全部实际P落SLR2、cut和时序尚未闭合，外层physopt/route未到。 Place46-14明确设计highly congested/may have difficulty routing，需保留布线困难风险；与旧同阶段原文相同，不提供候选效果、SLR1定量压力变化或已失败证据。内部30-746/46-19临时WNS+0.147（旧+0.103）均要求更准确report_timing，不能推导改善、setup/hold/PW/TNS或routed收敛。完整congestion报告在原POST中正常采集，不增设门或强停。

用户已解除PDU暂停，AT004北京时间17:23:05真实启动；C01→SLR2、b9dc/39源、144生产/父8451与已审完整restored preplace保持。较早USER_SLL_REG/SLL/clock-delay/BUFG提示的独立限定解释保留，原始输入保持不等于所有placer提示属性兑现。

下一步真实关闭完整place POST/locality，再自动独立physopt→route及各阶段全门；真实终态核输入/源/PID/start/lane/资源。同C01常规修复/独立delta/真实新AT连续重试委派保持，选型/架构/验收变化归Root。单EDA CPU0–7/nice5/max8，RSS192GiB/Mem48GiB30s/disk30GiB保护，正常无墙钟/静默强停；无bitstream/GPU/板卡/PPL/ACC。


---
Published: 2026-10-17T12:20:45.964291+00:00
Publication: P9eff92a4d9d64cd3b09ed755420a0e10
Execution state: running
Research verdict: unassessed
Applicability: AT004 true place native command0 independently verified (7858s); complete POST/locality still pending. High congestion warning retained; provisional WNS is not full timing. No qualified complete place, actual-P SLR2, outer physopt/route or formal signoff yet.
Evidence:
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/started.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_PBP_warning_observed_facts_20261017.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_postcommit_clock_BUFG_observed_facts_20261017.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_command_zero_POST_pending_facts_20261017.json
