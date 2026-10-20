# E010：GPU0补测运行中，GPU1继续暂停

execution_state: running
verdict: inconclusive

实测2026-10-18T08:30:57.499813+00:00：R003监督器PID13056、worker PID13059均存活，唯一active为GPU0 Llama-3.2-3B-Instruct/bf16，阶段smoke，worker状态starting，已完成题0/4。smoke/pilot/formal组数分别0/30、0/30、0/30；正式0/39570。实际GPU/CPU可见性及查询保存startup_observed.json。

重启后的启动预检与独立入口审核均通过；15份冻结runtime源未改。唯一GPU0队列自动按smoke→pilot→formal推进，长度、同卡独立进程重复性、内存和完整性门不放宽。若自然失败按合同保留原证据后排查。最终复算/发布仍待资格和数据全覆盖，不把启动或训练题作为正式ACC。

GPU1继续停用，不执行其诊断/维护或reset。M003/EDA/CPU0–7不触碰。原定时器已恢复enabled=true，复用当前对话，下一次北京时间17:29左右，每小时汇报一次；无重复定时器、无跨会话绑定。

运行实态优先读R003/current_state.json及各attempt manifest/summary。本次恢复记录：project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z。未完成pilot前不估计剩余时长。


---
Published: 2026-10-18T08:31:00.622651+00:00
Publication: P626a9a5e03f1431f93ad2b9f1aeb8796
Execution state: running
Research verdict: inconclusive
Applicability: GPU0-only R003 smoke真实运行；GPU1暂停；新boot全30组资格与正式39570题仍待完成
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/startup_observed.json
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/launch_command_result.json
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/postreboot_environment.json
