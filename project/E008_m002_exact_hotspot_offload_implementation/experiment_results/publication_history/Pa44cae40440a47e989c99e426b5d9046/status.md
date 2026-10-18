# E008：AT004运行中，真实place初始化

execution_state: running
verdict: unassessed

用户新的“可以继续了”已解除PDU暂停。AT004于北京时间17:23:05真实启动，当前父图恢复与实际成员子步骤已闭合并独立接受，资源/before策略与hard Pblock/真实XDC导出子步骤已独立接受，原策略保留及269完整端口索引/闭合alias已独立接受，本轮cut/timing及完整restored preplace实际门已闭合，10:07Z真实place SSI_SpreadSLLs已开始，10:08Z Phase1.2初始化。39源/b9dc、144输入/父8451、进程PID/start、CPU0–7/nice5与单EDA锁已核。[启动事实](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)。[完整preplace及真实place事实](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json)已保存；timing/global独立审核继续，place/physopt/route尚未完成。

AT003原始暂停/14项收尾/无新DCP证据保留；本次新AT从正式preplace父图重做原流程。原同C01常规修复登记与连续重试委派已恢复，不新增用户门；实质选型/架构/验收变化仍归Root。

正常无墙钟/无输出强停，单EDA及RSS192GiB/Mem48GiB30s/disk30GiB保护保持；无bitstream/GPU/板卡/PPL/ACC，旧工程只读。


---
Published: 2026-10-17T10:09:22.453028+00:00
Publication: P4d6d5deded0844af989fb2449cdba4f7
Execution state: running
Research verdict: unassessed
Applicability: AT004 complete restored preplace actually qualified, native Implementation/xcvu9p checkout succeeded and true place SSI_SpreadSLLs running. Independent timing/global preplace delta pending; physical stages not complete or signed off.
Evidence:
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/started.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/input_bindings.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/candidate_pre_place_native_port_index_closed_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/pre_place_closed_stage_facts.json
