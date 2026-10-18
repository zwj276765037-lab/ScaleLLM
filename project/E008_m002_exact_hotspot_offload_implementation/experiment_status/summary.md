# E008：AT004已自然失败结束，无活动EDA

execution_state: failed  
verdict: inconclusive

原生route 19:09:25Z失败：702396重叠节点、547548拥塞失败信号。五项失败诊断与失败locality已完成；21:18:30.695127Z监督自然结束，native1/supervisor1/stop_reason=null。完整place/physopt成功不代替route成功；失败图全局setup/hold/PW均FAIL，正式reset/CDC/IO OPEN。

工程14项终态收尾全true，144输入/冻结来源保持、PID/start消失、EDA锁释放；两个观察器均exit0、无活动进程。失败DCP和全部原始证据保持。A007独立终态审核已完成并接受工程收尾，工程证据整理及发布已完成；不重跑/不原样重试/不新AT。

[当前结果与集中证据](../experiment_results/summary.md) · [终态核验](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_summary.json)。此前running文字及逐阶段过程属于历史，见publication_history/raw。

此前running摘要因会话模型容量异常更新中断；本版已按原始终态回执校正。

[独立审核与工程最终交付](../experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_engineering_delivery_facts.json)。


---
Published: 2026-10-17T22:58:24.632449+00:00
Publication: P9e290ff193074fdb81e0b9242f3f822d
Execution state: failed
Research verdict: inconclusive
Applicability: AT004 natural illegal-route failure and engineering closure independently reviewed and accepted. Candidate9491 P allSLR2/locality established; complete legal route/setupholdPW/DRC/global routePOST/exact bus-skew coverage and formal safety not established. DCP hashes engineering-attributed; method inconclusive; no EDA/retry/newAT.
Evidence:
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/status.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_summary.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/observer_terminal_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/place_combined_independent_review_accepted_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/physopt_combined_independent_review_accepted_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/failed_route_terminal_facts.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/failed_route_terminal_summary.json
- project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/terminal_engineering_delivery_facts.json
