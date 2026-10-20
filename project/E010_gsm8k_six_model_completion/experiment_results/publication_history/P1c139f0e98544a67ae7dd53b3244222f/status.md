# E010：GPU0单worker正常推进smoke

execution_state: running
verdict: inconclusive

实测2026-10-18T17:31:21.693346+08:00：smoke/pilot/formal分别6/30、0/30、0/30，正式0/39570。监督器PID13056存活；当前唯一worker [{"stage": "smoke", "model": "Llama-3.1-8B-Instruct", "case": "a8w8_fp32", "pid": 21749, "pid_exists": true, "gpu_uuid": "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6", "attempt": "/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/smoke/Llama-3.1-8B-Instruct/a8w8_fp32/AT001", "worker_state": "starting", "n_completed": 0, "started_at": "2026-10-18T09:29:39.502021+00:00"}]。无失败、无当前阻塞。GPU0初始化/校验期间瞬时利用率为0不等于任务停止；实时GPU读数见本小时原始记录。GPU1无计算任务，继续暂停。

本小时完成6组smoke、24道训练题，正式增量0。后续继续剩余smoke→30组pilot/重复性与长度门→formal；保持GPU0-only、CPU16–17、单worker、原资源锁和正常无墙钟/静默强停，不触碰M003或GPU1。未取得完整pilot实测，不给全量ETA。

每小时提醒enabled=true，下一次约北京时间18:30；仍复用原定时器及当前对话。最终R003/finalizer_readiness.json继续缺失，生成完成进入generated_pending_review；父工程按protocol/R003_finalizer_readiness_candidate_AT001.json的parent_checklist核plan/formal_sources/frozen_contract/source_manifest后独立复算→渲染→本地发布，不新增用户审批。完整验证并交付最终表格后关闭提醒。

北京时间17:57补充：smoke已7/30（Llama3.1/a8w8_fp32也已自然通过），当前继续Llama3.1/a8w4_fp32。用户要求估时后给出基于smoke的粗略规划：单GPU0按当前逐题全权重校验方式约两个月或更久；仅按checkpoint字节数外推的非生成检查成本约44.6天，完整pilot时长/正式长度分布均未实测，不能当作可靠截止日期。未改变任何冻结源、验收或GPU任务；后续小时报告应区分此粗估与完整pilot后更新的ETA。


---
Published: 2026-10-18T09:58:36.210000+00:00
Publication: P5a1ce05052ff4b1bbc478828b24041a2
Execution state: running
Research verdict: inconclusive
Applicability: R003 smoke7/30，GPU0持续运行；粗略成本外推已记录，正式ACC/全量ETA均未验证
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/hourly_reports/20261018T093121Z_gpu0_progress.json
- project/E010_gsm8k_six_model_completion/experiment_results/runtime_estimates/20261018T095754Z_gpu0_estimate.json
