# GLM-4-9B-0414 结果来源

- 最终方法：`mlp_w4_scalecode`（Hadamard32、group-32、A8、Attention W8、MLP W4、ScaleCode）。
- `accuracy_scalecode_fullsplit.csv` 逐行复制自（换行统一为 LF）：
  `fpga_llm_project/results/0_Final_results/fix_accuracy/results/gyrot_aligned_accuracy/quality_accuracy_repaired/GLM-4-9B-0414__mlp_w4_scalecode/gyrot_aligned_quality_by_model.csv`
- `accuracy_bf16_fullsplit.csv` 逐行复制自（换行统一为 LF）：
  `fpga_llm_project/results/0_Final_results/fix_accuracy/results/gyrot_aligned_accuracy/quality_accuracy_repaired/GLM-4-9B-0414__original_bf16/gyrot_aligned_quality_by_model.csv`
- `accuracy_final_summary.csv` 从最终 `with_gsm8k_raw_observed` 表抽取 BF16 与 ScaleCode 两行。
- `ppl_wikitext2.csv` 从以下两个历史结果抽取并排整理：
  - BF16：`fpga_llm_project/results/All_results/ScalaPATH_4/S11_cross_model_portability/S11_E_quality_accuracy/GLM-4-9B-0414/quality_smoke_by_model.csv`
  - ScaleCode：`fpga_llm_project/results/All_results/accuracy_MLP_4bit/quality_accuracy/GLM-4-9B-0414__iah_scale_code_mlp_w4/quality_smoke_by_model.csv`

最终 repaired 表并入 GSM8K first-300：BF16=88.67%，ScaleCode=85.00%；具体替换来源见 _summary 下的 audit 文件。

选择题逐任务文件不包含 GSM8K；GSM8K 只出现在最终并表和审计链中。PPL 口径为 WikiText2、64 blocks、65,472 tokens，BF16 与 ScaleCode 均为 `records_complete=True`、`status=pass`。本归档保留 raw observed 数值，不做 display cap。
