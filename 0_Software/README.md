# ScaleLLM 最终软件与结果归档

`0_Software` 是对历史最终 ScaleCode 软件方法和 12 个模型 ACC/PPL 结果的集中整理，归档日期为 2026-09-10。原 `fpga_llm_project` 程序与结果全部保留，未移动、未覆盖。

## 最终确认的方法

```text
Hadamard32 + group-32
Activation: A8 unsigned asymmetric MinMax, no clipping
Attention Q/K/V/O: W8 signed symmetric
MLP Gate/Up/Down: W4 signed symmetric
Scale: uint8 code + uint8 shift
GLM gate_up_proj -> MLP W4
lm_head -> excluded
```

## 从哪里开始看

1. `introduction/01_final_scalecode_algorithm.md`：算法公式、位宽、分组和 clipping 核对要求。
2. `introduction/02_final_acc_ppl_results.md`：最终 12 模型 ACC/PPL 表和数据口径。
3. `introduction/03_reproduction_guide.md`：单模型复现方法和已知边界。
4. `experiment/`：最终量化与评测程序归档。
5. `results/`：按模型保存的历史最终结果及跨模型汇总。
6. `FPtoQ/`：验证常规 Host 激活在 Hadamard 前转换为 S24 Q8.16（仅 FPGA 内部 SwiGLU 乘积为 S32 Q16.16）的理论误差界、真实激活统计与完整 PPL A/B。

## 权威结果选择

- ACC：`fpga_llm_project/results/0_Final_results/.../gyrot_aligned_paper_style_table_with_gsm8k_raw_observed.csv`。
- PPL：不在 `0_Final_results`；已从 `fpga_llm_project/results/All_results` 的 BF16 与 `iah_scale_code_mlp_w4` 结果中核验归档。
- 不把 `fp_envelope_reported`、display cap 或 paired-loss 表当作原始推理结果。

最便于程序读取的两张总表是：

```text
results/_summary/final_accuracy_comparison.csv
results/_summary/final_scalecode_ppl_wikitext2.csv
```
