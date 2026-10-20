# E010：首轮失败已收尾，合同内诊断继续

execution_state: running
verdict: unassessed

R001 AT001终态failed，active=[]，未强停。两张GPU当前用于量化缓存数值路径诊断（a8w8_fp32/a8w4_fp32，保持原容差）。修正须重新冻结验证身份；正式test尚未开始。硬件M003及CPU0–7未触碰。NVML仍不可用，CUDA实测可运行。


---
Published: 2026-10-18T02:11:15.991462+00:00
Publication: Pee0038b7d03442acacbbe07697780a9e
Execution state: running
Research verdict: unassessed
Applicability: 首轮smoke与诊断；尚无正式GSM8K精度
Evidence:
- project/E010_gsm8k_six_model_completion/experiment_results/runs/R001/attempts/AT001_dual_gpu_gsm8k_pipeline/evidence/supervisor_terminal.json
