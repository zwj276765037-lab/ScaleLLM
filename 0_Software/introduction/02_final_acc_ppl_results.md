# 最终 ScaleCode ACC / PPL 结果总结

## 1. 结论

本文件汇总历史已有结果，没有重新运行大模型。最终方法为 Hadamard32、group-32、A8、Attention W8、MLP W4、8-bit `code + shift` 的 `mlp_w4_scalecode`。

- 共整理 12 个模型。
- 以每个模型表中已报告的 `Avg` 计算，ScaleCode 相对 BF16 平均变化为 **-1.085 个百分点**。
- WikiText2 PPL 全部记录完整且状态为 `pass`；ScaleCode 相对 BF16 的平均绝对增量为 **+1.141478**，平均相对增量为 **+7.70%**。
- ACC 越高越好，PPL 越低越好。

## 2. ACC

数值单位均为百分比。PIQA、ARC-Challenge、OpenBookQA、HellaSwag、WinoGrande 使用完整验证集；GSM8K 为 first-300。`Avg` 在 GSM8K 有值时为 6 项平均，否则为前 5 项平均。

| Model | PIQA | ARC-c | OBQA | HellaS. | WinoG. | GSM8K | ScaleCode Avg | BF16 Avg | Δ Avg (pp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek-R1-Distill-Llama-8B | 59.63 | 24.41 | 26.80 | 47.12 | 50.28 | 60.67 | 44.82 | 46.42 | -1.60 |
| GLM-4-9B-0414 | 79.92 | 57.86 | 47.80 | 79.98 | 68.82 | 85.00 | 69.90 | 71.03 | -1.13 |
| Llama-3.1-8B | 79.98 | 53.85 | 45.40 | 77.56 | 70.24 | NA | 65.41 | 66.24 | -0.83 |
| Llama-3.1-8B-Instruct | 79.60 | 55.18 | 49.80 | 77.56 | 71.59 | 79.67 | 68.90 | 69.44 | -0.54 |
| Llama-3.2-1B-Instruct | 72.25 | 37.46 | 35.80 | 57.30 | 54.85 | NA | 51.53 | 53.20 | -1.67 |
| Llama-3.2-3B-Instruct | 76.17 | 43.81 | 37.80 | 68.15 | 61.25 | 67.33 | 59.09 | 60.65 | -1.56 |
| Mistral-7B-Instruct | 82.86 | 58.19 | 49.00 | 81.85 | 70.64 | NA | 68.51 | 68.67 | -0.16 |
| Qwen2.5-0.5B-Instruct | 70.57 | 29.77 | 35.60 | 49.61 | 51.62 | NA | 47.43 | 49.64 | -2.21 |
| Qwen2.5-1.5B-Instruct | 74.81 | 50.84 | 40.20 | 65.67 | 58.64 | NA | 58.03 | 58.72 | -0.69 |
| Qwen2.5-3B-Instruct | 78.56 | 51.17 | 47.00 | 72.02 | 62.43 | NA | 62.24 | 62.29 | -0.05 |
| Qwen2.5-7B-Instruct | 79.22 | 49.50 | 45.60 | 78.31 | 65.90 | 88.00 | 67.76 | 69.40 | -1.64 |
| Qwen3-8B | 78.35 | 54.52 | 43.40 | 72.21 | 64.33 | 88.67 | 66.91 | 67.85 | -0.94 |

逐任务平均变化为：PIQA -0.7800 pp、ARC-c -1.1425 pp、OpenBookQA -0.9333 pp、HellaSwag -1.2325 pp、WinoGrande -0.5467 pp；有 GSM8K 的 6 个模型平均变化为 -2.8317 pp。

### ACC 实际口径

| Task | 样本数 | 主指标 |
|---|---:|---|
| PIQA | 1,838 | `score_char_norm` |
| ARC-Challenge validation | 299 | `score_char_norm` |
| OpenBookQA validation | 500 | `score_char_norm` |
| HellaSwag validation | 10,042 | `score_char_norm` |
| WinoGrande dev | 1,267 | `score_sum` |
| GSM8K | 300 | 提取数值后的 exact match |

归档 runner 的旧 docstring/default 曾把 GyRot-aligned 集合写成包含 ARC-Easy、BoolQ；但最终 repaired 表实际采用上面五个选择题数据集，并加入 OpenBookQA。复现时必须显式传入任务列表，不能依赖旧默认值。

## 3. WikiText2 PPL

统一口径：WikiText2 test、block size 1024、stride 1024、64 blocks、65,472 个计分 token。

| Model | BF16 PPL | ScaleCode PPL | ΔPPL | 相对变化 |
|---|---:|---:|---:|---:|
| DeepSeek-R1-Distill-Llama-8B | 33.876374 | 38.663694 | +4.787320 | +14.13% |
| GLM-4-9B-0414 | 12.215040 | 12.443745 | +0.228706 | +1.87% |
| Llama-3.1-8B | 7.103704 | 7.593815 | +0.490111 | +6.90% |
| Llama-3.1-8B-Instruct | 8.252565 | 8.761913 | +0.509347 | +6.17% |
| Llama-3.2-1B-Instruct | 15.556676 | 17.454712 | +1.898035 | +12.20% |
| Llama-3.2-3B-Instruct | 13.087921 | 13.737469 | +0.649548 | +4.96% |
| Mistral-7B-Instruct | 6.775111 | 6.915713 | +0.140602 | +2.08% |
| Qwen2.5-0.5B-Instruct | 16.435293 | 17.939881 | +1.504589 | +9.15% |
| Qwen2.5-1.5B-Instruct | 11.241255 | 11.918522 | +0.677268 | +6.02% |
| Qwen2.5-3B-Instruct | 9.652969 | 11.493648 | +1.840679 | +19.07% |
| Qwen2.5-7B-Instruct | 9.222337 | 9.798556 | +0.576219 | +6.25% |
| Qwen3-8B | 11.132663 | 11.527980 | +0.395316 | +3.55% |

## 4. 数据来源与风险说明

最终 ACC 的权威源是：

```text
fpga_llm_project/results/0_Final_results/fix_accuracy/results/gyrot_aligned_accuracy/
summary_repaired/gyrot_aligned_paper_style_table_with_gsm8k_raw_observed.csv
```

选择 `raw_observed` 是为了保留真实推理观测值。没有采用 `fp_envelope_reported.csv`，因为后者包含 display cap/paired-loss 等展示处理，不能当作原始推理结果。

PPL 没有进入 `0_Final_results`。本次核验到的完整来源为：

```text
BF16:      fpga_llm_project/results/All_results/ScalaPATH_4/S11_cross_model_portability/S11_E_quality_accuracy/
ScaleCode: fpga_llm_project/results/All_results/accuracy_MLP_4bit/quality_accuracy/*__iah_scale_code_mlp_w4/
```

GSM8K 最终值来自历史 kept 表和后续 repaired/SDPA 重跑的并表，不是 12 个模型一次统一重跑的结果。只有 DeepSeek、GLM、Llama-3.1-8B-Instruct、Llama-3.2-3B-Instruct、Qwen2.5-7B-Instruct、Qwen3-8B 有最终 GSM8K 值；其余模型为 `NA`。具体替换链见 `results/_summary/accuracy_raw_observed_merge_audit.csv` 和 `accuracy_gsm8k_kept_audit.csv`。
