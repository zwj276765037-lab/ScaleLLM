# E010：双GPU队列运行中

execution_state: running
verdict: unassessed

R002 AT001已原生启动，阶段smoke。权威动态状态：[/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R002_gsm8k_native_cache_v2/current_state.json](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/results/gsm8k_full_completion/R002_gsm8k_native_cache_v2/current_state.json)。监督器在资格门通过后自动推进pilot/formal；失败时停止新发并自然收尾已运行worker。正常无墙钟/静默强停。

CPU16–17/18–19，监督器14–15；保持M003 EDA CPU0–7。NVML仍失配，CUDA实际推理正常，系统驱动未改。尚无正式精度。当前摘要为阶段观察，动态状态以队列JSON/manifest为准，未承诺自动会话通知。


---
Published: 2026-10-18T02:25:51.020491+00:00
Publication: P4dee1f4819774fcb9fe4154753e10dd5
Execution state: running
Research verdict: unassessed
Applicability: R002双卡真实启动及smoke进行中；全量GSM8K待完成与独立复算
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/runs/R002/attempts/AT001_dual_gpu_native_cache_v2/evidence/supervisor_start_observed.json
- project/E010_gsm8k_six_model_completion/experiment_results/runs/R002/attempts/AT001_dual_gpu_native_cache_v2/evidence/gpu_inference_observed.json
- project/E010_gsm8k_six_model_completion/experiment_results/runs/R002/attempts/AT001_dual_gpu_native_cache_v2/evidence/cache_revision_evidence.json
