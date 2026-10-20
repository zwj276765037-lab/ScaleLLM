# E010：GPU0补测运行；完整性层性能缺陷修复准备

execution_state: running
verdict: inconclusive

实测2026-10-18T10:10:13.802015+00:00：R003 smoke/pilot/formal分别8/30、0/30、0/30，正式0/39570。当前worker [{"pid": 29244, "model": "Llama-3.1-8B-Instruct", "case": "a8w4_fp16", "state": "starting", "n_completed": 0}]；失败0。GPU0-only单worker继续；GPU1停用，M003/EDA不触碰。

用户明确拒绝约两个月速度，归因为新增完整性层每题两次完整GPU-D2H+CPU SHA256，而非原推理数学变慢。8B BF16四题生成7.724秒、总任务979.389秒；3B/8B每题非生成间隔45–47/105–106秒。旧选择题评估与GSM8K生成任务有固有差别，但不能解释当前校验主导的开销。此前两个月粗估仅属于此慢实现。

实际内部A013 /root/integrity_perf正在CPU18–19、CUDA空的独立候选实现/正负例；A010 /root/gsm8k_protocol在CPU8–9独立审查。候选目标保留原加载/QDQ SHA来源、逐题全部byte/名称/元数据/storage/_H_CACHE检查和原v2门，以可信不可变CPU bytes及复用chunk缓冲的精确比对避免逐题SHA。必须记录真实已比较字节与derived-hash证据，不能伪称重算SHA。现仅CPU准备，不热改R003冻结源码；替换必须新R和源冻结、实际独占交接、GPU验证后再判加速。当前无停止/切换指令执行，不因通知强停正常进程。

候选位置：project/software/0_Software/fix_experiment/results/gsm8k_full_completion/preparation_20261018/integrity_performance_20261018/implementation/；审核protocol_review_AT001.json/md在其父目录。后续小时报告应先核候选三摘要/实际CPU与GPU回执，不能把计划当已实现或未经测量就承诺完成时间。原每小时提醒继续enabled；最终完整正式复算通过后才能填ACC与均值。


---
Published: 2026-10-18T10:10:19.685054+00:00
Publication: P1c139f0e98544a67ae7dd53b3244222f
Execution state: running
Research verdict: inconclusive
Applicability: 原GPU0 R003继续运行；新增完整性层性能缺陷已归因，独立CPU候选修复进行中，尚未验证新速度
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/cause_and_candidate_status_20261018.json
- project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/user_feedback_and_repair_scope_20261018.json
- project/E010_gsm8k_six_model_completion/experiment_results/runtime_estimates/20261018T095754Z_gpu0_estimate.json
