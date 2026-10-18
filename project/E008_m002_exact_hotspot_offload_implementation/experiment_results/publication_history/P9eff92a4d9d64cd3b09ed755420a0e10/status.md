# E008：AT004实际place后段优化运行中

execution_state: running
verdict: unassessed

用户“可以继续了”已解除PDU暂停，AT004于北京时间17:23:05实际启动；C01→SLR2、源b9dc/39、144生产/父8451及已独立接受的完整restored preplace保持。截至12:10Z，实际place已推进到Phase4.1.1.3 Post Placement Timing Optimization；RSS32.76GiB/MemAvailable461.43GiB/disk390.86GiB、CPU持续增长。全局放置和详细布局已在命令内部输出结束记录，当前仍是place_design内部优化；完整place命令/POST/locality尚未完成，未到外层phys_opt_design或route。

[新增clock/BUFG提示独立审核](../../../agent/A007/E008_R001_AT004_actual_stage_review_20261017/clock_bufg_message_contract_impact_review.md)：DDR0两网delay当前cap3/3、旧同阶段亦3/3，日志无单位，不推导skew/slack。BUFG提示实际为INFO：当前11候选/0插入/0复制/11冲突跳过，旧22/0/0/22但集合不同、精确交集9，不能判改善或C01因果。当前11均非字面C01，跳过自动插入不直接等于必需时钟缺失或未布通。无新增停点，保持原fresh POST/locality/80保护、全局clocks-DRC-timing-PW及适用skew、route验收。

较早PBP的10865/17280 SLL是全设计SLR1→2早期估计；USER_SLL_REG可见100对象后抑制、真实总量未知，原字节保持不等于placer兑现。旧不同边界数字不相减。

后续连续取得完整真实place POST/80保护/reconciliation/全部P落SLR2/cut/timing，再独立physopt与route。真实终态核输入/源/PID/start/lane/资源；同C01常规修复/独立delta/新AT重试委派保持，选型/架构/验收变化归Root。正常无墙钟/静默强停，单EDA CPU0–7/nice5/max8、RSS192GiB/Mem48GiB30s/disk30GiB保护；无bitstream/GPU/板卡/PPL/ACC。


---
Published: 2026-10-17T12:10:47.456497+00:00
Publication: P3403ea397f214c2cb5f02891d36ffac1
Execution state: running
Research verdict: unassessed
Applicability: AT004 full restored preplace independently accepted; actual place internal Phase4.1.1.3 optimization running. Warning scopes independently bounded; complete place POST/locality/80 protection/actual P in SLR2, outer physopt/route and formal safety pending/OPEN.
Evidence:
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/started.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_PBP_warning_observed_facts_20261017.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_postcommit_clock_BUFG_observed_facts_20261017.json
