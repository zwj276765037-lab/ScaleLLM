# 最终推理结果归档

本目录按 12 个最终模型分别归档 BF16 与 `mlp_w4_scalecode` 结果，并在 `_summary` 提供跨模型汇总。

每个模型目录包含：

- `accuracy_scalecode_fullsplit.csv`：最终 repaired 的 ScaleCode 逐任务 ACC 原始行，字段与数据行保持一致，换行统一为 LF。
- `accuracy_bf16_fullsplit.csv`：最终 repaired 的 BF16 逐任务 ACC 原始行，字段与数据行保持一致，换行统一为 LF。
- `accuracy_final_summary.csv`：该模型 BF16/ScaleCode 的最终并表行，包含 GSM8K 和 Avg。
- `ppl_wikitext2.csv`：BF16/ScaleCode 的 WikiText2 PPL 对照。
- `provenance.md`：结果来源和口径说明。

`_summary` 中的主要文件：

- `final_accuracy_comparison.csv`：12 模型 BF16 与 ScaleCode 的 ACC 并排比较及 Avg 差值。
- `final_scalecode_accuracy_raw_observed.csv`：只保留 ScaleCode 行的最终真实观测表。
- `final_scalecode_ppl_wikitext2.csv`：12 模型 PPL 及绝对/相对变化。
- `accuracy_raw_observed_merge_audit.csv`、`accuracy_gsm8k_kept_audit.csv`：GSM8K 修复与并表审计链。
- `source_manifest.csv`：各归档结果对应的原始路径和 SHA256。

最终 ACC 来源位于 `fpga_llm_project/results/0_Final_results`。PPL 不在该目录中，完整 PPL 原始结果位于 `fpga_llm_project/results/All_results`；本归档已将两处结果统一整理，但没有改动任何原始文件。

本目录采用 raw observed 数据，不采用 `fp_envelope_reported`、display cap 或 paired-loss 处理后的展示数值。
