# E010：GPU0补测持续运行，GPU1继续暂停

execution_state: running
verdict: inconclusive

实测2026-10-18T08:35:29.455816+00:00：监督器PID13056存活，当前阶段smoke，smoke/pilot/formal完成组数0/30、0/30、0/30；活动worker [{"pid": 13059, "model": "Llama-3.2-3B-Instruct", "case": "bf16", "state": "running", "n_completed": 3, "gpu_uuid": "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6"}]。失败记录0；正式完成及独立接受0/39570。启动时间北京时间16:29:20。

首组Llama-3.2-3B-Instruct/BF16原native-cache v2验证通过，已实际生成训练题；GPU0唯一worker持续执行内容/storage完整性门。15份冻结runtime源未改，全部30组smoke→pilot→formal按原监督器自动推进；正常无墙钟/静默强停。GPU1实验、诊断、维护继续暂停，M003/EDA/CPU0–7不触碰。重启后匹配系统nvidia-smi580.178.04可查询实际状态，旧私有工具不再适用本boot。

原cron服务active，原每小时提醒enabled=true，复用当前对话，下一次北京时间17:29:20；无重复定时器。后续读current_state.json、worker manifest/summary和实际系统nvidia-smi，不能复用启动时快照当最新进度。未完成pilot前不估计剩余时长。

最终复算入口已独立准备在protocol/R003_finalizer_readiness_candidate_AT001.json（ready=false，仅候选）。R003/finalizer_readiness.json必须保持缺失；生成完成后监督器以generated_pending_review收尾。工程父按候选parent_checklist独立核plan、formal_sources、frozen_contract及merged/source_manifest绑定，再串行执行复算→渲染→本地发布；这是工程检查，不需要新增用户批准。完整30组/39570题及全部完整性/来源校验通过后才回填结果表和六项平均，并结束每小时提醒。候选ready=false不得直接安装到R003，否则会使监督器报错。

恢复与实际证据：project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z；最终结果仍未完成。


---
Published: 2026-10-18T08:36:00.781370+00:00
Publication: P0fa0927b783a427a8fd78685d906c6d6
Execution state: running
Research verdict: inconclusive
Applicability: GPU0-only R003 smoke真实运行；GPU1暂停；新boot全30组资格与正式39570题仍待完成
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/startup_observed.json
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/launch_command_result.json
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/postreboot_environment.json
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/first_gpu_progress.json
- project/E010_gsm8k_six_model_completion/experiment_results/gpu0_resume/20261018T082458Z/resume_delivery.json
