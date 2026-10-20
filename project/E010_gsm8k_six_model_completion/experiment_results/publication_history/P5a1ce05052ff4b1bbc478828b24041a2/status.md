# E010：GPU0单worker正常推进smoke

execution_state: running
verdict: inconclusive

实测2026-10-18T17:31:21.693346+08:00：smoke/pilot/formal分别6/30、0/30、0/30，正式0/39570。监督器PID13056存活；当前唯一worker [{"stage": "smoke", "model": "Llama-3.1-8B-Instruct", "case": "a8w8_fp32", "pid": 21749, "pid_exists": true, "gpu_uuid": "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6", "attempt": "/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/smoke/Llama-3.1-8B-Instruct/a8w8_fp32/AT001", "worker_state": "starting", "n_completed": 0, "started_at": "2026-10-18T09:29:39.502021+00:00"}]。无失败、无当前阻塞。GPU0初始化/校验期间瞬时利用率为0不等于任务停止；实时GPU读数见本小时原始记录。GPU1无计算任务，继续暂停。

本小时完成6组smoke、24道训练题，正式增量0。后续继续剩余smoke→30组pilot/重复性与长度门→formal；保持GPU0-only、CPU16–17、单worker、原资源锁和正常无墙钟/静默强停，不触碰M003或GPU1。未取得完整pilot实测，不给全量ETA。

每小时提醒enabled=true，下一次约北京时间18:30；仍复用原定时器及当前对话。最终R003/finalizer_readiness.json继续缺失，生成完成进入generated_pending_review；父工程按protocol/R003_finalizer_readiness_candidate_AT001.json的parent_checklist核plan/formal_sources/frozen_contract/source_manifest后独立复算→渲染→本地发布，不新增用户审批。完整验证并交付最终表格后关闭提醒。


---
Published: 2026-10-18T09:31:33.832163+00:00
Publication: Pa1fbea98af2c4a07a6f06fca3e93b8b8
Execution state: running
Research verdict: inconclusive
Applicability: R003新smoke6/30组已完成；GPU0第7组运行，GPU1停用；尚无正式GSM8K ACC
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/hourly_reports/20261018T093121Z_gpu0_progress.json
