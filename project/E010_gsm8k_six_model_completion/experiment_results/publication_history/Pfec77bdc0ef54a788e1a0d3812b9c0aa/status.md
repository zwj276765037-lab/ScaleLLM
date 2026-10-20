# E010：GPU0正常推进；加速候选待独审及独占GPU实测

execution_state: running
verdict: inconclusive

实测2026-10-18T18:32:42.248159+08:00，监督器PID13056存活，当前阶段smoke，组数smoke9/30、pilot0/30、formal0/30，正式0/39570。唯一项目worker [{"pid": 31810, "pid_exists": true, "model": "Llama-3.1-8B-Instruct", "case": "reference_qdq", "stage": "smoke", "gpu_uuid": "GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6", "worker_state": "starting", "n_completed": 0, "attempt": "/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity/smoke/Llama-3.1-8B-Instruct/reference_qdq/AT001"}]。失败0；当前原补测仍使用冻结R003慢校验，未热改。

本小时新增3组/12训练题，正式0；GPU1继续停用。GPU0出现外部yqh新attempt03 PID23186约12GiB计算占用，是旧已停attempt02后的不同进程/尝试；未操作该任务。总GPU利用率不能归给本项目，实际瞬时读数与客户端见本小时回执。

性能修复：A013独立候选实现与42项CPU验证已交付，父核源码及交付哈希；CPU单tensor合成10.281倍仅限该案例。A010独立源码审核已实际续派，CPU8–9/CUDA空；GPU benchmark和真实模型尚未执行，R003原始运行继续。候选路径preparation_20261018/integrity_performance_20261018/implementation/，A010审核输出independent_implementation_review_AT001/。真实GPU实测需原项目worker自然交接及外部GPU0任务释放，不能同时新开benchmark，也不因本通知停正常进程。后续接入必须新R/source/consumer证据冻结，全部检查频率、字节覆盖及原数学/生成/评分门保持。

下一步：继续原smoke，同时完成独立源码审；真实独占GPU0后才测pinned D2H、完整模型内存和速度，再决定新批次接入。此前两个月粗估仅适用于旧慢校验；新全量ETA仍未验证，暂不承诺。每小时提醒继续enabled，下次约北京时间19:30；最终完整39570条独立复算/来源绑定通过后才发布ACC并关闭提醒。M003/EDA/CPU0–7不触碰。


---
Published: 2026-10-18T10:33:13.150285+00:00
Publication: P054226b30875401c9350e1a3e2cb6621
Execution state: running
Research verdict: inconclusive
Applicability: R003 smoke9/30持续运行；加速候选CPU42项通过、独审已派发，GPU/端到端速度未测；GPU0有外部共享计算
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/hourly_reports/20261018T103242Z_gpu0_progress.json
